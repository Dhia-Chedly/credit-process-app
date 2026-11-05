"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, ExternalLink, UserRound } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/ui/data-state";
import { QueryErrorState } from "@/features/analytics/query-state";
import { apiFetch, type PaginatedResponse } from "@/lib/api/client";
import { cn } from "@/lib/utils";

type AlertState = "new" | "escalated";
type AlertTab = "new" | "escalated";

type DelayAlert = {
  id: string;
  agency: string;
  agency_name: string;
  reference: string;
  application_id: string;
  rule_label: string;
  state: AlertState;
  state_label: string;
  reporting_period: string;
  started_on: string;
  responsible_role: string;
  responsible_name: string;
};

type ResponsibleOption = {
  key: string;
  agencyId: string;
  agencyName: string;
  role: string;
  name: string;
};

type DelayAlertResponse = PaginatedResponse<DelayAlert> & {
  summary: Record<AlertTab, number>;
  filter_options: {
    agencies: Array<{ agency_id: string; agency__name: string }>;
    responsibles: Array<{
      agency_id: string;
      agency__name: string;
      responsible_role: string;
      responsible_name: string;
    }>;
  };
};

const tabs: ReadonlyArray<{ value: AlertTab; label: string }> = [
  { value: "new", label: "Nouvelles" },
  { value: "escalated", label: "Escaladées" },
];

const stateStyles: Record<AlertState, { card: string }> = {
  new: {
    card: "border-blue-200",
  },
  escalated: {
    card: "border-red-200",
  },
};

function ageInDays(value: string) {
  const started = new Date(`${value}T00:00:00`);
  return Math.max(Math.floor((Date.now() - started.getTime()) / 86_400_000), 0);
}

function urgencyStyle(days: number) {
  if (days >= 15) return "bg-red-100 text-red-800";
  if (days >= 8) return "bg-amber-100 text-amber-800";
  return "bg-emerald-100 text-emerald-800";
}

