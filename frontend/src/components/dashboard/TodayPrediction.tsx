"use client";
import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { useTodayMarket } from "@/hooks/useMarkets";
import { useTodayPrediction } from "@/hooks/usePredictions";
import { useActiveStrategies } from "@/hooks/useStrategies";
import { formatPercent } from "@/lib/format";
import { ArrowRight, Sparkles } from "lucide-react";

export function TodayPrediction() {
  const market = useTodayMarket();
  const prediction = useTodayPrediction();
  const strategies = useActiveStrategies();
  const strategy = strategies.data?.find((s) => s.market_id === market.data?.id);

  if (market.isLoading || prediction.isLoading) {
    return (
      <Card>
        <CardHeader><Skeleton className="h-6 w-48" /></CardHeader>
        <CardContent><Skeleton className="h-32 w-full" /></CardContent>
      </Card>
    );
  }
  if (!market.data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Today&apos;s prediction</CardTitle>
          <CardDescription>No market scanned yet today.</CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Run a scan from the Admin page or wait for the 00:00 UTC scheduler.
        </CardContent>
      </Card>
    );
  }
  const aiProb = prediction.data ? Number(prediction.data.predicted_probability) : null;
  const mktProb = market.data ? Number(market.data.current_yes_price) : null;
  const conf = prediction.data ? Number(prediction.data.confidence) : null;
  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="flex items-center gap-2"><Sparkles className="h-5 w-5 text-primary" /> Today&apos;s prediction</CardTitle>
            <CardDescription className="mt-1">{market.data.question}</CardDescription>
          </div>
          {strategy && (
            <Badge variant={strategy.action === "skip" ? "outline" : "default"}>
              {strategy.action.toUpperCase()}
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Stat label="Polymarket Yes" value={mktProb !== null ? formatPercent(mktProb) : "—"} />
          <Stat label="AI predicted" value={aiProb !== null ? formatPercent(aiProb) : "—"} />
          <Stat label="Confidence" value={conf !== null ? formatPercent(conf) : "—"} />
          <Stat label="Edge" value={prediction.data ? `${(Number(prediction.data.edge) * 100).toFixed(1)}%` : "—"} />
        </div>
        {prediction.data?.recommended_action && prediction.data.recommended_action !== "skip" && (
          <p className="text-sm text-muted-foreground">{prediction.data.reasoning}</p>
        )}
        <Button asChild variant="outline" size="sm">
          <Link href={prediction.data ? `/predictions/${prediction.data.id}` : "/predictions"}>
            Full analysis <ArrowRight className="ml-1 h-3 w-3" />
          </Link>
        </Button>
      </CardContent>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-lg font-semibold mt-1">{value}</div>
    </div>
  );
}
