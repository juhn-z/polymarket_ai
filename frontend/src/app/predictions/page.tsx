import { PredictionList } from "@/components/predictions/PredictionList";

export default function PredictionsPage() {
  return (
    <div className="container py-8 space-y-6">
      <header>
        <h1 className="text-3xl font-bold">Predictions</h1>
        <p className="text-muted-foreground">Every AI prediction the system has made — including skipped ones (audit trail).</p>
      </header>
      <PredictionList />
    </div>
  );
}
