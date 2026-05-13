"use client";
import { useEffect, useState } from "react";
import type { PreviewProps } from "../FilePreviewPanel";

export default function JsonPreview({ url }: PreviewProps) {
  const [text, setText] = useState("");
  useEffect(() => {
    fetch(url)
      .then((r) => r.text())
      .then(setText)
      .catch((e) => setText(`Error: ${e.message}`));
  }, [url]);
  let pretty = text;
  try {
    pretty = JSON.stringify(JSON.parse(text), null, 2);
  } catch {
    // leave raw text if not valid JSON
  }
  return <pre className="text-xs bg-muted/40 p-3 rounded overflow-x-auto">{pretty}</pre>;
}
