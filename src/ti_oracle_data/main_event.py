from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass

from .glicko2 import GlickoRating, win_probability
from .simulation import series_probability


@dataclass(frozen=True)
class MainEventTeam:
    key: str
    name: str
    glicko_rating: float
    glicko_deviation: float
    ti_map_wins: int
    ti_map_losses: int


@dataclass(frozen=True)
class SeriesResult:
    winner: str
    loser: str


def event_form_rating(team: MainEventTeam, center: float) -> float:
    """Convert TI map form to a conservative, beta-smoothed Elo-like rating."""
    odds = (team.ti_map_wins + 2.0) / (team.ti_map_losses + 2.0)
    return center + 400.0 * math.log10(odds)


def effective_ratings(
    teams: list[MainEventTeam], season_weight: float = 0.60
) -> dict[str, float]:
    if not 0.0 <= season_weight <= 1.0:
        raise ValueError("season_weight must be between zero and one")
    center = sum(team.glicko_rating for team in teams) / len(teams)
    return {
        team.key: (
            season_weight * team.glicko_rating
            + (1.0 - season_weight) * event_form_rating(team, center)
        )
        for team in teams
    }


def _probability_tables(
    teams: list[MainEventTeam], ratings: dict[str, float]
) -> tuple[dict[tuple[str, str], float], dict[tuple[str, str], float]]:
    by_key = {team.key: team for team in teams}
    bo3: dict[tuple[str, str], float] = {}
    bo5: dict[tuple[str, str], float] = {}
    for first in teams:
        for second in teams:
            if first.key == second.key:
                continue
            map_probability = win_probability(
                GlickoRating(ratings[first.key], first.glicko_deviation, 0.06),
                GlickoRating(ratings[second.key], second.glicko_deviation, 0.06),
            )
            bo3[first.key, second.key] = series_probability(map_probability, 3)
            bo5[first.key, second.key] = series_probability(map_probability, 5)
    return bo3, bo5


def _play(
    first: str,
    second: str,
    probabilities: dict[tuple[str, str], float],
    rng: random.Random,
) -> SeriesResult:
    if rng.random() < probabilities[first, second]:
        return SeriesResult(first, second)
    return SeriesResult(second, first)


def _favorite(
    first: str,
    second: str,
    probabilities: dict[tuple[str, str], float],
) -> SeriesResult:
    return (
        SeriesResult(first, second)
        if probabilities[first, second] >= 0.5
        else SeriesResult(second, first)
    )


