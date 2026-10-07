from __future__ import annotations

import csv
import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .glicko2 import GlickoRating, win_probability


@dataclass(frozen=True)
class TeamStrength:
    key: str
    name: str
    rating: float
    deviation: float


@dataclass
class Standing:
    team: TeamStrength
    initial_group: int
    seed: int
    wins: int = 0
    losses: int = 0
    opponents: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RoadResult:
    undefeated: tuple[str, ...]
    four_one: tuple[str, ...]
    elimination_winners: tuple[str, ...]
    elimination_losers: tuple[str, ...]
    one_four: tuple[str, ...]
    winless: tuple[str, ...]
    main_stage: tuple[str, ...]


@dataclass(frozen=True)
class ObservedSeries:
    round_number: int
    first: str
    second: str
    winner: str | None
    first_maps: int = 0
    second_maps: int = 0


def series_probability(map_probability: float, best_of: int = 3) -> float:
    needed = best_of // 2 + 1
    return sum(
        math.comb(best_of, wins)
        * map_probability**wins
        * (1.0 - map_probability) ** (best_of - wins)
        for wins in range(needed, best_of + 1)
    )


def _opponent_wins(standing: Standing, by_key: dict[str, Standing]) -> int:
    return sum(by_key[key].wins for key in standing.opponents)


def _ranking(states: list[Standing]) -> list[Standing]:
    by_key = {standing.team.key: standing for standing in states}
    return sorted(
        states,
        key=lambda standing: (
            standing.wins,
            -standing.losses,
            _opponent_wins(standing, by_key),
            standing.team.rating,
        ),
        reverse=True,
    )


def _valid_relation(first: Standing, second: Standing, round_number: int) -> bool:
    if round_number <= 3:
        return first.initial_group == second.initial_group
    if round_number == 4:
        return first.initial_group != second.initial_group
    return True


def _pair_pool(pool: list[Standing], round_number: int) -> list[tuple[Standing, Standing]]:
    pool_ranking = sorted(pool, key=lambda standing: standing.team.rating, reverse=True)
    rank_index = {standing.team.key: index for index, standing in enumerate(pool_ranking)}

    def solve(remaining: list[Standing]) -> list[tuple[Standing, Standing]] | None:
        if not remaining:
            return []
        first = remaining[0]
        candidates = [
            other
            for other in remaining
            if other is not first and _valid_relation(first, other, round_number)
        ]
        candidates.sort(
            key=lambda other: (
                int(other.team.key in first.opponents),
                abs(rank_index[first.team.key] - rank_index[other.team.key]),
                -other.team.rating,
            )
        )
        for second in candidates:
            leftover = [item for item in remaining if item not in (first, second)]
            solved = solve(leftover)
            if solved is not None:
                return [(first, second), *solved]
        return None

    pairs = solve(pool)
    if pairs is None:
        raise ValueError(f"unable to create valid round-{round_number} Swiss pairings")
    return pairs


def _play(first: Standing, second: Standing, rng: random.Random) -> Standing:
    probability = series_probability(
        win_probability(
            GlickoRating(first.team.rating, first.team.deviation, 0.06),
            GlickoRating(second.team.rating, second.team.deviation, 0.06),
        )
    )
    return first if rng.random() < probability else second


def load_round_one_fixtures(
    path: Path,
) -> tuple[dict[str, int], list[tuple[str, str]]]:
    """Load revealed Round 1 pairings and their inferred initial Swiss pools."""
    group_numbers: dict[str, int] = {}
    initial_groups: dict[str, int] = {}
    pairs: list[tuple[str, str]] = []
    with path.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            group = str(row["group"]).strip().upper()
            if group not in group_numbers:
                group_numbers[group] = len(group_numbers)
            first = str(row["team1"]).strip()
            second = str(row["team2"]).strip()
            if not first or not second or first == second:
                raise ValueError(f"invalid Round 1 fixture in {path}: {first!r}, {second!r}")
            pairs.append((first, second))
            for key in (first, second):
                if key in initial_groups:
                    raise ValueError(f"Round 1 fixture repeats {key!r} in {path}")
                initial_groups[key] = group_numbers[group]
    return initial_groups, pairs


def load_observed_series(path: Path) -> list[ObservedSeries]:
    observed: list[ObservedSeries] = []
    with path.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            first = str(row["team1"]).strip()
            second = str(row["team2"]).strip()
            winner = str(row["winner"]).strip()
            status = str(row.get("status") or "complete").strip().lower()
            if status == "complete" and winner not in (first, second):
                raise ValueError(f"observed winner {winner!r} is not in {first!r} vs {second!r}")
            if status not in ("complete", "live", "scheduled"):
                raise ValueError(f"unknown observed-series status {status!r}")
            observed.append(
                ObservedSeries(
                    int(row["round"]),
                    first,
                    second,
                    winner or None,
                    int(row.get("team1_maps") or 0),
                    int(row.get("team2_maps") or 0),
                )
            )
    return observed


