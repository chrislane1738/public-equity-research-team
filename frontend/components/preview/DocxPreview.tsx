"use client";
import { useEffect, useState } from "react";
import type { PreviewProps } from "../ArtifactPreviewModal";

export default function DocxPreview({ url }: PreviewProps) {
  const [html, setHtml] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const buf = await (await fetch(url)).arrayBuffer();
        // Dynamic import so mammoth's browser bundle ships only when needed.
        const mod = await import("mammoth");
        const mammoth = mod.default ?? mod;
        const out = await mammoth.convertToHtml({ arrayBuffer: buf });
        if (!cancelled) setHtml(out.value);
      } catch (e) {
        if (!cancelled) setHtml(`<p>Error: ${(e as Error).message}</p>`);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [url]);

  return (
    <div
      className="prose prose-invert prose-sm max-w-none"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
