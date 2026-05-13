"use client";
import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { PreviewProps } from "../ArtifactPreviewModal";

export default function MarkdownPreview({ url }: PreviewProps) {
  const [text, setText] = useState("");
  useEffect(() => {
    fetch(url)
      .then((r) => r.text())
      .then(setText)
      .catch((e) => setText(`Error: ${e.message}`));
  }, [url]);
  return (
    <div className="prose prose-invert prose-sm max-w-none">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
    </div>
  );
}
