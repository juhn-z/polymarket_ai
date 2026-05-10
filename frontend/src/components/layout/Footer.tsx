"use client";
import Link from "next/link";
import { useChainId } from "wagmi";
import { getContracts } from "@/lib/contracts";
import { shortAddress } from "@/lib/format";

export function Footer() {
  const chainId = useChainId();
  const { vault } = getContracts(chainId);
  const explorerBase =
    chainId === 137 ? "https://polygonscan.com/address/" :
    chainId === 80002 ? "https://amoy.polygonscan.com/address/" :
    "";
  return (
    <footer className="border-t border-border py-6 text-sm text-muted-foreground">
      <div className="container flex flex-col md:flex-row md:items-center justify-between gap-2">
        <div className="flex items-center gap-4">
          <Link href="https://polymarket.com" className="hover:text-foreground" target="_blank" rel="noopener">Polymarket</Link>
          <Link href="https://github.com" className="hover:text-foreground" target="_blank" rel="noopener">GitHub</Link>
        </div>
        <div className="flex items-center gap-2 font-mono text-xs">
          Vault:
          {explorerBase ? (
            <a href={`${explorerBase}${vault}`} target="_blank" rel="noopener" className="hover:text-foreground">{shortAddress(vault)}</a>
          ) : (
            <span>{shortAddress(vault)}</span>
          )}
        </div>
      </div>
    </footer>
  );
}
