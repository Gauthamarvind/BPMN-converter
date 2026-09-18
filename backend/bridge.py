"""
Bridge script for Process2BPMN.
Allows standard I/O communication between web server (Node/Vite) and Python backend pipeline.
"""

from __future__ import annotations
import sys
import json
from pathlib import Path

# Reserve real stdout for clean JSON IPC response; redirect sys.stdout to sys.stderr
_real_stdout = sys.stdout
sys.stdout = sys.stderr

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.config import config
from backend.server import process_pipeline, linter, template_storage
from backend.ir.models import ProcessIR
from backend.templates.mapper import LaneMapper
from backend.templates.blank_generator import generate_blank_xlsx, generate_blank_docx
import base64
import time


def output_json(data: dict):
    _real_stdout.write(json.dumps(data) + "\n")
    _real_stdout.flush()


def read_stdin_json() -> dict:
    import select
    try:
        if not sys.stdin.isatty():
            # Check if readable within 100ms
            r, _, _ = select.select([sys.stdin], [], [], 0.1)
            if r:
                raw = sys.stdin.read()
                if raw.strip():
                    return json.loads(raw)
    except Exception:
        pass
    return {}


def handle_health():
    res = {
        "status": "healthy",
        "service": "Process2BPMN",
        "version": "1.0.0",
        "active_provider": config.llm.provider,
        "active_model": config.llm.model,
        "base_url": config.llm.base_url
    }
    output_json(res)


def handle_profiles():
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
    output_json({"profiles": profiles_data})


def handle_samples():
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
    output_json({"samples": samples})


def handle_convert():
    data = read_stdin_json()
    
    text = data.get("text", "")
    base64_content = data.get("base64_content")
    if base64_content:
        raw_bytes = base64.b64decode(base64_content)
    else:
        raw_bytes = text.encode("utf-8")

    filename = data.get("filename", "process_input.txt")
    profile = data.get("profile", "generic")
    mock = data.get("mock", False)
    provider = data.get("provider")
    model = data.get("model")
    base_url = data.get("base_url")
    api_key = data.get("api_key")
    template_id = data.get("template_id")
    lane_map = data.get("lane_map")

    res = process_pipeline(
        raw_content=raw_bytes,
        filename=filename,
        profile_name=profile,
        mock=mock,
        provider_name=provider,
        model=model,
        base_url=base_url,
        api_key=api_key,
        template_id=template_id,
        lane_map=lane_map
    )
    output_json(res)


def handle_templates_list():
    templates = template_storage.list_templates()
    output_json({"templates": [t.model_dump() for t in templates]})


def handle_templates_get():
    data = read_stdin_json()
    template_id = data.get("template_id") or (sys.argv[2] if len(sys.argv) > 2 else "")
    record = template_storage.get_template(template_id)
    if not record:
        output_json({"error": f"Template '{template_id}' not found", "success": False})
        return
    meta, raw_xml, spec = record
    output_json({
        "success": True,
        "metadata": meta.model_dump(),
        "spec": spec.model_dump(),
        "xml": raw_xml
    })


def handle_templates_save():
    data = read_stdin_json()
    xml_content = data.get("xml", "")
    name = data.get("name", "Custom Template")
    filename = data.get("filename", "template.bpmn")
    description = data.get("description", "")
    tid = f"tpl_{int(time.time())}_{Path(filename).stem}"

    meta, report = template_storage.save_bpmn_template(
        template_id=tid,
        name=name,
        xml_content=xml_content,
        filename=filename,
        description=description
    )
    output_json({
        "success": True,
        "template": meta.model_dump(),
        "report": report.model_dump()
    })


def handle_templates_delete():
    data = read_stdin_json()
    template_id = data.get("template_id") or (sys.argv[2] if len(sys.argv) > 2 else "")
    res = template_storage.delete_template(template_id)
    output_json({"success": res})


def handle_templates_default():
    data = read_stdin_json()
    template_id = data.get("template_id") or (sys.argv[2] if len(sys.argv) > 2 else "")
    res = template_storage.set_default(template_id)
    output_json({"success": res})


def handle_templates_map_lanes():
    data = read_stdin_json()
    template_id = data.get("template_id", "")
    actors = data.get("actors", [])
    record = template_storage.get_template(template_id)
    if not record:
        output_json({"error": f"Template '{template_id}' not found", "success": False})
        return
    _, _, spec = record
    mapper = LaneMapper(spec)
    mappings = mapper.map_actors(actors, use_llm=False)
    output_json({
        "template_id": template_id,
        "mappings": [m.model_dump() for m in mappings],
        "available_lanes": [
            {"id": l.id, "name": l.name, "pool_name": spec.get_pool_for_lane(l.id).name if spec.get_pool_for_lane(l.id) else ""}
            for l in spec.get_all_lanes()
        ]
    })


def handle_templates_blank():
    data = read_stdin_json()
    fmt = data.get("type", "xlsx").lower()
    include_sample = data.get("sample", True)
    if fmt == "xlsx":
        b = generate_blank_xlsx(include_sample=include_sample)
        fname = "Process_Capture_Template.xlsx"
        mtype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        b = generate_blank_docx(include_sample=include_sample)
        fname = "Process_Capture_Template.docx"
        mtype = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    output_json({
        "filename": fname,
        "media_type": mtype,
        "base64": base64.b64encode(b).decode("ascii")
    })


def handle_lint():
    data = read_stdin_json()
    ir_dict = data.get("ir")
    profile = data.get("profile", "generic")
    
    if not ir_dict:
        output_json({"is_valid": True, "warnings": [], "assumptions": []})
        return

    ir = ProcessIR.from_dict(ir_dict)
    res = linter.lint(ir, profile_name=profile)
    out = {
        "profile_name": res.profile_name,
        "display_name": res.display_name,
        "is_valid": res.is_valid,
        "assumptions": res.assumptions,
        "warnings": [
            {"code": w.code, "message": w.message, "severity": w.severity, "element_id": w.element_id}
            for w in res.warnings
        ]
    }
    output_json(out)


def main():
    if len(sys.argv) < 2:
        output_json({"error": "No command specified"})
        sys.exit(1)

    cmd = sys.argv[1]
    try:
        if cmd == "health":
            handle_health()
        elif cmd == "profiles":
            handle_profiles()
        elif cmd == "samples":
            handle_samples()
        elif cmd == "convert":
            handle_convert()
        elif cmd == "lint":
            handle_lint()
        elif cmd == "templates_list":
            handle_templates_list()
        elif cmd == "templates_get":
            handle_templates_get()
        elif cmd == "templates_save":
            handle_templates_save()
        elif cmd == "templates_delete":
            handle_templates_delete()
        elif cmd == "templates_default":
            handle_templates_default()
        elif cmd == "templates_map_lanes":
            handle_templates_map_lanes()
        elif cmd == "templates_blank":
            handle_templates_blank()
        else:
            output_json({"error": f"Unknown command: {cmd}"})
            sys.exit(1)
    except Exception as ex:
        import traceback
        err = {"error": str(ex), "traceback": traceback.format_exc()}
        sys.stderr.write(json.dumps(err) + "\n")
        output_json({"success": False, "error": str(ex)})
        sys.exit(1)


if __name__ == "__main__":
    main()
