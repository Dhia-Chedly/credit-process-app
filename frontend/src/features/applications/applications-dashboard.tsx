"use client";

import type { ColumnDef } from "@tanstack/react-table";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import Link from "next/link";
import { FormEvent, memo, useState } from "react";

import { DataTable } from "@/components/data/data-table";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/ui/data-state";
import { QueryErrorState } from "@/features/analytics/query-state";
import { apiFetch, type PaginatedResponse } from "@/lib/api/client";
import type { CreditRequest } from "@/lib/api/contracts";
import { apiPaths } from "@/lib/api/paths";

function formatAmount(value: string | null) {
  if (value === null || value === "") return "—";
  const numeric = Number(value);
  return Number.isFinite(numeric)
    ? new Intl.NumberFormat("en-TN", { maximumFractionDigits: 3 }).format(numeric)
    : value;
}

type Period = "rolling" | "month" | "previous" | "quarter" | "year";

function monthStart(value: Date) {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-01`;
}

function periodFilters(period: Period) {
  if (period === "rolling") return {};
  const now = new Date();
  let start = new Date(now.getFullYear(), now.getMonth(), 1);
  let end = start;
  if (period === "previous") {
    start = new Date(now.getFullYear(), now.getMonth() - 1, 1);
    end = start;
  } else if (period === "quarter") {
    start = new Date(now.getFullYear(), Math.floor(now.getMonth() / 3) * 3, 1);
  } else if (period === "year") {
    start = new Date(now.getFullYear(), 0, 1);
  }
  return { request_date_from: monthStart(start), request_date_to: monthStart(end) };
}

const ApplicationsResults = memo(function ApplicationsResults({
  data,
  error,
  isError,
  isLoading,
}: {
  data: CreditRequest[];
  error: Error | null;
  isError: boolean;
  isLoading: boolean;
}) {
  if (isLoading) return <LoadingState label="Chargement des dossiers autorisés…" />;
  if (isError)
    return (
      <QueryErrorState
        error={error ?? new Error("Erreur de chargement")}
        label="Dossiers de crédit"
      />
    );
  return (
    <DataTable
      caption="Dossiers consolidés"
      columns={applicationColumns}
      data={data}
      emptyMessage="Aucun dossier autorisé ne correspond à ces filtres."
      getRowId={(row) => row.public_id ?? row.id}
      sortable={false}
    />
  );
});

const applicationColumns: ColumnDef<CreditRequest>[] = [
  {
    id: "reference",
    accessorFn: (row) => row.display_reference ?? row.reference ?? "Protected",
    header: "Référence",
    cell: ({ row }) => (
      <Link
        className="font-semibold text-[var(--brand)] hover:underline"
        href={`/applications/${row.original.public_id ?? row.original.id}`}
      >
        {row.original.display_reference ?? row.original.reference ?? "Protected"}
      </Link>
    ),
  },
  { accessorKey: "request_date", header: "Date de demande" },
  {
    id: "amount",
    accessorKey: "amount",
    header: "Montant demandé",
    cell: ({ getValue }) => (
      <span className="block text-right tabular-nums">
        {formatAmount(getValue() === null ? null : String(getValue()))}
      </span>
    ),
  },
  {
    accessorKey: "credit_type",
    header: "Type de crédit",
    cell: ({ getValue }) => String(getValue() || "—"),
  },
  {
    id: "status",
    accessorFn: (row) => row.status?.label ?? "Inconnu",
    header: "Statut",
    cell: ({ row }) => (
      <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">
        {row.original.status?.label ?? "Inconnu"}
      </span>
    ),
  },
];

export function ApplicationsDashboard() {
  const [draftSearch, setDraftSearch] = useState("");
  const [search, setSearch] = useState("");
  const [period, setPeriod] = useState<Period>("rolling");
  const filters = periodFilters(period);
  const query = useQuery({
    queryKey: ["applications", { search, ...filters }],
    queryFn: ({ signal }) =>
      apiFetch<PaginatedResponse<CreditRequest>>(apiPaths.creditRequests, {
        query: { search: search || undefined, ...filters },
        signal,
      }),
    placeholderData: (previous) => previous,
  });

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSearch(draftSearch.trim());
  }

  return (
    <div>
      <section
        aria-label="Filtres des dossiers"
        className="mt-6 max-w-sm rounded-2xl border border-[var(--border)] bg-slate-50 p-3"
      >
        <label className="relative flex-1">
          <span className="sr-only">Période</span>
          <select
            className="min-h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-800 shadow-sm"
            onChange={(event) => setPeriod(event.target.value as Period)}
            value={period}
          >
            <option value="rolling">12 derniers mois</option>
            <option value="month">Ce mois</option>
            <option value="previous">Mois précédent</option>
            <option value="quarter">Ce trimestre</option>
            <option value="year">Cette année</option>
          </select>
        </label>
      </section>
      <form className="mt-6 flex max-w-2xl flex-col gap-3 sm:flex-row" onSubmit={submitSearch}>
        <label className="relative flex-1">
          <span className="sr-only">Rechercher des dossiers</span>
          <Search aria-hidden="true" className="absolute left-3 top-3 text-slate-400" size={18} />
          <input
            className="min-h-11 w-full rounded-lg border border-[var(--border)] bg-white py-2 pl-10 pr-3 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand)]"
            onChange={(event) => setDraftSearch(event.target.value)}
            placeholder="Référence ou agence"
            type="search"
            value={draftSearch}
          />
        </label>
        <Button type="submit">Rechercher</Button>
        {search && (
          <Button
            onClick={() => {
              setDraftSearch("");
              setSearch("");
            }}
            type="button"
            variant="secondary"
          >
            Effacer la recherche
          </Button>
        )}
      </form>

      <div className="mt-6">
        <ApplicationsResults
          data={query.data?.results ?? []}
          error={query.error}
          isError={query.isError}
          isLoading={query.isLoading}
        />
      </div>
    </div>
  );
}
