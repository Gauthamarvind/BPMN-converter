"""
Process2BPMN FastAPI Application.
Exposes REST endpoints for document ingestion, LLM-based & rule-based process extraction,
graph repair, Sugiyama layout, profile-based linter, and BPMN 2.0 XML serialization.
"""

from __future__ import annotations
import os
import sys
import re
import io
import time
import base64
import zipfile
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

# Ensure project root is in sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Body, Response, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.config import config
from backend.ir.models import ProcessIR, TemplateBindings
from backend.ingestion.parser import ingest_file, IngestionError
from backend.llm.errors import (
    LLMError,
    LLMConfigurationError,
    LLMAuthenticationError,
    LLMConnectionError,
    LLMResponseError,
    LLMRateLimitError,
    LLMValidationError,
)
from backend.llm.factory import get_llm_provider
from backend.pipeline.chunker import ProcessExtractor
from backend.pipeline.validator import ProcessValidator
from backend.pipeline.layout import SugiyamaLayoutEngine
from backend.pipeline.serializer import BpmnXmlSerializer
from backend.pipeline.xsd_validator import BpmnSchemaError, BpmnSchemaConfigurationError
from backend.pipeline.linter import ProfileLinter
from backend.pipeline.process_pipeline import process_pipeline
from backend.cli import generate_mock_ir_from_text
from backend.templates.storage import TemplateStorage
from backend.templates.doc_parser import DocTemplateParser
from backend.templates.mapper import LaneMapper
from backend.templates.bpmn_renderer import BpmnTemplateRenderer
from backend.templates.bpmn_parser import BpmnTemplateParser
from backend.templates.blank_generator import generate_blank_xlsx, generate_blank_docx

logger = logging.getLogger(__name__)

template_storage = TemplateStorage()

