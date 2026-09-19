"""
Core End-to-End BPMN 2.0 Conversion Pipeline.
Orchestrates file ingestion, LLM / doc extraction, graph repair,
auto-layout, profile linting, and BPMN XML serialization.

Enforces strict error propagation for LLM failures (no silent fallbacks).
"""

from __future__ import annotations
import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Any

from backend.config import config
from backend.ir.models import ProcessIR, TemplateBindings
from backend.ingestion.parser import ingest_file
from backend.llm.factory import get_llm_provider
from backend.llm.errors import LLMError
from backend.pipeline.chunker import ProcessExtractor
from backend.pipeline.validator import ProcessValidator
from backend.pipeline.layout import SugiyamaLayoutEngine, DiagramLayout, EdgeLayout, Waypoint
from backend.pipeline.serializer import BpmnXmlSerializer
from backend.pipeline.xsd_validator import validate_bpmn, BpmnSchemaError
from backend.pipeline.linter import ProfileLinter
from backend.pipeline.profiles import DEFAULT_PROFILE, SUPPORTED_PROFILES
from backend.pipeline.mock_extractor import generate_mock_ir_from_text
from backend.templates.storage import TemplateStorage
from backend.templates.doc_parser import DocTemplateParser
from backend.templates.simple_parser import (
    SimpleTemplateParser,
    detect_template_kind,
    TEMPLATE_KIND_SIMPLE,
    TEMPLATE_KIND_LEGACY,
)
from backend.templates.mapper import LaneMapper


logger = logging.getLogger(__name__)
template_storage = TemplateStorage()
linter = ProfileLinter()


class ExportBlockedError(Exception):
    """Raised in strict mode when the repaired process still has ERROR-level issues."""

    def __init__(self, message: str, issues: Optional[list] = None, open_questions: Optional[list] = None):
        super().__init__(message)
        self.issues = issues or []
        self.open_questions = open_questions or []


