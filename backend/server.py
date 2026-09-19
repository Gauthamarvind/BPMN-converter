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
import json
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
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel

from backend.config import config
from backend.version import VERSION
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
from backend.pipeline.profiles import DEFAULT_PROFILE, SUPPORTED_PROFILES
from backend.pipeline.process_pipeline import process_pipeline, render_ir, ExportBlockedError
from backend.pipeline.xsd_validator import validate_bpmn
from backend.security import (
    security,
    AuthMiddleware,
    current_user,
    client_key,
    rate_limiter,
    extraction_slot,
    ExtractionSlot,
    validate_base_url,
    LOCAL_USER,
)
from backend.pipeline.mock_extractor import generate_mock_ir_from_text
from backend.templates.storage import TemplateStorage
from backend.templates.doc_parser import DocTemplateParser
from backend.templates.mapper import LaneMapper
from backend.templates.bpmn_renderer import BpmnTemplateRenderer
from backend.templates.bpmn_parser import BpmnTemplateParser
from backend.templates.blank_generator import generate_blank_xlsx, generate_blank_docx
from backend.templates.simple_parser import RowValidationError, RowIssue

logger = logging.getLogger(__name__)

template_storage = TemplateStorage()

app = FastAPI(
    title="Process2BPMN API",
    description="Converts unstructured process descriptions into valid, importable BPMN 2.0 files.",
    version="1.0.0"
)

# CORS: the SPA is served from this same origin (or proxied by Vite in dev), so no
# cross-origin access is needed by default. Set CORS_ALLOW_ORIGINS=https://a.example,https://b.example
# to allow other front-ends. "*" together with credentials is never sent (browsers reject it).
if security.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=security.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

# Authentication / identity (APP_AUTH_MODE=none|proxy|token, see backend/security.py)
app.add_middleware(AuthMiddleware)

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


@app.exception_handler(RowValidationError)
async def row_validation_error_handler(request: Request, exc: RowValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation failed on template rows",
            "kind": "RowValidationError",
            "message": str(exc),
            "row_errors": [
                {
                    "row": issue.row,
                    "column": issue.column,
                    "message": issue.message,
                    "severity": issue.severity,
                    "fix": issue.fix
                }
                for issue in exc.issues
            ]
        }
    )


@app.exception_handler(ExportBlockedError)
async def export_blocked_handler(request: Request, exc: ExportBlockedError):
    return JSONResponse(
        status_code=422,
        content={
            "error": str(exc),
            "detail": str(exc),
            "kind": "ExportBlockedError",
            "export_blocked": True,
            "validation_issues": exc.issues,
            "open_questions": exc.open_questions,
        }
    )


@app.exception_handler(ExtractionSlot.BusyError)
async def busy_handler(request: Request, exc: ExtractionSlot.BusyError):
    return JSONResponse(
        status_code=503,
        headers={"Retry-After": "15"},
        content={"error": str(exc), "detail": str(exc), "kind": "ServerBusy"}
    )


@app.exception_handler(PermissionError)
async def permission_error_handler(request: Request, exc: PermissionError):
    return JSONResponse(
        status_code=403,
        content={"error": str(exc) or "Forbidden", "detail": str(exc) or "Forbidden", "kind": "Forbidden"}
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
    profile: Optional[str] = DEFAULT_PROFILE
    provider: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    mock: Optional[bool] = False
    template_id: Optional[str] = None
    lane_map: Optional[Dict[str, str]] = None
    strict: Optional[bool] = False


class MapLanesRequest(BaseModel):
    template_id: str
    actors: List[str]


class LintRequest(BaseModel):
    ir: Optional[Dict[str, Any]] = None
    profile: str = DEFAULT_PROFILE


class RenderRequest(BaseModel):
    ir: Dict[str, Any]
    profile: str = DEFAULT_PROFILE
    template_id: Optional[str] = None
    lane_map: Optional[Dict[str, str]] = None
    filename: str = "process.bpmn"
    strict: Optional[bool] = False


class BulkExportRequest(BaseModel):
    process_name: Optional[str] = "process"
    ir: Dict[str, Any]
    template_id: Optional[str] = None
    lane_map: Optional[Dict[str, str]] = None
    svg: Optional[str] = None
    png_base64: Optional[str] = None
    profiles: Optional[List[str]] = None


class BpmnExportRequest(BaseModel):
    ir: Dict[str, Any]
    profile: str = DEFAULT_PROFILE
    template_id: Optional[str] = None
    lane_map: Optional[Dict[str, str]] = None
    process_name: Optional[str] = "process"


class LLMPingRequest(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None


def _llm_overrides(request: Request, provider: Optional[str], model: Optional[str],
                   base_url: Optional[str], api_key: Optional[str]):
    """
    Applies the deployment policy to per-request model settings.
    - base_url is always validated against the SSRF rules (private ranges, metadata hosts, allowlist).
    - With ALLOW_CLIENT_LLM_OVERRIDES=false, everything except provider=mock is ignored and the
      server's .env configuration is used (the org pays with one key, users cannot redirect calls).
    """
    provider = (provider or "").strip() or None
    if not security.allow_client_llm_overrides:
        return (provider if provider == "mock" else None), None, None, None
    try:
        base_url = validate_base_url(base_url)
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=f"Rejected base_url: {ex}")
    return provider, (model or None), base_url, (api_key or None)


def _throttle(request: Request) -> None:
    allowed, retry_after = rate_limiter.check(client_key(request))
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded ({security.rate_limit_per_minute}/min). Retry in {retry_after}s.",
            headers={"Retry-After": str(retry_after)},
        )


