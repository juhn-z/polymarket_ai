"use client";
import Link from "next/link";
import { useTradeHistory } from "@/hooks/useTrades";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { CheckCircle2, XCircle, Clock } from "lucide-react";

export function RecentTrades() {
  const { data, isLoading } = useTradeHistory(10);
  return (
    <Card>
      <CardHeader><CardTitle>Recent trades</CardTitle></CardHeader>
      <CardContent>
        {isLoading ? <Skeleton className="h-48 w-full" /> : (
          (!data || data.length === 0) ? (
            <p className="text-sm text-muted-foreground">No trades yet.</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {data.map((t) => {
                const pnl = t.pnl !== null ? Number(t.pnl) : null;
                const icon = pnl === null ? <Clock className="h-4 w-4 text-muted-foreground" /> :
                             pnl > 0 ? <CheckCircle2 className="h-4 w-4 text-success" /> :
                             <XCircle className="h-4 w-4 text-destructive" />;
                return (
                  <li key={t.id} className="flex items-center justify-between border-b border-border/50 pb-2">
                    <Link href={`/predictions`} className="flex items-center gap-2 hover:text-primary">
                      {icon}
                      <span className="font-mono text-xs">{t.created_at.slice(0, 10)}</span>
                      <span className="uppercase">{t.side}</span>
                    </Link>
                    <span className={pnl === null ? "" : pnl >= 0 ? "text-success" : "text-destructive"}>
                      {pnl === null ? "open" : `${pnl >= 0 ? "+" : ""}${pnl.toFixed(2)}`}
                    </span>
                  </li>
                );
              })}
            </ul>
          )
        )}
      </CardContent>
    </Card>
  );
}