function displayDate(value: string) {
  return new Intl.DateTimeFormat("fr-TN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(`${value}T00:00:00`));
}

function responsibleKey(option: Pick<ResponsibleOption, "agencyId" | "role" | "name">) {
  return [option.agencyId, option.role, option.name].join("\u001f");
}

export function DelayAlertsDashboard() {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<AlertTab>("new");
  const [agency, setAgency] = useState("all");
  const [responsible, setResponsible] = useState("all");
  const [responsibleFilter, setResponsibleFilter] = useState<ResponsibleOption | undefined>();
  const [page, setPage] = useState(1);
  const query = useQuery({
    queryKey: ["delay-alerts", { agency, page, responsible, tab }],
    queryFn: ({ signal }) => {
      return apiFetch<DelayAlertResponse>("/delay-alerts/", {
        signal,
        query: {
          agency: agency === "all" ? undefined : agency,
          page,
          responsible: responsibleFilter?.name,
          responsible_role: responsibleFilter?.role,
          state: tab,
        },
      });
    },
  });
  const resolve = useMutation({
    mutationFn: (id: string) =>
      apiFetch<void>(`/delay-alerts/${id}/resolve/`, { method: "DELETE" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["delay-alerts"] });
    },
  });

  const alerts = query.data?.results ?? [];
  const agencies = useMemo(
    () =>
      (query.data?.filter_options.agencies ?? []).map((item) => ({
        id: item.agency_id,
        name: item.agency__name,
      })),
    [query.data?.filter_options.agencies],
  );
  const responsibleOptions = useMemo<ResponsibleOption[]>(
    () =>
      (query.data?.filter_options.responsibles ?? [])
        .map((item) => {
          const option = {
            agencyId: item.agency_id,
            agencyName: item.agency__name,
            role: item.responsible_role,
            name: item.responsible_name,
          };
          return { ...option, key: responsibleKey(option) };
        })
        .sort((left, right) =>
          `${left.name} ${left.agencyName}`.localeCompare(
            `${right.name} ${right.agencyName}`,
            "fr",
          ),
        ),
    [query.data?.filter_options.responsibles],
  );
  const compatibleResponsibleOptions = responsibleOptions.filter(
    (option) => agency === "all" || option.agencyId === agency,
  );
  function changeAgency(nextAgency: string) {
    setAgency(nextAgency);
    const selectedResponsible = responsibleOptions.find((option) => option.key === responsible);
    if (
      nextAgency !== "all" &&
      selectedResponsible !== undefined &&
      selectedResponsible.agencyId !== nextAgency
    ) {
      setResponsible("all");
      setResponsibleFilter(undefined);
    }
    setPage(1);
  }

  function changeResponsible(nextResponsible: string) {
    setResponsible(nextResponsible);
    const selectedResponsible = responsibleOptions.find((option) => option.key === nextResponsible);
    setResponsibleFilter(selectedResponsible);
    if (selectedResponsible !== undefined) setAgency(selectedResponsible.agencyId);
    setPage(1);
  }

  if (query.isLoading) return <LoadingState label="Chargement des alertes…" />;
  if (query.isError) return <QueryErrorState error={query.error} label="Alertes de délai" />;

  return (
    <div className="mt-6 space-y-6">
      <section
        aria-label="File de traitement des alertes"
        className="rounded-2xl border border-[var(--border)] bg-slate-50/70 p-4 sm:p-5"
      >
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <h2 className="text-lg font-semibold">Alertes opérationnelles</h2>
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            <label>
              <span className="sr-only">Filtrer par agence</span>
              <select
                className="min-h-10 w-full rounded-lg border border-[var(--border)] bg-white px-3"
                onChange={(event) => changeAgency(event.target.value)}
                value={agency}
              >
                <option value="all">Toutes les agences</option>
                {agencies.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span className="sr-only">Filtrer par responsable</span>
              <select
                className="min-h-10 w-full rounded-lg border border-[var(--border)] bg-white px-3"
                onChange={(event) => changeResponsible(event.target.value)}
                value={responsible}
              >
                <option value="all">Tous les responsables</option>
                {compatibleResponsibleOptions.map((item) => (
                  <option key={item.key} value={item.key}>
                    {item.name || item.role}
                    {agency === "all" ? ` — ${item.agencyName}` : ""}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>
        <div aria-label="État des alertes" className="mt-5 flex gap-2 overflow-x-auto pb-1">
          {tabs.map((item) => {
            const selected = tab === item.value;
            const count = query.data?.summary[item.value] ?? 0;
            return (
              <button
                className={cn(
                  "min-h-9 shrink-0 rounded-full border px-3 text-sm font-semibold",
                  selected
                    ? "border-[var(--brand)] bg-[var(--brand)] text-white"
                    : "border-[var(--border)] bg-white text-slate-700 hover:border-emerald-300",
                )}
                key={item.value}
                onClick={() => {
                  setTab(item.value);
                  setPage(1);
                }}
                type="button"
              >
                {item.label}{" "}
                <span
                  className={cn(
                    "ml-1 rounded-full px-1.5 py-0.5 text-xs",
                    selected ? "bg-white/20" : "bg-slate-100",
                  )}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </div>

        {alerts.length === 0 ? (
          <p className="mt-5 rounded-xl border border-dashed border-[var(--border)] bg-white p-10 text-center text-sm text-[var(--muted)]">
            Aucune alerte ne correspond aux filtres sélectionnés.
          </p>
        ) : (
          <div className="mt-5 grid gap-4 xl:grid-cols-2">
            {alerts.map((alert) => {
              const age = ageInDays(alert.started_on);
              const style = stateStyles[alert.state];
              return (
                <article
                  className={cn("rounded-xl border bg-white p-4 shadow-sm", style.card)}
                  key={alert.id}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <Link
                        className="inline-flex items-center gap-1 font-semibold text-[var(--brand)] hover:underline"
                        href={`/applications/${alert.application_id}`}
                      >
                        {alert.reference}
                        <ExternalLink aria-hidden size={15} />
                      </Link>
                      <p className="mt-1 text-sm font-medium text-slate-800">{alert.rule_label}</p>
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-2">
                      <span
                        className={cn(
                          "rounded-full px-2.5 py-1 text-xs font-bold",
                          urgencyStyle(age),
                        )}
                      >
                        {`${age} j d’attente`}
                      </span>
                    </div>
                  </div>
                  <dl className="mt-4 grid gap-3 border-y border-slate-100 py-3 text-sm sm:grid-cols-2">
                    <div>
                      <dt className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-[var(--muted)]">
                        <UserRound aria-hidden size={14} />
                        Responsable
                      </dt>
                      <dd className="mt-1 font-medium">
                        {alert.responsible_name || alert.responsible_role}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs font-bold uppercase tracking-wide text-[var(--muted)]">
                        Bloqué depuis
                      </dt>
                      <dd className="mt-1">{displayDate(alert.started_on)}</dd>
                    </div>
                  </dl>
                  <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                    <Link
                      className="text-sm font-semibold text-[var(--brand)] hover:underline"
                      href={`/applications/${alert.application_id}`}
                    >
                      Ouvrir le dossier
                    </Link>
                    <Button
                      disabled={resolve.isPending}
                      onClick={() => resolve.mutate(alert.id)}
                      size="compact"
                      variant="secondary"
                    >
                      {resolve.isPending ? "Résolution…" : "Résoudre l’alerte"}
                    </Button>
                  </div>
                </article>
              );
            })}
          </div>
        )}
        <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 pt-4 text-sm text-[var(--muted)]">
          <span>
            Page {page} sur {Math.max(Math.ceil((query.data?.count ?? 0) / 50), 1)} ·{" "}
            {query.data?.count ?? 0} alerte
            {(query.data?.count ?? 0) > 1 ? "s" : ""}
          </span>
          <div className="flex gap-2">
            <Button
              disabled={!query.data?.previous}
              onClick={() => setPage((current) => current - 1)}
              size="compact"
              variant="secondary"
            >
              <ChevronLeft aria-hidden size={16} />
              Précédente
            </Button>
            <Button
              disabled={!query.data?.next}
              onClick={() => setPage((current) => current + 1)}
              size="compact"
              variant="secondary"
            >
              Suivante
              <ChevronRight aria-hidden size={16} />
            </Button>
          </div>
        </div>
      </section>
    </div>
  );
}
