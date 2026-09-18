"""
BPMN Reference Template Parser.
Safely parses BPMN 2.0 XML reference templates into TemplateSpec.
Enforces security: no XXE, size limits, external entity resolution disabled.
"""

from __future__ import annotations
import xml.etree.ElementTree as ET
import re
from typing import Dict, List, Tuple, Optional, Any
from backend.templates.models import (
    TemplateSpec,
    PoolMetric,
    LaneMetric,
    SkeletonNode,
    LayoutMetrics,
    TemplateDetectionReport
)
from backend.templates.profile_derivator import derive_profile_from_template

MAX_BPMN_FILE_SIZE = 15 * 1024 * 1024  # 15MB


def parse_safe_xml(xml_content: str) -> ET.Element:
    """
    Safely parses XML content.

    Any DOCTYPE / entity declaration is rejected outright: BPMN files never need one, and
    internal entity expansion ("billion laughs") is as much a denial-of-service vector as
    external entities are an exfiltration one. Parsing goes through ``defusedxml`` when it
    is installed (it is in requirements.txt); the DOCTYPE pre-check keeps the guarantee
    even if the dependency is missing.
    """
    if len(xml_content.encode("utf-8")) > MAX_BPMN_FILE_SIZE:
        raise ValueError(f"File exceeds maximum allowed size of {MAX_BPMN_FILE_SIZE // (1024 * 1024)}MB")

    head = xml_content[:4096].lstrip("\ufeff \t\r\n")
    if not head.startswith("<"):
        raise ValueError("Not an XML document")
    if re.search(r"<!\s*(DOCTYPE|ENTITY)", xml_content, re.IGNORECASE):
        raise ValueError(
            "Security violation: DOCTYPE and ENTITY declarations are not allowed in BPMN templates "
            "(XXE / entity-expansion protection)"
        )

    try:
        from defusedxml.ElementTree import fromstring as safe_fromstring  # type: ignore
        return safe_fromstring(xml_content, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except ImportError:
        return ET.fromstring(xml_content, parser=ET.XMLParser())


class BpmnTemplateParser:
    """
    Parses reference BPMN files into TemplateSpec and extracts structural patterns.
    """

    def __init__(self, template_id: str, name: str, xml_content: str):
        self.template_id = template_id
        self.name = name
        self.raw_xml = xml_content
        self.root: ET.Element = parse_safe_xml(xml_content)

    def parse(self) -> Tuple[TemplateSpec, TemplateDetectionReport]:
        # 1. Extract namespaces
        namespaces = self._extract_namespaces()
        
        # 2. Exporter and vendor attributes
        exporter = self.root.attrib.get("exporter")
        exporter_version = self.root.attrib.get("exporterVersion")
        target_namespace = self.root.attrib.get("targetNamespace")

        vendor_attrs = {
            k: v for k, v in self.root.attrib.items()
            if not k.startswith("xmlns") and k not in ("id", "name", "targetNamespace")
        }

        # 3. Detect vendor
        vendor = self._infer_vendor(namespaces, exporter)

        # 4. Extract BPMNDI bounds map: id -> (x, y, width, height)
        bounds_map = self._extract_di_bounds()

        # 5. Extract pools & lanes
        pools = self._extract_pools_and_lanes(bounds_map)

        # 6. Extract skeleton nodes (existing nodes to preserve)
        skeleton_nodes = self._extract_skeleton_nodes(bounds_map)

        # 7. Inferred ID pattern & layout metrics
        layout_metrics = self._infer_layout_metrics(pools, bounds_map)

        spec = TemplateSpec(
            template_id=self.template_id,
            name=self.name,
            source_vendor=vendor,
            namespaces=namespaces,
            exporter=exporter,
            exporter_version=exporter_version,
            target_namespace=target_namespace,
            vendor_definitions_attrs=vendor_attrs,
            pools=pools,
            skeleton_nodes=skeleton_nodes,
            layout_metrics=layout_metrics
        )

        derived = derive_profile_from_template(spec)
        spec.derived_profile_id = derived["profile_id"]

        report = TemplateDetectionReport(
            template_id=self.template_id,
            name=self.name,
            template_type="bpmn",
            vendor=vendor,
            detected_namespaces=list(namespaces.keys()),
            pools_count=len(pools),
            lanes=[
                {"id": l.id, "name": l.name, "order": l.order, "height": l.height}
                for p in pools for l in p.lanes
            ],
            skeleton_nodes=[
                {"id": s.id, "name": s.name, "type": s.type, "is_fixed": s.is_fixed}
                for s in skeleton_nodes
            ],
            valid_syntax=True,
            issues=[]
        )

        return spec, report

    def _extract_namespaces(self) -> Dict[str, str]:
        ns: Dict[str, str] = {}
        # Parse xmlns declarations from the raw root element string
        root_tag_match = re.search(r'<[^>]+>', self.raw_xml)
        if root_tag_match:
            first_tag = root_tag_match.group(0)
            matches = re.findall(r'xmlns:?([a-zA-Z0-9_\-\.]*)\s*=\s*["\']([^"\']+)["\']', first_tag)
            for prefix, uri in matches:
                ns[prefix if prefix else "default"] = uri
        return ns

    def _infer_vendor(self, namespaces: Dict[str, str], exporter: Optional[str]) -> str:
        ns_str = " ".join(namespaces.values()).lower()
        exp_str = (exporter or "").lower()
        if "camunda" in ns_str or "camunda" in exp_str:
            return "camunda"
        if "signavio" in ns_str or "signavio" in exp_str:
            return "signavio"
        if "aris" in ns_str or "aris" in exp_str or "ids-scheer" in ns_str:
            return "aris"
        if "celonis" in ns_str or "celonis" in exp_str:
            return "celonis"
        return "generic"

    def _extract_di_bounds(self) -> Dict[str, Dict[str, float]]:
        bounds_map: Dict[str, Dict[str, float]] = {}
        for elem in self.root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag == "BPMNShape":
                elem_id = elem.attrib.get("bpmnElement")
                if not elem_id:
                    continue
                for child in elem:
                    c_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                    if c_tag == "Bounds":
                        try:
                            bounds_map[elem_id] = {
                                "x": float(child.attrib.get("x", 0)),
                                "y": float(child.attrib.get("y", 0)),
                                "width": float(child.attrib.get("width", 0)),
                                "height": float(child.attrib.get("height", 0)),
                            }
                        except (ValueError, TypeError):
                            pass
        return bounds_map

    def _extract_pools_and_lanes(self, bounds_map: Dict[str, Dict[str, float]]) -> List[PoolMetric]:
        pools: List[PoolMetric] = []
        # Find collaborations and participants
        participants: Dict[str, Tuple[str, str]] = {}  # part_id -> (process_ref, name)
        for elem in self.root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag == "participant":
                pid = elem.attrib.get("id", "")
                name = elem.attrib.get("name", "Pool")
                pref = elem.attrib.get("processRef", "")
                if pid:
                    participants[pid] = (pref, name)

        # Find process and laneSets
        for elem in self.root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag == "process":
                proc_id = elem.attrib.get("id", "")
                # Find matching participant
                part_id = ""
                pool_name = "Default Pool"
                for pid, (pref, pname) in participants.items():
                    if pref == proc_id or not part_id:
                        part_id = pid
                        pool_name = pname
                if not part_id:
                    part_id = f"Participant_{proc_id}"

                pool_bounds = bounds_map.get(part_id, {"x": 100.0, "y": 80.0, "width": 1280.0, "height": 540.0})

                lanes: List[LaneMetric] = []
                lane_order = 0
                for child in elem.iter():
                    c_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                    if c_tag == "lane":
                        lid = child.attrib.get("id", f"Lane_{lane_order+1}")
                        lname = child.attrib.get("name", f"Lane {lane_order+1}")
                        lbounds = bounds_map.get(lid, {"height": 180.0, "y": 80.0 + lane_order * 180.0})
                        lanes.append(
                            LaneMetric(
                                id=lid,
                                name=lname,
                                order=lane_order,
                                height=lbounds.get("height", 180.0),
                                y_offset=lbounds.get("y", 80.0)
                            )
                        )
                        lane_order += 1

                pools.append(
                    PoolMetric(
                        id=part_id,
                        name=pool_name,
                        x=pool_bounds.get("x", 100.0),
                        y=pool_bounds.get("y", 80.0),
                        width=pool_bounds.get("width", 1280.0),
                        height=pool_bounds.get("height", 540.0),
                        lanes=lanes
                    )
                )

        # If no explicit pool found, create a sensible default
        if not pools:
            pools.append(
                PoolMetric(
                    id="Participant_1",
                    name="Default Process",
                    x=100.0,
                    y=80.0,
                    width=1280.0,
                    height=540.0,
                    lanes=[]
                )
            )

        return pools

    def _extract_skeleton_nodes(self, bounds_map: Dict[str, Dict[str, float]]) -> List[SkeletonNode]:
        """
        Extracts pre-existing nodes such as fixed start/end events, boundary events,
        or pre-modeled phase sub-processes that should be preserved.
        """
        skeleton_types = {
            "startEvent", "endEvent", "subProcess", "callActivity",
            "boundaryEvent", "intermediateCatchEvent", "intermediateThrowEvent"
        }
        nodes: List[SkeletonNode] = []
        for elem in self.root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag in skeleton_types:
                nid = elem.attrib.get("id", "")
                if not nid:
                    continue
                name = elem.attrib.get("name", "")
                b = bounds_map.get(nid, {"x": 180.0, "y": 150.0, "width": 36.0, "height": 36.0})

                incomings = [c.text.strip() for c in elem if c.tag.endswith("incoming") and c.text]
                outgoings = [c.text.strip() for c in elem if c.tag.endswith("outgoing") and c.text]

                nodes.append(
                    SkeletonNode(
                        id=nid,
                        type=tag,
                        name=name,
                        bounds=b,
                        is_fixed=True,
                        incoming_flows=incomings,
                        outgoing_flows=outgoings
                    )
                )
        return nodes

    def _infer_layout_metrics(
        self,
        pools: List[PoolMetric],
        bounds_map: Dict[str, Dict[str, float]]
    ) -> LayoutMetrics:
        metrics = LayoutMetrics()
        # Inferred ID patterns (e.g. Activity_XXXX or Signavio / Camunda formats)
        all_ids = [k for k in bounds_map.keys()]
        if all_ids:
            if all(re.match(r"^[A-Za-z0-9_]+$", id_) for id_ in all_ids):
                metrics.id_pattern = r"^[A-Za-z0-9_]+$"
        
        # Check task dimensions
        task_widths = []
        task_heights = []
        for b in bounds_map.values():
            w = b.get("width", 0)
            h = b.get("height", 0)
            if 70 <= w <= 160 and 40 <= h <= 120:
                task_widths.append(w)
                task_heights.append(h)

        if task_widths:
            metrics.default_task_width = float(sum(task_widths) / len(task_widths))
        if task_heights:
            metrics.default_task_height = float(sum(task_heights) / len(task_heights))

        # Check lane heights
        lane_heights = [l.height for p in pools for l in p.lanes if l.height > 0]
        if lane_heights:
            metrics.default_lane_height = float(sum(lane_heights) / len(lane_heights))

        return metrics