app = FastAPI(
    title="Process2BPMN API",
    description="Converts unstructured process descriptions into valid, importable BPMN 2.0 files.",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

linter = ProfileLinter()


# =========================================================================
# EXCEPTION HANDLERS
# =========================================================================

@app.exception_handler(IngestionError)
async def ingestion_error_handler(request: Request, exc: IngestionError):
    return JSONResponse(
        status_code=400,
        content={"error": str(exc), "detail": str(exc), "kind": "IngestionError"}
    )


@app.exception_handler(BpmnSchemaError)
async def bpmn_schema_error_handler(request: Request, exc: BpmnSchemaError):
    return JSONResponse(
        status_code=422,
        content={
            "error": str(exc),
            "detail": str(exc),
            "kind": "BpmnSchemaError",
            "errors": exc.errors,
        }
    )


@app.exception_handler(BpmnSchemaConfigurationError)
async def bpmn_schema_configuration_error_handler(request: Request, exc: BpmnSchemaConfigurationError):
    return JSONResponse(
        status_code=500,
        content={
            "error": str(exc),
            "detail": str(exc),
            "kind": "BpmnSchemaConfigurationError",
        }
    )


@app.exception_handler(LLMConfigurationError)
async def llm_configuration_error_handler(request: Request, exc: LLMConfigurationError):
    return JSONResponse(
        status_code=400,
        content={
            "error": str(exc),
            "detail": str(exc),
            "kind": getattr(exc, "kind", "LLMConfigurationError"),
            "provider": getattr(exc, "provider", None) or getattr(config.llm, "provider", None),
            "model": getattr(exc, "model", None) or getattr(config.llm, "model", None),
        }
    )


@app.exception_handler(LLMAuthenticationError)
async def llm_authentication_error_handler(request: Request, exc: LLMAuthenticationError):
    return JSONResponse(
        status_code=401,
        content={
            "error": str(exc),
            "detail": str(exc),
            "kind": getattr(exc, "kind", "LLMAuthenticationError"),
            "provider": getattr(exc, "provider", None) or getattr(config.llm, "provider", None),
            "model": getattr(exc, "model", None) or getattr(config.llm, "model", None),
        }
    )


@app.exception_handler(LLMConnectionError)
@app.exception_handler(LLMResponseError)
@app.exception_handler(LLMRateLimitError)
@app.exception_handler(LLMValidationError)
async def llm_gateway_error_handler(request: Request, exc: LLMError):
    return JSONResponse(
        status_code=502,
        content={
            "error": str(exc),
            "kind": getattr(exc, "kind", exc.__class__.__name__),
            "provider": getattr(exc, "provider", None) or getattr(config.llm, "provider", None),
            "model": getattr(exc, "model", None) or getattr(config.llm, "model", None),
        }
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    if isinstance(exc, (LLMConnectionError, LLMResponseError, LLMRateLimitError, LLMValidationError)):
        return JSONResponse(
            status_code=502,
            content={
                "error": str(exc),
                "kind": getattr(exc, "kind", exc.__class__.__name__),
                "provider": getattr(exc, "provider", None) or getattr(config.llm, "provider", None),
                "model": getattr(exc, "model", None) or getattr(config.llm, "model", None),
            }
        )
    return JSONResponse(
        status_code=400,
        content={"error": str(exc), "detail": str(exc), "kind": "ValueError"}
    )


class ConvertTextRequest(BaseModel):
    text: str
    filename: Optional[str] = "process_input.txt"
    profile: Optional[str] = "generic"
    provider: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    mock: Optional[bool] = False
    template_id: Optional[str] = None
    lane_map: Optional[Dict[str, str]] = None


class MapLanesRequest(BaseModel):
    template_id: str
    actors: List[str]


class LintRequest(BaseModel):
    ir: Optional[Dict[str, Any]] = None
    profile: str = "generic"


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "Process2BPMN",
        "version": "1.0.0",
        "active_provider": config.llm.provider,
        "active_model": config.llm.model,
        "base_url": config.llm.base_url
    }


@app.get("/api/profiles")
def get_profiles():
    profiles_data = []
    for p_id in linter.list_available_profiles():
        prof = linter.load_profile(p_id)
        profiles_data.append({
            "id": p_id,
            "name": prof.get("name", p_id),
            "displayName": prof.get("displayName", p_id),
            "description": prof.get("description", ""),
            "assumptions": prof.get("assumptions", []),
            "targetVendor": prof.get("targetVendor", "")
        })
    return {"profiles": profiles_data}


@app.get("/api/samples")
def get_samples():
    samples_dir = _PROJECT_ROOT / "samples"
    samples = []
    if samples_dir.exists():
        for f in sorted(samples_dir.iterdir()):
            if f.is_file() and not f.name.endswith(".bpmn"):
                try:
                    content = f.read_text(encoding="utf-8", errors="ignore")
                    samples.append({
                        "name": f.name,
                        "title": f.stem.replace("_", " ").title(),
                        "extension": f.suffix,
                        "content": content
                    })
                except Exception:
                    pass
    return {"samples": samples}


# =========================================================================
# TEMPLATE MANAGEMENT ENDPOINTS
# =========================================================================

@app.get("/api/templates")
def list_templates():
    """Lists all stored reference and document templates."""
    templates = template_storage.list_templates()
    return {"templates": [t.model_dump() for t in templates]}


@app.get("/api/templates/{template_id}")
def get_template(template_id: str):
    """Fetches details, raw XML, and parsed specification for a template."""
    record = template_storage.get_template(template_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found.")
    meta, raw_xml, spec = record
    return {
        "metadata": meta.model_dump(),
        "spec": spec.model_dump(),
        "xml": raw_xml
    }


@app.post("/api/templates/upload")
async def upload_template(
    file: UploadFile = File(...),
    description: Optional[str] = Form(None)
):
    """Uploads and indexes a reference BPMN XML template file."""
    raw_bytes = await file.read()
    raw_xml = raw_bytes.decode("utf-8", errors="ignore")
    try:
        meta, report = template_storage.save_template(
            xml_content=raw_xml,
            filename=file.filename or "template.bpmn",
            description=description or ""
        )
        return {
            "success": True,
            "template": meta.model_dump(),
            "report": report.model_dump()
        }
    except Exception as ex:
        raise HTTPException(status_code=400, detail=f"Template indexing error: {str(ex)}")


@app.delete("/api/templates/{template_id}")
def delete_template(template_id: str):
    """Deletes a custom template."""
    success = template_storage.delete_template(template_id)
    if not success:
        raise HTTPException(status_code=404, detail="Template not found.")
    return {"success": True}


@app.post("/api/templates/{template_id}/default")
def set_default_template(template_id: str):
    """Sets a template as the default for matching export profiles."""
    success = template_storage.set_default(template_id)
    if not success:
        raise HTTPException(status_code=404, detail="Template not found.")
    return {"success": True}


@app.post("/api/templates/map-lanes")
def map_actors_to_lanes(req: MapLanesRequest):
    """Maps extracted process actors/roles to reference template lanes."""
    record = template_storage.get_template(req.template_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Template '{req.template_id}' not found.")
    _, _, spec = record

    mapper = LaneMapper(spec)
    mapping_result = mapper.map_actors(req.actors)
    return mapping_result.model_dump()


@app.get("/api/templates/download-blank/{format_type}")
def download_blank_template(format_type: str):
    """Downloads a pre-formatted Excel or Word template for structured capture."""
    fmt = format_type.lower()
    if fmt == "xlsx":
        file_bytes = generate_blank_xlsx()
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = "Process_Capture_Template.xlsx"
    elif fmt == "docx":
        file_bytes = generate_blank_docx()
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        filename = "Process_Capture_Template.docx"
    else:
        raise HTTPException(status_code=400, detail="Invalid format type. Supported: 'xlsx', 'docx'.")

    return Response(
        content=file_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


MAX_UPLOAD_SIZE_BYTES = int(os.environ.get("MAX_UPLOAD_SIZE_BYTES", 20 * 1024 * 1024))


@app.post("/api/convert")
async def convert_document(
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    filename: Optional[str] = Form("process_input.txt"),
    profile: Optional[str] = Form("generic"),
    mock: Optional[bool] = Form(False),
    provider: Optional[str] = Form(None),
    model: Optional[str] = Form(None),
    base_url: Optional[str] = Form(None),
    api_key: Optional[str] = Form(None),
    template_id: Optional[str] = Form(None),
    lane_map: Optional[str] = Form(None)
):
    import json
    if file is not None:
        raw_content = await file.read()
        fname = file.filename or filename or "uploaded_process.txt"
    elif text:
        raw_content = text.encode("utf-8")
        fname = filename or "pasted_process.txt"
    else:
        raise HTTPException(status_code=400, detail="Either a file upload or text body must be provided.")

    # 1. Enforce size limit (default 20 MB)
    if len(raw_content) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum upload size limit of {MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)}MB."
        )

    # 2. Detect type by extension plus magic bytes
    ext = Path(fname).suffix.lower()
    if ext in (".xlsx", ".docx"):
        if not raw_content.startswith(b"PK"):
            raise HTTPException(
                status_code=415,
                detail=f"File extension '{ext}' does not match file contents (expected PK zip signature)."
            )
    elif ext == ".pdf":
        if not raw_content.startswith(b"%PDF"):
            raise HTTPException(
                status_code=415,
                detail="File extension '.pdf' does not match file contents (expected %PDF signature)."
            )

    lane_map_dict = None
    if lane_map:
        try:
            lane_map_dict = json.loads(lane_map)
        except Exception:
            pass

    return process_pipeline(
        raw_content=raw_content,
        filename=fname,
        profile_name=profile or "generic",
        mock=mock or False,
        provider_name=provider,
        model=model,
        base_url=base_url,
        api_key=api_key,
        template_id=template_id,
        lane_map=lane_map_dict
    )


@app.post("/api/convert-json")
def convert_json_payload(req: ConvertTextRequest):
    raw_content = req.text.encode("utf-8")
    return process_pipeline(
        raw_content=raw_content,
        filename=req.filename or "process_input.txt",
        profile_name=req.profile or "generic",
        mock=req.mock or False,
        provider_name=req.provider,
        model=req.model,
        base_url=req.base_url,
        api_key=req.api_key,
        template_id=req.template_id,
        lane_map=req.lane_map
    )


@app.post("/api/lint")
def lint_process(req: LintRequest):
    if not req.ir:
        return {"is_valid": True, "warnings": [], "assumptions": []}
    ir = ProcessIR.from_dict(req.ir)
    res = linter.lint(ir, profile_name=req.profile)
    return {
        "profile_name": res.profile_name,
        "display_name": res.display_name,
        "is_valid": res.is_valid,
        "assumptions": res.assumptions,
        "warnings": [
            {"code": w.code, "message": w.message, "severity": w.severity, "element_id": w.element_id}
            for w in res.warnings
        ]
    }


@app.post("/api/export/bulk")
def export_bulk_zip(data: Dict[str, Any]):
    """Accepts process_name, optional ir, optional bpmn_by_profile, svg, png and generates a downloadable ZIP bundle with on-demand multi-profile serialization."""
    process_name = data.get("process_name", "process")
    safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', process_name).lower()
    bpmn_by_profile = dict(data.get("bpmn_by_profile") or {})
    svg_content = data.get("svg")
    png_base64 = data.get("png_base64")
    ir_data = data.get("ir")
    template_id = data.get("template_id")

    supported_profiles = ["generic", "camunda", "signavio", "celonis", "aris"]

    # If profiles not all present and IR is provided, re-serialize server-side on-demand
    if ir_data:
        try:
            ir_obj = ProcessIR.from_dict(ir_data)
            template_spec = None
            template_raw_xml = None
            if template_id:
                record = template_storage.get_template(template_id)
                if record:
                    _, template_raw_xml, template_spec = record

            layout_engine = SugiyamaLayoutEngine(ir_obj, template_spec=template_spec)
            layout = layout_engine.compute_layout()

            for p_name in supported_profiles:
                if p_name not in bpmn_by_profile:
                    p_cfg = linter.load_profile(p_name)
                    if template_spec and template_raw_xml:
                        p_renderer = BpmnTemplateRenderer(
                            template_raw_xml=template_raw_xml,
                            spec=template_spec,
                            ir=ir_obj,
                            layout=layout,
                            profile_config=p_cfg
                        )
                        bpmn_by_profile[p_name] = p_renderer.render()
                    else:
                        p_serializer = BpmnXmlSerializer(ir_obj, layout, p_cfg)
                        bpmn_by_profile[p_name] = p_serializer.serialize()
        except Exception as ser_ex:
            logger.error(f"[Process2BPMN Bulk Export] Error re-serializing profiles: {ser_ex}")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # Write BPMN for each profile
        for prof, xml_str in bpmn_by_profile.items():
            zf.writestr(f"{safe_name}_{prof}.bpmn", xml_str)

        # Write SVG if provided
        if svg_content:
            zf.writestr(f"{safe_name}.svg", svg_content)

        # Write PNG if provided
        if png_base64:
            if "," in png_base64:
                png_base64 = png_base64.split(",", 1)[1]
            png_bytes = base64.b64decode(png_base64)
            zf.writestr(f"{safe_name}.png", png_bytes)

        # Write README manifest
        readme = f"""Process2BPMN Complete Process Package
===================================
Process Name: {process_name}
Generated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}

Files Included:
"""
        for prof in bpmn_by_profile.keys():
            readme += f"- {safe_name}_{prof}.bpmn : BPMN 2.0 XML ({prof.capitalize()} profile)\n"
        if svg_content:
            readme += f"- {safe_name}.svg : Scalable Vector Graphics diagram\n"
        if png_base64:
            readme += f"- {safe_name}.png : High-resolution raster diagram\n"

        zf.writestr("README.txt", readme)

    zip_buffer.seek(0)
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}_all_formats.zip"'}
    )


# Serve built frontend from dist/ at / (StaticFiles with SPA fallback to index.html)
dist_dir = _PROJECT_ROOT / "dist"
if dist_dir.exists():
    assets_dir = dist_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path.startswith("api"):
            raise HTTPException(status_code=404, detail="API endpoint not found")
        target_file = dist_dir / full_path
        if full_path and target_file.is_file():
            return FileResponse(target_file)
        index_file = dist_dir / "index.html"
        if index_file.is_file():
            return FileResponse(index_file)
        raise HTTPException(status_code=404, detail="Not Found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.server:app", host="0.0.0.0", port=8000, reload=False)
