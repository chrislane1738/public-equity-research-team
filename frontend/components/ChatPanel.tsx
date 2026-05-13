"use client";

import { useEffect, useRef } from "react";
import { useWorkspace } from "@/lib/store";
import { api } from "@/lib/api";
import { openJobStream } from "@/lib/ws";
import type { JobStreamHandle } from "@/lib/ws";
import MdProgress from "./MdProgress";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { toast } from "sonner";

function nowMs() {
  return Date.now();
}

function uuid() {
  return crypto.randomUUID();
}

export default function ChatPanel() {
  const activeTabId = useWorkspace((s) => s.activeTabId);
  const messages = useWorkspace((s) => s.messagesByTab[s.activeTabId] ?? []);
  const appendMessage = useWorkspace((s) => s.appendMessage);
  const setActiveJob = useWorkspace((s) => s.setActiveJob);
  const pushJobLog = useWorkspace((s) => s.pushJobLog);
  const selectTicker = useWorkspace((s) => s.selectTicker);
  const setFileTree = useWorkspace((s) => s.setFileTree);

  const scrollRef = useRef<HTMLDivElement>(null);
  const streamRef = useRef<JobStreamHandle | null>(null);

  // Auto-scroll to the latest message.
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages.length]);

  // Listen for job:dispatched events from TopBar.
  useEffect(() => {
    async function handler(e: Event) {
      const { jobId, ticker } = (
        e as CustomEvent<{ jobId: string; ticker: string; workflow: string }>
      ).detail;

      selectTicker(ticker);

      try {
        const initial = await api.getJob(jobId);
        setActiveJob(initial);
      } catch {
        // Repo may not have flushed; the WS state frame will hydrate.
      }

      // Close any prior stream before opening a new one. Multiple dispatches
      // while a previous job is in flight would otherwise leave abandoned
      // WebSockets that keep writing to the MD message stream.
      streamRef.current?.close();
      streamRef.current = openJobStream(api.baseUrl, jobId, async (ev) => {
        if (ev.type === "state") {
          setActiveJob(ev.state);
          if (ev.state.status === "complete") {
            toast.success(`${ev.state.workflow} for ${ev.state.ticker} complete`);
            try {
              const tree = await api.listFiles(ticker);
              setFileTree(tree);
            } catch {
              // ignore — tree refresh is best-effort
            }
          }
          if (ev.state.status === "failed") {
            toast.error(
              `Job ${ev.state.workflow} failed: ${ev.state.error ?? "unknown"}`,
            );
          }
        }
        if (ev.type === "agent_completed") {
          pushJobLog({ agent: ev.agent, cost: ev.cost_usd, ts: ev.ts });
          appendMessage("md", {
            id: uuid(),
            role: "assistant",
            agent: ev.agent,
            content: `**${ev.agent}** complete · $${ev.cost_usd.toFixed(3)}`,
            ts: nowMs(),
          });
        }
        if (ev.type === "agent_failed") {
          appendMessage("md", {
            id: uuid(),
            role: "system",
            content: `❌ **${ev.agent}** failed: ${ev.error}`,
            ts: nowMs(),
          });
        }
      });
    }

    window.addEventListener("job:dispatched", handler as EventListener);
    return () => {
      window.removeEventListener("job:dispatched", handler as EventListener);
      streamRef.current?.close();
      streamRef.current = null;
    };
  }, [appendMessage, pushJobLog, selectTicker, setActiveJob, setFileTree]);

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {activeTabId === "md" && <MdProgress />}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {messages.length === 0 && (
          <p className="text-sm text-muted-foreground italic">
            No messages yet. Pick a ticker and click a workflow button to start.
          </p>
        )}
        {messages.map((m) => (
          <div key={m.id} className="text-sm">
            <div className="text-xs text-muted-foreground mb-1">
              {m.role}
              {m.agent ? ` · ${m.agent}` : ""}
            </div>
            <div className="prose prose-invert prose-sm max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
