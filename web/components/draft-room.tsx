"use client";

import { useEffect, useMemo, useState } from "react";
import { getJSON, percent } from "@/lib/api";
import type { DraftHero, DraftResponse, UploadResponse } from "@/lib/types";

export function DraftRoom() {
  const [heroes, setHeroes] = useState<DraftHero[]>([]);
  const [enemy, setEnemy] = useState<number[]>([]);
  const [ally, setAlly] = useState<number[]>([]);
  const [enemyChoice, setEnemyChoice] = useState(0);
  const [allyChoice, setAllyChoice] = useState(0);
  const [recommendations, setRecommendations] = useState<DraftResponse | null>(null);
  const [uploadMessage, setUploadMessage] = useState("");
  const [error, setError] = useState("");
  const byId = useMemo(() => new Map(heroes.map((hero) => [hero.hero_id, hero])), [heroes]);

  useEffect(() => {
    getJSON<DraftHero[]>("/api/draft/heroes").then((rows) => {
      setHeroes(rows);
      setEnemyChoice(rows[0]?.hero_id ?? 0);
      setAllyChoice(rows[0]?.hero_id ?? 0);
      const defaults = [33, 62].filter((id) => rows.some((hero) => hero.hero_id === id));
      setEnemy(defaults);
    }).catch((requestError: Error) => setError(requestError.message));
  }, []);

  useEffect(() => {
    if (!enemy.length) {
      return;
    }
    const query = new URLSearchParams();
    enemy.forEach((id) => query.append("enemy", String(id)));
    ally.forEach((id) => query.append("ally", String(id)));
    query.set("limit", "8");
    const controller = new AbortController();
    getJSON<DraftResponse>(`/api/draft/recommend?${query.toString()}`, { signal: controller.signal })
      .then((result) => { setRecommendations(result); setError(""); })
      .catch((requestError: Error) => { if (requestError.name !== "AbortError") setError(requestError.message); });
    return () => controller.abort();
  }, [enemy, ally]);

  const displayRecommendations = enemy.length ? recommendations : null;

  function add(side: "enemy" | "ally") {
    const choice = side === "enemy" ? enemyChoice : allyChoice;
    if (!choice || enemy.includes(choice) || ally.includes(choice)) return;
    if (side === "enemy" && enemy.length < 5) setEnemy((current) => [...current, choice]);
    if (side === "ally" && ally.length < 5) setAlly((current) => [...current, choice]);
  }

  async function upload(file?: File) {
    if (!file) return;
    setUploadMessage("Validating draft image…");
    const body = new FormData(); body.append("file", file);
    try {
      setUploadMessage((await getJSON<UploadResponse>("/api/upload/draft", { method: "POST", body })).message);
    } catch (requestError) {
      setUploadMessage((requestError as Error).message);
    }
  }

  const slots = (values: number[], remove: (id: number) => void) => (
    <div className="draft-slots">
      {values.map((id) => {
        const hero = byId.get(id);
        return hero ? <button type="button" className="hero-chip" onClick={() => remove(id)} title={`Remove ${hero.hero}`} key={id}>{hero.image_url && <img src={hero.image_url} alt={hero.hero} />}</button> : null;
      })}
    </div>
  );

  return (
    <section className="draft-section" id="draft">
      <div className="draft-copy">
        <span className="section-index">04 / DRAFT ROOM</span>
        <h2>The next edge<br />starts at pick six.</h2>
        <p>Screenshot recognition will convert a live draft into hero IDs, then rank counters through patch win rate, role fit, team comfort and ban likelihood.</p>
        <label className="draft-upload">
          <input type="file" accept="image/png,image/jpeg,image/webp" onChange={(event) => void upload(event.target.files?.[0])} />
          <span>↥ Upload live draft image</span>
        </label>
        <p className="draft-upload-result" role="status">{uploadMessage}</p>
      </div>
      <div className="draft-board live" aria-label="Draft counterpick console">
        <div className="draft-inputs">
          <div className="draft-side radiant">
            <span>Your side</span>
            <div className="hero-add"><select value={allyChoice} onChange={(event) => setAllyChoice(Number(event.target.value))} aria-label="Choose allied hero">{heroes.map((hero) => <option value={hero.hero_id} key={hero.hero_id}>{hero.hero}</option>)}</select><button type="button" onClick={() => add("ally")}>Add</button></div>
            {slots(ally, (id) => setAlly((current) => current.filter((value) => value !== id)))}
          </div>
          <div className="draft-side dire">
            <span>Enemy picks</span>
            <div className="hero-add"><select value={enemyChoice} onChange={(event) => setEnemyChoice(Number(event.target.value))} aria-label="Choose enemy hero">{heroes.map((hero) => <option value={hero.hero_id} key={hero.hero_id}>{hero.hero}</option>)}</select><button type="button" onClick={() => add("enemy")}>Add</button></div>
            {slots(enemy, (id) => setEnemy((current) => current.filter((value) => value !== id)))}
          </div>
          <button type="button" className="analyze-draft" onClick={() => setEnemy((current) => [...current])}>Refresh counterpicks</button>
        </div>
        <div className="counter-console">
          <div className="board-head"><span>Recommended next picks</span><span>Patch model</span></div>
          <div className="counter-results">
            {error && <p>{error}</p>}
            {!error && !displayRecommendations && <p>Add at least one enemy hero to calculate counters.</p>}
            {displayRecommendations?.recommendations.map((hero) => (
              <div className="counter-row" key={hero.hero_id}>
                {hero.image_url && <img src={hero.image_url} alt="" loading="lazy" />}
                <div><strong>{hero.hero}</strong><small>{hero.matchup_games} matchup maps · {percent(hero.meta_rate)} patch WR</small></div>
                <b>{(hero.score * 100).toFixed(1)}</b>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