def simulate_main_event(
    teams: list[MainEventTeam],
    upper_quarterfinals: list[tuple[str, str]],
    *,
    iterations: int = 1_000_000,
    seed: int = 20260817,
    season_weight: float = 0.60,
) -> dict[str, object]:
    """Simulate the revealed eight-team TI double-elimination bracket.

    The first two quarterfinals form one upper-bracket half and the final two
    form the other. Lower round two crosses the upper-semifinal losers to avoid
    an immediate rematch. Every series is Bo3 except the Bo5 grand final.
    """
    if iterations < 1:
        raise ValueError("iterations must be positive")
    keys = {team.key for team in teams}
    paired = [key for pair in upper_quarterfinals for key in pair]
    if len(teams) != 8 or len(upper_quarterfinals) != 4:
        raise ValueError("main event requires eight teams and four quarterfinals")
    if len(set(paired)) != 8 or set(paired) != keys:
        raise ValueError("quarterfinals must contain every team exactly once")

    names = {team.key: team.name for team in teams}
    ratings = effective_ratings(teams, season_weight)
    bo3, bo5 = _probability_tables(teams, ratings)
    rng = random.Random(seed)

    finishes: dict[str, Counter[str]] = {key: Counter() for key in keys}
    stage_reached: dict[str, Counter[str]] = {key: Counter() for key in keys}
    series_totals: Counter[str] = Counter()
    node_matchups: dict[str, Counter[tuple[str, str]]] = defaultdict(Counter)
    node_winners: dict[str, Counter[str]] = defaultdict(Counter)
    final_pairings: Counter[tuple[str, str]] = Counter()

    def play_node(node: str, first: str, second: str, *, final: bool = False) -> SeriesResult:
        ordered = tuple(sorted((first, second)))
        node_matchups[node][ordered] += 1
        result = _play(first, second, bo5 if final else bo3, rng)
        node_winners[node][result.winner] += 1
        series_totals[first] += 1
        series_totals[second] += 1
        return result

    for _ in range(iterations):
        qf = [
            play_node(f"upper_quarterfinal_{index + 1}", first, second)
            for index, (first, second) in enumerate(upper_quarterfinals)
        ]
        for result in qf:
            stage_reached[result.winner]["upper_semifinal"] += 1

        ub_sf1 = play_node("upper_semifinal_1", qf[0].winner, qf[1].winner)
        ub_sf2 = play_node("upper_semifinal_2", qf[2].winner, qf[3].winner)
        stage_reached[ub_sf1.winner]["upper_final"] += 1
        stage_reached[ub_sf2.winner]["upper_final"] += 1

        lb1a = play_node("lower_round_1a", qf[0].loser, qf[1].loser)
        lb1b = play_node("lower_round_1b", qf[2].loser, qf[3].loser)
        finishes[lb1a.loser]["7-8"] += 1
        finishes[lb1b.loser]["7-8"] += 1

        lb2a = play_node("lower_round_2a", lb1a.winner, ub_sf2.loser)
        lb2b = play_node("lower_round_2b", lb1b.winner, ub_sf1.loser)
        finishes[lb2a.loser]["5-6"] += 1
        finishes[lb2b.loser]["5-6"] += 1

        ub_final = play_node("upper_final", ub_sf1.winner, ub_sf2.winner)
        stage_reached[ub_final.winner]["grand_final"] += 1

        lb3 = play_node("lower_round_3", lb2a.winner, lb2b.winner)
        finishes[lb3.loser]["4"] += 1
        stage_reached[lb3.winner]["lower_final"] += 1

        lb_final = play_node("lower_final", lb3.winner, ub_final.loser)
        finishes[lb_final.loser]["3"] += 1
        stage_reached[lb_final.winner]["grand_final"] += 1

        final = play_node("grand_final", ub_final.winner, lb_final.winner, final=True)
        final_pairings[tuple(sorted((ub_final.winner, lb_final.winner)))] += 1
        finishes[final.winner]["1"] += 1
        finishes[final.loser]["2"] += 1

    # Produce the single most probable branch to copy into the Dota client.
    def favorite_node(node: str, first: str, second: str, *, final: bool = False) -> SeriesResult:
        result = _favorite(first, second, bo5 if final else bo3)
        recommended.append({
            "node": node,
            "first": names[first],
            "second": names[second],
            "winner": names[result.winner],
            "winner_probability": max(
                (bo5 if final else bo3)[first, second],
                (bo5 if final else bo3)[second, first],
            ),
        })
        return result

    recommended: list[dict[str, object]] = []
    fqf = [
        favorite_node(f"upper_quarterfinal_{index + 1}", first, second)
        for index, (first, second) in enumerate(upper_quarterfinals)
    ]
    fubsf1 = favorite_node("upper_semifinal_1", fqf[0].winner, fqf[1].winner)
    fubsf2 = favorite_node("upper_semifinal_2", fqf[2].winner, fqf[3].winner)
    flb1a = favorite_node("lower_round_1a", fqf[0].loser, fqf[1].loser)
    flb1b = favorite_node("lower_round_1b", fqf[2].loser, fqf[3].loser)
    flb2a = favorite_node("lower_round_2a", flb1a.winner, fubsf2.loser)
    flb2b = favorite_node("lower_round_2b", flb1b.winner, fubsf1.loser)
    fubf = favorite_node("upper_final", fubsf1.winner, fubsf2.winner)
    flb3 = favorite_node("lower_round_3", flb2a.winner, flb2b.winner)
    flbf = favorite_node("lower_final", flb3.winner, fubf.loser)
    favorite_node("grand_final", fubf.winner, flbf.winner, final=True)

    team_rows = []
    for team in teams:
        finish = finishes[team.key]
        team_rows.append({
            "key": team.key,
            "name": team.name,
            "glicko_rating": team.glicko_rating,
            "glicko_deviation": team.glicko_deviation,
            "ti_map_record": f"{team.ti_map_wins}-{team.ti_map_losses}",
            "event_form_rating": event_form_rating(
                team, sum(item.glicko_rating for item in teams) / len(teams)
            ),
            "effective_rating": ratings[team.key],
            "champion": finish["1"] / iterations,
            "runner_up": finish["2"] / iterations,
            "third": finish["3"] / iterations,
            "fourth": finish["4"] / iterations,
            "fifth_sixth": finish["5-6"] / iterations,
            "seventh_eighth": finish["7-8"] / iterations,
            "grand_final": stage_reached[team.key]["grand_final"] / iterations,
            "upper_final": stage_reached[team.key]["upper_final"] / iterations,
            "average_series": series_totals[team.key] / iterations,
        })
    team_rows.sort(key=lambda row: float(row["champion"]), reverse=True)

    opening = []
    for index, (first, second) in enumerate(upper_quarterfinals, start=1):
        opening.append({
            "node": f"upper_quarterfinal_{index}",
            "first": names[first],
            "second": names[second],
            "first_win_probability": bo3[first, second],
            "second_win_probability": bo3[second, first],
        })

    return {
        "iterations": iterations,
        "seed": seed,
        "model": {
            "season_glicko_weight": season_weight,
            "current_ti_form_weight": 1.0 - season_weight,
            "ti_form_prior": "Beta(2, 2) on map wins",
            "series_format": "Bo3 except Bo5 grand final",
            "bracket": "eight-team double elimination; lower round two crosses upper-semifinal losers",
        },
        "opening_match_probabilities": opening,
        "recommended_bracket": recommended,
        "team_probabilities": team_rows,
        "top_grand_final_matchups": [
            {
                "teams": [names[first], names[second]],
                "probability": count / iterations,
            }
            for (first, second), count in final_pairings.most_common(10)
        ],
        "node_most_likely_matchups": {
            node: [
                {
                    "teams": [names[first], names[second]],
                    "probability": count / iterations,
                }
                for (first, second), count in matchups.most_common(3)
            ]
            for node, matchups in node_matchups.items()
        },
    }
