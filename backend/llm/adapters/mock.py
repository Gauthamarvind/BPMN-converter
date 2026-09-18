"""
Offline Mock Adapter.
Provides deterministic, zero-network ProcessIR generation for offline testing and air-gapped workflows.
"""

from __future__ import annotations
import json
import re
from typing import List, Dict, Any, Optional, Tuple

from backend.llm.base import LLMProvider


class MockAdapter(LLMProvider):
    """
    Mock LLM provider adapter that generates valid ProcessIR JSON locally without any network connection.
    """

    def __init__(
        self,
        base_url: str = "",
        api_key: str = "",
        model: str = "mock",
        timeout: float = 90.0,
    ):
        self.base_url = base_url
        self.api_key = api_key
        self.model = model or "mock"
        self.timeout = timeout
        self.provider = "mock"

    def complete(
        self,
        messages: List[Dict[str, str]],
        json_schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> Tuple[Optional[Dict[str, Any]], str, Dict[str, Any]]:
        # Extract prompt content
        user_content = ""
        for m in messages:
            if m.get("role") == "user":
                user_content += m.get("content", "") + "\n"

        ir_dict = self._generate_ir_from_prompt(user_content)
        raw_text = json.dumps(ir_dict, indent=2)

        usage = {
            "prompt_tokens": max(10, len(user_content) // 4),
            "completion_tokens": max(20, len(raw_text) // 4),
            "total_tokens": max(30, (len(user_content) + len(raw_text)) // 4),
        }

        return ir_dict, raw_text, usage

    def _generate_ir_from_prompt(self, text: str) -> Dict[str, Any]:
        """Generates a valid ProcessIR dictionary structure deterministically."""
        # Find lines in the text
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        
        roles = set()
        activities = []

        for idx, line in enumerate(lines):
            if ":" in line and not line.startswith("http") and not line.startswith("{") and not line.startswith('"'):
                parts = line.split(":", 1)
                speaker = parts[0].strip().replace("#", "").strip()
                content = parts[1].strip()
                if 2 <= len(speaker) <= 25 and len(content) > 3:
                    clean_speaker = re.sub(r"[^a-zA-Z0-9_ ]", "", speaker).strip() or "User"
                    roles.add(clean_speaker)
                    activities.append((clean_speaker, content[:50]))
                    continue

            if line.startswith(("-", "*", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")):
                cleaned = line.lstrip("-*0123456789. ")
                if len(cleaned) > 3:
                    activities.append(("Operations", cleaned[:50]))
                    roles.add("Operations")

        if not activities:
            activities = [
                ("User", "Submit Request"),
                ("Manager", "Review and Approve"),
                ("System", "Execute Processing"),
            ]
            roles.update(["User", "Manager", "System"])

        sorted_roles = sorted(list(roles)) if roles else ["Operations"]
        lanes = [{"id": f"Lane_{i + 1}", "name": r} for i, r in enumerate(sorted_roles)]
        role_to_lane = {lane["name"]: lane["id"] for lane in lanes}

        elements = []
        flows = []

        first_lane = lanes[0]["id"]
        elements.append({
            "id": "Event_start",
            "type": "startEvent",
            "name": "Process Start",
            "laneId": first_lane,
            "confidence": 1.0,
            "sourceRefs": [{"sourceLocation": "Header", "textSnippet": "Initiation"}]
        })

        prev_id = "Event_start"
        for i, (role, act_name) in enumerate(activities[:12]):
            task_id = f"Activity_step_{i + 1}"
            lane_id = role_to_lane.get(role, first_lane)
            elements.append({
                "id": task_id,
                "type": "task",
                "name": act_name,
                "laneId": lane_id,
                "confidence": 0.95,
                "sourceRefs": [{"sourceLocation": f"Step {i + 1}", "textSnippet": act_name}]
            })
            flows.append({
                "id": f"Flow_seq_{i + 1}",
                "sourceRef": prev_id,
                "targetRef": task_id,
                "condition": ""
            })
            prev_id = task_id

        last_lane = lanes[-1]["id"]
        elements.append({
            "id": "Event_end",
            "type": "endEvent",
            "name": "Process Complete",
            "laneId": last_lane,
            "confidence": 1.0,
            "sourceRefs": [{"sourceLocation": "Footer", "textSnippet": "Completion"}]
        })
        flows.append({
            "id": f"Flow_seq_end",
            "sourceRef": prev_id,
            "targetRef": "Event_end",
            "condition": ""
        })

        return {
            "id": "Process_mock_generated",
            "name": "Generated Process",
            "documentation": "Generated by MockAdapter offline.",
            "pools": [
                {
                    "id": "Participant_1",
                    "name": "Business Organization",
                    "lanes": lanes
                }
            ],
            "elements": elements,
            "flows": flows,
            "dataObjects": [],
            "openQuestions": []
        }
