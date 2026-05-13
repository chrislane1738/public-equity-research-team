"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { TickerSearchHit } from "@/lib/types";
import { useWorkspace } from "@/lib/store";

export default function TickerPicker() {
  const selectedTicker = useWorkspace((s) => s.selectedTicker);
  const selectTicker = useWorkspace((s) => s.selectTicker);

  // Track the last external selectedTicker we've reflected into the draft.
  // When selectedTicker changes externally (e.g., sidebar click), we re-sync
  // the input value. We compare during render so setState happens during render,
  // not inside an effect (React 19 / react-hooks/set-state-in-effect compliant).
  const [draft, setDraft] = useState(selectedTicker ?? "");
  const [lastSyncedSelection, setLastSyncedSelection] = useState(selectedTicker);
  if (selectedTicker !== lastSyncedSelection) {
    setLastSyncedSelection(selectedTicker);
    if (selectedTicker) setDraft(selectedTicker);
  }

  const [hits, setHits] = useState<TickerSearchHit[]>([]);
  const [open, setOpen] = useState(false);
  const debounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (debounce.current) clearTimeout(debounce.current);
    const q = draft.trim();
    debounce.current = setTimeout(() => {
      if (!q) {
        setHits([]);
        return;
      }
      api
        .searchTickers(q)
        .then(setHits)
        .catch(() => setHits([]));
    }, 150);
    return () => {
      if (debounce.current) clearTimeout(debounce.current);
    };
  }, [draft]);

  function commit(symbol: string) {
    selectTicker(symbol);
    setDraft(symbol);
    setOpen(false);
  }

  return (
    <div className="relative">
      <input
        value={draft}
        onChange={(e) => {
          setDraft(e.target.value.toUpperCase());
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 100)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            const trimmed = draft.trim().toUpperCase();
            if (trimmed) commit(trimmed);
          }
          if (e.key === "Escape") setOpen(false);
        }}
        placeholder="Ticker"
        className="w-44 h-8 px-2 text-sm bg-background border border-border rounded focus:outline-none focus:ring-1 focus:ring-ring"
      />
      {open && hits.length > 0 && (
        <div className="absolute top-9 left-0 w-72 bg-popover border border-border rounded shadow-md z-50 max-h-80 overflow-y-auto">
          {hits.map((h) => (
            <button
              key={h.symbol}
              type="button"
              onMouseDown={(e) => {
                e.preventDefault(); // prevent blur before click
                commit(h.symbol);
              }}
              className="block w-full text-left px-3 py-1.5 text-sm hover:bg-accent"
            >
              <span className="font-mono mr-2">{h.symbol}</span>
              <span className="text-muted-foreground text-xs">{h.name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
