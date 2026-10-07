"use client";

import { useMemo, useState } from "react";
import {
  GUIDE_PAIRS,
  GUIDE_SOURCE,
  METRIC_PRIORITIES,
  STAGE_PATTERNS,
  type EmblemColor,
  type GuideRole,
} from "@/lib/fantasy-guide-2026";
import {
  FANTASY_SCORING_RULES,
  flatFantasyPointsPerGame,
  preferredFantasyMetrics,
  projectedBestSeriesPoints,
  type FantasyStage,
} from "@/lib/fantasy-scoring";
import type { FantasyPlayer } from "@/lib/types";

const roles: GuideRole[] = ["Core", "Mid", "Support"];
const stages: FantasyStage[] = ["Group Stage", "The International"];
const methodReference = {
  name: "thewondercow · 2026 Fantasy expected-value breakdown",
  url: "https://www.youtube.com/watch?v=mloprLWAAJc",
};
const purgeReferences = [
  {
    name: "Purge · TI 2026 Fantasy guide",
    url: "https://www.youtube.com/watch?v=sbsSf8t4qFU",
  },
  {
    name: "Purge · TI 2026 prediction board",
    url: "https://www.youtube.com/watch?v=Vdf85DFFsmQ&t=80s",
  },
];

function quantile(values: number[], position: number): number {
  if (!values.length) return 0;
  const ordered = [...values].sort((first, second) => first - second);
  const index = (ordered.length - 1) * position;
  const lower = Math.floor(index);
  const upper = Math.ceil(index);
  if (lower === upper) return ordered[lower];
  return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower);
}

function metricRows(role: GuideRole) {
  const pairs = GUIDE_PAIRS.filter((pair) => pair.role === role);
  const seen = new Set<string>();
  const metrics: Array<{ metric: string; color: EmblemColor }> = [];
  for (const color of ["Red", "Green", "Blue"] as EmblemColor[]) {
    for (const metric of METRIC_PRIORITIES[role][color] ?? []) {
      if (!seen.has(metric)) {
        seen.add(metric);
        metrics.push({ metric, color });
      }
    }
  }
  return metrics.map(({ metric, color }) => {
    const available = pairs.filter((pair) => pair.stats[metric] != null);
    const values = available.map((pair) => pair.stats[metric]);
    const leader = [...available].sort((first, second) => second.stats[metric] - first.stats[metric])[0];
    return {
      metric,
      color,
      median: Math.round(quantile(values, 0.5)),
      elite: Math.round(quantile(values, 0.75)),
      leader: leader?.players.join(" + ") ?? "—",
      peak: leader?.stats[metric] ?? 0,
    };
  });
}

function preferredRecipe(role: GuideRole, stage: FantasyStage): Array<{ metric: string; color: EmblemColor }> {
  const pattern = STAGE_PATTERNS[role][stage];
  return (["Red", "Green", "Blue"] as EmblemColor[]).flatMap((color) => {
    const count = pattern.filter((slotColor) => slotColor === color).length;
    return (METRIC_PRIORITIES[role][color] ?? []).slice(0, count).map((metric) => ({ color, metric }));
  });
}

function topPlayersForRole(players: FantasyPlayer[], eligibleTeams: string[], role: GuideRole, stage: FantasyStage) {
  const eligible = new Set(eligibleTeams.map((team) => team.toLowerCase()));
  const metrics = preferredFantasyMetrics(role, stage);
  return players
    .filter((player) => player.inferred_role === role && player.maps >= 3)
    .filter((player) => eligible.size === 0 || eligible.has((player.team_name ?? "").toLowerCase()))
    .map((player) => {
      const perGame = flatFantasyPointsPerGame(player, metrics);
      return { player, perGame, projected: projectedBestSeriesPoints(perGame) };
    })
    .sort((first, second) => second.projected - first.projected)
    .slice(0, 5);
}

function points(value: number): string {
  return Math.round(value).toLocaleString();
}

