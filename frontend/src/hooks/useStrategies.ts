"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { StrategyResponse } from "@/types/api";
import { useAdminStore } from "@/store/admin";

export function useActiveStrategies() {
  return useQuery({
    queryKey: ["strategies", "active"],
    queryFn: () => api.get<StrategyResponse[]>("/strategies/active"),
    refetchInterval: 15_000,
  });
}

export function useStrategyHistory() {
  return useQuery({
    queryKey: ["strategies", "history"],
    queryFn: () => api.get<StrategyResponse[]>("/strategies/history"),
  });
}

export function useGenerateStrategy() {
  const qc = useQueryClient();
  const adminToken = useAdminStore((s) => s.token);
  return useMutation({
    mutationFn: () => api.post<StrategyResponse>("/strategies/generate", undefined, { adminToken }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["strategies"] }),
  });
}
