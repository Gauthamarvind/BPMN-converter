"""
Tests for the endpoints that keep the UI fluid:
- POST /api/render re-serializes an existing IR for another target tool without a model call
- POST /api/llm/ping reports connectivity as data (never as an HTTP error)
- GET  /api/health reports the loaded configuration without leaking the key
"""

from __future__ import annotations
import unittest
from pathlib import Path

from starlette.testclient import TestClient

from backend.server import app

ROOT = Path(__file__).resolve().parents[2]


class TestRenderAndPing(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def _convert_leave_request(self) -> dict:
        path = ROOT / "samples" / "sample_leave_request.xlsx"
        with open(path, "rb") as fh:
            res = self.client.post(
                "/api/convert",
                files={"file": (path.name, fh.read(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                data={"profile": "generic", "mock": "true"},
            )
        self.assertEqual(res.status_code, 200, res.text[:300])
        return res.json()

    def test_render_switches_profile_without_reextraction(self):
        first = self._convert_leave_request()
        res = self.client.post(
            "/api/render",
            json={"ir": first["ir"], "profile": "aris", "filename": "sample_leave_request.xlsx"},
        )
        self.assertEqual(res.status_code, 200, res.text[:300])
        data = res.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["lint_result"]["profile_name"], "aris")
        self.assertIn("<bpmn:definitions", data["bpmn_xml"])
        self.assertEqual(data["metadata"]["element_count"], first["metadata"]["element_count"])
        self.assertEqual(data["metadata"]["extraction"]["mode"], "render")

    def test_render_rejects_garbage(self):
        res = self.client.post("/api/render", json={"ir": {"id": "x"}, "profile": "generic"})
        # An empty IR is repaired into start -> end; it must not crash the server
        self.assertIn(res.status_code, (200, 400, 422))

    def test_ping_mock_is_ok_without_network(self):
        res = self.client.post("/api/llm/ping", json={"provider": "mock"})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["ok"])

    def test_ping_reports_connection_failure_as_data(self):
        res = self.client.post(
            "/api/llm/ping",
            json={"provider": "openai_compatible", "base_url": "http://127.0.0.1:9", "model": "x", "api_key": "k"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertFalse(data["ok"])
        self.assertEqual(data["kind"], "LLMConnectionError")
        self.assertEqual(data["provider"], "openai_compatible")

    def test_ping_unknown_provider_is_configuration_error(self):
        res = self.client.post("/api/llm/ping", json={"provider": "does-not-exist"})
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.json()["ok"])
        self.assertEqual(res.json()["kind"], "LLMConfigurationError")

    def test_health_never_returns_the_key(self):
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        for field in ("active_provider", "active_model", "base_url", "api_key_set", "single_pool"):
            self.assertIn(field, data)
        self.assertNotIn("api_key", data)
        hint = data.get("api_key_hint", "")
        self.assertTrue(len(hint) <= 8 or "…" in hint)


if __name__ == "__main__":
    unittest.main()
