"use client";

import type { EChartsOption } from "echarts";

import { AnalyticsChart } from "@/components/data/analytics-chart";
import { DataState, LoadingState } from "@/components/ui/data-state";
import { DashboardFilters } from "@/features/analytics/dashboard-filters";
import { QueryErrorState } from "@/features/analytics/query-state";
import { useAnalyticsResults } from "@/features/analytics/queries";
import { numberValue, stringValue } from "@/features/analytics/value";

export function ActivityDashboard() {
  const query = useAnalyticsResults("activities");
  const rows = query.data?.results ?? [];
  const controlled = rows.filter((row) => row.activity_source === "controlled");
  const activities = [
    ...new Set(controlled.map((row) => stringValue(row, ["activity_label"]) ?? "Autres")),
  ];
  const activityTotals = activities
    .map((activity) => {
      const activityRows = controlled.filter(
        (row) => stringValue(row, ["activity_label"]) === activity,
      );
      return {
        activity,
        requests: activityRows.reduce(
          (sum, row) => sum + (numberValue(row, ["total_requests"]) ?? 0),
          0,
        ),
        funded: activityRows.reduce(
          (sum, row) => sum + (numberValue(row, ["funded_requests"]) ?? 0),
          0,
        ),
        rejected: activityRows.reduce(
          (sum, row) => sum + (numberValue(row, ["rejected_requests"]) ?? 0),
          0,
        ),
        requestedAmount: activityRows.reduce(
          (sum, row) => sum + (numberValue(row, ["requested_amount"]) ?? 0),
          0,
        ),
      };
    })
    .sort((a, b) => b.requests - a.requests);

  return (
    <div>
      <DashboardFilters showEmployeeFilters={false} />
      <div className="mt-6 space-y-6">
        {query.isLoading ? (
          <LoadingState label="Chargement des activités…" />
        ) : query.isError ? (
          <QueryErrorState error={query.error} label="Analyse des activités" />
        ) : (
          <>
            {controlled.length === 0 ? (
              <DataState title="Analyse des activités indisponible" tone="empty">
                Aucune catégorie d’activité gouvernée n’est disponible pour ces filtres. Les
                libellés bruts ne sont pas transformés en classement.
              </DataState>
            ) : (
              <>
                <AnalyticsChart
                  columns={[
                    { key: "activity", label: "Activité" },
                    { key: "requests", label: "Demandes" },
                    { key: "funded", label: "Financées" },
                    { key: "rejected", label: "Rejetées" },
                  ]}
                  dataset={activityTotals}
                  description=""
                  height={Math.max(340, activityTotals.length * 44 + 120)}
                  hideFallback
                  options={
                    {
                      legend: { top: 0 },
                      grid: { left: 120, top: 42 },
                      xAxis: { type: "value" },
                      yAxis: { type: "category" },
                      series: [
                        {
                          name: "Demandes",
                          type: "bar",
                          encode: { x: "requests", y: "activity" },
                          itemStyle: { color: "#2563eb" },
                        },
                        {
                          name: "Financées",
                          type: "bar",
                          encode: { x: "funded", y: "activity" },
                          itemStyle: { color: "#0b6e5d" },
                        },
                        {
                          name: "Rejetées",
                          type: "bar",
                          encode: { x: "rejected", y: "activity" },
                          itemStyle: { color: "#dc2626" },
                        },
                      ],
                    } as EChartsOption
                  }
                  title="Résultats par activité"
                />
                <AnalyticsChart
                  columns={[
                    { key: "activity", label: "Activité" },
                    { key: "requestedAmount", label: "Montant demandé (TND)" },
                  ]}
                  dataset={activityTotals}
                  description=""
                  hideFallback
                  options={
                    {
                      tooltip: { trigger: "axis" },
                      grid: { left: 75, right: 30, bottom: 90 },
                      xAxis: { type: "category", axisLabel: { rotate: 30 } },
                      yAxis: { type: "value", name: "TND" },
                      series: [
                        {
                          name: "Montant demandé",
                          type: "bar",
                          encode: { x: "activity", y: "requestedAmount" },
                          itemStyle: { color: "#0b6e5d", borderRadius: [6, 6, 0, 0] },
                        },
                      ],
                    } as EChartsOption
                  }
                  title="Montant demandé par activité"
                />
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
