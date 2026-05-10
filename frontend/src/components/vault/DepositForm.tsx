"use client";
import * as React from "react";
import { useAccount } from "wagmi";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useApproveUsdc, useDepositUsdc } from "@/hooks/useVaultWrite";
import { useUSDC } from "@/hooks/useUSDC";
import { useVaultStats } from "@/hooks/useVault";
import { formatUsdc } from "@/lib/format";

export function DepositForm() {
  const { address } = useAccount();
  const usdc = useUSDC(address);
  const stats = useVaultStats();
  const approve = useApproveUsdc();
  const deposit = useDepositUsdc();
  const [amountStr, setAmountStr] = React.useState("100");

  const amount = React.useMemo(() => {
    const n = parseFloat(amountStr);
    if (isNaN(n) || n <= 0) return 0n;
    return BigInt(Math.floor(n * 1_000_000));
  }, [amountStr]);

  const previewShares = stats.sharePrice > 0n ? (amount * 10n ** 18n) / stats.sharePrice : 0n;
  const needsApproval = amount > 0n && usdc.allowance < amount;
  const exceedsBalance = amount > usdc.balance;

  return (
    <Card>
      <CardHeader><CardTitle>Deposit</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="dep-amt">Amount (USDC)</Label>
          <Input id="dep-amt" type="number" min={1} value={amountStr} onChange={(e) => setAmountStr(e.target.value)} />
          <div className="text-xs text-muted-foreground">
            Wallet: {formatUsdc(usdc.balance)} USDC · You will receive ~{formatUsdc(previewShares / 10n ** 12n, 6)} pvUSDC
          </div>
          {exceedsBalance && <p className="text-xs text-destructive">Insufficient USDC balance</p>}
        </div>
        <div className="flex flex-col gap-2">
          {needsApproval ? (
            <Button onClick={() => approve.approve(amount)} disabled={approve.isPending || approve.isConfirming || amount === 0n}>
              {approve.isConfirming ? "Confirming…" : approve.isPending ? "Waiting wallet…" : "Approve USDC"}
            </Button>
          ) : (
            <Button onClick={() => deposit.deposit(amount)} disabled={deposit.isPending || deposit.isConfirming || amount === 0n || exceedsBalance}>
              {deposit.isConfirming ? "Confirming…" : deposit.isPending ? "Waiting wallet…" : "Deposit"}
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
