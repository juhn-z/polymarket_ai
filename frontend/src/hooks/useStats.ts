"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { OverviewResponse, DailyPnLResponse, VaultSnapshotResponse, LeaderboardEntryResponse } from "@/types/api";

export function useOverview() {
  return useQuery({
    queryKey: ["stats", "overview"],
    queryFn: () => api.get<OverviewResponse>("/stats/overview"),
    refetchInterval: 30_000,
  });
}

export function useDailyPnL(days: number = 30) {
  return useQuery({
    queryKey: ["stats", "daily", days],
    queryFn: () => api.get<DailyPnLResponse[]>(`/stats/daily?days=${days}`),
  });
}

export function useVaultHistory(limit: number = 168) {
  return useQuery({
    queryKey: ["stats", "vault", limit],
    queryFn: () => api.get<VaultSnapshotResponse[]>(`/stats/vault?limit=${limit}`),
  });
}

export function useLeaderboard() {
  return useQuery({
    queryKey: ["stats", "leaderboard"],
    queryFn: () => api.get<LeaderboardEntryResponse[]>("/stats/leaderboard"),
  });
}
