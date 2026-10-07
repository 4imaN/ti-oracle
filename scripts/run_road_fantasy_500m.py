#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import pickle
import random
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ti_oracle_data.fantasy_projection import write_fantasy_projection  # noqa: E402
from ti_oracle_data.reports import ti_team_baseline_rows  # noqa: E402
from ti_oracle_data.simulation import TeamStrength, simulate_road_once  # noqa: E402
from ti_oracle_data.store import Store  # noqa: E402


CATEGORIES = (
    "undefeated",
    "four_one",
    "elimination_winners",
    "elimination_losers",
    "one_four",
    "winless",
    "main_stage",
)
SEED_STRIDE = 1_000_003
FORMAT_ASSUMPTION = (
    "five Swiss rounds; rounds 1-3 within seeded initial groups, round 4 cross-group, "
    "round 5 open; all series Bo3; 4-0/4-1 qualify, 3-2 plays 2-3"
)


def _atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _atomic_pickle(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        pickle.dump(value, handle, protocol=pickle.HIGHEST_PROTOCOL)
    temporary.replace(path)


def _simulate_chunk(
    task: tuple[int, int, int, list[TeamStrength]],
) -> tuple[int, int, dict[str, Counter[str]], Counter[tuple[str, ...]]]:
    chunk_index, iterations, seed, teams = task
    rng = random.Random(seed + chunk_index * SEED_STRIDE)
    marginal = {category: Counter() for category in CATEGORIES}
    combinations: Counter[tuple[str, ...]] = Counter()
    for _ in range(iterations):
        result = simulate_road_once(teams, rng)
        for category in CATEGORIES:
            marginal[category].update(getattr(result, category))
        combinations[tuple(sorted(result.main_stage))] += 1
    return chunk_index, iterations, marginal, combinations


def _load_base(
    artifact: Path,
) -> tuple[int, dict[str, Counter[str]], Counter[tuple[str, ...]]]:
    value = json.loads(artifact.read_text(encoding="utf-8"))
    iterations = int(value["iterations"])
    marginal = {category: Counter() for category in CATEGORIES}
    for team in value["team_probabilities"]:
        for category in CATEGORIES:
            marginal[category][str(team["key"])] = round(
                float(team[category]) * iterations
            )
    combinations: Counter[tuple[str, ...]] = Counter()
    for row in value["top_main_stage_combinations"]:
        keys = tuple(sorted(str(team["key"]) for team in row["teams"]))
        count = row.get("count")
        if count is None:
            count = round(float(row["probability"]) * iterations)
        combinations[keys] = int(count)
    return iterations, marginal, combinations


def _artifact_payload(
    *,
    completed: int,
    seed: int,
    workers: int,
    chunk_size: int,
    marginal: dict[str, Counter[str]],
    combinations: Counter[tuple[str, ...]],
    teams: list[TeamStrength],
    combination_limit: int | None,
) -> dict[str, object]:
    names = {team.key: team.name for team in teams}
    probabilities = {
        key: {
            category: marginal[category][key] / completed for category in CATEGORIES
        }
        for key in names
    }
    team_order = sorted(
        names, key=lambda key: probabilities[key]["main_stage"], reverse=True
    )
    most_common = combinations.most_common(combination_limit)
    return {
        "iterations": completed,
        "seed": seed,
        "workers": workers,
        "chunk_size": chunk_size,
        "seed_strategy": f"seed + chunk_index * {SEED_STRIDE}",
        "format_assumption": FORMAT_ASSUMPTION,
        "unique_main_stage_combinations_observed": len(combinations),
        "team_probabilities": [
            {"key": key, "name": names[key], **probabilities[key]}
            for key in team_order
        ],
        "top_main_stage_combinations": [
            {
                "rank": rank,
                "count": count,
                "probability": count / completed,
                "teams": [{"key": key, "name": names[key]} for key in combination],
            }
            for rank, (combination, count) in enumerate(most_common, 1)
        ],
    }


def _write_fantasy(
    store: Store,
    road_artifact: Path,
    destination: Path,
    bootstrap_samples: int,
) -> dict[str, object]:
    with store.connect() as connection:
        return write_fantasy_projection(
            connection,
            road_artifact,
            destination,
            PROJECT_ROOT / "data/reference/ti_2026_roster_positions.csv",
            PROJECT_ROOT / "data/reference/ti_2026_participants.csv",
            bootstrap_samples=bootstrap_samples,
        )


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resume the 100M TI Road result to 500M and generate Fantasy projections."
    )
    parser.add_argument("--target-iterations", type=int, default=500_000_000)
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    parser.add_argument("--chunk-size", type=int, default=100_000)
    parser.add_argument("--checkpoint-every", type=int, default=5_000_000)
    parser.add_argument("--progress-every", type=int, default=1_000_000)
    parser.add_argument("--bootstrap-samples", type=int, default=50_000)
    parser.add_argument("--seed", type=int, default=2026)
    return parser.parse_args()


