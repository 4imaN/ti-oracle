export interface Overview {
  patch: { patch_id: number; name: string; released_at: string | null } | null;
  latest_map: number | null;
  counts: { maps: number; detailed_maps: number; players: number; draft_events: number };
  model: { status: string; test_accuracy: number | null; test_maps: number | null };
}

export interface Team {
  canonical_team: string;
  display_name: string;
  qualification: string;
  active_source_team_id: number | null;
  rating: number | null;
  games: number;
  glicko_rating: number | null;
  glicko_deviation: number | null;
  logo_url: string | null;
}

export interface Prediction {
  team_a: Team;
  team_b: Team;
  best_of: number;
  map_probability: number;
  series_probability: number;
  method: string;
}

export interface HeroMeta {
  hero_id: number;
  hero: string;
  picks: number;
  posterior_rate: number;
  lower_95: number;
  upper_95: number;
  image_url: string | null;
  icon_url: string | null;
}

export interface HeroMetaResponse {
  bracket: number;
  bracket_name: string;
  heroes: HeroMeta[];
}

export interface TrendPoint {
  bracket: number;
  rank: string;
  picks: number;
  win_rate: number | null;
}

export interface HeroTrend {
  hero_id: number;
  hero: string;
  points: TrendPoint[];
}

export interface FantasyPlayer {
  account_id: number;
  name: string | null;
  avatar_url: string | null;
  current_team_id: number | null;
  fantasy_role: number | null;
  inferred_role: "Core" | "Mid" | "Support";
  position_label: string;
  role_source: string;
  team_name: string | null;
  logo_url: string | null;
  maps: number;
  signal_index: number;
  kills: number | null;
  deaths: number | null;
  creep_score: number | null;
  denies: number | null;
  gold_per_min: number | null;
  xp_per_min: number | null;
  tower_kills: number | null;
  roshan_kills: number | null;
  teamfight_participation: number | null;
  wards_planted: number | null;
  camps_stacked: number | null;
  runes_grabbed: number | null;
  first_blood: number | null;
  stuns: number | null;
  smokes_used: number | null;
  courier_kills: number | null;
  lotus_item_uses: number | null;
  tormentor_kills: number | null;
  watchers_taken: number | null;
  madstones: number | null;
  safe_lane_maps: number;
  mid_lane_maps: number;
  off_lane_maps: number;
  last_hits: number | null;
}

export interface FantasyResponse {
  players: FantasyPlayer[];
  method: string;
}

export interface FantasyTitle {
  kind: string;
  key: string;
  bonus_percent: string;
  activation: string;
}

export interface SimulationTeamProbability {
  key: string;
  name: string;
  undefeated: number;
  four_one: number;
  elimination_winners: number;
  elimination_losers: number;
  one_four: number;
  winless: number;
  main_stage: number;
}

export interface SimulationCombination {
  rank: number;
  probability: number;
  teams: Array<{ key: string; name: string }>;
}

export interface RoadSimulation {
  iterations: number;
  seed: number;
  format_assumption: string;
  team_probabilities: SimulationTeamProbability[];
  top_main_stage_combinations: SimulationCombination[];
}

export interface DraftHero {
  hero_id: number;
  hero: string;
  image_url: string | null;
  icon_url: string | null;
}

export interface DraftRecommendation extends DraftHero {
  patch: number;
  score: number;
  matchup_rate: number;
  matchup_games: number;
  enemy_coverage: number;
  meta_rate: number;
  meta_games: number;
  synergy_rate: number;
}

export interface DraftResponse {
  enemy: number[];
  ally: number[];
  recommendations: DraftRecommendation[];
  method: string;
}

export interface UploadResponse {
  filename: string;
  bytes: number;
  image_kind: string;
  status: string;
  message: string;
}

export interface RecognizedBanner {
  role: "Core" | "Mid" | "Support";
  metric: string;
  multiplier: number;
  color: "Red" | "Green" | "Blue";
  slot: number;
  tier: number | null;
  trait: "Fractal" | "Friendly" | "Vampiric" | "Unique" | "Benevolent" | null;
  trait_bonus: number | null;
  recognition_confidence: number;
}

export interface RerollAdvice {
  role: "Core" | "Mid" | "Support";
  slot: number;
  action: "KEEP" | "REROLL STAT" | "RAISE QUALITY" | "REROLL TRAIT";
  reason: string;
  priority: number;
  expected_uplift: number;
}

export interface RecognizedFantasyPlayer extends FantasyPlayer {
  role: "Core" | "Mid" | "Support";
  recognition_confidence: number;
  predicted_points: number;
  banner_fit: number;
  guide_rank: number | null;
  prefix_fit: number;
  team_run_probability: number;
}

export interface ProjectedFantasyPlayer extends FantasyPlayer {
  role: "Core" | "Mid" | "Support";
  predicted_points: number;
  banner_fit: number;
  guide_rank: number | null;
  prefix_fit: number;
  team_run_probability: number;
}

export interface FantasyLineupRecommendation {
  core_team: string;
  mid_team: string;
  support_team: string;
  expected_points: number;
  improvement: number;
  players: ProjectedFantasyPlayer[];
  assumption: string;
}

export interface FantasyScreenshotAnalysis {
  raw_text: string;
  ocr_confidence: number;
  prefix: FantasyTitle | null;
  suffix: FantasyTitle | null;
  players: RecognizedFantasyPlayer[];
  banners: RecognizedBanner[];
  stage: "Group Stage" | "The International";
  expected_emblems_per_banner: number;
  reroll_advice: RerollAdvice[];
  expected_points: number;
  low_points: number;
  high_points: number;
  recommended_lineup: FantasyLineupRecommendation | null;
  recognition_note: string;
  data_basis: string;
}