def _convert_guarded(**kwargs):
    """Runs the pipeline inside an extraction slot so a burst of uploads cannot exhaust the server."""
    with extraction_slot:
        return process_pipeline(**kwargs)


def _mask(value: str) -> str:
    if not value:
        return ""
    return value[:4] + "…" + value[-2:] if len(value) > 8 else "•••"


@app.get("/api/health")
def health_check():
    """
    Liveness + the model configuration the UI needs to label its "model pill".
    The API key itself is never returned. On a shared deployment (APP_AUTH_MODE != none)
    the endpoint is public, so the base URL and key hint are withheld unless
    EXPOSE_SERVER_CONFIG=true.
    """
    key = config.llm.api_key or ""
    placeholder_keys = ("", "ollama", "dummy", "your-api-key", "changeme")
    key_set = key.strip().lower() not in placeholder_keys
    payload = {
        "status": "healthy",
        "service": "Process2BPMN",
        "version": VERSION,
        "auth_mode": security.auth_mode,
        "client_llm_overrides": security.allow_client_llm_overrides,
        "active_provider": config.llm.provider,
        "active_model": config.llm.model,
        "base_url": config.llm.base_url if security.expose_server_config else "",
        "api_key_set": key_set,
        "api_key_hint": _mask(key) if (key_set and security.expose_server_config) else "",
        "context_tokens": config.llm.context_tokens,
        "single_pool": config.single_pool,
    }
    return payload


@app.post("/api/llm/ping")
def llm_ping(req: LLMPingRequest, request: Request):
    """
    Cheap connectivity test for the active (or overridden) model: one tiny completion.
    Never raises for LLM problems; returns ok=false with the typed error so the UI can show it.
    """
    provider_name = (req.provider or config.llm.provider or "").lower()
    if provider_name == "mock":
        return {"ok": True, "provider": "mock", "model": "rule-engine", "latency_ms": 0,
                "note": "Mock mode never calls a model; text inputs use the rule engine."}
    started = time.time()
    try:
        p_name, p_model, p_url, p_key = _llm_overrides(request, req.provider, req.model, req.base_url, req.api_key)
        prov = get_llm_provider(
            provider_name=p_name,
            base_url=p_url,
            api_key=p_key,
            model=p_model,
        )
        _, raw_text, usage = prov.complete(
            [{"role": "user", "content": "Reply with the single word OK."}],
            temperature=0.0,
            max_tokens=8,
        )
        return {
            "ok": True,
            "provider": getattr(prov, "provider_name", provider_name),
            "model": getattr(prov, "model", req.model or config.llm.model),
            "latency_ms": int((time.time() - started) * 1000),
            "reply": (raw_text or "")[:40],
            "tokens": usage.get("total_tokens", 0) if isinstance(usage, dict) else 0,
        }
    except HTTPException:
        raise
    except LLMError as ex:
        return {
            "ok": False,
            "provider": getattr(ex, "provider", None) or provider_name,
            "model": getattr(ex, "model", None) or req.model or config.llm.model,
            "latency_ms": int((time.time() - started) * 1000),
            "kind": ex.__class__.__name__,
            "error": str(ex),
        }
    except Exception as ex:  # configuration problems, unexpected adapter failures
        return {
            "ok": False,
            "provider": provider_name,
            "model": req.model or config.llm.model,
            "latency_ms": int((time.time() - started) * 1000),
            "kind": ex.__class__.__name__,
            "error": str(ex),
        }


