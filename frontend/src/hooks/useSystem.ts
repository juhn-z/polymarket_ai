"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { SystemStatusResponse } from "@/types/api";
import { useAdminStore } from "@/store/admin";

export function useSystemStatus() {
  return useQuery({
    queryKey: ["system", "status"],
    queryFn: () => api.get<SystemStatusResponse>("/system/status"),
    refetchInterval: 15_000,
  });
}

export function usePauseSystem() {
  const qc = useQueryClient();
  const adminToken = useAdminStore((s) => s.token);
  return useMutation({
    mutationFn: () => api.post<void>("/system/pause", undefined, { adminToken }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["system"] }),
  });
}

export function useResumeSystem() {
  const qc = useQueryClient();
  const adminToken = useAdminStore((s) => s.token);
  return useMutation({
    mutationFn: () => api.post<void>("/system/resume", undefined, { adminToken }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["system"] }),
  });
}
