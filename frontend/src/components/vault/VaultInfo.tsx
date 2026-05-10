"use client";
import { useAccount } from "wagmi";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useVaultStats, useUserVaultPosition } from "@/hooks/useVault";
import { formatUsdc, formatShares } from "@/lib/format";

export function VaultInfo() {
  const { address } = useAccount();
  const stats = useVaultStats();
  const pos = useUserVaultPosition(address);
  const profit = pos.assets - pos.shares; // a rough proxy when share price > 1
  return (
    <Card>
      <CardHeader><CardTitle>Vault</CardTitle></CardHeader>
      <CardContent className="grid gap-4 md:grid-cols-3">
        <Stat label="TVL" value={`$${formatUsdc(stats.totalAssets)}`} />
        <Stat label="Share price" value={`$${formatUsdc(stats.sharePrice / 10n ** 12n, 6)}`} />
        <Stat label="Total supply" value={formatShares(stats.totalSupply)} />
        <Stat label="Your shares" value={formatShares(pos.shares)} />
        <Stat label="Your value" value={`$${formatUsdc(pos.assets)}`} />
        <Stat label="Approx PnL" value={`${profit >= 0n ? "+" : ""}$${formatUsdc(profit)}`} />
      </CardContent>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-xl font-semibold mt-1 font-mono">{value}</div>
    </div>
  );
}