@app.post("/api/render")
def render_from_ir(req: RenderRequest, request: Request):
    """
    Re-runs validation, template binding, lint, layout and serialization on an existing IR.
    Lets the UI switch target tool, template or lane mapping without calling the model again.
    """
    ir = ProcessIR.from_dict(req.ir)
    return render_ir(
        ir=ir,
        filename=req.filename,
        profile_name=req.profile,
        mock=True,  # never call a model here; lane mapping falls back to name matching
        template_id=req.template_id,
        lane_map=req.lane_map,
        strict=bool(req.strict),
        user_id=current_user(request),
    )


@app.get("/api/profiles")
def get_profiles():
    profiles_data = []
    available = set(linter.list_available_profiles())
    ordered = [p for p in SUPPORTED_PROFILES if p in available]
    for p_id in ordered:
        prof = linter.load_profile(p_id)
        profiles_data.append({
            "id": p_id,
            "name": prof.get("name", p_id),
            "displayName": prof.get("displayName", p_id),
            "shortName": prof.get("shortName", prof.get("displayName", p_id)),
            "description": prof.get("description", ""),
            "assumptions": prof.get("assumptions", []),
            "targetVendor": prof.get("targetVendor", "")
        })
    return {"profiles": profiles_data}


# =========================================================================
# TEMPLATE MANAGEMENT ENDPOINTS
# =========================================================================

@app.get("/api/templates")
def list_templates(request: Request):
    """Lists built-in templates plus the caller's own uploads."""
    templates = template_storage.list_templates(user_id=current_user(request))
    return {"templates": [t.model_dump() for t in templates]}


async def _register_template(request: Request, file: UploadFile, name: Optional[str], description: Optional[str]):
    raw_bytes = await file.read()
    if len(raw_bytes) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="Template exceeds the upload size limit.")
    raw_xml = raw_bytes.decode("utf-8", errors="ignore")
    try:
        meta, report = template_storage.save_template(
            xml_content=raw_xml,
            filename=file.filename or "template.bpmn",
            name=name,
            description=description or "",
            owner_id=current_user(request) if current_user(request) != LOCAL_USER else "",
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=f"Template indexing error: {ex}")
    except Exception as ex:
        logger.exception("Template registration failed")
        raise HTTPException(status_code=400, detail=f"Template indexing error: {ex}")
    return {"success": True, "template": meta.model_dump(), "report": report.model_dump()}


@app.post("/api/templates")
async def register_template(
    request: Request,
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
):
    """Uploads and indexes a reference BPMN XML template (the route the UI's Template Manager uses)."""
    return await _register_template(request, file, name, description)


