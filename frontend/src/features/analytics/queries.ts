"use client";

import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";

import { apiFetch, type QueryValue } from "@/lib/api/client";
import type {
  AnalyticsMetadata,
  AnalyticsResultsResponse,
  DelaysResponse,
  OverviewResponse,
} from "@/lib/api/contracts";
import { apiPaths, type DashboardResultsEndpoint } from "@/lib/api/paths";

export function useDashboardQuery() {
  const searchParams = useSearchParams();
  return {
    date_from: searchParams.get("date_from") ?? undefined,
    date_to: searchParams.get("date_to") ?? undefined,
    agency: searchParams.get("agency") ?? undefined,
    ca: searchParams.get("ca") ?? undefined,
    gp: searchParams.get("gp") ?? undefined,
  } satisfies Record<string, QueryValue>;
}

export function useMetadata() {
  const searchParams = useSearchParams();
  const agency = searchParams.get("agency") ?? undefined;
  return useQuery({
    queryKey: ["analytics", "metadata", agency],
    queryFn: ({ signal }) =>
      apiFetch<AnalyticsMetadata>(apiPaths.dashboard("metadata"), {
        query: { agency },
        signal,
      }),
    placeholderData: (previous) => previous,
    staleTime: 5 * 60_000,
  });
}

export function useAnalyticsResults(
  endpoint: DashboardResultsEndpoint,
  extraQuery: Record<string, QueryValue> = {},
) {
  const dashboardQuery = useDashboardQuery();
  const query = { ...dashboardQuery, ...extraQuery };
  return useQuery({
    queryKey: ["analytics", endpoint, query],
    queryFn: ({ signal }) =>
      apiFetch<AnalyticsResultsResponse>(apiPaths.dashboard(endpoint), { query, signal }),
    placeholderData: (previous) => previous,
  });
}

export function useOverview() {
  const query = useDashboardQuery();
  return useQuery({
    queryKey: ["analytics", "overview", query],
    queryFn: ({ signal }) =>
      apiFetch<OverviewResponse>(apiPaths.dashboard("overview"), { query, signal }),
    placeholderData: (previous) => previous,
  });
}

export function useDelays(interval?: string) {
  const dashboardQuery = useDashboardQuery();
  const query = { ...dashboardQuery, interval };
  return useQuery({
    queryKey: ["analytics", "delays", query],
    queryFn: ({ signal }) =>
      apiFetch<DelaysResponse>(apiPaths.dashboard("delays"), { query, signal }),
    placeholderData: (previous) => previous,
  });
}
