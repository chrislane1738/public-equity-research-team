"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { useWorkspace } from "@/lib/store";
import { api } from "@/lib/api";
import {
  ChevronRight,
  ChevronDown,
  Folder,
  File as FileIcon,
} from "lucide-react";
import type { FileNode } from "@/lib/types";

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
  const openTab = useWorkspace((s) => s.openTab);

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

  function handleOpenFile(path: string) {
    const name = path.split("/").pop() ?? path;
    openTab({ id: `file:${path}`, label: name });
  }

  return (
    <div className="p-3">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs uppercase text-muted-foreground tracking-wider">
          {selectedTicker ?? "no ticker selected"}
        </h3>
        {selectedTicker && (
          <button
            type="button"
            className="text-xs text-muted-foreground hover:text-foreground underline"
            onClick={async () => {
              try {
                const p = await api.getTickerPath(selectedTicker);
                await navigator.clipboard.writeText(p);
                toast.success(`Path copied: ${p}`);
              } catch (e) {
                toast.error(`Couldn't copy path: ${(e as Error).message}`);
              }
            }}
          >
            Copy path
          </button>
        )}
      </div>
      {selectedTicker && fileTree.length === 0 && (
        <p className="text-xs text-muted-foreground italic">
          No artifacts yet. Run a workflow.
        </p>
      )}
      {fileTree.map((n) => (
        <Node key={n.path} node={n} depth={0} onOpenFile={handleOpenFile} />
      ))}
    </div>
  );
}
