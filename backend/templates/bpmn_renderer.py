"""
BPMN Template Renderer.
Renders extracted ProcessIR directly into a copy of a reference BPMN XML template.
Preserves vendor namespaces, definitions attributes, extension elements, pools, lanes,
and skeleton nodes while injecting new elements and computed BPMNDI layout bounds.
"""

from __future__ import annotations
import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import Dict, List, Optional, Any
from copy import deepcopy

from backend.ir.models import ProcessIR, FlowNode, SequenceFlow
from backend.pipeline.layout import DiagramLayout, Bounds, Waypoint
from backend.templates.models import TemplateSpec
from backend.templates.bpmn_parser import parse_safe_xml
from backend.pipeline.serializer import ELEMENT_TAG_MAPPING, BPMN_NS, BPMNDI_NS, DC_NS, DI_NS


class BpmnTemplateRenderer:
    """
    Writes into a reference BPMN template XML document, replacing/injecting elements
    while strictly preserving vendor extensions, namespaces, and skeleton nodes.
    """

    def __init__(
        self,
        template_raw_xml: str,
        spec: TemplateSpec,
        ir: ProcessIR,
        layout: DiagramLayout,
        profile_config: Optional[Dict[str, Any]] = None
    ):
        self.template_raw_xml = template_raw_xml
        self.spec = spec
        self.ir = ir
        self.layout = layout
        self.profile = profile_config or {}

    def render(self) -> str:
        root = parse_safe_xml(self.template_raw_xml)

        # Register standard namespaces with xml.etree
        ET.register_namespace("bpmn", BPMN_NS)
        ET.register_namespace("bpmndi", BPMNDI_NS)
        ET.register_namespace("dc", DC_NS)
        ET.register_namespace("di", DI_NS)
        for prefix, uri in self.spec.namespaces.items():
            if prefix and prefix not in ("bpmn", "bpmndi", "dc", "di", "default"):
                try:
                    ET.register_namespace(prefix, uri)
                except Exception:
                    pass

        # 1. Locate main process element
        process_elem = None
        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag == "process":
                process_elem = elem
                break

        if process_elem is None:
            # Create a process element if not found
            process_elem = ET.SubElement(root, f"{{{BPMN_NS}}}process", {
                "id": self.ir.id or "Process_1",
                "name": self.ir.name or "Business Process",
                "isExecutable": "false"
            })

        # 2. Get skeleton node IDs to preserve
        skeleton_ids = {s.id for s in self.spec.skeleton_nodes if s.is_fixed}

        # Clear existing non-skeleton flow nodes and flows from process
        children_to_remove = []
        for child in process_elem:
            c_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            c_id = child.attrib.get("id", "")
            if c_tag in (
                "task", "userTask", "serviceTask", "manualTask", "sendTask",
                "receiveTask", "exclusiveGateway", "parallelGateway", "inclusiveGateway",
                "sequenceFlow"
            ) and c_id not in skeleton_ids:
                children_to_remove.append(child)

        for child in children_to_remove:
            process_elem.remove(child)

        # 3. Add FlowNodes from IR
        lane_node_refs: Dict[str, List[str]] = {}
        for elem in self.ir.elements:
            if elem.id in skeleton_ids:
                continue

            tag_name = ELEMENT_TAG_MAPPING.get(elem.type, "task")
            node_attrib = {
                "id": elem.id,
                "name": elem.name or ""
            }
            elem_xml = ET.SubElement(process_elem, f"{{{BPMN_NS}}}{tag_name}", node_attrib)

            if elem.documentation:
                doc_xml = ET.SubElement(elem_xml, f"{{{BPMN_NS}}}documentation")
                doc_xml.text = elem.documentation

            # Incoming / outgoing sequences
            incomings = [f.id for f in self.ir.flows if f.targetId == elem.id]
            outgoings = [f.id for f in self.ir.flows if f.sourceId == elem.id]

            for inc in incomings:
                inc_xml = ET.SubElement(elem_xml, f"{{{BPMN_NS}}}incoming")
                inc_xml.text = inc

            for out in outgoings:
                out_xml = ET.SubElement(elem_xml, f"{{{BPMN_NS}}}outgoing")
                out_xml.text = out

            # Track for lane association
            target_lane = elem.laneId
            if self.ir.templateBindings and elem.laneId in self.ir.templateBindings.laneMap:
                target_lane = self.ir.templateBindings.laneMap[elem.laneId]

            if target_lane:
                lane_node_refs.setdefault(target_lane, []).append(elem.id)

        # 4. Add SequenceFlows from IR
        for flow in self.ir.flows:
            flow_attrib = {
                "id": flow.id,
                "sourceRef": flow.sourceId,
                "targetRef": flow.targetId
            }
            if flow.name:
                flow_attrib["name"] = flow.name

            flow_xml = ET.SubElement(process_elem, f"{{{BPMN_NS}}}sequenceFlow", flow_attrib)

            if flow.condition:
                cond_xml = ET.SubElement(
                    flow_xml,
                    f"{{{BPMN_NS}}}conditionExpression",
                    {"xsi:type": "bpmn:tFormalExpression"}
                )
                cond_xml.text = flow.condition

        # 5. Update Lane flowNodeRefs in template laneSets
        for elem in process_elem.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag == "lane":
                lid = elem.attrib.get("id", "")
                if lid in lane_node_refs:
                    existing_refs = {
                        c.text.strip() for c in elem
                        if c.tag.endswith("flowNodeRef") and c.text
                    }
                    for nid in lane_node_refs[lid]:
                        if nid not in existing_refs:
                            ref_xml = ET.SubElement(elem, f"{{{BPMN_NS}}}flowNodeRef")
                            ref_xml.text = nid

        # 6. Update BPMNDI Diagram and Plane
        self._update_bpmndi(root, skeleton_ids)

        rough_string = ET.tostring(root, encoding="utf-8")
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ", encoding="UTF-8").decode("utf-8")

    def _update_bpmndi(self, root: ET.Element, skeleton_ids: set):
        plane_elem = None
        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag == "BPMNPlane":
                plane_elem = elem
                break

        if plane_elem is None:
            diag_elem = ET.SubElement(root, f"{{{BPMNDI_NS}}}BPMNDiagram", {"id": "BPMNDiagram_1"})
            plane_elem = ET.SubElement(
                diag_elem,
                f"{{{BPMNDI_NS}}}BPMNPlane",
                {"id": "BPMNPlane_1", "bpmnElement": self.ir.id}
            )

        # Remove existing BPMNShape / BPMNEdge unless it belongs to skeleton or pool/lane
        shapes_to_remove = []
        for child in plane_elem:
            c_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            elem_ref = child.attrib.get("bpmnElement", "")
            if c_tag in ("BPMNShape", "BPMNEdge"):
                # Preserve pools, lanes, and skeleton nodes
                is_pool_or_lane = any(
                    elem_ref == p.id or any(elem_ref == l.id for l in p.lanes)
                    for p in self.spec.pools
                )
                if not is_pool_or_lane and elem_ref not in skeleton_ids:
                    shapes_to_remove.append(child)

        for child in shapes_to_remove:
            plane_elem.remove(child)

        # Add BPMNShapes for new elements
        for elem_id, node_layout in self.layout.nodes.items():
            if elem_id in skeleton_ids:
                continue

            shape_elem = ET.SubElement(
                plane_elem,
                f"{{{BPMNDI_NS}}}BPMNShape",
                {"id": f"BPMNShape_{elem_id}", "bpmnElement": elem_id}
            )
            ET.SubElement(
                shape_elem,
                f"{{{DC_NS}}}Bounds",
                {
                    "x": str(node_layout.bounds.x),
                    "y": str(node_layout.bounds.y),
                    "width": str(node_layout.bounds.width),
                    "height": str(node_layout.bounds.height)
                }
            )

            if node_layout.label_bounds:
                label_elem = ET.SubElement(shape_elem, f"{{{BPMNDI_NS}}}BPMNLabel")
                ET.SubElement(
                    label_elem,
                    f"{{{DC_NS}}}Bounds",
                    {
                        "x": str(node_layout.label_bounds.x),
                        "y": str(node_layout.label_bounds.y),
                        "width": str(node_layout.label_bounds.width),
                        "height": str(node_layout.label_bounds.height)
                    }
                )

        # Add BPMNEdges for flows
        for flow_id, edge_layout in self.layout.edges.items():
            edge_elem = ET.SubElement(
                plane_elem,
                f"{{{BPMNDI_NS}}}BPMNEdge",
                {"id": f"BPMNEdge_{flow_id}", "bpmnElement": flow_id}
            )
            for wp in edge_layout.waypoints:
                ET.SubElement(
                    edge_elem,
                    f"{{{DI_NS}}}waypoint",
                    {"x": str(wp.x), "y": str(wp.y)}
                )

            if edge_layout.label_bounds:
                label_elem = ET.SubElement(edge_elem, f"{{{BPMNDI_NS}}}BPMNLabel")
                ET.SubElement(
                    label_elem,
                    f"{{{DC_NS}}}Bounds",
                    {
                        "x": str(edge_layout.label_bounds.x),
                        "y": str(edge_layout.label_bounds.y),
                        "width": str(edge_layout.label_bounds.width),
                        "height": str(edge_layout.label_bounds.height)
                    }
                )
