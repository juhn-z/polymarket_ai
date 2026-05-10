"use client";
import * as React from "react";
import { useAccount } from "wagmi";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useUserVaultPosition, useVaultStats } from "@/hooks/useVault";
import { useRequestWithdraw } from "@/hooks/useVaultWrite";
import { formatShares, formatUsdc, formatCountdown } from "@/lib/format";

export function WithdrawForm() {
  const { address } = useAccount();
  const pos = useUserVaultPosition(address);
  const stats = useVaultStats();
  const request = useRequestWithdraw();
  const [shareStr, setShareStr] = React.useState("");

  const shares = React.useMemo(() => {
    const n = parseFloat(shareStr);
    if (isNaN(n) || n <= 0) return 0n;
    return BigInt(Math.floor(n * 1e18));
  }, [shareStr]);

  const exceedsBalance = shares > pos.shares;
  const previewAssets = stats.sharePrice > 0n ? (shares * stats.sharePrice) / 10n ** 18n : 0n;

  return (
    <Card>
      <CardHeader><CardTitle>Request withdrawal</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="wd-shares">Shares (pvUSDC)</Label>
          <Input id="wd-shares" type="number" min={0} step="0.0001" value={shareStr} onChange={(e) => setShareStr(e.target.value)} />
          <div className="text-xs text-muted-foreground">
            Balance: {formatShares(pos.shares)} pvUSDC · You will receive ~${formatUsdc(previewAssets)} after {formatCountdown(Number(stats.withdrawalDelay))}
          </div>
          {exceedsBalance && <p className="text-xs text-destructive">Insufficient share balance</p>}
        </div>
        <Button
          variant="outline"
          onClick={() => request.request(shares)}
          disabled={request.isPending || request.isConfirming || shares === 0n || exceedsBalance || (pos.pending?.pending ?? false)}
        >
          {request.isConfirming ? "Confirming…" : request.isPending ? "Waiting wallet…" : pos.pending?.pending ? "Pending request exists" : "Request withdrawal"}
        </Button>
      </CardContent>
    </Card>
  );
}
