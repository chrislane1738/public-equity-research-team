"use client";

import dynamic from "next/dynamic";
import { Button } from "@/components/ui/button";
import { Download } from "lucide-react";
import { api } from "@/lib/api";

import MarkdownPreview from "./preview/MarkdownPreview";
import JsonPreview from "./preview/JsonPreview";
import ImagePreview from "./preview/ImagePreview";
import XlsxPreview from "./preview/XlsxPreview";
import DocxPreview from "./preview/DocxPreview";
import PptxPreview from "./preview/PptxPreview";
import UnknownPreview from "./preview/UnknownPreview";

export interface PreviewProps {
  url: string;
  name: string;
}

// PDF preview pulls in pdfjs-dist which references DOMMatrix at module-eval
// time and breaks SSR. Defer loading to the client only.
const PdfPreview = dynamic(() => import("./preview/PdfPreview"), {
  ssr: false,
  loading: () => <p className="text-sm text-muted-foreground">Loading PDF…</p>,
});

export default function FilePreviewPanel({ path }: { path: string }) {
  const name = path.split("/").pop() ?? path;
  const ext = (name.split(".").pop() || "").toLowerCase();
  const url = api.fileUrl(path);

  const Body: React.ComponentType<PreviewProps> =
    ext === "md"
      ? MarkdownPreview
      : ext === "json"
        ? JsonPreview
        : ext === "png" || ext === "jpg" || ext === "jpeg"
          ? ImagePreview
          : ext === "xlsx"
            ? XlsxPreview
            : ext === "docx"
              ? DocxPreview
              : ext === "pdf"
                ? PdfPreview
                : ext === "pptx"
                  ? PptxPreview
                  : UnknownPreview;

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="border-b border-border px-4 py-2 flex items-center justify-between gap-4 bg-muted/30">
        <div className="text-xs font-mono text-muted-foreground truncate">{path}</div>
        <a href={url} download={name}>
          <Button variant="ghost" size="sm">
            <Download className="h-4 w-4 mr-1" />
            Download
          </Button>
        </a>
      </div>
      <div className="flex-1 overflow-auto px-4 py-4">
        <Body url={url} name={name} />
      </div>
    </div>
  );
}
