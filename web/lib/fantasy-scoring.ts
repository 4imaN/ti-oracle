import { METRIC_PRIORITIES, STAGE_PATTERNS, type EmblemColor, type GuideRole } from "@/lib/fantasy-guide-2026";
import type { FantasyPlayer, RecognizedBanner } from "@/lib/types";

export type FantasyStage = "Group Stage" | "The International";
export type FantasyMetric =
  | "Kills" | "Deaths" | "Creeps" | "GPM" | "Madstones" | "Towers"
  | "Wards" | "Camps stacked" | "Runes" | "Watchers" | "Lotuses"
  | "Roshan" | "Teamfight" | "Stuns" | "Tormentor" | "Courier kills"
  | "First blood" | "Smokes";

export const FANTASY_SCORING_RULES: Array<{ metric: FantasyMetric; label: string; formula: string }> = [
  { metric: "Kills", label: "Kills", formula: "+107 per kill" },
  { metric: "Deaths", label: "Deaths", formula: "1,950 starting · −195 per death" },
  { metric: "Creeps", label: "Creep score", formula: "+3 per last hit or deny" },
  { metric: "GPM", label: "GPM", formula: "GPM ×2" },
  { metric: "Madstones", label: "Madstone collected", formula: "+13 each" },
  { metric: "Towers", label: "Tower kills", formula: "+352 per last hit" },
  { metric: "Wards", label: "Wards placed", formula: "+117 per observer ward" },
  { metric: "Camps stacked", label: "Camps stacked", formula: "+234 each" },
  { metric: "Runes", label: "Runes grabbed", formula: "+141 bottled or taken" },
  { metric: "Watchers", label: "Watchers taken", formula: "+147 captured" },
  { metric: "Lotuses", label: "Lotuses grabbed", formula: "+176 taken" },
  { metric: "Roshan", label: "Roshan kills", formula: "+1,172 each" },
  { metric: "Teamfight", label: "Teamfight participation", formula: "Up to 2,124" },
  { metric: "Stuns", label: "Stuns", formula: "+10 per second" },
  { metric: "Tormentor", label: "Tormentor kills", formula: "+879 each" },
  { metric: "Courier kills", label: "Courier kills", formula: "+703 each" },
  { metric: "First blood", label: "First blood", formula: "+1,934 when claimed" },
  { metric: "Smokes", label: "Smokes used", formula: "+293 each" },
];

function value(player: FantasyPlayer, field: keyof FantasyPlayer): number {
  return Number(player[field] ?? 0);
}

export function fantasyStatPoints(player: FantasyPlayer, metric: FantasyMetric): number {
  switch (metric) {
    case "Kills": return value(player, "kills") * 107;
    case "Deaths": return 1950 - value(player, "deaths") * 195;
    case "Creeps": return (value(player, "creep_score") + value(player, "denies")) * 3;
    case "GPM": return value(player, "gold_per_min") * 2;
    case "Madstones": return value(player, "madstones") * 13;
    case "Towers": return value(player, "tower_kills") * 352;
    case "Wards": return value(player, "wards_planted") * 117;
    case "Camps stacked": return value(player, "camps_stacked") * 234;
    case "Runes": return value(player, "runes_grabbed") * 141;
    case "Watchers": return value(player, "watchers_taken") * 147;
    case "Lotuses": return value(player, "lotus_item_uses") * 176;
    case "Roshan": return value(player, "roshan_kills") * 1172;
    case "Teamfight": return Math.min(1, Math.max(0, value(player, "teamfight_participation"))) * 2124;
    case "Stuns": return value(player, "stuns") * 10;
    case "Tormentor": return value(player, "tormentor_kills") * 879;
    case "Courier kills": return value(player, "courier_kills") * 703;
    case "First blood": return value(player, "first_blood") * 1934;
    case "Smokes": return value(player, "smokes_used") * 293;
  }
}

export function preferredFantasyMetrics(role: GuideRole, stage: FantasyStage): FantasyMetric[] {
  const pattern = STAGE_PATTERNS[role][stage];
  return (["Red", "Green", "Blue"] as EmblemColor[]).flatMap((color) => {
    const count = pattern.filter((slotColor) => slotColor === color).length;
    return (METRIC_PRIORITIES[role][color] ?? []).slice(0, count) as FantasyMetric[];
  });
}

export function flatFantasyPointsPerGame(player: FantasyPlayer, metrics: FantasyMetric[]): number {
  return metrics.reduce((total, metric) => total + fantasyStatPoints(player, metric), 0);
}

export function bannerFantasyPointsPerGame(player: FantasyPlayer, banners: RecognizedBanner[]): number {
  return banners.reduce((total, banner) => (
    total + fantasyStatPoints(player, banner.metric as FantasyMetric) * banner.multiplier / 100
  ), 0);
}

export function projectedBestSeriesPoints(pointsPerGame: number): number {
  return pointsPerGame * 2;
}

export function averageRolePoints(points: number[]): number {
  return points.length ? points.reduce((total, item) => total + item, 0) / points.length : 0;
}
