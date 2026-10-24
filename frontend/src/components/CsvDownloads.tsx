"use client";

import { useMemo } from "react";

import { csvFilename, type Table, toCsv } from "@/lib/export/csv";
import { type ExportableResponse, exportTables } from "@/lib/export/tables";

/** Save `text` as a file, made in the browser: nothing is sent to the server. */
function saveFile(text: string, filename: string) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/csv;charset=utf-8" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/** One CSV download button per table this model exports, from the response on screen. */
export function CsvDownloads({ response }: { response: ExportableResponse }) {
  const tables = useMemo(() => exportTables(response), [response]);
  if (tables.length === 0) return null;
  // Only claim units when this model's tables carry some (the dataset profile has none).
  const hasUnits = tables.some((t) => t.columns.some((c) => c.unit));
  const download = (t: Table) =>
    saveFile(toCsv(t), csvFilename(response.model.id, response.metadata.run_id, t.name));
  return (
    <>
      <div className="download-buttons" role="group" aria-label="Download as CSV">
        {tables.map((t) => (
          <button key={t.name} type="button" className="secondary" onClick={() => download(t)}>
            Download {t.label} (CSV)
          </button>
        ))}
      </div>
      <p className="note">
        The values of this run exactly as computed, at full precision
        {hasUnits ? ", with units in the headers where the model gives them" : ""}.
      </p>
    </>
  );
}
