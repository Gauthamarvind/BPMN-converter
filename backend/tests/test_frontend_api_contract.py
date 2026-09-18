"""
Frontend <-> backend API contract check.

Scans the React sources for `fetch('/api/...')` calls and asserts that each path exists on
the FastAPI app with the HTTP method the frontend uses. This is what would have caught the
Template Manager posting to a route that did not exist. It runs with the Python test suite
so no Node toolchain is needed in CI.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.server import app

FETCH_RE = re.compile(
    r"fetch\(\s*(?P<q>[`'\"])(?P<path>/api/[^`'\"]*)(?P=q)\s*(?:,\s*\{(?P<opts>.*?)\})?\s*\)",
    re.S,
)
METHOD_RE = re.compile(r"method\s*:\s*['\"](?P<m>[A-Z]+)['\"]")


def _template_to_regex(route_path: str) -> re.Pattern:
    pattern = re.sub(r"\{[^}/]+:path\}", r".+", route_path)
    pattern = re.sub(r"\{[^}]+\}", r"[^/]+", pattern)
    return re.compile("^" + pattern + "$")


class TestFrontendApiContract(unittest.TestCase):
    def test_every_frontend_fetch_has_a_backend_route(self):
        src_dir = _PROJECT_ROOT / "src"
        self.assertTrue(src_dir.exists(), "frontend sources missing")

        routes = []
        for r in app.routes:
            path = getattr(r, "path", None)
            methods = getattr(r, "methods", None)
            if path and methods:
                routes.append((_template_to_regex(path), set(methods), path))

        problems = []
        seen = 0
        for tsx in list(src_dir.rglob("*.tsx")) + list(src_dir.rglob("*.ts")):
            text = tsx.read_text(encoding="utf-8")
            for m in FETCH_RE.finditer(text):
                seen += 1
                raw_path = m.group("path")
                # template literals like `/api/templates/${templateId}` -> a single segment
                path = re.sub(r"\$\{[^}]*\}", "x", raw_path).split("?")[0]
                method = "GET"
                if m.group("opts"):
                    mm = METHOD_RE.search(m.group("opts"))
                    if mm:
                        method = mm.group("m")
                if not any(rx.match(path) and method in methods for rx, methods, _ in routes):
                    problems.append(f"{tsx.relative_to(_PROJECT_ROOT)}: {method} {raw_path}")

        # href="/api/..." download links
        for tsx in src_dir.rglob("*.tsx"):
            text = tsx.read_text(encoding="utf-8")
            for m in re.finditer(r"href=\{?[`'\"](?P<path>/api/[^`'\"]*)", text):
                seen += 1
                path = re.sub(r"\$\{[^}]*\}", "x", m.group("path")).split("?")[0]
                if not any(rx.match(path) and "GET" in methods for rx, methods, _ in routes):
                    problems.append(f"{tsx.relative_to(_PROJECT_ROOT)}: GET(href) {m.group('path')}")

        self.assertGreater(seen, 5, "expected to find API calls in the frontend sources")
        self.assertEqual(problems, [], "frontend calls routes the backend does not serve:\n" + "\n".join(problems))


if __name__ == "__main__":
    unittest.main()
