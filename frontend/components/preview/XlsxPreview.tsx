"use client";
import { useEffect, useState } from "react";
import * as XLSX from "xlsx";
import type { PreviewProps } from "../FilePreviewPanel";

export default function XlsxPreview({ url }: PreviewProps) {
  const [sheets, setSheets] = useState<{ name: string; rows: unknown[][] }[]>([]);
  const [active, setActive] = useState(0);

  useEffect(() => {
    fetch(url)
      .then((r) => r.arrayBuffer())
      .then((buf) => {
        const wb = XLSX.read(buf);
        setSheets(
          wb.SheetNames.map((n) => ({
            name: n,
            rows: XLSX.utils.sheet_to_json(wb.Sheets[n], { header: 1 }) as unknown[][],
          })),
        );
      });
  }, [url]);

  if (sheets.length === 0) return <p className="text-sm text-muted-foreground">Loading…</p>;
  const sheet = sheets[active];
  return (
    <div>
      <div className="flex gap-1 mb-2 flex-wrap">
        {sheets.map((s, i) => (
          <button
            key={s.name}
            onClick={() => setActive(i)}
            className={`px-2 py-0.5 text-xs rounded ${
              i === active ? "bg-accent" : "hover:bg-accent/50"
            }`}
          >
            {s.name}
          </button>
        ))}
      </div>
      <div className="overflow-auto max-h-[60vh]">
        <table className="text-xs">
          <tbody>
            {sheet.rows.slice(0, 200).map((row, i) => (
              <tr key={i} className="border-b border-border">
                {(row as unknown[]).map((c, j) => (
                  <td key={j} className="px-2 py-0.5 whitespace-nowrap">
                    {String(c ?? "")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {sheet.rows.length > 200 && (
          <p className="mt-2 text-xs text-muted-foreground">
            Showing first 200 of {sheet.rows.length} rows. Download for full file.
          </p>
        )}
      </div>
    </div>
  );
}
