"use client";
import type { PreviewProps } from "../ArtifactPreviewModal";

export default function UnknownPreview({ name }: PreviewProps) {
  return (
    <p className="text-sm text-muted-foreground">
      No in-browser preview for <code>{name}</code>. Use Download.
    </p>
  );
}
