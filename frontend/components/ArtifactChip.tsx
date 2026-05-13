"use client";

import { useState } from "react";
import {
  FileText,
  Image as ImageIcon,
  FileSpreadsheet,
  Presentation,
  File as FileIcon,
} from "lucide-react";
import ArtifactPreviewModal from "./ArtifactPreviewModal";

const ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  md: FileText,
  txt: FileText,
  json: FileText,
  png: ImageIcon,
  jpg: ImageIcon,
  jpeg: ImageIcon,
  xlsx: FileSpreadsheet,
  pptx: Presentation,
  docx: FileText,
  pdf: FileText,
};

export default function ArtifactChip({ path }: { path: string }) {
  const [open, setOpen] = useState(false);
  const name = path.split("/").pop() ?? path;
  const ext = (name.split(".").pop() || "").toLowerCase();
  const Icon = ICONS[ext] ?? FileIcon;
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1.5 px-2 py-0.5 mx-0.5 text-xs border border-border rounded hover:bg-accent"
      >
        <Icon className="h-3 w-3" />
        {name}
      </button>
      {open && <ArtifactPreviewModal path={path} onClose={() => setOpen(false)} />}
    </>
  );
}
