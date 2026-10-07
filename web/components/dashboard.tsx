"use client";

import { useEffect, useState } from "react";
import { DraftRoom } from "@/components/draft-room";
import { FantasyWorkbench } from "@/components/fantasy-workbench";
import { HeroOverview } from "@/components/hero-overview";
import { MatchLab } from "@/components/match-lab";
import { Rail } from "@/components/rail";
import { RankChart } from "@/components/rank-chart";
import { getJSON, integer } from "@/lib/api";
import type { Overview } from "@/lib/types";

export function Dashboard() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [serviceState, setServiceState] = useState<"checking" | "online" | "offline">("checking");
  const [retrying, setRetrying] = useState(false);

  useEffect(() => {
    getJSON<Overview>("/api/overview")
      .then((result) => {
        setOverview(result);
        setServiceState("online");
      })
      .catch((error: Error) => {
        setApiError(error.message);
        setServiceState("offline");
      });
  }, []);

  async function retryConnection() {
    setRetrying(true);
    try {
      const result = await getJSON<Overview>("/api/overview");
      setOverview(result);
      setApiError(null);
      setServiceState("online");
      window.location.reload();
    } catch (error) {
      setApiError((error as Error).message);
      setServiceState("offline");
      setRetrying(false);
    }
  }

  return (
    <>
      <div className="grain" aria-hidden="true" />
      <Rail serviceState={serviceState} />
      <main id="top">
        <header className="topbar">
          <div className="event-lockup">
            <span className="eyebrow">The International 2026</span>
            <strong>Competitive intelligence desk</strong>
          </div>
          <div className="system-strip">
            <span>Patch <b>{overview?.patch?.name ?? "—"}</b></span>
            <span>Maps <b>{overview ? integer.format(overview.counts.maps) : "—"}</b></span>
            <span>Model <b className={serviceState === "offline" ? "system-error" : ""}>{serviceState === "offline" ? "Paused" : (overview?.model.status ?? "Loading")}</b></span>
          </div>
        </header>

        {apiError && (
          <div className="api-banner" role="alert">
            <span className="api-banner-mark" aria-hidden="true">!</span>
            <div>
              <strong>Data engine paused</strong>
              <p>{apiError}</p>
            </div>
            <div className="api-banner-actions">
              <button type="button" onClick={retryConnection} disabled={retrying}>
                {retrying ? "Checking…" : "Retry connection"}
              </button>
              <code>npm run dev</code>
            </div>
          </div>
        )}

        <HeroOverview modelAccuracy={overview?.model.test_accuracy ?? null} />
        <MatchLab />
        <RankChart />
        <FantasyWorkbench />
        <DraftRoom />

        <footer>
          <span>TI Oracle / Next.js research build 0.2</span>
          <span>OpenDota-derived match data · probabilities are uncertain</span>
        </footer>
      </main>
    </>
  );
}
