from __future__ import annotations

import unittest

from ti_oracle_data.glicko_timeline import rebuild_glicko_timeline


class GlickoTimelineImportTest(unittest.TestCase):
    def test_builder_is_importable(self) -> None:
        self.assertTrue(callable(rebuild_glicko_timeline))


if __name__ == "__main__":
    unittest.main()
