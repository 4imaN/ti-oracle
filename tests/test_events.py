from __future__ import annotations

import unittest

from ti_oracle_data.events import utc_date_epoch


class EventTest(unittest.TestCase):
    def test_end_of_day_is_exclusive_next_day(self) -> None:
        self.assertEqual(
            utc_date_epoch("2026-08-23", end_of_day=True) - utc_date_epoch("2026-08-23"),
            86400,
        )


if __name__ == "__main__":
    unittest.main()
