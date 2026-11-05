"use client";

import type { EChartsOption } from "echarts";

import { AnalyticsChart } from "@/components/data/analytics-chart";
import { DataState, LoadingState } from "@/components/ui/data-state";
import { DashboardFilters } from "@/features/analytics/dashboard-filters";
import { QueryErrorState } from "@/features/analytics/query-state";
import { useAnalyticsResults } from "@/features/analytics/queries";
import { numberValue, stringValue } from "@/features/analytics/value";

export function AgencyDashboard() {
  const agencies = useAnalyticsResults("agencies");
  const observedAgencies = (agencies.data?.results ?? []).filter(
    (row) => numberValue(row, ["total_requests"]) !== undefined,
  );
  const outcomeRows = observedAgencies
    .map((row) => ({
      agency: stringValue(row, ["agency_name"]) ?? "Agence",
      total: numberValue(row, ["total_requests"]) ?? 0,
      funded: numberValue(row, ["funded_requests"]) ?? 0,
      rejected: numberValue(row, ["rejected_requests"]) ?? 0,
      open: numberValue(row, ["open_or_unknown_requests", "active_requests"]) ?? 0,
    }))
    .sort(
      (first, second) => second.total - first.total || first.agency.localeCompare(second.agency),
    );
  const positioningRows = observedAgencies.map((row) => ({
    agency: stringValue(row, ["agency_name"]) ?? "Agence",
    volume: numberValue(row, ["total_requests"]) ?? null,
    rate: numberValue(row, ["financing_rate"]) ?? null,
    delay: numberValue(row, ["average_processing_days"]) ?? null,
  }));
  const agencyVolumeAverage =
    positioningRows.reduce((sum, row) => sum + (row.volume ?? 0), 0) /
    Math.max(positioningRows.length, 1);
  const agencyRateAverage =
    positioningRows.reduce((sum, row) => sum + (row.rate ?? 0), 0) /
    Math.max(positioningRows.length, 1);

  return (
    <div>
      <DashboardFilters showAgencyFilter={false} showEmployeeFilters={false} />
      <div className="mt-6 space-y-6">
        {agencies.isLoading ? (
          <LoadingState label="Chargement du réseau…" />
        ) : agencies.isError ? (
          <QueryErrorState error={agencies.error} label="Indicateurs réseau" />
        ) : outcomeRows.length === 0 ? (
          <DataState title="Analyse du réseau indisponible" tone="empty">
            Aucune demande observée n’est disponible pour les filtres sélectionnés.
          </DataState>
        ) : (
          <>
            <AnalyticsChart
              columns={[
                { key: "agency", label: "Agence" },
                { key: "total", label: "Demandes" },
                { key: "funded", label: "Financées" },
                { key: "rejected", label: "Rejetées" },
                { key: "open", label: "En cours" },
              ]}
              dataset={outcomeRows}
              description=""
              hideFallback
              height={Math.max(360, outcomeRows.length * 44 + 120)}
              options={
                {
                  color: ["#0b6e5d", "#dc2626", "#d97706"],
                  legend: { top: 0 },
                  grid: { left: 140, top: 42 },
                  xAxis: { type: "value", name: "Demandes" },
                  yAxis: { type: "category", inverse: true },
                  series: [
                    {
                      name: "Financées",
                      type: "bar",
                      stack: "résultats",
                      encode: { x: "funded", y: "agency" },
                    },
                    {
                      name: "Rejetées",
                      type: "bar",
                      stack: "résultats",
                      encode: { x: "rejected", y: "agency" },
                    },
                    {
                      name: "En cours",
                      type: "bar",
                      stack: "résultats",
                      encode: { x: "open", y: "agency" },
                    },
                  ],
                } as EChartsOption
              }
              title="Volume et résultats par agence"
            />

            <AnalyticsChart
              columns={[
                { key: "agency", label: "Agence" },
                { key: "volume", label: "Demandes" },
                { key: "rate", label: "Taux de financement" },
                { key: "delay", label: "Délai moyen" },
              ]}
              dataset={positioningRows}
              description=""
              options={
                {
                  tooltip: {
                    trigger: "item",
                    formatter: (params: { data?: { agency?: string }; name?: string }) =>
                      params.data?.agency ?? params.name ?? "Agence",
                  },
                  grid: { bottom: 56 },
                  xAxis: { type: "value", name: "Demandes" },
                  yAxis: { type: "value", name: "Financement (%)", min: 0, max: 100 },
                  visualMap: {
                    dimension: 3,
                    orient: "horizontal",
                    bottom: 0,
                    left: "center",
                    inRange: { color: ["#0b6e5d", "#d97706", "#dc2626"] },
                  },
                  series: [
                    {
                      type: "scatter",
                      symbolSize: 18,
                      encode: {
                        x: "volume",
                        y: "rate",
                        itemName: "agency",
                        tooltip: ["agency"],
                      },
                      markLine: {
                        silent: true,
                        symbol: "none",
                        lineStyle: { type: "dashed", color: "#94a3b8" },
                        data: [{ xAxis: agencyVolumeAverage }, { yAxis: agencyRateAverage }],
                      },
                    },
                  ],
                } as EChartsOption
              }
              title="Positionnement des agences"
            />
          </>
        )}
      </div>
    </div>
  );
}
