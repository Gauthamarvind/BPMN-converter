"""
Actor-to-Lane Matching Engine.
Matches detected roles/actors to template swimlanes using:
1. Exact string match (case-insensitive, whitespace-trimmed)
2. Fuzzy matching (token containment, Levenshtein/difflib ratio >= 0.70)
3. LLM Fallback (prompts/lane_mapping.md) via LLMProvider
4. Unmatched actors fallback (create new lane or flag)
"""

from __future__ import annotations
import difflib
import json
from typing import List, Dict, Tuple, Optional, Any
from pathlib import Path
from backend.templates.models import TemplateSpec, LaneMetric, LaneMappingResult
from backend.llm.factory import get_llm_provider
from backend.config import config


class LaneMapper:
    """
    Reconciles actors discovered in a process description with reference template lanes.
    """

    def __init__(self, spec: TemplateSpec, allow_new_lanes: bool = True):
        self.spec = spec
        self.allow_new_lanes = allow_new_lanes
        self.template_lanes = spec.get_all_lanes()

    def map_actors(
        self,
        actors: List[str],
        use_llm: bool = True,
        llm_provider: Optional[Any] = None
    ) -> List[LaneMappingResult]:
        results: List[LaneMappingResult] = []
        unmatched_actors: List[str] = []

        # 1. Exact & Fuzzy matching
        for actor in actors:
            actor_clean = actor.strip()
            if not actor_clean:
                continue

            match = self._find_exact_match(actor_clean)
            if match:
                results.append(
                    LaneMappingResult(
                        actor=actor_clean,
                        lane_id=match.id,
                        lane_name=match.name,
                        confidence=1.0,
                        match_type="exact",
                        rationale=f"Exact match to template lane '{match.name}'"
                    )
                )
                continue

            fuzzy_match, score = self._find_fuzzy_match(actor_clean)
            if fuzzy_match and score >= 0.70:
                results.append(
                    LaneMappingResult(
                        actor=actor_clean,
                        lane_id=fuzzy_match.id,
                        lane_name=fuzzy_match.name,
                        confidence=round(score, 2),
                        match_type="fuzzy",
                        rationale=f"Fuzzy match to '{fuzzy_match.name}' (similarity {int(score * 100)}%)"
                    )
                )
                continue

            unmatched_actors.append(actor_clean)

        # 2. LLM Fallback for remaining unmatched actors
        if unmatched_actors and use_llm and self.template_lanes:
            llm_results = self._resolve_with_llm(unmatched_actors, llm_provider)
            for res in llm_results:
                results.append(res)
                if res.actor in unmatched_actors:
                    unmatched_actors.remove(res.actor)

        # 3. Handle any remaining actors
        for actor in unmatched_actors:
            if self.allow_new_lanes:
                new_id = f"Lane_New_{len(results) + 1}"
                results.append(
                    LaneMappingResult(
                        actor=actor,
                        lane_id=new_id,
                        lane_name=actor,
                        confidence=0.6,
                        match_type="new_lane",
                        rationale=f"Unmatched: Created new lane for '{actor}'"
                    )
                )
            else:
                results.append(
                    LaneMappingResult(
                        actor=actor,
                        lane_id=None,
                        lane_name=None,
                        confidence=0.0,
                        match_type="unmatched",
                        rationale=f"Actor '{actor}' does not match any template lane"
                    )
                )

        return results

    def _find_exact_match(self, actor: str) -> Optional[LaneMetric]:
        lower = actor.lower()
        for lane in self.template_lanes:
            if lane.name.lower() == lower:
                return lane
        return None

    def _find_fuzzy_match(self, actor: str) -> Tuple[Optional[LaneMetric], float]:
        best_lane: Optional[LaneMetric] = None
        best_score = 0.0
        actor_lower = actor.lower()

        for lane in self.template_lanes:
            lane_lower = lane.name.lower()
            # Token containment
            if actor_lower in lane_lower or lane_lower in actor_lower:
                score = 0.85
            else:
                score = difflib.SequenceMatcher(None, actor_lower, lane_lower).ratio()

            if score > best_score:
                best_score = score
                best_lane = lane

        return best_lane, best_score

    def _resolve_with_llm(
        self,
        actors: List[str],
        provider: Optional[Any] = None
    ) -> List[LaneMappingResult]:
        if not provider:
            try:
                provider = get_llm_provider()
            except Exception:
                return []

        prompt_path = Path(__file__).resolve().parent.parent.parent / "prompts" / "lane_mapping.md"
        prompt_template = ""
        if prompt_path.exists():
            prompt_template = prompt_path.read_text(encoding="utf-8")
        else:
            prompt_template = "Map candidate actors to existing template lanes."

        lanes_summary = [
            {"id": l.id, "name": l.name, "order": l.order}
            for l in self.template_lanes
        ]

        user_content = (
            f"{prompt_template}\n\n"
            f"Candidate Actors to map:\n{json.dumps(actors, indent=2)}\n\n"
            f"Existing Template Lanes:\n{json.dumps(lanes_summary, indent=2)}\n"
        )

        try:
            response_text, _ = provider.generate(
                prompt=user_content,
                system_instruction="You are a BPMN 2.0 system expert. Respond ONLY with valid JSON.",
                temperature=0.0
            )
            # Clean possible markdown block
            clean = response_text.strip()
            if clean.startswith("```json"):
                clean = clean[7:]
            if clean.startswith("```"):
                clean = clean[3:]
            if clean.endswith("```"):
                clean = clean[:-3]
            clean = clean.strip()

            parsed = json.loads(clean)
            lane_mapping = parsed.get("lane_mapping", {})
            confidence_scores = parsed.get("confidence_scores", {})
            rationales = parsed.get("rationale", {})

            lane_dict = {l.id: l.name for l in self.template_lanes}
            results = []
            for actor, target_id in lane_mapping.items():
                if target_id and target_id in lane_dict:
                    results.append(
                        LaneMappingResult(
                            actor=actor,
                            lane_id=target_id,
                            lane_name=lane_dict[target_id],
                            confidence=float(confidence_scores.get(actor, 0.85)),
                            match_type="llm",
                            rationale=rationales.get(actor, f"LLM matched to '{lane_dict[target_id]}'")
                        )
                    )
            return results
        except Exception:
            return []
