"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export default function BackendStatusPill() {
  const [ok, setOk] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function ping() {
      try {
        const r = await fetch(`${api.baseUrl}/healthz`, { cache: "no-store" });
        if (!cancelled) setOk(r.ok);
      } catch {
        if (!cancelled) setOk(false);
      }
    }
    ping();
    const t = setInterval(ping, 5000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, []);

  const color =
    ok === null ? "bg-muted-foreground" : ok ? "bg-emerald-500" : "bg-red-500";
  const label =
    ok === null ? "Connecting…" : ok ? "Connected" : "Backend unreachable";

  return (
    <Tooltip>
      <TooltipTrigger
        type="button"
        className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-default focus:outline-none"
      >
        <span className={cn("h-2 w-2 rounded-full", color)} />
        {label}
      </TooltipTrigger>
      <TooltipContent>GET {api.baseUrl}/healthz</TooltipContent>
    </Tooltip>
  );
}
