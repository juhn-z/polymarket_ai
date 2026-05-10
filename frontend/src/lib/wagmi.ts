"use client";
import { getDefaultConfig } from "@rainbow-me/rainbowkit";
import { http } from "wagmi";
import { hardhatLocal, supportedChains } from "./chains";
import { polygon, polygonAmoy } from "viem/chains";

const projectId = process.env.NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID || "polypredict-dev";

export const wagmiConfig = getDefaultConfig({
  appName: "PolyPredict AI",
  projectId,
  chains: supportedChains,
  transports: {
    [hardhatLocal.id]: http(process.env.NEXT_PUBLIC_HARDHAT_RPC || "http://127.0.0.1:8545"),
    [polygonAmoy.id]: http(),
    [polygon.id]: http(),
  },
  ssr: true,
});