def process_pipeline(
    raw_content: bytes,
    filename: str,
    profile_name: str = DEFAULT_PROFILE,
    mock: bool = False,
    provider_name: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    template_id: Optional[str] = None,
    lane_map: Optional[Dict[str, str]] = None,
    strict: bool = False,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executes the end-to-end Process2BPMN conversion pipeline.

    Args:
        raw_content: Input file or text bytes.
        filename: Name of the input document (determines parser & title).
        profile_name: Target export profile ('celonis' — the default — or 'generic').
        mock: When True, uses deterministic rule-based mock extraction without calling LLM.
        provider_name: LLM provider override ('openai_compatible', 'anthropic', 'gemini').
        model: LLM model name override.
        base_url: LLM API base URL override.
        api_key: LLM API key override.
        template_id: Optional BPMN reference template identifier.
        lane_map: Optional explicit mapping of actor names to template lane IDs.
        strict: When True, raise ExportBlockedError instead of returning XML for a process
            with blocking validation errors (API/CLI consumers that must not receive an
            unreviewed diagram). The UI leaves this False so it can show what is wrong.

    Returns:
        Dict containing bpmn_xml, IR dictionary, validation issues, lint results, template info, and metadata.

    Raises:
        LLMError or subclass: When LLM extraction fails in non-mock mode.
        RuntimeError / ValueError: On fatal parsing or pipeline failures.
    """
    title = Path(filename).stem.replace("_", " ").title()
    ext = Path(filename).suffix.lower()
    # "provider=mock" and "mock=true" are the same request: one rule engine, one code path.
    effective_provider = (provider_name or config.llm.provider or "").strip().lower()
    mock = bool(mock) or effective_provider == "mock"
    logger.info(f"[ProcessPipeline] Starting conversion for '{filename}' (profile={profile_name}, mock={mock})")

    # 1. Pipeline Hook: Check if file is a structured document template via signature detection
    ir: Optional[ProcessIR] = None
    extraction_meta = {"mode": "llm", "tokens_used": 0}

    template_kind = detect_template_kind(raw_content, filename)
    if template_kind == TEMPLATE_KIND_SIMPLE:
        simple_parser = SimpleTemplateParser()
        ir = simple_parser.parse_bytes(raw_content, filename)
        extraction_meta["mode"] = "simple_template_parser"
        logger.info(f"[ProcessPipeline] SimpleTemplateParser extracted {len(ir.elements)} elements from '{filename}'")
    elif template_kind == TEMPLATE_KIND_LEGACY:
        try:
            doc_parser = DocTemplateParser()
            ir = doc_parser.parse_bytes(raw_content, filename)
            extraction_meta["mode"] = "doc_template_parser"
            logger.info(f"[ProcessPipeline] Legacy DocTemplateParser extracted {len(ir.elements)} elements from '{filename}'")
        except Exception as doc_ex:
            logger.debug(f"[ProcessPipeline] Legacy template parser error ({doc_ex}); proceeding to standard text ingestion.")
            ir = None
    else:
        # Not a template: standard document / SOP text ingestion
        ir = None

    # 2. Ingestion & Process Extraction (LLM or Rule-based Mock)
    doc = None
    if ir is None:
        doc = ingest_file(raw_content, filename)

        if mock:
            logger.info(f"[ProcessPipeline] Using deterministic rule engine mock for '{filename}'")
            ir = generate_mock_ir_from_text(doc.normalized_text, title=title)
            extraction_meta["mode"] = "deterministic_rule_engine"
        else:
            logger.info(f"[ProcessPipeline] Initiating LLM extraction with provider={provider_name or config.llm.provider}")
            try:
                prov = get_llm_provider(
                    provider_name=provider_name or config.llm.provider,
                    base_url=base_url or config.llm.base_url,
                    api_key=api_key or config.llm.api_key,
                    model=model or config.llm.model
                )
                extractor = ProcessExtractor(provider=prov)
                ir, usage = extractor.extract(doc.normalized_text, title=title)
                extraction_meta["tokens_used"] = usage.get("total_tokens", 0)
                logger.info(f"[ProcessPipeline] LLM extraction completed. Tokens used: {extraction_meta['tokens_used']}")
            except LLMError as llm_err:
                logger.error(f"[ProcessPipeline] LLM extraction error for '{filename}': {llm_err}")
                raise
            except Exception as ex:
                logger.error(f"[ProcessPipeline] Unexpected failure during LLM extraction for '{filename}': {ex}")
                raise RuntimeError(f"LLM extraction failed: {str(ex)}") from ex

    # Ensure IR was successfully extracted
    if ir is None:
        raise ValueError(f"Failed to extract Process IR from '{filename}'")

    return render_ir(
        ir=ir,
        filename=filename,
        profile_name=profile_name,
        mock=mock,
        template_id=template_id,
        lane_map=lane_map,
        extraction_meta=extraction_meta,
        normalized_text=doc.normalized_text if doc else "",
        strict=strict,
        user_id=user_id,
    )


def _straight_edge(layout: DiagramLayout, flow: Any) -> EdgeLayout:
    """A straight connector for a flow the validator added to a preset (imported) layout."""
    src = layout.nodes.get(flow.sourceId)
    tgt = layout.nodes.get(flow.targetId)
    if not src or not tgt:
        return EdgeLayout(flow_id=flow.id, waypoints=[Waypoint(x=0.0, y=0.0), Waypoint(x=0.0, y=0.0)])
    return EdgeLayout(
        flow_id=flow.id,
        waypoints=[
            Waypoint(x=src.bounds.x + src.bounds.width, y=src.bounds.y + src.bounds.height / 2),
            Waypoint(x=tgt.bounds.x, y=tgt.bounds.y + tgt.bounds.height / 2),
        ],
    )


def render_ir(
    ir: ProcessIR,
    filename: str = "process.bpmn",
    profile_name: str = DEFAULT_PROFILE,
    mock: bool = False,
    template_id: Optional[str] = None,
    lane_map: Optional[Dict[str, str]] = None,
    extraction_meta: Optional[Dict[str, Any]] = None,
    normalized_text: str = "",
    strict: bool = False,
    user_id: Optional[str] = None,
    preset_layout: Optional[DiagramLayout] = None,
) -> Dict[str, Any]:
    """
    Stages 3-8 of the pipeline: validate/repair an existing Process IR, bind an optional
    reference template, lint against the target profile, lay out, serialize, XSD-validate.
    Used by process_pipeline() after extraction and by /api/render to switch target tools,
    templates or lane mappings without calling the model again.

    ``preset_layout`` carries coordinates that already exist — the diagram interchange of an
    imported BPMN file — so an import keeps the shape it had in the tool it came from. It is
    ignored when a reference template is bound (the template owns the geometry) or when the
    validator had to add elements the preset does not cover.
    """
    # 3. Deterministic Validation & Repair
    logger.info(f"[ProcessPipeline] Validating and repairing process graph...")
    validator = ProcessValidator(ir)
    repaired_ir, raw_issues = validator.validate_and_repair()
    issues = [
        {
            "severity": iss.severity,
            "message": iss.message,
            "element_id": iss.element_id,
            "auto_fixed": iss.auto_fixed,
            "details": iss.details
        }
        for iss in raw_issues
    ]
    logger.info(f"[ProcessPipeline] Validation complete. {len(issues)} issues detected/repaired.")

    # 4. Pipeline Hook: Apply Reference BPMN Template if requested
    template_spec = None
    template_raw_xml = None
    template_info = None

    if template_id:
        record = template_storage.get_template(template_id, user_id=user_id)
        if not record:
            raise ValueError(f"Template '{template_id}' was not found or is not available to you.")
        if record:
            meta, template_raw_xml, template_spec = record
            if not lane_map:
                actors = [l.name for p in repaired_ir.pools for l in p.lanes]
                mapper = LaneMapper(template_spec)
                mapping_res = mapper.map_actors(actors, use_llm=not mock)
                lane_map = {m.actor: m.lane_id for m in mapping_res if m.lane_id}

            repaired_ir.templateBindings = TemplateBindings(
                templateId=template_id,
                laneMap=lane_map or {}
            )
            # A Celonis reference template pins the Celonis profile; templates exported from
            # other tools (Camunda, Signavio, ARIS, ...) keep whatever target the caller chose.
            if template_spec.source_vendor == "celonis":
                profile_name = "celonis"

            template_info = {
                "template_id": template_id,
                "name": meta.name,
                "source_vendor": template_spec.source_vendor,
                "lane_map": lane_map or {}
            }
            logger.info(f"[ProcessPipeline] Bound reference template '{meta.name}' ({len(lane_map or {})} lanes)")

    # 5. Profile Linter
    logger.info(f"[ProcessPipeline] Linting process against profile '{profile_name}'...")
    lint_res = linter.lint(repaired_ir, profile_name=profile_name)
    lint_dict = {
        "profile_name": lint_res.profile_name,
        "display_name": lint_res.display_name,
        "is_valid": lint_res.is_valid,
        "assumptions": lint_res.assumptions,
        "warnings": [
            {"code": w.code, "message": w.message, "severity": w.severity, "element_id": w.element_id}
            for w in lint_res.warnings
        ]
    }

    # 6. Layout: keep supplied coordinates when they cover the graph, else Sugiyama.
    layout = None
    if preset_layout is not None and template_spec is None:
        missing = [e.id for e in repaired_ir.elements if e.id not in preset_layout.nodes]
        if missing:
            logger.info(
                "[ProcessPipeline] Preset layout misses %s repaired element(s); using auto-layout instead.",
                len(missing),
            )
        else:
            logger.info("[ProcessPipeline] Using the supplied (imported) diagram layout.")
            layout = preset_layout
            for flow in repaired_ir.flows:
                if flow.id not in layout.edges:
                    layout.edges[flow.id] = _straight_edge(layout, flow)

    if layout is None:
        logger.info(f"[ProcessPipeline] Computing Sugiyama auto-layout...")
        layout_engine = SugiyamaLayoutEngine(repaired_ir, template_spec=template_spec)
        layout = layout_engine.compute_layout()

    # 7. BPMN 2.0 XML Serialization (TemplateRenderer or standard Serializer)
    profile_config = linter.load_profile(profile_name)
    if template_spec and template_raw_xml:
        from backend.templates.bpmn_renderer import BpmnTemplateRenderer
        renderer = BpmnTemplateRenderer(
            template_raw_xml=template_raw_xml,
            spec=template_spec,
            ir=repaired_ir,
            layout=layout,
            profile_config=profile_config
        )
        bpmn_xml = renderer.render()
    else:
        serializer = BpmnXmlSerializer(repaired_ir, layout, profile_config)
        bpmn_xml = serializer.serialize()

    # Strict BPMN 2.0 XSD Schema Validation
    schema_errors = validate_bpmn(bpmn_xml)
    if schema_errors:
        raise BpmnSchemaError(
            f"Generated BPMN XML failed XSD schema validation ({len(schema_errors)} errors)",
            errors=schema_errors
        )

    # 8. Multi-Profile Bulk Export Metadata
    supported_profiles = list(SUPPORTED_PROFILES)
    bulk_export = {
        "process_name": repaired_ir.name or Path(filename).stem,
        "supported_profiles": supported_profiles,
        "available_formats": [".bpmn", ".svg", ".png"]
    }

    export_blocked = validator.export_blocked or any(iss.get("severity") == "ERROR" for iss in issues)

    logger.info(f"[ProcessPipeline] Conversion successful for '{filename}'. Generated {len(bpmn_xml)} bytes XML. export_blocked={export_blocked}")

    if strict and export_blocked:
        raise ExportBlockedError(
            "The process has blocking validation errors; export refused in strict mode.",
            issues=[iss for iss in issues if iss.get("severity") == "ERROR"],
            open_questions=[q.model_dump() for q in repaired_ir.openQuestions],
        )

    return {
        "success": True,
        "export_blocked": export_blocked,
        "bpmn_xml": bpmn_xml,
        "ir": repaired_ir.to_dict(),
        "validation_issues": issues,
        "lint_result": lint_dict,
        "template_info": template_info,
        "bulk_export": bulk_export,
        "metadata": {
            "filename": filename,
            "process_name": repaired_ir.name,
            "element_count": len(repaired_ir.elements),
            "flow_count": len(repaired_ir.flows),
            "pool_count": len(repaired_ir.pools),
            "lane_count": sum(len(p.lanes) for p in repaired_ir.pools),
            "extraction": extraction_meta or {"mode": "render", "tokens_used": 0}
        },
        "normalized_text": normalized_text
    }


def import_bpmn_pipeline(
    raw_content: bytes,
    filename: str = "imported.bpmn",
    profile_name: str = DEFAULT_PROFILE,
    relayout: bool = False,
    template_id: Optional[str] = None,
    lane_map: Optional[Dict[str, str]] = None,
    strict: bool = False,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Imports a BPMN 2.0 file exported from another tool and re-exports it for the target
    profile. Deterministic: no model is called at any point.

    The source file's own coordinates are kept unless ``relayout`` is set, in which case the
    Sugiyama engine lays the diagram out from scratch.
    """
    from backend.ingestion.bpmn_importer import import_bpmn_bytes

    logger.info(f"[ProcessPipeline] Importing BPMN file '{filename}' (relayout={relayout})...")
    ir, layout, report = import_bpmn_bytes(raw_content, filename=filename)

    result = render_ir(
        ir=ir,
        filename=filename,
        profile_name=profile_name,
        mock=True,
        template_id=template_id,
        lane_map=lane_map,
        extraction_meta={"mode": "bpmn-import", "tokens_used": 0},
        normalized_text="",
        strict=strict,
        user_id=user_id,
        preset_layout=None if relayout else layout,
    )

    report.original_layout = bool(layout) and not relayout
    result["import_info"] = report.to_dict()
    result["metadata"]["source_vendor"] = report.source_vendor
    logger.info(
        "[ProcessPipeline] Imported %s elements / %s flows from a %s file.",
        report.element_count,
        report.flow_count,
        report.source_vendor,
    )
    return result
