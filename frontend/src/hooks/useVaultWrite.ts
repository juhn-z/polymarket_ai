"use client";
import * as React from "react";
import { useAccount, useChainId, useWaitForTransactionReceipt, useWriteContract } from "wagmi";
import { toast } from "sonner";
import { polyVaultAbi, mockUsdcAbi, getContracts } from "@/lib/contracts";
import type { Address } from "viem";

type WriteHelpers = ReturnType<typeof useWriteContract>;

function useTracked(action: string, helpers: WriteHelpers) {
  const wait = useWaitForTransactionReceipt({ hash: helpers.data });
  React.useEffect(() => {
    if (wait.isSuccess && helpers.data) toast.success(`${action} confirmed`, { description: helpers.data });
    if (helpers.isError) toast.error(`${action} failed`, { description: (helpers.error as Error)?.message });
  }, [wait.isSuccess, helpers.isError, helpers.data, action, helpers.error]);
  return {
    write: helpers.writeContract,
    hash: helpers.data,
    isPending: helpers.isPending,
    isConfirming: wait.isLoading,
    isSuccess: wait.isSuccess,
  };
}

export function useApproveUsdc() {
  const chainId = useChainId();
  const { vault, usdc } = getContracts(chainId);
  const w = useWriteContract();
  const tracked = useTracked("Approve", w);
  return {
    ...tracked,
    approve: (amount: bigint) =>
      w.writeContract({ abi: mockUsdcAbi, address: usdc as Address, functionName: "approve", args: [vault as Address, amount] }),
  };
}

export function useDepositUsdc() {
  const { address } = useAccount();
  const chainId = useChainId();
  const { vault } = getContracts(chainId);
  const w = useWriteContract();
  const tracked = useTracked("Deposit", w);
  return {
    ...tracked,
    deposit: (amount: bigint) => {
      if (!address) return;
      w.writeContract({ abi: polyVaultAbi, address: vault as Address, functionName: "deposit", args: [amount, address] });
    },
  };
}

export function useRequestWithdraw() {
  const chainId = useChainId();
  const { vault } = getContracts(chainId);
  const w = useWriteContract();
  const tracked = useTracked("Request withdraw", w);
  return {
    ...tracked,
    request: (shares: bigint) =>
      w.writeContract({ abi: polyVaultAbi, address: vault as Address, functionName: "requestWithdraw", args: [shares] }),
  };
}

export function useCancelWithdraw() {
  const chainId = useChainId();
  const { vault } = getContracts(chainId);
  const w = useWriteContract();
  const tracked = useTracked("Cancel withdraw", w);
  return {
    ...tracked,
    cancel: () => w.writeContract({ abi: polyVaultAbi, address: vault as Address, functionName: "cancelWithdraw", args: [] }),
  };
}

export function useExecuteWithdraw() {
  const chainId = useChainId();
  const { vault } = getContracts(chainId);
  const w = useWriteContract();
  const tracked = useTracked("Execute withdraw", w);
  return {
    ...tracked,
    execute: () => w.writeContract({ abi: polyVaultAbi, address: vault as Address, functionName: "executeWithdraw", args: [] }),
  };
}
