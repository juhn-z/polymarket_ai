"use client";
import * as React from "react";
import { WagmiProvider } from "wagmi";
import { RainbowKitProvider, darkTheme, lightTheme } from "@rainbow-me/rainbowkit";
import { useTheme } from "next-themes";
import "@rainbow-me/rainbowkit/styles.css";
import { wagmiConfig } from "@/lib/wagmi";

export function Web3Provider({ children }: { children: React.ReactNode }) {
  const { resolvedTheme } = useTheme();
  return (
    <WagmiProvider config={wagmiConfig}>
      <RainbowKitProvider
        theme={resolvedTheme === "dark" ? darkTheme() : lightTheme()}
        modalSize="compact"
      >
        {children}
      </RainbowKitProvider>
    </WagmiProvider>
  );
}
