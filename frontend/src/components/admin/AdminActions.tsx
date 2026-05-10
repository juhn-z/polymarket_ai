"use client";
import * as React from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAdminStore } from "@/store/admin";
import { useScanMarket } from "@/hooks/useMarkets";
import { useTriggerPrediction } from "@/hooks/usePredictions";
import { useGenerateStrategy } from "@/hooks/useStrategies";
import { useExecuteTrade } from "@/hooks/useTrades";
import { usePauseSystem, useResumeSystem } from "@/hooks/useSystem";

export function AdminActions() {
  const token = useAdminStore((s) => s.token);
  const setToken = useAdminStore((s) => s.setToken);
  const scan = useScanMarket();
  const predict = useTriggerPrediction();
  const generate = useGenerateStrategy();
  const execute = useExecuteTrade();
  const pause = usePauseSystem();
  const resume = useResumeSystem();

  const wrap = (label: string, m: { mutateAsync: () => Promise<unknown> }) => async () => {
    try { await m.mutateAsync(); toast.success(`${label} OK`); }
    catch (e) { toast.error(`${label} failed`, { description: (e as Error).message }); }
  };

  return (
    <Card>
      <CardHeader><CardTitle>Admin actions</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="admin-token">Admin API key</Label>
          <Input id="admin-token" type="password" value={token} onChange={(e) => setToken(e.target.value)} />
          <p className="text-xs text-muted-foreground">Stored in localStorage; matches backend ADMIN_API_KEY.</p>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <Button variant="outline" onClick={wrap("Market scan", scan)} disabled={scan.isPending}>1. Scan market</Button>
          <Button variant="outline" onClick={wrap("Prediction", predict)} disabled={predict.isPending}>2. Predict</Button>
          <Button variant="outline" onClick={wrap("Generate", generate)} disabled={generate.isPending}>3. Generate strategy</Button>
          <Button variant="outline" onClick={wrap("Execute", execute)} disabled={execute.isPending}>4. Execute trade</Button>
          <Button variant="destructive" onClick={wrap("Pause", pause)} disabled={pause.isPending}>Pause</Button>
          <Button variant="default" onClick={wrap("Resume", resume)} disabled={resume.isPending}>Resume</Button>
        </div>
      </CardContent>
    </Card>
  );
}
