"use client";
import type { PreviewProps } from "../ArtifactPreviewModal";

export default function ImagePreview({ url, name }: PreviewProps) {
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={url} alt={name} className="w-full h-auto" />;
}
