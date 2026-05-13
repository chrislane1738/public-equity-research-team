import { describe, it, expect, vi } from "vitest";
import { openJobStream } from "../ws";

class FakeWS {
  static instances: FakeWS[] = [];
  onmessage: ((e: { data: string }) => void) | null = null;
  onerror: ((e: Event) => void) | null = null;
  onclose: (() => void) | null = null;
  constructor(public url: string) {
    FakeWS.instances.push(this);
  }
  close() {
    this.onclose?.();
  }
  emit(payload: unknown) {
    this.onmessage?.({ data: JSON.stringify(payload) });
  }
}

describe("openJobStream", () => {
  it("translates http base URL to ws and dispatches events", () => {
    vi.stubGlobal("WebSocket", FakeWS);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const seen: any[] = [];
    const h = openJobStream("http://127.0.0.1:8001", "job-1", (e) => seen.push(e));
    const ws = FakeWS.instances.at(-1)!;
    expect(ws.url).toBe("ws://127.0.0.1:8001/jobs/job-1/stream");
    ws.emit({ type: "agent_completed", agent: "dcf", job_id: "job-1",
              input_tokens: 10, output_tokens: 5, cost_usd: 0.01,
              stop_reason: null, ts: "2026-05-13T00:00:00Z" });
    expect(seen[0].agent).toBe("dcf");
    h.close();
  });

  it("close() prevents reconnect attempts", () => {
    vi.useFakeTimers();
    vi.stubGlobal("WebSocket", FakeWS);
    const h = openJobStream("http://127.0.0.1:8001", "job-2", () => {});
    h.close();
    const before = FakeWS.instances.length;
    vi.advanceTimersByTime(10_000);
    expect(FakeWS.instances.length).toBe(before);
    vi.useRealTimers();
  });
});
