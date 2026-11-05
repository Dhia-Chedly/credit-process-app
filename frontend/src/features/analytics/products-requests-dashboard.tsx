"use client";

import type { EChartsOption } from "echarts";

import { AnalyticsChart } from "@/components/data/analytics-chart";
import { DataState, LoadingState } from "@/components/ui/data-state";
import { MetricCard } from "@/components/ui/metric-card";
import { DashboardFilters } from "@/features/analytics/dashboard-filters";
import { QueryErrorState } from "@/features/analytics/query-state";
import { useAnalyticsResults } from "@/features/analytics/queries";
import { numberValue, stringValue } from "@/features/analytics/value";
import type { AnalyticsRecord } from "@/lib/api/contracts";

type Classification = "request_type_label" | "credit_type_label";

function formatAmount(value: number) {
  return `${new Intl.NumberFormat("fr-TN", { maximumFractionDigits: 3 }).format(value)} TND`;
}

function monthLabel(value: string) {
  const match = /^(\d{4}-\d{2})/.exec(value);
  return match?.[1] ?? value;
}

function classify(rows: AnalyticsRecord[], field: Classification) {
  const grouped = new Map<
    string,
    {
      label: string;
      demandes: number;
      montant: number;
      decaissees: number;
      rejetees: number;
      enCours: number;
    }
  >();
  for (const row of rows) {
    const label = stringValue(row, [field]);
    if (!label) continue;
    const current = grouped.get(label) ?? {
      label,
      demandes: 0,
      montant: 0,
      decaissees: 0,
      rejetees: 0,
      enCours: 0,
    };
    current.demandes += numberValue(row, ["total_requests"]) ?? 0;
    current.montant += numberValue(row, ["requested_amount"]) ?? 0;
    current.decaissees += numberValue(row, ["funded_requests"]) ?? 0;
    current.rejetees += numberValue(row, ["rejected_requests"]) ?? 0;
    current.enCours += numberValue(row, ["active_requests"]) ?? 0;
    grouped.set(label, current);
  }
  return [...grouped.values()].sort((first, second) => second.demandes - first.demandes);
}

function monthlyRequestTypes(rows: AnalyticsRecord[]) {
  const grouped = new Map<string, { mois: string; type: string; demandes: number }>();
  for (const row of rows) {
    const rawMonth = stringValue(row, ["month"]);
    const type = stringValue(row, ["request_type_label"]);
    if (!rawMonth || !type) continue;
    const mois = monthLabel(rawMonth);
    const key = `${mois}:${type}`;
    const current = grouped.get(key) ?? { mois, type, demandes: 0 };
    current.demandes += numberValue(row, ["total_requests"]) ?? 0;
    grouped.set(key, current);
  }
  return [...grouped.values()].sort((first, second) => first.mois.localeCompare(second.mois));
}

function requestCreditMatrix(rows: AnalyticsRecord[]) {
  const classifiedRows = rows.flatMap((row) => {
    const requestType = stringValue(row, ["request_type_label"]);
    const creditType = stringValue(row, ["credit_type_label"]);
    return requestType && creditType ? [{ row, requestType, creditType }] : [];
  });
  const requestTypes = [...new Set(classifiedRows.map(({ requestType }) => requestType))];
  const creditTypes = [...new Set(classifiedRows.map(({ creditType }) => creditType))];
  const totals = new Map<string, number>();
  for (const { row, requestType, creditType } of classifiedRows) {
    const key = `${requestType}:${creditType}`;
    totals.set(key, (totals.get(key) ?? 0) + (numberValue(row, ["total_requests"]) ?? 0));
  }
  const values = [...totals].map(([key, demandes]) => {
    const [rawRequestType, rawCreditType] = key.split(":");
    const requestType = rawRequestType ?? "";
    const creditType = rawCreditType ?? "";
    return [creditTypes.indexOf(creditType), requestTypes.indexOf(requestType), demandes];
  });
  return { requestTypes, creditTypes, values };
}

