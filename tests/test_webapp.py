from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from ti_oracle_data.webapp import _image_kind, _infer_fantasy_role, create_app


class WebAppTest(unittest.TestCase):
    def test_image_signature_detection(self) -> None:
        self.assertEqual(_image_kind(b"\xff\xd8\xffrest"), "jpeg")
        self.assertEqual(_image_kind(b"\x89PNG\r\n\x1a\nrest"), "png")
        self.assertEqual(_image_kind(b"RIFF1234WEBPrest"), "webp")
        self.assertIsNone(_image_kind(b"not an image"))

    def test_overview_works_with_empty_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            app = create_app(Path(directory) / "web.sqlite3")
            response = TestClient(app).get("/api/overview")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["counts"]["maps"], 0)

    def test_role_inference_uses_roster_category_then_match_fallback(self) -> None:
        self.assertEqual(_infer_fantasy_role(0, 52, 0, 0, 740, 1, 601), "Core")
        self.assertEqual(_infer_fantasy_role(0, 1, 77, 0, 643, 2, 459), "Mid")
        self.assertEqual(_infer_fantasy_role(2, 73, 3, 3, 345, 34, 52), "Support")
        self.assertEqual(_infer_fantasy_role(2, 0, 20, 0, 500, 2, 200), "Support")


if __name__ == "__main__":
    unittest.main()
