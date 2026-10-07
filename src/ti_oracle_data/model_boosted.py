from __future__ import annotations

import json
import math
import sqlite3
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression

from .model_baseline import Metrics, evaluate


DAY_SECONDS = 86_400

FEATURE_NAMES = [
    "elo_difference",
    "glicko_difference",
    "radiant_glicko_deviation",
    "dire_glicko_deviation",
    "glicko_deviation_difference",
    "log_games_difference",
    "log_minimum_team_games",
    "recent_5_win_rate_difference",
    "recent_10_win_rate_difference",
    "ema_form_difference",
    "patch_win_rate_difference",
    "log_patch_games_difference",
    "radiant_rest_days",
    "dire_rest_days",
    "activity_30d_difference",
    "streak_difference",
    "head_to_head_advantage",
    "head_to_head_games_log",
    "series_score_difference",
    "series_maps_played",
    "radiant_side_recent_win_rate",
    "is_premium",
    "is_professional",
    "patch_id",
]


@dataclass
class TeamState:
    games: int = 0
    wins: int = 0
    recent: deque[float] = field(default_factory=lambda: deque(maxlen=10))
    activity: deque[int] = field(default_factory=deque)
    ema: float = 0.5
    streak: int = 0
    last_time: int | None = None
    patch_results: dict[int, list[int]] = field(
        default_factory=lambda: defaultdict(lambda: [0, 0])
    )


@dataclass(frozen=True)
class FeatureDataset:
    x: np.ndarray
    y: np.ndarray
    elo_probability: np.ndarray
    glicko_probability: np.ndarray
    start_times: np.ndarray
    match_ids: np.ndarray


def _smoothed_rate(wins: float, games: int, prior_games: float = 6.0) -> float:
    return (wins + 0.5 * prior_games) / (games + prior_games)


def _recent_rate(results: deque[float], window: int) -> float:
    values = list(results)[-window:]
    return _smoothed_rate(sum(values), len(values))


def _rest_days(state: TeamState, now: int) -> float:
    if state.last_time is None:
        return 30.0
    return min(30.0, max(0.0, (now - state.last_time) / DAY_SECONDS))


def _active_games(state: TeamState, now: int) -> int:
    threshold = now - 30 * DAY_SECONDS
    while state.activity and state.activity[0] < threshold:
        state.activity.popleft()
    return len(state.activity)


def _signed_streak(state: TeamState) -> int:
    return state.streak


def _update_team(state: TeamState, won: int, start_time: int, patch: int) -> None:
    state.games += 1
    state.wins += won
    state.recent.append(float(won))
    state.activity.append(start_time)
    state.ema = 0.15 * won + 0.85 * state.ema
    if won:
        state.streak = state.streak + 1 if state.streak >= 0 else 1
    else:
        state.streak = state.streak - 1 if state.streak <= 0 else -1
    state.last_time = start_time
    state.patch_results[patch][0] += won
    state.patch_results[patch][1] += 1


