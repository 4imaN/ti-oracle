from __future__ import annotations

import unittest

from ti_oracle_data.rosters import lineup_key


class RosterTest(unittest.TestCase):
    def test_lineup_key_is_order_independent(self) -> None:
        self.assertEqual(lineup_key([1, 2, 3, 4, 5]), lineup_key([5, 3, 1, 4, 2]))

    def test_lineup_change_changes_key(self) -> None:
        self.assertNotEqual(lineup_key([1, 2, 3, 4, 5]), lineup_key([1, 2, 3, 4, 6]))


if __name__ == "__main__":
    unittest.main()
