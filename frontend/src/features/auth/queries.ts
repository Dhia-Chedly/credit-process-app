"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch, setAccessToken } from "@/lib/api/client";
import type { AuthTokenResponse, CurrentUser } from "@/lib/api/contracts";
import { apiPaths } from "@/lib/api/paths";

export const currentUserKey = ["auth", "me"] as const;

export function useCurrentUser() {
  return useQuery({
    queryKey: currentUserKey,
    queryFn: ({ signal }) => apiFetch<CurrentUser>(apiPaths.me, { signal }),
    retry: false,
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (credentials: { username: string; password: string }) =>
      apiFetch<AuthTokenResponse>(apiPaths.login, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(credentials),
        skipAuthRefresh: true,
      }),
    onSuccess: async (response) => {
      setAccessToken(response.access);
      await queryClient.invalidateQueries({ queryKey: currentUserKey });
    },
  });
}

export function useRegister() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (credentials: {
      username: string;
      password: string;
      password_confirmation: string;
    }) =>
      apiFetch<AuthTokenResponse>(apiPaths.register, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(credentials),
        skipAuthRefresh: true,
      }),
    onSuccess: async (response) => {
      setAccessToken(response.access);
      await queryClient.invalidateQueries({ queryKey: currentUserKey });
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch<void>(apiPaths.logout, { method: "POST", skipAuthRefresh: true }),
    onSettled: () => {
      setAccessToken(null);
      queryClient.clear();
    },
  });
}
