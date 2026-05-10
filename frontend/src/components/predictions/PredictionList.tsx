"use client";
import * as React from "react";
import { usePredictionHistory } from "@/hooks/usePredictions";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PredictionCard } from "./PredictionCard";

type Filter = "all" | "trade" | "skip";

export function PredictionList() {
  const { data, isLoading } = usePredictionHistory();
  const [filter, setFilter] = React.useState<Filter>("all");

  if (isLoading) return <Skeleton className="h-96 w-full" />;
  const items = (data ?? []).filter((p) => {
    if (filter === "trade") return p.recommended_action !== "skip";
    if (filter === "skip") return p.recommended_action === "skip";
    return true;
  });
  return (
    <div className="space-y-4">
      <Tabs value={filter} onValueChange={(v) => setFilter(v as Filter)}>
        <TabsList>
          <TabsTrigger value="all">All</TabsTrigger>
          <TabsTrigger value="trade">Trades</TabsTrigger>
          <TabsTrigger value="skip">Skipped</TabsTrigger>
        </TabsList>
      </Tabs>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">No predictions yet.</p>
      ) : (
        <div className="space-y-3">{items.map((p) => <PredictionCard key={p.id} prediction={p} />)}</div>
      )}
    </div>
  );
}
