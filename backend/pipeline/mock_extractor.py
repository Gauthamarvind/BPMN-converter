"""
Deterministic rule-based mock extractor.
Used only when LLM_PROVIDER=mock or the request explicitly asks for mock mode.
It never calls a model and is intentionally simple; quality is far below LLM extraction.
"""

from __future__ import annotations
import re
from typing import List, Dict, Optional

from backend.ir.models import ProcessIR, FlowNode, SequenceFlow, Pool, Lane, SourceRef


def generate_mock_ir_from_text(text: str, title: str = "Extracted Business Process") -> ProcessIR:
    """
    Deterministic rule-based mock extractor for Phase 1 testing and offline execution.
    Extracts steps, identifies actor/system roles, and synthesizes a well-formed ProcessIR.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    
    # 1. Pools & Lanes identification
    lanes_detected = set()
    activities_raw = []

    for idx, line in enumerate(lines):
        # CSV parsing if comma separated with step
        if "," in line and not line.lower().startswith("step"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3:
                role = parts[1] if parts[1] else "General"
                name = parts[2] if parts[2] else parts[0]
                lanes_detected.add(role)
                activities_raw.append((role, name, f"Row {idx + 1}", line))
                continue

        # Dialogue or transcript line (e.g., "Sarah: The manager approves...")
        if ":" in line and not line.startswith("http"):
            speaker, content = line.split(":", 1)
            speaker = speaker.strip()
            content = content.strip()
            if 2 <= len(speaker) <= 25 and len(content) > 5:
                lanes_detected.add(speaker)
                activities_raw.append((speaker, content[:60], f"Line {idx + 1}", line))
                continue

        # SOP / Markdown bullet points or numbered lists
        if line.startswith(("-", "*", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")):
            cleaned = line.lstrip("-*0123456789. ")
            activities_raw.append(("Operations", cleaned[:60], f"Line {idx + 1}", line))
            lanes_detected.add("Operations")

    if not activities_raw:
        # Fallback activities if text is brief or freeform
        activities_raw = [
            ("User", "Submit Request", "Paragraph 1", "Employee initiates request"),
            ("Manager", "Review and Approve", "Paragraph 2", "Manager verifies justification"),
            ("System", "Execute Processing", "Paragraph 3", "Automated system completes order"),
        ]
        lanes_detected.update(["User", "Manager", "System"])

    # Create lanes
    sorted_lanes = sorted(list(lanes_detected)) if lanes_detected else ["General"]
    lane_objs = [
        Lane(id=f"Lane_{i + 1}", name=role_name)
        for i, role_name in enumerate(sorted_lanes)
    ]
    role_to_lane_id = {lane.name: lane.id for lane in lane_objs}

    pool = Pool(
        id="Participant_1",
        name=title,
        lanes=lane_objs
    )

    # Create flow nodes
    elements = []
    flows = []

    # Start Event
    first_lane = lane_objs[0].id
    start_event = FlowNode(
        id="Event_start",
        type="startEvent",
        name="Start",
        laneId=first_lane,
        confidence=1.0,
        sourceRefs=[SourceRef(sourceLocation="Header", textSnippet="Process initiation")]
    )
    elements.append(start_event)

    prev_node_id = start_event.id

    # Create tasks
    for i, (role, name, loc, snippet) in enumerate(activities_raw):
        task_id = f"Activity_{i + 1}"
        assigned_lane = role_to_lane_id.get(role, first_lane)
        
        # Decide task type
        task_type = "userTask" if role.lower() in ("user", "customer", "employee") else "task"
        if "system" in role.lower() or "bot" in role.lower():
            task_type = "serviceTask"

        node = FlowNode(
            id=task_id,
            type=task_type,
            name=name,
            laneId=assigned_lane,
            documentation=snippet,
            confidence=0.92,
            sourceRefs=[SourceRef(sourceLocation=loc, textSnippet=snippet)]
        )
        elements.append(node)

        # Flow from previous
        flow = SequenceFlow(
            id=f"Flow_{prev_node_id}_{task_id}",
            type="sequence",
            sourceId=prev_node_id,
            targetId=task_id,
            name=""
        )
        flows.append(flow)
        prev_node_id = task_id

    # End Event
    last_lane = lane_objs[-1].id
    end_event = FlowNode(
        id="Event_end",
        type="endEvent",
        name="End",
        laneId=last_lane,
        confidence=1.0,
        sourceRefs=[]
    )
    elements.append(end_event)

    flows.append(
        SequenceFlow(
            id=f"Flow_{prev_node_id}_{end_event.id}",
            type="sequence",
            sourceId=prev_node_id,
            targetId=end_event.id,
            name=""
        )
    )

    return ProcessIR(
        id="Process_1",
        name=title,
        description=f"Generated from: {title}",
        pools=[pool],
        elements=elements,
        flows=flows
    )
