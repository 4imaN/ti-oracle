"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getJSON } from "@/lib/api";
import type { HeroTrend } from "@/lib/types";

const colors = ["#d8b465", "#9dd0b1", "#c9644e", "#9caed2", "#d5a1c2"];
const ranks = ["Herald", "Guardian", "Crusader", "Archon", "Legend", "Ancient", "Divine"];
const rankColors = ["#8d745e", "#9e8570", "#72a9a6", "#5b9c79", "#b08bc2", "#77a9d5", "#d7b95c"];

type RankTickProps = {
  x?: number;
  y?: number;
  payload?: { value?: string };
};

function RankTick({ x = 0, y = 0, payload }: RankTickProps) {
  const rank = payload?.value ?? "";
  const rankIndex = Math.max(0, ranks.indexOf(rank));
  const color = rankColors[rankIndex];

  return (
    <g transform={`translate(${x}, ${y + 13})`}>
      <path
        d="M0 -10 L9 -5 L8 7 L0 12 L-8 7 L-9 -5 Z"
        fill={`${color}24`}
        stroke={color}
        strokeWidth="1.25"
      />
      <path d="M-5 -4 L0 -7 L5 -4 L4 4 L0 7 L-4 4 Z" fill={color} opacity="0.72" />
      <text y="4" textAnchor="middle" fill="#090b0a" fontSize="7" fontWeight="800">
        {rankIndex + 1}
      </text>
      <text y="30" textAnchor="middle" fill="#8b9389" fontSize="9" fontWeight="600" letterSpacing=".04em">
        {rank}
      </text>
    </g>
  );
}

export function RankChart() {
  const [series, setSeries] = useState<HeroTrend[]>([]);
  const [active, setActive] = useState<number | null>(null);

  useEffect(() => {
    getJSON<HeroTrend[]>("/api/heroes/rank-trends?limit=5").then(setSeries).catch(() => setSeries([]));
  }, []);

  const chartData = useMemo(() => ranks.map((rank, rankIndex) => {
    const row: Record<string, string | number | null> = { rank };
    for (const hero of series) {
      const point = hero.points.find((candidate) => candidate.bracket === rankIndex + 1);
      row[hero.hero] = point?.win_rate == null ? null : Number((point.win_rate * 100).toFixed(2));
    }
    return row;
  }), [series]);

  return (
    <section className="rank-section">
      <div className="rank-copy">
        <span className="section-index">PATCH LENS / RANK CURVE</span>
        <h2>One patch.<br />Seven different metas.</h2>
        <p>Win rate moves as coordination, execution and draft knowledge change by bracket. Focus a hero to compare how reliably it scales.</p>
        <div className="trend-legend" onMouseLeave={() => setActive(null)}>
          {series.map((hero, index) => (
            <button className={active === index ? "active" : ""} key={hero.hero_id} onMouseEnter={() => setActive(index)} onFocus={() => setActive(index)} onBlur={() => setActive(null)}>
              <i style={{ background: colors[index] }} />{hero.hero}
            </button>
          ))}
        </div>
      </div>
      <div className="chart-wrap">
        <div className="chart-shell">
          <div className="chart-topline"><span>Current-patch win rate</span><b>50% baseline</b></div>
          <ResponsiveContainer width="100%" height={410}>
            <LineChart data={chartData} margin={{ top: 22, right: 24, left: 0, bottom: 20 }}>
              <CartesianGrid stroke="rgba(231,233,223,.09)" vertical={false} />
              <XAxis dataKey="rank" axisLine={false} tickLine={false} tick={<RankTick />} height={58} />
              <YAxis domain={[45, 60]} ticks={[46, 48, 50, 52, 54, 56, 58, 60]} axisLine={false} tickLine={false} tick={{ fill: "#747c72", fontSize: 10 }} tickFormatter={(value) => `${value}%`} width={42} />
              <ReferenceLine y={50} stroke="rgba(216,180,101,.38)" strokeDasharray="5 5" />
              <Tooltip
                cursor={{ stroke: "rgba(216,180,101,.24)", strokeWidth: 1 }}
                contentStyle={{ background: "#0b0e0c", border: "1px solid rgba(216,180,101,.28)", borderRadius: 0, color: "#e7e9df", fontSize: 11 }}
                labelStyle={{ color: "#d8b465", marginBottom: 7, textTransform: "uppercase", letterSpacing: ".08em" }}
                itemStyle={{ paddingBlock: 2 }}
                formatter={(value) => [`${Number(value).toFixed(1)}%`]}
              />
              {series.map((hero, index) => (
                <Line
                  activeDot={{ r: 5, stroke: "#090b0a", strokeWidth: 2 }}
                  animationDuration={650}
                  connectNulls
                  dataKey={hero.hero}
                  dot={{ r: 3, fill: colors[index], stroke: "#090b0a", strokeWidth: 2 }}
                  key={hero.hero_id}
                  name={hero.hero}
                  opacity={active === null || active === index ? 1 : 0.1}
                  stroke={colors[index]}
                  strokeWidth={active === index ? 3.5 : 2.25}
                  type="monotone"
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
          <p className="chart-footnote">Hover any point for its exact bracket win rate. Samples are patch snapshots, not hero recommendations by themselves.</p>
        </div>
      </div>
    </section>
  );
}