export function ProductsRequestsDashboard() {
  const query = useAnalyticsResults("products-requests");
  const rows = query.data?.results ?? [];
  const requestTypes = classify(rows, "request_type_label");
  const creditTypes = classify(rows, "credit_type_label");
  const monthly = monthlyRequestTypes(rows);
  const matrix = requestCreditMatrix(rows);
  const months = [...new Set(monthly.map((row) => row.mois))];
  const monthlyTypes = [...new Set(monthly.map((row) => row.type))];
  const totalRequestedAmount = creditTypes.reduce((sum, creditType) => sum + creditType.montant, 0);
  const mostRequestedCreditType = creditTypes[0];

  return (
    <div>
      <DashboardFilters showEmployeeFilters={false} />
      <div className="mt-6 space-y-6">
        {query.isLoading ? (
          <LoadingState label="Chargement des produits et demandes…" />
        ) : query.isError ? (
          <QueryErrorState error={query.error} label="Produits et demandes" />
        ) : rows.length === 0 ? (
          <DataState title="Aucune donnée de produit disponible" tone="empty">
            Aucun dossier consolidé ne correspond aux filtres sélectionnés.
          </DataState>
        ) : (
          <>
            <section aria-label="Indicateurs clés" className="grid gap-4 sm:grid-cols-2">
              <MetricCard
                accent="brand"
                label="Montant demandé"
                note=""
                value={formatAmount(totalRequestedAmount)}
              />
              <MetricCard
                accent="info"
                label="Type de crédit le plus demandé"
                note={`${mostRequestedCreditType?.demandes ?? 0} dossier${mostRequestedCreditType?.demandes === 1 ? "" : "s"}`}
                value={mostRequestedCreditType?.label ?? "—"}
              />
            </section>
            <div className="grid gap-6 xl:grid-cols-2">
              <AnalyticsChart
                columns={[
                  { key: "label", label: "Type de demande" },
                  { key: "demandes", label: "Dossiers" },
                  { key: "montant", label: "Montant demandé (TND)" },
                ]}
                dataset={requestTypes}
                description=""
                hideFallback
                options={
                  {
                    grid: { left: 110, right: 35, bottom: 70 },
                    tooltip: { trigger: "axis" },
                    xAxis: { type: "category", axisLabel: { rotate: 20 } },
                    yAxis: [
                      { type: "value", name: "Dossiers" },
                      { type: "value", name: "TND" },
                    ],
                    series: [
                      {
                        name: "Dossiers",
                        type: "bar",
                        encode: { x: "label", y: "demandes" },
                        itemStyle: { color: "#2563eb" },
                      },
                      {
                        name: "Montant demandé",
                        type: "line",
                        yAxisIndex: 1,
                        encode: { x: "label", y: "montant" },
                        itemStyle: { color: "#0b6e5d" },
                      },
                    ],
                  } as EChartsOption
                }
                title="Demandes par type"
              />
              <AnalyticsChart
                columns={[
                  { key: "label", label: "Type de crédit" },
                  { key: "demandes", label: "Dossiers" },
                  { key: "montant", label: "Montant demandé (TND)" },
                ]}
                dataset={creditTypes}
                description=""
                hideFallback
                options={
                  {
                    grid: { left: 110, right: 35, bottom: 80 },
                    tooltip: { trigger: "axis" },
                    xAxis: [
                      { type: "value", name: "Dossiers" },
                      { type: "value", name: "TND" },
                    ],
                    yAxis: { type: "category" },
                    series: [
                      {
                        name: "Dossiers",
                        type: "bar",
                        encode: { x: "demandes", y: "label" },
                        itemStyle: { color: "#7c3aed" },
                      },
                      {
                        name: "Montant demandé",
                        type: "bar",
                        xAxisIndex: 1,
                        encode: { x: "montant", y: "label" },
                        itemStyle: { color: "#0b6e5d" },
                      },
                    ],
                  } as EChartsOption
                }
                title="Demandes par type de crédit"
              />
            </div>
            <div className="grid gap-6 xl:grid-cols-2">
              <AnalyticsChart
                columns={[
                  { key: "label", label: "Type de crédit" },
                  { key: "decaissees", label: "Décaissées" },
                  { key: "rejetees", label: "Rejetées" },
                  { key: "enCours", label: "En cours" },
                ]}
                dataset={creditTypes}
                description=""
                hideFallback
                options={
                  {
                    legend: { top: 0 },
                    grid: { left: 110, top: 42, bottom: 80 },
                    xAxis: { type: "value" },
                    yAxis: { type: "category" },
                    series: [
                      {
                        name: "Décaissées",
                        type: "bar",
                        stack: "statut",
                        encode: { x: "decaissees", y: "label" },
                        itemStyle: { color: "#0b6e5d" },
                      },
                      {
                        name: "Rejetées",
                        type: "bar",
                        stack: "statut",
                        encode: { x: "rejetees", y: "label" },
                        itemStyle: { color: "#dc2626" },
                      },
                      {
                        name: "En cours",
                        type: "bar",
                        stack: "statut",
                        encode: { x: "enCours", y: "label" },
                        itemStyle: { color: "#d97706" },
                      },
                    ],
                  } as EChartsOption
                }
                title="Résultats par type de crédit"
              />
              <AnalyticsChart
                columns={[
                  { key: "mois", label: "Mois" },
                  { key: "type", label: "Type de demande" },
                  { key: "demandes", label: "Dossiers" },
                ]}
                dataset={monthly}
                description=""
                hideFallback
                options={
                  {
                    tooltip: { trigger: "axis" },
                    grid: { left: 55, right: 30, bottom: 70 },
                    yAxis: { type: "value", name: "Dossiers" },
                    xAxis: { type: "category", data: months, axisLabel: { rotate: 25 } },
                    series: monthlyTypes.map((type) => ({
                      name: type,
                      type: "line",
                      smooth: true,
                      data: months.map(
                        (month) =>
                          monthly.find((row) => row.mois === month && row.type === type)
                            ?.demandes ?? 0,
                      ),
                    })),
                  } as EChartsOption
                }
                title="Évolution mensuelle des types de demande"
              />
            </div>
            <AnalyticsChart
              columns={[
                { key: "typeDemande", label: "Type de demande" },
                { key: "typeCredit", label: "Type de crédit" },
                { key: "demandes", label: "Dossiers" },
              ]}
              dataset={matrix.values.map((value) => ({
                typeDemande: matrix.requestTypes[Number(value[1])] ?? "",
                typeCredit: matrix.creditTypes[Number(value[0])] ?? "",
                demandes: Number(value[2]),
              }))}
              description=""
              hideFallback
              options={
                {
                  tooltip: { position: "top" },
                  grid: { left: 150, right: 30, top: 20, bottom: 90 },
                  xAxis: { type: "category", data: matrix.creditTypes, axisLabel: { rotate: 25 } },
                  yAxis: { type: "category", data: matrix.requestTypes },
                  visualMap: {
                    min: 0,
                    max: Math.max(...matrix.values.map((value) => Number(value[2])), 1),
                    calculable: true,
                    orient: "horizontal",
                    left: "center",
                    bottom: 0,
                    inRange: { color: ["#eef7f3", "#2563eb", "#0b6e5d"] },
                  },
                  series: [{ type: "heatmap", data: matrix.values, label: { show: true } }],
                } as EChartsOption
              }
              title="Types de demande × types de crédit"
            />
          </>
        )}
      </div>
    </div>
  );
}
