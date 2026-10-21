/**
 * Bar centres and widths for histogram bins with the given edges, without overflow.
 *
 * Values can be as large as about 1.8e308, so (a + b) / 2 can overflow to Infinity even
 * when a and b are finite; then a / 2 + b / 2 is used instead. Otherwise (a + b) / 2 is kept,
 * because halving first would round the tiniest (subnormal) values to 0. Widths are always
 * finite: the backend uses at least two bins whenever min < max, so no bin spans more than
 * the largest double. A zero width (a constant column's single bin) becomes 1, so the bar is
 * visible.
 */
export function binGeometry(edges: number[]): { centres: number[]; widths: number[] } {
  const centres: number[] = [];
  const widths: number[] = [];
  for (let i = 0; i + 1 < edges.length; i++) {
    const a = edges[i]!;
    const b = edges[i + 1]!;
    const mid = (a + b) / 2;
    centres.push(Number.isFinite(mid) ? mid : a / 2 + b / 2);
    const w = b - a;
    widths.push(w > 0 ? w : 1);
  }
  return { centres, widths };
}
