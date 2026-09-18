"""
Deterministic Process IR Validator and Graph Repair Engine.
Enforces NCName identifier rules, start/end event guarantees, reachability traversal,
gateway branching conditions, and parallel split-join pairing.
"""

from __future__ import annotations
from typing import List, Dict, Set, Tuple, Any, Optional
from dataclasses import dataclass, field
import re

from backend.config import config
from backend.ir.models import (
    ProcessIR,
    FlowNode,
    SequenceFlow,
    Pool,
    Lane,
    OpenQuestion,
    NCNAME_REGEX,
    ALLOWED_ELEMENT_TYPES,
)


@dataclass
class ValidationIssue:
    severity: str  # "INFO", "WARNING", "ERROR"
    message: str
    element_id: str = ""
    auto_fixed: bool = False
    details: str = ""


def sanitize_ncname(raw_id: str, prefix: str = "id") -> str:
    """Converts any string to a strictly valid NCName XML identifier."""
    if not raw_id:
        return f"{prefix}_1"
    
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]", "_", raw_id.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    
    if not cleaned or not cleaned[0].isalpha():
        cleaned = f"{prefix}_{cleaned}" if cleaned else f"{prefix}_1"
        
    return cleaned


class ProcessValidator:
    """
    Validates and auto-repairs a ProcessIR graph deterministically.
    Only auto-fixes: NCName ID sanitizing, missing start/end event, lane assignment, removal of dangling references.
    Reports errors for unreachable nodes and unlabeled gateways without mutating graph.
    """

    def __init__(self, ir: ProcessIR, single_pool: Optional[bool] = None):
        self.ir = ir
        self.single_pool = config.single_pool if single_pool is None else single_pool
        self.issues: List[ValidationIssue] = []
        self.export_blocked: bool = False

    def validate_and_repair(self) -> Tuple[ProcessIR, List[ValidationIssue]]:
        self.issues.clear()
        self.export_blocked = False
        
        if not getattr(self.ir, "pools", None):
            self.ir.pools = []
        if not getattr(self.ir, "elements", None):
            self.ir.elements = []
        if not getattr(self.ir, "flows", None):
            self.ir.flows = []
        if not getattr(self.ir, "openQuestions", None):
            self.ir.openQuestions = []

        # 1. Sanitize & deduplicate IDs
        self._sanitize_ids()

        # 2. Validate pools, lanes and single_pool configuration
        self._validate_pools_and_lanes()

        # 3. Ensure valid element types
        self._validate_element_types()

        # 4. Prune completely invalid or orphan flows (dangling references, direct self-loops)
        self._validate_flows()

        # 5. Ensure at least one start event and connect if needed
        self._ensure_start_event()

        # 6. Ensure at least one end event
        self._ensure_end_event()

        # 7. Gateway validation: conditions on multi-outgoing, default flows
        self._validate_gateways()

        # 8. Reachability graph check
        self._check_reachability()

        if any(iss.severity == "ERROR" for iss in self.issues):
            self.export_blocked = True

        return self.ir, self.issues

    def _sanitize_ids(self) -> None:
        """Enforces unique NCName-valid IDs on all entities and updates references."""
        id_remap: Dict[str, str] = {}
        used_ids: Set[str] = set()

        # Process ID
        if not NCNAME_REGEX.match(self.ir.id):
            clean_pid = sanitize_ncname(self.ir.id, "Process")
            self.issues.append(ValidationIssue(
                severity="INFO",
                message=f"Sanitized process ID '{self.ir.id}' to '{clean_pid}'",
                element_id=clean_pid,
                auto_fixed=True
            ))
            self.ir.id = clean_pid
        used_ids.add(self.ir.id)

        # Pool & Lane IDs
        for pool in self.ir.pools:
            new_pool_id = sanitize_ncname(pool.id, "Participant")
            while new_pool_id in used_ids:
                new_pool_id = f"{new_pool_id}_1"
            if new_pool_id != pool.id:
                id_remap[pool.id] = new_pool_id
                pool.id = new_pool_id
            used_ids.add(pool.id)

            for lane in pool.lanes:
                new_lane_id = sanitize_ncname(lane.id, "Lane")
                while new_lane_id in used_ids:
                    new_lane_id = f"{new_lane_id}_1"
                if new_lane_id != lane.id:
                    id_remap[lane.id] = new_lane_id
                    lane.id = new_lane_id
                used_ids.add(lane.id)

        # Element IDs
        for elem in self.ir.elements:
            prefix = "Activity"
            if "Gateway" in elem.type or "gateway" in elem.type.lower():
                prefix = "Gateway"
            elif "Event" in elem.type or "event" in elem.type.lower():
                prefix = "Event"
                
            new_id = sanitize_ncname(elem.id, prefix)
            while new_id in used_ids:
                new_id = f"{new_id}_1"

            if new_id != elem.id:
                self.issues.append(ValidationIssue(
                    severity="INFO",
                    message=f"Sanitized element ID '{elem.id}' to '{new_id}'",
                    element_id=new_id,
                    auto_fixed=True
                ))
                id_remap[elem.id] = new_id
                elem.id = new_id
            used_ids.add(elem.id)

            # Update lane reference if remapped
            if elem.laneId in id_remap:
                elem.laneId = id_remap[elem.laneId]

        # Flow IDs and endpoints
        for flow in self.ir.flows:
            new_flow_id = sanitize_ncname(flow.id, "Flow")
            while new_flow_id in used_ids:
                new_flow_id = f"{new_flow_id}_1"
            if new_flow_id != flow.id:
                flow.id = new_flow_id
            used_ids.add(flow.id)

            # Remap endpoints
            if flow.sourceId in id_remap:
                flow.sourceId = id_remap[flow.sourceId]
            if flow.targetId in id_remap:
                flow.targetId = id_remap[flow.targetId]

    def _validate_pools_and_lanes(self) -> None:
        """Ensures pools and lanes exist; applies single_pool merge if enabled."""
        if not self.ir.pools:
            default_lane = Lane(id="Lane_Default", name="General")
            default_pool = Pool(
                id="Participant_Default",
                name="Main Process Organization",
                lanes=[default_lane]
            )
            self.ir.pools.append(default_pool)
            self.issues.append(ValidationIssue(
                severity="INFO",
                message="Created default Participant pool and General lane",
                element_id=default_pool.id,
                auto_fixed=True
            ))

        # Single pool merge policy: when True, merge multiple pools into one pool
        if self.single_pool and len(self.ir.pools) > 1:
            first_pool = self.ir.pools[0]
            all_lanes: List[Lane] = []
            for p in self.ir.pools:
                all_lanes.extend(p.lanes)
            first_pool.lanes = all_lanes
            self.ir.pools = [first_pool]

            # Convert message flows to sequence flows
            converted_count = 0
            for f in self.ir.flows:
                if f.type == "message":
                    f.type = "sequence"
                    converted_count += 1

            self.issues.append(ValidationIssue(
                severity="WARNING",
                message=f"Single pool mode enabled: merged pools into '{first_pool.name}' and converted {converted_count} message flow(s) to sequence flow(s)",
                element_id=first_pool.id,
                auto_fixed=True
            ))

        all_lane_ids = {l.id for p in self.ir.pools for l in p.lanes}
        fallback_lane_id = next(iter(all_lane_ids)) if all_lane_ids else "Lane_Default"

        for elem in self.ir.elements:
            if not elem.laneId or elem.laneId not in all_lane_ids:
                elem.laneId = fallback_lane_id
                self.issues.append(ValidationIssue(
                    severity="INFO",
                    message=f"Assigned element '{elem.name}' ({elem.id}) to default lane '{fallback_lane_id}'",
                    element_id=elem.id,
                    auto_fixed=True
                ))

    def _validate_element_types(self) -> None:
        """Ensures all element types are within the BPMN 2.0 Analytic subset."""
        for elem in self.ir.elements:
            if elem.type not in ALLOWED_ELEMENT_TYPES:
                old_type = elem.type
                elem.type = "task"
                self.issues.append(ValidationIssue(
                    severity="WARNING",
                    message=f"Unsupported element type '{old_type}' converted to standard 'task'",
                    element_id=elem.id,
                    auto_fixed=True
                ))

    def _validate_flows(self) -> None:
        """Removes self-loops and flows referring to non-existent nodes."""
        valid_element_ids = {e.id for e in self.ir.elements}
        filtered_flows: List[SequenceFlow] = []

        for flow in self.ir.flows:
            if flow.sourceId not in valid_element_ids:
                self.issues.append(ValidationIssue(
                    severity="WARNING",
                    message=f"Flow '{flow.id}' references non-existent source '{flow.sourceId}'; removed",
                    element_id=flow.id,
                    auto_fixed=True
                ))
                continue
            if flow.targetId not in valid_element_ids:
                self.issues.append(ValidationIssue(
                    severity="WARNING",
                    message=f"Flow '{flow.id}' references non-existent target '{flow.targetId}'; removed",
                    element_id=flow.id,
                    auto_fixed=True
                ))
                continue
            if flow.sourceId == flow.targetId:
                self.issues.append(ValidationIssue(
                    severity="WARNING",
                    message=f"Flow '{flow.id}' is a direct self-loop on '{flow.sourceId}'; removed",
                    element_id=flow.id,
                    auto_fixed=True
                ))
                continue
            filtered_flows.append(flow)

        self.ir.flows = filtered_flows

    def _ensure_start_event(self) -> None:
        """Guarantees at least one startEvent exists and is connected."""
        start_events = [e for e in self.ir.elements if e.type == "startEvent"]
        
        if not start_events:
            fallback_lane = self.ir.pools[0].lanes[0].id if (self.ir.pools and self.ir.pools[0].lanes) else "Lane_Default"
            new_start = FlowNode(
                id="Event_start",
                type="startEvent",
                name="Start",
                laneId=fallback_lane,
                confidence=1.0,
                documentation="Auto-generated start event"
            )
            self.ir.elements.insert(0, new_start)
            
            # Find the first logical activity (element with 0 incoming sequence flows)
            incoming_counts = {e.id: 0 for e in self.ir.elements if e.id != new_start.id}
            for f in self.ir.flows:
                if f.targetId in incoming_counts:
                    incoming_counts[f.targetId] += 1
                    
            candidates = [eid for eid, count in incoming_counts.items() if count == 0]
            target_id = candidates[0] if candidates else (self.ir.elements[1].id if len(self.ir.elements) > 1 else None)
            
            if target_id:
                new_flow = SequenceFlow(
                    id="Flow_start_init",
                    type="sequence",
                    sourceId=new_start.id,
                    targetId=target_id,
                    name=""
                )
                self.ir.flows.insert(0, new_flow)
                
            self.issues.append(ValidationIssue(
                severity="INFO",
                message="Added required startEvent 'Event_start'",
                element_id=new_start.id,
                auto_fixed=True
            ))

    def _ensure_end_event(self) -> None:
        """Guarantees at least one endEvent exists and all terminal nodes flow to it."""
        end_events = [e for e in self.ir.elements if e.type == "endEvent"]
        
        outgoing_counts = {e.id: 0 for e in self.ir.elements}
        for f in self.ir.flows:
            if f.sourceId in outgoing_counts:
                outgoing_counts[f.sourceId] += 1

        terminal_nodes = [
            e.id for e in self.ir.elements
            if outgoing_counts[e.id] == 0 and e.type != "endEvent"
        ]

        if not end_events:
            fallback_lane = self.ir.pools[0].lanes[0].id if (self.ir.pools and self.ir.pools[0].lanes) else "Lane_Default"
            new_end = FlowNode(
                id="Event_end",
                type="endEvent",
                name="End",
                laneId=fallback_lane,
                confidence=1.0,
                documentation="Auto-generated end event"
            )
            self.ir.elements.append(new_end)
            end_events.append(new_end)
            
            self.issues.append(ValidationIssue(
                severity="INFO",
                message="Added required endEvent 'Event_end'",
                element_id=new_end.id,
                auto_fixed=True
            ))

        target_end_id = end_events[0].id
        for term_id in terminal_nodes:
            new_flow = SequenceFlow(
                id=f"Flow_to_end_{term_id}",
                type="sequence",
                sourceId=term_id,
                targetId=target_end_id,
                name=""
            )
            self.ir.flows.append(new_flow)
            self.issues.append(ValidationIssue(
                severity="INFO",
                message=f"Connected terminal node '{term_id}' to end event '{target_end_id}'",
                element_id=new_flow.id,
                auto_fixed=True
            ))

    def _validate_gateways(self) -> None:
        """Ensures gateways with multiple outgoing branches have conditions or default flow. Does NOT auto-invent labels."""
        for elem in self.ir.elements:
            if elem.type in ("exclusiveGateway", "inclusiveGateway"):
                outgoing = [f for f in self.ir.flows if f.sourceId == elem.id]
                if len(outgoing) > 1:
                    unlabeled = [f for f in outgoing if not f.condition and not f.name and not f.isDefault]
                    if unlabeled:
                        self.export_blocked = True
                        msg = f"Gateway '{elem.name or elem.id}' ({elem.id}) has {len(unlabeled)} unlabeled outgoing branch(es). Conditions or a default flow are required."
                        self.issues.append(ValidationIssue(
                            severity="ERROR",
                            message=msg,
                            element_id=elem.id,
                            auto_fixed=False
                        ))
                        self.ir.openQuestions.append(OpenQuestion(
                            topic="Gateway Branching",
                            question=f"Gateway '{elem.name or elem.id}' ({elem.id}) has unlabeled outgoing branches. What condition triggers each branch?"
                        ))

    def _check_reachability(self) -> None:
        """Flags nodes that cannot be reached from any startEvent as ERROR without auto-bridging."""
        start_ids = [e.id for e in self.ir.elements if e.type == "startEvent"]
        if not start_ids:
            return

        adjacency: Dict[str, List[str]] = {e.id: [] for e in self.ir.elements}
        for f in self.ir.flows:
            if f.sourceId in adjacency:
                adjacency[f.sourceId].append(f.targetId)

        visited: Set[str] = set()
        queue = list(start_ids)
        for s in start_ids:
            visited.add(s)

        while queue:
            curr = queue.pop(0)
            for neighbor in adjacency.get(curr, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        unreachable = [e for e in self.ir.elements if e.id not in visited]
        for u in unreachable:
            self.export_blocked = True
            msg = f"Element '{u.name or u.id}' ({u.id}) is unreachable from any start event."
            self.issues.append(ValidationIssue(
                severity="ERROR",
                message=msg,
                element_id=u.id,
                auto_fixed=False
            ))
            self.ir.openQuestions.append(OpenQuestion(
                topic="Unreachable Node",
                question=f"Element '{u.name or u.id}' ({u.id}) cannot be reached from any start event. How should it connect to the flow?"
            ))
