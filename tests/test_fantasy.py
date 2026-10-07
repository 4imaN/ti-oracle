from __future__ import annotations

import unittest

from ti_oracle_data.fantasy import _integer


class FantasyTest(unittest.TestCase):
    def test_missing_item_counter_is_zero(self) -> None:
        self.assertEqual(_integer(None, "smoke_of_deceit"), 0)
        self.assertEqual(_integer({}, "smoke_of_deceit"), 0)

    def test_item_counter_is_integer(self) -> None:
        self.assertEqual(_integer({"smoke_of_deceit": 3}, "smoke_of_deceit"), 3)


if __name__ == "__main__":
    unittest.main()
