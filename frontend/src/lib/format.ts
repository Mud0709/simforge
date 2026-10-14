/** Format a value to `sig` significant figures, switching to scientific notation for very
 *  large or small magnitudes. Trailing zeros are dropped: they would imply precision. */
export function formatSig(x: number, sig = 6): string {
  if (!Number.isFinite(x)) return "—";
  if (x === 0) return "0";
  const a = Math.abs(x);
  if (a >= 1e-3 && a < 1e6) return String(Number(x.toPrecision(sig)));
  return formatExp(x, sig);
}

/** Scientific notation with `sig` significant figures, e.g. 2.2e-12. */
export function formatExp(x: number, sig = 2): string {
  if (!Number.isFinite(x)) return "—";
  if (x === 0) return "0";
  const [mantissa, exponent] = x.toExponential(sig - 1).split("e");
  const trimmed = mantissa!.includes(".") ? mantissa!.replace(/\.?0+$/, "") : mantissa!;
  return `${trimmed}e${exponent!.replace("+", "")}`;
}
