"use client";

import { useEffect, useState } from "react";
import { useWorkspace } from "@/lib/store";
import { api } from "@/lib/api";
import {
  ChevronRight,
  ChevronDown,
  Folder,
  File as FileIcon,
} from "lucide-react";
import type { FileNode } from "@/lib/types";
import ArtifactPreviewModal from "./ArtifactPreviewModal";

function Node({
  node,
  depth,
  onOpenFile,
}: {
  node: FileNode;
  depth: number;
  onOpenFile: (path: string) => void;
}) {
  const [open, setOpen] = useState(depth < 1);

  if (node.kind === "dir") {
    return (
      <div>
        <button
          type="button"
          onClick={() => setOpen(!open)}
          className="flex items-center gap-1 w-full hover:bg-accent rounded-sm px-1 py-0.5 text-sm"
          style={{ paddingLeft: `${depth * 12 + 4}px` }}
        >
          {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
          <Folder className="h-3 w-3" />
          <span className="truncate">{node.name}</span>
        </button>
        {open &&
          node.children?.map((child) => (
            <Node key={child.path} node={child} depth={depth + 1} onOpenFile={onOpenFile} />
          ))}
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={() => onOpenFile(node.path)}
      className="flex items-center gap-1 w-full hover:bg-accent rounded-sm px-1 py-0.5 text-xs text-muted-foreground"
      style={{ paddingLeft: `${depth * 12 + 16}px` }}
    >
      <FileIcon className="h-3 w-3" />
      <span className="truncate">{node.name}</span>
    </button>
  );
}

export default function FolderTree() {
  const selectedTicker = useWorkspace((s) => s.selectedTicker);
  const fileTree = useWorkspace((s) => s.fileTree);
  const setFileTree = useWorkspace((s) => s.setFileTree);
  const [previewPath, setPreviewPath] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedTicker) {
      setFileTree([]);
      return;
    }
    api
      .listFiles(selectedTicker)
      .then(setFileTree)
      .catch(() => setFileTree([]));
  }, [selectedTicker, setFileTree]);

  return (
    <div className="p-3">
      <h3 className="text-xs uppercase text-muted-foreground tracking-wider mb-2">
        {selectedTicker ?? "no ticker selected"}
      </h3>
      {selectedTicker && fileTree.length === 0 && (
        <p className="text-xs text-muted-foreground italic">
          No artifacts yet. Run a workflow.
        </p>
      )}
      {fileTree.map((n) => (
        <Node key={n.path} node={n} depth={0} onOpenFile={setPreviewPath} />
      ))}
      {previewPath && (
        <ArtifactPreviewModal path={previewPath} onClose={() => setPreviewPath(null)} />
      )}
    </div>
  );
}
