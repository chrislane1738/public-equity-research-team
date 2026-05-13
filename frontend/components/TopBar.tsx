"use client";

import { useWorkspace } from "@/lib/store";
import { api } from "@/lib/api";
import { toast } from "sonner";
import type { Workflow } from "@/lib/types";
import { Button } from "@/components/ui/button";
import TickerPicker from "./TickerPicker";

function now(): number {
  return Date.now();
}

const WORKFLOWS: { id: Workflow; label: string; prompt: (t: string) => string }[] = [
  {
    id: "full-deep-dive",
    label: "Full Deep-Dive",
    prompt: (t) => `Run a full deep-dive on ${t}.`,
  },
  {
    id: "earnings-update",
    label: "Earnings Update",
    prompt: (t) => `${t} just reported. Run an earnings update.`,
  },
  {
    id: "morning-note",
    label: "Morning Note",
    prompt: (t) => `Write a morning note on ${t}.`,
  },
  {
    id: "thesis-check",
    label: "Thesis Check",
    prompt: (t) => `Run a thesis check on ${t}.`,
  },
  {
    id: "sector-sweep",
    label: "Sector Sweep",
    prompt: (t) => `Run a sector sweep starting from ${t}.`,
  },
];

export default function TopBar() {
  const selectedTicker = useWorkspace((s) => s.selectedTicker);
  const openTab = useWorkspace((s) => s.openTab);
  const appendMessage = useWorkspace((s) => s.appendMessage);

  async function dispatch(w: Workflow, label: string, promptFn: (t: string) => string) {
    const t = selectedTicker?.trim().toUpperCase() ?? "";
    if (!t) {
      toast.error("Pick a ticker first.");
      return;
    }
    openTab({ id: "md", label: "MD", pinned: true });
    appendMessage("md", {
      id: crypto.randomUUID(),
      role: "user",
      content: promptFn(t),
      ts: now(),
    });
    try {
      const body =
        w === "sector-sweep"
          ? { workflow: w, tickers: [t] }
          : w === "thesis-check"
            ? { workflow: w, ticker: t, question: promptFn(t) }
            : { workflow: w, ticker: t };
      const job = await api.createJob(body);
      toast.success(`${label} dispatched · job ${job.job_id.slice(0, 8)}`);
      window.dispatchEvent(
        new CustomEvent("job:dispatched", {
          detail: { jobId: job.job_id, ticker: t, workflow: w },
        }),
      );
    } catch (e) {
      toast.error(`Failed to dispatch ${label}: ${(e as Error).message}`);
    }
  }

  return (
    <header className="h-12 border-b border-border flex items-center px-4 gap-3">
      <TickerPicker />
      <div className="flex-1" />
      {WORKFLOWS.map((w) => (
        <Button
          key={w.id}
          variant="secondary"
          size="sm"
          onClick={() => dispatch(w.id, w.label, w.prompt)}
        >
          {w.label}
        </Button>
      ))}
    </header>
  );
}
