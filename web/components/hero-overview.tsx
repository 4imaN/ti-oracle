"use client";

import { useEffect, useState } from "react";
import { getJSON, integer, percent } from "@/lib/api";
import type { HeroMetaResponse } from "@/lib/types";

export function HeroOverview({ modelAccuracy }: { modelAccuracy: number | null }) {
  const [data, setData] = useState<HeroMetaResponse | null>(null);

  useEffect(() => {
    getJSON<HeroMetaResponse>("/api/heroes/meta?bracket=7&limit=6&minimum_picks=5000")
      .then(setData)
      .catch(() => setData(null));
  }, []);

  return (
    <section className="hero-intro" id="overview">
      <div className="intro-copy reveal">
        <span className="section-index">01 / LIVE OUTLOOK</span>
        <h1>Read the tournament<br /><em>before it breaks.</em></h1>
        <p>
          Patch form, lineup continuity, draft tendencies and player output—kept separate,
          tested forward in time, then combined only when the evidence earns it.
        </p>
        <div className="intro-actions">
          <a href="#teams">Open team predictions <span>→</span></a>
          <a href="#fantasy">Analyze Fantasy screenshot</a>
        </div>
        <div className="confidence-note">
          <span>{modelAccuracy == null ? "—" : percent(modelAccuracy)}</span>
          <p><b>held-out map accuracy</b><br />Roster model remains provisional until the sample grows.</p>
        </div>
      </div>
      <div className="meta-window reveal delay-1">
        <div className="window-label">
          <span>Current pressure points</span>
          <span>{data ? `${data.bracket_name} bracket` : "Loading bracket"}</span>
        </div>
        <div className="hero-strip" aria-live="polite">
          {data?.heroes.map((hero, index) => (
            <article className="hero-entry" key={hero.hero_id}>
              {hero.image_url && <img src={hero.image_url} alt="" loading="lazy" />}
              <span className="hero-rank">{String(index + 1).padStart(2, "0")}</span>
              <div>
                <strong>{hero.hero}</strong>
                <p>{percent(hero.posterior_rate)} win · {integer.format(hero.picks)} picks</p>
              </div>
            </article>
          ))}
          {!data && Array.from({ length: 6 }, (_, index) => <div className="hero-entry loading-block" key={index} />)}
        </div>
      </div>
    </section>
  );
}
