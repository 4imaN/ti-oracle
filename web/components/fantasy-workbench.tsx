"use client";

import { DragEvent, useEffect, useRef, useState } from "react";
import { FantasyEvLab } from "@/components/fantasy-ev-lab";
import { analyzeFantasyScreenshot } from "@/lib/fantasy-analyzer";
import { getJSON, integer } from "@/lib/api";
import type { FantasyResponse, FantasyScreenshotAnalysis, FantasyTitle, RoadSimulation, Team, UploadResponse } from "@/lib/types";

export function FantasyWorkbench() {
  const [fantasy, setFantasy] = useState<FantasyResponse | null>(null);
  const [titles, setTitles] = useState<FantasyTitle[]>([]);
  const [eligibleTeams, setEligibleTeams] = useState<string[]>([]);
  const [teamRunProbabilities, setTeamRunProbabilities] = useState<Record<string, number>>({});
  const [uploadMessage, setUploadMessage] = useState("");
  const [analysis, setAnalysis] = useState<FantasyScreenshotAnalysis | null>(null);
  const [preview, setPreview] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const sourcePortraitPositions = ["2% 80%", "9% 80%", "39% 80%", "74% 80%", "85% 80%"];

  useEffect(() => {
    getJSON<FantasyResponse>("/api/fantasy/players?limit=500").then(setFantasy).catch(() => setFantasy(null));
    getJSON<FantasyTitle[]>("/api/fantasy/titles").then(setTitles).catch(() => setTitles([]));
    getJSON<Team[]>("/api/teams").then((teams) => setEligibleTeams(teams.map((team) => team.display_name))).catch(() => setEligibleTeams([]));
    getJSON<RoadSimulation>("/api/simulation/road").then((road) => setTeamRunProbabilities(Object.fromEntries(
      road.team_probabilities.map((team) => [team.name.toLowerCase(), team.main_stage]),
    ))).catch(() => setTeamRunProbabilities({}));
  }, []);

  async function upload(file?: File) {
    if (!file) return;
    if (!fantasy || titles.length === 0 || eligibleTeams.length === 0) {
      setUploadMessage("Player and title data are still loading. Try the screenshot again in a moment.");
      return;
    }
    if (preview) URL.revokeObjectURL(preview);
    setPreview(URL.createObjectURL(file));
    setAnalysis(null);
    setAnalyzing(true);
    setUploadMessage("Validating screenshot…");
    const body = new FormData();
    body.append("file", file);
    try {
      const result = await getJSON<UploadResponse>("/api/upload/fantasy", { method: "POST", body });
      setUploadMessage(`${result.filename} · ${(result.bytes / 1024).toFixed(0)} KB`);
      const recognized = await analyzeFantasyScreenshot(file, fantasy.players, titles, eligibleTeams, teamRunProbabilities, setUploadMessage);
      setAnalysis(recognized);
      setUploadMessage("Analysis complete");
    } catch (error) {
      setUploadMessage((error as Error).message);
    } finally {
      setAnalyzing(false);
    }
  }

  function drop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragging(false);
    void upload(event.dataTransfer.files[0]);
  }

  return (
    <section className="fantasy-section" id="fantasy">
      <div className="section-head fantasy-head">
        <div><span className="section-index">03 / FANTASY WORKBENCH</span><h2>Build around the title.<br />Then price the player.</h2></div>
        <p>{fantasy?.method ?? "Loading player signal model…"} Title-aware scoring activates after client rules are verified.</p>
      </div>
      <div className="fantasy-grid">
        <div className="player-board">
          <div className="board-head"><span>Player signal</span><span>Recent parsed maps</span></div>
          <div className="player-list">
            {fantasy?.players.slice(0, 12).map((player) => (
              <article className="player-entry" key={player.account_id}>
                {player.avatar_url ? <img src={player.avatar_url} alt="" loading="lazy" /> : <span className="portrait-fallback">{player.name?.slice(0, 1) ?? "?"}</span>}
                <div><strong>{player.name ?? "Unknown"}</strong><small>{player.position_label} · {player.team_name ?? "Unattached"} · {player.maps} maps</small></div>
                <div className="signal"><b>{player.signal_index.toFixed(1)}</b><span>signal</span></div>
              </article>
            ))}
          </div>
        </div>
        <div className="upload-bay">
          <span className="upload-number">F / 26</span>
          <h3>Bring your lineup.</h3>
          <p>Upload the in-game Fantasy screen. Local OCR reads player names, title modifiers and each role&apos;s War Banners, then matches them against current roster data.</p>
          <label className={`drop-zone ${dragging ? "drag" : ""}`} onDragEnter={(event) => { event.preventDefault(); setDragging(true); }} onDragOver={(event) => event.preventDefault()} onDragLeave={() => setDragging(false)} onDrop={drop}>
            <input ref={inputRef} disabled={analyzing} type="file" accept="image/png,image/jpeg,image/webp" onChange={(event) => void upload(event.target.files?.[0])} />
            <span className="drop-icon">{analyzing ? "◌" : "↥"}</span><b>{analyzing ? "Analyzing lineup" : "Drop screenshot or browse"}</b><small>Runs locally in your browser · PNG, JPEG or WebP</small>
          </label>
          {uploadMessage && <div className="upload-result" role="status">{uploadMessage}</div>}
          <div className="title-ticker">
            {titles.slice(0, 8).map((title) => <span className="title-chip" title={title.activation} key={`${title.kind}-${title.key}`}><b>{title.key}</b> +{title.bonus_percent}%</span>)}
          </div>
        </div>
      </div>
      <FantasyEvLab players={fantasy?.players ?? []} eligibleTeams={eligibleTeams} />
      {analysis && (
        <div className="fantasy-analysis" aria-live="polite">
          <div className="analysis-visual">
            {preview && <img src={preview} alt="Uploaded Fantasy selection" />}
            <div className="analysis-caption"><span>Source frame</span><b>{analysis.ocr_confidence}% OCR confidence</b></div>
          </div>
          <div className="analysis-report">
            <div className="analysis-title-row">
              <div>
                <span className="section-index">RECOGNIZED LOADOUT</span>
                <h3>{analysis.prefix?.key ?? "Unknown prefix"} <em>{analysis.suffix?.key ?? "unknown suffix"}</em></h3>
              </div>
              <div className="fantasy-total"><span>Expected total</span><b>{integer.format(analysis.expected_points)}</b><small>{integer.format(analysis.low_points)}–{integer.format(analysis.high_points)} range</small></div>
            </div>
            <p className="analysis-note">{analysis.recognition_note} The projection uses Valve&apos;s base stat values; the final score still depends on the actual top two games, best series and title activation.</p>
            <div className="analysis-basis">
              <div><span>Stage detected</span><strong>{analysis.stage}</strong></div>
              <div><span>Banner shape</span><strong>{analysis.expected_emblems_per_banner} emblems</strong></div>
              <div><span>Reroll budget</span><strong>{analysis.stage === "Group Stage" ? 40 : 30} rolls</strong></div>
              <a href="https://www.reddit.com/r/DotA2/comments/1vble84/fantasy_league_2026_guide/" target="_blank" rel="noreferrer">Guide prior ↗</a>
            </div>
            <div className="recognized-players">
              {analysis.players.map((player, index) => (
                <article key={player.account_id}>
                  {player.avatar_url
                    ? <img src={player.avatar_url} alt={`${player.name} official profile`} />
                    : preview ? <span className="source-portrait" role="img" aria-label={`${player.name} portrait from uploaded screenshot`} style={{ backgroundImage: `url("${preview}")`, backgroundPosition: sourcePortraitPositions[index] }} />
                      : <span className="portrait-fallback">{player.name?.[0] ?? "?"}</span>}
                  <div><span>{player.role} · {player.position_label}</span><strong>{player.name}</strong><small>{player.team_name ?? "Team unverified"} · #{player.guide_rank ?? "—"} guide · {player.team_run_probability}% advance</small></div>
                  <b>{integer.format(player.predicted_points)}</b>
                </article>
              ))}
            </div>
            <details className="ocr-details"><summary>Review recognized text</summary><pre>{analysis.raw_text}</pre></details>
          </div>
          <section className="emblem-inspector" aria-label="Recognized War Banner emblems">
            <div className="inspector-head">
              <div><span className="section-index">WAR BANNER READOUT</span><h4>Every emblem, decoded.</h4></div>
              <p>Stats are judged first, then quality, then trait—matching the guide&apos;s reroll order.</p>
            </div>
            <div className="emblem-role-grid">
              {(["Core", "Mid", "Support"] as const).map((role) => (
                <section key={role}>
                  <header><span>{role}</span><b>{analysis.banners.filter((banner) => banner.role === role).length}/{analysis.expected_emblems_per_banner}</b></header>
                  <div className="emblem-stack">
                    {analysis.banners.filter((banner) => banner.role === role).map((banner) => (
                      <article className={`emblem-card emblem-${banner.color.toLowerCase()}`} key={`${banner.role}-${banner.slot}`}>
                        <div className="emblem-number">0{banner.slot}</div>
                        <div><span>{banner.color} · {banner.tier ? `Tier ${banner.tier}` : "Tier unread"}</span><strong>{banner.metric}</strong><small>{banner.trait ?? "Trait unread"}{banner.trait_bonus != null ? ` · ${banner.trait_bonus > 0 ? "+" : ""}${banner.trait_bonus}%` : ""}</small></div>
                        <b>{banner.multiplier}%</b>
                      </article>
                    ))}
                  </div>
                </section>
              ))}
            </div>
          </section>
          <section className="reroll-board" aria-label="Reroll recommendations">
            <div className="inspector-head">
              <div><span className="section-index">ROLL ECONOMY</span><h4>Spend the next token here.</h4></div>
              <p>Estimated uplift ranks weak stats before low tiers and awkward trait placement.</p>
            </div>
            <div className="reroll-list">
              {analysis.reroll_advice.map((advice, index) => (
                <article key={`${advice.role}-${advice.slot}`}>
                  <span className="reroll-rank">{String(index + 1).padStart(2, "0")}</span>
                  <div><small>{advice.role} · Emblem {advice.slot}</small><strong>{advice.action}</strong><p>{advice.reason}</p></div>
                  <b>{advice.expected_uplift > 0 ? `+${advice.expected_uplift.toFixed(1)}` : "LOCK"}<small>est. value</small></b>
                </article>
              ))}
            </div>
          </section>
          {analysis.recommended_lineup && (
            <section className="lineup-optimizer" aria-label="Recommended alternative Fantasy lineup">
              <div className="optimizer-head">
                <div><span className="section-index">BANNER-OPTIMIZED ALTERNATIVE</span><h4>Higher-fit lineup</h4></div>
                <div className="optimizer-score"><span>Potential score</span><b>{integer.format(analysis.recommended_lineup.expected_points)}</b><small className={analysis.recommended_lineup.improvement >= 0 ? "positive" : ""}>{analysis.recommended_lineup.improvement >= 0 ? "+" : ""}{integer.format(analysis.recommended_lineup.improvement)} vs yours</small></div>
              </div>
              <div className="optimizer-teams">
                {(["Core", "Mid", "Support"] as const).map((role) => {
                  const rolePlayers = analysis.recommended_lineup!.players.filter((player) => player.role === role);
                  const teamName = role === "Core" ? analysis.recommended_lineup!.core_team : role === "Mid" ? analysis.recommended_lineup!.mid_team : analysis.recommended_lineup!.support_team;
                  return (
                    <article key={role}>
                      <div className="optimizer-team-name">
                        {rolePlayers[0]?.logo_url && <img src={rolePlayers[0].logo_url} alt="" />}
                        <div><span>{role} block</span><strong>{teamName}</strong></div>
                      </div>
                      {rolePlayers.map((player) => (
                        <div className="optimizer-player" key={player.account_id}>
                          {player.avatar_url ? <img src={player.avatar_url} alt="" /> : <span className="optimizer-fallback">{player.name?.[0] ?? "?"}</span>}
                          <div><b>{player.name}</b><small>{player.position_label} · #{player.guide_rank ?? "—"} guide · {player.banner_fit}% fit</small></div>
                          <strong>{integer.format(player.predicted_points)}</strong>
                        </div>
                      ))}
                    </article>
                  );
                })}
              </div>
              <p>{analysis.recommended_lineup.assumption}</p>
            </section>
          )}
          <p className="fantasy-data-basis">{analysis.data_basis}</p>
        </div>
      )}
    </section>
  );
}
