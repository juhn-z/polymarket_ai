// Strongly-typed shapes for vault read/write helpers.
import type { Address } from "viem";

export interface WithdrawalRequest {
  shares: bigint;
  requestTimestamp: bigint;
  pending: boolean;
}

export interface VaultStats {
  totalAssets: bigint;
  sharePrice: bigint;            // 1e18-scaled (one full share)
  withdrawalDelay: bigint;       // seconds
  minDeposit: bigint;            // 6-decimal USDC
  maxDeposit: bigint;            // 6-decimal USDC
}

export interface UserVaultPosition {
  shares: bigint;
  assets: bigint;                // shares-converted USDC value
  pendingWithdrawal: WithdrawalRequest | null;
  usdcBalance: bigint;
  usdcAllowance: bigint;
}

export type WriteState =
  | { status: "idle" }
  | { status: "pending" }
  | { status: "confirming"; hash: Address }
  | { status: "success"; hash: Address }
  | { status: "error"; message: string };
