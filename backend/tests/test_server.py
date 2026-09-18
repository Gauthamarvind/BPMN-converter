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


if __name__ == "__main__":
    unittest.main()
