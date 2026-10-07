from __future__ import annotations

import csv
import json
import math
import sqlite3
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile

from .config import Settings
from .glicko2 import GlickoRating, win_probability
from .meta import RANK_NAMES, rank_hero_meta
from .reports import ti_team_baseline_rows
from .store import Store
from .draft import recommend_counters


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PARTICIPANTS = PROJECT_ROOT / "data/reference/ti_2026_participants.csv"
TITLES = PROJECT_ROOT / "data/reference/fantasy_titles_2026.csv"
ROSTER_POSITIONS = PROJECT_ROOT / "data/reference/ti_2026_roster_positions.csv"
HERO_CDN = "https://cdn.cloudflare.steamstatic.com"


def _hero_url(path: str | None) -> str | None:
    if not path:
        return None
    return HERO_CDN + path.rstrip("?")


def _image_kind(payload: bytes) -> str | None:
    if payload.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if len(payload) >= 12 and payload[:4] == b"RIFF" and payload[8:12] == b"WEBP":
        return "webp"
    return None


def _infer_fantasy_role(
    fantasy_role: int | None,
    safe_maps: int,
    mid_maps: int,
    off_maps: int,
    gold_per_min: float,
    wards_planted: float,
    last_hits: float,
) -> str:
    if fantasy_role == 1:
        return "Core"
    if fantasy_role == 2:
        return "Support"
    lane_maps = max(safe_maps + mid_maps + off_maps, 1)
    if mid_maps / lane_maps >= 0.55 and gold_per_min >= 450:
        return "Mid"
    if wards_planted >= 5 or (gold_per_min < 430 and last_hits < 160):
        return "Support"
    return "Core"


def _player_key(name: str | None) -> str:
    return "".join(character for character in (name or "").lower() if character.isalnum())


def _registered_roster_positions() -> dict[tuple[int, str], int]:
    with ROSTER_POSITIONS.open(newline="", encoding="utf-8") as handle:
        return {
            (int(row["source_team_id"]), _player_key(row["player"])): int(row["position"])
            for row in csv.DictReader(handle)
        }


def _position_label(
    role: str,
    safe_maps: int,
    off_maps: int,
    registered_position: int | None,
) -> str:
    if registered_position is not None:
        return f"Position {registered_position}"
    if role == "Mid":
        return "Position 2"
    if role == "Core":
        return "Position 1" if safe_maps >= off_maps else "Position 3"
    return "Position 4" if off_maps > safe_maps else "Position 5"


def _team_rows(connection: sqlite3.Connection) -> list[dict[str, object]]:
    rows = ti_team_baseline_rows(connection, PARTICIPANTS)
    for row in rows:
        source_id = row["active_source_team_id"]
        asset = connection.execute(
            "SELECT logo_url FROM teams WHERE team_id=?", (source_id,)
        ).fetchone()
        row["logo_url"] = asset[0].strip() if asset and asset[0] else None
    return rows


