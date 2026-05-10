"use client";
import { useChainId, useReadContract } from "wagmi";
import { mockUsdcAbi, getContracts } from "@/lib/contracts";
import type { Address } from "viem";

export function useUSDC(user: Address | undefined) {
  const chainId = useChainId();
  const { vault, usdc } = getContracts(chainId);
  const enabled = !!user;
  const opts = { abi: mockUsdcAbi, address: usdc as Address };

  const balance = useReadContract({
    ...opts, functionName: "balanceOf", args: user ? [user] : undefined,
    query: { enabled, refetchInterval: 30_000 },
  });
  const allowance = useReadContract({
    ...opts, functionName: "allowance", args: user ? [user, vault as Address] : undefined,
    query: { enabled, refetchInterval: 15_000 },
  });

  return {
    balance: (balance.data as bigint | undefined) ?? 0n,
    allowance: (allowance.data as bigint | undefined) ?? 0n,
    isLoading: balance.isLoading || allowance.isLoading,
    refetch: () => { balance.refetch(); allowance.refetch(); },
  };
}
