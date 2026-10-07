import { createWorker, PSM } from "tesseract.js";
import {
  GUIDE_PAIRS,
  GUIDE_SOURCE,
  METRIC_PRIORITIES,
  STAGE_PATTERNS,
  TRAIT_PRIORITY,
  guideMetricRank,
  guidePrefixRate,
  type GuidePair,
  type GuideRole,
} from "@/lib/fantasy-guide-2026";
import {
  averageRolePoints,
  bannerFantasyPointsPerGame,
  flatFantasyPointsPerGame,
  preferredFantasyMetrics,
  projectedBestSeriesPoints,
} from "@/lib/fantasy-scoring";
import type {
  FantasyPlayer,
  FantasyLineupRecommendation,
  FantasyScreenshotAnalysis,
  FantasyTitle,
  ProjectedFantasyPlayer,
  RecognizedBanner,
  RecognizedFantasyPlayer,
  RerollAdvice,
} from "@/lib/types";

type ProgressCallback = (message: string) => void;
type Role = GuideRole;
type Stage = "Group Stage" | "The International";
type Trait = RecognizedBanner["trait"];
type StatKey =
  | "kills" | "deaths" | "creep_score" | "gold_per_min" | "tower_kills"
  | "roshan_kills" | "teamfight_participation" | "wards_planted" | "camps_stacked"
  | "runes_grabbed" | "first_blood" | "stuns" | "smokes_used" | "madstones"
  | "watchers_taken" | "lotus_item_uses" | "tormentor_kills" | "courier_kills";

const roleSequence: Role[] = ["Core", "Core", "Mid", "Support", "Support"];
const traits = ["Fractal", "Friendly", "Vampiric", "Unique", "Benevolent"] as const;
const metricAliases: Record<string, string[]> = {
  Creeps: ["creeps", "creep score", "cs"],
  GPM: ["gpm", "gold per min"],
  Deaths: ["deaths", "death"],
  Towers: ["towers", "tower kills"],
  Kills: ["kills", "hero kills"],
  Madstones: ["madstones", "madstone collected", "madstone", "ouiens"],
  Teamfight: ["teamfight", "team fight", "teamfight participation"],
  Stuns: ["stuns", "stun duration"],
  Tormentor: ["tormentor", "tormentor kills"],
  Roshan: ["roshan", "roshan kills"],
  "First blood": ["first blood", "firstblood"],
  "Courier kills": ["courier kills", "courier kitts", "counter kitts", "courier"],
  Wards: ["observer wards planted", "obs wards planted", "obs wards", "wards planted", "observers planted"],
  "Camps stacked": ["camps stacked", "camp stacked", "stacks"],
  Lotuses: ["lotuses gained", "lotus gained", "lotusss gained", "totusss canes", "totusesamnin", "orussseans", "ormsseans", "oomsseans", "lotuses", "lotus"],
  Watchers: ["watchers taken", "watchers", "watcher"],
  Runes: ["runes grabbed", "runes", "rune pickups"],
  Smokes: ["smokes used", "smokes", "smoke"],
};
const metricFields: Partial<Record<string, StatKey>> = {
  Creeps: "creep_score", GPM: "gold_per_min", Deaths: "deaths", Towers: "tower_kills",
  Kills: "kills", Madstones: "madstones", Teamfight: "teamfight_participation", Stuns: "stuns",
  Tormentor: "tormentor_kills", Roshan: "roshan_kills", "First blood": "first_blood",
  "Courier kills": "courier_kills", Wards: "wards_planted", "Camps stacked": "camps_stacked",
  Lotuses: "lotus_item_uses", Watchers: "watchers_taken", Runes: "runes_grabbed", Smokes: "smokes_used",
};

function normalize(value: string): string {
  const compact = value.toLowerCase().replace(/[^a-z0-9]+/g, "");
  return ({ kingjungles: "kj", marl1ne: "malr1ne" } as Record<string, string>)[compact] ?? compact;
}

function normalizePlayerHandle(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "");
}

