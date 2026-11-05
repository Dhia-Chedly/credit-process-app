"use client";

import type { EChartsOption } from "echarts";
import { useState } from "react";

import { AnalyticsChart, type ChartDatasetRow } from "@/components/data/analytics-chart";
import { RankingPanel } from "@/components/data/dashboard-panels";
import { LoadingState } from "@/components/ui/data-state";
import { DashboardFilters } from "@/features/analytics/dashboard-filters";
import { QueryErrorState } from "@/features/analytics/query-state";
import { useAnalyticsResults } from "@/features/analytics/queries";
import { numberValue, stringValue } from "@/features/analytics/value";
import type { AnalyticsRecord } from "@/lib/api/contracts";

function summarize(rows: AnalyticsRecord[], keyName: "reason" | "agency" | "gp") {
  const keyFields =
    keyName === "reason"
      ? ["reason_label", "reason_category"]
      : keyName === "agency"
        ? ["agency_name"]
        : ["gp_name"];
  const grouped = new Map<string, number>();
  for (const row of rows) {
    const key = stringValue(row, keyFields) ?? "Non classé";
    grouped.set(key, (grouped.get(key) ?? 0) + (numberValue(row, ["rejected_requests"]) ?? 0));
  }
  return [...grouped].sort((a, b) => b[1] - a[1]);
}

function matrixData(rows: AnalyticsRecord[]) {
  const agencies = [...new Set(rows.map((row) => stringValue(row, ["agency_name"]) ?? "Agence"))];
  const reasons = [
    ...new Set(
      rows.map((row) => stringValue(row, ["reason_label", "reason_category"]) ?? "Non classé"),
    ),
  ];
  const values = rows.map((row) => [
    agencies.indexOf(stringValue(row, ["agency_name"]) ?? "Agence"),
    reasons.indexOf(stringValue(row, ["reason_label", "reason_category"]) ?? "Non classé"),
    numberValue(row, ["rejected_requests"]) ?? 0,
  ]);
  return { agencies, reasons, values };
}

export function RejectionDashboard() {
  const [rankingScope, setRankingScope] = useState<"agency" | "gp">("agency");
  const query = useAnalyticsResults("rejections");
  const rows = query.data?.results ?? [];
  const reasons = summarize(rows, "reason");
  const reasonTotal = reasons.reduce((sum, [, value]) => sum + value, 0);
  const paretoReasons = reasons.slice(0, 10);
  const pareto = paretoReasons.map(([label, value], index) => {
    const cumulativeRejections = paretoReasons
      .slice(0, index + 1)
      .reduce((sum, [, count]) => sum + count, 0);
    return {
      cause: label,
      rejections: value,
      cumulative: reasonTotal ? Math.round((10000 * cumulativeRejections) / reasonTotal) / 100 : 0,
    };
  });
  const ranking = summarize(rows, rankingScope).slice(0, 5);
  const matrix = matrixData(rows);
  const heatmapRows: ChartDatasetRow[] = rows.map((row) => ({
    agence: stringValue(row, ["agency_name"]) ?? "Agence",
    cause: stringValue(row, ["reason_label", "reason_category"]) ?? "Non classé",
    rejets: numberValue(row, ["rejected_requests"]) ?? 0,
  }));

  return (
    <div>
      <DashboardFilters showEmployeeFilters={false} />
      <div className="mt-6 space-y-6">
        {query.isLoading ? (
          <LoadingState label="Chargement des rejets…" />
        ) : query.isError ? (
          <QueryErrorState error={query.error} label="Analyse des rejets" />
        ) : (
          <>
            <div className="grid gap-6 xl:grid-cols-2">
              <AnalyticsChart
                columns={[
                  { key: "cause", label: "Motif du rejet" },
                  { key: "rejections", label: "Rejets" },
                  { key: "cumulative", label: "Part cumulée" },
                ]}
                dataset={pareto}
                description=""
                hideFallback
                options={
                  {
                    tooltip: { trigger: "axis" },
                    grid: { bottom: 100 },
                    xAxis: { type: "category", axisLabel: { rotate: 35 } },
                    yAxis: [
                      { type: "value", name: "Rejets" },
                      { type: "value", name: "% cumulé", min: 0, max: 100 },
                    ],
                    series: [
                      {
                        name: "Rejets",
                        type: "bar",
                        encode: { x: "cause", y: "rejections" },
                        itemStyle: { color: "#b91c1c" },
                      },
                      {
                        name: "Part cumulée",
                        type: "line",
                        yAxisIndex: 1,
                        encode: { x: "cause", y: "cumulative" },
                        smooth: true,
                        itemStyle: { color: "#d97706" },
                        markLine: {
                          symbol: "none",
                          lineStyle: { type: "dashed", color: "#64748b" },
                          data: [{ yAxis: 80, name: "80%" }],
                        },
                      },
                    ],
                  } as EChartsOption
                }
                title="Motifs de rejet prioritaires"
              />
              <div>
                <div className="mb-4 inline-flex rounded-lg border border-[var(--border)] p-1">
                  <button
                    className={`rounded-md px-3 py-1.5 text-sm font-semibold ${rankingScope === "agency" ? "bg-[var(--brand)] text-white" : "text-slate-600"}`}
                    onClick={() => setRankingScope("agency")}
                    type="button"
                  >
                    Agences
                  </button>
                  <button
                    className={`rounded-md px-3 py-1.5 text-sm font-semibold ${rankingScope === "gp" ? "bg-[var(--brand)] text-white" : "text-slate-600"}`}
                    onClick={() => setRankingScope("gp")}
                    type="button"
                  >
                    GP
                  </button>
                </div>
                <RankingPanel
                  description=""
                  items={ranking.map(([label, value], index) => ({
                    id: String(index),
                    label,
                    value,
                  }))}
                  title={
                    rankingScope === "agency"
                      ? "Agences les plus concernées"
                      : "GP les plus concernés"
                  }
                  valueLabel="rejets"
                />
              </div>
            </div>
            <AnalyticsChart
              columns={[
                { key: "agence", label: "Agence" },
                { key: "cause", label: "Motif du rejet" },
                { key: "rejets", label: "Rejets" },
              ]}
              dataset={heatmapRows}
              description=""
              hideFallback
              options={
                {
                  tooltip: { position: "top" },
                  grid: { left: 120, right: 30, top: 20, bottom: 90 },
                  xAxis: { type: "category", data: matrix.agencies, axisLabel: { rotate: 35 } },
                  yAxis: { type: "category", data: matrix.reasons },
                  visualMap: {
                    min: 0,
                    max: Math.max(...matrix.values.map((value) => Number(value[2])), 1),
                    calculable: true,
                    orient: "horizontal",
                    left: "center",
                    bottom: 0,
                    inRange: { color: ["#eef7f3", "#f59e0b", "#b91c1c"] },
                  },
                  series: [{ type: "heatmap", data: matrix.values, label: { show: true } }],
                } as EChartsOption
              }
              title="Matrice agence × motif de rejet"
            />
          </>
        )}
      </div>
    </div>
  );
}
