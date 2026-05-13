"use client";

import { useEffect } from "react";
import { useWorkspace } from "@/lib/store";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

const RESEARCH = [
  { id: "fundamentals", label: "Fundamentals" },
  { id: "industry", label: "Industry & Moat" },
  { id: "dcf", label: "DCF" },
  { id: "comps", label: "Comps" },
  { id: "macro", label: "Macro" },
  { id: "risk", label: "Risk" },
  { id: "technicals", label: "Technicals" },
];

const PRODUCTION = [
  { id: "deck_builder", label: "Deck Builder" },
  { id: "memo_builder", label: "Memo Builder" },
];

function GroupHeader({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-[10px] uppercase text-muted-foreground px-3 pt-4 pb-1 tracking-wider">
      {children}
    </div>
  );
}

function AgentItem({ id, label }: { id: string; label: string }) {
  const activeTabId = useWorkspace((s) => s.activeTabId);
  const openTab = useWorkspace((s) => s.openTab);
  const active = activeTabId === id;
  return (
    <button
      onClick={() => openTab({ id, label, pinned: id === "md" })}
      className={cn(
        "block w-full text-left px-3 py-1.5 rounded-sm text-sm hover:bg-accent",
        active && "bg-accent text-accent-foreground",
      )}
    >
      {label}
    </button>
  );
}

export default function Sidebar() {
  const recentTickers = useWorkspace((s) => s.recentTickers);
  const selectedTicker = useWorkspace((s) => s.selectedTicker);
  const selectTicker = useWorkspace((s) => s.selectTicker);

  useEffect(() => {
    // Hydrate from BOTH the SQLite jobs index AND the on-disk RESEARCH_DIR.
    // Filesystem is the source of truth for "what artifacts exist" — a job
    // row may be missing if the DB was reset, but the artifacts persist.
    Promise.all([
      api.listJobs(20).catch(() => []),
      api.listTickers().catch(() => []),
    ]).then(([jobs, diskTickers]) => {
      const order: string[] = [];
      const seen = new Set<string>();
      // Recent jobs first (preserves "most recently worked on" order).
      for (const j of jobs) {
        if (!seen.has(j.ticker)) {
          seen.add(j.ticker);
          order.push(j.ticker);
        }
      }
      // Then any tickers found on disk that the DB doesn't know about.
      for (const t of diskTickers) {
        if (!seen.has(t)) {
          seen.add(t);
          order.push(t);
        }
      }
      if (order.length) {
        useWorkspace.setState((s) => ({
          recentTickers: order,
          selectedTicker: s.selectedTicker ?? order[0],
        }));
      }
    });
  }, []);

  return (
    <nav className="py-2">
      <GroupHeader>Active</GroupHeader>
      <AgentItem id="md" label="MD" />
      <GroupHeader>Research</GroupHeader>
      {RESEARCH.map((a) => (
        <AgentItem key={a.id} {...a} />
      ))}
      <GroupHeader>Production</GroupHeader>
      {PRODUCTION.map((a) => (
        <AgentItem key={a.id} {...a} />
      ))}
      <GroupHeader>Recent Tickers</GroupHeader>
      {recentTickers.length === 0 && (
        <div className="px-3 py-1 text-xs text-muted-foreground italic">
          No runs yet.
        </div>
      )}
      {recentTickers.map((t) => (
        <button
          key={t}
          onClick={() => selectTicker(t)}
          className={cn(
            "block w-full text-left px-3 py-1 text-sm hover:bg-accent rounded-sm",
            selectedTicker === t && "text-foreground font-medium",
          )}
        >
          {t}
        </button>
      ))}
    </nav>
  );
}
