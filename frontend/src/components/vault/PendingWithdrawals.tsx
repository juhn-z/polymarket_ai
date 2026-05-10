"use client";
import * as React from "react";
import { useAccount } from "wagmi";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useUserVaultPosition, useVaultStats } from "@/hooks/useVault";
import { useCancelWithdraw, useExecuteWithdraw } from "@/hooks/useVaultWrite";
import { formatShares, formatUsdc, formatCountdown } from "@/lib/format";

export function PendingWithdrawals() {
  const { address } = useAccount();
  const pos = useUserVaultPosition(address);
  const stats = useVaultStats();
  const cancel = useCancelWithdraw();
  const exec = useExecuteWithdraw();

  // Re-render once a second to update countdown
  const [, setTick] = React.useState(0);
  React.useEffect(() => {
    const id = setInterval(() => setTick((x) => x + 1), 1_000);
    return () => clearInterval(id);
  }, []);

  if (!pos.pending?.pending) {
    return (
      <Card>
        <CardHeader><CardTitle>Pending withdrawals</CardTitle></CardHeader>
        <CardContent className="text-sm text-muted-foreground">No pending withdrawals.</CardContent>
      </Card>
    );
  }
  const ready = Number(pos.pending.requestTimestamp) + Number(stats.withdrawalDelay);
  const now = Math.floor(Date.now() / 1000);
  const remaining = Math.max(0, ready - now);
  const previewAssets = stats.sharePrice > 0n ? (pos.pending.shares * stats.sharePrice) / 10n ** 18n : 0n;

  return (
    <Card>
      <CardHeader><CardTitle>Pending withdrawals</CardTitle></CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div>
          <strong>{formatShares(pos.pending.shares)} pvUSDC</strong> → ~${formatUsdc(previewAssets)}
        </div>
        <div>
          Requested at <span className="font-mono">{new Date(Number(pos.pending.requestTimestamp) * 1000).toLocaleString()}</span>
        </div>
        <div>
          {remaining > 0 ? `Available in ${formatCountdown(remaining)}` : "Available now"}
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => cancel.cancel()} disabled={cancel.isPending || cancel.isConfirming}>
            {cancel.isConfirming ? "Cancelling…" : "Cancel"}
          </Button>
          <Button size="sm" onClick={() => exec.execute()} disabled={remaining > 0 || exec.isPending || exec.isConfirming}>
            {exec.isConfirming ? "Confirming…" : "Execute"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
