"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { PredictionResponse, PredictionDetailResponse } from "@/types/api";
import { useAdminStore } from "@/store/admin";

export function useTodayPrediction() {
  return useQuery({
    queryKey: ["predictions", "today"],
    queryFn: () => api.get<PredictionResponse>("/predictions/today"),
    refetchInterval: 15_000,
  });
}

export function usePredictionHistory() {
  return useQuery({
    queryKey: ["predictions", "history"],
    queryFn: () => api.get<PredictionResponse[]>("/predictions/history"),
  });
}

export function usePredictionDetail(id: number | undefined) {
  return useQuery({
    queryKey: ["predictions", "detail", id],
    queryFn: () => api.get<PredictionDetailResponse>(`/predictions/${id}`),
    enabled: id !== undefined,
  });
}

export function useTriggerPrediction() {
  const qc = useQueryClient();
  const adminToken = useAdminStore((s) => s.token);
  return useMutation({
    mutationFn: () => api.post<PredictionResponse>("/predictions/trigger", undefined, { adminToken }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["predictions"] }),
  });
}
