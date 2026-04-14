"""
test_extractor.py
-----------------
Unit + integration tests for the ETL extraction layer.

Run (unit tests only, no network needed):
    SKIP_INTEGRATION=1 python test_extractor.py

Run everything (requires internet):
    python test_extractor.py

Run with pytest:
    pytest test_extractor.py -v
    pytest test_extractor.py -v -k "not Integration"
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from api_extractor import (
    _detect_shape,
    _flatten_dict,
    _normalise,
    _safe_filename,
    extract_api_to_csv,
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Shape detection
# ─────────────────────────────────────────────────────────────────────────────

class TestDetectShape(unittest.TestCase):

    def test_list_of_dicts(self):
        self.assertEqual(_detect_shape([{"id": 1}, {"id": 2}]), "list_of_dicts")

    def test_list_of_scalars(self):
        self.assertEqual(_detect_shape([1, 2, 3]),       "list_of_scalars")
        self.assertEqual(_detect_shape(["a", "b", "c"]), "list_of_scalars")

    def test_empty_list(self):
        self.assertEqual(_detect_shape([]), "empty_list")

    def test_flat_dict(self):
        self.assertEqual(_detect_shape({"id": 1, "name": "Alice"}), "flat_dict")

    def test_nested_dict(self):
        data = {"user": {"id": 1, "name": "Alice"}, "page": 1}
        self.assertEqual(_detect_shape(data), "nested_dict")

    def test_wrapped_envelope(self):
        data = {"data": [{"id": 1}, {"id": 2}], "total": 2, "page": 1}
        self.assertEqual(_detect_shape(data), "wrapped")

    def test_unknown_scalar(self):
        self.assertEqual(_detect_shape(42),   "unknown")
        self.assertEqual(_detect_shape(None), "unknown")


# ─────────────────────────────────────────────────────────────────────────────
# 2. Dict flattener
# ─────────────────────────────────────────────────────────────────────────────

class TestFlattenDict(unittest.TestCase):

    def test_flat_passthrough(self):
        d = {"a": 1, "b": "hello"}
        self.assertEqual(_flatten_dict(d), d)

    def test_one_level_nesting(self):
        d = {"user": {"id": 1, "name": "Alice"}}
        self.assertEqual(_flatten_dict(d), {"user.id": 1, "user.name": "Alice"})

    def test_deep_nesting(self):
        d = {"a": {"b": {"c": 42}}}
        self.assertEqual(_flatten_dict(d), {"a.b.c": 42})

    def test_list_values_serialised_as_json(self):
        d = {"tags": ["python", "etl"]}
        result = _flatten_dict(d)
        self.assertEqual(result["tags"], '["python", "etl"]')

    def test_mixed_nested_and_flat(self):
        d = {"id": 1, "address": {"city": "Cairo", "zip": "12345"}}
        result = _flatten_dict(d)
        self.assertEqual(result["id"],           1)
        self.assertEqual(result["address.city"], "Cairo")
        self.assertEqual(result["address.zip"],  "12345")


# ─────────────────────────────────────────────────────────────────────────────
# 3. Normaliser
# ─────────────────────────────────────────────────────────────────────────────

class TestNormalise(unittest.TestCase):

    def test_list_of_dicts(self):
        rows = [{"id": 1}, {"id": 2}]
        result = _normalise(rows, "list_of_dicts")
        self.assertEqual(len(result), 2)
        self.assertIn("id", result[0])

    def test_list_of_scalars(self):
        result = _normalise([10, 20, 30], "list_of_scalars")
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], {"index": 0, "value": 10})

    def test_flat_dict_single_row(self):
        d = {"x": 1, "y": 2}
        self.assertEqual(_normalise(d, "flat_dict"), [d])

    def test_nested_dict_flattened(self):
        d = {"user": {"id": 1, "name": "A"}, "page": 2}
        result = _normalise(d, "nested_dict")
        self.assertEqual(len(result), 1)
        self.assertIn("user.id", result[0])

    def test_wrapped_extracts_rows_and_meta(self):
        data = {"items": [{"id": 1}, {"id": 2}], "total": 2}
        result = _normalise(data, "wrapped")
        self.assertEqual(len(result), 2)
        self.assertIn("_meta_total", result[0])
        self.assertEqual(result[0]["_meta_total"], 2)

    def test_empty_list(self):
        self.assertEqual(_normalise([], "empty_list"), [])

    def test_unknown_fallback(self):
        result = _normalise(42, "unknown")
        self.assertEqual(len(result), 1)
        self.assertIn("raw", result[0])


# ─────────────────────────────────────────────────────────────────────────────
# 4. Safe filename helper
# ─────────────────────────────────────────────────────────────────────────────

class TestSafeFilename(unittest.TestCase):

    def test_strips_scheme_and_host(self):
        self.assertEqual(_safe_filename("https://api.example.com/v1/users"), "v1_users")

    def test_strips_query_string(self):
        self.assertEqual(_safe_filename("https://api.example.com/forecast?lat=40&lon=-74"), "forecast")

    def test_root_path_fallback(self):
        self.assertEqual(_safe_filename("https://api.example.com/"), "extract")


# ─────────────────────────────────────────────────────────────────────────────
# 5. Full pipeline — mocked HTTP (no real network needed)
# ─────────────────────────────────────────────────────────────────────────────

class TestExtractApiToCsvMocked(unittest.TestCase):

    def _mock_response(self, payload, status_code: int = 200):
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.json.return_value = payload
        mock_resp.raise_for_status = MagicMock()
        return mock_resp

    @patch("api_extractor.requests.get")
    def test_list_of_dicts_creates_csv(self, mock_get):
        payload = [{"id": i, "name": f"User{i}"} for i in range(5)]
        mock_get.return_value = self._mock_response(payload)

        with tempfile.TemporaryDirectory() as tmpdir:
            result = extract_api_to_csv("https://fake.api/users", tmpdir)
            self.assertEqual(result["status"],    "success")
            self.assertEqual(result["shape"],     "list_of_dicts")
            self.assertEqual(result["row_count"], 5)
            self.assertIn("id", result["columns"])
            self.assertTrue(Path(result["csv_path"]).exists())

    @patch("api_extractor.requests.get")
    def test_wrapped_envelope(self, mock_get):
        payload = {"results": [{"id": 1}, {"id": 2}], "count": 2}
        mock_get.return_value = self._mock_response(payload)

        with tempfile.TemporaryDirectory() as tmpdir:
            result = extract_api_to_csv("https://fake.api/items", tmpdir)
            self.assertEqual(result["shape"],     "wrapped")
            self.assertEqual(result["row_count"], 2)
            self.assertIn("_meta_count", result["columns"])

    @patch("api_extractor.requests.get")
    def test_flat_dict_single_row(self, mock_get):
        payload = {"status": "ok", "version": "1.0"}
        mock_get.return_value = self._mock_response(payload)

        with tempfile.TemporaryDirectory() as tmpdir:
            result = extract_api_to_csv("https://fake.api/health", tmpdir)
            self.assertEqual(result["shape"],     "flat_dict")
            self.assertEqual(result["row_count"], 1)

    @patch("api_extractor.requests.get")
    def test_nested_dict(self, mock_get):
        payload = {"user": {"id": 1, "name": "Alice"}, "token": "abc"}
        mock_get.return_value = self._mock_response(payload)

        with tempfile.TemporaryDirectory() as tmpdir:
            result = extract_api_to_csv("https://fake.api/me", tmpdir)
            self.assertEqual(result["shape"],     "nested_dict")
            self.assertIn("user.id", result["columns"])

    @patch("api_extractor.requests.get")
    def test_custom_filename_used(self, mock_get):
        mock_get.return_value = self._mock_response([{"id": 1}])

        with tempfile.TemporaryDirectory() as tmpdir:
            result = extract_api_to_csv("https://fake.api/x", tmpdir, filename="my_output")
            self.assertTrue(result["csv_path"].endswith("my_output.csv"))
            self.assertTrue(Path(result["csv_path"]).exists())

    @patch("api_extractor.requests.get")
    def test_network_error_returns_error_status(self, mock_get):
        import requests as req
        mock_get.side_effect = req.ConnectionError("No route to host")

        with tempfile.TemporaryDirectory() as tmpdir:
            result = extract_api_to_csv("https://unreachable.api/data", tmpdir)
            self.assertEqual(result["status"], "error")
            self.assertIn("message", result)

    @patch("api_extractor.requests.get")
    def test_empty_response_no_csv(self, mock_get):
        mock_get.return_value = self._mock_response([])

        with tempfile.TemporaryDirectory() as tmpdir:
            result = extract_api_to_csv("https://fake.api/empty", tmpdir)
            self.assertEqual(result["row_count"], 0)
            self.assertIsNone(result["csv_path"])

    @patch("api_extractor.requests.get")
    def test_invalid_json_returns_error(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.side_effect = ValueError("No JSON")
        mock_get.return_value = mock_resp

        with tempfile.TemporaryDirectory() as tmpdir:
            result = extract_api_to_csv("https://fake.api/bad", tmpdir)
            self.assertEqual(result["status"], "error")


# ─────────────────────────────────────────────────────────────────────────────
# 6. Integration tests — real public APIs (requires internet)
# ─────────────────────────────────────────────────────────────────────────────

class TestRealAPIIntegration(unittest.TestCase):
    """
    Hits live public APIs. Skipped automatically when:
      • SKIP_INTEGRATION env var is set, OR
      • the API is unreachable (result["status"] == "error")
    """

    def setUp(self):
        if os.environ.get("SKIP_INTEGRATION"):
            self.skipTest("SKIP_INTEGRATION is set — skipping live API tests.")

    def _run(self, url: str, expected_shape: str):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = extract_api_to_csv(url, tmpdir)

        if result["status"] == "error":
            self.skipTest(f"Network unavailable: {result['message']}")

        self.assertEqual(result["shape"], expected_shape,
                         f"Expected shape '{expected_shape}', got '{result['shape']}'")
        self.assertGreater(result["row_count"], 0)
        self.assertTrue(
            Path(result["csv_path"]).exists() if result["csv_path"] else True
        )
        print(f"\n  ✓ {url}")
        print(f"    shape={result['shape']}, rows={result['row_count']}, cols={result['col_count']}")
        return result

    def test_users(self):
        result = self._run("https://jsonplaceholder.typicode.com/users", "list_of_dicts")
        self.assertEqual(result["row_count"], 10)

    def test_posts(self):
        result = self._run("https://jsonplaceholder.typicode.com/posts", "list_of_dicts")
        self.assertEqual(result["row_count"], 100)

    def test_todos(self):
        result = self._run("https://jsonplaceholder.typicode.com/todos", "list_of_dicts")
        self.assertEqual(result["row_count"], 200)

    def test_open_meteo_weather(self):
        url = (
            "https://api.open-meteo.com/v1/forecast"
            "?latitude=30.06&longitude=31.24&current_weather=true"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            result = extract_api_to_csv(url, tmpdir)
        if result["status"] == "error":
            self.skipTest(f"Network unavailable: {result['message']}")
        self.assertIn(result["shape"], ("nested_dict", "flat_dict", "wrapped"))
        print(f"\n  ✓ open-meteo  shape={result['shape']}, cols={result['columns']}")


# ─────────────────────────────────────────────────────────────────────────────
# Runner (works without pytest)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print()
    print("═" * 62)
    print("  ETL Extractor — Test Suite")
    print("═" * 62)

    loader = unittest.TestLoader()
    suite  = unittest.TestSuite()

    # Unit tests first (fast, no network)
    for cls in [
        TestDetectShape,
        TestFlattenDict,
        TestNormalise,
        TestSafeFilename,
        TestExtractApiToCsvMocked,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    # Integration tests last (network required)
    suite.addTests(loader.loadTestsFromTestCase(TestRealAPIIntegration))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
