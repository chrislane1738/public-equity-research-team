"use client";

import { useState } from "react";
import { useWorkspace } from "./store";
import { api } from "./api";
import { toast } from "sonner";
import type { Workflow } from "./types";

function nowMs() {
  return Date.now();
}

function uuid() {
  return crypto.randomUUID();
}

export interface DispatchHook {
  /** True while a thesis-check dialog should be open. */
  thesisOpen: boolean;
  /** True while a sector-sweep dialog should be open. */
  sweepOpen: boolean;
  /** Open the appropriate dialog or kick off the workflow directly. */
  start: (w: Workflow, label: string, promptFn: (t: string) => string) => void;
  /** Submit a captured thesis-check question. */
  submitThesis: (question: string) => Promise<void>;
  /** Submit a captured sector-sweep ticker list. */
  submitSweep: (tickers: string[]) => Promise<void>;
  /** Cancel the open dialog. */
  cancelThesis: () => void;
  cancelSweep: () => void;
}

export function useDispatchWorkflow(): DispatchHook {
  const selectedTicker = useWorkspace((s) => s.selectedTicker);
  const openTab = useWorkspace((s) => s.openTab);
  const appendMessage = useWorkspace((s) => s.appendMessage);
  const [thesisOpen, setThesisOpen] = useState(false);
  const [sweepOpen, setSweepOpen] = useState(false);

  function ticker(): string | null {
    const t = selectedTicker?.trim().toUpperCase();
    return t || null;
  }

  function start(w: Workflow, label: string, promptFn: (t: string) => string) {
    const t = ticker();
    if (!t) {
      toast.error("Pick a ticker first.");
      return;
    }
    if (w === "thesis-check") {
      setThesisOpen(true);
      return;
    }
    if (w === "sector-sweep") {
      setSweepOpen(true);
      return;
    }
    void run({ workflow: w, ticker: t }, t, label, promptFn(t));
  }

  async function run(
    body: { workflow: Workflow; ticker?: string; tickers?: string[]; question?: string },
    repTicker: string,
    label: string,
    userMsg: string,
  ) {
    openTab({ id: "md", label: "MD", pinned: true });
    appendMessage("md", {
      id: uuid(),
      role: "user",
      content: userMsg,
      ts: nowMs(),
    });
    try {
      const job = await api.createJob(body);
      toast.success(`${label} dispatched · job ${job.job_id.slice(0, 8)}`);
      window.dispatchEvent(
        new CustomEvent("job:dispatched", {
          detail: { jobId: job.job_id, ticker: repTicker, workflow: body.workflow },
        }),
      );
    } catch (e) {
      toast.error(`Failed to dispatch ${label}: ${(e as Error).message}`);
    }
  }

  async function submitThesis(question: string) {
    const t = ticker();
    if (!t) return;
    setThesisOpen(false);
    await run(
      { workflow: "thesis-check", ticker: t, question },
      t,
      "Thesis check",
      `Thesis check on ${t}: ${question}`,
    );
  }

  async function submitSweep(tickers: string[]) {
    setSweepOpen(false);
    if (tickers.length < 2) return;
    await run(
      { workflow: "sector-sweep", tickers },
      tickers[0],
      "Sector sweep",
      `Sector sweep across ${tickers.join(", ")}.`,
    );
  }

  return {
    thesisOpen,
    sweepOpen,
    start,
    submitThesis,
    submitSweep,
    cancelThesis: () => setThesisOpen(false),
    cancelSweep: () => setSweepOpen(false),
  };
}
