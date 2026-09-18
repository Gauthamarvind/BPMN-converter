import os
import sys
from pathlib import Path
import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from starlette.testclient import TestClient
from backend.server import app

client = TestClient(app)

class TestTemplatesAndSamples:
    def test_samples_manifest_endpoint(self):
        res = client.get("/api/samples")
        assert res.status_code == 200
        data = res.json()
        assert "samples" in data
        assert len(data["samples"]) >= 7

        filenames = [s["name"] for s in data["samples"]]
        assert "sample_leave_request.xlsx" in filenames
        assert "sample_sop.docx" in filenames
        assert "sample_transcript.vtt" in filenames
        assert "sample_sop.pdf" in filenames

        for s in data["samples"]:
            assert "name" in s
            assert "title" in s
            assert "download_url" in s
            assert "type" in s

    def test_sample_download_endpoint(self):
        res = client.get("/api/samples/download/sample_leave_request.xlsx")
        assert res.status_code == 200
        assert res.headers["content-type"] in (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/octet-stream",
        )
        assert len(res.content) > 1000

        # Non-existent file
        res_404 = client.get("/api/samples/download/non_existent.xyz")
        assert res_404.status_code == 404

    def test_all_samples_convert_successfully(self):
        samples_dir = Path("samples")
        samples = [f for f in sorted(samples_dir.iterdir()) if f.is_file() and f.suffix in ('.xlsx', '.docx', '.vtt', '.pdf', '.md', '.txt', '.csv')]
        assert len(samples) >= 7

        for s in samples:
            with open(s, "rb") as f:
                content = f.read()
            res = client.post(
                "/api/convert",
                files={"file": (s.name, content)},
                data={"mock": "true", "profile": "generic"}
            )
            assert res.status_code == 200, f"Failed converting sample {s.name}: {res.text}"
            data = res.json()
            assert data.get("success") is True, f"Conversion failed for {s.name}"
            assert len(data.get("bpmn_xml", "")) > 100
            assert "ir" in data
            assert len(data["ir"]["elements"]) > 0

    def test_template_download_endpoints(self):
        # Blank xlsx
        res_blank_xlsx = client.get("/api/templates/download-blank?type=xlsx&sample=false")
        assert res_blank_xlsx.status_code == 200
        assert len(res_blank_xlsx.content) > 1000

        # Example xlsx
        res_sample_xlsx = client.get("/api/templates/download-blank?type=xlsx&sample=true")
        assert res_sample_xlsx.status_code == 200
        assert len(res_sample_xlsx.content) > 1000

        # Blank docx
        res_blank_docx = client.get("/api/templates/download-blank?type=docx&sample=false")
        assert res_blank_docx.status_code == 200
        assert len(res_blank_docx.content) > 1000

        # Example docx
        res_sample_docx = client.get("/api/templates/download-blank?type=docx&sample=true")
        assert res_sample_docx.status_code == 200
        assert len(res_sample_docx.content) > 1000
