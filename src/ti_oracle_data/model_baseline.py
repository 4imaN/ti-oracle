from __future__ import annotations

import json
import math
import sqlite3
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np


FEATURE_NAMES = [
    "rating_difference",
    "glicko_rating_difference",
    "radiant_glicko_deviation",
    "dire_glicko_deviation",
    "log_radiant_games_before",
    "log_dire_games_before",
    "is_premium",
    "is_professional",
]


@dataclass(frozen=True)
class Metrics:
    rows: int
    log_loss: float
    brier_score: float
    accuracy: float
    calibration_error: float


def _sigmoid(values: np.ndarray) -> np.ndarray:
    clipped = np.clip(values, -35.0, 35.0)
    return 1.0 / (1.0 + np.exp(-clipped))


def evaluate(y_true: np.ndarray, probability: np.ndarray) -> Metrics:
    probability = np.clip(probability, 1e-9, 1.0 - 1e-9)
    log_loss = float(
        -np.mean(y_true * np.log(probability) + (1.0 - y_true) * np.log(1.0 - probability))
    )
    brier = float(np.mean((probability - y_true) ** 2))
    accuracy = float(np.mean((probability >= 0.5) == y_true))
    calibration = 0.0
    for lower in np.linspace(0.0, 0.9, 10):
        upper = lower + 0.1
        mask = (probability >= lower) & (
            probability <= upper if upper >= 1.0 else probability < upper
        )
        if np.any(mask):
            calibration += float(np.mean(mask)) * abs(
                float(np.mean(probability[mask])) - float(np.mean(y_true[mask]))
            )
    return Metrics(len(y_true), log_loss, brier, accuracy, calibration)


def _matrix(rows: list[sqlite3.Row]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    features = []
    targets = []
    elo_probabilities = []
    for row in rows:
        features.append(
            [
                float(row["rating_difference"]),
                float(row["glicko_rating_difference"]),
                float(row["radiant_glicko_deviation"]),
                float(row["dire_glicko_deviation"]),
                math.log1p(int(row["radiant_games_before"])),
                math.log1p(int(row["dire_games_before"])),
                float(row["league_tier"] == "premium"),
                float(row["league_tier"] == "professional"),
            ]
        )
        targets.append(float(row["radiant_win"]))
        elo_probabilities.append(float(row["radiant_expected"]))
    return np.asarray(features), np.asarray(targets), np.asarray(elo_probabilities)


def fit_logistic(
    x: np.ndarray,
    y: np.ndarray,
    l2: float = 0.25,
    maximum_iterations: int = 100,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    means = x.mean(axis=0)
    scales = x.std(axis=0)
    scales[scales < 1e-9] = 1.0
    standardized = (x - means) / scales
    design = np.column_stack([np.ones(len(x)), standardized])
    weights = np.zeros(design.shape[1])
    regularizer = np.eye(design.shape[1]) * l2
    regularizer[0, 0] = 0.0
    for _ in range(maximum_iterations):
        probabilities = _sigmoid(design @ weights)
        gradient = design.T @ (probabilities - y) / len(y) + regularizer @ weights / len(y)
        curvature = probabilities * (1.0 - probabilities)
        hessian = (design.T * curvature) @ design / len(y) + regularizer / len(y)
        step = np.linalg.solve(hessian + np.eye(len(weights)) * 1e-9, gradient)
        weights -= step
        if float(np.max(np.abs(step))) < 1e-8:
            break
    return weights, means, scales


def predict(
    x: np.ndarray, weights: np.ndarray, means: np.ndarray, scales: np.ndarray
) -> np.ndarray:
    design = np.column_stack([np.ones(len(x)), (x - means) / scales])
    return _sigmoid(design @ weights)


def train_chronological_baseline(
    connection: sqlite3.Connection,
    cutoff_epoch: int,
    artifact_path: Path,
) -> dict[str, object]:
    rows = list(
        connection.execute(
            """
            SELECT e.start_time AS start_time, e.rating_difference AS rating_difference,
                   radiant_games_before,
                   dire_games_before, league_tier, e.radiant_expected, e.radiant_win,
                   g.rating_difference AS glicko_rating_difference,
                   g.radiant_deviation_before AS radiant_glicko_deviation,
                   g.dire_deviation_before AS dire_glicko_deviation
            FROM map_rating_features e
            JOIN map_glicko_features g USING(match_id)
            ORDER BY e.start_time, e.match_id
            """
        )
    )
    training_rows = [row for row in rows if int(row["start_time"]) < cutoff_epoch]
    test_rows = [row for row in rows if int(row["start_time"]) >= cutoff_epoch]
    if not training_rows or not test_rows:
        raise ValueError("chronological cutoff must leave non-empty train and test sets")

    x_train, y_train, elo_train = _matrix(training_rows)
    x_test, y_test, elo_test = _matrix(test_rows)
    weights, means, scales = fit_logistic(x_train, y_train)
    train_probability = predict(x_train, weights, means, scales)
    test_probability = predict(x_test, weights, means, scales)
    artifact: dict[str, object] = {
        "model": "l2_logistic_elo_calibrator",
        "created_at": int(time.time()),
        "cutoff_epoch": cutoff_epoch,
        "feature_names": FEATURE_NAMES,
        "intercept": float(weights[0]),
        "weights": [float(value) for value in weights[1:]],
        "means": [float(value) for value in means],
        "scales": [float(value) for value in scales],
        "train_metrics": asdict(evaluate(y_train, train_probability)),
        "test_metrics": asdict(evaluate(y_test, test_probability)),
        "elo_train_metrics": asdict(evaluate(y_train, elo_train)),
        "elo_test_metrics": asdict(evaluate(y_test, elo_test)),
    }
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    return artifact
