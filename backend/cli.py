#!/usr/bin/env python3
"""
Process2BPMN Standalone CLI.
Converts unstructured process documents into BPMN 2.0 XML with full BPMNDI auto-layout.
Usage:
  process2bpmn convert input.docx --profile celonis -o out.bpmn
  python3 -m backend.cli convert input.docx --profile generic -o out.bpmn
"""

from __future__ import annotations
import sys
import os
import argparse
import re
import json
from pathlib import Path
from typing import Optional

# Ensure project root is in sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.ir.models import ProcessIR
from backend.config import config


from backend.pipeline.mock_extractor import generate_mock_ir_from_text  # re-exported for backwards compatibility

__all__ = ["generate_mock_ir_from_text", "convert_file", "main"]


def _resolve_template_id(template: Optional[str], mock: bool) -> Optional[str]:
    """
    Accepts a stored template id or a path to a .bpmn file. A file path is imported into the
    template store (so it also becomes available in the UI) and its id is returned.
    """
    if not template:
        return None
    from backend.templates.storage import TemplateStorage
    storage = TemplateStorage()
    if storage.get_template(template):
        return template
    tpl_path = Path(template)
    if tpl_path.exists():
        template_id = f"tpl_{re.sub(r'[^A-Za-z0-9_]+', '_', tpl_path.stem).strip('_')[:40] or 'file'}"
        xml_content = tpl_path.read_text(encoding="utf-8")
        storage.save_bpmn_template(template_id, tpl_path.stem, xml_content, filename=tpl_path.name)
        print(f"[Process2BPMN] Imported reference template '{tpl_path.name}' as '{template_id}'.", file=sys.stderr)
        return template_id
    raise FileNotFoundError(f"Template '{template}' is neither a stored template id nor an existing file.")


def convert_file(
    input_path: str,
    output_path: Optional[str] = None,
    profile_name: str = "generic",
    mock: bool = False,
    provider_name: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    template: Optional[str] = None,
    force: bool = False,
) -> str:
    """
    Converts a file to BPMN 2.0 XML using exactly the same pipeline as the HTTP API
    (signature-based template detection, validation policy, XSD validation, profile lint).
    """
    # Imported here to avoid a circular import (process_pipeline imports the mock extractor).
    from backend.pipeline.process_pipeline import process_pipeline, ExportBlockedError

    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Input file '{input_path}' does not exist.")

    template_id = _resolve_template_id(template, mock)

    result = process_pipeline(
        raw_content=path.read_bytes(),
        filename=path.name,
        profile_name=profile_name,
        mock=mock,
        provider_name=provider_name,
        model=model,
        base_url=base_url,
        api_key=api_key,
        template_id=template_id,
    )

    meta = result.get("metadata", {})
    extraction = meta.get("extraction", {})
    print(
        f"[Process2BPMN] Extracted {meta.get('element_count', 0)} elements / {meta.get('flow_count', 0)} flows "
        f"in {meta.get('lane_count', 0)} lane(s) via {extraction.get('mode', 'unknown')}.",
        file=sys.stderr,
    )
    for issue in result.get("validation_issues", []):
        sev = issue.get("severity", "INFO")
        print(f"[{sev}] {issue.get('code', '')}: {issue.get('message', '')}", file=sys.stderr)
    lint = result.get("lint_result") or {}
    for w in lint.get("warnings", []) if isinstance(lint, dict) else []:
        print(f"[LINT] {w.get('code', '')}: {w.get('message', '')}", file=sys.stderr)

    xml_output = result["bpmn_xml"]
    if result.get("export_blocked"):
        if force:
            print(
                "[Process2BPMN] WARNING: exporting despite ERROR-level issues because --force was given. "
                "The file is for inspection only and may not import cleanly.",
                file=sys.stderr,
            )
        else:
            raise ExportBlockedError(
                "Export is BLOCKED: the diagram has ERROR-level issues that need review (see messages above). "
                "Fix the input or re-run with --force to write the XML for inspection.",
                issues=[i for i in result.get("validation_issues", []) if i.get("severity") == "ERROR"],
            )

    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(xml_output, encoding="utf-8")
        print(f"[Process2BPMN] Successfully exported BPMN 2.0 to: {output_path}", file=sys.stderr)

    return xml_output


def main():
    parser = argparse.ArgumentParser(
        prog="process2bpmn",
        description="Process2BPMN: Convert unstructured process descriptions into valid, importable BPMN 2.0 files."
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: convert
    convert_parser = subparsers.add_parser("convert", help="Convert document to BPMN 2.0 XML")
    convert_parser.add_argument("input", help="Path to input file (.txt, .md, .csv, .docx, .pdf, .xlsx, .vtt, .srt)")
    convert_parser.add_argument(
        "--profile", "-p",
        default="generic",
        choices=["celonis", "generic"],
        help="Target tool profile (default: generic)"
    )
    convert_parser.add_argument("--output", "-o", help="Output .bpmn file path (default: stdout)")
    convert_parser.add_argument("--mock", action="store_true", default=False, help="Force offline deterministic extraction")
    convert_parser.add_argument("--template", "-t", help="BPMN reference template ID, file path, or structured document template")
    convert_parser.add_argument("--provider", help="LLM Provider (openai_compatible, anthropic, gemini)")
    convert_parser.add_argument("--model", help="LLM Model name")
    convert_parser.add_argument("--base-url", help="LLM Base URL (e.g., http://localhost:11434/v1)")
    convert_parser.add_argument("--api-key", help="LLM API Key")
    convert_parser.add_argument(
        "--force", action="store_true", default=False,
        help="Write the BPMN file even when validation found blocking errors (exit code 0 instead of 2)"
    )

    # Command: profiles
    subparsers.add_parser("profiles", help="List available target-tool export profiles")

    args = parser.parse_args()

    if args.command == "profiles":
        from backend.pipeline.linter import ProfileLinter  # was missing: `profiles` crashed with NameError
        linter = ProfileLinter()
        for p in linter.list_available_profiles():
            data = linter.load_profile(p)
            print(f"  • {p:<10} - {data.get('displayName', p)}: {data.get('description', '')}")
        sys.exit(0)

    elif args.command == "convert":
        try:
            xml = convert_file(
                input_path=args.input,
                output_path=args.output,
                profile_name=args.profile,
                mock=args.mock,
                provider_name=getattr(args, "provider", None),
                model=getattr(args, "model", None),
                base_url=getattr(args, "base_url", None),
                api_key=getattr(args, "api_key", None),
                template=getattr(args, "template", None),
                force=bool(getattr(args, "force", False)),
            )
            if not args.output:
                print(xml)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            # 2 = the process was converted but has blocking validation errors; 1 = any other failure
            sys.exit(2 if e.__class__.__name__ == "ExportBlockedError" else 1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