export function FantasyEvLab({ players, eligibleTeams }: { players: FantasyPlayer[]; eligibleTeams: string[] }) {
  const [role, setRole] = useState<GuideRole>("Core");
  const [stage, setStage] = useState<FantasyStage>("Group Stage");
  const rows = useMemo(() => metricRows(role), [role]);
  const preferred = useMemo(() => preferredRecipe(role, stage), [role, stage]);
  const leaders = useMemo(() => Object.fromEntries(
    roles.map((item) => [item, topPlayersForRole(players, eligibleTeams, item, stage)]),
  ) as Record<GuideRole, ReturnType<typeof topPlayersForRole>>, [players, eligibleTeams, stage]);
  const rolePairs = GUIDE_PAIRS.filter((pair) => pair.role === role);
  const topAverage = [...rolePairs].sort((first, second) => second.average - first.average)[0];
  const topCeiling = [...rolePairs].sort((first, second) => second.top - first.top)[0];
  const largestMedian = Math.max(...rows.map((row) => row.median), 1);

  return (
    <section className="fantasy-ev-lab" aria-labelledby="fantasy-ev-heading">
      <header className="ev-head">
        <div>
          <span className="section-index">EXPECTED VALUE / ROLE MODEL</span>
          <h3 id="fantasy-ev-heading">See where the points come from.</h3>
        </div>
        <p>Compare banner stats inside the correct role and stage before choosing a player. Higher values are useful priors—not guaranteed Valve points.</p>
      </header>

      <div className="ev-controls">
        <div className="ev-segment" aria-label="Fantasy role">
          {roles.map((item) => <button type="button" className={role === item ? "active" : ""} aria-pressed={role === item} onClick={() => setRole(item)} key={item}>{item}</button>)}
        </div>
        <div className="ev-segment stage" aria-label="Fantasy stage">
          {stages.map((item) => <button type="button" className={stage === item ? "active" : ""} aria-pressed={stage === item} onClick={() => setStage(item)} key={item}>{item === "Group Stage" ? "Groups · 3" : "TI · 5"}</button>)}
        </div>
      </div>

      <div className="ev-summary">
        <article>
          <span>Top average {role.toLowerCase()}</span>
          <strong>{topAverage?.players.join(" + ") ?? "—"}</strong>
          <b>{topAverage?.average.toLocaleString() ?? "—"}<small>guide average</small></b>
        </article>
        <article>
          <span>Highest observed ceiling</span>
          <strong>{topCeiling?.players.join(" + ") ?? "—"}</strong>
          <b>{topCeiling?.top.toLocaleString() ?? "—"}<small>guide ceiling</small></b>
        </article>
        <article className="banner-recipe">
          <span>Top average banner · {stage}</span>
          <div>{preferred.map((item, index) => <b className={`recipe-${item.color.toLowerCase()}`} key={`${item.color}-${index}`}><i>{item.color[0]}</i>{item.metric}</b>)}</div>
        </article>
      </div>

      <div className="fantasy-rule-flow" aria-label="Fantasy period scoring sequence">
        {[
          ["01", "Period begins", "Roster snapshot locks"],
          ["02", "Each map", "Score each player"],
          ["03", "Each role", "Average its players"],
          ["04", "Each series", "Keep top two maps"],
          ["05", "Whole period", "Keep best series"],
        ].map(([number, title, detail]) => <div key={number}><i>{number}</i><span>{title}</span><strong>{detail}</strong></div>)}
      </div>

      <section className="role-leaderboards" aria-label={`Top projected Fantasy players for ${stage}`}>
        {roles.map((leaderRole) => (
          <article className="role-leaderboard" key={leaderRole}>
            <header>
              <div><span>{leaderRole}</span><strong>Top projected players</strong></div>
              <small>{stage === "Group Stage" ? "3-stat banner" : "5-stat banner"}</small>
            </header>
            <div className="leader-metrics">
              {preferredFantasyMetrics(leaderRole, stage).map((metric) => <span key={metric}>{metric}</span>)}
            </div>
            <div className="projected-player-list">
              {leaders[leaderRole].length ? leaders[leaderRole].map(({ player, perGame, projected }, index) => (
                <div className={`projected-player ${index === 0 ? "leader" : ""}`} key={player.account_id}>
                  <i>{String(index + 1).padStart(2, "0")}</i>
                  {player.avatar_url ? <img src={player.avatar_url} alt="" loading="lazy" /> : <span className="projected-fallback">{player.name?.[0] ?? "?"}</span>}
                  <div><strong>{player.name ?? "Unknown"}</strong><small>{player.team_name ?? "Unattached"} · {player.maps} maps · {points(perGame)}/map</small></div>
                  <b>{points(projected)}<small>projected pts</small></b>
                </div>
              )) : <p className="leaderboard-empty">Loading eligible player data…</p>}
            </div>
          </article>
        ))}
      </section>

      <details className="scoring-manifest">
        <summary><span>Official base scoring formula</span><b>{FANTASY_SCORING_RULES.length} tracked stats</b></summary>
        <div className="scoring-formula-grid">
          {FANTASY_SCORING_RULES.map((rule) => <div key={rule.metric}><span>{rule.label}</span><strong>{rule.formula}</strong></div>)}
        </div>
        <p>Rankings use each role&apos;s preferred stats at a flat 100% banner and two average maps. Uploaded banners replace that flat assumption with their recognized multipliers and coach-title expected value. Valve&apos;s final result can differ because it uses the actual top two maps and best series in the locked period.</p>
      </details>

      <div className="ev-table-wrap">
        <div className="ev-table-head"><span>Emblem stat</span><span>Guide median</span><span>Elite quartile</span><span>Best observed pair</span></div>
        <div className="ev-table">
          {rows.map((row, index) => (
            <article key={row.metric} className={`ev-row ev-${row.color.toLowerCase()}`}>
              <div className="ev-metric"><i>{String(index + 1).padStart(2, "0")}</i><span>{row.color}</span><strong>{row.metric}</strong></div>
              <div className="ev-value"><b>{row.median.toLocaleString()}</b><i style={{ width: `${row.median / largestMedian * 100}%` }} /></div>
              <b className="ev-elite">{row.elite.toLocaleString()}</b>
              <div className="ev-leader"><strong>{row.leader}</strong><small>{row.peak.toLocaleString()} peak</small></div>
            </article>
          ))}
        </div>
      </div>

      <footer className="ev-source">
        <span>Numbers: <a href={GUIDE_SOURCE.url} target="_blank" rel="noreferrer">{GUIDE_SOURCE.sample} prior ↗</a></span>
        <span>Method reference: <a href={methodReference.url} target="_blank" rel="noreferrer">{methodReference.name} ↗</a></span>
        {purgeReferences.map((reference) => <span key={reference.url}>Expert cross-check: <a href={reference.url} target="_blank" rel="noreferrer">{reference.name} ↗</a></span>)}
        <span>The video&apos;s claimed data volume is not merged into this local model.</span>
        <span>Creator picks are qualitative, low-weight priors; match, roster, draft, and player-stat data remain authoritative.</span>
      </footer>
    </section>
  );
}
