# TI Oracle

Data and modeling foundation for a Dota 2 TI prediction and Fantasy optimization site.

## Current milestone

The repository now provides a resumable data/model pipeline and a working local web research app for:

- professional match indexes;
- detailed match/player Fantasy statistics;
- ordered hero picks and bans;
- team names and official logo URLs;
- professional player identities and portraits;
- hero metadata and rank-bracket snapshot statistics.
- leak-free Elo, Glicko-2, player-lineup, roster-continuity and patch-form features;
- forward-tested match probability models with explicit promotion gates;
- a resumable 500-million-run TI Road Swiss/elimination simulator with Fantasy exposure;
- current-patch hero matchup, synergy, team comfort and ban statistics;
- an interactive dark interface with matchup odds, qualification probabilities, rank curves,
  local Fantasy screenshot OCR, title/banner extraction, player matching, and a manual counterpick console.

## Quick start

Install the data/model and web extras, then build or serve the local research app.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[model,web,dev]'
ti-data init-db
ti-data sync-static
ti-data sync-pro-index --since 2026-01-01
ti-data enrich-matches --since 2026-01-01 --limit 25
# Prioritize one team or event without redownloading completed matches:
ti-data enrich-matches --since 2026-01-01 --team-id 9247354 --limit 100
ti-data enrich-matches --since 2016-01-01 --league-id 18324
ti-data sync-ti-history --first-year 2016 --last-year 2025
ti-data build-elo --since 2026-01-01
ti-data build-glicko --since 2026-01-01
ti-data build-rosters
ti-data build-ti-events
ti-data build-fantasy-stats
ti-data build-player-ratings
ti-data build-draft-stats
ti-data report-ti-teams
ti-data report-hero-meta --bracket 7 --limit 15
ti-data train-match-baseline --cutoff 2026-07-01
ti-data train-match-boosted --cutoff 2026-07-01
ti-data train-match-roster --cutoff 2026-07-01
ti-data simulate-ti-road --fixtures data/reference/ti_2026_round1.csv --iterations 20000 --top 10
# Once TI is live, condition the remaining paths on completed series:
ti-data simulate-ti-road --observed-results data/reference/ti_2026_live_results.csv --iterations 250000 --top 10
python3 scripts/build_live_ti_fantasy.py
ti-data status
```

The default database is `data/ti_oracle.sqlite3`. Set `OPENDOTA_API_KEY` if a higher OpenDota allowance is available. STRATZ and Steam credentials are optional future enrichments; see `.env.example`.

Start the Next.js frontend. In development this command also launches FastAPI on port 8000, so only one terminal is required:

```bash
cd web
npm install
npm run dev
```

Open `http://127.0.0.1:3000`. Next.js proxies `/api/*` to FastAPI at `http://127.0.0.1:8000`. If an API is already running there, the development launcher reuses it. Use `npm run dev:web` to start only Next.js, or set `TI_ORACLE_API_ORIGIN` when the backend uses another origin.

## 500M Road + Fantasy simulation

The long runner resumes the checked-in 100M aggregate, checkpoints every 5M new paths,
and regenerates Fantasy projections after reaching 500M:

```bash
python3 scripts/run_road_fantasy_500m.py
```

Live state is written to `artifacts/ti_road_500m_progress.json` and is also available at
`/api/simulation/road/progress`. Tournament probabilities are served at
`/api/simulation/road`; role/player Fantasy projections and the top ten lineups are served
at `/api/fantasy/simulation`.

Fantasy sampling uses complete map rows so GPM, XPM, wards, and the other stats retain
their observed relationships. XPM is a predictive feature only because the supplied 2026
rules award it no direct points. The scorer averages players within each role for a map,
keeps the best two maps in a Bo3, and then keeps the best series available in the period.

## Model gate

- Raw 2026 Elo remains the accepted all-map baseline: 0.6420 held-out log loss over 481 maps after 2026-07-01.
- The team-only nonlinear candidate scored 0.6483 and was rejected.
- The lineup-aware candidate scored 0.5831 versus Elo's 0.5971 over the 196 held-out maps for which full rosters were parsed. It is provisionally better, but its paired confidence interval still crosses zero, so it is not yet marked fully promoted.
- All match features are generated before the map result is applied. Model selection uses pre-cutoff validation only; July–August results remain the final test.

## Collection policy

- Raw source payloads are stored in normalized database rows plus `raw_json` for reproducibility.
- Inserts are idempotent, so interrupted jobs can be rerun safely.
- Requests use bounded exponential backoff and an explicit delay.
- Every snapshot records its collection time and source.
- Modeling splits must be chronological to prevent future-data leakage.
