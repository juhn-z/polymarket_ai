"use client";
import { useVaultHistory } from "@/hooks/useStats";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

export function SharePriceChart() {
  const { data, isLoading } = useVaultHistory(168);
  const series = (data ?? []).slice().reverse().map((s) => ({
    t: s.snapshot_at.slice(5, 10),
    price: Number(s.share_price),
  }));
  return (
    <Card>
      <CardHeader><CardTitle>Share price history</CardTitle></CardHeader>
      <CardContent className="h-64">
        {isLoading ? <Skeleton className="h-full w-full" /> : (
          series.length === 0 ? (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">No snapshots yet</div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={series}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="t" stroke="hsl(var(--muted-foreground))" fontSize={12} />
                <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} domain={["auto", "auto"]} />
                <Tooltip contentStyle={{ background: "hsl(var(--card))", border: "1px solid hsl(var(--border))" }} />
                <Line type="monotone" dataKey="price" stroke="hsl(var(--primary))" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          )
        )}
      </CardContent>
    </Card>
  );
}
