"use client";
import { create } from "zustand";
import { persist } from "zustand/middleware";

interface AdminState {
  token: string;
  setToken: (token: string) => void;
  clear: () => void;
}

export const useAdminStore = create<AdminState>()(
  persist(
    (set) => ({
      token: process.env.NEXT_PUBLIC_ADMIN_API_KEY || "",
      setToken: (token) => set({ token }),
      clear: () => set({ token: "" }),
    }),
    { name: "polypredict-admin" }
  )
);
