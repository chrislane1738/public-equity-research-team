"use client";

import dynamic from "next/dynamic";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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

// PDF preview pulls in pdfjs-dist which references DOMMatrix at module-eval
// time and breaks SSR. Defer loading to the client only.
const PdfPreview = dynamic(() => import("./preview/PdfPreview"), {
  ssr: false,
  loading: () => (
    <p className="text-sm text-muted-foreground">Loading PDF…</p>
  ),
});

export interface PreviewProps {
  url: string;
  name: string;
}

export default function ArtifactPreviewModal({
  path,
  onClose,
}: {
  path: string;
  onClose: () => void;
}) {
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
    <Dialog
      open
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
    >
      <DialogContent className="max-w-4xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <div className="flex flex-row items-center justify-between gap-4">
            <DialogTitle className="text-sm font-mono truncate">{path}</DialogTitle>
            <a href={url} download={name}>
              <Button variant="ghost" size="sm">
                <Download className="h-4 w-4 mr-1" />
                Download
              </Button>
            </a>
          </div>
        </DialogHeader>
        <Body url={url} name={name} />
      </DialogContent>
    </Dialog>
  );
}
