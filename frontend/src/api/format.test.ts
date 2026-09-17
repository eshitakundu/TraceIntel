import { expect, it } from "vitest";
import { formatUnits, formatCompactUnits } from "./format";

it("formats token amounts without floating-point conversion", () => {
  expect(formatUnits("1000001", 6)).toBe("1.000001");
  expect(formatUnits("1", 18)).toBe("0.000000000000000001");
  expect(formatUnits("123456789012345678901234567890", 6)).toBe(
    "123456789012345678901234.56789",
  );
  expect(formatUnits("0", 6)).toBe("0");
  expect(formatUnits("42", null)).toBe("42");
});

it("keeps enormous allowances readable without losing raw precision", () => {
  expect(formatCompactUnits(((1n << 256n) - 2n).toString(), 6)).toBe(
    "≈ 1.1579 × 10⁷¹",
  );
  expect(formatCompactUnits("1000001", 6)).toBe("1.000001");
  expect(formatCompactUnits("0", null)).toBe("0");
});
