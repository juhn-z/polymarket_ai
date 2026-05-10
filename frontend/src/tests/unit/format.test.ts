import { describe, it, expect } from "vitest";
import { formatUsdc, formatPercent, formatShares, shortAddress, formatCountdown } from "@/lib/format";

describe("formatUsdc", () => {
  it("formats 6-decimal USDC bigint to human string", () => {
    expect(formatUsdc(1_000_000n)).toBe("1.00");
    expect(formatUsdc(1_500_000n)).toBe("1.50");
    expect(formatUsdc(0n)).toBe("0.00");
    expect(formatUsdc(1_234_567_890n, 4)).toBe("1234.5679");
  });
});

describe("formatPercent", () => {
  it("formats 0..1 to integer percent by default", () => {
    expect(formatPercent(0.62)).toBe("62%");
    expect(formatPercent(0.7811)).toBe("78%");
    expect(formatPercent(1)).toBe("100%");
    expect(formatPercent(0.625, 1)).toBe("62.5%");
  });
});

describe("formatShares", () => {
  it("formats 18-decimal share bigints", () => {
    expect(formatShares(1_000_000_000_000_000_000n)).toBe("1.0000");
    expect(formatShares(0n)).toBe("0.0000");
  });
});

describe("shortAddress", () => {
  it("abbreviates a 0x-address", () => {
    expect(shortAddress("0x1234567890abcdef1234567890abcdef12345678")).toBe("0x1234...5678");
  });
});

describe("formatCountdown", () => {
  it("formats seconds-remaining as Hh Mm", () => {
    expect(formatCountdown(0)).toBe("now");
    expect(formatCountdown(60)).toBe("1m");
    expect(formatCountdown(3600)).toBe("1h 0m");
    expect(formatCountdown(60 * 60 * 24)).toBe("24h 0m");
    expect(formatCountdown(60 * 60 * 25 + 60 * 30)).toBe("25h 30m");
  });
});
