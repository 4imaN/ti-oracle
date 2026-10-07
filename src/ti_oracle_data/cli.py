from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
import sys
import time
import re
from pathlib import Path

from .config import Settings
from .http import DataSourceError, JsonHttpClient
from .opendota import OpenDotaClient
from .ratings import load_team_aliases, rebuild_elo
from .rosters import rebuild_roster_observations
from .reports import ti_team_baseline_rows
from .events import rebuild_ti_event_matches
from .glicko_timeline import rebuild_glicko_timeline
from .meta import RANK_NAMES, rank_hero_meta
from .store import Store
from .fantasy import rebuild_fantasy_stats
from .player_ratings import rebuild_player_ratings
from .draft import rebuild_draft_stats


def parse_date(value: str) -> int:
    parsed = dt.datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=dt.UTC)
    return int(parsed.timestamp())


def build_client(settings: Settings) -> OpenDotaClient:
    return OpenDotaClient(
        JsonHttpClient(
            "https://api.opendota.com/api",
            timeout_seconds=settings.request_timeout_seconds,
            delay_seconds=settings.request_delay_seconds,
        ),
        api_key=settings.opendota_api_key,
    )


def init_db(store: Store) -> None:
    store.initialize()
    print(f"initialized {store.path}")


def sync_static(store: Store, client: OpenDotaClient) -> None:
    store.initialize()
    collected_at = int(time.time())
    with store.run("opendota", "static") as (connection, run_id):
        rows = 0
        for hero in client.hero_stats():
            rows += Store.upsert_hero_snapshot(connection, hero, collected_at)
        for player in client.pro_players():
            Store.upsert_player(connection, player)
            rows += 1
        for team in client.teams():
            Store.upsert_team(connection, team)
            rows += 1
        for league in client.leagues():
            Store.upsert_league(connection, league)
            rows += 1
        for patch in client.patches():
            Store.upsert_patch(connection, int(patch["id"]), patch)
            rows += 1
        Store.add_run_rows(connection, run_id, rows)
        connection.commit()
    print(f"wrote {rows} static/snapshot rows")


def sync_ti_history(
    store: Store, client: OpenDotaClient, first_year: int, last_year: int
) -> None:
    store.initialize()
    exact = re.compile(r"^The International (\d{4})$", re.IGNORECASE)
    selected: list[tuple[int, int, str]] = []
    for league in client.leagues():
        match = exact.match(league.get("name") or "")
        if not match:
            continue
        year = int(match.group(1))
        if first_year <= year <= last_year:
            league_id = int(league.get("leagueid") or league.get("league_id"))
            selected.append((year, league_id, league["name"]))

    written = 0
    with store.run("opendota", "ti_history_index") as (connection, run_id):
        for year, league_id, name in sorted(selected):
            matches = client.league_matches(league_id)
            for match in matches:
                if not match.get("league_name"):
                    match["league_name"] = name
                Store.upsert_pro_match(connection, match)
            Store.add_run_rows(connection, run_id, len(matches))
            connection.commit()
            written += len(matches)
            print(f"year={year} league={league_id} matches={len(matches)}")
    print(f"indexed {written} TI matches from {first_year} through {last_year}")


def build_elo(store: Store, since_epoch: int, participants_path: str | None) -> None:
    store.initialize()
    aliases = load_team_aliases(Path(participants_path)) if participants_path else {}
    with store.connect() as connection:
        written = rebuild_elo(connection, since_epoch, aliases)
        connection.commit()
        teams = connection.execute(
            "SELECT COUNT(DISTINCT team_id) FROM team_rating_history"
        ).fetchone()[0]
    print(f"wrote {written} rating transitions for {teams} teams")


def build_rosters(store: Store) -> None:
    store.initialize()
    with store.connect() as connection:
        written = rebuild_roster_observations(connection)
        connection.commit()
        lineups = connection.execute(
            "SELECT COUNT(DISTINCT lineup_key) FROM team_roster_observations"
        ).fetchone()[0]
    print(f"wrote {written} roster observations across {lineups} unique lineups")


