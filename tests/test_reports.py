from __future__ import annotations

import unittest

from ti_oracle_data.reports import ti_team_baseline_rows


class ReportImportTest(unittest.TestCase):
    def test_report_function_is_importable(self) -> None:
        self.assertTrue(callable(ti_team_baseline_rows))


if __name__ == "__main__":
    unittest.main()
