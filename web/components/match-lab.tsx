"use client";

import { useEffect, useMemo, useState } from "react";
import { getJSON, percent } from "@/lib/api";
import type { Prediction, RoadSimulation, SimulationTeamProbability, Team } from "@/lib/types";

type OutcomeField = "undefeated" | "four_one" | "elimination_winners" | "elimination_losers" | "one_four" | "winless";
type ProjectionSlot = {
  field: OutcomeField;
  outcome: string;
  advancing: boolean;
  team: SimulationTeamProbability;
};

const projectionLanes: Array<{ field: OutcomeField; outcome: string; count: number; advancing: boolean }> = [
  { field: "undefeated", outcome: "4–0", count: 1, advancing: true },
  { field: "four_one", outcome: "4–1", count: 2, advancing: true },
  { field: "elimination_winners", outcome: "Elimination winner", count: 5, advancing: true },
  { field: "elimination_losers", outcome: "Elimination loser", count: 5, advancing: false },
  { field: "one_four", outcome: "1–4", count: 2, advancing: false },
  { field: "winless", outcome: "0–4", count: 1, advancing: false },
];

function projectedFinish(road: RoadSimulation | null): ProjectionSlot[] {
  if (!road) return [];
  const slots = projectionLanes.flatMap((lane) => Array.from({ length: lane.count }, () => lane));
  const teams = road.team_probabilities;
  if (teams.length !== slots.length || teams.length > 20) return [];

  const stateCount = 1 << teams.length;
  const scores = new Float64Array(stateCount);
  scores.fill(Number.NEGATIVE_INFINITY);
  scores[0] = 0;
  const parentTeam = new Int16Array(stateCount);
  parentTeam.fill(-1);

  for (let mask = 0; mask < stateCount; mask += 1) {
    if (!Number.isFinite(scores[mask])) continue;
    let assigned = 0;
    for (let value = mask; value; value &= value - 1) assigned += 1;
    if (assigned >= slots.length) continue;
    const field = slots[assigned].field;
    for (let teamIndex = 0; teamIndex < teams.length; teamIndex += 1) {
      const bit = 1 << teamIndex;
      if (mask & bit) continue;
      const nextMask = mask | bit;
      const score = scores[mask] + Math.log(Math.max(teams[teamIndex][field], 1e-9));
      if (score > scores[nextMask]) {
        scores[nextMask] = score;
        parentTeam[nextMask] = teamIndex;
      }
    }
  }

  const selectedTeams = new Array<SimulationTeamProbability>(slots.length);
  let mask = stateCount - 1;
  for (let slotIndex = slots.length - 1; slotIndex >= 0; slotIndex -= 1) {
    const teamIndex = parentTeam[mask];
    if (teamIndex < 0) return [];
    selectedTeams[slotIndex] = teams[teamIndex];
    mask ^= 1 << teamIndex;
  }
  return slots.map((slot, index) => ({ ...slot, team: selectedTeams[index] }));
}

