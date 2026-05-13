"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

export default function SectorSweepDialog({
  initial,
  open,
  onCancel,
  onSubmit,
}: {
  initial: string;
  open: boolean;
  onCancel: () => void;
  onSubmit: (tickers: string[]) => void;
}) {
  const [text, setText] = useState(initial);

  function parse(): string[] {
    return text
      .split(/[\s,]+/)
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean);
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) onCancel();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Sector sweep — pick tickers</DialogTitle>
        </DialogHeader>
        <textarea
          rows={3}
          autoFocus
          className="w-full bg-background border border-border rounded p-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
          placeholder="NVDA AMD AVGO ARM"
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <p className="text-xs text-muted-foreground mt-1">
          Whitespace- or comma-separated. Need at least 2 tickers.
        </p>
        <div className="flex justify-end gap-2 mt-2">
          <Button variant="ghost" size="sm" onClick={onCancel}>
            Cancel
          </Button>
          <Button size="sm" disabled={parse().length < 2} onClick={() => onSubmit(parse())}>
            Run sweep
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
