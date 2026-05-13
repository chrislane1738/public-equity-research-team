"use client";
import { useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import type { PreviewProps } from "../FilePreviewPanel";

pdfjs.GlobalWorkerOptions.workerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjs.version}/pdf.worker.min.mjs`;

export default function PdfPreview({ url }: PreviewProps) {
  // Key on `url` so React fully remounts the inner component when the file
  // changes — that resets numPages without a setState-in-effect.
  return <PdfDoc key={url} url={url} />;
}

function PdfDoc({ url }: { url: string }) {
  const [numPages, setNumPages] = useState(0);
  return (
    <Document file={url} onLoadSuccess={(d) => setNumPages(d.numPages)}>
      {Array.from(new Array(numPages), (_, i) => (
        <Page key={i} pageNumber={i + 1} width={720} />
      ))}
    </Document>
  );
}
