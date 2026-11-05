"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { DataState, LoadingState } from "@/components/ui/data-state";
import { QueryErrorState } from "@/features/analytics/query-state";
import { apiFetch } from "@/lib/api/client";
import type { CreditRequest } from "@/lib/api/contracts";
import { apiPaths } from "@/lib/api/paths";

function formatDate(value: string | null | undefined) {
  if (!value) return "Non atteint";
  const date = new Date(`${value.slice(0, 10)}T00:00:00`);
  return Number.isNaN(date.valueOf())
    ? value
    : new Intl.DateTimeFormat("fr-TN", { day: "2-digit", month: "short", year: "numeric" }).format(
        date,
      );
}

function daysBetween(from: string | null | undefined, to: string | null | undefined) {
  if (!from || !to) return null;
  const start = new Date(`${from.slice(0, 10)}T00:00:00`).valueOf();
  const end = new Date(`${to.slice(0, 10)}T00:00:00`).valueOf();
  const days = Math.round((end - start) / 86_400_000);
  return days >= 0 ? `${days} j` : null;
}

export function ApplicationDetail({ applicationId }: { applicationId: string }) {
  const query = useQuery({
    queryKey: ["applications", applicationId],
    queryFn: ({ signal }) =>
      apiFetch<CreditRequest>(apiPaths.creditRequest(applicationId), { signal }),
  });

  if (query.isLoading) return <LoadingState label="Chargement du détail de la demande…" />;
  if (query.isError) return <QueryErrorState error={query.error} label="Détail de la demande" />;
  if (!query.data)
    return (
      <DataState title="Demande indisponible" tone="empty">
        Aucun détail n’a été retourné.
      </DataState>
    );

  const application = query.data;
  const finalStep = application.rejection_date
    ? ["Rejeté", application.rejection_date]
    : application.disbursement_date
      ? ["Décaissé", application.disbursement_date]
      : ["Résultat", null];
  const milestones = [
    ["Demande", application.request_date],
    ["Réception", application.received_at_agency_date],
    ["Affectation GP", application.assigned_to_gp_date],
    ["Visite", application.visit_date],
    finalStep,
  ] as [string, string | null | undefined][];
  const currentIndex = milestones.findIndex(([, date]) => !date);
  return (
    <div>
      <Link
        className="mb-6 inline-flex min-h-10 items-center rounded-lg border border-[var(--border)] px-4 py-2 text-sm font-semibold hover:bg-slate-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand)]"
        href="/applications"
      >
        Retour aux demandes
      </Link>
      <section className="rounded-2xl border border-[var(--border)] bg-slate-50/70 p-5">
        <h1 className="text-xl font-semibold text-slate-900">Chronologie du dossier</h1>
        <ol className="mt-7 grid gap-5 sm:grid-cols-5 sm:gap-0" aria-label="Étapes du dossier">
          {milestones.map(([label, date], index) => {
            const completed = Boolean(date);
            const current = currentIndex === index;
            const rejected = label === "Rejeté" && completed;
            const duration = index > 0 ? daysBetween(milestones[index - 1]?.[1], date) : null;
            return (
              <li className="relative min-w-0 sm:pr-4" key={label}>
                {index > 0 && (
                  <span className="absolute z-0 -left-[calc(100%-0.5rem)] top-4 hidden h-0.5 w-full bg-slate-200 sm:block" />
                )}
                <span
                  className={`relative z-10 flex size-8 items-center justify-center rounded-full border-2 text-xs font-bold ${rejected ? "border-red-600 bg-red-600 text-white" : completed ? "border-emerald-700 bg-emerald-700 text-white" : current ? "border-blue-600 bg-blue-50 text-blue-700" : "border-slate-300 bg-white text-slate-400"}`}
                >
                  {completed ? "✓" : index + 1}
                </span>
                <p className="mt-3 font-semibold text-slate-900">{label}</p>
                <p className="mt-1 text-sm text-[var(--muted)]">{formatDate(date)}</p>
                {duration && (
                  <p className="mt-1 text-xs font-semibold text-emerald-800">
                    {duration} depuis l’étape précédente
                  </p>
                )}
                {current && (
                  <p className="mt-1 text-xs font-semibold text-blue-700">Étape en cours</p>
                )}
              </li>
            );
          })}
        </ol>
        <p className="mt-6 border-t border-slate-200 pt-4 text-sm text-slate-700">
          <span className="font-semibold">CA/CAA :</span>{" "}
          {application.counsellor_name || "Non affecté"}
          <span className="mx-3 text-slate-300">|</span>
          <span className="font-semibold">GP :</span> {application.gp_name || "Non affecté"}
        </p>
      </section>
    </div>
  );
}
