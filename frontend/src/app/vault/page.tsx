"use client";
import { useAccount } from "wagmi";
import { ConnectButton } from "@rainbow-me/rainbowkit";
import { VaultInfo } from "@/components/vault/VaultInfo";
import { DepositForm } from "@/components/vault/DepositForm";
import { WithdrawForm } from "@/components/vault/WithdrawForm";
import { PendingWithdrawals } from "@/components/vault/PendingWithdrawals";
import { SharePriceChart } from "@/components/vault/SharePriceChart";

export default function VaultPage() {
  const { isConnected } = useAccount();
  return (
    <div className="container py-8 space-y-6">
      <header>
        <h1 className="text-3xl font-bold">Vault</h1>
        <p className="text-muted-foreground">Deposit USDC to mint pvUSDC; withdrawals require a 24h delay.</p>
      </header>
      {!isConnected ? (
        <div className="rounded-lg border border-dashed p-8 text-center space-y-3">
          <p className="text-muted-foreground">Connect a wallet to deposit or withdraw.</p>
          <div className="flex justify-center"><ConnectButton /></div>
        </div>
      ) : (
        <>
          <VaultInfo />
          <div className="grid gap-4 md:grid-cols-2">
            <DepositForm />
            <WithdrawForm />
          </div>
          <PendingWithdrawals />
          <SharePriceChart />
        </>
      )}
    </div>
  );
}
