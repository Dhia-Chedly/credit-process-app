"use client";

import type { EChartsOption } from "echarts";

import { AnalyticsChart } from "@/components/data/analytics-chart";
import { LoadingState } from "@/components/ui/data-state";
import { MetricCard } from "@/components/ui/metric-card";
import { DashboardFilters } from "@/features/analytics/dashboard-filters";
import { EmployeeWorkloadChart } from "@/features/analytics/employee-workload-chart";
import { QueryErrorState } from "@/features/analytics/query-state";
import { useOverview } from "@/features/analytics/queries";
import { formatInteger, numberValue } from "@/features/analytics/value";

export function ExecutiveOverview() {
  const overview = useOverview();
  const summary = overview.data?.summary;
  const total = numberValue(summary, ["total_requests", "registered_requests"]);
  const funded = numberValue(summary, ["funded_requests", "financed_requests"]);
  const rejected = numberValue(summary, ["rejected_requests"]);
  const open = numberValue(summary, ["open_or_unknown_requests", "active_requests"]);
  return (
    <div>
      <DashboardFilters showEmployeeFilters={false} />

      <div className="mt-6 space-y-6">
        {overview.isLoading ? (
          <LoadingState label="Chargement des indicateurs de direction…" />
        ) : overview.isError ? (
          <QueryErrorState error={overview.error} label="Indicateurs de direction" />
        ) : (
          <>
            <section aria-label="Indicateurs clés" className="grid gap-4 sm:grid-cols-3">
              <MetricCard accent="info" label="Demandes" value={formatInteger(total)} />
              <MetricCard accent="brand" label="Financées" value={formatInteger(funded)} />
              <MetricCard accent="critical" label="Rejets" value={formatInteger(rejected)} />
            </section>

            <div className="grid gap-6">
              <AnalyticsChart
                columns={[
                  { key: "result", label: "Résultat" },
                  { key: "value", label: "Demandes" },
                ]}
                dataset={[
                  { result: "Décaissées", value: funded ?? null },
                  { result: "Rejetées", value: rejected ?? null },
                  { result: "En cours", value: open ?? null },
                ]}
                description=""
                hideFallback
                options={
                  {
                    color: ["#08654f", "#dc2626", "#d97706"],
                    tooltip: { trigger: "item" },
                    series: [
                      {
                        type: "pie",
                        radius: ["48%", "72%"],
                        center: ["50%", "52%"],
                        encode: { itemName: "result", value: "value" },
                        label: { formatter: "{b}\n{d}%" },
                      },
                    ],
                    graphic: [
                      {
                        type: "text",
                        left: "center",
                        top: "42%",
                        style: {
                          text: `${formatInteger(total)}\ndemandes`,
                          textAlign: "center",
                          fill: "#0f172a",
                          fontSize: 15,
                          fontWeight: 700,
                          lineHeight: 22,
                        },
                      },
                    ],
                    legend: { bottom: 0 },
                  } as EChartsOption
                }
                title="Résultat des demandes"
              />
              <EmployeeWorkloadChart />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