def _fantasy_players(connection: sqlite3.Connection, limit: int) -> list[dict[str, object]]:
    roster_positions = _registered_roster_positions()
    rows = list(
        connection.execute(
            """
            SELECT f.account_id,
                   COALESCE(p.handle, p.persona_name, mp.player_name, mp.persona_name) AS name,
                   p.avatar_url, p.current_team_id, p.fantasy_role,
                   t.name AS team_name, t.logo_url,
                   COUNT(*) AS maps,
                   AVG(f.kills) AS kills, AVG(f.deaths) AS deaths,
                   AVG(f.creep_score) AS creep_score, AVG(f.gold_per_min) AS gold_per_min,
                   AVG(mp.xp_per_min) AS xp_per_min,
                   AVG(mp.denies) AS denies,
                   AVG(f.tower_kills) AS tower_kills, AVG(f.roshan_kills) AS roshan_kills,
                   AVG(f.teamfight_participation) AS teamfight_participation,
                   AVG(mp.observer_wards) AS wards_planted,
                   AVG(f.camps_stacked) AS camps_stacked,
                   AVG(f.runes_grabbed) AS runes_grabbed,
                   AVG(f.first_blood) AS first_blood, AVG(f.stuns) AS stuns,
                   AVG(f.smokes_used) AS smokes_used, AVG(f.madstones) AS madstones,
                   AVG(f.watchers_taken) AS watchers_taken,
                   AVG(f.lotus_item_uses) AS lotus_item_uses,
                   AVG(f.tormentor_kills) AS tormentor_kills,
                   AVG(f.courier_kills) AS courier_kills,
                   SUM(CASE WHEN mp.lane_role=1 THEN 1 ELSE 0 END) AS safe_lane_maps,
                   SUM(CASE WHEN mp.lane_role=2 THEN 1 ELSE 0 END) AS mid_lane_maps,
                   SUM(CASE WHEN mp.lane_role=3 THEN 1 ELSE 0 END) AS off_lane_maps,
                   AVG(mp.last_hits) AS last_hits,
                   MAX(m.start_time) AS last_map
            FROM fantasy_player_stats f
            JOIN pro_matches m USING(match_id)
            JOIN match_players mp
              ON mp.match_id=f.match_id AND mp.player_slot=f.player_slot
            LEFT JOIN players p ON p.account_id=f.account_id
            LEFT JOIN teams t ON t.team_id=p.current_team_id
            WHERE f.account_id IS NOT NULL AND m.start_time >= 1767225600
            GROUP BY f.account_id
            HAVING COUNT(*) >= 3
            ORDER BY maps DESC
            """
        )
    )
    output = []
    raw_scores = []
    for row in rows:
        value = dict(row)
        score = (
            float(value["kills"] or 0) * 1.0
            - float(value["deaths"] or 0) * 0.45
            + float(value["creep_score"] or 0) * 0.004
            + float(value["gold_per_min"] or 0) * 0.002
            + float(value["tower_kills"] or 0) * 1.5
            + float(value["roshan_kills"] or 0) * 2.0
            + float(value["teamfight_participation"] or 0) * 4.0
            + float(value["wards_planted"] or 0) * 0.35
            + float(value["camps_stacked"] or 0) * 0.45
            + float(value["runes_grabbed"] or 0) * 0.15
            + float(value["first_blood"] or 0) * 2.0
            + float(value["stuns"] or 0) * 0.025
            + float(value["smokes_used"] or 0) * 0.4
            + float(value["tormentor_kills"] or 0) * 1.5
            + float(value["courier_kills"] or 0) * 1.0
        )
        value["logo_url"] = value["logo_url"].strip() if value.get("logo_url") else None
        safe_maps = int(value["safe_lane_maps"] or 0)
        mid_maps = int(value["mid_lane_maps"] or 0)
        off_maps = int(value["off_lane_maps"] or 0)
        team_id = int(value["current_team_id"] or 0)
        registered_position = roster_positions.get((team_id, _player_key(str(value.get("name") or ""))))
        if registered_position is not None:
            role = "Mid" if registered_position == 2 else "Core" if registered_position in (1, 3) else "Support"
            value["role_source"] = "TI 2026 registered roster"
        else:
            role = _infer_fantasy_role(
                int(value["fantasy_role"]) if value.get("fantasy_role") is not None else None,
                safe_maps,
                mid_maps,
                off_maps,
                float(value["gold_per_min"] or 0),
                float(value["wards_planted"] or 0),
                float(value["last_hits"] or 0),
            )
            value["role_source"] = "recent match fallback"
        value["inferred_role"] = role
        value["position_label"] = _position_label(role, safe_maps, off_maps, registered_position)
        value["raw_signal"] = score
        output.append(value)
        raw_scores.append(score)
    if not output:
        return []
    lower, upper = min(raw_scores), max(raw_scores)
    scale = max(upper - lower, 1e-9)
    for value in output:
        value["signal_index"] = round(40.0 + 60.0 * (value.pop("raw_signal") - lower) / scale, 1)
    output.sort(key=lambda value: (float(value["signal_index"]), int(value["maps"])), reverse=True)
    return output[:limit]