@app.get("/api/templates/download-blank")
def download_blank_template_query(type: str = "xlsx", sample: bool = True):
    """Downloads a pre-formatted Excel or Word template for structured capture with query params."""
    fmt = type.lower()
    if fmt == "xlsx":
        file_bytes = generate_blank_xlsx(include_sample=sample)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = "Process_Capture_Template_Example.xlsx" if sample else "Process_Capture_Template.xlsx"
    elif fmt == "docx":
        file_bytes = generate_blank_docx(include_sample=sample)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        filename = "Process_Capture_Template_Example.docx" if sample else "Process_Capture_Template.docx"
    else:
        raise HTTPException(status_code=400, detail="Invalid format type. Supported: 'xlsx', 'docx'.")

    return Response(
        content=file_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@app.get("/api/templates/{template_id}")
def get_template(template_id: str, request: Request):
    """Fetches details, raw XML, and parsed specification for a template."""
    record = template_storage.get_template(template_id, user_id=current_user(request))
    if not record:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found.")
    meta, raw_xml, spec = record
    return {
        "metadata": meta.model_dump(),
        "spec": spec.model_dump(),
        "xml": raw_xml
    }


@app.get("/api/templates/{template_id}/download")
def download_template(template_id: str, request: Request):
    """Downloads the reference .bpmn file of a template (link used by the Template Manager)."""
    record = template_storage.get_template(template_id, user_id=current_user(request))
    if not record:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found.")
    meta, raw_xml, _ = record
    fname = Path(meta.filename).name or f"{template_id}.bpmn"
    return Response(
        content=raw_xml,
        media_type="application/xml; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'}
    )


@app.post("/api/templates/upload")
async def upload_template(
    request: Request,
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
):
    """Alias of POST /api/templates kept for existing API clients."""
    return await _register_template(request, file, name, description)


@app.delete("/api/templates/{template_id}")
def delete_template(template_id: str, request: Request):
    """Deletes one of the caller's templates (built-ins cannot be deleted on shared deployments)."""
    success = template_storage.delete_template(template_id, user_id=current_user(request))
    if not success:
        raise HTTPException(status_code=404, detail="Template not found.")
    return {"success": True}


@app.post("/api/templates/{template_id}/default")
def set_default_template(template_id: str, request: Request):
    """Sets a template as the caller's default for matching export profiles."""
    success = template_storage.set_default(template_id, user_id=current_user(request))
    if not success:
        raise HTTPException(status_code=404, detail="Template not found.")
    return {"success": True}


@app.post("/api/templates/map-lanes")
def map_actors_to_lanes(req: MapLanesRequest, request: Request):
    """Maps extracted process actors/roles to reference template lanes."""
    record = template_storage.get_template(req.template_id, user_id=current_user(request))
    if not record:
        raise HTTPException(status_code=404, detail=f"Template '{req.template_id}' not found.")
    _, _, spec = record

    mapper = LaneMapper(spec)
    mapping_result = mapper.map_actors(req.actors)
    return mapping_result.model_dump()


@app.get("/api/templates/download-blank/{format_type}")
def download_blank_template(format_type: str, sample: bool = True):
    """Downloads a pre-formatted Excel or Word template for structured capture (path param)."""
    return download_blank_template_query(type=format_type, sample=sample)


MAX_UPLOAD_SIZE_BYTES = int(os.environ.get("MAX_UPLOAD_SIZE_BYTES", 20 * 1024 * 1024))


@app.post("/api/convert")
async def convert_document(
    request: Request,
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    filename: Optional[str] = Form("process_input.txt"),
    profile: Optional[str] = Form(DEFAULT_PROFILE),
    mock: Optional[bool] = Form(False),
    provider: Optional[str] = Form(None),
    model: Optional[str] = Form(None),
    base_url: Optional[str] = Form(None),
    api_key: Optional[str] = Form(None),
    template_id: Optional[str] = Form(None),
    lane_map: Optional[str] = Form(None),
    strict: Optional[bool] = Form(False),
):
    _throttle(request)
    if file is not None:
        raw_content = await file.read()
        fname = Path(file.filename or filename or "uploaded_process.txt").name
    elif text:
        raw_content = text.encode("utf-8")
        fname = Path(filename or "pasted_process.txt").name
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
            raise HTTPException(status_code=400, detail="lane_map must be a JSON object of actor -> lane id.")

    p_name, p_model, p_url, p_key = _llm_overrides(request, provider, model, base_url, api_key)

    # The pipeline (document parsing + a model round-trip that can take tens of seconds) is
    # synchronous; running it on the event loop would freeze every other user's request.
    return await run_in_threadpool(
        _convert_guarded,
        raw_content=raw_content,
        filename=fname,
        profile_name=profile or DEFAULT_PROFILE,
        mock=mock or False,
        provider_name=p_name,
        model=p_model,
        base_url=p_url,
        api_key=p_key,
        template_id=template_id,
        lane_map=lane_map_dict,
        strict=bool(strict),
        user_id=current_user(request),
    )


@app.post("/api/convert-json")
def convert_json_payload(req: ConvertTextRequest, request: Request):
    _throttle(request)
    raw_content = req.text.encode("utf-8")
    p_name, p_model, p_url, p_key = _llm_overrides(request, req.provider, req.model, req.base_url, req.api_key)
    return _convert_guarded(
        raw_content=raw_content,
        filename=Path(req.filename or "process_input.txt").name,
        profile_name=req.profile or DEFAULT_PROFILE,
        mock=req.mock or False,
        provider_name=p_name,
        model=p_model,
        base_url=p_url,
        api_key=p_key,
        template_id=req.template_id,
        lane_map=req.lane_map,
        strict=bool(req.strict),
        user_id=current_user(request),
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


def _serialize_profiles(ir_data: Dict[str, Any], profiles: List[str], template_id: Optional[str],
                        lane_map: Optional[Dict[str, str]], user_id: str, filename: str) -> Dict[str, str]:
    """
    Validates/repairs the IR once, then renders one XSD-validated BPMN document per profile
    through the normal pipeline. Raises ExportBlockedError when the process has blocking
    errors and BpmnSchemaError if any profile output fails schema validation, so a bundle
    can never contain an unusable file.
    """
    out: Dict[str, str] = {}
    for p_name in profiles:
        if p_name not in SUPPORTED_PROFILES:
            raise HTTPException(status_code=400, detail=f"Unknown profile '{p_name}'. Supported: {', '.join(SUPPORTED_PROFILES)}")
        ir_obj = ProcessIR.from_dict(ir_data)  # fresh copy: render_ir mutates during repair
        result = render_ir(
            ir=ir_obj,
            filename=filename,
            profile_name=p_name,
            mock=True,
            template_id=template_id,
            lane_map=lane_map,
            strict=True,
            user_id=user_id,
        )
        out[p_name] = result["bpmn_xml"]
    return out


@app.post("/api/export/bpmn")
def export_bpmn(req: BpmnExportRequest, request: Request):
    """Returns the validated BPMN 2.0 file for one profile; refuses (422) when export is blocked."""
    xml_by_profile = _serialize_profiles(
        req.ir, [req.profile], req.template_id, req.lane_map, current_user(request), f"{req.process_name}.bpmn"
    )
    safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', req.process_name or "process").lower() or "process"
    return Response(
        content=xml_by_profile[req.profile],
        media_type="application/xml; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}_{req.profile}.bpmn"'}
    )


@app.post("/api/export/bulk")
def export_bulk_zip(req: BulkExportRequest, request: Request):
    """
    Builds the multi-format bundle server-side: one *distinct* BPMN file per vendor profile
    (each validated against the BPMN 2.0 XSD), plus the SVG/PNG the browser rendered.
    The export gate applies: a process with blocking validation errors returns 422.
    """
    process_name = req.process_name or "process"
    safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', process_name).lower() or "process"
    profiles = req.profiles or SUPPORTED_PROFILES

    bpmn_by_profile = _serialize_profiles(
        req.ir, profiles, req.template_id, req.lane_map, current_user(request), f"{safe_name}.bpmn"
    )

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for prof, xml_str in bpmn_by_profile.items():
            zf.writestr(f"{safe_name}_{prof}.bpmn", xml_str)

        if req.svg:
            zf.writestr(f"{safe_name}.svg", req.svg)

        png_base64 = req.png_base64
        if png_base64:
            if "," in png_base64:
                png_base64 = png_base64.split(",", 1)[1]
            try:
                zf.writestr(f"{safe_name}.png", base64.b64decode(png_base64, validate=True))
            except Exception:
                raise HTTPException(status_code=400, detail="png_base64 is not valid base64.")

        manifest = {
            "processName": process_name,
            "exportedAt": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            "generator": f"Process2BPMN {VERSION}",
            "profiles": list(bpmn_by_profile.keys()),
            "files": [f"{safe_name}_{p}.bpmn" for p in bpmn_by_profile]
                     + ([f"{safe_name}.svg"] if req.svg else [])
                     + ([f"{safe_name}.png"] if req.png_base64 else []),
            "xsdValidated": True,
        }
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))

        readme = f"""Process2BPMN Complete Process Package
===================================
Process Name: {process_name}
Generated: {manifest['exportedAt']}

Files Included:
"""
        for prof in bpmn_by_profile.keys():
            readme += f"- {safe_name}_{prof}.bpmn : BPMN 2.0 XML tailored for the {prof.capitalize()} profile (XSD validated)\n"
        if req.svg:
            readme += f"- {safe_name}.svg : Scalable Vector Graphics diagram\n"
        if req.png_base64:
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

    _dist_root = dist_dir.resolve()

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path.startswith("api"):
            raise HTTPException(status_code=404, detail="API endpoint not found")
        if full_path:
            target_file = (_dist_root / full_path).resolve()
            # Never serve anything outside dist/ (e.g. /../.env)
            if target_file.is_file() and _dist_root in target_file.parents:
                return FileResponse(target_file)
        index_file = dist_dir / "index.html"
        if index_file.is_file():
            return FileResponse(index_file)
        raise HTTPException(status_code=404, detail="Not Found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.server:app", host="0.0.0.0", port=8000, reload=False)
