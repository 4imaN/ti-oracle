"use client";

import { useEffect, useState } from "react";

const links = [
  ["overview", "Overview"],
  ["teams", "Team predictions"],
  ["fantasy", "Fantasy"],
  ["draft", "Draft room"],
] as const;

export function Rail({ serviceState }: { serviceState: "checking" | "online" | "offline" }) {
  const [active, setActive] = useState("overview");

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((first, second) => second.intersectionRatio - first.intersectionRatio)[0];
        if (visible?.target.id) setActive(visible.target.id);
      },
      { rootMargin: "-20% 0px -65%", threshold: [0.05, 0.25] },
    );
    links.forEach(([id]) => {
      const section = document.getElementById(id);
      if (section) observer.observe(section);
    });
    return () => observer.disconnect();
  }, []);

  return (
    <aside className="rail">
      <a className="mark" href="#top" aria-label="TI Oracle home">
        <span className="mark-rune">ϟ</span>
        <span className="mark-copy">TI<br />ORACLE</span>
      </a>
      <nav aria-label="Primary navigation">
        {links.map(([id, label], index) => (
          <a key={id} className={`nav-link ${active === id ? "active" : ""}`} href={`#${id}`}>
            <span>{String(index + 1).padStart(2, "0")}</span>{label}
          </a>
        ))}
      </nav>
      <div className="rail-foot">
        <span className={`live-dot ${serviceState}`} />
        <span>{serviceState === "online" ? "Data live" : serviceState === "offline" ? "Data paused" : "Connecting"}</span>
        <small>Probabilities, not promises.</small>
      </div>
    </aside>
  );
}
