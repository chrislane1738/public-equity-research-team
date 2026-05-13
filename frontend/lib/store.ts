"use client";
import { create } from "zustand";
import type { FileNode, JobState } from "./types";

export interface Tab {
  id: string;
  label: string;
  pinned?: boolean;
}

export interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  agent?: string;
  ts: number;
}

interface State {
  selectedTicker: string | null;
  recentTickers: string[];

  tabs: Tab[];
  activeTabId: string;

  activeJob: JobState | null;
  jobLog: { agent: string; cost: number; ts: string }[];

  messagesByTab: Record<string, Message[]>;
  fileTree: FileNode[];

  selectTicker: (t: string) => void;
  openTab: (tab: Tab) => void;
  closeTab: (id: string) => void;
  setActiveTab: (id: string) => void;
  appendMessage: (tabId: string, msg: Message) => void;
  setActiveJob: (job: JobState | null) => void;
  pushJobLog: (entry: { agent: string; cost: number; ts: string }) => void;
  setFileTree: (tree: FileNode[]) => void;
}

export const useWorkspace = create<State>((set, get) => ({
  selectedTicker: null,
  recentTickers: [],
  tabs: [{ id: "md", label: "MD", pinned: true }],
  activeTabId: "md",
  activeJob: null,
  jobLog: [],
  messagesByTab: { md: [] },
  fileTree: [],

  selectTicker(t) {
    const { recentTickers } = get();
    const next = [t, ...recentTickers.filter((r) => r !== t)].slice(0, 5);
    set({ selectedTicker: t, recentTickers: next });
  },

  openTab(tab) {
    const { tabs, messagesByTab } = get();
    if (tabs.find((x) => x.id === tab.id)) {
      set({ activeTabId: tab.id });
      return;
    }
    set({
      tabs: [...tabs, tab],
      activeTabId: tab.id,
      messagesByTab: { ...messagesByTab, [tab.id]: messagesByTab[tab.id] ?? [] },
    });
  },

  closeTab(id) {
    if (id === "md") return;
    const { tabs, activeTabId } = get();
    const next = tabs.filter((t) => t.id !== id);
    set({
      tabs: next,
      activeTabId: activeTabId === id ? "md" : activeTabId,
    });
  },

  setActiveTab(id) {
    set({ activeTabId: id });
  },

  appendMessage(tabId, msg) {
    const { messagesByTab } = get();
    const list = messagesByTab[tabId] ?? [];
    set({ messagesByTab: { ...messagesByTab, [tabId]: [...list, msg] } });
  },

  setActiveJob(job) {
    set({ activeJob: job, jobLog: job ? get().jobLog : [] });
  },

  pushJobLog(entry) {
    set({ jobLog: [...get().jobLog, entry] });
  },

  setFileTree(tree) {
    set({ fileTree: tree });
  },
}));