function levenshtein(first: string, second: string): number {
  const previous = Array.from({ length: second.length + 1 }, (_, index) => index);
  for (let row = 1; row <= first.length; row += 1) {
    const current = [row];
    for (let column = 1; column <= second.length; column += 1) {
      current[column] = Math.min(
        current[column - 1] + 1,
        previous[column] + 1,
        previous[column - 1] + (first[row - 1] === second[column - 1] ? 0 : 1),
      );
    }
    previous.splice(0, previous.length, ...current);
  }
  return previous[second.length];
}

function bestTextMatch(text: string, target: string): { score: number; position: number } {
  const source = normalize(text);
  const wanted = normalize(target);
  if (wanted.length < 2) return { score: 0, position: -1 };
  const exact = source.indexOf(wanted);
  if (exact >= 0) return { score: 0.99, position: exact };
  if (source.length < wanted.length - 2) return { score: 0, position: -1 };
  let best = { score: 0, position: -1 };
  for (const size of [wanted.length - 1, wanted.length, wanted.length + 1].filter((value) => value > 1)) {
    for (let index = 0; index <= source.length - size; index += 1) {
      const window = source.slice(index, index + size);
      const score = 1 - levenshtein(window, wanted) / Math.max(window.length, wanted.length);
      if (score > best.score) best = { score, position: index };
    }
  }
  return best;
}

