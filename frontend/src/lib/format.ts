export function formatUsdc(amount: bigint, decimals: number = 2): string {
  // USDC has 6 raw decimals. For `decimals >= 6` we just pad; for fewer
  // decimals we round half-up so `formatUsdc(1_234_567_890n, 4)` → "1234.5679"
  // rather than truncating to "1234.5678".
  if (decimals >= 6) {
    const whole = amount / 1_000_000n;
    const frac = amount % 1_000_000n;
    return `${whole.toString()}.${frac.toString().padStart(6, "0").slice(0, decimals)}`;
  }
  const scale = 10n ** BigInt(6 - decimals);
  const rounded = (amount + scale / 2n) / scale;
  const divisor = 10n ** BigInt(decimals);
  const whole = rounded / divisor;
  const frac = rounded % divisor;
  return `${whole.toString()}.${frac.toString().padStart(decimals, "0")}`;
}

export function formatShares(shares: bigint, decimals: number = 4): string {
  const divisor = 10n ** 18n;
  const whole = shares / divisor;
  const frac = shares % divisor;
  const fracStr = frac.toString().padStart(18, "0").slice(0, decimals);
  return `${whole.toString()}.${fracStr}`;
}

export function formatPercent(ratio: number, decimals: number = 0): string {
  return `${(ratio * 100).toFixed(decimals)}%`;
}

export function shortAddress(addr: string): string {
  if (!addr || addr.length < 10) return addr;
  return `${addr.slice(0, 6)}...${addr.slice(-4)}`;
}

export function formatCountdown(seconds: number): string {
  if (seconds <= 0) return "now";
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  const remM = m % 60;
  return `${h}h ${remM}m`;
}
