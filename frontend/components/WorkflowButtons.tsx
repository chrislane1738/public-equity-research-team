"use client";

import { Button } from "@/components/ui/button";
import { useDispatchWorkflow } from "@/lib/dispatch";
import ThesisCheckDialog from "./ThesisCheckDialog";
import SectorSweepDialog from "./SectorSweepDialog";
import { useWorkspace } from "@/lib/store";
import type { Workflow } from "@/lib/types";

const ALL_WORKFLOWS: { id: Workflow; label: string; prompt: (t: string) => string }[] = [
  { id: "full-deep-dive", label: "Full Deep-Dive", prompt: (t) => `Run a full deep-dive on ${t}.` },
  {
    id: "earnings-update",
    label: "Earnings Update",
    prompt: (t) => `${t} just reported. Run an earnings update.`,
  },
  { id: "morning-note", label: "Morning Note", prompt: (t) => `Write a morning note on ${t}.` },
  { id: "thesis-check", label: "Thesis Check", prompt: (t) => `Run a thesis check on ${t}.` },
  {
    id: "sector-sweep",
    label: "Sector Sweep",
    prompt: (t) => `Run a sector sweep starting from ${t}.`,
  },
];

const AGENT_WORKFLOWS: Record<string, Workflow[]> = {
  md: ["full-deep-dive", "earnings-update", "morning-note", "thesis-check", "sector-sweep"],
  fundamentals: [
    "full-deep-dive",
    "earnings-update",
    "morning-note",
    "thesis-check",
    "sector-sweep",
  ],
  industry: ["full-deep-dive", "sector-sweep"],
  dcf: ["full-deep-dive", "earnings-update"],
  comps: ["full-deep-dive", "sector-sweep"],
  macro: ["full-deep-dive", "sector-sweep"],
  risk: ["full-deep-dive", "earnings-update"],
  technicals: ["full-deep-dive"],
  deck_builder: ["full-deep-dive"],
  memo_builder: ["full-deep-dive", "earnings-update", "thesis-check"],
};

export default function WorkflowButtons({ agentId }: { agentId: string }) {
  const selectedTicker = useWorkspace((s) => s.selectedTicker);
  const dispatch = useDispatchWorkflow();
  const allowed = new Set(AGENT_WORKFLOWS[agentId] ?? []);
  const visible = ALL_WORKFLOWS.filter((w) => allowed.has(w.id));
  if (visible.length === 0) return null;

  return (
    <>
      <div className="border-t border-border bg-muted/20 px-4 py-3 flex flex-wrap gap-2">
        {visible.map((w) => (
          <Button
            key={w.id}
            variant="secondary"
            size="sm"
            onClick={() => dispatch.start(w.id, w.label, w.prompt)}
          >
            {w.label}
          </Button>
        ))}
      </div>
      {selectedTicker && (
        <>
          <ThesisCheckDialog
            ticker={selectedTicker}
            open={dispatch.thesisOpen}
            onCancel={dispatch.cancelThesis}
            onSubmit={dispatch.submitThesis}
          />
          <SectorSweepDialog
            initial={selectedTicker}
            open={dispatch.sweepOpen}
            onCancel={dispatch.cancelSweep}
            onSubmit={dispatch.submitSweep}
          />
        </>
      )}
    </>
  );
}
