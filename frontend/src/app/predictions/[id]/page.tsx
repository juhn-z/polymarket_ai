import { PredictionDetail } from "@/components/predictions/PredictionDetail";

export default function PredictionDetailPage({ params }: { params: { id: string } }) {
  const id = parseInt(params.id, 10);
  return (
    <div className="container py-8">
      {Number.isNaN(id) ? <p className="text-destructive">Invalid prediction id.</p> : <PredictionDetail id={id} />}
    </div>
  );
}
