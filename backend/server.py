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
from pathlib import Path
from typing import Optional, List, Dict, Any

# Ensure project root is in sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Body, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.config import config
from backend.ir.models import ProcessIR, TemplateBindings
from backend.ingestion.parser import ingest_file
from backend.llm.factory import get_llm_provider
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
from backend.templates.bpmn_parser import BpmnTemplateParser
from backend.templates.blank_generator import generate_blank_xlsx, generate_blank_docx

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


@app.post("/api/templates")
async def upload_template(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    description: Optional[str] = Form("")
):
    """Uploads and registers a new BPMN reference template."""
    import time
    try:
        content_bytes = await file.read()
        raw_xml = content_bytes.decode("utf-8")
        tid = f"tpl_{int(time.time())}_{Path(file.filename or 'tpl').stem}"
        disp_name = name or Path(file.filename or "Template").stem.replace("_", " ").title()

        meta, report = template_storage.save_bpmn_template(
            template_id=tid,
            name=disp_name,
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
        raise HTTPException(status_code=400, detail=f"Failed to parse template: {str(ex)}")


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
    """Maps extracted process actors to reference template swimlanes."""
    record = template_storage.get_template(req.template_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Template '{req.template_id}' not found.")
    _, _, spec = record
    mapper = LaneMapper(spec)
    mappings = mapper.map_actors(req.actors, use_llm=False)
    return {
        "template_id": req.template_id,
        "mappings": [m.model_dump() for m in mappings],
        "available_lanes": [
            {"id": l.id, "name": l.name, "pool_name": spec.get_pool_for_lane(l.id).name if spec.get_pool_for_lane(l.id) else ""}
            for l in spec.get_all_lanes()
        ]
    }


@app.get("/api/templates/download-blank")
def download_blank_template(type: str = "xlsx", sample: bool = True):
    """Generates and serves a blank downloadable .xlsx or .docx capture form."""
    if type.lower() == "xlsx":
        file_bytes = generate_blank_xlsx(include_sample=sample)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = "Process_Capture_Template.xlsx"
    elif type.lower() == "docx":
        file_bytes = generate_blank_docx(include_sample=sample)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        filename = "Process_Capture_Template.docx"
    else:
        raise HTTPException(status_code=400, detail="Invalid format type. Supported: 'xlsx', 'docx'.")

    return Response(
        content=file_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


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
    """Core conversion pipeline."""
    title = Path(filename).stem.replace("_", " ").title()
    ext = Path(filename).suffix.lower()

    # 1. Pipeline Hook: Check if file is a structured document template
    ir: Optional[ProcessIR] = None
    extraction_meta = {"mode": "llm", "tokens_used": 0}

    if ext in (".xlsx", ".csv", ".docx", ".json"):
        try:
            doc_parser = DocTemplateParser()
            ir = doc_parser.parse_bytes(raw_content, filename)
            extraction_meta["mode"] = "doc_template_parser"
        except Exception as doc_ex:
            print(f"[Process2BPMN Server] Doc parser fallback: {doc_ex}", file=sys.stderr)
            ir = None

    # 2. Ingestion & Process Extraction (LLM or Rule-based Mock)
    doc = None
    if ir is None:
        doc = ingest_file(raw_content, filename)
        if not mock:
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
            except Exception as ex:
                print(f"[Process2BPMN Server] Extraction fallback triggered: {ex}", file=sys.stderr)
                ir = None

        if ir is None:
            ir = generate_mock_ir_from_text(doc.normalized_text, title=title)
            extraction_meta["mode"] = "deterministic_rule_engine"

    # 3. Deterministic Validation & Repair
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

    # 5. Profile Linter
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

    # 8. Multi-Profile Bulk Export Generation (Pre-render BPMN XML for all supported profiles)
    supported_profiles = ["generic", "camunda", "signavio", "celonis", "aris"]
    bpmn_by_profile: Dict[str, str] = {}
    for p_name in supported_profiles:
        if p_name == profile_name:
            bpmn_by_profile[p_name] = bpmn_xml
        else:
            try:
                p_cfg = linter.load_profile(p_name)
                if template_spec and template_raw_xml:
                    p_renderer = BpmnTemplateRenderer(
                        template_raw_xml=template_raw_xml,
                        spec=template_spec,
                        ir=repaired_ir,
                        layout=layout,
                        profile_config=p_cfg
                    )
                    bpmn_by_profile[p_name] = p_renderer.render()
                else:
                    p_serializer = BpmnXmlSerializer(repaired_ir, layout, p_cfg)
                    bpmn_by_profile[p_name] = p_serializer.serialize()
            except Exception as e:
                # Fallback to base BPMN XML if custom profile render encounters issue
                bpmn_by_profile[p_name] = bpmn_xml

    bulk_export = {
        "process_name": repaired_ir.name or Path(filename).stem,
        "supported_profiles": supported_profiles,
        "bpmn_by_profile": bpmn_by_profile,
        "available_formats": [".bpmn", ".svg", ".png"]
    }

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
    try:
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

        result = process_pipeline(
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
        return result
    except HTTPException:
        raise
    except Exception as ex:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(ex))


@app.post("/api/convert-json")
def convert_json_payload(req: ConvertTextRequest):
    try:
        raw_content = req.text.encode("utf-8")
        result = process_pipeline(
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
        return result
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex))


@app.post("/api/lint")
def lint_process(req: LintRequest):
    try:
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
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex))


@app.post("/api/export/bulk")
def export_bulk_zip(data: Dict[str, Any]):
    """Accepts process_name, bpmn_by_profile, svg, png and generates a downloadable ZIP bundle."""
    try:
        import io
        import zipfile
        from fastapi.responses import Response

        process_name = data.get("process_name", "process")
        safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', process_name).lower()
        bpmn_by_profile = data.get("bpmn_by_profile", {})
        svg_content = data.get("svg")
        png_base64 = data.get("png_base64")

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
                import base64
                if "," in png_base64:
                    png_base64 = png_base64.split(",", 1)[1]
                png_bytes = base64.b64decode(png_base64)
                zf.writestr(f"{safe_name}.png", png_bytes)

            # Write README manifest
            readme = f"""Text2BPMN Complete Process Package
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
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex))


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
