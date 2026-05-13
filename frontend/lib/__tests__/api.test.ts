import { describe, it, expect, vi, beforeEach } from "vitest";
import { api } from "../api";

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("api.searchTickers", () => {
  it("short-circuits on empty query", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    expect(await api.searchTickers("")).toEqual([]);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("returns parsed results", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          results: [{ symbol: "NVDA", name: "NVIDIA", exchange: "NASDAQ" }],
        }),
      }),
    );
    const out = await api.searchTickers("NV");
    expect(out[0].symbol).toBe("NVDA");
  });
});

describe("api.createJob", () => {
  it("POSTs JSON and returns body", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ job_id: "x", status: "running", workflow: "morning-note" }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const out = await api.createJob({ workflow: "morning-note", ticker: "NVDA" });
    expect(out.job_id).toBe("x");
    const [, init] = fetchMock.mock.calls[0];
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body).ticker).toBe("NVDA");
  });

  it("throws on non-ok", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        statusText: "Bad",
        text: async () => "bad",
      }),
    );
    await expect(
      api.createJob({ workflow: "morning-note", ticker: "" }),
    ).rejects.toThrow(/HTTP 400/);
  });
});

describe("api.fileUrl", () => {
  it("URL-encodes the path", () => {
    expect(api.fileUrl("NVDA/folder with space/file.md")).toContain(
      "NVDA%2Ffolder%20with%20space%2Ffile.md",
    );
  });
});

describe("api.listJobs", () => {
  it("returns parsed job list", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          jobs: [{ id: "1", ticker: "NVDA", workflow: "morning-note", status: "complete",
                   current_stage: null, stages: {}, rating: "Buy",
                   error: null, created_at: null, completed_at: null }],
        }),
      }),
    );
    const out = await api.listJobs(5);
    expect(out[0].ticker).toBe("NVDA");
  });
});
