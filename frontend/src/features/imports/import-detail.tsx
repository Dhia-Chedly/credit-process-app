"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo } from "react";

import { DataState, LoadingState } from "@/components/ui/data-state";
import { QueryErrorState } from "@/features/analytics/query-state";
import { failedImportGuidance, IMPORT_STATUS_LABELS } from "@/features/imports/import-presentation";
import { apiFetch, type PaginatedResponse } from "@/lib/api/client";
import type { DataQualityIssue, ImportBatch } from "@/lib/api/contracts";
import { apiPaths } from "@/lib/api/paths";

const ACTIVE_STATUSES = new Set<ImportBatch["status"]>(["uploaded", "queued", "processing"]);
const DATE_FIELDS = new Set([
  "request_date",
  "received_at_agency_date",
  "assigned_to_gp_date",
  "visit_date",
  "outcome_date",
]);

function linesLabel(count: number) {
  return `${count.toLocaleString("fr-FR")} ${count === 1 ? "ligne" : "lignes"}`;
}

function importedLinesSentence(count: number) {
  return `${linesLabel(count)} ${count === 1 ? "a été importée" : "ont été importées"} correctement.`;
}

function displayedCellValue(fieldName: string, value: string | null) {
  if (value === null || value === "") return value;
  if (DATE_FIELDS.has(fieldName)) {
    const match = /^(\d{4})-(\d{2})-(\d{2})(?:T.*)?$/.exec(value);
    if (match) return `${match[3]}/${match[2]}/${match[1]}`;
  }
  return value;
}

function OutcomePanel({ batch }: { batch: ImportBatch }) {
  if (batch.status === "failed") {
    if (batch.quarantined_count > 0) {
      return (
        <section aria-live="polite" className="border-l-4 border-red-600 pl-5">
          <h2 className="text-2xl font-semibold text-red-800">
            {linesLabel(batch.quarantined_count)}{" "}
            {batch.quarantined_count === 1 ? "doit" : "doivent"} être corrigée
            {batch.quarantined_count === 1 ? "" : "s"}
          </h2>
          <p className="mt-2">Aucune ligne n’a été importée.</p>
          <p className="mt-1 text-[var(--muted)]">
            Corrigez les cellules indiquées ci-dessous, puis importez de nouveau le fichier.
          </p>
        </section>
      );
    }
    const guidance = failedImportGuidance(batch.error_message);
    return (
      <section aria-live="polite" className="border-l-4 border-red-600 pl-5">
        <h2 className="text-2xl font-semibold text-red-800">L’import a échoué</h2>
        {batch.error_message && (
          <p className="mt-3 font-semibold">Erreur signalée : {batch.error_message}</p>
        )}
        <p className="mt-3">Cause probable : {guidance.explanation}</p>
        <p className="mt-2 font-medium">Action recommandée : {guidance.action}</p>
      </section>
    );
  }
  if (ACTIVE_STATUSES.has(batch.status)) {
    return (
      <section aria-live="polite">
        <h2 className="text-2xl font-semibold">{IMPORT_STATUS_LABELS[batch.status]}</h2>
        <p className="mt-2 text-[var(--muted)]">
          Le traitement est automatique. Cette page est actualisée toutes les quatre secondes.
        </p>
      </section>
    );
  }
  if (batch.quarantined_count === 0) {
    if (batch.unmatched_count > 0) {
      return (
        <section aria-live="polite">
          <h2 className="text-2xl font-semibold">
            Import accepté — {linesLabel(batch.unmatched_count)} en attente du suivi correspondant
          </h2>
          <p className="mt-2 text-[var(--muted)]">
            {linesLabel(batch.unmatched_count)}{" "}
            {batch.unmatched_count === 1 ? "est en attente" : "sont en attente"} du suivi
            correspondant.
          </p>
          <p className="mt-1 text-[var(--muted)]">
            Elles sont conservées en attente dans le système. Aucun dossier n’est créé avant le
            rapprochement exact avec l’autre suivi.
          </p>
        </section>
      );
    }
    return (
      <section aria-live="polite">
        <h2 className="text-2xl font-semibold">Import terminé</h2>
        <p className="mt-2">Toutes les lignes valides ont été importées correctement.</p>
      </section>
    );
  }
  return (
    <section aria-live="polite">
      <h2 className="text-2xl font-semibold">
        {linesLabel(batch.quarantined_count)} {batch.quarantined_count === 1 ? "doit" : "doivent"}{" "}
        être corrigée{batch.quarantined_count === 1 ? "" : "s"}
      </h2>
      <p className="mt-2">
        {batch.published_or_updated_count > 0
          ? importedLinesSentence(batch.published_or_updated_count)
          : "Aucune ligne erronée n’a été importée."}
      </p>
      <p className="mt-1 text-[var(--muted)]">
        Corrigez les valeurs indiquées ci-dessous, puis importez de nouveau le fichier.
      </p>
      {batch.unmatched_count > 0 && (
        <p className="mt-3 text-sm">
          {linesLabel(batch.unmatched_count)} attendent également le suivi correspondant.
        </p>
      )}
    </section>
  );
}

