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

class TestTemplatesAndFixtures:
    def test_all_fixture_documents_convert_successfully(self):
        fixtures_dir = _PROJECT_ROOT / "backend" / "tests" / "fixtures"
        samples = [f for f in sorted(fixtures_dir.iterdir()) if f.is_file() and f.suffix in ('.xlsx', '.docx', '.vtt', '.pdf', '.md', '.txt', '.csv')]
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
