"use client";

import type { Config, Data, Layout } from "plotly.js";
import { useEffect, useRef } from "react";

interface Props {
  data: Data[];
  layout: Partial<Layout>;
  title: string;
}

const CONFIG: Partial<Config> = { responsive: true, displaylogo: false };

/**
 * Thin wrapper around Plotly. Plotly touches `window`, so it is imported lazily on the
 * client inside an effect; `Plotly.react` diffs against the previous figure for cheap updates.
 */
export function PlotlyChart({ data, layout, title }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    const el = ref.current;
    void import("plotly.js-dist-min").then(({ default: Plotly }) => {
      if (cancelled || !el) return;
      const styles = getComputedStyle(document.documentElement);
      const fg = styles.getPropertyValue("--fg").trim() || "#1a1d24";
      const grid = styles.getPropertyValue("--grid").trim() || "#e3e6ec";
      void Plotly.react(
        el,
        data,
        {
          margin: { l: 64, r: 16, t: 16, b: 52 },
          paper_bgcolor: "transparent",
          plot_bgcolor: "transparent",
          font: { family: "inherit", color: fg, size: 12 },
          legend: { orientation: "h", y: -0.22 },
          ...layout,
          xaxis: { gridcolor: grid, zerolinecolor: grid, ...layout.xaxis },
          yaxis: { gridcolor: grid, zerolinecolor: grid, ...layout.yaxis },
        },
        CONFIG,
      );
    });
    return () => {
      cancelled = true;
    };
  }, [data, layout]);

  useEffect(() => {
    const el = ref.current;
    return () => {
      if (el) void import("plotly.js-dist-min").then(({ default: Plotly }) => Plotly.purge(el));
    };
  }, []);

  return <div ref={ref} className="chart" role="img" aria-label={title} />;
}
