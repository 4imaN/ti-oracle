from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import StandardScaler

from .model_baseline import evaluate
from .model_boosted import (
    DAY_SECONDS,
    FEATURE_NAMES as TEAM_FEATURE_NAMES,
    _paired_log_loss_interval,
    build_feature_dataset,
)


ROSTER_FEATURE_NAMES = [
    "player_rating_difference",
    "log_player_experience_difference",
    "log_minimum_lineup_player_experience",
    "log_exact_lineup_maps_difference",
    "log_exact_lineup_maps_total",
    "pair_chemistry_difference",
    "retained_players_difference",
    "new_players_difference",
]
FEATURE_NAMES = TEAM_FEATURE_NAMES + ROSTER_FEATURE_NAMES


@dataclass(frozen=True)
class RosterDataset:
    x: np.ndarray
    y: np.ndarray
    elo_probability: np.ndarray
    start_times: np.ndarray
    match_ids: np.ndarray


def _extra_features(row: sqlite3.Row) -> list[float]:
    return [
        float(row["player_rating_difference"]) / 400.0,
        np.log1p(float(row["radiant_average_games"]))
        - np.log1p(float(row["dire_average_games"])),
        np.log1p(
            min(
                float(row["radiant_average_games"]),
                float(row["dire_average_games"]),
            )
        ),
        np.log1p(int(row["radiant_lineup_maps"]))
        - np.log1p(int(row["dire_lineup_maps"])),
        np.log1p(
            int(row["radiant_lineup_maps"]) + int(row["dire_lineup_maps"])
        ),
        float(row["radiant_pair_maps"]) - float(row["dire_pair_maps"]),
        float(row["radiant_retained_players"] - row["dire_retained_players"]),
        float(row["radiant_new_players"] - row["dire_new_players"]),
    ]


def build_roster_dataset(connection: sqlite3.Connection) -> RosterDataset:
    team = build_feature_dataset(connection)
    index_by_match = {
        int(match_id): index for index, match_id in enumerate(team.match_ids)
    }
    rows = list(
        connection.execute(
            "SELECT * FROM map_roster_features ORDER BY start_time, match_id"
        )
    )
    usable = [row for row in rows if int(row["match_id"]) in index_by_match]
    x = []
    y = []
    elo = []
    start_times = []
    match_ids = []
    for row in usable:
        match_id = int(row["match_id"])
        team_index = index_by_match[match_id]
        x.append([*team.x[team_index], *_extra_features(row)])
        y.append(float(row["radiant_win"]))
        elo.append(float(team.elo_probability[team_index]))
        start_times.append(int(row["start_time"]))
        match_ids.append(match_id)
    return RosterDataset(
        x=np.asarray(x, dtype=float),
        y=np.asarray(y, dtype=float),
        elo_probability=np.asarray(elo, dtype=float),
        start_times=np.asarray(start_times, dtype=np.int64),
        match_ids=np.asarray(match_ids, dtype=np.int64),
    )


def _new_model(c_value: float) -> Pipeline:
    return make_pipeline(
        StandardScaler(),
        LogisticRegression(C=c_value, max_iter=2_000, random_state=2026),
    )


def _weights(times: np.ndarray, reference: int, half_life_days: float) -> np.ndarray:
    age_days = np.maximum(0.0, (reference - times) / DAY_SECONDS)
    return np.maximum(0.05, np.power(0.5, age_days / half_life_days))


