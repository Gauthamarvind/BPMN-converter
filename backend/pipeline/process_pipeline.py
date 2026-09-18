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
from backend.pipeline.layout import SugiyamaLayoutEngine
from backend.pipeline.serializer import BpmnXmlSerializer
from backend.pipeline.linter import ProfileLinter
from backend.cli import generate_mock_ir_from_text
from backend.templates.storage import TemplateStorage
from backend.templates.doc_parser import DocTemplateParser
from backend.templates.mapper import LaneMapper
from backend.templates.bpmn_renderer import BpmnTemplateRenderer

logger = logging.getLogger(__name__)
template_storage = TemplateStorage()
linter = ProfileLinter()


def process_pipeline(
    raw_content: bytes,
    filename: str,
    profile_name: str = "generic",
    mock: bool = False,
    provider_name: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    template_id: Optional[str] = None,
    lane_map: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Executes the end-to-end Process2BPMN conversion pipeline.

    Args:
        raw_content: Input file or text bytes.
        filename: Name of the input document (determines parser & title).
        profile_name: Target BPMN vendor profile ('generic', 'camunda', 'signavio', 'celonis', 'aris').
        mock: When True, uses deterministic rule-based mock extraction without calling LLM.
        provider_name: LLM provider override ('openai_compatible', 'anthropic', 'gemini').
        model: LLM model name override.
        base_url: LLM API base URL override.
        api_key: LLM API key override.
        template_id: Optional BPMN reference template identifier.
        lane_map: Optional explicit mapping of actor names to template lane IDs.

    Returns:
        Dict containing bpmn_xml, IR dictionary, validation issues, lint results, template info, and metadata.

    Raises:
        LLMError or subclass: When LLM extraction fails in non-mock mode.
        RuntimeError / ValueError: On fatal parsing or pipeline failures.
    """
    title = Path(filename).stem.replace("_", " ").title()
    ext = Path(filename).suffix.lower()
    logger.info(f"[ProcessPipeline] Starting conversion for '{filename}' (profile={profile_name}, mock={mock})")

    # 1. Pipeline Hook: Check if file is a structured document template
    ir: Optional[ProcessIR] = None
    extraction_meta = {"mode": "llm", "tokens_used": 0}

    if ext in (".xlsx", ".csv", ".docx", ".json"):
        try:
            doc_parser = DocTemplateParser()
            ir = doc_parser.parse_bytes(raw_content, filename)
            extraction_meta["mode"] = "doc_template_parser"
            logger.info(f"[ProcessPipeline] Document template parser extracted {len(ir.elements)} elements from '{filename}'")
        except Exception as doc_ex:
            logger.debug(f"[ProcessPipeline] File is not a structured template ({doc_ex}); proceeding to standard text ingestion.")
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
        record = template_storage.get_template(template_id)
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
            if template_spec.source_vendor in ("signavio", "camunda", "aris", "celonis"):
                profile_name = template_spec.source_vendor

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

    # 6. Sugiyama Auto-Layout Engine (passes optional template constraints)
    logger.info(f"[ProcessPipeline] Computing Sugiyama auto-layout...")
    layout_engine = SugiyamaLayoutEngine(repaired_ir, template_spec=template_spec)
    layout = layout_engine.compute_layout()

    # 7. BPMN 2.0 XML Serialization (TemplateRenderer or standard Serializer)
    profile_config = linter.load_profile(profile_name)
    if template_spec and template_raw_xml:
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

    # 8. Multi-Profile Bulk Export Metadata
    supported_profiles = ["generic", "camunda", "signavio", "celonis", "aris"]
    bulk_export = {
        "process_name": repaired_ir.name or Path(filename).stem,
        "supported_profiles": supported_profiles,
        "available_formats": [".bpmn", ".svg", ".png"]
    }

    logger.info(f"[ProcessPipeline] Conversion successful for '{filename}'. Generated {len(bpmn_xml)} bytes XML.")

    return {
        "success": True,
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
            "extraction": extraction_meta
        },
        "normalized_text": doc.normalized_text if doc else ""
    }
