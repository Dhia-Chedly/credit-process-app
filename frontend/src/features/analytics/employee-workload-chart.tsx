"use client";

import * as Tabs from "@radix-ui/react-tabs";
import { useState } from "react";

import { AnalyticsChart } from "@/components/data/analytics-chart";
import { LoadingState } from "@/components/ui/data-state";
import { QueryErrorState } from "@/features/analytics/query-state";
import { useAnalyticsResults } from "@/features/analytics/queries";
import { numberValue, stringValue } from "@/features/analytics/value";

function WorkloadChart({ role }: { role: "gp" | "ca" }) {
  const query = useAnalyticsResults("employees", { role });
  if (query.isLoading) return <LoadingState label="Chargement de la charge de travail…" />;
  if (query.isError) return <QueryErrorState error={query.error} label="Charge de travail" />;
  const rows = (query.data?.results ?? []).filter(
    (row) => stringValue(row, ["employee_name"])?.trim().toLocaleLowerCase("fr-FR") !== "inconnu",
  );
  const dataset = rows.map((row) => {
    const employee = stringValue(row, ["employee_name"]) ?? "Non assigné";
    const agency = stringValue(row, ["agency_name"]);
    return {
      employee: agency ? `${employee} — ${agency}` : employee,
      requests: numberValue(row, ["total_requests"]) ?? 0,
    };
  });
  return (
    <AnalyticsChart
      columns={[
        { key: "employee", label: "Collaborateur" },
        { key: "requests", label: "Demandes" },
      ]}
      dataset={dataset}
      description=""
      emptyMessage="Aucune affectation disponible."
      options={{
        tooltip: { trigger: "item" },
        xAxis: { type: "category", axisLabel: { rotate: 35 } },
        yAxis: { type: "value" },
        series: [
          {
            name: "Demandes",
            type: "bar",
            encode: { x: "employee", y: "requests", itemName: "employee", tooltip: ["requests"] },
          },
        ],
      }}
      title={role === "gp" ? "Charge des GP" : "Charge des CA/CAA"}
    />
  );
}

export function EmployeeWorkloadChart() {
  const [role, setRole] = useState<"gp" | "ca">("gp");
  return (
    <Tabs.Root onValueChange={(value) => setRole(value as "gp" | "ca")} value={role}>
      <Tabs.List className="mb-5 inline-flex rounded-xl border border-[var(--border)] bg-white p-1">
        <Tabs.Trigger
          className="min-h-10 rounded-lg px-5 text-sm font-semibold data-[state=active]:bg-[var(--brand)] data-[state=active]:text-white"
          value="gp"
        >
          GP
        </Tabs.Trigger>
        <Tabs.Trigger
          className="min-h-10 rounded-lg px-5 text-sm font-semibold data-[state=active]:bg-[var(--brand)] data-[state=active]:text-white"
          value="ca"
        >
          CA/CAA
        </Tabs.Trigger>
      </Tabs.List>
      <WorkloadChart role={role} />
    </Tabs.Root>
  );
}