def train_chronological_roster_model(
    connection: sqlite3.Connection,
    cutoff_epoch: int,
    artifact_path: Path,
    recency_half_life_days: float = 120.0,
) -> dict[str, object]:
    dataset = build_roster_dataset(connection)
    training = np.flatnonzero(dataset.start_times < cutoff_epoch)
    test = np.flatnonzero(dataset.start_times >= cutoff_epoch)
    if len(training) < 250 or len(test) < 100:
        raise ValueError("roster model needs at least 250 train and 100 test maps")
    calibration_size = max(75, int(len(training) * 0.2))
    core = training[:-calibration_size]
    calibration = training[-calibration_size:]
    candidate_c = [0.01, 0.03, 0.1, 0.3, 1.0, 3.0]
    candidates: list[tuple[float, float, Pipeline]] = []
    core_weight = _weights(
        dataset.start_times[core], cutoff_epoch, recency_half_life_days
    )
    for c_value in candidate_c:
        candidate = _new_model(c_value)
        candidate.fit(
            dataset.x[core],
            dataset.y[core],
            logisticregression__sample_weight=core_weight,
        )
        probability = candidate.predict_proba(dataset.x[calibration])[:, 1]
        candidates.append(
            (float(log_loss(dataset.y[calibration], probability)), c_value, candidate)
        )
    candidates.sort(key=lambda item: (item[0], item[1]))
    calibration_loss, selected_c, evaluation_model = candidates[0]
    test_probability = evaluation_model.predict_proba(dataset.x[test])[:, 1]
    train_probability = evaluation_model.predict_proba(dataset.x[training])[:, 1]
    test_metrics = evaluate(dataset.y[test], test_probability)
    elo_test_metrics = evaluate(dataset.y[test], dataset.elo_probability[test])
    delta, lower, upper = _paired_log_loss_interval(
        dataset.y[test], test_probability, dataset.elo_probability[test], samples=10_000
    )
    provisional = bool(
        test_metrics.log_loss < elo_test_metrics.log_loss
        and test_metrics.brier_score < elo_test_metrics.brier_score
    )
    promoted = bool(provisional and upper < 0.0)

    deployment_model = _new_model(selected_c)
    deployment_reference = int(dataset.start_times.max()) + DAY_SECONDS
    deployment_model.fit(
        dataset.x,
        dataset.y,
        logisticregression__sample_weight=_weights(
            dataset.start_times, deployment_reference, recency_half_life_days
        ),
    )
    coefficients = evaluation_model.named_steps["logisticregression"].coef_[0]
    strongest = sorted(
        zip(FEATURE_NAMES, coefficients, strict=True),
        key=lambda pair: abs(float(pair[1])),
        reverse=True,
    )[:12]
    model_path = artifact_path.with_suffix(".joblib")
    artifact: dict[str, object] = {
        "model": "recency_weighted_roster_logistic",
        "created_at": int(time.time()),
        "cutoff_epoch": cutoff_epoch,
        "feature_names": FEATURE_NAMES,
        "recency_half_life_days": recency_half_life_days,
        "core_train_rows": len(core),
        "calibration_rows": len(calibration),
        "test_rows": len(test),
        "candidate_validation_log_loss": {
            str(c_value): loss for loss, c_value, _ in sorted(candidates, key=lambda x: x[1])
        },
        "selected_c": selected_c,
        "selected_validation_log_loss": calibration_loss,
        "train_metrics": asdict(evaluate(dataset.y[training], train_probability)),
        "test_metrics": asdict(test_metrics),
        "elo_test_metrics": asdict(elo_test_metrics),
        "log_loss_delta_vs_elo": delta,
        "log_loss_delta_95_interval": [lower, upper],
        "provisional_improvement": provisional,
        "promoted": promoted,
        "promotion_rule": "point log-loss and Brier improve; 95% paired bootstrap log-loss interval must also be below zero",
        "strongest_standardized_coefficients": [
            {"feature": name, "coefficient": float(value)} for name, value in strongest
        ],
        "model_path": str(model_path),
        "deployment_fit_rows": len(dataset.y),
    }
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "evaluation_model": evaluation_model,
            "deployment_model": deployment_model,
            "feature_names": FEATURE_NAMES,
            "cutoff_epoch": cutoff_epoch,
            "selected_c": selected_c,
        },
        model_path,
    )
    artifact_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    return artifact
