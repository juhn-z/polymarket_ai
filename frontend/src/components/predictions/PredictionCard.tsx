"use client";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import type { PredictionResponse, MarketResponse } from "@/types/api";
import { formatPercent } from "@/lib/format";

export function PredictionCard({
  prediction, market,
}: { prediction: PredictionResponse; market?: MarketResponse }) {
  const aiProb = Number(prediction.predicted_probability);
  const mktProb = Number(prediction.market_probability);
  const edge = Number(prediction.edge);
  const edgeColor = edge > 0 ? "text-success" : edge < 0 ? "text-destructive" : "text-muted-foreground";
  // NOTE: deviation from plan — shadcn Card doesn't expose `asChild`, so wrap a
  // plain Link around a Card instead of `<Card asChild><Link/></Card>`.
  return (
    <Link href={`/predictions/${prediction.id}`} className="block">
      <Card className="hover:bg-muted/30 transition-colors">
        <CardHeader className="flex flex-row items-start justify-between gap-4 space-y-0 pb-3">
          <div>
            <div className="text-xs text-muted-foreground font-mono">{prediction.created_at.slice(0, 10)}</div>
            <h3 className="font-medium mt-1">{market?.question ?? `Market #${prediction.market_id}`}</h3>
          </div>
          <Badge variant={prediction.recommended_action === "skip" ? "outline" : "default"}>
            {prediction.recommended_action.replace("_", " ").toUpperCase()}
          </Badge>
        </CardHeader>
        <CardContent className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
          <div><div className="text-xs text-muted-foreground">AI</div><div>{formatPercent(aiProb)}</div></div>
          <div><div className="text-xs text-muted-foreground">Market</div><div>{formatPercent(mktProb)}</div></div>
          <div><div className="text-xs text-muted-foreground">Edge</div><div className={edgeColor}>{(edge * 100).toFixed(1)}%</div></div>
          <div><div className="text-xs text-muted-foreground">Confidence</div><div>{formatPercent(Number(prediction.confidence))}</div></div>
        </CardContent>
      </Card>
    </Link>
  );
}
