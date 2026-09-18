"""
Token Budget Chunker and Map-Reduce Process Extraction Engine.
Chunks long documents based on LLM_CONTEXT_TOKENS, extracts ProcessIR fragments,
and merges them deterministically using prompt templates.
"""

from __future__ import annotations
import json
import sys
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from backend.config import config
from backend.ir.models import ProcessIR, FlowNode, SequenceFlow, Pool, Lane, DataObject, OpenQuestion
from backend.llm.base import LLMProvider
from backend.llm.structured import extract_with_self_healing


class ProcessExtractor:
    """
    Manages process extraction from normalized text using LLM provider and prompt templates.
    Supports single-pass or Map-Reduce chunked extraction.
    """

    def __init__(self, provider: LLMProvider):
        self.provider = provider
        self.prompts_dir = config.prompts_dir
        self.extract_template = (self.prompts_dir / "extract_chunk.md").read_text(encoding="utf-8")
        self.merge_template = (self.prompts_dir / "merge_fragments.md").read_text(encoding="utf-8")

    def estimate_tokens(self, text: str) -> int:
        """Heuristic token estimation: ~4 chars per token."""
        return max(1, len(text) // 4)

    def chunk_text(self, text: str, max_chunk_tokens: int) -> List[str]:
        """
        Splits text into chunks respecting paragraph / sentence boundaries within token budget.
        """
        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = []
        current_tokens = 0

        for para in paragraphs:
            para_tokens = self.estimate_tokens(para)
            if current_tokens + para_tokens > max_chunk_tokens and current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [para]
                current_tokens = para_tokens
            else:
                current_chunk.append(para)
                current_tokens += para_tokens

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks if chunks else [text]

    def render_prompt(self, chunk_text: str, title: str, pools_hint: str = "") -> str:
        """
        Fills the extraction template. The template uses ``{{CHUNK_TEXT}}`` / ``{{POOLS_HINT}}``;
        older copies used ``{{CHUNK_CONTENT}}`` / ``{{PROCESS_TITLE}}``. Both spellings are
        substituted so a customised prompt file can never silently drop the document text.
        """
        hint = pools_hint or (
            f"Process title: {title}. No pools or lanes are known yet; derive them from the actors, "
            f"departments and systems named in the text."
        )
        prompt = (
            self.extract_template
            .replace("{{CHUNK_TEXT}}", chunk_text)
            .replace("{{CHUNK_CONTENT}}", chunk_text)
            .replace("{{POOLS_HINT}}", hint)
            .replace("{{PROCESS_TITLE}}", title)
        )
        if chunk_text and chunk_text not in prompt:
            raise RuntimeError(
                "Extraction prompt template has no chunk placeholder ({{CHUNK_TEXT}}); the document "
                "text would not reach the model. Check prompts/extract_chunk.md."
            )
        return prompt

    def extract(self, text: str, title: str = "Extracted Business Process") -> Tuple[ProcessIR, Dict[str, Any]]:
        """
        Main extraction entry point.
        Uses single-pass if within budget, or Map-Reduce for long multi-page documents.
        """
        context_budget = config.llm.context_tokens
        # Reserve tokens for system message, schema instructions, and output
        chunk_token_limit = max(1000, (context_budget // 2) - 500)

        total_tokens = self.estimate_tokens(text)
        total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        # Single chunk path
        if total_tokens <= chunk_token_limit:
            prompt = self.render_prompt(text, title)
            ir, usage = extract_with_self_healing(
                provider=self.provider,
                prompt=prompt,
                prompts_dir=self.prompts_dir,
                temperature=config.llm.temperature,
                max_tokens=config.llm.max_output_tokens
            )
            return ir, usage

        # Multi-chunk Map-Reduce path
        chunks = self.chunk_text(text, max_chunk_tokens=chunk_token_limit)
        print(f"[Process2BPMN] Document exceeds single chunk budget ({total_tokens} tokens). Running Map-Reduce on {len(chunks)} chunks.", file=sys.stderr)

        fragments: List[ProcessIR] = []
        for idx, chunk in enumerate(chunks, start=1):
            chunk_header = f"=== Chunk {idx}/{len(chunks)} ===\n{chunk}"
            pools_hint = ""
            if fragments:
                # Give later chunks the lanes already discovered so IDs and roles stay consistent.
                known = sorted({l.name for fr in fragments for p in fr.pools for l in p.lanes})
                if known:
                    pools_hint = "Lanes already identified in earlier chunks (reuse these names): " + ", ".join(known)
            prompt = self.render_prompt(chunk_header, f"{title} (Part {idx})", pools_hint)
            frag_ir, usage = extract_with_self_healing(
                provider=self.provider,
                prompt=prompt,
                prompts_dir=self.prompts_dir,
                temperature=config.llm.temperature,
                max_tokens=config.llm.max_output_tokens
            )
            for k in total_usage:
                total_usage[k] += usage.get(k, 0)
            fragments.append(frag_ir)

        # Reduce / Merge step
        merged_ir = self.merge_fragments(fragments, title=title)
        return merged_ir, total_usage

    def merge_fragments(self, fragments: List[ProcessIR], title: str) -> ProcessIR:
        """
        Merges fragment ProcessIR models. First attempts LLM-based intelligent synthesis;
        falls back to deterministic graph union if LLM merge is ambiguous.
        """
        # Format fragments as JSON strings for the merge prompt
        fragments_summary = [f"--- Fragment {i + 1} ---\n" + json.dumps(f.to_dict(), indent=2) for i, f in enumerate(fragments)]
        combined_text = "\n\n".join(fragments_summary)

        # Check if combined fits in merge prompt budget
        if self.estimate_tokens(combined_text) < (config.llm.context_tokens - 1000):
            prompt = self.merge_template.replace("{{FRAGMENTS_JSON}}", combined_text).replace("{{PROCESS_TITLE}}", title)
            try:
                merged_ir, _ = extract_with_self_healing(
                    provider=self.provider,
                    prompt=prompt,
                    prompts_dir=self.prompts_dir,
                    temperature=config.llm.temperature,
                    max_tokens=config.llm.max_output_tokens
                )
                return merged_ir
            except Exception as ex:
                print(f"[Process2BPMN] LLM merge encountered issue: {ex}. Falling back to deterministic graph union.", file=sys.stderr)

        # Deterministic union fallback
        return self._deterministic_union(fragments, title)

    def _deterministic_union(self, fragments: List[ProcessIR], title: str) -> ProcessIR:
        """
        Merge fragments without a model, without losing anything.

        Each fragment was extracted independently, so IDs such as ``Lane_1`` or
        ``Activity_1`` collide across fragments. Every fragment is namespaced with a
        ``f<n>_`` prefix first; lanes are then unified by *name* (the only stable key),
        only the first fragment keeps its start events and only the last keeps its end
        events, and each fragment's terminal nodes are stitched to the next fragment's
        first activity so the result is one connected process. Anything still ambiguous
        is left for the validator to report.
        """
        if not fragments:
            return ProcessIR(id="Process_Merged", name=title)
        if len(fragments) == 1:
            return fragments[0]

        lanes_by_name: Dict[str, Lane] = {}
        pool_name = fragments[0].pools[0].name if fragments[0].pools else title
        elements: List[FlowNode] = []
        flows: List[SequenceFlow] = []
        data_objects: List[DataObject] = []
        questions: List[OpenQuestion] = []
        last_fragment = len(fragments) - 1
        prev_terminals: List[str] = []

        for idx, frag in enumerate(fragments):
            prefix = f"f{idx + 1}_"
            lane_remap: Dict[str, str] = {}
            for p in frag.pools:
                for l in p.lanes:
                    key = (l.name or l.id).strip().lower()
                    if key not in lanes_by_name:
                        lanes_by_name[key] = Lane(id=f"Lane_{len(lanes_by_name) + 1}", name=l.name or l.id)
                    lane_remap[l.id] = lanes_by_name[key].id

            id_remap: Dict[str, str] = {}
            kept: List[FlowNode] = []
            for e in frag.elements:
                if e.type == "startEvent" and idx != 0:
                    continue
                if e.type == "endEvent" and idx != last_fragment:
                    continue
                new_id = prefix + e.id
                id_remap[e.id] = new_id
                kept.append(FlowNode(
                    id=new_id,
                    type=e.type,
                    name=e.name,
                    laneId=lane_remap.get(e.laneId, e.laneId),
                    documentation=e.documentation,
                    timerDuration=e.timerDuration,
                    confidence=e.confidence,
                    sourceRefs=list(e.sourceRefs),
                ))
            elements.extend(kept)

            frag_flows: List[SequenceFlow] = []
            for f in frag.flows:
                if f.sourceId in id_remap and f.targetId in id_remap:
                    frag_flows.append(SequenceFlow(
                        id=prefix + f.id,
                        type=f.type,
                        sourceId=id_remap[f.sourceId],
                        targetId=id_remap[f.targetId],
                        name=f.name,
                        condition=f.condition,
                        isDefault=f.isDefault,
                    ))
            flows.extend(frag_flows)

            # Stitch: previous fragment's dangling ends -> this fragment's first activity
            incoming = {f.targetId for f in frag_flows}
            entry_candidates = [e.id for e in kept if e.type != "startEvent" and e.id not in incoming]
            entry = entry_candidates[0] if entry_candidates else (kept[0].id if kept else None)
            if entry and prev_terminals:
                for t_idx, term in enumerate(prev_terminals):
                    flows.append(SequenceFlow(
                        id=f"Flow_stitch_{idx}_{t_idx + 1}",
                        sourceId=term,
                        targetId=entry,
                        name="",
                    ))
                if len(prev_terminals) > 1:
                    questions.append(OpenQuestion(
                        topic="Chunk Boundary",
                        question=(
                            f"Fragment {idx} ended with {len(prev_terminals)} open branches that were all "
                            f"joined into '{entry}'. Confirm this is the intended continuation."
                        ),
                    ))

            outgoing = {f.sourceId for f in frag_flows}
            prev_terminals = [e.id for e in kept if e.type != "endEvent" and e.id not in outgoing]

            for d in frag.dataObjects:
                data_objects.append(DataObject(id=prefix + d.id, name=d.name, itemSubjectRef=d.itemSubjectRef))
            questions.extend(frag.openQuestions)

        pool = Pool(id="Participant_1", name=pool_name, lanes=list(lanes_by_name.values()))
        return ProcessIR(
            id="Process_Merged",
            name=title,
            pools=[pool],
            elements=elements,
            flows=flows,
            dataObjects=data_objects,
            openQuestions=questions,
        )
