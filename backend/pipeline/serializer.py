"""
BPMN 2.0 XML Serializer with Full BPMNDI Diagram Interchange Support.
Generates compliant definitions, collaborations, participants, swimlanes,
typed flow nodes with strict XSD element ordering, sequence flows, message flows,
data objects, and BPMNDI shapes/edges.
"""

from __future__ import annotations
import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import Dict, List, Optional, Any, Set

from backend.version import VERSION
from backend.ir.models import ProcessIR, FlowNode, SequenceFlow, DataObject
from backend.pipeline.layout import DiagramLayout, Bounds, Waypoint
from backend.pipeline.validator import sanitize_ncname


BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
BPMNDI_NS = "http://www.omg.org/spec/BPMN/20100524/DI"
DC_NS = "http://www.omg.org/spec/DD/20100524/DC"
DI_NS = "http://www.omg.org/spec/DD/20100524/DI"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"

ELEMENT_TAG_MAPPING = {
    "startEvent": "startEvent",
    "endEvent": "endEvent",
    "intermediateTimerEvent": "intermediateCatchEvent",
    "intermediateMessageEvent": "intermediateCatchEvent",
    "task": "task",
    "userTask": "userTask",
    "serviceTask": "serviceTask",
    "manualTask": "manualTask",
    "sendTask": "sendTask",
    "receiveTask": "receiveTask",
    "exclusiveGateway": "exclusiveGateway",
    "parallelGateway": "parallelGateway",
    "inclusiveGateway": "inclusiveGateway",
    "subProcess": "subProcess",
    "callActivity": "callActivity",
}


def prettify_xml(elem: ET.Element) -> str:
    """Returns a pretty-printed XML string with declarations and indentation."""
    rough_string = ET.tostring(elem, encoding="utf-8")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ", encoding="UTF-8").decode("utf-8")


