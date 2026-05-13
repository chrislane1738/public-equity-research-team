"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

export default function ThesisCheckDialog({
  ticker,
  open,
  onCancel,
  onSubmit,
}: {
  ticker: string;
  open: boolean;
  onCancel: () => void;
  onSubmit: (question: string) => void;
}) {
  const [q, setQ] = useState("");
  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) onCancel();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Thesis check — {ticker}</DialogTitle>
        </DialogHeader>
        <textarea
          rows={4}
          autoFocus
          className="w-full bg-background border border-border rounded p-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
          placeholder="What part of the thesis are you checking? e.g. 'Are NVDA H100 ASPs holding above $25k or compressing?'"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <div className="flex justify-end gap-2 mt-2">
          <Button variant="ghost" size="sm" onClick={onCancel}>
            Cancel
          </Button>
          <Button size="sm" disabled={!q.trim()} onClick={() => onSubmit(q.trim())}>
            Run
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
