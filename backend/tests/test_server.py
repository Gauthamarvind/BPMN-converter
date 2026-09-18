"""
FastAPI Server Integration Tests.
Verifies /api/health, /api/profiles, /api/samples, /api/convert, and /api/lint.
"""

import sys
import unittest
from pathlib import Path

# Add project root to sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from starlette.testclient import TestClient
from backend.server import app


class TestServerEndpoints(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_health(self):
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["service"], "Process2BPMN")

    def test_profiles(self):
        res = self.client.get("/api/profiles")
        self.assertEqual(res.status_code, 200)
        profiles = res.json()["profiles"]
        ids = [p["id"] for p in profiles]
        self.assertIn("generic", ids)
        self.assertIn("signavio", ids)
        self.assertIn("camunda", ids)

    def test_samples(self):
        res = self.client.get("/api/samples")
        self.assertEqual(res.status_code, 200)
        samples = res.json()["samples"]
        self.assertGreaterEqual(len(samples), 3)

    def test_convert_text(self):
        payload = {
            "text": "1. Customer submits purchase order.\n2. Manager reviews order.\n3. Billing system charges credit card.",
            "filename": "order_flow.txt",
            "profile": "signavio",
            "mock": True
        }
        res = self.client.post("/api/convert-json", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertIn("bpmn:definitions", data["bpmn_xml"])
        self.assertIn("BPMNDiagram", data["bpmn_xml"])
        self.assertGreaterEqual(data["metadata"]["element_count"], 3)

    def test_lint_endpoint(self):
        payload = {
            "profile": "signavio",
            "ir": {
                "id": "Process_1",
                "name": "Signavio Test",
                "elements": [
                    {"id": "Start_1", "type": "startEvent", "name": "Start", "laneId": "Lane_1"},
                    {"id": "End_1", "type": "endEvent", "name": "End", "laneId": "Lane_1"}
                ],
                "flows": [
                    {"id": "Flow_1", "sourceId": "Start_1", "targetId": "End_1"}
                ]
            }
        }
        res = self.client.post("/api/lint", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("assumptions", data)

    def test_convert_bulk_export_structure(self):
        payload = {
            "text": "1. Requester submits request.\n2. Approver evaluates request.\n3. Request approved.",
            "filename": "approval_flow.txt",
            "profile": "camunda",
            "mock": True
        }
        res = self.client.post("/api/convert-json", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertIn("bulk_export", data)
        bulk = data["bulk_export"]
        self.assertIn("process_name", bulk)
        self.assertIn("supported_profiles", bulk)
        self.assertIn("available_formats", bulk)
        self.assertEqual(set(bulk["available_formats"]), {".bpmn", ".svg", ".png"})
        self.assertIn("camunda", bulk["supported_profiles"])

    def test_export_bulk_zip_endpoint(self):
        import zipfile
        import io
        payload = {
            "process_name": "Invoice Approval",
            "ir": {
                "id": "Process_1",
                "name": "Invoice Approval",
                "pools": [{"id": "Pool_1", "name": "Org", "lanes": [{"id": "Lane_1", "name": "Finance"}]}],
                "elements": [
                    {"id": "Start_1", "type": "startEvent", "name": "Start", "laneId": "Lane_1"},
                    {"id": "Task_1", "type": "task", "name": "Approve", "laneId": "Lane_1"},
                    {"id": "End_1", "type": "endEvent", "name": "End", "laneId": "Lane_1"}
                ],
                "flows": [
                    {"id": "Flow_1", "sourceId": "Start_1", "targetId": "Task_1"},
                    {"id": "Flow_2", "sourceId": "Task_1", "targetId": "End_1"}
                ]
            },
            "svg": "<svg xmlns='http://www.w3.org/2000/svg'><rect width='100' height='100'/></svg>",
            "png_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        }
        res = self.client.post("/api/export/bulk", json=payload)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("content-type"), "application/zip")

        # Verify ZIP contents
        zf = zipfile.ZipFile(io.BytesIO(res.content))
        namelist = zf.namelist()
        self.assertIn("invoice_approval_camunda.bpmn", namelist)
        self.assertIn("invoice_approval_signavio.bpmn", namelist)
        self.assertIn("invoice_approval_generic.bpmn", namelist)
        self.assertIn("invoice_approval.svg", namelist)
        self.assertIn("invoice_approval.png", namelist)
        self.assertIn("README.txt", namelist)
        self.assertIn("invoice_approval_generic.bpmn", namelist)
        self.assertIn("invoice_approval.svg", namelist)
        self.assertIn("invoice_approval.png", namelist)
        self.assertIn("README.txt", namelist)

    def test_convert_multipart_upload(self):
        text_content = b"1. Step one.\n2. Step two.\n3. Step three."
        files = {"file": ("simple.txt", text_content, "text/plain")}
        data = {"profile": "generic", "mock": "true"}
        res = self.client.post("/api/convert", files=files, data=data)
        self.assertEqual(res.status_code, 200)
        json_data = res.json()
        self.assertTrue(json_data["success"])

    def test_convert_magic_bytes_mismatch_xlsx(self):
        # Fake xlsx with invalid magic bytes (not PK)
        fake_content = b"not a zip file content"
        files = {"file": ("test.xlsx", fake_content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        res = self.client.post("/api/convert", files=files)
        self.assertEqual(res.status_code, 415)
        self.assertIn("PK zip signature", res.json()["detail"])

    def test_convert_magic_bytes_mismatch_pdf(self):
        # Fake pdf with invalid magic bytes (not %PDF)
        fake_content = b"not a pdf file"
        files = {"file": ("test.pdf", fake_content, "application/pdf")}
        res = self.client.post("/api/convert", files=files)
        self.assertEqual(res.status_code, 415)
        self.assertIn("%PDF", res.json()["detail"])

    def test_convert_size_limit_exceeded(self):
        import backend.server as srv
        original_limit = srv.MAX_UPLOAD_SIZE_BYTES
        try:
            srv.MAX_UPLOAD_SIZE_BYTES = 50  # 50 bytes limit for test
            files = {"file": ("huge.txt", b"A" * 100, "text/plain")}
            res = self.client.post("/api/convert", files=files)
            self.assertEqual(res.status_code, 413)
            self.assertIn("File exceeds maximum upload size limit", res.json()["detail"])
        finally:
            srv.MAX_UPLOAD_SIZE_BYTES = original_limit

    def test_spa_fallback(self):
        dist_index = Path(__file__).resolve().parents[2] / "dist" / "index.html"
        if not dist_index.is_file():
            self.skipTest("frontend not built (run `npm run build` first); SPA fallback needs dist/index.html")
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("<!doctype html>", res.text.lower())


if __name__ == "__main__":
    unittest.main()