export function MatchLab() {
  const [teams, setTeams] = useState<Team[]>([]);
  const [road, setRoad] = useState<RoadSimulation | null>(null);
  const [teamA, setTeamA] = useState("");
  const [teamB, setTeamB] = useState("");
  const [bestOf, setBestOf] = useState(3);
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [method, setMethod] = useState("Choose two teams to calculate a matchup.");

  useEffect(() => {
    getJSON<Team[]>("/api/teams").then((rows) => {
      setTeams(rows);
      setTeamA(rows[0]?.canonical_team ?? "");
      setTeamB(rows[1]?.canonical_team ?? "");
    }).catch(() => setTeams([]));
    getJSON<RoadSimulation>("/api/simulation/road").then(setRoad).catch(() => setRoad(null));
  }, []);

  useEffect(() => {
    if (!teamA || !teamB) return;
    if (teamA === teamB) {
      return;
    }
    const controller = new AbortController();
    getJSON<Prediction>(`/api/predict?team_a=${encodeURIComponent(teamA)}&team_b=${encodeURIComponent(teamB)}&best_of=${bestOf}`, { signal: controller.signal })
      .then((result) => {
        setPrediction(result);
        setMethod(result.method);
      })
      .catch((error: Error) => {
        if (error.name !== "AbortError") setMethod(error.message);
      });
    return () => controller.abort();
  }, [teamA, teamB, bestOf]);

  const displayPrediction = teamA !== teamB ? prediction : null;
  const displayMethod = teamA === teamB ? "Choose two different teams." : method;
  const series = displayPrediction?.series_probability ?? 0.5;
  const favored = displayPrediction
    ? Math.abs(series - 0.5) < 0.06
      ? "Toss-up"
      : series > 0.5 ? displayPrediction.team_a.display_name : displayPrediction.team_b.display_name
    : teamA === teamB ? "Invalid" : "Waiting";
  const finishSlots = useMemo(() => projectedFinish(road), [road]);
  const topSlots = finishSlots.slice(0, 8);
  const bottomSlots = finishSlots.slice(8);

  function teamLogo(slot: ProjectionSlot): string | null {
    return teams.find((team) => team.canonical_team === slot.team.key)?.logo_url
      ?? teams.find((team) => team.display_name.toLowerCase() === slot.team.name.toLowerCase())?.logo_url
      ?? null;
  }

  function stageCard(slot: ProjectionSlot, index: number) {
    const logo = teamLogo(slot);
    return (
      <article className={`stage-card ${slot.advancing ? "advancing" : "eliminated"}`} key={slot.team.key}>
        <span className="stage-card-index">{String(index + 1).padStart(2, "0")}</span>
        <span className="stage-card-odds">{percent(slot.team[slot.field])}</span>
        <div className="stage-logo">
          {logo ? <img src={logo} alt="" loading="lazy" /> : <span>{slot.team.name.slice(0, 2)}</span>}
        </div>
        <div className="stage-card-copy">
          <strong>{slot.team.name}</strong>
          <small>{slot.outcome} · {percent(slot.team.main_stage)} main stage</small>
        </div>
      </article>
    );
  }

  return (
    <section className="workspace" id="teams">
      <div className="section-head">
        <div><span className="section-index">02 / TEAM PREDICTIONS</span><h2>Who advances.<br />Who wins.</h2></div>
        <p>Choose any two TI teams for map and series odds. The qualification board below predicts who reaches the main stage.</p>
      </div>

      <div className="match-grid">
        <div className="power-board">
          <div className="board-head"><span>TI field</span><span>Glicko / uncertainty</span></div>
          <ol className="team-list">
            {teams.map((team, index) => (
              <li className="team-row" key={team.canonical_team}>
                <span className="rank">{String(index + 1).padStart(2, "0")}</span>
                {team.logo_url ? <img src={team.logo_url} alt="" loading="lazy" /> : <span />}
                <div><span className="team-name">{team.display_name}</span><small>{team.qualification} · {team.games} rated maps</small></div>
                <div className="rating"><strong>{team.glicko_rating?.toFixed(0) ?? "—"}</strong><small>± {team.glicko_deviation?.toFixed(0) ?? "—"}</small></div>
              </li>
            ))}
          </ol>
        </div>
        <div className="versus-desk">
          <div className="versus-head">
            <span>Matchup console</span>
            <select value={bestOf} onChange={(event) => setBestOf(Number(event.target.value))} aria-label="Series length">
              <option value={1}>Best of 1</option><option value={3}>Best of 3</option><option value={5}>Best of 5</option>
            </select>
          </div>
          <div className="selectors">
            <label>Team A<select value={teamA} onChange={(event) => setTeamA(event.target.value)}>{teams.map((team) => <option value={team.canonical_team} key={team.canonical_team}>{team.display_name}</option>)}</select></label>
            <span className="versus">VS</span>
            <label>Team B<select value={teamB} onChange={(event) => setTeamB(event.target.value)}>{teams.map((team) => <option value={team.canonical_team} key={team.canonical_team}>{team.display_name}</option>)}</select></label>
          </div>
          <div className="odds-bar" aria-label="Predicted series probability">
            <div className="odds-fill" style={{ width: `${series * 100}%` }} />
            <span>{displayPrediction ? percent(series, 0) : "—"}</span><span>{displayPrediction ? percent(1 - series, 0) : "—"}</span>
          </div>
          <div className="prediction-output">
            <div><span>Map edge</span><strong>{displayPrediction ? percent(displayPrediction.map_probability) : "—"}</strong></div>
            <div><span>Series edge</span><strong>{displayPrediction ? percent(series) : "—"}</strong></div>
            <div><span>Signal</span><strong>{favored}</strong></div>
          </div>
          <p className="method-note">{displayMethod}</p>
        </div>
      </div>

      <div className="road-sim">
        <div className="road-head">
          <div><span className="section-index">ROAD TO THE INTERNATIONAL</span><h3>{road?.iterations.toLocaleString() ?? "—"} possible roads.</h3></div>
          <p>Monte Carlo series outcomes from current Glicko ratings. Initial groups are seeded until the organizer publishes official assignments.</p>
        </div>
        <div className="stage-scroll" role="region" aria-label="Predicted group-stage finishing board" tabIndex={0}>
          <div className="stage-prediction">
            <div className="stage-group-labels top">
              <div className="group-four-zero"><b>4–0</b><span>One undefeated team</span></div>
              <div className="group-four-one"><b>4–1</b><span>Two teams with four wins</span></div>
              <div className="group-elim-winner"><b>Elimination round winner</b><span>Five teams advance through elimination</span></div>
            </div>
            <div className="stage-card-grid">
              {topSlots.length ? topSlots.map(stageCard) : Array.from({ length: 8 }, (_, index) => <div className="stage-card loading-block" key={index} />)}
            </div>
            <div className="stage-card-grid lower">
              {bottomSlots.length ? bottomSlots.map((slot, index) => stageCard(slot, index + 8)) : Array.from({ length: 8 }, (_, index) => <div className="stage-card loading-block" key={index} />)}
            </div>
            <div className="stage-group-labels bottom">
              <div className="group-elim-loser"><span>Five teams leave in elimination</span><b>Elimination round loser</b></div>
              <div className="group-one-four"><span>Two teams with one win</span><b>1–4</b></div>
              <div className="group-zero-four"><span>One winless team</span><b>0–4</b></div>
            </div>
          </div>
        </div>
        <div className="stage-legend">
          <span><i className="advance-key" />Top row advances to the main stage</span>
          <span><i className="exit-key" />Bottom row exits the tournament</span>
          <span>Card percentage = chance of that exact finish</span>
        </div>
        <div className="stage-combinations combination-board">
          <div className="board-head"><span>Top 10 exact main-stage combinations</span><span>Joint probability</span></div>
          <ol id="combination-list">{road?.top_main_stage_combinations.map((combo) => (
            <li className="combo-row" key={combo.rank}>
              <span className="rank">{String(combo.rank).padStart(2, "0")}</span>
              <p>{combo.teams.map((team, index) => <span key={team.key}><b>{index < 3 ? team.name : ""}</b>{index >= 3 ? team.name : ""}{index < combo.teams.length - 1 ? " · " : ""}</span>)}</p>
              <b>{percent(combo.probability, 2)}</b>
            </li>
          ))}</ol>
        </div>
      </div>
    </section>
  );
}
