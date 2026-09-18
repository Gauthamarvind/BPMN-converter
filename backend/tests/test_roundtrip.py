"""
Real round-trip integration tests for Process2BPMN.
Uploads actual .xlsx, .docx, .pdf, and other real sample files from samples/
through /api/convert in mock mode and asserts:
1. HTTP 200 and success response.
2. Non-empty BPMN 2.0 XML diagram.
3. Official OMG BPMN 2.0 XSD schema validity.
"""

from __future__ import annotations
import sys
from pathlib import Path
import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from starlette.testclient import TestClient
from backend.server import app
from backend.pipeline.xsd_validator import validate_bpmn

client = TestClient(app)
SAMPLES_DIR = _PROJECT_ROOT / "samples"


class TestRoundtrip:
    def test_roundtrip_xlsx(self):
        """Uploads the real sample_leave_request.xlsx and verifies valid BPMN 2.0 output."""
        file_path = SAMPLES_DIR / "sample_leave_request.xlsx"
        assert file_path.is_file(), f"Sample file not found: {file_path}"

        with open(file_path, "rb") as f:
            file_bytes = f.read()

        assert len(file_bytes) > 500, "Real sample xlsx is unexpectedly small"

        res = client.post(
            "/api/convert",
            files={"file": ("sample_leave_request.xlsx", file_bytes)},
            data={"mock": "true", "profile": "generic"}
        )

        assert res.status_code == 200, f"Conversion failed: {res.text}"
        data = res.json()
        assert data.get("success") is True
        bpmn_xml = data.get("bpmn_xml", "")
        assert len(bpmn_xml) > 200
        assert "<bpmn:definitions" in bpmn_xml or "<definitions" in bpmn_xml
        assert "<bpmndi:BPMNDiagram" in bpmn_xml

        # Assert XSD validity
        xsd_errors = validate_bpmn(bpmn_xml)
        assert len(xsd_errors) == 0, f"XSD validation errors on xlsx conversion: {xsd_errors}"

    def test_roundtrip_docx(self):
        """Uploads the real sample_sop.docx and verifies valid BPMN 2.0 output."""
        file_path = SAMPLES_DIR / "sample_sop.docx"
        assert file_path.is_file(), f"Sample file not found: {file_path}"

        with open(file_path, "rb") as f:
            file_bytes = f.read()

        assert len(file_bytes) > 500, "Real sample docx is unexpectedly small"

        res = client.post(
            "/api/convert",
            files={"file": ("sample_sop.docx", file_bytes)},
            data={"mock": "true", "profile": "generic"}
        )

        assert res.status_code == 200, f"Conversion failed: {res.text}"
        data = res.json()
        assert data.get("success") is True
        bpmn_xml = data.get("bpmn_xml", "")
        assert len(bpmn_xml) > 200
        assert "<bpmn:definitions" in bpmn_xml or "<definitions" in bpmn_xml
        assert "<bpmndi:BPMNDiagram" in bpmn_xml

        # Assert XSD validity
        xsd_errors = validate_bpmn(bpmn_xml)
        assert len(xsd_errors) == 0, f"XSD validation errors on docx conversion: {xsd_errors}"

    def test_roundtrip_pdf(self):
        """Uploads the real sample_sop.pdf and verifies valid BPMN 2.0 output."""
        file_path = SAMPLES_DIR / "sample_sop.pdf"
        assert file_path.is_file(), f"Sample file not found: {file_path}"

        with open(file_path, "rb") as f:
            file_bytes = f.read()

        assert len(file_bytes) > 500, "Real sample pdf is unexpectedly small"

        res = client.post(
            "/api/convert",
            files={"file": ("sample_sop.pdf", file_bytes)},
            data={"mock": "true", "profile": "generic"}
        )

        assert res.status_code == 200, f"Conversion failed: {res.text}"
        data = res.json()
        assert data.get("success") is True
        bpmn_xml = data.get("bpmn_xml", "")
        assert len(bpmn_xml) > 200
        assert "<bpmn:definitions" in bpmn_xml or "<definitions" in bpmn_xml
        assert "<bpmndi:BPMNDiagram" in bpmn_xml

        # Assert XSD validity
        xsd_errors = validate_bpmn(bpmn_xml)
        assert len(xsd_errors) == 0, f"XSD validation errors on pdf conversion: {xsd_errors}"

    def test_roundtrip_all_vendor_profiles_for_samples(self):
        """Verifies that all samples convert cleanly across all export profiles."""
        profiles = ["generic", "camunda", "signavio", "celonis", "aris"]
        sample_files = ["sample_leave_request.xlsx", "sample_sop.docx", "sample_sop.pdf"]

        for fname in sample_files:
            file_path = SAMPLES_DIR / fname
            with open(file_path, "rb") as f:
                content = f.read()

            for prof in profiles:
                res = client.post(
                    "/api/convert",
                    files={"file": (fname, content)},
                    data={"mock": "true", "profile": prof}
                )
                assert res.status_code == 200, f"Profile {prof} failed for {fname}: {res.text}"
                data = res.json()
                assert data.get("success") is True
                assert len(data.get("bpmn_xml", "")) > 100