export function ImportDetail({ importId }: { importId: string }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const batch = useQuery({
    queryKey: ["imports", importId],
    queryFn: ({ signal }) => apiFetch<ImportBatch>(apiPaths.importBatch(importId), { signal }),
    refetchInterval: (query) =>
      query.state.data && ACTIVE_STATUSES.has(query.state.data.status) ? 4_000 : false,
  });
  const issues = useQuery({
    queryKey: ["imports", importId, "issues"],
    queryFn: async ({ signal }) => {
      const path = apiPaths.importBatchIssues(importId);
      const firstPage = await apiFetch<PaginatedResponse<DataQualityIssue>>(path, {
        signal,
      });
      const pageCount = Math.ceil(firstPage.count / Math.max(firstPage.results.length, 1));
      if (pageCount <= 1) return firstPage;
      const remainingPages = await Promise.all(
        Array.from({ length: pageCount - 1 }, (_, index) =>
          apiFetch<PaginatedResponse<DataQualityIssue>>(`${path}?page=${index + 2}`, { signal }),
        ),
      );
      return {
        ...firstPage,
        next: null,
        results: [firstPage, ...remainingPages].flatMap((page) => page.results),
      };
    },
    refetchInterval: batch.data && ACTIVE_STATUSES.has(batch.data.status) ? 4_000 : false,
  });
  useEffect(() => {
    if (
      searchParams.get("fromUpload") === "1" &&
      batch.data?.status === "completed" &&
      batch.data.unmatched_count === 0
    ) {
      router.replace("/imports");
    }
  }, [batch.data?.status, batch.data?.unmatched_count, router, searchParams]);
  const issueTables = useMemo(() => {
    const sheets = new Map<
      string,
      {
        columns: Map<string, string>;
        rows: Map<
          number,
          {
            issues: Map<string, DataQualityIssue>;
            values: Map<string, { label: string; value: string | null }>;
          }
        >;
      }
    >();
    const workbookIssues: DataQualityIssue[] = [];
    for (const issue of issues.data?.results ?? []) {
      if (issue.source_row === null) {
        workbookIssues.push(issue);
        continue;
      }
      const sheetName = issue.sheet_name ?? "Feuille non disponible";
      const sheet = sheets.get(sheetName) ?? { columns: new Map(), rows: new Map() };
      const row = sheet.rows.get(issue.source_row) ?? {
        issues: new Map<string, DataQualityIssue>(),
        values: new Map<string, { label: string; value: string | null }>(),
      };
      for (const cell of issue.row_values) {
        sheet.columns.set(cell.field_name, cell.field_label);
        row.values.set(cell.field_name, { label: cell.field_label, value: cell.value });
      }
      sheet.columns.set(issue.field_name, issue.field_label);
      row.issues.set(issue.field_name, issue);
      sheet.rows.set(issue.source_row, row);
      sheets.set(sheetName, sheet);
    }
    return {
      workbookIssues,
      sheets: [...sheets.entries()].map(([sheetName, sheet]) => ({
        sheetName,
        columns: [...sheet.columns.entries()],
        rows: [...sheet.rows.entries()].sort((left, right) => left[0] - right[0]),
      })),
    };
  }, [issues.data]);

  if (batch.isLoading) return <LoadingState label="Chargement du rapport d’import…" />;
  if (batch.isError) return <QueryErrorState error={batch.error} label="Rapport d’import" />;
  if (!batch.data)
    return (
      <DataState title="Import indisponible" tone="empty">
        Aucun lot n’a été retourné.
      </DataState>
    );

  return (
    <div>
      <Link
        className="inline-flex min-h-10 items-center rounded-lg border border-[var(--border)] px-4 py-2 text-sm font-semibold hover:bg-slate-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand)]"
        href="/imports"
      >
        Retour aux imports
      </Link>
      <div className="mt-6">
        <OutcomePanel batch={batch.data} />
      </div>

      <section className="mt-7" id="corrections">
        {issues.isLoading ? (
          <LoadingState label="Chargement des corrections…" />
        ) : issues.isError ? (
          <QueryErrorState error={issues.error} label="Corrections" />
        ) : issueTables.sheets.length === 0 && issueTables.workbookIssues.length === 0 ? (
          <div className="mt-4">
            <DataState title="Aucune correction requise" tone="empty">
              Aucun problème de qualité n’a été enregistré pour ce lot.
            </DataState>
          </div>
        ) : (
          <div className="mt-6 space-y-8">
            {issueTables.workbookIssues.length > 0 && (
              <section>
                <h3 className="font-semibold">Erreurs générales du fichier</h3>
                <ul className="mt-3 divide-y divide-red-200 border-y border-red-200">
                  {issueTables.workbookIssues.map((issue) => (
                    <li className="bg-red-50 px-3 py-3 text-sm" key={issue.id}>
                      <span className="font-semibold text-red-900">{issue.user_title}</span> —{" "}
                      {issue.required_correction}
                    </li>
                  ))}
                </ul>
              </section>
            )}
            {issueTables.sheets.map((sheet) => (
              <section key={sheet.sheetName}>
                <h3 className="text-lg font-semibold">Feuille {sheet.sheetName}</h3>
                <p className="mt-1 text-sm text-[var(--muted)]">
                  La ligne complète est visible ; seules les cellules non valides sont surlignées.
                </p>
                <div className="mt-3 overflow-x-auto border-y border-[var(--border)]">
                  <table className="w-full min-w-max border-collapse text-left text-sm">
                    <thead>
                      <tr className="border-b border-[var(--border)]">
                        <th className="px-3 py-3 font-semibold" scope="col">
                          Ligne Excel
                        </th>
                        {sheet.columns.map(([fieldName, fieldLabel]) => (
                          <th
                            className="max-w-72 px-3 py-3 font-semibold"
                            key={fieldName}
                            scope="col"
                          >
                            {fieldLabel}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--border)]">
                      {sheet.rows.map(([rowNumber, row]) => (
                        <tr key={rowNumber}>
                          <th className="px-3 py-4 align-top font-semibold" scope="row">
                            {rowNumber}
                          </th>
                          {sheet.columns.map(([fieldName, fieldLabel]) => {
                            const issue = row.issues.get(fieldName);
                            const displayedValue = displayedCellValue(
                              fieldName,
                              row.values.get(fieldName)?.value ?? null,
                            );
                            if (!issue) {
                              return (
                                <td className="max-w-80 px-3 py-4 align-top" key={fieldName}>
                                  <span className="break-words">
                                    {displayedValue === null || displayedValue === undefined
                                      ? "—"
                                      : displayedValue === ""
                                        ? "Cellule vide"
                                        : displayedValue}
                                  </span>
                                </td>
                              );
                            }
                            return (
                              <td
                                aria-label={`Erreur ligne ${rowNumber}, colonne ${fieldLabel}`}
                                className="max-w-80 bg-red-50 px-3 py-4 align-top text-red-950"
                                key={fieldName}
                                title={`${issue.user_title}. ${issue.required_correction}`}
                              >
                                <p className="font-semibold">
                                  {issue.submitted_value === ""
                                    ? "Cellule vide"
                                    : issue.submitted_value === null
                                      ? "Valeur non disponible"
                                      : `« ${displayedCellValue(fieldName, issue.submitted_value)} »`}
                                </p>
                                <p className="mt-1 text-xs font-semibold text-red-800">
                                  Erreur : {issue.user_title}
                                </p>
                                <p className="mt-2 text-xs">
                                  <span className="font-semibold">Attendu : </span>
                                  {issue.expected_format}
                                </p>
                                <details className="mt-2 text-xs text-red-800/80">
                                  <summary className="cursor-pointer font-semibold">
                                    Détails techniques
                                  </summary>
                                  <p className="mt-1">Code : {issue.code}</p>
                                  <p className="mt-1">{issue.message}</p>
                                </details>
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
