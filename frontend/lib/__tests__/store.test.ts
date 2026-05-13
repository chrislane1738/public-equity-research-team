import { describe, it, expect, beforeEach } from "vitest";
import { useWorkspace } from "../store";

beforeEach(() => {
  useWorkspace.setState({
    selectedTicker: null,
    recentTickers: [],
    tabs: [{ id: "md", label: "MD", pinned: true }],
    activeTabId: "md",
    activeJob: null,
    jobLog: [],
    messagesByTab: { md: [] },
    fileTree: [],
  });
});

describe("workspace store", () => {
  it("selectTicker pushes onto MRU and caps at 5", () => {
    const { selectTicker } = useWorkspace.getState();
    ["A", "B", "C", "D", "E", "F"].forEach((t) => selectTicker(t));
    expect(useWorkspace.getState().recentTickers).toEqual(["F", "E", "D", "C", "B"]);
    expect(useWorkspace.getState().selectedTicker).toBe("F");
  });

  it("selectTicker dedupes existing ticker before pushing", () => {
    const { selectTicker } = useWorkspace.getState();
    ["A", "B", "C", "A"].forEach((t) => selectTicker(t));
    expect(useWorkspace.getState().recentTickers).toEqual(["A", "C", "B"]);
  });

  it("openTab adds new tab and activates it", () => {
    useWorkspace.getState().openTab({ id: "dcf", label: "DCF" });
    expect(useWorkspace.getState().activeTabId).toBe("dcf");
    expect(useWorkspace.getState().tabs.length).toBe(2);
  });

  it("openTab is idempotent — re-opening just activates", () => {
    useWorkspace.getState().openTab({ id: "dcf", label: "DCF" });
    useWorkspace.getState().openTab({ id: "md", label: "MD", pinned: true });
    useWorkspace.getState().openTab({ id: "dcf", label: "DCF" });
    expect(useWorkspace.getState().tabs.length).toBe(2);
    expect(useWorkspace.getState().activeTabId).toBe("dcf");
  });

  it("closeTab refuses to close MD", () => {
    useWorkspace.getState().closeTab("md");
    expect(useWorkspace.getState().tabs.find((t) => t.id === "md")).toBeTruthy();
  });

  it("closeTab falls back to MD if active tab is closed", () => {
    useWorkspace.getState().openTab({ id: "dcf", label: "DCF" });
    useWorkspace.getState().closeTab("dcf");
    expect(useWorkspace.getState().activeTabId).toBe("md");
    expect(useWorkspace.getState().tabs.length).toBe(1);
  });

  it("appendMessage targets the right tab", () => {
    useWorkspace.getState().appendMessage("md", {
      id: "1", role: "user", content: "hi", ts: 1,
    });
    expect(useWorkspace.getState().messagesByTab.md.length).toBe(1);
  });
});
