import type { Metadata } from "next";

import { QuantLab } from "@/components/QuantLab";

export const metadata: Metadata = { title: "Dataset profile" };

export default function DatasetProfilePage() {
  return (
    <>
      <header className="page-header">
        <p className="eyebrow">Quant Research Lab</p>
        <h1>Dataset profile</h1>
        <p>
          Before analysing data, find out what is actually in it. Import a CSV file (or use a
          bundled sample) to see its column types, missing values, duplicate rows and descriptive
          statistics, with every interpretation rule stated. This describes the file; it does not
          test or predict anything.
        </p>
      </header>
      <QuantLab />
    </>
  );
}