def _play_pending(series: ObservedSeries, first: Standing, second: Standing, rng: random.Random) -> Standing:
    map_probability = win_probability(
        GlickoRating(first.team.rating, first.team.deviation, 0.06),
        GlickoRating(second.team.rating, second.team.deviation, 0.06),
    )
    first_needed = max(0, 2 - series.first_maps)
    second_needed = max(0, 2 - series.second_maps)
    if first_needed == 0:
        return first
    if second_needed == 0:
        return second
    if (first_needed, second_needed) == (1, 1):
        probability = map_probability
    elif (first_needed, second_needed) == (1, 2):
        probability = 1.0 - (1.0 - map_probability) ** 2
    elif (first_needed, second_needed) == (2, 1):
        probability = map_probability**2
    else:
        probability = series_probability(map_probability)
    return first if rng.random() < probability else second


def _validate_revealed_format(
    teams: list[TeamStrength],
    initial_groups: dict[str, int] | None,
    round_one_pairs: list[tuple[str, str]] | None,
) -> None:
    keys = {team.key for team in teams}
    if initial_groups is not None:
        if set(initial_groups) != keys:
            missing = sorted(keys - set(initial_groups))
            extra = sorted(set(initial_groups) - keys)
            raise ValueError(f"initial groups do not match teams; missing={missing}, extra={extra}")
        sizes = Counter(initial_groups.values())
        if sorted(sizes.values()) != [8, 8]:
            raise ValueError(f"initial groups must contain two groups of eight: {dict(sizes)}")
    if round_one_pairs is not None:
        paired = [key for pair in round_one_pairs for key in pair]
        if len(round_one_pairs) != 8 or len(set(paired)) != 16 or set(paired) != keys:
            raise ValueError("Round 1 fixtures must pair all 16 teams exactly once")
        if initial_groups is not None and any(
            initial_groups[first] != initial_groups[second]
            for first, second in round_one_pairs
        ):
            raise ValueError("each Round 1 fixture must stay within one initial group")


