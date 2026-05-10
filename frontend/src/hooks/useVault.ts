"use client";
import { useReadContract, useChainId } from "wagmi";
import { polyVaultAbi, getContracts } from "@/lib/contracts";
import type { Address } from "viem";

const REFETCH_INTERVAL = 30_000; // 30s per PRD §4.4

export function useVaultStats() {
  const chainId = useChainId();
  const { vault } = getContracts(chainId);
  const opts = { abi: polyVaultAbi, address: vault as Address, query: { refetchInterval: REFETCH_INTERVAL } };

  const totalAssets = useReadContract({ ...opts, functionName: "totalAssets" });
  const withdrawalDelay = useReadContract({ ...opts, functionName: "withdrawalDelay" });
  const minDeposit = useReadContract({ ...opts, functionName: "minDeposit" });
  const maxDeposit = useReadContract({ ...opts, functionName: "maxDeposit" });
  const sharePrice = useReadContract({
    ...opts,
    functionName: "convertToAssets",
    args: [10n ** 18n], // value of 1 share
  });
  const strategyDebt = useReadContract({ ...opts, functionName: "strategyDebt" });
  const totalSupply = useReadContract({ ...opts, functionName: "totalSupply" });

  return {
    totalAssets: (totalAssets.data as bigint | undefined) ?? 0n,
    sharePrice: (sharePrice.data as bigint | undefined) ?? 10n ** 18n, // 1.0 default
    withdrawalDelay: (withdrawalDelay.data as bigint | undefined) ?? 0n,
    minDeposit: (minDeposit.data as bigint | undefined) ?? 0n,
    maxDeposit: (maxDeposit.data as bigint | undefined) ?? 0n,
    strategyDebt: (strategyDebt.data as bigint | undefined) ?? 0n,
    totalSupply: (totalSupply.data as bigint | undefined) ?? 0n,
    isLoading: totalAssets.isLoading || sharePrice.isLoading,
    refetchAll: () => {
      totalAssets.refetch();
      sharePrice.refetch();
      strategyDebt.refetch();
      totalSupply.refetch();
    },
  };
}

export function useUserVaultPosition(user: Address | undefined) {
  const chainId = useChainId();
  const { vault } = getContracts(chainId);
  const enabled = !!user;
  const opts = { abi: polyVaultAbi, address: vault as Address };

  const shares = useReadContract({
    ...opts, functionName: "balanceOf", args: user ? [user] : undefined,
    query: { enabled, refetchInterval: REFETCH_INTERVAL },
  });
  const sharesValue = useReadContract({
    ...opts, functionName: "convertToAssets",
    args: shares.data !== undefined ? [shares.data as bigint] : undefined,
    query: { enabled: enabled && shares.data !== undefined },
  });
  const pending = useReadContract({
    ...opts, functionName: "getWithdrawalRequest", args: user ? [user] : undefined,
    query: { enabled, refetchInterval: REFETCH_INTERVAL },
  });

  return {
    shares: (shares.data as bigint | undefined) ?? 0n,
    assets: (sharesValue.data as bigint | undefined) ?? 0n,
    pending: pending.data as { shares: bigint; requestTimestamp: bigint; pending: boolean } | undefined,
    isLoading: shares.isLoading || pending.isLoading,
    refetch: () => { shares.refetch(); sharesValue.refetch(); pending.refetch(); },
  };
}