def report_ti_teams(store: Store, participants_path: str) -> None:
    store.initialize()
    with store.connect() as connection:
        rows = ti_team_baseline_rows(connection, Path(participants_path))
    print(
        f"{'rank':>4}  {'team':<20} {'glicko':>7} {'rd':>6} {'elo':>7} "
        f"{'games':>6} {'source id':>10}"
    )
    for rank, row in enumerate(rows, start=1):
        rating = f"{row['rating']:.1f}" if row["rating"] is not None else "n/a"
        glicko = (
            f"{row['glicko_rating']:.1f}" if row["glicko_rating"] is not None else "n/a"
        )
        deviation = (
            f"{row['glicko_deviation']:.1f}"
            if row["glicko_deviation"] is not None
            else "n/a"
        )
        print(
            f"{rank:>4}  {str(row['display_name']):<20} {glicko:>7} {deviation:>6} "
            f"{rating:>7} {int(row['games']):>6} "
            f"{str(row['active_source_team_id'] or '-'):>10}"
        )


def build_ti_events(store: Store, events_path: str) -> None:
    store.initialize()
    with store.connect() as connection:
        written = rebuild_ti_event_matches(connection, Path(events_path))
        connection.commit()
        venue = connection.execute(
            "SELECT COUNT(*) FROM ti_event_matches WHERE is_venue_stage=1"
        ).fetchone()[0]
    print(f"classified {written} TI-league matches; {venue} fall within venue-stage dates")


def build_glicko(store: Store, since_epoch: int, participants_path: str | None) -> None:
    store.initialize()
    aliases = load_team_aliases(Path(participants_path)) if participants_path else {}
    with store.connect() as connection:
        written = rebuild_glicko_timeline(connection, since_epoch, aliases)
        connection.commit()
        teams = connection.execute(
            "SELECT COUNT(DISTINCT team_id) FROM team_glicko_history"
        ).fetchone()[0]
    print(f"wrote {written} daily Glicko-2 transitions for {teams} teams")


def report_hero_meta(store: Store, bracket: int, limit: int, minimum_picks: int) -> None:
    store.initialize()
    with store.connect() as connection:
        rows = rank_hero_meta(connection, bracket, limit, minimum_picks)
    rank_name = RANK_NAMES.get(bracket, f"Bracket {bracket}")
    print(f"{rank_name} Bayesian hero ranking (latest collected snapshot)")
    print(f"{'rank':>4}  {'hero':<22} {'picks':>9} {'win':>8} {'95% interval':>17}")
    for index, row in enumerate(rows, start=1):
        interval = f"{100*float(row['lower_95']):.1f}-{100*float(row['upper_95']):.1f}%"
        print(
            f"{index:>4}  {str(row['hero']):<22} {int(row['picks']):>9} "
            f"{100*float(row['posterior_rate']):>7.2f}% {interval:>17}"
        )


def train_match_baseline(store: Store, cutoff_epoch: int, artifact_path: str) -> None:
    from .model_baseline import train_chronological_baseline

    store.initialize()
    with store.connect() as connection:
        artifact = train_chronological_baseline(
            connection, cutoff_epoch, Path(artifact_path)
        )
    print(json.dumps({
        "artifact": artifact_path,
        "train_metrics": artifact["train_metrics"],
        "test_metrics": artifact["test_metrics"],
        "elo_test_metrics": artifact["elo_test_metrics"],
    }, indent=2))


def train_match_boosted(store: Store, cutoff_epoch: int, artifact_path: str) -> None:
    from .model_boosted import train_chronological_boosted

    store.initialize()
    with store.connect() as connection:
        artifact = train_chronological_boosted(
            connection, cutoff_epoch, Path(artifact_path)
        )
    print(json.dumps({
        "artifact": artifact_path,
        "test_metrics": artifact["test_metrics"],
        "elo_test_metrics": artifact["elo_test_metrics"],
        "log_loss_delta_vs_elo": artifact["log_loss_delta_vs_elo"],
        "log_loss_delta_95_interval": artifact["log_loss_delta_95_interval"],
        "promoted": artifact["promoted"],
    }, indent=2))


