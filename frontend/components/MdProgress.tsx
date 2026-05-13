"use client";

import { useWorkspace } from "@/lib/store";
import { Badge } from "@/components/ui/badge";

export default function MdProgress() {
  const activeJob = useWorkspace((s) => s.activeJob);
  const jobLog = useWorkspace((s) => s.jobLog);

  if (!activeJob) return null;

  const totalCost = jobLog.reduce((s, l) => s + (l.cost ?? 0), 0);
  const completedAgents = jobLog.map((l) => l.agent);
  const statusVariant: "default" | "secondary" | "destructive" | "outline" =
    activeJob.status === "complete"
      ? "secondary"
      : activeJob.status === "failed"
        ? "destructive"
        : "default";

  return (
    <div className="border-b border-border bg-muted/30 px-4 py-3 text-sm">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <Badge variant={statusVariant}>{activeJob.status}</Badge>
          <span className="text-muted-foreground">
            {activeJob.workflow} · {activeJob.ticker}
          </span>
          {activeJob.current_stage && (
            <span className="text-xs text-muted-foreground">
              · stage: {activeJob.current_stage}
            </span>
          )}
        </div>
        <div className="text-xs text-muted-foreground">
          ${totalCost.toFixed(2)} · {completedAgents.length} agents complete
        </div>
      </div>
      {completedAgents.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {completedAgents.map((a, i) => (
            <Badge key={`${a}-${i}`} variant="outline" className="text-xs">
              {a}
            </Badge>
          ))}
        </div>
      )}
      {activeJob.rating && (
        <div className="mt-2 text-sm">
          Rating: <strong>{activeJob.rating}</strong>
        </div>
      )}
    </div>
  );
}
