"use client";

import { useWorkspace } from "@/lib/store";
import { cn } from "@/lib/utils";
import { X } from "lucide-react";

export default function TabBar() {
  const tabs = useWorkspace((s) => s.tabs);
  const activeTabId = useWorkspace((s) => s.activeTabId);
  const setActiveTab = useWorkspace((s) => s.setActiveTab);
  const closeTab = useWorkspace((s) => s.closeTab);

  return (
    <div className="h-10 border-b border-border flex items-center px-2 gap-1 overflow-x-auto">
      {tabs.map((t) => (
        <div
          key={t.id}
          role="tab"
          aria-selected={activeTabId === t.id}
          className={cn(
            "group flex items-center gap-2 px-3 py-1 text-sm rounded-t-md cursor-pointer select-none",
            activeTabId === t.id
              ? "bg-background border-x border-t border-border -mb-px"
              : "text-muted-foreground hover:bg-accent",
          )}
          onClick={() => setActiveTab(t.id)}
        >
          <span>{t.label}</span>
          {!t.pinned && (
            <button
              aria-label={`close ${t.label} tab`}
              className="opacity-0 group-hover:opacity-100 hover:text-foreground transition-opacity"
              onClick={(e) => {
                e.stopPropagation();
                closeTab(t.id);
              }}
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
