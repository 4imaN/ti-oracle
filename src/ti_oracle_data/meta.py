from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass


RANK_NAMES = {
    1: "Herald",
    2: "Guardian",
    3: "Crusader",
    4: "Archon",
    5: "Legend",
    6: "Ancient",
    7: "Divine",
    8: "Immortal",
}


@dataclass(frozen=True)
class BayesianRate:
    mean: float
    lower_95: float
    upper_95: float


def beta_binomial_rate(
    wins: int,
    games: int,
    prior_mean: float,
    prior_games: float,
) -> BayesianRate:
    if games < 0 or wins < 0 or wins > games:
        raise ValueError("wins and games must describe a valid binomial sample")
    alpha = wins + prior_mean * prior_games
    beta = games - wins + (1.0 - prior_mean) * prior_games
    total = alpha + beta
    mean = alpha / total
    variance = alpha * beta / (total * total * (total + 1.0))
    margin = 1.96 * math.sqrt(variance)
    return BayesianRate(mean, max(0.0, mean - margin), min(1.0, mean + margin))


def rank_hero_meta(
    connection: sqlite3.Connection,
    bracket: int,
    limit: int = 15,
    minimum_picks: int = 100,
) -> list[dict[str, object]]:
    collected_at = connection.execute(
        "SELECT MAX(collected_at) FROM hero_meta_snapshots"
    ).fetchone()[0]
    if collected_at is None:
        return []
    totals = connection.execute(
        "SELECT SUM(picks), SUM(wins) FROM hero_meta_snapshots WHERE collected_at=? AND bracket=?",
        (collected_at, bracket),
    ).fetchone()
    total_games = int(totals[0] or 0)
    total_wins = int(totals[1] or 0)
    if total_games == 0:
        return []
    prior_mean = total_wins / total_games
    rows = connection.execute(
        """
        SELECT s.hero_id, h.localized_name, s.picks, s.wins
        FROM hero_meta_snapshots s
        JOIN heroes h ON h.hero_id = s.hero_id
        WHERE s.collected_at=? AND s.bracket=? AND s.picks>=?
        """,
        (collected_at, bracket, minimum_picks),
    )
    output: list[dict[str, object]] = []
    for row in rows:
        estimate = beta_binomial_rate(
            int(row["wins"]), int(row["picks"]), prior_mean, 500.0
        )
        output.append(
            {
                "hero_id": int(row["hero_id"]),
                "hero": row["localized_name"],
                "picks": int(row["picks"]),
                "wins": int(row["wins"]),
                "raw_rate": int(row["wins"]) / int(row["picks"]),
                "posterior_rate": estimate.mean,
                "lower_95": estimate.lower_95,
                "upper_95": estimate.upper_95,
                "popularity_share": int(row["picks"]) / total_games,
                "collected_at": int(collected_at),
            }
        )
    return sorted(
        output,
        key=lambda item: (float(item["lower_95"]), int(item["picks"])),
        reverse=True,
    )[:limit]
