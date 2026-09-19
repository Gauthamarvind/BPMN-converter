"""
Scope v2 phase 2: Celonis is the default export target everywhere.

A caller that does not name a profile — the HTTP API, the CLI, or the pipeline directly —
must get Celonis, not generic. These tests pin that down so the default cannot drift back.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from starlette.testclient import TestClient

from backend.server import app
from backend.pipeline.profiles import DEFAULT_PROFILE, SUPPORTED_PROFILES, normalize_profile


SIMPLE_TEXT = (
    "1. Requester submits a purchase request.\n"
    "2. Manager reviews the request.\n"
    "3. Finance releases the payment.\n"
)


class TestProfileConstants(unittest.TestCase):
    def test_celonis_is_first_and_default(self):
        self.assertEqual(SUPPORTED_PROFILES, ["celonis", "generic"])
        self.assertEqual(DEFAULT_PROFILE, "celonis")

    def test_normalize_falls_back_to_default(self):
        self.assertEqual(normalize_profile("generic"), "generic")
        self.assertEqual(normalize_profile(None), "celonis")
        self.assertEqual(normalize_profile("signavio"), "celonis")


class TestApiDefaults(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_profiles_endpoint_lists_both_targets_celonis_first(self):
        res = self.client.get("/api/profiles")
        self.assertEqual(res.status_code, 200)
        ids = [p["id"] for p in res.json()["profiles"]]
        self.assertEqual(ids, ["celonis", "generic"])

    def test_convert_json_without_profile_uses_celonis(self):
        res = self.client.post(
            "/api/convert-json",
            json={"text": SIMPLE_TEXT, "filename": "purchase.txt", "mock": True},
        )
        self.assertEqual(res.status_code, 200, res.text[:300])
        data = res.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["lint_result"]["profile_name"], "celonis")

    def test_convert_upload_without_profile_uses_celonis(self):
        res = self.client.post(
            "/api/convert",
            files={"file": ("purchase.txt", SIMPLE_TEXT.encode("utf-8"), "text/plain")},
            data={"mock": "true"},
        )
        self.assertEqual(res.status_code, 200, res.text[:300])
        self.assertEqual(res.json()["lint_result"]["profile_name"], "celonis")

    def test_explicit_generic_is_still_honoured(self):
        res = self.client.post(
            "/api/convert-json",
            json={"text": SIMPLE_TEXT, "filename": "purchase.txt", "mock": True, "profile": "generic"},
        )
        self.assertEqual(res.status_code, 200, res.text[:300])
        self.assertEqual(res.json()["lint_result"]["profile_name"], "generic")

    def test_removed_vendor_profile_is_rejected_on_export(self):
        ir = {
            "id": "Process_1",
            "name": "Purchase",
            "pools": [{"id": "Pool_1", "name": "Org", "lanes": [{"id": "Lane_1", "name": "Finance"}]}],
            "elements": [
                {"id": "Start_1", "type": "startEvent", "name": "Start", "laneId": "Lane_1"},
                {"id": "Task_1", "type": "task", "name": "Pay", "laneId": "Lane_1"},
                {"id": "End_1", "type": "endEvent", "name": "End", "laneId": "Lane_1"},
            ],
            "flows": [
                {"id": "Flow_1", "sourceId": "Start_1", "targetId": "Task_1"},
                {"id": "Flow_2", "sourceId": "Task_1", "targetId": "End_1"},
            ],
        }
        res = self.client.post(
            "/api/export/bpmn",
            json={"process_name": "Purchase", "ir": ir, "profile": "signavio"},
        )
        self.assertEqual(res.status_code, 400)


class TestCliDefaults(unittest.TestCase):
    def test_cli_convert_defaults_to_celonis(self):
        import inspect
        from backend.cli import convert_file

        sig = inspect.signature(convert_file)
        self.assertEqual(sig.parameters["profile_name"].default, "celonis")

    def test_pipeline_defaults_to_celonis(self):
        import inspect
        from backend.pipeline.process_pipeline import process_pipeline, render_ir

        self.assertEqual(inspect.signature(process_pipeline).parameters["profile_name"].default, "celonis")
        self.assertEqual(inspect.signature(render_ir).parameters["profile_name"].default, "celonis")


if __name__ == "__main__":
    unittest.main()
