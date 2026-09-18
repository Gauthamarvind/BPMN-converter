#!/usr/bin/env python3
"""
Process2BPMN Standalone CLI.
Converts unstructured process documents into BPMN 2.0 XML with full BPMNDI auto-layout.
Usage:
  process2bpmn convert input.docx --profile signavio -o out.bpmn
  python3 -m backend.cli convert input.docx --profile camunda -o out.bpmn
"""

from __future__ import annotations
import sys
import os
import argparse
import json
from pathlib import Path
from typing import Optional

# Ensure project root is in sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.ir.models import ProcessIR, FlowNode, SequenceFlow, Pool, Lane, SourceRef
from backend.pipeline.validator import ProcessValidator
from backend.pipeline.layout import SugiyamaLayoutEngine
from backend.pipeline.serializer import BpmnXmlSerializer
from backend.pipeline.linter import ProfileLinter
from backend.ingestion.parser import ingest_file
from backend.llm.factory import get_llm_provider
from backend.pipeline.chunker import ProcessExtractor
from backend.config import config


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


def convert_file(
    input_path: str,
    output_path: Optional[str] = None,
    profile_name: str = "generic",
    mock: bool = False,
    provider_name: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    template: Optional[str] = None
) -> str:
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Input file '{input_path}' does not exist.")

    title = path.stem.replace("_", " ").title()
    ext = path.suffix.lower()

    # Step 1: Extract (Structured Document Template, LLM, or deterministic mock)
    ir: Optional[ProcessIR] = None

    # Pipeline Hook: Check if document template applies directly
    if ext in (".xlsx", ".csv", ".docx", ".json"):
        try:
            from backend.templates.doc_parser import DocTemplateParser
            doc_parser = DocTemplateParser()
            ir = doc_parser.parse_file(str(path), path.name)
            print(f"[Process2BPMN] Structured document parser mapped {len(ir.elements)} nodes deterministically.")
        except Exception as doc_ex:
            print(f"[Process2BPMN] Document template parse fallback: {doc_ex}")
            ir = None

    if ir is None:
        content_bytes = path.read_bytes()
        doc = ingest_file(content_bytes, path.name)

        if not mock:
            prov = get_llm_provider(
                provider_name=provider_name or config.llm.provider,
                base_url=base_url or config.llm.base_url,
                api_key=api_key or config.llm.api_key,
                model=model or config.llm.model
            )
            extractor = ProcessExtractor(provider=prov)
            ir, usage = extractor.extract(doc.normalized_text, title=title)
            print(f"[Process2BPMN] LLM Extraction successful ({usage.get('total_tokens', 0)} tokens used).")
        else:
            ir = generate_mock_ir_from_text(doc.normalized_text, title=title)

    # Step 2: Validate & Repair
    validator = ProcessValidator(ir)
    repaired_ir, issues = validator.validate_and_repair()
    if issues:
        print(f"[Process2BPMN] Validator identified {len(issues)} repair actions.")

    # Pipeline Hook: Check if BPMN reference template applies
    template_spec = None
    template_raw_xml = None
    if template:
        try:
            from backend.templates.storage import TemplateStorage
            from backend.templates.bpmn_parser import BpmnTemplateParser
            from backend.templates.mapper import LaneMapper
            from backend.templates.models import TemplateBindings

            storage = TemplateStorage()
            template_record = storage.get_template(template)
            if template_record:
                _, template_raw_xml, template_spec = template_record
            elif Path(template).exists():
                template_raw_xml = Path(template).read_text(encoding="utf-8")
                parser = BpmnTemplateParser(Path(template).stem, Path(template).stem, template_raw_xml)
                template_spec, _ = parser.parse()

            if template_spec and template_raw_xml:
                # Extract actors
                actors = [l.name for p in repaired_ir.pools for l in p.lanes]
                mapper = LaneMapper(template_spec)
                mapping_results = mapper.map_actors(actors, use_llm=not mock)
                lane_map = {m.actor: m.lane_id for m in mapping_results if m.lane_id}
                repaired_ir.templateBindings = TemplateBindings(
                    templateId=template_spec.template_id,
                    laneMap=lane_map
                )
                print(f"[Process2BPMN] Conformed to reference template '{template_spec.name}' ({len(lane_map)} lane bindings).")
        except Exception as t_ex:
            print(f"[Process2BPMN] Template application encountered error: {t_ex}")
            template_spec = None
            template_raw_xml = None

    # Step 3: Lint against Profile
    linter = ProfileLinter()
    active_profile = profile_name
    if template_spec and template_spec.source_vendor in ("signavio", "camunda", "aris", "celonis"):
        active_profile = template_spec.source_vendor

    lint_result = linter.lint(repaired_ir, profile_name=active_profile)
    if lint_result.warnings:
        for w in lint_result.warnings:
            print(f"[{w.severity}] {w.code}: {w.message}")

    # Step 4: Sugiyama Auto-Layout (with optional template constraints)
    layout_engine = SugiyamaLayoutEngine(repaired_ir, template_spec=template_spec)
    layout = layout_engine.compute_layout()

    # Step 5: Serialize BPMN 2.0 XML (TemplateRenderer or standard BpmnXmlSerializer)
    profile_config = linter.load_profile(active_profile)
    if template_spec and template_raw_xml:
        from backend.templates.bpmn_renderer import BpmnTemplateRenderer
        renderer = BpmnTemplateRenderer(
            template_raw_xml=template_raw_xml,
            spec=template_spec,
            ir=repaired_ir,
            layout=layout,
            profile_config=profile_config
        )
        xml_output = renderer.render()
    else:
        serializer = BpmnXmlSerializer(repaired_ir, layout, profile_config)
        xml_output = serializer.serialize()

    # Write output if requested
    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(xml_output, encoding="utf-8")
        print(f"[Process2BPMN] Successfully exported BPMN 2.0 to: {output_path}")

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
        choices=["generic", "signavio", "aris", "celonis", "camunda"],
        help="Target tool profile (default: generic)"
    )
    convert_parser.add_argument("--output", "-o", help="Output .bpmn file path (default: stdout)")
    convert_parser.add_argument("--mock", action="store_true", default=False, help="Force offline deterministic extraction")
    convert_parser.add_argument("--template", "-t", help="BPMN reference template ID, file path, or structured document template")
    convert_parser.add_argument("--provider", help="LLM Provider (openai_compatible, anthropic, gemini)")
    convert_parser.add_argument("--model", help="LLM Model name")
    convert_parser.add_argument("--base-url", help="LLM Base URL (e.g., http://localhost:11434/v1)")
    convert_parser.add_argument("--api-key", help="LLM API Key")

    # Command: profiles
    subparsers.add_parser("profiles", help="List available target-tool export profiles")

    args = parser.parse_args()

    if args.command == "profiles":
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
                template=getattr(args, "template", None)
            )
            if not args.output:
                print(xml)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
