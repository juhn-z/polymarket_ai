"use client";
import { useLeaderboard } from "@/hooks/useStats";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Trophy, Medal } from "lucide-react";
import { shortAddress } from "@/lib/format";

const RANK_ICON = (rank: number) =>
  rank === 1 ? <Trophy className="h-4 w-4 text-yellow-500" /> :
  rank === 2 ? <Medal className="h-4 w-4 text-zinc-400" /> :
  rank === 3 ? <Medal className="h-4 w-4 text-amber-700" /> :
  <span className="text-muted-foreground">#{rank}</span>;

export function LeaderboardTable() {
  const { data, isLoading } = useLeaderboard();
  if (isLoading) return <Skeleton className="h-96 w-full" />;
  if (!data || data.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No depositors indexed yet. The leaderboard requires on-chain deposit-event indexing —
        run the backend seed script after some deposits are made on-chain.
      </p>
    );
  }
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-16">Rank</TableHead>
          <TableHead>Wallet</TableHead>
          <TableHead className="text-right">Deposited</TableHead>
          <TableHead className="text-right">Current value</TableHead>
          <TableHead className="text-right">Profit</TableHead>
          <TableHead className="text-right">Profit %</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {data.map((row) => {
          const profit = Number(row.profit);
          return (
            <TableRow key={row.wallet}>
              <TableCell>{RANK_ICON(row.rank)}</TableCell>
              <TableCell className="font-mono">{shortAddress(row.wallet)}</TableCell>
              <TableCell className="text-right font-mono">${row.deposited}</TableCell>
              <TableCell className="text-right font-mono">${row.current_value}</TableCell>
              <TableCell className={`text-right font-mono ${profit > 0 ? "text-success" : profit < 0 ? "text-destructive" : ""}`}>
                {profit >= 0 ? "+" : ""}${row.profit}
              </TableCell>
              <TableCell className="text-right font-mono">{row.profit_pct}%</TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