def main() -> None:
    args = _arguments()
    artifacts = PROJECT_ROOT / "artifacts"
    base_artifact = artifacts / "ti_road_simulation_100m_all_combinations.json"
    web_artifact = artifacts / "ti_road_simulation.json"
    full_artifact = artifacts / "ti_road_simulation_500m_all_combinations.json"
    progress_artifact = artifacts / "ti_road_500m_progress.json"
    checkpoint_path = artifacts / ".ti_road_500m_checkpoint.pkl"
    fantasy_artifact = artifacts / "ti_fantasy_projection.json"
    final_fantasy_artifact = artifacts / "ti_fantasy_projection_500m.json"
    store = Store(PROJECT_ROOT / "data/ti_oracle.sqlite3")

    with store.connect() as connection:
        baseline_rows = ti_team_baseline_rows(
            connection, PROJECT_ROOT / "data/reference/ti_2026_participants.csv"
        )
    teams = [
        TeamStrength(
            key=str(row["canonical_team"]),
            name=str(row["display_name"]),
            rating=float(row["glicko_rating"]),
            deviation=float(row["glicko_deviation"]),
        )
        for row in baseline_rows
        if row["glicko_rating"] is not None and row["glicko_deviation"] is not None
    ]
    if len(teams) != 16:
        raise RuntimeError(f"expected 16 rated TI teams, found {len(teams)}")

    if checkpoint_path.exists():
        with checkpoint_path.open("rb") as handle:
            state = pickle.load(handle)
        completed = int(state["completed"])
        marginal = state["marginal"]
        combinations = state["combinations"]
    else:
        completed, marginal, combinations = _load_base(base_artifact)
    if completed > args.target_iterations:
        raise ValueError("checkpoint/base already exceeds target iterations")
    if completed % args.chunk_size:
        raise ValueError("completed iterations must align with the selected chunk size")

    initial_payload = _artifact_payload(
        completed=completed,
        seed=args.seed,
        workers=args.workers,
        chunk_size=args.chunk_size,
        marginal=marginal,
        combinations=combinations,
        teams=teams,
        combination_limit=10,
    )
    _atomic_json(web_artifact, initial_payload)
    fantasy = _write_fantasy(
        store, web_artifact, fantasy_artifact, args.bootstrap_samples
    )
    print(
        json.dumps(
            {
                "status": "starting",
                "completed_iterations": completed,
                "target_iterations": args.target_iterations,
                "fantasy_roles": {
                    role: len(rows)
                    for role, rows in fantasy["role_leaderboards"].items()
                },
            }
        ),
        flush=True,
    )

    started = time.monotonic()
    starting_iterations = completed
    last_checkpoint = completed
    last_progress = completed

    def progress(status: str) -> None:
        elapsed = max(time.monotonic() - started, 1e-9)
        session_completed = completed - starting_iterations
        rate = session_completed / elapsed
        remaining = max(args.target_iterations - completed, 0)
        value = {
            "status": status,
            "completed_iterations": completed,
            "total_iterations": args.target_iterations,
            "percent": completed / args.target_iterations,
            "session_simulations_per_second": rate,
            "session_elapsed_seconds": elapsed,
            "estimated_seconds_remaining": remaining / rate if rate else None,
            "unique_main_stage_combinations_observed": len(combinations),
            "workers": args.workers,
            "fantasy_artifact": str(fantasy_artifact.relative_to(PROJECT_ROOT)),
            "web_artifact": str(web_artifact.relative_to(PROJECT_ROOT)),
            "full_artifact": str(full_artifact.relative_to(PROJECT_ROOT)),
            "updated_at": int(time.time()),
            "updated_at_iso": datetime.now(timezone.utc).isoformat(),
        }
        _atomic_json(progress_artifact, value)
        print(json.dumps(value), flush=True)

    progress("running" if completed < args.target_iterations else "finalizing")
    next_chunk = completed // args.chunk_size
    tasks = []
    pending = args.target_iterations - completed
    while pending:
        size = min(args.chunk_size, pending)
        tasks.append((next_chunk, size, args.seed, teams))
        pending -= size
        next_chunk += 1

    try:
        if tasks:
            context = mp.get_context("spawn")
            with context.Pool(processes=args.workers) as pool:
                for _, iterations, chunk_marginal, chunk_combinations in pool.imap(
                    _simulate_chunk, tasks, chunksize=1
                ):
                    completed += iterations
                    for category in CATEGORIES:
                        marginal[category].update(chunk_marginal[category])
                    combinations.update(chunk_combinations)
                    if completed - last_progress >= args.progress_every:
                        progress("running")
                        last_progress = completed
                    if completed - last_checkpoint >= args.checkpoint_every:
                        _atomic_pickle(
                            checkpoint_path,
                            {
                                "completed": completed,
                                "marginal": marginal,
                                "combinations": combinations,
                            },
                        )
                        partial = _artifact_payload(
                            completed=completed,
                            seed=args.seed,
                            workers=args.workers,
                            chunk_size=args.chunk_size,
                            marginal=marginal,
                            combinations=combinations,
                            teams=teams,
                            combination_limit=10,
                        )
                        _atomic_json(web_artifact, partial)
                        last_checkpoint = completed
    except BaseException:
        _atomic_pickle(
            checkpoint_path,
            {"completed": completed, "marginal": marginal, "combinations": combinations},
        )
        progress("interrupted")
        raise

    web_payload = _artifact_payload(
        completed=completed,
        seed=args.seed,
        workers=args.workers,
        chunk_size=args.chunk_size,
        marginal=marginal,
        combinations=combinations,
        teams=teams,
        combination_limit=10,
    )
    full_payload = _artifact_payload(
        completed=completed,
        seed=args.seed,
        workers=args.workers,
        chunk_size=args.chunk_size,
        marginal=marginal,
        combinations=combinations,
        teams=teams,
        combination_limit=None,
    )
    _atomic_json(web_artifact, web_payload)
    _atomic_json(full_artifact, full_payload)
    fantasy = _write_fantasy(
        store, web_artifact, fantasy_artifact, args.bootstrap_samples
    )
    _atomic_json(final_fantasy_artifact, fantasy)
    progress("complete")


if __name__ == "__main__":
    main()
