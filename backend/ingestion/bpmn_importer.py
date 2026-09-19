"""
BPMN 2.0 Import.

Reads a ``.bpmn`` / BPMN 2.0 ``.xml`` file exported from another modelling tool
(Camunda Modeler, SAP Signavio, ARIS, Bizagi, Flowable, bpmn.io, Celonis) and turns it into
a Process IR, so it can be re-exported as Celonis-ready or generic BPMN 2.0.

Two things make this different from the reference-template parser next door
(``backend/templates/bpmn_parser.py``, whose safe-XML reader this module reuses):

* it extracts the **whole graph** — every flow node, sequence flow, lane and pool — rather
  than a structural skeleton;
* vendor namespaces and extension elements are **dropped on the floor**. Nothing outside the
  BPMN 2.0 MODEL and DI namespaces is read, so nothing vendor-specific can survive into the
  IR. The re-export is built from the IR alone.

Element types outside the IR's vocabulary are mapped to the closest supported type and
reported as warnings; nothing is silently invented.

Diagram interchange (DI) coordinates are preserved when the file carries them, so an imported
diagram looks like it did in the tool it came from. The caller can ask for a fresh Sugiyama
layout instead (``relayout=True`` on the endpoint, ``--relayout`` on the CLI).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.ir.models import (
    NCNAME_REGEX,
    FlowNode,
    Lane,
    Pool,
    ProcessIR,
    SequenceFlow,
)
from backend.pipeline.layout import (
    Bounds,
    DiagramLayout,
    EdgeLayout,
    LaneLayout,
    NodeLayout,
    PoolLayout,
    Waypoint,
    get_default_element_dimensions,
)
from backend.templates.bpmn_parser import parse_safe_xml

logger = logging.getLogger(__name__)

BPMN_EXTENSIONS = (".bpmn", ".bpmn2", ".bpmn20.xml", ".xml")

#: Foreign BPMN tags that map straight onto an IR element type.
DIRECT_TYPE_MAP: Dict[str, str] = {
    "startEvent": "startEvent",
    "endEvent": "endEvent",
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

#: Tags the IR has no equivalent for. Each maps to the nearest supported type, and every
#: substitution is reported so the person can see what changed.
APPROXIMATED_TYPE_MAP: Dict[str, Tuple[str, str]] = {
    "businessRuleTask": ("serviceTask", "business rule task"),
    "scriptTask": ("serviceTask", "script task"),
    "transaction": ("subProcess", "transaction"),
    "adHocSubProcess": ("subProcess", "ad-hoc sub-process"),
    "eventBasedGateway": ("exclusiveGateway", "event-based gateway"),
    "complexGateway": ("inclusiveGateway", "complex gateway"),
}

#: Tags that are dropped entirely, with a warning.
SKIPPED_TAGS = {
    "boundaryEvent",
    "intermediateThrowEvent",
}

EVENT_DEFINITION_TIMER = "timerEventDefinition"
EVENT_DEFINITION_MESSAGE = "messageEventDefinition"


@dataclass
class ImportReport:
    """What the importer found and what it had to change."""

    source_vendor: str = "generic"
    exporter: str = ""
    original_layout: bool = False
    element_count: int = 0
    flow_count: int = 0
    pool_count: int = 0
    lane_count: int = 0
    stripped_namespaces: List[str] = field(default_factory=list)
    stripped_extensions: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_vendor": self.source_vendor,
            "exporter": self.exporter,
            "original_layout": self.original_layout,
            "element_count": self.element_count,
            "flow_count": self.flow_count,
            "pool_count": self.pool_count,
            "lane_count": self.lane_count,
            "stripped_namespaces": self.stripped_namespaces,
            "stripped_extensions": self.stripped_extensions,
            "warnings": self.warnings,
        }


class BpmnImportError(ValueError):
    """Raised when a file is not usable BPMN 2.0."""


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _namespace(tag: str) -> str:
    return tag.split("}")[0].lstrip("{") if "}" in tag else ""


def looks_like_bpmn(filename: str, raw: bytes) -> bool:
    """True when the name and the first bytes both point at a BPMN 2.0 document."""
    name = filename.lower()
    if not any(name.endswith(ext) for ext in BPMN_EXTENSIONS):
        return False
    head = raw[:4096].decode("utf-8", errors="ignore").lower()
    return "bpmn" in head and "definitions" in head


def sanitize_id(raw_id: str, fallback_prefix: str, used: Dict[str, str]) -> str:
    """
    Returns an NCName-safe id, stable per source id.

    Foreign exporters emit ids the IR rejects — leading digits, spaces, GUID braces. The
    mapping is kept so sequence flows can be rewired to the renamed nodes.
    """
    if raw_id in used:
        return used[raw_id]

    candidate = re.sub(r"[^a-zA-Z0-9_.-]", "_", raw_id or "")
    if not candidate or not NCNAME_REGEX.match(candidate):
        candidate = f"{fallback_prefix}_{len(used) + 1}"
        if not NCNAME_REGEX.match(candidate):  # pragma: no cover - prefix is always safe
            candidate = f"Node_{len(used) + 1}"

    existing = set(used.values())
    if candidate in existing:
        suffix = 2
        while f"{candidate}_{suffix}" in existing:
            suffix += 1
        candidate = f"{candidate}_{suffix}"

    used[raw_id] = candidate
    return candidate


class BpmnImporter:
    """Parses one BPMN 2.0 document into a ProcessIR plus its original layout."""

    def __init__(self, xml_content: str, filename: str = "imported.bpmn"):
        self.raw_xml = xml_content
        self.filename = filename
        self.root = parse_safe_xml(xml_content)
        if _local(self.root.tag) != "definitions":
            raise BpmnImportError(
                "This file is not a BPMN 2.0 document (its root element is "
                f"'{_local(self.root.tag)}', expected 'definitions')."
            )
        self.report = ImportReport()
        self.id_map: Dict[str, str] = {}

    # ------------------------------------------------------------------ public API
    def parse(self) -> Tuple[ProcessIR, Optional[DiagramLayout], ImportReport]:
        namespaces = self._extract_namespaces()
        self.report.exporter = self.root.attrib.get("exporter", "")
        self.report.source_vendor = self._infer_vendor(namespaces, self.report.exporter)
        self.report.stripped_namespaces = self._vendor_namespaces(namespaces)
        self.report.stripped_extensions = self._extension_elements()

        processes = [e for e in self.root.iter() if _local(e.tag) == "process"]
        if not processes:
            raise BpmnImportError("The file contains no <process> element, so there is nothing to import.")

        participants = self._participants()
        elements, lane_of_element = self._extract_elements(processes)
        if not elements:
            raise BpmnImportError("The file contains no flow nodes (tasks, events or gateways).")

        pools = self._extract_pools(processes, participants, lane_of_element)
        flows = self._extract_flows(processes, {e.id for e in elements})

        ir = ProcessIR(
            id=sanitize_id(processes[0].attrib.get("id", "Process_1"), "Process", {}),
            name=self._process_name(processes[0], participants),
            description=f"Imported from {Path(self.filename).name}",
            pools=pools,
            elements=elements,
            flows=flows,
        )

        self.report.element_count = len(elements)
        self.report.flow_count = len(flows)
        self.report.pool_count = len(pools)
        self.report.lane_count = sum(len(p.lanes) for p in pools)

        layout = self._extract_layout(ir)
        self.report.original_layout = layout is not None

        return ir, layout, self.report

    # ------------------------------------------------------------------ namespaces / vendor
    def _extract_namespaces(self) -> Dict[str, str]:
        """
        Reads the xmlns declarations off the root element.

        The XML declaration (``<?xml …?>``) and any leading comment are skipped — matching the
        first ``<…>`` in the document would otherwise return the processing instruction and
        report a file as having no namespaces at all.
        """
        ns: Dict[str, str] = {}
        without_pi = re.sub(r"<\?.*?\?>", "", self.raw_xml, flags=re.S)
        without_comments = re.sub(r"<!--.*?-->", "", without_pi, flags=re.S)
        root_tag_match = re.search(r"<[a-zA-Z][^>]*>", without_comments, re.S)
        if root_tag_match:
            for prefix, uri in re.findall(
                r'xmlns:?([a-zA-Z0-9_\-\.]*)\s*=\s*["\']([^"\']+)["\']', root_tag_match.group(0)
            ):
                ns[prefix or "default"] = uri
        return ns

    @staticmethod
    def _infer_vendor(namespaces: Dict[str, str], exporter: Optional[str]) -> str:
        ns_str = " ".join(namespaces.values()).lower()
        exp_str = (exporter or "").lower()
        for needle, vendor in (
            ("camunda", "camunda"),
            ("signavio", "signavio"),
            ("ids-scheer", "aris"),
            ("aris", "aris"),
            ("celonis", "celonis"),
            ("bizagi", "bizagi"),
            ("flowable", "flowable"),
            ("activiti", "flowable"),
        ):
            if needle in ns_str or needle in exp_str:
                return vendor
        return "generic"

    @staticmethod
    def _vendor_namespaces(namespaces: Dict[str, str]) -> List[str]:
        standard = (
            "omg.org/spec/BPMN",
            "omg.org/spec/DD",
            "www.w3.org/2001/XMLSchema",
            "www.omg.org/spec/BPMN",
            "www.omg.org/spec/DD",
        )
        return sorted(
            uri for uri in namespaces.values() if not any(s in uri for s in standard)
        )

    def _extension_elements(self) -> List[str]:
        found: List[str] = []
        for elem in self.root.iter():
            if _local(elem.tag) != "extensionElements":
                continue
            for child in elem:
                label = _local(child.tag)
                prefix = _namespace(child.tag)
                entry = f"{label} ({prefix})" if prefix else label
                if entry not in found:
                    found.append(entry)
        return sorted(found)

    # ------------------------------------------------------------------ graph
    def _participants(self) -> Dict[str, Tuple[str, str]]:
        """process id -> (participant id, pool name)"""
        by_process: Dict[str, Tuple[str, str]] = {}
        for elem in self.root.iter():
            if _local(elem.tag) == "participant":
                pref = elem.attrib.get("processRef", "")
                if pref:
                    by_process[pref] = (elem.attrib.get("id", ""), elem.attrib.get("name", "Pool"))
        return by_process

    def _process_name(self, process: Any, participants: Dict[str, Tuple[str, str]]) -> str:
        proc_id = process.attrib.get("id", "")
        if proc_id in participants and participants[proc_id][1]:
            return participants[proc_id][1]
        return process.attrib.get("name") or Path(self.filename).stem.replace("_", " ").title()

    def _resolve_type(self, tag: str, elem: Any) -> Optional[str]:
        if tag in ("intermediateCatchEvent", "intermediateThrowEvent"):
            kinds = {_local(c.tag) for c in elem}
            if EVENT_DEFINITION_TIMER in kinds:
                return "intermediateTimerEvent"
            if EVENT_DEFINITION_MESSAGE in kinds:
                return "intermediateMessageEvent"
            if tag == "intermediateCatchEvent":
                self.report.warnings.append(
                    f"Intermediate event '{elem.attrib.get('name') or elem.attrib.get('id')}' has no timer or "
                    "message definition; imported as a message event."
                )
                return "intermediateMessageEvent"
            return None

        if tag in DIRECT_TYPE_MAP:
            return DIRECT_TYPE_MAP[tag]

        if tag in APPROXIMATED_TYPE_MAP:
            mapped, label = APPROXIMATED_TYPE_MAP[tag]
            name = elem.attrib.get("name") or elem.attrib.get("id") or label
            self.report.warnings.append(f"'{name}' is a {label}; imported as a {mapped}.")
            return mapped

        return None

    def _lane_membership(self, processes: List[Any]) -> Dict[str, str]:
        """raw element id -> raw lane id"""
        membership: Dict[str, str] = {}
        for process in processes:
            for elem in process.iter():
                if _local(elem.tag) != "lane":
                    continue
                lane_id = elem.attrib.get("id", "")
                for child in elem:
                    if _local(child.tag) == "flowNodeRef" and (child.text or "").strip():
                        membership[(child.text or "").strip()] = lane_id
        return membership

    def _extract_elements(self, processes: List[Any]) -> Tuple[List[FlowNode], Dict[str, str]]:
        membership = self._lane_membership(processes)
        elements: List[FlowNode] = []
        lane_of_element: Dict[str, str] = {}
        seen_raw: set[str] = set()

        for process in processes:
            for elem in process.iter():
                tag = _local(elem.tag)
                raw_id = elem.attrib.get("id", "")

                if tag in SKIPPED_TAGS:
                    name = elem.attrib.get("name") or raw_id or tag
                    self.report.warnings.append(
                        f"'{name}' is a {tag} and was not imported — the IR has no equivalent."
                    )
                    continue

                ir_type = self._resolve_type(tag, elem)
                if ir_type is None or not raw_id or raw_id in seen_raw:
                    continue

                seen_raw.add(raw_id)
                node_id = sanitize_id(raw_id, "Node", self.id_map)
                lane_raw = membership.get(raw_id, "")
                lane_id = sanitize_id(lane_raw, "Lane", self.id_map) if lane_raw else ""

                documentation = ""
                for child in elem:
                    if _local(child.tag) == "documentation" and (child.text or "").strip():
                        documentation = (child.text or "").strip()
                        break

                elements.append(
                    FlowNode(
                        id=node_id,
                        type=ir_type,  # type: ignore[arg-type]
                        name=(elem.attrib.get("name") or "").strip(),
                        laneId=lane_id,
                        documentation=documentation,
                    )
                )
                lane_of_element[node_id] = lane_id

        return elements, lane_of_element

    def _extract_pools(
        self,
        processes: List[Any],
        participants: Dict[str, Tuple[str, str]],
        lane_of_element: Dict[str, str],
    ) -> List[Pool]:
        pools: List[Pool] = []
        for process in processes:
            proc_id = process.attrib.get("id", "")
            lanes: List[Lane] = []
            for elem in process.iter():
                if _local(elem.tag) != "lane":
                    continue
                raw_lane_id = elem.attrib.get("id", "")
                if not raw_lane_id:
                    continue
                lanes.append(
                    Lane(
                        id=sanitize_id(raw_lane_id, "Lane", self.id_map),
                        name=(elem.attrib.get("name") or "Lane").strip(),
                    )
                )

            if not lanes and any(lane_of_element.get(k) == "" for k in lane_of_element):
                # A pool-less diagram: everything lands in one default lane so the layout and
                # the swimlane-based serializer have something to hang the nodes on.
                lanes = [Lane(id="Lane_Imported", name="Process")]

            pool_name = participants.get(proc_id, ("", ""))[1] or process.attrib.get("name") or "Process"
            pools.append(
                Pool(
                    id=sanitize_id(proc_id or "Pool_1", "Pool", self.id_map),
                    name=pool_name.strip(),
                    lanes=lanes,
                )
            )
        return pools

    def _extract_flows(self, processes: List[Any], known_ids: set[str]) -> List[SequenceFlow]:
        flows: List[SequenceFlow] = []
        seen: set[str] = set()

        for process in processes:
            for elem in process.iter():
                if _local(elem.tag) != "sequenceFlow":
                    continue
                raw_id = elem.attrib.get("id", "")
                raw_src = elem.attrib.get("sourceRef", "")
                raw_tgt = elem.attrib.get("targetRef", "")
                if not raw_src or not raw_tgt:
                    continue

                source_id = self.id_map.get(raw_src)
                target_id = self.id_map.get(raw_tgt)
                if source_id not in known_ids or target_id not in known_ids:
                    # One end was a boundary event or another skipped node.
                    self.report.warnings.append(
                        f"Sequence flow '{elem.attrib.get('name') or raw_id}' was dropped because one of its "
                        "ends is an element that could not be imported."
                    )
                    continue

                flow_id = sanitize_id(raw_id or f"Flow_{len(flows) + 1}", "Flow", self.id_map)
                if flow_id in seen:
                    continue
                seen.add(flow_id)

                condition = ""
                for child in elem:
                    if _local(child.tag) == "conditionExpression":
                        condition = (child.text or "").strip()
                        break

                flows.append(
                    SequenceFlow(
                        id=flow_id,
                        sourceId=source_id,
                        targetId=target_id,
                        name=(elem.attrib.get("name") or "").strip(),
                        condition=condition,
                    )
                )
        return flows

    # ------------------------------------------------------------------ diagram interchange
    def _extract_layout(self, ir: ProcessIR) -> Optional[DiagramLayout]:
        """
        Rebuilds the source file's layout so the diagram keeps the shape it had in the tool
        it came from. Returns None when the file has no usable DI for the imported nodes,
        in which case the caller falls back to the Sugiyama engine.
        """
        shapes: Dict[str, Bounds] = {}
        edges: Dict[str, List[Waypoint]] = {}

        for elem in self.root.iter():
            tag = _local(elem.tag)
            if tag == "BPMNShape":
                raw_ref = elem.attrib.get("bpmnElement", "")
                mapped = self.id_map.get(raw_ref)
                if not mapped:
                    continue
                for child in elem:
                    if _local(child.tag) != "Bounds":
                        continue
                    try:
                        shapes[mapped] = Bounds(
                            x=float(child.attrib.get("x", 0)),
                            y=float(child.attrib.get("y", 0)),
                            width=float(child.attrib.get("width", 0)) or 100.0,
                            height=float(child.attrib.get("height", 0)) or 80.0,
                        )
                    except (TypeError, ValueError):
                        pass
            elif tag == "BPMNEdge":
                raw_ref = elem.attrib.get("bpmnElement", "")
                mapped = self.id_map.get(raw_ref)
                if not mapped:
                    continue
                points: List[Waypoint] = []
                for child in elem:
                    if _local(child.tag) != "waypoint":
                        continue
                    try:
                        points.append(
                            Waypoint(x=float(child.attrib.get("x", 0)), y=float(child.attrib.get("y", 0)))
                        )
                    except (TypeError, ValueError):
                        pass
                if len(points) >= 2:
                    edges[mapped] = points

        node_ids = {e.id for e in ir.elements}
        if not node_ids or not node_ids.issubset(shapes.keys()):
            missing = len(node_ids - set(shapes.keys()))
            if missing:
                logger.info(
                    "[BpmnImporter] %s of %s nodes have no DI shape; falling back to auto-layout.",
                    missing,
                    len(node_ids),
                )
            return None

        layout = DiagramLayout()
        for node_id in node_ids:
            layout.nodes[node_id] = NodeLayout(element_id=node_id, bounds=shapes[node_id])

        for flow in ir.flows:
            if flow.id in edges:
                layout.edges[flow.id] = EdgeLayout(flow_id=flow.id, waypoints=edges[flow.id])
            else:
                layout.edges[flow.id] = EdgeLayout(
                    flow_id=flow.id, waypoints=_straight_waypoints(shapes, flow.sourceId, flow.targetId)
                )

        _fill_containers(layout, ir, shapes)

        xs = [b.x + b.width for b in shapes.values()]
        ys = [b.y + b.height for b in shapes.values()]
        layout.total_width = max(xs) + 120.0 if xs else 1200.0
        layout.total_height = max(ys) + 120.0 if ys else 600.0
        return layout


def _straight_waypoints(shapes: Dict[str, Bounds], source_id: str, target_id: str) -> List[Waypoint]:
    """A simple left-edge-to-right-edge line, for flows the source file gave no waypoints for."""
    src = shapes.get(source_id)
    tgt = shapes.get(target_id)
    if not src or not tgt:
        return [Waypoint(x=0.0, y=0.0), Waypoint(x=0.0, y=0.0)]
    return [
        Waypoint(x=src.x + src.width, y=src.y + src.height / 2),
        Waypoint(x=tgt.x, y=tgt.y + tgt.height / 2),
    ]


def _fill_containers(layout: DiagramLayout, ir: ProcessIR, shapes: Dict[str, Bounds]) -> None:
    """
    Gives each pool and lane a box.

    A lane's own DI shape is used when the file has one; otherwise the lane is sized to the
    nodes it holds, so a tool that exported lanes without shapes still renders sensibly.
    """
    for pool in ir.pools:
        lane_layouts: List[LaneLayout] = []
        for lane in pool.lanes:
            bounds = shapes.get(lane.id)
            if bounds is None:
                members = [
                    layout.nodes[e.id].bounds
                    for e in ir.elements
                    if e.laneId == lane.id and e.id in layout.nodes
                ]
                if members:
                    min_x = min(b.x for b in members) - 60.0
                    min_y = min(b.y for b in members) - 40.0
                    max_x = max(b.x + b.width for b in members) + 60.0
                    max_y = max(b.y + b.height for b in members) + 40.0
                    bounds = Bounds(x=min_x, y=min_y, width=max_x - min_x, height=max_y - min_y)
                else:
                    bounds = Bounds(x=160.0, y=80.0, width=1000.0, height=180.0)
            lane_layouts.append(LaneLayout(lane_id=lane.id, pool_id=pool.id, bounds=bounds))

        pool_bounds = shapes.get(pool.id)
        if pool_bounds is None:
            if lane_layouts:
                min_x = min(l.bounds.x for l in lane_layouts)
                min_y = min(l.bounds.y for l in lane_layouts)
                max_x = max(l.bounds.x + l.bounds.width for l in lane_layouts)
                max_y = max(l.bounds.y + l.bounds.height for l in lane_layouts)
                pool_bounds = Bounds(x=min_x - 30.0, y=min_y, width=max_x - min_x + 30.0, height=max_y - min_y)
            else:
                pool_bounds = Bounds(x=130.0, y=80.0, width=1100.0, height=400.0)
        layout.pools.append(PoolLayout(pool_id=pool.id, bounds=pool_bounds, lanes=lane_layouts))


def import_bpmn_bytes(raw: bytes, filename: str = "imported.bpmn") -> Tuple[ProcessIR, Optional[DiagramLayout], ImportReport]:
    """Decodes and imports a BPMN file. Raises BpmnImportError for anything unusable."""
    try:
        xml_content = raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            xml_content = raw.decode("utf-16")
        except UnicodeDecodeError as exc:
            raise BpmnImportError("The file is not valid UTF-8 or UTF-16 text.") from exc

    try:
        return BpmnImporter(xml_content, filename=filename).parse()
    except BpmnImportError:
        raise
    except ValueError as exc:
        # parse_safe_xml raises ValueError for DOCTYPE/size violations; ET raises ParseError.
        raise BpmnImportError(str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise BpmnImportError(f"The BPMN file could not be parsed: {exc}") from exc
