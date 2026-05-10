import { defineChain } from "viem";
import { polygon, polygonAmoy } from "viem/chains";

// Hardhat default localhost — Anvil/Foundry use the same.
export const hardhatLocal = defineChain({
  id: 31337,
  name: "Hardhat Localhost",
  nativeCurrency: { name: "Ether", symbol: "ETH", decimals: 18 },
  rpcUrls: {
    default: { http: ["http://127.0.0.1:8545"] },
    public: { http: ["http://127.0.0.1:8545"] },
  },
  testnet: true,
});

export const supportedChains = [hardhatLocal, polygonAmoy, polygon] as const;