def train_match_roster(store: Store, cutoff_epoch: int, artifact_path: str) -> None:
    from .model_roster import train_chronological_roster_model

    store.initialize()
    with store.connect() as connection:
        artifact = train_chronological_roster_model(
            connection, cutoff_epoch, Path(artifact_path)
        )
    print(json.dumps({
        "artifact": artifact_path,
        "selected_c": artifact["selected_c"],
        "test_metrics": artifact["test_metrics"],
        "elo_test_metrics": artifact["elo_test_metrics"],
        "log_loss_delta_vs_elo": artifact["log_loss_delta_vs_elo"],
        "log_loss_delta_95_interval": artifact["log_loss_delta_95_interval"],
        "provisional_improvement": artifact["provisional_improvement"],
        "promoted": artifact["promoted"],
    }, indent=2))


def build_fantasy_stats(store: Store) -> None:
    store.initialize()
    with store.connect() as connection:
        player_rows, match_rows = rebuild_fantasy_stats(connection)
        connection.commit()
    print(f"wrote {player_rows} Fantasy player rows and {match_rows} title-event rows")


def build_player_ratings(store: Store, participants_path: str | None) -> None:
    store.initialize()
    aliases = load_team_aliases(Path(participants_path)) if participants_path else {}
    with store.connect() as connection:
        player_rows, map_rows = rebuild_player_ratings(connection, aliases)
        connection.commit()
    print(f"wrote {player_rows} player-rating transitions and {map_rows} roster map features")


def simulate_ti_road(
    store: Store,
    participants_path: str,
    fixtures_path: str | None,
    observed_results_path: str | None,
    iterations: int,
    seed: int,
    top: int,
    artifact_path: str,
) -> None:
    from .simulation import (
        TeamStrength,
        load_observed_series,
        load_round_one_fixtures,
        simulate_road,
    )

    store.initialize()
    with store.connect() as connection:
        rows = ti_team_baseline_rows(connection, Path(participants_path))
    teams = [
        TeamStrength(
            key=str(row["canonical_team"]),
            name=str(row["display_name"]),
            rating=float(row["glicko_rating"]),
            deviation=float(row["glicko_deviation"]),
        )
        for row in rows
        if row["glicko_rating"] is not None and row["glicko_deviation"] is not None
    ]
    initial_groups = None
    round_one_pairs = None
    if fixtures_path:
        initial_groups, round_one_pairs = load_round_one_fixtures(Path(fixtures_path))
    observed_series = (
        load_observed_series(Path(observed_results_path))
        if observed_results_path
        else None
    )
    result = simulate_road(
        teams,
        iterations=iterations,
        seed=seed,
        top=top,
        initial_groups=initial_groups,
        round_one_pairs=round_one_pairs,
        observed_series=observed_series,
    )
    destination = Path(artifact_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "artifact": artifact_path,
        "iterations": iterations,
        "top_main_stage_probabilities": [
            {"team": row["name"], "probability": row["main_stage"]}
            for row in result["team_probabilities"][:8]
        ],
    }, indent=2))


def build_draft_stats(store: Store, participants_path: str | None) -> None:
    store.initialize()
    aliases = load_team_aliases(Path(participants_path)) if participants_path else {}
    with store.connect() as connection:
        matchup_rows, synergy_rows, team_rows = rebuild_draft_stats(connection, aliases)
        connection.commit()
    print(
        f"wrote {matchup_rows} hero matchups, {synergy_rows} synergies, "
        f"and {team_rows} team-hero rows"
    )


def sync_pro_index(store: Store, client: OpenDotaClient, since_epoch: int) -> None:
    store.initialize()
    written = 0
    with store.run("opendota", "pro_match_index") as (connection, run_id):
        for page_number, page in enumerate(client.pro_match_pages(since_epoch), start=1):
            in_range = [m for m in page if int(m.get("start_time") or 0) >= since_epoch]
            for match in in_range:
                Store.upsert_pro_match(connection, match)
            written += len(in_range)
            Store.add_run_rows(connection, run_id, len(in_range))
            connection.commit()
            oldest = min(int(m.get("start_time") or 0) for m in page)
            oldest_date = dt.datetime.fromtimestamp(oldest, tz=dt.UTC).date()
            print(f"page={page_number} written={written} oldest={oldest_date}")
    print(f"indexed {written} professional matches")