def create_app(database_path: Path | None = None) -> FastAPI:
    settings = Settings.from_env()
    store = Store(database_path or settings.database_path)
    store.initialize()
    app = FastAPI(title="TI Oracle", version="0.1.0")

    @app.get("/api/overview")
    def overview() -> dict[str, object]:
        with store.connect() as connection:
            patch = connection.execute(
                "SELECT patch_id, name, released_at FROM patches ORDER BY patch_id DESC LIMIT 1"
            ).fetchone()
            latest = connection.execute("SELECT MAX(start_time) FROM pro_matches").fetchone()[0]
            counts = {
                "maps": connection.execute("SELECT COUNT(*) FROM pro_matches").fetchone()[0],
                "detailed_maps": connection.execute(
                    "SELECT COUNT(*) FROM pro_matches WHERE detailed=1"
                ).fetchone()[0],
                "players": connection.execute("SELECT COUNT(*) FROM players").fetchone()[0],
                "draft_events": connection.execute("SELECT COUNT(*) FROM picks_bans").fetchone()[0],
            }
        artifact_path = PROJECT_ROOT / "artifacts/match_roster.json"
        model = json.loads(artifact_path.read_text()) if artifact_path.exists() else None
        return {
            "patch": dict(patch) if patch else None,
            "latest_map": latest,
            "counts": counts,
            "model": {
                "status": "provisional" if model and model["provisional_improvement"] else "baseline",
                "test_accuracy": model["test_metrics"]["accuracy"] if model else None,
                "test_maps": model["test_rows"] if model else None,
            },
        }

    @app.get("/api/teams")
    def teams() -> list[dict[str, object]]:
        with store.connect() as connection:
            return _team_rows(connection)

    @app.get("/api/predict")
    def predict(team_a: str, team_b: str, best_of: int = Query(3, ge=1, le=5)) -> dict[str, object]:
        if team_a == team_b:
            raise HTTPException(400, "choose two different teams")
        with store.connect() as connection:
            rows = _team_rows(connection)
        by_key = {str(row["canonical_team"]): row for row in rows}
        if team_a not in by_key or team_b not in by_key:
            raise HTTPException(404, "team not found")
        first, second = by_key[team_a], by_key[team_b]
        if first["glicko_rating"] is None or second["glicko_rating"] is None:
            raise HTTPException(409, "ratings are not ready for this matchup")
        map_probability = win_probability(
            GlickoRating(float(first["glicko_rating"]), float(first["glicko_deviation"]), 0.06),
            GlickoRating(float(second["glicko_rating"]), float(second["glicko_deviation"]), 0.06),
        )
        wins_needed = best_of // 2 + 1
        series_probability = sum(
            math.comb(best_of, wins) * map_probability**wins * (1-map_probability)**(best_of-wins)
            for wins in range(wins_needed, best_of + 1)
        )
        return {
            "team_a": first,
            "team_b": second,
            "best_of": best_of,
            "map_probability": map_probability,
            "series_probability": series_probability,
            "method": "Glicko-2 pre-draft baseline; roster model activates after verified lineups",
        }

    @app.get("/api/heroes/meta")
    def heroes_meta(
        bracket: int = Query(7, ge=1, le=8),
        limit: int = Query(10, ge=1, le=30),
        minimum_picks: int = Query(100, ge=0),
    ) -> dict[str, object]:
        with store.connect() as connection:
            rows = rank_hero_meta(connection, bracket, limit, minimum_picks)
            for row in rows:
                asset = connection.execute(
                    "SELECT image_path, icon_path FROM heroes WHERE hero_id=?",
                    (row["hero_id"],),
                ).fetchone()
                row["image_url"] = _hero_url(asset[0] if asset else None)
                row["icon_url"] = _hero_url(asset[1] if asset else None)
        return {"bracket": bracket, "bracket_name": RANK_NAMES[bracket], "heroes": rows}

    @app.get("/api/heroes/rank-trends")
    def hero_rank_trends(limit: int = Query(5, ge=1, le=10)) -> list[dict[str, object]]:
        with store.connect() as connection:
            top = rank_hero_meta(connection, 7, limit, 100)
            collected = connection.execute(
                "SELECT MAX(collected_at) FROM hero_meta_snapshots"
            ).fetchone()[0]
            output = []
            for hero in top:
                rows = connection.execute(
                    "SELECT bracket, picks, wins FROM hero_meta_snapshots "
                    "WHERE collected_at=? AND hero_id=? ORDER BY bracket",
                    (collected, hero["hero_id"]),
                )
                points = [
                    {
                        "bracket": int(row["bracket"]),
                        "rank": RANK_NAMES[int(row["bracket"])],
                        "picks": int(row["picks"]),
                        "win_rate": int(row["wins"]) / int(row["picks"]) if row["picks"] else None,
                    }
                    for row in rows
                ]
                output.append({"hero_id": hero["hero_id"], "hero": hero["hero"], "points": points})
        return output

    @app.get("/api/draft/heroes")
    def draft_heroes() -> list[dict[str, object]]:
        with store.connect() as connection:
            rows = connection.execute(
                "SELECT hero_id, localized_name, image_path, icon_path "
                "FROM heroes ORDER BY localized_name"
            )
            return [
                {
                    "hero_id": int(row["hero_id"]),
                    "hero": row["localized_name"],
                    "image_url": _hero_url(row["image_path"]),
                    "icon_url": _hero_url(row["icon_path"]),
                }
                for row in rows
            ]

    @app.get("/api/draft/recommend")
    def draft_recommend(
        enemy: list[int] = Query(...),
        ally: list[int] = Query(default=[]),
        limit: int = Query(10, ge=1, le=25),
    ) -> dict[str, object]:
        if len(enemy) > 5 or len(ally) > 5:
            raise HTTPException(400, "a draft side can contain at most five heroes")
        with store.connect() as connection:
            try:
                rows = recommend_counters(connection, enemy, ally, limit=limit)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
        for row in rows:
            row["image_url"] = _hero_url(str(row.pop("image_path")))
        return {
            "enemy": enemy,
            "ally": ally,
            "recommendations": rows,
            "method": "60% opponent matchup, 25% patch meta, 15% ally synergy; samples use Bayesian shrinkage",
        }

    @app.get("/api/fantasy/players")
    def fantasy_players(limit: int = Query(20, ge=1, le=500)) -> dict[str, object]:
        with store.connect() as connection:
            rows = _fantasy_players(connection, limit)
        return {
            "players": rows,
            "method": "Official 2026 stat values applied to current player map averages; role recommendations use the 1,601-map Tier-1 guide prior",
        }

    @app.get("/api/fantasy/titles")
    def fantasy_titles() -> list[dict[str, str]]:
        with TITLES.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    @app.get("/api/simulation/road")
    def road_simulation() -> dict[str, object]:
        artifact = PROJECT_ROOT / "artifacts/ti_road_simulation.json"
        if not artifact.exists():
            raise HTTPException(503, "run ti-data simulate-ti-road first")
        return json.loads(artifact.read_text(encoding="utf-8"))

    @app.get("/api/simulation/road/progress")
    def road_simulation_progress() -> dict[str, object]:
        artifact = PROJECT_ROOT / "artifacts/ti_road_500m_progress.json"
        if not artifact.exists():
            raise HTTPException(503, "the 500M simulation has not been started")
        return json.loads(artifact.read_text(encoding="utf-8"))

    @app.get("/api/simulation/main-event")
    def main_event_simulation() -> dict[str, object]:
        artifact = PROJECT_ROOT / "artifacts/ti_main_event_simulation.json"
        if not artifact.exists():
            raise HTTPException(503, "run scripts/run_ti_main_event.py first")
        return json.loads(artifact.read_text(encoding="utf-8"))

    @app.get("/api/fantasy/simulation")
    def fantasy_simulation() -> dict[str, object]:
        artifact = PROJECT_ROOT / "artifacts/ti_fantasy_projection.json"
        if not artifact.exists():
            raise HTTPException(503, "Fantasy simulation has not been generated")
        return json.loads(artifact.read_text(encoding="utf-8"))

    @app.post("/api/upload/fantasy")
    async def upload_fantasy(file: UploadFile = File(...)) -> dict[str, object]:
        if not (file.content_type or "").startswith("image/"):
            raise HTTPException(415, "upload a PNG, JPEG, or WebP image")
        payload = await file.read(10 * 1024 * 1024 + 1)
        if len(payload) > 10 * 1024 * 1024:
            raise HTTPException(413, "image exceeds the 10 MB limit")
        image_kind = _image_kind(payload)
        if image_kind is None:
            raise HTTPException(415, "the uploaded bytes are not a supported image")
        return {
            "filename": file.filename,
            "bytes": len(payload),
            "image_kind": image_kind,
            "status": "received",
            "message": "Screenshot received. Automatic card/title recognition is the next model stage.",
        }

    @app.post("/api/upload/draft")
    async def upload_draft(file: UploadFile = File(...)) -> dict[str, object]:
        if not (file.content_type or "").startswith("image/"):
            raise HTTPException(415, "upload a PNG, JPEG, or WebP image")
        payload = await file.read(10 * 1024 * 1024 + 1)
        if len(payload) > 10 * 1024 * 1024:
            raise HTTPException(413, "image exceeds the 10 MB limit")
        image_kind = _image_kind(payload)
        if image_kind is None:
            raise HTTPException(415, "the uploaded bytes are not a supported image")
        return {
            "filename": file.filename,
            "bytes": len(payload),
            "image_kind": image_kind,
            "status": "received",
            "message": "Draft image received. Use manual hero selection until recognition is trained.",
        }

    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("ti_oracle_data.webapp:app", host="127.0.0.1", port=8000, reload=False)
