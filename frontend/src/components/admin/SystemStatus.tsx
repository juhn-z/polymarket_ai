"use client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useSystemStatus } from "@/hooks/useSystem";

export function SystemStatus() {
  const { data, isLoading } = useSystemStatus();
  return (
    <Card>
      <CardHeader><CardTitle>System status</CardTitle></CardHeader>
      <CardContent className="space-y-2 text-sm">
        <Row label="Paused" value={data?.paused} ok={!data?.paused} loading={isLoading} />
        <Row label="Scheduler" value={data?.scheduler_running} ok={!!data?.scheduler_running} loading={isLoading} />
        <Row label="Monitor" value={data?.monitor_running} ok={!!data?.monitor_running} loading={isLoading} />
      </CardContent>
    </Card>
  );
}

function Row({ label, value, ok, loading }: { label: string; value: boolean | undefined; ok: boolean; loading: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <span>{label}</span>
      {loading ? <Badge variant="outline">…</Badge> :
        <Badge variant={ok ? "default" : "destructive"}>{value ? "true" : "false"}</Badge>}
    </div>
  );
}