function playerTokenMatch(text: string, target: string): { score: number; position: number; exact: boolean } {
  const wanted = normalizePlayerHandle(target);
  const confusable = (value: string) => value.replace(/[1l|!]/g, "i").replace(/0/g, "o");
  let best = { score: 0, position: -1, exact: false };
  // Two-character handles collide constantly with ordinary OCR fragments (for
  // example `Se` inside SeaGull). Missing is safer than a false roster pick.
  if (wanted.length <= 2) return best;
  for (const match of text.matchAll(/[A-Za-z0-9][A-Za-z0-9_`[\].-]*/g)) {
    const token = normalizePlayerHandle(match[0]);
    if (token === wanted || confusable(token) === confusable(wanted)) {
      return { score: 0.995, position: match.index ?? 0, exact: true };
    }
    if (wanted.length < 4 || Math.abs(token.length - wanted.length) > 1) continue;
    const score = 1 - levenshtein(confusable(token), confusable(wanted)) / Math.max(token.length, wanted.length);
    if (score > best.score) best = { score, position: match.index ?? 0, exact: false };
  }
  return best;
}

function playerMatchThreshold(name: string): number {
  const length = normalizePlayerHandle(name).length;
  if (length <= 3) return 0.995;
  if (length <= 5) return 0.79;
  if (length <= 7) return 0.82;
  return 0.86;
}

function titleMatch(text: string, titles: FantasyTitle[], kind: "prefix" | "suffix"): FantasyTitle | null {
  const titleLine = text.split("\n")[0] ?? text;
  return titles.filter((title) => title.kind === kind)
    .map((title) => ({ title, ...bestTextMatch(titleLine, title.key) }))
    .sort((first, second) => second.score - first.score)
    .find((candidate) => candidate.score >= 0.58)?.title ?? null;
}

function metricFromLine(line: string): { metric: string; confidence: number } | null {
  const source = normalize(line);
  let best: { metric: string; confidence: number; specificity: number } | null = null;
  for (const [metric, aliases] of Object.entries(metricAliases)) {
    for (const alias of aliases) {
      const wanted = normalize(alias);
      const exact = source.includes(wanted);
      const confidence = exact ? 0.99 : bestTextMatch(source, wanted).score;
      if (confidence >= (wanted.length <= 3 ? 0.99 : 0.72)
        && (!best || confidence > best.confidence || (confidence === best.confidence && wanted.length > best.specificity))) {
        best = { metric, confidence, specificity: wanted.length };
      }
    }
  }
  return best ? { metric: best.metric, confidence: best.confidence } : null;
}

function percentage(line: string): number | null {
  const match = line.match(/(?:^|\s)([1-3]?\d{2})(?:[09])?\s*(?:%|[Yy][oO0])(?=\s|$|[,.;])/);
  if (match) {
    const value = Number(match[1]);
    if (value >= 100 && value <= 350) return value;
  }
  // Tesseract occasionally inserts punctuation into banner values, turning
  // 250% into 25.09%. Strip the punctuation, then discard one trailing OCR
  // artifact only when the remaining value is in the valid banner range.
  const noisy = line.match(/(?:^|\s)(\d[\d.,]{1,6})\s*%/);
  if (!noisy) return null;
  const digits = noisy[1].replace(/\D/g, "");
  for (const candidate of [digits, /[09]$/.test(digits) ? digits.slice(0, -1) : ""]) {
    const value = Number(candidate);
    if (value >= 100 && value <= 350) return value;
  }
  return null;
}

function tierNumber(lines: string[]): number | null {
  const tierLine = lines.find((line) => /tier/i.test(line));
  if (!tierLine) return null;
  const qualityBonus = tierLine.match(/\+?\s*(10|30|60|100|150)\s*%/);
  if (qualityBonus) return ({ 10: 1, 30: 2, 60: 3, 100: 4, 150: 5 } as Record<string, number>)[qualityBonus[1]];
  const cleaned = tierLine.replace(/[1|!\]]/g, "I");
  const match = cleaned.match(/tier\s*(iv|v|iii|ii|i|[1-5])/i);
  if (!match) return null;
  const lookup: Record<string, number> = { i: 1, ii: 2, iii: 3, iv: 4, v: 5 };
  return lookup[match[1].toLowerCase()] ?? Number(match[1]);
}

function traitFromBlock(block: string): Trait {
  return traits.find((trait) => normalize(block).includes(normalize(trait))) ?? null;
}

function parseEmblemCrop(text: string, role: Role): RecognizedBanner[] {
  const lines = text.split("\n").map((line) => line.trim()).filter(Boolean);
  const rawCandidates = lines.flatMap((line, index) => {
    if (/tier/i.test(line) || traits.some((trait) => normalize(line).includes(normalize(trait)))) return [];
    const nextLine = lines[index + 1] ?? "";
    const combined = percentage(line) == null && percentage(nextLine) != null && !/tier/i.test(nextLine)
      ? `${line} ${nextLine}`
      : line;
    if (percentage(combined) == null) return [];
    const match = metricFromLine(combined);
    return match ? [{ index, line: combined, match }] : [];
  });
  const seenReadings = new Set<string>();
  const candidates = rawCandidates.filter((candidate) => {
    const signature = `${candidate.match.metric}:${percentage(candidate.line) ?? 100}`;
    if (seenReadings.has(signature)) return false;
    seenReadings.add(signature);
    return true;
  });
  const fiveSlotPattern = STAGE_PATTERNS[role]["The International"];
  const anchors: Array<(typeof candidates)[number] & { slotIndex: number }> = [];
  let nextSlot = 0;
  for (const candidate of candidates) {
    for (let slotIndex = nextSlot; slotIndex < fiveSlotPattern.length; slotIndex += 1) {
      const allowed = METRIC_PRIORITIES[role][fiveSlotPattern[slotIndex]] ?? [];
      if (allowed.includes(candidate.match!.metric)) {
        anchors.push({ ...candidate, slotIndex });
        nextSlot = slotIndex + 1;
        break;
      }
    }
  }
  return anchors.map((anchor, anchorIndex) => {
    const next = anchors[anchorIndex + 1]?.index ?? Math.min(lines.length, anchor.index + 5);
    const blockLines = lines.slice(anchor.index, next);
    const block = blockLines.join(" ");
    const trait = traitFromBlock(block);
    const traitLine = trait ? blockLines.find((line) => normalize(line).includes(normalize(trait))) : null;
    const traitBonusMatch = traitLine?.match(/([+-]?\d{1,3})\s*%/);
    const multiplier = percentage(anchor.line) ?? blockLines.map(percentage).find((value) => value !== null) ?? 100;
    return {
      role,
      metric: anchor.match!.metric,
      multiplier,
      color: fiveSlotPattern[anchor.slotIndex],
      slot: anchor.slotIndex + 1,
      tier: tierNumber(blockLines),
      trait,
      trait_bonus: traitBonusMatch ? Number(traitBonusMatch[1]) : null,
      recognition_confidence: Math.round(anchor.match!.confidence * 100),
    };
  });
}

function mergeBannerReading(preferred: RecognizedBanner, alternate: RecognizedBanner): RecognizedBanner {
  return {
    ...preferred,
    tier: preferred.tier ?? alternate.tier,
    trait: preferred.trait ?? alternate.trait,
    trait_bonus: preferred.trait_bonus ?? alternate.trait_bonus,
  };
}

function sameBannerReading(first: RecognizedBanner, second: RecognizedBanner): boolean {
  return first.metric === second.metric && Math.abs(first.multiplier - second.multiplier) <= 5;
}

function deduplicateBannerReadings(items: RecognizedBanner[]): RecognizedBanner[] {
  const unique: RecognizedBanner[] = [];
  for (const item of [...items].sort((first, second) => first.slot - second.slot)) {
    const duplicateIndex = unique.findIndex((current) => sameBannerReading(current, item));
    if (duplicateIndex < 0) {
      unique.push(item);
      continue;
    }
    const current = unique[duplicateIndex];
    const currentDetail = Number(current.tier != null) + Number(current.trait != null) + Number(current.trait_bonus != null);
    const itemDetail = Number(item.tier != null) + Number(item.trait != null) + Number(item.trait_bonus != null);
    const preferred = item.recognition_confidence > current.recognition_confidence || itemDetail > currentDetail ? item : current;
    const alternate = preferred === item ? current : item;
    unique[duplicateIndex] = { ...mergeBannerReading(preferred, alternate), slot: Math.min(current.slot, item.slot) };
  }
  return unique;
}

function suffixActivationProbability(title: FantasyTitle | null): number {
  if (!title) return 0;
  const key = title.key.toLowerCase();
  if (key === "the lucky") return 0.1;
  if (key === "the underdog") return 0.44;
  if (key === "the clutch") return 0.34;
  if (["the tormented", "the cruel"].includes(key)) return 0.04;
  if (key === "the decisive") return 0.05;
  if (key === "the flayed twins acolyte") return 0.05;
  if (key === "the patient") return 0.01;
  return 0.08;
}

function titleExpectedFactor(player: FantasyPlayer, prefix: FantasyTitle | null, suffix: FantasyTitle | null): { factor: number; prefixFit: number } {
  const prefixFit = guidePrefixRate(player.name, prefix?.key ?? null);
  const prefixBoost = prefix ? Number(prefix.bonus_percent) / 100 * prefixFit / 100 : 0;
  const suffixBoost = suffix ? Number(suffix.bonus_percent) / 100 * suffixActivationProbability(suffix) : 0;
  return { factor: 1 + prefixBoost + suffixBoost, prefixFit };
}

function percentile(player: FantasyPlayer, field: StatKey, pool: FantasyPlayer[]): number {
  const values = pool.map((candidate) => Number(candidate[field] ?? 0)).sort((first, second) => first - second);
  if (values.length < 2 || player[field] == null) return 0.5;
  const value = Number(player[field]);
  const below = values.filter((candidate) => candidate <= value).length;
  const raw = (below - 1) / (values.length - 1);
  return field === "deaths" ? 1 - raw : raw;
}

function guidePairForPlayer(player: FantasyPlayer, role: Role): GuidePair | null {
  const playerName = normalize(player.name ?? "");
  return GUIDE_PAIRS.find((pair) => pair.role === role && pair.players.some((name) => normalize(name) === playerName)) ?? null;
}

function guidePairRank(pair: GuidePair | null): number | null {
  if (!pair) return null;
  return GUIDE_PAIRS.filter((candidate) => candidate.role === pair.role).findIndex((candidate) => candidate === pair) + 1;
}

function guideStatFit(pair: GuidePair | null, role: Role, metric: string): number {
  if (!pair || pair.stats[metric] == null) return 0.5;
  const values = GUIDE_PAIRS.filter((candidate) => candidate.role === role && candidate.stats[metric] != null).map((candidate) => candidate.stats[metric]);
  const lower = Math.min(...values);
  const upper = Math.max(...values);
  return upper === lower ? 0.5 : (pair.stats[metric] - lower) / (upper - lower);
}

function projectPlayer(
  player: FantasyPlayer,
  role: Role,
  banners: RecognizedBanner[],
  prefix: FantasyTitle | null,
  suffix: FantasyTitle | null,
  candidates: FantasyPlayer[],
  teamRunProbabilities: Record<string, number>,
  stage: Stage,
): ProjectedFantasyPlayer {
  const rolePool = candidates.filter((candidate) => candidate.inferred_role === role);
  const roleBanners = banners.filter((banner) => banner.role === role);
  const pair = guidePairForPlayer(player, role);
  let weightedFit = 0;
  for (const banner of roleBanners) {
    const field = metricFields[banner.metric];
    const localFit = field ? percentile(player, field, rolePool) : 0.5;
    const guideFit = guideStatFit(pair, role, banner.metric);
    const fit = guideFit * 0.7 + localFit * 0.3;
    weightedFit += fit;
  }
  const title = titleExpectedFactor(player, prefix, suffix);
  const runProbability = teamRunProbabilities[player.team_name?.toLowerCase() ?? ""] ?? 0.5;
  const pointsPerGame = roleBanners.length
    ? bannerFantasyPointsPerGame(player, roleBanners)
    : flatFantasyPointsPerGame(player, preferredFantasyMetrics(role, stage));
  return {
    ...player,
    role,
    predicted_points: Math.round(projectedBestSeriesPoints(pointsPerGame) * title.factor),
    banner_fit: Math.round((roleBanners.length ? weightedFit / roleBanners.length : 0.5) * 100),
    guide_rank: guidePairRank(pair),
    prefix_fit: title.prefixFit,
    team_run_probability: Math.round(runProbability * 100),
  };
}

function traitScore(banner: RecognizedBanner, stage: Stage): number {
  if (!banner.trait) return 0.45;
  if (banner.trait_bonus != null) {
    if (banner.trait_bonus >= 40) return 0.92;
    if (banner.trait_bonus > 0) return 0.74;
    if (banner.trait_bonus < 0) return 0.12;
  }
  const count = stage === "Group Stage" ? 3 : 5;
  const edge = banner.slot === 1 || banner.slot === count;
  const middle = banner.slot === Math.ceil(count / 2);
  if (banner.trait === "Friendly") return banner.trait_bonus === 0 ? 0.34 : banner.role === "Core" ? 0.46 : 0.82;
  if (banner.trait === "Vampiric") return edge ? 0.9 : 0.58;
  if (banner.trait === "Benevolent") return middle ? 0.86 : 0.5;
  if (banner.trait === "Unique") return 0.42;
  return 0.3;
}

function rerollAdvice(banners: RecognizedBanner[], stage: Stage): RerollAdvice[] {
  return banners.map((banner) => {
    const metricScore = guideMetricRank(banner.role, banner.color, banner.metric);
    const qualityScore = Math.min(1, Math.max(0, (banner.multiplier - 100) / 200));
    const currentTraitScore = traitScore(banner, stage);
    let action: RerollAdvice["action"] = "KEEP";
    let reason = `${banner.metric} is a strong ${banner.color.toLowerCase()} stat for ${banner.role.toLowerCase()}.`;
    let priority = 10;
    let expectedUplift = 0;
    if (metricScore < 0.55) {
      action = "REROLL STAT";
      reason = `${banner.metric} trails ${METRIC_PRIORITIES[banner.role][banner.color]?.slice(0, 2).join(" and ") ?? "the preferred stats"}; stat quality comes first.`;
      priority = 90 + Math.round((0.55 - metricScore) * 10);
      expectedUplift = Math.round((0.86 - metricScore) * Math.max(30, banner.multiplier - 100) * 10) / 10;
    } else if ((banner.tier == null && qualityScore < 0.25) || (banner.tier != null && banner.tier <= 2)) {
      action = "RAISE QUALITY";
      reason = `${banner.metric} is worth keeping, but ${banner.tier ? `Tier ${banner.tier}` : `${banner.multiplier}%`} leaves quality value on the table.`;
      priority = 65;
      const qualityByTier = [0, 10, 30, 60, 100, 150];
      const qualityGap = banner.tier != null ? Math.max(0, 60 - qualityByTier[banner.tier]) : Math.max(0, 180 - banner.multiplier);
      expectedUplift = Math.round(qualityGap * metricScore * 10) / 10;
    } else if (currentTraitScore < 0.48) {
      action = "REROLL TRAIT";
      reason = `${banner.trait ?? "Missing trait"} is low-value in slot ${banner.slot}; ${TRAIT_PRIORITY.slice(0, 3).join(", ")} are safer targets.`;
      priority = 42;
      expectedUplift = Math.round((0.72 - currentTraitScore) * Math.max(20, banner.multiplier - 100) * 10) / 10;
    }
    return { role: banner.role, slot: banner.slot, action, reason, priority, expected_uplift: expectedUplift };
  }).sort((first, second) => second.priority - first.priority || second.expected_uplift - first.expected_uplift);
}

type TeamBlock = { team: string; players: ProjectedFantasyPlayer[]; score: number };

function teamBlocks(
  role: Role,
  playerCount: number,
  candidates: FantasyPlayer[],
  banners: RecognizedBanner[],
  prefix: FantasyTitle | null,
  suffix: FantasyTitle | null,
  eligibleTeams: Set<string>,
  teamRunProbabilities: Record<string, number>,
  stage: Stage,
): TeamBlock[] {
  const grouped = new Map<string, ProjectedFantasyPlayer[]>();
  for (const player of candidates) {
    const team = player.team_name?.trim();
    if (!team || !eligibleTeams.has(team.toLowerCase()) || player.inferred_role !== role || player.maps < 5) continue;
    const projected = projectPlayer(player, role, banners, prefix, suffix, candidates, teamRunProbabilities, stage);
    grouped.set(team, [...(grouped.get(team) ?? []), projected]);
  }
  return Array.from(grouped, ([team, players]) => {
    const selected = players.sort((first, second) => second.predicted_points - first.predicted_points).slice(0, playerCount);
    return { team, players: selected, score: averageRolePoints(selected.map((player) => player.predicted_points)) };
  }).filter((block) => block.players.length === playerCount).sort((first, second) => second.score - first.score).slice(0, 16);
}

function recommendLineup(
  candidates: FantasyPlayer[], banners: RecognizedBanner[], prefix: FantasyTitle | null, suffix: FantasyTitle | null,
  currentPlayers: RecognizedFantasyPlayer[], currentScore: number, eligibleTeamNames: string[],
  teamRunProbabilities: Record<string, number>, stage: Stage,
): FantasyLineupRecommendation | null {
  const eligibleTeams = new Set(eligibleTeamNames.map((team) => team.toLowerCase()));
  const cores = teamBlocks("Core", 2, candidates, banners, prefix, suffix, eligibleTeams, teamRunProbabilities, stage);
  const mids = teamBlocks("Mid", 1, candidates, banners, prefix, suffix, eligibleTeams, teamRunProbabilities, stage);
  const supports = teamBlocks("Support", 2, candidates, banners, prefix, suffix, eligibleTeams, teamRunProbabilities, stage);
  const currentIds = new Set(currentPlayers.map((player) => player.account_id));
  let best: { core: TeamBlock; mid: TeamBlock; support: TeamBlock; score: number } | null = null;
  for (const core of cores) for (const mid of mids) for (const support of supports) {
    if (new Set([core.team, mid.team, support.team]).size < 3) continue;
    const players = [...core.players, ...mid.players, ...support.players];
    if (players.every((player) => currentIds.has(player.account_id))) continue;
    const score = core.score + mid.score + support.score;
    if (!best || score > best.score) best = { core, mid, support, score };
  }
  if (!best) return null;
  return {
    core_team: best.core.team, mid_team: best.mid.team, support_team: best.support.team,
    expected_points: Math.round(best.score * 10) / 10,
    improvement: Math.round((best.score - currentScore) * 10) / 10,
    players: [...best.core.players, ...best.mid.players, ...best.support.players],
    assumption: `Uses the official base stat values, recognized banner multipliers, expected title activation and the top-two-map series rule; player form comes from ${GUIDE_SOURCE.sample} plus current parsed maps.`,
  };
}

export async function analyzeFantasyScreenshot(
  file: File,
  candidates: FantasyPlayer[],
  titles: FantasyTitle[],
  eligibleTeamNames: string[],
  teamRunProbabilities: Record<string, number>,
  onProgress: ProgressCallback,
): Promise<FantasyScreenshotAnalysis> {
  onProgress("Loading local OCR engine…");
  const worker = await createWorker("eng", 1, { logger: (event) => {
    if (event.status === "recognizing text") onProgress(`Reading lineup… ${Math.round(event.progress * 100)}%`);
  } });
  try {
    const full = await worker.recognize(file);
    const text = full.data.text;
    const bitmap = await createImageBitmap(file);
    const regions: Array<{ role: Role; left: number; width: number }> = [
      { role: "Core", left: 0.17, width: 0.145 },
      { role: "Mid", left: 0.505, width: 0.145 },
      { role: "Support", left: 0.81, width: 0.18 },
    ];
    const parsedByRole: Record<Role, RecognizedBanner[]> = { Core: [], Mid: [], Support: [] };
    const bannerOcr: string[] = [];
    onProgress("Identifying emblem stats, tiers and traits…");
    await worker.setParameters({
      tessedit_pageseg_mode: PSM.SINGLE_BLOCK,
      preserve_interword_spaces: "1",
    });
    for (const region of regions) {
      const sourceX = Math.round(bitmap.width * region.left);
      const sourceY = Math.round(bitmap.height * 0.075);
      const sourceWidth = Math.round(bitmap.width * region.width);
      const sourceHeight = Math.round(bitmap.height * 0.64);
      const scale = 4;
      const renderCrop = (binary: boolean) => {
        const canvas = document.createElement("canvas");
        canvas.width = sourceWidth * scale;
        canvas.height = sourceHeight * scale;
        const context = canvas.getContext("2d");
        if (!context) throw new Error("Screenshot canvas is unavailable");
        context.imageSmoothingEnabled = true;
        context.filter = binary ? "none" : "grayscale(1) contrast(1.55)";
        context.drawImage(bitmap, sourceX, sourceY, sourceWidth, sourceHeight, 0, 0, canvas.width, canvas.height);
        if (binary) {
          const pixels = context.getImageData(0, 0, canvas.width, canvas.height);
          for (let index = 0; index < pixels.data.length; index += 4) {
            const luminance = pixels.data[index] * 0.299 + pixels.data[index + 1] * 0.587 + pixels.data[index + 2] * 0.114;
            const value = luminance >= 145 ? 0 : 255;
            pixels.data[index] = value;
            pixels.data[index + 1] = value;
            pixels.data[index + 2] = value;
          }
          context.putImageData(pixels, 0, 0);
        }
        return canvas;
      };
      const primary = await worker.recognize(renderCrop(false));
      let selectedText = primary.data.text;
      const primaryItems = parseEmblemCrop(selectedText, region.role);
      const recovery = await worker.recognize(renderCrop(true));
      const recoveredItems = parseEmblemCrop(recovery.data.text, region.role);
      const useRecoveryOrder = recoveredItems.length > primaryItems.length;
      const positionalItems = useRecoveryOrder ? recoveredItems : primaryItems;
      const supplementalItems = useRecoveryOrder ? primaryItems : recoveredItems;
      const selectedItems = positionalItems.map((item) => {
        const alternate = supplementalItems.find((candidate) => sameBannerReading(candidate, item));
        if (!alternate) return item;
        const preferred = item.recognition_confidence >= alternate.recognition_confidence ? item : alternate;
        return { ...mergeBannerReading(preferred, preferred === item ? alternate : item), slot: item.slot };
      });
      for (const item of supplementalItems) {
        if (selectedItems.some((current) => sameBannerReading(current, item))) continue;
        if (!selectedItems.some((current) => current.slot === item.slot)) selectedItems.push(item);
      }
      selectedItems.sort((first, second) => first.slot - second.slot);
      selectedText = `${selectedText}\n\n--- HIGH-CONTRAST RETRY ---\n${recovery.data.text}`;
      bannerOcr.push(`${region.role.toUpperCase()} BANNER\n${selectedText}`);
      parsedByRole[region.role] = deduplicateBannerReadings(selectedItems);
    }
    bitmap.close();
    const stage: Stage = Math.max(...Object.values(parsedByRole).map((items) => items.length)) >= 4 ? "The International" : "Group Stage";
    const expectedCount = stage === "Group Stage" ? 3 : 5;
    const banners = (Object.entries(parsedByRole) as Array<[Role, RecognizedBanner[]]>).flatMap(([role, items]) => items.map((banner, index) => {
      const slot = stage === "Group Stage" && items.length === 3 ? index + 1 : banner.slot;
      return {
        ...banner,
        slot,
        color: STAGE_PATTERNS[role][stage][slot - 1] ?? "Green",
      };
    }));

    // Card headings often wrap the Mid or second Support name onto another OCR line,
    // so matching only the first line containing two ampersands silently drops them.
    const playerText = text;
    const possibleMatches = candidates.filter((player) => player.name).map((player) => {
      const token = playerTokenMatch(playerText, player.name ?? "");
      return {
        player,
        score: token.score,
        position: token.position,
        tokenExact: token.exact,
      };
    })
      .filter((match, index, rows) => rows.findIndex((row) => normalize(row.player.name ?? "") === normalize(match.player.name ?? "")) === index);
    const expectedByRole: Record<Role, number> = { Core: 2, Mid: 1, Support: 2 };
    const matched = (["Core", "Mid", "Support"] as Role[]).flatMap((role) => {
      const roleMatches = possibleMatches.filter((match) => match.player.inferred_role === role);
      const exactMatches = roleMatches.filter((match) => match.tokenExact)
        .sort((first, second) => first.position - second.position);
      const exactNames = new Set(exactMatches.map((match) => normalize(match.player.name ?? "")));
      const fallbackMatches = roleMatches
        .filter((match) => match.score >= playerMatchThreshold(match.player.name ?? "") && !exactNames.has(normalize(match.player.name ?? "")))
        .sort((first, second) => second.score - first.score || first.position - second.position);
      return [...exactMatches, ...fallbackMatches].slice(0, expectedByRole[role]);
    });
    const prefix = titleMatch(text, titles, "prefix");
    const suffix = titleMatch(text, titles, "suffix");
    const players: RecognizedFantasyPlayer[] = matched.map((match, index) => {
      const inferredRole = match.player.inferred_role;
      const role: Role = inferredRole === "Core" || inferredRole === "Mid" || inferredRole === "Support" ? inferredRole : roleSequence[index] ?? "Support";
      const projection = projectPlayer(match.player, role, banners, prefix, suffix, candidates, teamRunProbabilities, stage);
      return { ...projection, recognition_confidence: Math.round(match.score * 100) };
    });
    const expectedPoints = (["Core", "Mid", "Support"] as Role[]).reduce((total, role) => (
      total + averageRolePoints(players.filter((player) => player.role === role).map((player) => player.predicted_points))
    ), 0);
    const recommendedLineup = recommendLineup(candidates, banners, prefix, suffix, players, expectedPoints, eligibleTeamNames, teamRunProbabilities, stage);
    const completeRoles = (Object.values(parsedByRole).filter((items) => items.length === expectedCount)).length;
    return {
      raw_text: `${text}\n\n--- BANNER OCR ---\n${bannerOcr.join("\n\n")}`, ocr_confidence: Math.round(full.data.confidence), prefix, suffix, players, banners, stage,
      expected_emblems_per_banner: expectedCount,
      reroll_advice: rerollAdvice(banners, stage),
      expected_points: Math.round(expectedPoints * 10) / 10,
      low_points: Math.round(expectedPoints * 0.82 * 10) / 10,
      high_points: Math.round(expectedPoints * 1.18 * 10) / 10,
      recommended_lineup: recommendedLineup,
      recognition_note: `${players.length} of 5 players matched; ${completeRoles} of 3 banners yielded all ${expectedCount} ${stage.toLowerCase()} emblems. Confirm low-confidence OCR before rerolling.`,
      data_basis: `Official 2026 base stat values applied to locally parsed 2026 OpenDota map averages; banner selection priors use ${GUIDE_SOURCE.sample}, published ${GUIDE_SOURCE.published}. Final Valve scoring uses the period's observed top-two maps and best series.`,
    };
  } finally {
    await worker.terminate();
  }
}
