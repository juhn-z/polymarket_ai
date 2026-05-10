"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { TradeResponse } from "@/types/api";
import { useAdminStore } from "@/store/admin";

export function useActiveTrades() {
  return useQuery({
    queryKey: ["trades", "active"],
    queryFn: () => api.get<TradeResponse[]>("/trades/active"),
    refetchInterval: 15_000,
  });
}

export function useTradeHistory(limit?: number) {
  return useQuery({
    queryKey: ["trades", "history", limit],
    queryFn: async () => {
      const all = await api.get<TradeResponse[]>("/trades/history");
      if (!all) return [];
      return limit ? all.slice(0, limit) : all;
    },
  });
}

export function useExecuteTrade() {
  const qc = useQueryClient();
  const adminToken = useAdminStore((s) => s.token);
  return useMutation({
    mutationFn: () => api.post<TradeResponse>("/trades/execute", undefined, { adminToken }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["trades"] }),
  });
}
