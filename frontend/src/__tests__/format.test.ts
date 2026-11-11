import { describe, expect, it } from "vitest";
import { formatCell, formatValue } from "@/lib/format";

describe("formatValue mirrors the backend verifier formatting", () => {
  it.each([
    [1234.567, "currency", "$1,234.57"],
    [-5, "currency", "-$5.00"],
    [12.345, "percent", "12.3%"],
    [0.0004, "pvalue", "p < 0.001"],
    [0.0312, "pvalue", "p = 0.031"],
    [1234.0, "count", "1,234"],
    [0.5, "ratio", "0.500"],
    [null, "number", "n/a"],
  ] as const)("%s as %s -> %s", (v, unit, text) => {
    expect(formatValue(v, unit)).toBe(text);
  });
  it("formats table cells", () => {
    expect(formatCell(null)).toBe("—");
    expect(formatCell(true)).toBe("true");
    expect(formatCell(1500)).toBe("1,500");
  });
});