def enrich_matches(
    store: Store,
    client: OpenDotaClient,
    since_epoch: int,
    limit: int | None,
    league_ids: list[int] | None,
    team_ids: list[int] | None,
    oldest_first: bool,
) -> None:
    store.initialize()
    with store.connect() as connection:
        query = "SELECT match_id FROM pro_matches WHERE start_time>=? AND detailed=0"
        params: list[int] = [since_epoch]
        if league_ids:
            placeholders = ",".join("?" for _ in league_ids)
            query += f" AND league_id IN ({placeholders})"
            params.extend(league_ids)
        if team_ids:
            placeholders = ",".join("?" for _ in team_ids)
            query += (
                f" AND (radiant_team_id IN ({placeholders})"
                f" OR dire_team_id IN ({placeholders}))"
            )
            params.extend(team_ids)
            params.extend(team_ids)
        query += " ORDER BY start_time " + ("ASC" if oldest_first else "DESC")
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        match_ids = [int(row[0]) for row in connection.execute(query, params)]

    written = 0
    with store.run("opendota", "match_details") as (connection, run_id):
        for match_id in match_ids:
            detail = client.match(match_id)
            Store.upsert_match_detail(connection, detail)
            Store.add_run_rows(connection, run_id, 1)
            connection.commit()
            written += 1
            print(f"enriched {written}/{len(match_ids)} match={match_id}")
    print(f"enriched {written} professional matches")