def build_feature_dataset(connection: sqlite3.Connection) -> FeatureDataset:
    rows = list(
        connection.execute(
            """
            SELECT e.match_id, e.start_time, COALESCE(e.patch, 0) AS patch,
                   e.league_tier, e.radiant_team_id, e.dire_team_id,
                   e.rating_difference AS elo_difference,
                   e.radiant_games_before, e.dire_games_before,
                   e.radiant_expected AS elo_probability, e.radiant_win,
                   g.rating_difference AS glicko_difference,
                   g.radiant_deviation_before, g.dire_deviation_before,
                   g.radiant_expected AS glicko_probability,
                   COALESCE(m.series_id, 0) AS series_id
            FROM map_rating_features e
            JOIN map_glicko_features g USING(match_id)
            JOIN pro_matches m USING(match_id)
            ORDER BY e.start_time, e.match_id
            """
        )
    )
    teams: dict[int, TeamState] = defaultdict(TeamState)
    pairs: dict[tuple[int, int], list[int]] = defaultdict(lambda: [0, 0])
    series: dict[tuple[int, int, int], dict[int, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    radiant_recent: deque[int] = deque(maxlen=500)

    features: list[list[float]] = []
    targets: list[float] = []
    elo_probabilities: list[float] = []
    glicko_probabilities: list[float] = []
    start_times: list[int] = []
    match_ids: list[int] = []

    for row in rows:
        start_time = int(row["start_time"])
        patch = int(row["patch"])
        radiant_id = int(row["radiant_team_id"])
        dire_id = int(row["dire_team_id"])
        radiant = teams[radiant_id]
        dire = teams[dire_id]
        radiant_activity = _active_games(radiant, start_time)
        dire_activity = _active_games(dire, start_time)

        radiant_patch = radiant.patch_results[patch]
        dire_patch = dire.patch_results[patch]
        radiant_patch_rate = _smoothed_rate(radiant_patch[0], radiant_patch[1], 10.0)
        dire_patch_rate = _smoothed_rate(dire_patch[0], dire_patch[1], 10.0)

        pair = (min(radiant_id, dire_id), max(radiant_id, dire_id))
        pair_wins_first, pair_games = pairs[pair]
        first_rate = _smoothed_rate(pair_wins_first, pair_games, 8.0)
        radiant_h2h = first_rate if radiant_id == pair[0] else 1.0 - first_rate

        series_id = int(row["series_id"])
        series_key = (series_id, pair[0], pair[1])
        series_score = series[series_key] if series_id else {}
        radiant_series_wins = int(series_score.get(radiant_id, 0))
        dire_series_wins = int(series_score.get(dire_id, 0))

        league_tier = str(row["league_tier"] or "").lower()
        features.append(
            [
                float(row["elo_difference"]) / 400.0,
                float(row["glicko_difference"]) / 400.0,
                float(row["radiant_deviation_before"]) / 350.0,
                float(row["dire_deviation_before"]) / 350.0,
                (
                    float(row["radiant_deviation_before"])
                    - float(row["dire_deviation_before"])
                )
                / 350.0,
                math.log1p(int(row["radiant_games_before"]))
                - math.log1p(int(row["dire_games_before"])),
                math.log1p(
                    min(
                        int(row["radiant_games_before"]),
                        int(row["dire_games_before"]),
                    )
                ),
                _recent_rate(radiant.recent, 5) - _recent_rate(dire.recent, 5),
                _recent_rate(radiant.recent, 10) - _recent_rate(dire.recent, 10),
                radiant.ema - dire.ema,
                radiant_patch_rate - dire_patch_rate,
                math.log1p(radiant_patch[1]) - math.log1p(dire_patch[1]),
                _rest_days(radiant, start_time),
                _rest_days(dire, start_time),
                float(radiant_activity - dire_activity),
                float(
                    max(-5, min(5, _signed_streak(radiant)))
                    - max(-5, min(5, _signed_streak(dire)))
                ),
                radiant_h2h - 0.5,
                math.log1p(pair_games),
                float(radiant_series_wins - dire_series_wins),
                float(radiant_series_wins + dire_series_wins),
                _smoothed_rate(sum(radiant_recent), len(radiant_recent), 20.0),
                float(league_tier == "premium"),
                float(league_tier == "professional"),
                float(patch),
            ]
        )
        radiant_win = int(row["radiant_win"])
        targets.append(float(radiant_win))
        elo_probabilities.append(float(row["elo_probability"]))
        glicko_probabilities.append(float(row["glicko_probability"]))
        start_times.append(start_time)
        match_ids.append(int(row["match_id"]))

        _update_team(radiant, radiant_win, start_time, patch)
        _update_team(dire, 1 - radiant_win, start_time, patch)
        if radiant_id == pair[0]:
            pairs[pair][0] += radiant_win
        else:
            pairs[pair][0] += 1 - radiant_win
        pairs[pair][1] += 1
        if series_id:
            series[series_key][radiant_id] += radiant_win
            series[series_key][dire_id] += 1 - radiant_win
        radiant_recent.append(radiant_win)

    return FeatureDataset(
        x=np.asarray(features, dtype=float),
        y=np.asarray(targets, dtype=float),
        elo_probability=np.asarray(elo_probabilities, dtype=float),
        glicko_probability=np.asarray(glicko_probabilities, dtype=float),
        start_times=np.asarray(start_times, dtype=np.int64),
        match_ids=np.asarray(match_ids, dtype=np.int64),
    )


def _logit(probability: np.ndarray) -> np.ndarray:
    clipped = np.clip(probability, 1e-6, 1.0 - 1e-6)
    return np.log(clipped / (1.0 - clipped)).reshape(-1, 1)


def _paired_log_loss_interval(
    y_true: np.ndarray,
    candidate: np.ndarray,
    baseline: np.ndarray,
    samples: int = 2_000,
) -> tuple[float, float, float]:
    candidate = np.clip(candidate, 1e-9, 1.0 - 1e-9)
    baseline = np.clip(baseline, 1e-9, 1.0 - 1e-9)
    candidate_loss = -(y_true * np.log(candidate) + (1.0 - y_true) * np.log(1.0 - candidate))
    baseline_loss = -(y_true * np.log(baseline) + (1.0 - y_true) * np.log(1.0 - baseline))
    difference = candidate_loss - baseline_loss
    rng = np.random.default_rng(2026)
    indices = rng.integers(0, len(y_true), size=(samples, len(y_true)))
    bootstrapped = difference[indices].mean(axis=1)
    return (
        float(difference.mean()),
        float(np.quantile(bootstrapped, 0.025)),
        float(np.quantile(bootstrapped, 0.975)),
    )


def _metrics_dict(metrics: Metrics) -> dict[str, float | int]:
    return asdict(metrics)


def train_chronological_boosted(
    connection: sqlite3.Connection,
    cutoff_epoch: int,
    artifact_path: Path,
    recency_half_life_days: float = 120.0,
) -> dict[str, object]:
    dataset = build_feature_dataset(connection)
    training_indices = np.flatnonzero(dataset.start_times < cutoff_epoch)
    test_indices = np.flatnonzero(dataset.start_times >= cutoff_epoch)
    if len(training_indices) < 200 or len(test_indices) < 50:
        raise ValueError("chronological cutoff needs at least 200 train and 50 test maps")

    calibration_size = max(100, int(len(training_indices) * 0.2))
    core_indices = training_indices[:-calibration_size]
    calibration_indices = training_indices[-calibration_size:]
    if len(core_indices) < 100:
        raise ValueError("not enough pre-cutoff maps after calibration split")

    age_days = (cutoff_epoch - dataset.start_times[core_indices]) / DAY_SECONDS
    sample_weight = np.power(0.5, np.maximum(age_days, 0.0) / recency_half_life_days)
    sample_weight = np.maximum(sample_weight, 0.05)
    model = HistGradientBoostingClassifier(
        learning_rate=0.04,
        max_iter=250,
        max_leaf_nodes=15,
        min_samples_leaf=35,
        l2_regularization=3.0,
        early_stopping=False,
        random_state=2026,
    )
    model.fit(dataset.x[core_indices], dataset.y[core_indices], sample_weight=sample_weight)

    calibration_raw = model.predict_proba(dataset.x[calibration_indices])[:, 1]
    calibrator = LogisticRegression(C=10.0, solver="lbfgs", random_state=2026)
    calibrator.fit(_logit(calibration_raw), dataset.y[calibration_indices])

    train_raw = model.predict_proba(dataset.x[training_indices])[:, 1]
    test_raw = model.predict_proba(dataset.x[test_indices])[:, 1]
    train_probability = calibrator.predict_proba(_logit(train_raw))[:, 1]
    test_probability = calibrator.predict_proba(_logit(test_raw))[:, 1]
    elo_test = dataset.elo_probability[test_indices]
    delta, lower, upper = _paired_log_loss_interval(
        dataset.y[test_indices], test_probability, elo_test
    )
    test_metrics = evaluate(dataset.y[test_indices], test_probability)
    elo_test_metrics = evaluate(dataset.y[test_indices], elo_test)
    promoted = bool(
        upper < 0.0 and test_metrics.brier_score < elo_test_metrics.brier_score
    )

    model_path = artifact_path.with_suffix(".joblib")
    artifact: dict[str, object] = {
        "model": "recency_weighted_hist_gradient_boosting_with_platt_calibration",
        "created_at": int(time.time()),
        "cutoff_epoch": cutoff_epoch,
        "feature_names": FEATURE_NAMES,
        "recency_half_life_days": recency_half_life_days,
        "core_train_rows": len(core_indices),
        "calibration_rows": len(calibration_indices),
        "test_rows": len(test_indices),
        "train_metrics": _metrics_dict(evaluate(dataset.y[training_indices], train_probability)),
        "test_metrics": _metrics_dict(test_metrics),
        "uncalibrated_test_metrics": _metrics_dict(
            evaluate(dataset.y[test_indices], test_raw)
        ),
        "elo_test_metrics": _metrics_dict(elo_test_metrics),
        "glicko_test_metrics": _metrics_dict(
            evaluate(dataset.y[test_indices], dataset.glicko_probability[test_indices])
        ),
        "log_loss_delta_vs_elo": delta,
        "log_loss_delta_95_interval": [lower, upper],
        "promoted": promoted,
        "promotion_rule": "upper 95% paired bootstrap log-loss delta < 0 and Brier improves",
        "model_path": str(model_path),
    }
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "calibrator": calibrator,
            "feature_names": FEATURE_NAMES,
            "cutoff_epoch": cutoff_epoch,
        },
        model_path,
    )
    artifact_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    return artifact