def simulate_road_once(
    teams: list[TeamStrength],
    rng: random.Random,
    *,
    initial_groups: dict[str, int] | None = None,
    round_one_pairs: list[tuple[str, str]] | None = None,
    observed_series: list[ObservedSeries] | None = None,
) -> RoadResult:
    if len(teams) != 16:
        raise ValueError("the TI Road simulator requires exactly 16 teams")
    _validate_revealed_format(teams, initial_groups, round_one_pairs)
    seeded = sorted(teams, key=lambda team: team.rating, reverse=True)
    states = [
        Standing(
            team=team,
            initial_group=(
                initial_groups[team.key] if initial_groups is not None else index % 2
            ),
            seed=index + 1,
        )
        for index, team in enumerate(seeded)
    ]
    by_key = {state.team.key: state for state in states}
    completed_rounds = 0
    if observed_series:
        seen: set[tuple[int, str]] = set()
        for series in observed_series:
            if series.first not in by_key or series.second not in by_key:
                raise ValueError(f"observed series contains an unknown team: {series}")
            if series.first == series.second:
                raise ValueError(f"observed series repeats the same team: {series}")
            first = by_key[series.first]
            second = by_key[series.second]
            if not _valid_relation(first, second, series.round_number):
                raise ValueError(f"observed series violates round relation: {series}")
            for key in (series.first, series.second):
                marker = (series.round_number, key)
                if marker in seen:
                    raise ValueError(f"team {key!r} appears twice in round {series.round_number}")
                seen.add(marker)
            winner = (
                by_key[series.winner]
                if series.winner is not None
                else _play_pending(series, first, second, rng)
            )
            loser = second if winner is first else first
            winner.wins += 1
            loser.losses += 1
            first.opponents.append(second.team.key)
            second.opponents.append(first.team.key)
        games_played = {state.wins + state.losses for state in states}
        if len(games_played) != 1:
            raise ValueError(
                "observed results must contain complete rounds for all teams; "
                f"games played={sorted(games_played)}"
            )
        completed_rounds = games_played.pop()
        if completed_rounds > 5:
            raise ValueError("observed results exceed the five Swiss rounds")

    for round_number in range(completed_rounds + 1, 6):
        active = [state for state in states if state.wins < 4 and state.losses < 4]
        if round_number == 1 and round_one_pairs is not None:
            pairs = [(by_key[first], by_key[second]) for first, second in round_one_pairs]
        else:
            pools: dict[tuple[int, int], list[Standing]] = defaultdict(list)
            for state in active:
                pools[(state.wins, state.losses)].append(state)
            pairs = [
                pair
                for pool in pools.values()
                for pair in _pair_pool(pool, round_number)
            ]
        for first, second in pairs:
            winner = _play(first, second, rng)
            loser = second if winner is first else first
            winner.wins += 1
            loser.losses += 1
            first.opponents.append(second.team.key)
            second.opponents.append(first.team.key)

    ranked = _ranking(states)
    four_zero = [state for state in ranked if (state.wins, state.losses) == (4, 0)]
    four_one = [state for state in ranked if (state.wins, state.losses) == (4, 1)]
    three_two = [state for state in ranked if (state.wins, state.losses) == (3, 2)]
    two_three = [state for state in reversed(ranked) if (state.wins, state.losses) == (2, 3)]
    one_four = [state for state in ranked if (state.wins, state.losses) == (1, 4)]
    zero_four = [state for state in ranked if (state.wins, state.losses) == (0, 4)]
    sizes = tuple(map(len, (four_zero, four_one, three_two, two_three, one_four, zero_four)))
    if sizes != (1, 2, 5, 5, 2, 1):
        raise AssertionError(f"unexpected Swiss record distribution: {sizes}")

    elimination_winners: list[Standing] = []
    elimination_losers: list[Standing] = []
    for high, low in zip(three_two, two_three, strict=True):
        winner = _play(high, low, rng)
        loser = low if winner is high else high
        elimination_winners.append(winner)
        elimination_losers.append(loser)
    final_rank = {state.team.key: index for index, state in enumerate(ranked)}
    elimination_winners.sort(key=lambda state: final_rank[state.team.key])
    elimination_losers.sort(key=lambda state: final_rank[state.team.key])
    main = sorted(
        [*four_zero, *four_one, *elimination_winners],
        key=lambda state: final_rank[state.team.key],
    )
    keys = lambda values: tuple(value.team.key for value in values)
    return RoadResult(
        undefeated=keys(four_zero),
        four_one=keys(four_one),
        elimination_winners=keys(elimination_winners),
        elimination_losers=keys(elimination_losers),
        one_four=keys(one_four),
        winless=keys(zero_four),
        main_stage=keys(main),
    )


def simulate_road(
    teams: list[TeamStrength],
    iterations: int = 20_000,
    seed: int = 2026,
    top: int = 10,
    *,
    initial_groups: dict[str, int] | None = None,
    round_one_pairs: list[tuple[str, str]] | None = None,
    observed_series: list[ObservedSeries] | None = None,
) -> dict[str, object]:
    if iterations < 1:
        raise ValueError("iterations must be positive")
    rng = random.Random(seed)
    categories = [
        "undefeated",
        "four_one",
        "elimination_winners",
        "elimination_losers",
        "one_four",
        "winless",
        "main_stage",
    ]
    marginal: dict[str, Counter[str]] = {category: Counter() for category in categories}
    combinations: Counter[tuple[str, ...]] = Counter()
    for _ in range(iterations):
        result = simulate_road_once(
            teams,
            rng,
            initial_groups=initial_groups,
            round_one_pairs=round_one_pairs,
            observed_series=observed_series,
        )
        for category in categories:
            marginal[category].update(getattr(result, category))
        combinations[tuple(sorted(result.main_stage))] += 1
    names = {team.key: team.name for team in teams}
    probabilities = {
        key: {
            category: marginal[category][key] / iterations for category in categories
        }
        for key in names
    }
    ordered_teams = sorted(
        probabilities,
        key=lambda key: probabilities[key]["main_stage"],
        reverse=True,
    )
    return {
        "iterations": iterations,
        "seed": seed,
        "format_assumption": (
            "five Swiss rounds; rounds 1-3 within initial groups, round 4 cross-group, "
            "round 5 open; 4-0/4-1 qualify, 3-2 plays 2-3; "
            + (
                f"{len(observed_series)} completed series fixed as observed"
                if observed_series
                else (
                    "revealed Round 1 fixtures applied"
                    if round_one_pairs is not None
                    else "Round 1 generated from rating seeds"
                )
            )
        ),
        "team_probabilities": [
            {"key": key, "name": names[key], **probabilities[key]} for key in ordered_teams
        ],
        "top_main_stage_combinations": [
            {
                "rank": index + 1,
                "probability": count / iterations,
                "teams": [{"key": key, "name": names[key]} for key in combination],
            }
            for index, (combination, count) in enumerate(combinations.most_common(top))
        ],
    }
