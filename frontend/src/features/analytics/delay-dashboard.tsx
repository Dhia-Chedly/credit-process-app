"use client";

import * as Tabs from "@radix-ui/react-tabs";
import type { EChartsOption } from "echarts";
import { useState } from "react";

import { AnalyticsChart } from "@/components/data/analytics-chart";
import { LoadingState } from "@/components/ui/data-state";
import { MetricCard } from "@/components/ui/metric-card";
import { DashboardFilters } from "@/features/analytics/dashboard-filters";
import { QueryErrorState } from "@/features/analytics/query-state";
import { useAnalyticsResults, useDelays } from "@/features/analytics/queries";
import { formatDays, numberValue, stringValue } from "@/features/analytics/value";

const STAGE_DURATION_INTERVALS = new Set([
  "request_to_reception",
  "reception_to_assignment",
  "assignment_to_visit",
  "visit_to_outcome",
]);

function ComparisonPanel({ role }: { role: "agency" | "gp" | "ca" }) {
  const query = useAnalyticsResults(
    role === "agency" ? "agencies" : "employees",
    role === "agency" ? {} : { role },
  );
  if (query.isLoading) return <LoadingState label="Chargement de la comparaison…" />;
  if (query.isError) return <QueryErrorState error={query.error} label="Comparaison des délais" />;
  const rows = query.data?.results ?? [];
  const delayField = role === "agency" ? "average_processing_days" : "average_role_delay_days";
  const delayLabel =
    role === "agency" ? "Jours moyens demande → résultat" : "Jours moyens sur l’étape suivie";
  const categoryField = role === "agency" ? ["agency_name"] : ["employee_name"];
  const categoryLabel = role === "agency" ? "Agence" : role.toUpperCase();
  const chartRows = rows
    .map((row) => {
      const category = stringValue(row, categoryField) ?? "Non assigné";
      const agency = role === "agency" ? undefined : stringValue(row, ["agency_name"]);
      return {
        category: agency ? `${category} — ${agency}` : category,
        delay: numberValue(row, [delayField]) ?? null,
      };
    })
    .sort((left, right) =>
      left.category.localeCompare(right.category, "fr", { sensitivity: "base" }),
    );
  return (
    <div className="space-y-5">
      <AnalyticsChart
        columns={[
          { key: "category", label: categoryLabel },
          { key: "delay", label: delayLabel },
        ]}
        dataset={chartRows}
        description=""
        emptyMessage="Aucun délai mesurable pour ce périmètre."
        height={440}
        options={{
          grid: { left: 24, right: 20, top: 32, bottom: 110, containLabel: true },
          tooltip: { trigger: "item" },
          xAxis: {
            type: "category",
            axisLabel: { interval: 0, rotate: 45, hideOverlap: false, fontSize: 11 },
          },
          yAxis: { type: "value", name: "Jours" },
          series: [
            {
              type: "bar",
              encode: { x: "category", y: "delay", itemName: "category", tooltip: ["delay"] },
              name: delayLabel,
            },
          ],
        }}
        title={`Délai par ${role === "agency" ? "agence" : role.toUpperCase()}`}
      />
    </div>
  );
}

export function DelayDashboard() {
  const [comparison, setComparison] = useState<"agency" | "gp" | "ca">("agency");
  const delays = useDelays();
  const intervals = delays.data?.intervals ?? [];
  const stageIntervals = intervals.filter((row) =>
    STAGE_DURATION_INTERVALS.has(String(row.interval_code)),
  );
  const processStages = stageIntervals.map((row) => ({
    key: String(row.interval_code),
    label: stringValue(row, ["interval_label"]) ?? "Étape",
    average: numberValue(row, ["average_days"]),
    sample: numberValue(row, ["sample_size"]) ?? 0,
  }));
  const processDataset = processStages.some((stage) => stage.average !== null)
    ? [
        {
          process: "Parcours moyen",
          ...Object.fromEntries(processStages.map((stage) => [stage.key, stage.average])),
        },
      ]
    : [];
  return (
    <div>
      <DashboardFilters showEmployeeFilters={false} />
      <div className="mt-6 space-y-6">
        {delays.isLoading ? (
          <LoadingState label="Chargement des délais…" />
        ) : delays.isError ? (
          <QueryErrorState error={delays.error} label="Délais de traitement" />
        ) : (
          <>
            <section className="grid gap-4 sm:grid-cols-3" aria-label="Synthèse des délais">
              <MetricCard
                accent="info"
                label="Délai global demande → résultat"
                value={formatDays(
                  intervals.find((row) => row.interval_code === "request_to_outcome")?.average_days,
                )}
              />
              <MetricCard
                accent="brand"
                label="Délai demande → décaissement"
                value={formatDays(
                  intervals.find((row) => row.interval_code === "request_to_disbursement")
                    ?.average_days,
                )}
              />
              <MetricCard
                accent="critical"
                label="Délai demande → rejet"
                value={formatDays(
                  intervals.find((row) => row.interval_code === "request_to_rejection")
                    ?.average_days,
                )}
              />
            </section>

            <AnalyticsChart
              columns={[
                { key: "process", label: "Processus" },
                ...processStages.map((stage) => ({
                  key: stage.key,
                  label: `${stage.label} (${stage.sample} dossiers)`,
                })),
              ]}
              dataset={processDataset}
              description=""
              hideFallback
              emptyMessage="Aucune étape mesurable pour ce périmètre."
              options={
                {
                  legend: { top: 0 },
                  grid: { left: 120, right: 24, top: 48, bottom: 24, containLabel: true },
                  tooltip: { trigger: "axis" },
                  xAxis: { type: "value", name: "Jours" },
                  yAxis: { type: "category" },
                  series: processStages.map((stage) => ({
                    name: stage.label,
                    type: "bar",
                    stack: "parcours",
                    encode: { x: stage.key, y: "process" },
                  })),
                } as EChartsOption
              }
              title="Durée du parcours par étape"
            />

            <Tabs.Root
              onValueChange={(value) => setComparison(value as typeof comparison)}
              value={comparison}
            >
              <Tabs.List
                aria-label="Comparer les délais"
                className="mb-5 inline-flex rounded-xl border border-[var(--border)] bg-white p-1"
              >
                {(
                  [
                    { value: "agency", label: "Agences" },
                    { value: "gp", label: "GP" },
                    { value: "ca", label: "CA" },
                  ] as const
                ).map((item) => (
                  <Tabs.Trigger
                    className="min-h-10 rounded-lg px-5 text-sm font-semibold text-slate-600 data-[state=active]:bg-[var(--brand)] data-[state=active]:text-white"
                    key={item.value}
                    value={item.value}
                  >
                    {item.label}
                  </Tabs.Trigger>
                ))}
              </Tabs.List>
              <Tabs.Content value={comparison}>
                <ComparisonPanel role={comparison} />
              </Tabs.Content>
            </Tabs.Root>
          </>
        )}
      </div>
    </div>
  );
}
