export type Workflow =
  | "full-deep-dive"
  | "earnings-update"
  | "morning-note"
  | "thesis-check"
  | "sector-sweep";

export type JobStatus = "running" | "complete" | "failed";

export interface JobState {
  id: string;
  ticker: string;
  workflow: Workflow | string;
  status: JobStatus;
  current_stage: string | null;
  stages: Record<string, string>;
  rating: "Buy" | "Hold" | "Sell" | null;
  error: string | null;
  created_at: string | null;
  completed_at: string | null;
}

export type JobEvent =
  | { type: "state"; state: JobState }
  | {
      type: "agent_completed";
      agent: string;
      job_id: string;
      input_tokens: number;
      output_tokens: number;
      cost_usd: number;
      stop_reason: string | null;
      ts: string;
    }
  | { type: "agent_failed"; agent: string; error: string; job_id: string; ts: string }
  | { type: "stage"; stage: string; status: string; job_id: string; ts: string }
  | { type: "job_terminal"; job_id: string; status: "complete" | "failed" };

export interface FileNode {
  name: string;
  path: string;
  kind: "dir" | "file";
  ext?: string;
  size?: number;
  children?: FileNode[];
}

export interface TickerSearchHit {
  symbol: string;
  name: string;
  exchange: string;
}
