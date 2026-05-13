import type { FileNode, JobState, TickerSearchHit, Workflow } from "./types";

const BASE = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8001";

async function jsonOrThrow<T>(r: Response): Promise<T> {
  if (!r.ok) {
    const text = await r.text();
    throw new Error(`HTTP ${r.status}: ${text || r.statusText}`);
  }
  return r.json() as Promise<T>;
}

export const api = {
  baseUrl: BASE,

  async listTickers(): Promise<string[]> {
    const r = await fetch(`${BASE}/tickers`);
    return (await jsonOrThrow<{ tickers: string[] }>(r)).tickers;
  },

  async listFiles(ticker: string): Promise<FileNode[]> {
    const r = await fetch(`${BASE}/tickers/${encodeURIComponent(ticker)}/files`);
    return (await jsonOrThrow<{ tree: FileNode[] }>(r)).tree;
  },

  async getTickerPath(ticker: string): Promise<string> {
    const r = await fetch(`${BASE}/tickers/${encodeURIComponent(ticker)}/path`);
    return (await jsonOrThrow<{ path: string }>(r)).path;
  },

  fileUrl(path: string): string {
    return `${BASE}/files?path=${encodeURIComponent(path)}`;
  },

  async searchTickers(q: string): Promise<TickerSearchHit[]> {
    if (!q.trim()) return [];
    const r = await fetch(`${BASE}/tickers/search?q=${encodeURIComponent(q)}`);
    return (await jsonOrThrow<{ results: TickerSearchHit[] }>(r)).results;
  },

  async createJob(opts: {
    workflow: Workflow;
    ticker?: string;
    tickers?: string[];
    question?: string;
  }): Promise<{ job_id: string; status: string; workflow: string }> {
    const r = await fetch(`${BASE}/jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(opts),
    });
    return jsonOrThrow(r);
  },

  async getJob(jobId: string): Promise<JobState> {
    const r = await fetch(`${BASE}/jobs/${jobId}`);
    return jsonOrThrow(r);
  },

  async listJobs(limit = 20): Promise<JobState[]> {
    const r = await fetch(`${BASE}/jobs?limit=${limit}`);
    return (await jsonOrThrow<{ jobs: JobState[] }>(r)).jobs;
  },
};
