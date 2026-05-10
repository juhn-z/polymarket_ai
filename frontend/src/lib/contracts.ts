import polyVaultArtifact from "./abi/PolyVault.json";
import mockUsdcArtifact from "./abi/MockUSDC.json";

export const polyVaultAbi = polyVaultArtifact.abi;
export const mockUsdcAbi = mockUsdcArtifact.abi;

// Address registry. Per chain. Hardhat localhost addresses come from
// .env.local (overwritten by the dev script after deploying); Polygon Amoy
// + mainnet addresses are filled in once those deployments exist.
export const addresses: Record<number, { vault: `0x${string}`; usdc: `0x${string}` }> = {
  31337: {
    vault: (process.env.NEXT_PUBLIC_VAULT_ADDRESS || "0x0000000000000000000000000000000000000000") as `0x${string}`,
    usdc: (process.env.NEXT_PUBLIC_USDC_ADDRESS || "0x0000000000000000000000000000000000000000") as `0x${string}`,
  },
  80002: {
    vault: "0x0000000000000000000000000000000000000000",
    usdc: "0x0000000000000000000000000000000000000000", // fill once deployed
  },
  137: {
    vault: "0x0000000000000000000000000000000000000000",
    usdc: "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359", // native USDC on Polygon
  },
};

export function getContracts(chainId: number | undefined) {
  const cid = chainId ?? 31337;
  return addresses[cid] ?? addresses[31337];
}
