"use client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useOverview } from "@/hooks/useStats";
import { formatUsdc, formatPercent } from "@/lib/format";
import { TrendingUp, TrendingDown, Wallet, Target, DollarSign } from "lucide-react";

export function StatsCards() {
  const { data, isLoading } = useOverview();
  const tvl = data ? BigInt(data.tvl.split(".")[0] || "0") * 1_000_000n + BigInt((data.tvl.split(".")[1] || "0").padEnd(6, "0").slice(0, 6)) : 0n;
  const sharePrice = data ? Number(data.share_price) : 1;
  const pnl = data ? Number(data.total_pnl) : 0;
  const winRate = data ? Number(data.win_rate) : 0;
  const stat = (label: string, value: React.ReactNode, icon: React.ReactNode) => (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
        <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
        {icon}
      </CardHeader>
      <CardContent>
        {isLoading ? <Skeleton className="h-8 w-24" /> : <div className="text-2xl font-bold">{value}</div>}
      </CardContent>
    </Card>
  );
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {stat("TVL", `$${formatUsdc(tvl, 0)}`, <Wallet className="h-4 w-4 text-muted-foreground" />)}
      {stat("Win rate", formatPercent(winRate), <Target className="h-4 w-4 text-muted-foreground" />)}
      {stat("Total PnL",
        <span className={pnl >= 0 ? "text-success" : "text-destructive"}>
          {pnl >= 0 ? "+" : ""}{pnl.toFixed(2)} USDC
        </span>,
        pnl >= 0 ? <TrendingUp className="h-4 w-4 text-success" /> : <TrendingDown className="h-4 w-4 text-destructive" />)}
      {stat("Share price", `$${sharePrice.toFixed(4)}`, <DollarSign className="h-4 w-4 text-muted-foreground" />)}
    </div>
  );
}
