import { describe, it, expect } from "vitest";
import { formatTokens } from "@/lib/formatTokens";

describe("formatTokens", () => {
  it("returns raw number for values under 1000", () => {
    expect(formatTokens(0)).toBe("0");
    expect(formatTokens(42)).toBe("42");
    expect(formatTokens(999)).toBe("999");
  });

  it("formats thousands as K", () => {
    expect(formatTokens(1000)).toBe("1.0K");
    expect(formatTokens(1500)).toBe("1.5K");
    expect(formatTokens(42300)).toBe("42.3K");
    expect(formatTokens(999999)).toBe("1000.0K");
  });

  it("formats millions as M", () => {
    expect(formatTokens(1000000)).toBe("1.0M");
    expect(formatTokens(1500000)).toBe("1.5M");
    expect(formatTokens(10750000)).toBe("10.8M");
  });
});
