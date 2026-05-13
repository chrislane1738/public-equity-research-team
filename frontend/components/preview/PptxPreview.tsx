"use client";
import { useEffect, useState } from "react";
import JSZip from "jszip";
import type { PreviewProps } from "../FilePreviewPanel";

interface SlideTitle {
  idx: number;
  title: string;
}

export default function PptxPreview({ url, name }: PreviewProps) {
  const [slides, setSlides] = useState<SlideTitle[]>([]);

  useEffect(() => {
    fetch(url)
      .then((r) => r.arrayBuffer())
      .then(async (buf) => {
        const zip = await JSZip.loadAsync(buf);
        const slideFiles = Object.keys(zip.files)
          .filter((n) => /^ppt\/slides\/slide\d+\.xml$/.test(n))
          .sort((a, b) => Number(a.match(/\d+/)![0]) - Number(b.match(/\d+/)![0]));
        const titles: SlideTitle[] = [];
        for (let i = 0; i < slideFiles.length; i++) {
          const xml = await zip.files[slideFiles[i]].async("text");
          const m = xml.match(/<a:t>([^<]+)<\/a:t>/);
          titles.push({ idx: i + 1, title: m ? m[1] : `Slide ${i + 1}` });
        }
        setSlides(titles);
      });
  }, [url]);

  return (
    <div>
      <p className="text-xs text-muted-foreground mb-3">
        {name} · {slides.length} slides · pptx full preview not supported in browser; download to open.
      </p>
      <ol className="space-y-1 text-sm list-decimal pl-5">
        {slides.map((s) => (
          <li key={s.idx}>{s.title}</li>
        ))}
      </ol>
    </div>
  );
}
