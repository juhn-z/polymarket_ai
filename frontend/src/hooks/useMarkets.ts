"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { MarketResponse } from "@/types/api";
import { useAdminStore } from "@/store/admin";

export function useTodayMarket() {
  return useQuery({
    queryKey: ["markets", "today"],
    queryFn: () => api.get<MarketResponse>("/markets/today"),
  });
}

export function useScanMarket() {
  const qc = useQueryClient();
  const adminToken = useAdminStore((s) => s.token);
  return useMutation({
    mutationFn: () => api.post<MarketResponse>("/markets/scan", undefined, { adminToken }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["markets"] }),
  });
}