def show_status(store: Store) -> None:
    store.initialize()
    with store.connect() as connection:
        tables = [
            "heroes", "players", "teams", "leagues", "patches", "pro_matches", "match_players",
            "picks_bans", "team_rating_history",
            "map_rating_features", "team_roster_observations", "ti_event_matches",
            "team_glicko_history", "map_glicko_features",
            "fantasy_player_stats", "fantasy_match_events",
            "player_rating_history", "map_roster_features",
            "hero_matchup_stats", "hero_synergy_stats", "team_hero_stats",
        ]
        for table in tables:
            count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"{table}: {count}")
        detailed = connection.execute(
            "SELECT COUNT(*) FROM pro_matches WHERE detailed=1"
        ).fetchone()[0]
        print(f"detailed_matches: {detailed}")
        bounds = connection.execute(
            "SELECT MIN(start_time), MAX(start_time) FROM pro_matches"
        ).fetchone()
        if bounds[0]:
            print(
                "match_range:",
                dt.datetime.fromtimestamp(bounds[0], tz=dt.UTC).isoformat(),
                "to",
                dt.datetime.fromtimestamp(bounds[1], tz=dt.UTC).isoformat(),
            )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="ti-data")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("init-db")
    commands.add_parser("sync-static")

    index = commands.add_parser("sync-pro-index")
    index.add_argument("--since", default="2026-01-01", type=parse_date)

    enrich = commands.add_parser("enrich-matches")
    enrich.add_argument("--since", default="2026-01-01", type=parse_date)
    enrich.add_argument("--limit", type=int)
    enrich.add_argument("--league-id", action="append", type=int, dest="league_ids")
    enrich.add_argument("--team-id", action="append", type=int, dest="team_ids")
    enrich.add_argument("--oldest-first", action="store_true")
    history = commands.add_parser("sync-ti-history")
    history.add_argument("--first-year", type=int, default=2016)
    history.add_argument("--last-year", type=int, default=2025)

    elo = commands.add_parser("build-elo")
    elo.add_argument("--since", default="2026-01-01", type=parse_date)
    elo.add_argument(
        "--participants", default="data/reference/ti_2026_participants.csv"
    )
    commands.add_parser("build-rosters")
    report = commands.add_parser("report-ti-teams")
    report.add_argument(
        "--participants", default="data/reference/ti_2026_participants.csv"
    )
    ti_events = commands.add_parser("build-ti-events")
    ti_events.add_argument("--events", default="data/reference/ti_events.csv")
    glicko = commands.add_parser("build-glicko")
    glicko.add_argument("--since", default="2026-01-01", type=parse_date)
    glicko.add_argument(
        "--participants", default="data/reference/ti_2026_participants.csv"
    )
    hero_meta = commands.add_parser("report-hero-meta")
    hero_meta.add_argument("--bracket", type=int, default=7, choices=range(1, 9))
    hero_meta.add_argument("--limit", type=int, default=15)
    hero_meta.add_argument("--minimum-picks", type=int, default=100)
    baseline = commands.add_parser("train-match-baseline")
    baseline.add_argument("--cutoff", default="2026-07-01", type=parse_date)
    baseline.add_argument("--artifact", default="artifacts/match_baseline.json")
    boosted = commands.add_parser("train-match-boosted")
    boosted.add_argument("--cutoff", default="2026-07-01", type=parse_date)
    boosted.add_argument("--artifact", default="artifacts/match_boosted.json")
    roster_model = commands.add_parser("train-match-roster")
    roster_model.add_argument("--cutoff", default="2026-07-01", type=parse_date)
    roster_model.add_argument("--artifact", default="artifacts/match_roster.json")
    commands.add_parser("build-fantasy-stats")
    player_ratings = commands.add_parser("build-player-ratings")
    player_ratings.add_argument(
        "--participants", default="data/reference/ti_2026_participants.csv"
    )
    simulator = commands.add_parser("simulate-ti-road")
    simulator.add_argument(
        "--participants", default="data/reference/ti_2026_participants.csv"
    )
    simulator.add_argument(
        "--fixtures", default="data/reference/ti_2026_round1.csv"
    )
    simulator.add_argument("--observed-results")
    simulator.add_argument("--iterations", type=int, default=20_000)
    simulator.add_argument("--seed", type=int, default=2026)
    simulator.add_argument("--top", type=int, default=10)
    simulator.add_argument("--artifact", default="artifacts/ti_road_simulation.json")
    draft_stats = commands.add_parser("build-draft-stats")
    draft_stats.add_argument(
        "--participants", default="data/reference/ti_2026_participants.csv"
    )
    commands.add_parser("status")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    settings = Settings.from_env()
    store = Store(settings.database_path)
    client = build_client(settings)
    try:
        if args.command == "init-db":
            init_db(store)
        elif args.command == "sync-static":
            sync_static(store, client)
        elif args.command == "sync-pro-index":
            sync_pro_index(store, client, args.since)
        elif args.command == "enrich-matches":
            enrich_matches(
                store, client, args.since, args.limit, args.league_ids, args.team_ids,
                args.oldest_first,
            )
        elif args.command == "sync-ti-history":
            sync_ti_history(store, client, args.first_year, args.last_year)
        elif args.command == "build-elo":
            build_elo(store, args.since, args.participants)
        elif args.command == "build-rosters":
            build_rosters(store)
        elif args.command == "report-ti-teams":
            report_ti_teams(store, args.participants)
        elif args.command == "build-ti-events":
            build_ti_events(store, args.events)
        elif args.command == "build-glicko":
            build_glicko(store, args.since, args.participants)
        elif args.command == "report-hero-meta":
            report_hero_meta(store, args.bracket, args.limit, args.minimum_picks)
        elif args.command == "train-match-baseline":
            train_match_baseline(store, args.cutoff, args.artifact)
        elif args.command == "train-match-boosted":
            train_match_boosted(store, args.cutoff, args.artifact)
        elif args.command == "train-match-roster":
            train_match_roster(store, args.cutoff, args.artifact)
        elif args.command == "build-fantasy-stats":
            build_fantasy_stats(store)
        elif args.command == "build-player-ratings":
            build_player_ratings(store, args.participants)
        elif args.command == "simulate-ti-road":
            simulate_ti_road(
                store, args.participants, args.fixtures, args.observed_results,
                args.iterations, args.seed, args.top, args.artifact,
            )
        elif args.command == "build-draft-stats":
            build_draft_stats(store, args.participants)
        elif args.command == "status":
            show_status(store)
    except (DataSourceError, sqlite3.Error, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
