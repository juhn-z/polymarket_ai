"use client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { usePredictionDetail } from "@/hooks/usePredictions";
import { formatPercent } from "@/lib/format";

export function PredictionDetail({ id }: { id: number }) {
  const { data, isLoading } = usePredictionDetail(id);
  if (isLoading) return <Skeleton className="h-[600px] w-full" />;
  if (!data) return <p className="text-muted-foreground">Prediction not found.</p>;

  const aiProb = Number(data.predicted_probability);
  const mktProb = Number(data.market_probability);
  const edge = Number(data.edge);
  const conf = Number(data.confidence);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Prediction #{data.id}</h1>
          <p className="text-muted-foreground font-mono text-sm">{data.created_at}</p>
        </div>
        <Badge variant={data.recommended_action === "skip" ? "outline" : "default"} className="text-base">
          {data.recommended_action.replace("_", " ").toUpperCase()}
        </Badge>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="AI predicted" value={formatPercent(aiProb)} />
        <Stat label="Polymarket" value={formatPercent(mktProb)} />
        <Stat label="Edge" value={`${(edge * 100).toFixed(1)}%`} cls={edge > 0 ? "text-success" : edge < 0 ? "text-destructive" : ""} />
        <Stat label="Confidence" value={formatPercent(conf)} />
      </div>
      <Card>
        <CardHeader><CardTitle>Reasoning</CardTitle></CardHeader>
        <CardContent className="prose prose-sm dark:prose-invert max-w-none">{data.reasoning}</CardContent>
      </Card>
      <div className="grid gap-4 md:grid-cols-2">
        <FactorList title="Key factors" items={data.key_factors} tone="success" />
        <FactorList title="Risk factors" items={data.risk_factors} tone="destructive" />
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <Section title="Technical">{data.technical_analysis}</Section>
        <Section title="Sentiment">{data.sentiment_analysis}</Section>
        <Section title="News">{data.news_impact}</Section>
        <Section title="On-chain">{data.onchain_analysis}</Section>
      </div>
      <Card>
        <CardHeader><CardTitle>Data snapshot</CardTitle></CardHeader>
        <CardContent>
          <pre className="text-xs overflow-x-auto bg-muted p-4 rounded">{JSON.stringify(data.data_snapshot, null, 2)}</pre>
        </CardContent>
      </Card>
    </div>
  );
}

function Stat({ label, value, cls }: { label: string; value: string; cls?: string }) {
  return (
    <Card>
      <CardHeader className="pb-2"><CardTitle className="text-xs text-muted-foreground">{label}</CardTitle></CardHeader>
      <CardContent><div className={`text-2xl font-bold ${cls ?? ""}`}>{value}</div></CardContent>
    </Card>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader><CardTitle className="text-sm">{title}</CardTitle></CardHeader>
      <CardContent className="text-sm text-muted-foreground">{children}</CardContent>
    </Card>
  );
}

function FactorList({ title, items, tone }: { title: string; items: string[]; tone: "success" | "destructive" }) {
  return (
    <Card>
      <CardHeader><CardTitle className="text-sm">{title}</CardTitle></CardHeader>
      <CardContent>
        <ul className="space-y-2 text-sm">
          {items.map((it, i) => (
            <li key={i} className="flex gap-2">
              <span className={tone === "success" ? "text-success" : "text-destructive"}>•</span>
              <span>{it}</span>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
