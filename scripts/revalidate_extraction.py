#!/usr/bin/env python3
"""
Phase 7 — real-model extraction re-validation.

Until the QA review, the extraction prompt never contained the document: ``chunker`` substituted
``{{CHUNK_CONTENT}}`` while the prompt used ``{{CHUNK_TEXT}}``, so every real-model conversion was
extracting from the literal placeholder. Anything generated before that fix — including the
``backend/tests/golden/test_sop_*.bpmn`` files — may encode nonsense.

This script re-runs the free-text fixtures through a real provider (Ollama by default), writes the
results to a directory for inspection, and prints a comparison against the current goldens so you
can see what changed before deciding whether to refresh them.

It never overwrites a golden by itself. Use ``--update-goldens`` deliberately, after reading the
diff and opening the new files in bpmn.io.

Usage:
    python3 scripts/revalidate_extraction.py
    python3 scripts/revalidate_extraction.py --provider ollama --model llama3.1:8b
    python3 scripts/revalidate_extraction.py --only sample_sop.md
    python3 scripts/revalidate_extraction.py --update-goldens
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

FIXTURES = _PROJECT_ROOT / "backend" / "tests" / "fixtures"
GOLDEN = _PROJECT_ROOT / "backend" / "tests" / "golden"
DEFAULT_OUT = _PROJECT_ROOT / "revalidation"

#: Free-text inputs — these are the ones that need a model. Structured inputs (.xlsx, .csv) are
#: converted by rules and are already covered by the deterministic test suite.
FREE_TEXT_FIXTURES = [
    "sample_sop.md",
    "sample_interview_transcript.txt",
    "sample_transcript.vtt",
    "sample_sop.pdf",
]

#: Which golden file, if any, a fixture's output should be compared against.
GOLDEN_FOR = {
    "sample_sop.md": "test_sop.bpmn",
    "sample_interview_transcript.txt": "test_interview.bpmn",
}


def _summarise(result: Dict) -> Dict[str, object]:
    ir = result.get("ir") or {}
    elements = ir.get("elements") or []
    flows = ir.get("flows") or []
    pools = ir.get("pools") or []
    return {
        "elements": len(elements),
        "flows": len(flows),
        "lanes": sum(len(p.get("lanes") or []) for p in pools),
        "lane_names": sorted({l.get("name", "") for p in pools for l in (p.get("lanes") or [])}),
        "step_names": [e.get("name", "") for e in elements],
        "gateways": [e.get("name", "") for e in elements if "ateway" in (e.get("type") or "")],
        "open_questions": len(ir.get("openQuestions") or []),
        "issues": [i.get("message") for i in result.get("validation_issues") or []],
        "export_blocked": bool(result.get("export_blocked")),
    }


def _xml_diff(old: str, new: str, name: str) -> List[str]:
    return list(
        difflib.unified_diff(
            old.splitlines(), new.splitlines(), fromfile=f"golden/{name}", tofile=f"new/{name}", lineterm="", n=1
        )
    )


def run(
    provider: Optional[str],
    model: Optional[str],
    base_url: Optional[str],
    out_dir: Path,
    only: Optional[str],
    update_goldens: bool,
) -> int:
    from backend.pipeline.process_pipeline import process_pipeline

    out_dir.mkdir(parents=True, exist_ok=True)
    targets = [f for f in FREE_TEXT_FIXTURES if not only or f == only]
    if not targets:
        print(f"No fixture matches '{only}'. Available: {', '.join(FREE_TEXT_FIXTURES)}", file=sys.stderr)
        return 1

    report: Dict[str, Dict] = {}
    failures = 0

    for fixture_name in targets:
        path = FIXTURES / fixture_name
        if not path.is_file():
            print(f"  ! {fixture_name}: not found in {FIXTURES}", file=sys.stderr)
            failures += 1
            continue

        print(f"\n=== {fixture_name}")
        started = time.time()
        try:
            result = process_pipeline(
                raw_content=path.read_bytes(),
                filename=path.name,
                profile_name="celonis",
                mock=False,
                provider_name=provider,
                model=model,
                base_url=base_url,
            )
        except Exception as exc:  # a model failure is a result, not a crash
            print(f"  ! extraction failed: {exc}", file=sys.stderr)
            report[fixture_name] = {"error": str(exc)}
            failures += 1
            continue

        elapsed = time.time() - started
        summary = _summarise(result)
        summary["seconds"] = round(elapsed, 1)
        report[fixture_name] = summary

        out_file = out_dir / f"{Path(fixture_name).stem}.bpmn"
        out_file.write_text(result["bpmn_xml"], encoding="utf-8")

        print(f"  {summary['elements']} elements, {summary['flows']} flows, {summary['lanes']} lanes in {elapsed:.1f}s")
        print(f"  lanes: {', '.join(summary['lane_names']) or '(none)'}")
        print(f"  steps: {'; '.join(summary['step_names'][:8])}")
        if summary["export_blocked"]:
            print("  EXPORT BLOCKED:")
            for issue in summary["issues"]:
                print(f"    - {issue}")
        print(f"  written: {out_file.relative_to(_PROJECT_ROOT)}")

        golden_name = GOLDEN_FOR.get(fixture_name)
        if golden_name:
            golden_path = GOLDEN / golden_name
            if golden_path.is_file():
                diff = _xml_diff(golden_path.read_text(encoding="utf-8"), result["bpmn_xml"], golden_name)
                if diff:
                    print(f"  differs from {golden_name} ({len(diff)} diff lines)")
                    for line in diff[:20]:
                        print(f"    {line}")
                    if len(diff) > 20:
                        print(f"    … {len(diff) - 20} more lines")
                    if update_goldens:
                        golden_path.write_text(result["bpmn_xml"], encoding="utf-8")
                        print(f"  golden refreshed: {golden_path.relative_to(_PROJECT_ROOT)}")
                else:
                    print(f"  matches {golden_name}")
            else:
                print(f"  (no golden at {golden_path.relative_to(_PROJECT_ROOT)})")

    report_path = out_dir / "report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nSummary written to {report_path.relative_to(_PROJECT_ROOT)}")

    if update_goldens:
        print(
            "\nGoldens were refreshed. Open each one in bpmn.io before committing, and re-run "
            "`pytest backend/tests/test_golden_templates.py`."
        )
    else:
        print("\nNo goldens were changed. Re-run with --update-goldens once you have read the diffs.")

    return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-validate real-model extraction quality (scope v2 phase 7).")
    parser.add_argument("--provider", default=None, help="Override LLM_PROVIDER (e.g. ollama, openai_compatible)")
    parser.add_argument("--model", default=None, help="Override LLM_MODEL (e.g. llama3.1:8b)")
    parser.add_argument("--base-url", default=None, help="Override LLM_BASE_URL (e.g. http://localhost:11434/v1)")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Directory for the generated .bpmn files")
    parser.add_argument("--only", default=None, help="Run a single fixture by file name")
    parser.add_argument(
        "--update-goldens",
        action="store_true",
        help="Overwrite backend/tests/golden/*.bpmn with the new output (read the diff first)",
    )
    args = parser.parse_args()

    sys.exit(
        run(
            provider=args.provider,
            model=args.model,
            base_url=args.base_url,
            out_dir=Path(args.out),
            only=args.only,
            update_goldens=args.update_goldens,
        )
    )


if __name__ == "__main__":
    main()
