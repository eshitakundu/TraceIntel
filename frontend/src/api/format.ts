export function formatUnits(raw: string, decimals: number | null): string {
  if (decimals === null || decimals === 0) return raw;
  const padded = raw.padStart(decimals + 1, "0");
  const fraction = padded.slice(-decimals).replace(/0+$/, "");
  return padded.slice(0, -decimals) + (fraction ? "." + fraction : "");
}

/** Compact display only; exact quantities remain in the report and raw details. */
export function formatCompactUnits(
  raw: string,
  decimals: number | null,
): string {
  const exact = formatUnits(raw, decimals);
  const whole = exact.split(".")[0];
  if (whole.length <= 18) return exact;
  const exponent = String(whole.length - 1).replace(
    /[0-9]/g,
    (digit) => "⁰¹²³⁴⁵⁶⁷⁸⁹"[Number(digit)],
  );
  return "≈ " + whole[0] + "." + whole.slice(1, 5) + " × 10" + exponent;
}
