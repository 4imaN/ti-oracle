from __future__ import annotations

import unittest

import numpy as np

from ti_oracle_data.model_baseline import evaluate, fit_logistic, predict


class BaselineModelTest(unittest.TestCase):
    def test_logistic_learns_ordered_signal(self) -> None:
        x = np.asarray([[-2.0], [-1.0], [1.0], [2.0]])
        y = np.asarray([0.0, 0.0, 1.0, 1.0])
        weights, means, scales = fit_logistic(x, y)
        probability = predict(x, weights, means, scales)
        self.assertLess(probability[0], probability[-1])
        self.assertGreater(evaluate(y, probability).accuracy, 0.5)


if __name__ == "__main__":
    unittest.main()
