PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS ingestion_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    entity TEXT NOT NULL,
    started_at INTEGER NOT NULL,
    completed_at INTEGER,
    rows_written INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    error TEXT
);

CREATE TABLE IF NOT EXISTS teams (
    team_id INTEGER PRIMARY KEY,
    name TEXT,
    tag TEXT,
    logo_url TEXT,
    rating REAL,
    wins INTEGER,
    losses INTEGER,
    last_match_time INTEGER,
    source TEXT NOT NULL,
    updated_at INTEGER NOT NULL,
    raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS leagues (
    league_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    tier TEXT,
    banner TEXT,
    source TEXT NOT NULL,
    updated_at INTEGER NOT NULL,
    raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS patches (
    patch_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    released_at TEXT,
    source TEXT NOT NULL,
    updated_at INTEGER NOT NULL,
    raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS players (
    account_id INTEGER PRIMARY KEY,
    steam_id TEXT,
    handle TEXT,
    persona_name TEXT,
    country_code TEXT,
    fantasy_role INTEGER,
    current_team_id INTEGER,
    avatar_url TEXT,
    profile_url TEXT,
    last_match_time TEXT,
    source TEXT NOT NULL,
    updated_at INTEGER NOT NULL,
    raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS heroes (
    hero_id INTEGER PRIMARY KEY,
    internal_name TEXT NOT NULL,
    localized_name TEXT NOT NULL,
    primary_attribute TEXT,
    attack_type TEXT,
    roles_json TEXT NOT NULL,
    image_path TEXT,
    icon_path TEXT,
    source TEXT NOT NULL,
    updated_at INTEGER NOT NULL,
    raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hero_meta_snapshots (
    collected_at INTEGER NOT NULL,
    hero_id INTEGER NOT NULL,
    bracket INTEGER NOT NULL,
    picks INTEGER NOT NULL,
    wins INTEGER NOT NULL,
    pro_picks INTEGER,
    pro_wins INTEGER,
    pro_bans INTEGER,
    raw_json TEXT NOT NULL,
    PRIMARY KEY (collected_at, hero_id, bracket),
    FOREIGN KEY (hero_id) REFERENCES heroes(hero_id)
);

CREATE TABLE IF NOT EXISTS pro_matches (
    match_id INTEGER PRIMARY KEY,
    start_time INTEGER NOT NULL,
    duration INTEGER,
    patch INTEGER,
    version INTEGER,
    league_id INTEGER,
    league_name TEXT,
    series_id INTEGER,
    series_type INTEGER,
    radiant_team_id INTEGER,
    radiant_name TEXT,
    dire_team_id INTEGER,
    dire_name TEXT,
    radiant_score INTEGER,
    dire_score INTEGER,
    radiant_win INTEGER NOT NULL,
    detailed INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL,
    updated_at INTEGER NOT NULL,
    raw_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pro_matches_start_time
    ON pro_matches(start_time);
CREATE INDEX IF NOT EXISTS idx_pro_matches_teams
    ON pro_matches(radiant_team_id, dire_team_id);

CREATE TABLE IF NOT EXISTS match_players (
    match_id INTEGER NOT NULL,
    account_id INTEGER,
    player_slot INTEGER NOT NULL,
    team_side INTEGER NOT NULL,
    player_name TEXT,
    persona_name TEXT,
    hero_id INTEGER NOT NULL,
    lane_role INTEGER,
    is_roaming INTEGER,
    kills INTEGER,
    deaths INTEGER,
    assists INTEGER,
    gold_per_min INTEGER,
    xp_per_min INTEGER,
    last_hits INTEGER,
    denies INTEGER,
    net_worth INTEGER,
    hero_damage INTEGER,
    tower_damage INTEGER,
    hero_healing INTEGER,
    stuns REAL,
    observer_wards INTEGER,
    sentry_wards INTEGER,
    camps_stacked INTEGER,
    rune_pickups INTEGER,
    teamfight_participation REAL,
    firstblood_claimed INTEGER,
    raw_json TEXT NOT NULL,
    PRIMARY KEY (match_id, player_slot),
    FOREIGN KEY (match_id) REFERENCES pro_matches(match_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_match_players_account
    ON match_players(account_id, match_id);
CREATE INDEX IF NOT EXISTS idx_match_players_hero
    ON match_players(hero_id, match_id);

CREATE TABLE IF NOT EXISTS picks_bans (
    match_id INTEGER NOT NULL,
    draft_order INTEGER NOT NULL,
    team_side INTEGER NOT NULL,
    is_pick INTEGER NOT NULL,
    hero_id INTEGER NOT NULL,
    raw_json TEXT NOT NULL,
    PRIMARY KEY (match_id, draft_order),
    FOREIGN KEY (match_id) REFERENCES pro_matches(match_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_picks_bans_hero
    ON picks_bans(hero_id, is_pick, match_id);

CREATE TABLE IF NOT EXISTS team_rating_history (
    match_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    rating_before REAL NOT NULL,
    rating_after REAL NOT NULL,
    opponent_team_id INTEGER NOT NULL,
    expected_score REAL NOT NULL,
    actual_score REAL NOT NULL,
    created_at INTEGER NOT NULL,
    PRIMARY KEY (match_id, team_id),
    FOREIGN KEY (match_id) REFERENCES pro_matches(match_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_team_rating_latest
    ON team_rating_history(team_id, match_id);

CREATE TABLE IF NOT EXISTS map_rating_features (
    match_id INTEGER PRIMARY KEY,
    start_time INTEGER NOT NULL,
    patch INTEGER,
    league_id INTEGER,
    league_tier TEXT,
    radiant_team_id INTEGER NOT NULL,
    dire_team_id INTEGER NOT NULL,
    radiant_rating_before REAL NOT NULL,
    dire_rating_before REAL NOT NULL,
    radiant_games_before INTEGER NOT NULL,
    dire_games_before INTEGER NOT NULL,
    rating_difference REAL NOT NULL,
    radiant_expected REAL NOT NULL,
    radiant_win INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    FOREIGN KEY (match_id) REFERENCES pro_matches(match_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_map_features_time
    ON map_rating_features(start_time);

CREATE TABLE IF NOT EXISTS team_glicko_history (
    period_date TEXT NOT NULL,
    team_id INTEGER NOT NULL,
    rating_before REAL NOT NULL,
    deviation_before REAL NOT NULL,
    volatility_before REAL NOT NULL,
    rating_after REAL NOT NULL,
    deviation_after REAL NOT NULL,
    volatility_after REAL NOT NULL,
    maps INTEGER NOT NULL,
    wins REAL NOT NULL,
    created_at INTEGER NOT NULL,
    PRIMARY KEY (period_date, team_id)
);

CREATE INDEX IF NOT EXISTS idx_glicko_latest
    ON team_glicko_history(team_id, period_date);

CREATE TABLE IF NOT EXISTS map_glicko_features (
    match_id INTEGER PRIMARY KEY,
    start_time INTEGER NOT NULL,
    radiant_team_id INTEGER NOT NULL,
    dire_team_id INTEGER NOT NULL,
    radiant_rating_before REAL NOT NULL,
    dire_rating_before REAL NOT NULL,
    radiant_deviation_before REAL NOT NULL,
    dire_deviation_before REAL NOT NULL,
    rating_difference REAL NOT NULL,
    radiant_expected REAL NOT NULL,
    radiant_win INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    FOREIGN KEY (match_id) REFERENCES pro_matches(match_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ti_event_matches (
    match_id INTEGER PRIMARY KEY,
    ti_year INTEGER NOT NULL,
    league_id INTEGER NOT NULL,
    is_venue_stage INTEGER NOT NULL,
    event_start TEXT NOT NULL,
    event_end TEXT NOT NULL,
    host_city TEXT NOT NULL,
    host_country TEXT NOT NULL,
    timezone TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    FOREIGN KEY (match_id) REFERENCES pro_matches(match_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS team_roster_observations (
    match_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    team_side INTEGER NOT NULL,
    start_time INTEGER NOT NULL,
    lineup_key TEXT NOT NULL,
    account_ids_json TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    PRIMARY KEY (match_id, team_side),
    FOREIGN KEY (match_id) REFERENCES pro_matches(match_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_roster_lineup
    ON team_roster_observations(lineup_key, start_time);
CREATE INDEX IF NOT EXISTS idx_roster_team
    ON team_roster_observations(team_id, start_time);

CREATE TABLE IF NOT EXISTS player_rating_history (
    match_id INTEGER NOT NULL,
    account_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    rating_before REAL NOT NULL,
    rating_after REAL NOT NULL,
    games_before INTEGER NOT NULL,
    expected_score REAL NOT NULL,
    actual_score REAL NOT NULL,
    created_at INTEGER NOT NULL,
    PRIMARY KEY (match_id, account_id),
    FOREIGN KEY (match_id) REFERENCES pro_matches(match_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_player_rating_latest
    ON player_rating_history(account_id, match_id);

CREATE TABLE IF NOT EXISTS map_roster_features (
    match_id INTEGER PRIMARY KEY,
    start_time INTEGER NOT NULL,
    radiant_team_id INTEGER NOT NULL,
    dire_team_id INTEGER NOT NULL,
    radiant_player_rating REAL NOT NULL,
    dire_player_rating REAL NOT NULL,
    player_rating_difference REAL NOT NULL,
    radiant_expected REAL NOT NULL,
    radiant_average_games REAL NOT NULL,
    dire_average_games REAL NOT NULL,
    radiant_lineup_maps INTEGER NOT NULL,
    dire_lineup_maps INTEGER NOT NULL,
    radiant_pair_maps REAL NOT NULL,
    dire_pair_maps REAL NOT NULL,
    radiant_retained_players INTEGER NOT NULL,
    dire_retained_players INTEGER NOT NULL,
    radiant_new_players INTEGER NOT NULL,
    dire_new_players INTEGER NOT NULL,
    radiant_win INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    FOREIGN KEY (match_id) REFERENCES pro_matches(match_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_roster_features_time
    ON map_roster_features(start_time);

CREATE TABLE IF NOT EXISTS hero_matchup_stats (
    patch INTEGER NOT NULL,
    hero_id INTEGER NOT NULL,
    opponent_hero_id INTEGER NOT NULL,
    games INTEGER NOT NULL,
    wins INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    PRIMARY KEY (patch, hero_id, opponent_hero_id)
);

CREATE TABLE IF NOT EXISTS hero_synergy_stats (
    patch INTEGER NOT NULL,
    hero_id INTEGER NOT NULL,
    ally_hero_id INTEGER NOT NULL,
    games INTEGER NOT NULL,
    wins INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    PRIMARY KEY (patch, hero_id, ally_hero_id)
);

CREATE TABLE IF NOT EXISTS team_hero_stats (
    patch INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    hero_id INTEGER NOT NULL,
    picks INTEGER NOT NULL,
    wins INTEGER NOT NULL,
    bans INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    PRIMARY KEY (patch, team_id, hero_id)
);

CREATE VIEW IF NOT EXISTS player_training_features AS
SELECT
    mp.match_id,
    m.start_time,
    m.patch,
    m.league_id,
    COALESCE(l.tier, 'professional') AS league_tier,
    mp.account_id,
    mp.player_name,
    p.fantasy_role,
    mp.team_side,
    CASE WHEN mp.team_side = 0 THEN m.radiant_team_id ELSE m.dire_team_id END AS team_id,
    CASE WHEN mp.team_side = 0 THEN m.dire_team_id ELSE m.radiant_team_id END AS opponent_team_id,
    CASE
        WHEN mp.team_side = 0 THEN m.radiant_win
        ELSE 1 - m.radiant_win
    END AS won,
    mp.hero_id,
    mp.lane_role,
    m.duration,
    mp.kills,
    mp.deaths,
    mp.assists,
    mp.gold_per_min,
    mp.xp_per_min,
    mp.last_hits,
    mp.denies,
    mp.net_worth,
    mp.hero_damage,
    mp.tower_damage,
    mp.hero_healing,
    mp.stuns,
    mp.observer_wards,
    mp.sentry_wards,
    mp.camps_stacked,
    mp.rune_pickups,
    mp.teamfight_participation,
    mp.firstblood_claimed,
    CASE WHEN m.duration > 0 THEN mp.kills * 60.0 / m.duration END AS kills_per_minute,
    CASE WHEN m.duration > 0 THEN mp.assists * 60.0 / m.duration END AS assists_per_minute,
    CASE WHEN m.duration > 0 THEN mp.last_hits * 60.0 / m.duration END AS last_hits_per_minute,
    CASE WHEN m.duration > 0 THEN mp.hero_damage * 60.0 / m.duration END AS hero_damage_per_minute,
    CASE WHEN m.duration > 0 THEN mp.tower_damage * 60.0 / m.duration END AS tower_damage_per_minute,
    CASE WHEN m.duration > 0 THEN mp.stuns * 60.0 / m.duration END AS stuns_per_minute
FROM match_players mp
JOIN pro_matches m ON m.match_id = mp.match_id
LEFT JOIN players p ON p.account_id = mp.account_id
LEFT JOIN leagues l ON l.league_id = m.league_id;

CREATE TABLE IF NOT EXISTS fantasy_player_stats (
    match_id INTEGER NOT NULL,
    player_slot INTEGER NOT NULL,
    account_id INTEGER,
    kills INTEGER,
    deaths INTEGER,
    creep_score INTEGER,
    gold_per_min INTEGER,
    tower_kills INTEGER,
    roshan_kills INTEGER,
    teamfight_participation REAL,
    wards_planted INTEGER,
    camps_stacked INTEGER,
    runes_grabbed INTEGER,
    first_blood INTEGER,
    stuns REAL,
    smokes_used INTEGER,
    madstones INTEGER,
    watchers_taken INTEGER,
    lotus_item_uses INTEGER,
    tormentor_kills INTEGER,
    courier_kills INTEGER,
    created_at INTEGER NOT NULL,
    PRIMARY KEY (match_id, player_slot),
    FOREIGN KEY (match_id) REFERENCES pro_matches(match_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS fantasy_match_events (
    match_id INTEGER PRIMARY KEY,
    duration INTEGER NOT NULL,
    first_blood_time INTEGER,
    first_blood_before_horn INTEGER,
    first_blood_after_ten_minutes INTEGER,
    under_25_minutes INTEGER NOT NULL,
    duration_ends_in_eight INTEGER NOT NULL,
    any_tormentor_death INTEGER NOT NULL,
    fountain_death_proxy INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    FOREIGN KEY (match_id) REFERENCES pro_matches(match_id) ON DELETE CASCADE
);
