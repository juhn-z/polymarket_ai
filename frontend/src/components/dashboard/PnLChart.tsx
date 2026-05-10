"use client";
import { useDailyPnL } from "@/hooks/useStats";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

export function PnLChart() {
  const { data, isLoading } = useDailyPnL(30);
  const series = (data ?? []).map((d) => ({ day: d.day.slice(5), pnl: Number(d.pnl) }));
  // running cumulative PnL
  let cum = 0;
  const cumSeries = series.map((s) => ({ day: s.day, cum: (cum += s.pnl) }));
  return (
    <Card className="col-span-2">
      <CardHeader><CardTitle>30-day PnL</CardTitle></CardHeader>
      <CardContent className="h-64">
        {isLoading ? <Skeleton className="h-full w-full" /> : (
          cumSeries.length === 0 ? (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">No trades yet</div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={cumSeries}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="day" stroke="hsl(var(--muted-foreground))" fontSize={12} />
                <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} />
                <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))" }} />
                <Line type="monotone" dataKey="cum" stroke="hsl(var(--primary))" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )
        )}
      </CardContent>
    </Card>
  );
}
