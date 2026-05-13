"use client";

import TickerPicker from "./TickerPicker";
import BackendStatusPill from "./BackendStatusPill";

export default function TopBar() {
  return (
    <header className="h-12 border-b border-border flex items-center px-4 gap-3">
      <TickerPicker />
      <div className="flex-1" />
      <BackendStatusPill />
    </header>
  );
}