class BpmnXmlSerializer:
    """
    Serializes a ProcessIR and its computed DiagramLayout into valid BPMN 2.0 XML with BPMNDI.
    """

    def __init__(
        self,
        ir: ProcessIR,
        layout: DiagramLayout,
        profile_config: Optional[Dict[str, Any]] = None,
    ):
        self.ir = ir
        self.layout = layout
        self.profile = profile_config or {}

        # Profile preferences
        self.condition_loc = self.profile.get("conditionLocation", "conditionExpression")
        self.max_label_len = self.profile.get("maxLabelLength", 128)
        self.force_collab = self.profile.get("forceCollaboration", True)

    def serialize(self) -> str:
        # Register namespaces to prevent ns0 / ns1 prefixes
        ET.register_namespace("bpmn", BPMN_NS)
        ET.register_namespace("bpmndi", BPMNDI_NS)
        ET.register_namespace("dc", DC_NS)
        ET.register_namespace("di", DI_NS)
        ET.register_namespace("xsi", XSI_NS)

        definitions_attrib = {
            "id": sanitize_ncname(f"Definitions_{self.ir.id}", "Definitions"),
            "targetNamespace": "http://bpmn.io/schema/bpmn",
            "exporter": "Process2BPMN",
            "exporterVersion": VERSION,
        }

        # Add profile extension namespaces
        ext_namespaces = self.profile.get("extensionNamespaces", {})
        if isinstance(ext_namespaces, dict):
            for prefix, uri in ext_namespaces.items():
                if prefix and uri:
                    definitions_attrib[f"xmlns:{prefix}"] = uri

        root = ET.Element(f"{{{BPMN_NS}}}definitions", definitions_attrib)

        # Index incoming and outgoing flows per node
        incoming_map: Dict[str, List[str]] = {e.id: [] for e in self.ir.elements}
        outgoing_map: Dict[str, List[str]] = {e.id: [] for e in self.ir.elements}
        for f in self.ir.flows:
            if f.type == "sequence":
                if f.sourceId in outgoing_map:
                    outgoing_map[f.sourceId].append(f.id)
                if f.targetId in incoming_map:
                    incoming_map[f.targetId].append(f.id)

        # Determine multi-pool mode vs single-pool mode
        is_multi_pool = len(self.ir.pools) > 1
        has_pools = bool(self.ir.pools) or self.force_collab
        collaboration_id = sanitize_ncname(f"Collaboration_{self.ir.id}", "Collaboration")

        # 1. Collaboration & Participants & Message Flows
        if has_pools:
            collab_el = ET.SubElement(root, f"{{{BPMN_NS}}}collaboration", {"id": collaboration_id})
            for pool in self.ir.pools:
                proc_ref = sanitize_ncname(f"Process_{pool.id}", "Process") if is_multi_pool else self.ir.id
                ET.SubElement(
                    collab_el,
                    f"{{{BPMN_NS}}}participant",
                    {
                        "id": pool.id,
                        "name": self._truncate_label(pool.name),
                        "processRef": proc_ref,
                    }
                )

            # Message Flows in Collaboration
            for flow in self.ir.flows:
                if flow.type == "message":
                    flow_attrib = {
                        "id": flow.id,
                        "sourceRef": flow.sourceId,
                        "targetRef": flow.targetId,
                    }
                    if flow.name:
                        flow_attrib["name"] = self._truncate_label(flow.name)
                    ET.SubElement(collab_el, f"{{{BPMN_NS}}}messageFlow", flow_attrib)

        # 2. Process Elements
        if is_multi_pool:
            # Emit one process per pool
            for pool_idx, pool in enumerate(self.ir.pools):
                proc_id = sanitize_ncname(f"Process_{pool.id}", "Process")
                pool_lane_ids = {l.id for l in pool.lanes}
                pool_elements = [e for e in self.ir.elements if e.laneId in pool_lane_ids]
                pool_element_ids = {e.id for e in pool_elements}
                pool_flows = [
                    f for f in self.ir.flows
                    if f.type == "sequence" and f.sourceId in pool_element_ids
                ]

                process_el = ET.SubElement(
                    root,
                    f"{{{BPMN_NS}}}process",
                    {
                        "id": proc_id,
                        "name": self._truncate_label(pool.name),
                        "isExecutable": "false",
                    }
                )

                # Strictly ordered children per BPMN 2.0 XSD:
                # 1. laneSet
                if pool.lanes:
                    lane_set = ET.SubElement(
                        process_el,
                        f"{{{BPMN_NS}}}laneSet",
                        {"id": sanitize_ncname(f"LaneSet_{pool.id}", "LaneSet")}
                    )
                    for lane in pool.lanes:
                        lane_el = ET.SubElement(
                            lane_set,
                            f"{{{BPMN_NS}}}lane",
                            {"id": lane.id, "name": self._truncate_label(lane.name)}
                        )
                        for elem in pool_elements:
                            if elem.laneId == lane.id:
                                fn_ref = ET.SubElement(lane_el, f"{{{BPMN_NS}}}flowNodeRef")
                                fn_ref.text = elem.id

                # 2. flowElements (dataObjects, dataObjectReferences, flowNodes, sequenceFlows)
                if pool_idx == 0:
                    self._serialize_data_objects(process_el)

                for elem in pool_elements:
                    self._serialize_flow_node(process_el, elem, incoming_map, outgoing_map)

                for flow in pool_flows:
                    self._serialize_sequence_flow(process_el, flow)
        else:
            # Single Process
            process_el = ET.SubElement(
                root,
                f"{{{BPMN_NS}}}process",
                {
                    "id": self.ir.id,
                    "name": self._truncate_label(self.ir.name),
                    "isExecutable": "false",
                }
            )

            # Strictly ordered children per BPMN 2.0 XSD:
            # 1. documentation
            if self.ir.description:
                doc_el = ET.SubElement(process_el, f"{{{BPMN_NS}}}documentation")
                doc_el.text = self.ir.description

            # 2. laneSet
            if self.ir.pools and self.ir.pools[0].lanes:
                lane_set = ET.SubElement(
                    process_el,
                    f"{{{BPMN_NS}}}laneSet",
                    {"id": sanitize_ncname(f"LaneSet_{self.ir.id}", "LaneSet")}
                )
                for pool in self.ir.pools:
                    for lane in pool.lanes:
                        lane_el = ET.SubElement(
                            lane_set,
                            f"{{{BPMN_NS}}}lane",
                            {"id": lane.id, "name": self._truncate_label(lane.name)}
                        )
                        for elem in self.ir.elements:
                            if elem.laneId == lane.id:
                                fn_ref = ET.SubElement(lane_el, f"{{{BPMN_NS}}}flowNodeRef")
                                fn_ref.text = elem.id

            # 3. flowElements (dataObjects, dataObjectReferences, flowNodes, sequenceFlows)
            self._serialize_data_objects(process_el)

            for elem in self.ir.elements:
                self._serialize_flow_node(process_el, elem, incoming_map, outgoing_map)

            for flow in self.ir.flows:
                if flow.type == "sequence":
                    self._serialize_sequence_flow(process_el, flow)

        # 3. BPMNDI Section
        diagram_el = ET.SubElement(
            root,
            f"{{{BPMNDI_NS}}}BPMNDiagram",
            {"id": sanitize_ncname(f"BPMNDiagram_{self.ir.id}", "BPMNDiagram")}
        )
        plane_target = collaboration_id if has_pools else self.ir.id
        plane_el = ET.SubElement(
            diagram_el,
            f"{{{BPMNDI_NS}}}BPMNPlane",
            {"id": sanitize_ncname(f"BPMNPlane_{self.ir.id}", "BPMNPlane"), "bpmnElement": plane_target}
        )

        # 3a. Pool & Lane Shapes
        for pool_layout in self.layout.pools:
            pool_shape = ET.SubElement(
                plane_el,
                f"{{{BPMNDI_NS}}}BPMNShape",
                {
                    "id": sanitize_ncname(f"BPMNShape_{pool_layout.pool_id}", "BPMNShape"),
                    "bpmnElement": pool_layout.pool_id,
                    "isHorizontal": "true",
                }
            )
            self._add_bounds(pool_shape, pool_layout.bounds)

            for lane_layout in pool_layout.lanes:
                lane_shape = ET.SubElement(
                    plane_el,
                    f"{{{BPMNDI_NS}}}BPMNShape",
                    {
                        "id": sanitize_ncname(f"BPMNShape_{lane_layout.lane_id}", "BPMNShape"),
                        "bpmnElement": lane_layout.lane_id,
                        "isHorizontal": "true",
                    }
                )
                self._add_bounds(lane_shape, lane_layout.bounds)

        # 3b. Flow Node Shapes
        for elem in self.ir.elements:
            node_layout = self.layout.nodes.get(elem.id)
            if not node_layout:
                continue

            node_shape = ET.SubElement(
                plane_el,
                f"{{{BPMNDI_NS}}}BPMNShape",
                {
                    "id": sanitize_ncname(f"BPMNShape_{elem.id}", "BPMNShape"),
                    "bpmnElement": elem.id,
                }
            )
            self._add_bounds(node_shape, node_layout.bounds)

            if node_layout.label_bounds and elem.name:
                label_el = ET.SubElement(node_shape, f"{{{BPMNDI_NS}}}BPMNLabel")
                self._add_bounds(label_el, node_layout.label_bounds)

        # 3c. Data Object Shapes
        for do in getattr(self.ir, "dataObjects", []):
            do_ref_id = sanitize_ncname(f"DataObjectRef_{do.id}", "DataObjectRef")
            do_layout = self.layout.nodes.get(do_ref_id)
            if do_layout:
                do_shape = ET.SubElement(
                    plane_el,
                    f"{{{BPMNDI_NS}}}BPMNShape",
                    {
                        "id": sanitize_ncname(f"BPMNShape_{do_ref_id}", "BPMNShape"),
                        "bpmnElement": do_ref_id,
                    }
                )
                self._add_bounds(do_shape, do_layout.bounds)
                if do_layout.label_bounds and do.name:
                    label_el = ET.SubElement(do_shape, f"{{{BPMNDI_NS}}}BPMNLabel")
                    self._add_bounds(label_el, do_layout.label_bounds)

        # 3d. Flow Edges (Sequence Flows and Message Flows)
        for flow in self.ir.flows:
            edge_layout = self.layout.edges.get(flow.id)
            if not edge_layout:
                continue

            edge_el = ET.SubElement(
                plane_el,
                f"{{{BPMNDI_NS}}}BPMNEdge",
                {
                    "id": sanitize_ncname(f"BPMNEdge_{flow.id}", "BPMNEdge"),
                    "bpmnElement": flow.id,
                }
            )

            for wp in edge_layout.waypoints:
                ET.SubElement(
                    edge_el,
                    f"{{{DI_NS}}}waypoint",
                    {"x": f"{wp.x:.1f}", "y": f"{wp.y:.1f}"}
                )

            if edge_layout.label_bounds and (flow.name or flow.condition):
                label_el = ET.SubElement(edge_el, f"{{{BPMNDI_NS}}}BPMNLabel")
                self._add_bounds(label_el, edge_layout.label_bounds)

        return prettify_xml(root)

    def _serialize_data_objects(self, process_el: ET.Element) -> None:
        """Serializes ir.dataObjects as bpmn:dataObject + bpmn:dataObjectReference."""
        for do in getattr(self.ir, "dataObjects", []):
            do_id = sanitize_ncname(f"DataObject_{do.id}", "DataObject")
            do_ref_id = sanitize_ncname(f"DataObjectRef_{do.id}", "DataObjectRef")

            ET.SubElement(
                process_el,
                f"{{{BPMN_NS}}}dataObject",
                {"id": do_id, "isCollection": "false"}
            )
            ET.SubElement(
                process_el,
                f"{{{BPMN_NS}}}dataObjectReference",
                {
                    "id": do_ref_id,
                    "name": self._truncate_label(do.name),
                    "dataObjectRef": do_id,
                }
            )

    def _serialize_flow_node(
        self,
        parent: ET.Element,
        elem: FlowNode,
        incoming_map: Dict[str, List[str]],
        outgoing_map: Dict[str, List[str]],
    ) -> None:
        """
        Emits a FlowNode child element adhering strictly to the BPMN 2.0 XSD sequence:
        1. documentation
        2. extensionElements
        3. incoming*
        4. outgoing*
        5. event definitions (e.g. timerEventDefinition, messageEventDefinition)
        """
        tag_name = ELEMENT_TAG_MAPPING.get(elem.type, "task")
        elem_attrib = {
            "id": elem.id,
            "name": self._truncate_label(elem.name),
        }

        if elem.type in ("exclusiveGateway", "inclusiveGateway"):
            default_flow = next((f.id for f in self.ir.flows if f.sourceId == elem.id and f.isDefault), None)
            if default_flow:
                elem_attrib["default"] = default_flow

        node_el = ET.SubElement(parent, f"{{{BPMN_NS}}}{tag_name}", elem_attrib)

        # 1. documentation
        if elem.documentation:
            doc_el = ET.SubElement(node_el, f"{{{BPMN_NS}}}documentation")
            doc_el.text = elem.documentation

        # 2. incoming flows
        for inc_id in incoming_map.get(elem.id, []):
            inc_el = ET.SubElement(node_el, f"{{{BPMN_NS}}}incoming")
            inc_el.text = inc_id

        # 3. outgoing flows
        for out_id in outgoing_map.get(elem.id, []):
            out_el = ET.SubElement(node_el, f"{{{BPMN_NS}}}outgoing")
            out_el.text = out_id

        # 4. Event definitions (after incoming/outgoing per XSD inheritance)
        if elem.type == "intermediateTimerEvent":
            timer_id = sanitize_ncname(f"Timer_{elem.id}", "Timer")
            timer_def = ET.SubElement(node_el, f"{{{BPMN_NS}}}timerEventDefinition", {"id": timer_id})
            if getattr(elem, "timerDuration", None) and elem.timerDuration.strip():
                time_dur = ET.SubElement(
                    timer_def,
                    f"{{{BPMN_NS}}}timeDuration",
                    {f"{{{XSI_NS}}}type": "bpmn:tFormalExpression"}
                )
                time_dur.text = elem.timerDuration.strip()
        elif elem.type == "intermediateMessageEvent":
            msg_id = sanitize_ncname(f"Message_{elem.id}", "Message")
            ET.SubElement(node_el, f"{{{BPMN_NS}}}messageEventDefinition", {"id": msg_id})

    def _serialize_sequence_flow(self, parent: ET.Element, flow: SequenceFlow) -> None:
        flow_name = flow.name
        if self.condition_loc in ("flowName", "both") and flow.condition and not flow_name:
            flow_name = flow.condition

        flow_attrib = {
            "id": flow.id,
            "sourceRef": flow.sourceId,
            "targetRef": flow.targetId,
        }
        if flow_name:
            flow_attrib["name"] = self._truncate_label(flow_name)

        flow_el = ET.SubElement(parent, f"{{{BPMN_NS}}}sequenceFlow", flow_attrib)

        # Condition expression if requested
        if self.condition_loc in ("conditionExpression", "both") and flow.condition and not flow.isDefault:
            cond_el = ET.SubElement(
                flow_el,
                f"{{{BPMN_NS}}}conditionExpression",
                {f"{{{XSI_NS}}}type": "bpmn:tFormalExpression"}
            )
            cond_el.text = flow.condition

    def _add_bounds(self, parent: ET.Element, bounds: Bounds) -> None:
        ET.SubElement(
            parent,
            f"{{{DC_NS}}}Bounds",
            {
                "x": f"{bounds.x:.1f}",
                "y": f"{bounds.y:.1f}",
                "width": f"{bounds.width:.1f}",
                "height": f"{bounds.height:.1f}",
            }
        )

    def _truncate_label(self, label: str) -> str:
        if not label:
            return ""
        if len(label) > self.max_label_len:
            return label[:self.max_label_len - 3] + "..."
        return label
