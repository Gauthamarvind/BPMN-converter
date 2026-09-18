"""
Token Budget Chunker and Map-Reduce Process Extraction Engine.
Chunks long documents based on LLM_CONTEXT_TOKENS, extracts ProcessIR fragments,
and merges them deterministically using prompt templates.
"""

from __future__ import annotations
import json
from typing import List, Dict, Any, Optional
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
            prompt = self.extract_template.replace("{{CHUNK_CONTENT}}", text).replace("{{PROCESS_TITLE}}", title)
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
            prompt = self.extract_template.replace("{{CHUNK_CONTENT}}", chunk_header).replace("{{PROCESS_TITLE}}", f"{title} (Part {idx})")
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
        pools_by_id = {}
        elements_by_id = {}
        flows_by_id = {}
        data_by_id = {}
        questions = []

        for frag in fragments:
            for p in frag.pools:
                if p.id not in pools_by_id:
                    pools_by_id[p.id] = p
                else:
                    existing_lane_ids = {l.id for l in pools_by_id[p.id].lanes}
                    for l in p.lanes:
                        if l.id not in existing_lane_ids:
                            pools_by_id[p.id].lanes.append(l)

            for elem in frag.elements:
                if elem.id not in elements_by_id:
                    elements_by_id[elem.id] = elem

            for flow in frag.flows:
                if flow.id not in flows_by_id:
                    flows_by_id[flow.id] = flow

            for d in frag.dataObjects:
                if d.id not in data_by_id:
                    data_by_id[d.id] = d

            questions.extend(frag.openQuestions)

        return ProcessIR(
            id="Process_Merged",
            name=title,
            pools=list(pools_by_id.values()),
            elements=list(elements_by_id.values()),
            flows=list(flows_by_id.values()),
            dataObjects=list(data_by_id.values()),
            openQuestions=questions
        )
