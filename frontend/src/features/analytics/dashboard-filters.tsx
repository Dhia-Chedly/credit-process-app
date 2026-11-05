"use client";

import { RotateCcw, X } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { useMetadata } from "@/features/analytics/queries";

const FILTER_KEYS = ["date_from", "date_to", "agency", "ca", "gp"] as const;

function isFallbackEmployee(displayName: string) {
  return displayName.trim().toLocaleLowerCase("fr-FR") === "inconnu";
}

function monthStart(value: Date) {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-01`;
}

function datePreset(searchParams: URLSearchParams) {
  const from = searchParams.get("date_from");
  const to = searchParams.get("date_to");
  if (!from && !to) return "rolling";
  const now = new Date();
  const currentMonth = monthStart(new Date(now.getFullYear(), now.getMonth(), 1));
  const previousMonth = monthStart(new Date(now.getFullYear(), now.getMonth() - 1, 1));
  const quarterStart = monthStart(
    new Date(now.getFullYear(), Math.floor(now.getMonth() / 3) * 3, 1),
  );
  const yearStart = monthStart(new Date(now.getFullYear(), 0, 1));
  if (from === currentMonth && to === currentMonth) return "month";
  if (from === previousMonth && to === previousMonth) return "previous";
  if (from === quarterStart && to === currentMonth) return "quarter";
  if (from === yearStart && to === currentMonth) return "year";
  return "custom";
}

export function DashboardFilters({
  showEmployeeFilters = true,
  showAgencyFilter = true,
}: {
  showEmployeeFilters?: boolean;
  showAgencyFilter?: boolean;
}) {
  const metadata = useMetadata();
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [customDates, setCustomDates] = useState(datePreset(searchParams) === "custom");
  const [customFrom, setCustomFrom] = useState(searchParams.get("date_from")?.slice(0, 7) ?? "");
  const [customTo, setCustomTo] = useState(searchParams.get("date_to")?.slice(0, 7) ?? "");
  const [customDateError, setCustomDateError] = useState("");
  const [draftAgencyIds, setDraftAgencyIds] = useState<string[] | null>(null);
  const agencyDetailsRef = useRef<HTMLDetailsElement>(null);

  function navigate(next: URLSearchParams) {
    const query = next.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  }

  function update(key: string, value: string) {
    const next = new URLSearchParams(searchParams.toString());
    if (value) next.set(key, value);
    else next.delete(key);
    navigate(next);
  }

  function updateAgencies(value: string[]) {
    const next = new URLSearchParams(searchParams.toString());
    if (value.length > 0) next.set("agency", value.join(","));
    else next.delete("agency");
    next.delete("ca");
    next.delete("gp");
    navigate(next);
  }

  function chooseDatePreset(value: string) {
    if (value === "custom") {
      setCustomDates(true);
      const next = new URLSearchParams(searchParams.toString());
      if (!next.get("date_from") || !next.get("date_to")) {
        const now = new Date();
        const from = monthStart(new Date(now.getFullYear(), now.getMonth() - 11, 1)).slice(0, 7);
        const to = monthStart(new Date(now.getFullYear(), now.getMonth(), 1)).slice(0, 7);
        next.set("date_from", `${from}-01`);
        next.set("date_to", `${to}-01`);
        setCustomFrom(from);
        setCustomTo(to);
      }
      setCustomDateError("");
      navigate(next);
      return;
    }
    setCustomDates(false);
    const now = new Date();
    const next = new URLSearchParams(searchParams.toString());
    if (value === "rolling") {
      next.delete("date_from");
      next.delete("date_to");
    } else {
      let start = new Date(now.getFullYear(), now.getMonth(), 1);
      let end = start;
      if (value === "previous") {
        start = new Date(now.getFullYear(), now.getMonth() - 1, 1);
        end = start;
      } else if (value === "quarter") {
        start = new Date(now.getFullYear(), Math.floor(now.getMonth() / 3) * 3, 1);
      } else if (value === "year") {
        start = new Date(now.getFullYear(), 0, 1);
      }
      next.set("date_from", monthStart(start));
      next.set("date_to", monthStart(end));
    }
    navigate(next);
  }

  function saveCustomRange(from: string, to: string) {
    const validMonth = /^\d{4}-(0[1-9]|1[0-2])$/;
    if (!validMonth.test(from) || !validMonth.test(to)) {
      setCustomDateError("Format de mois invalide.");
      return;
    }
    if (from > to) {
      setCustomDateError("Le mois de début doit précéder le mois de fin.");
      return;
    }
    setCustomDateError("");
    const next = new URLSearchParams(searchParams.toString());
    next.set("date_from", `${from}-01`);
    next.set("date_to", `${to}-01`);
    navigate(next);
  }

  function reset() {
    const next = new URLSearchParams(searchParams.toString());
    FILTER_KEYS.forEach((key) => next.delete(key));
    setCustomDates(false);
    navigate(next);
  }

  const agencyIds = (searchParams.get("agency") ?? "").split(",").filter(Boolean);
  const visibleAgencyIds = draftAgencyIds ?? agencyIds;
  const caId = searchParams.get("ca") ?? "";
  const gpId = searchParams.get("gp") ?? "";
  const agencies = metadata.data?.agencies ?? [];
  const caOptions = (metadata.data?.employees?.ca ?? []).filter(
    (employee) => !isFallbackEmployee(employee.display_name),
  );
  const gpOptions = (metadata.data?.employees?.gp ?? []).filter(
    (employee) => !isFallbackEmployee(employee.display_name),
  );
  const selectedAgencyNames = agencies
    .filter((item) => agencyIds.includes(item.id ?? item.agency_id ?? ""))
    .map((item) => item.name);
  const caName = caOptions.find((item) => item.id === caId)?.display_name;
  const gpName = gpOptions.find((item) => item.id === gpId)?.display_name;
  const activeFilters = [
    searchParams.get("date_from") || searchParams.get("date_to")
      ? {
          key: "date",
          label: `Date : ${searchParams.get("date_from")?.slice(0, 7) ?? "…"} → ${searchParams.get("date_to")?.slice(0, 7) ?? "…"}`,
        }
      : null,
    agencyIds.length > 0
      ? {
          key: "agency",
          label:
            agencyIds.length === 1
              ? `Agence : ${selectedAgencyNames[0] ?? "sélectionnée"}`
              : `Agences : ${agencyIds.length} sélectionnées`,
        }
      : null,
    showEmployeeFilters && caId ? { key: "ca", label: `CA : ${caName ?? "sélectionné"}` } : null,
    showEmployeeFilters && gpId ? { key: "gp", label: `GP : ${gpName ?? "sélectionné"}` } : null,
  ].filter((item): item is { key: string; label: string } => item !== null);

  function removeFilter(key: string) {
    const next = new URLSearchParams(searchParams.toString());
    if (key === "date") {
      next.delete("date_from");
      next.delete("date_to");
      setCustomDates(false);
    } else {
      next.delete(key);
    }
    navigate(next);
  }

  const controlClass =
    "min-h-11 min-w-0 rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-800 shadow-sm transition hover:border-emerald-300 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand)] disabled:opacity-55";

  return (
    <section
      aria-label="Filtres du tableau de bord"
      className="sticky top-20 z-20 mt-6 rounded-2xl border border-[var(--border)] bg-slate-50/95 p-3 shadow-sm backdrop-blur"
    >
      <div
        className={`grid gap-2 sm:grid-cols-2 ${
          showEmployeeFilters
            ? "xl:grid-cols-[1.15fr_1.2fr_1fr_1fr_auto]"
            : showAgencyFilter
              ? "xl:grid-cols-[1.2fr_1.2fr_auto]"
              : "xl:grid-cols-[1.2fr_auto]"
        }`}
      >
        <label className="relative flex items-center gap-2">
          <span className="sr-only">Période</span>
          <select
            className={`${controlClass} w-full`}
            onChange={(event) => chooseDatePreset(event.target.value)}
            value={customDates ? "custom" : datePreset(searchParams)}
          >
            <option value="rolling">12 derniers mois</option>
            <option value="month">Ce mois</option>
            <option value="previous">Mois précédent</option>
            <option value="quarter">Ce trimestre</option>
            <option value="year">Cette année</option>
            <option value="custom">Période personnalisée</option>
          </select>
        </label>

        {showEmployeeFilters && (
          <label className="relative flex items-center gap-2">
            <span className="sr-only">CA</span>
            <select
              className={`${controlClass} w-full`}
              disabled={metadata.isLoading || metadata.isError}
              onChange={(event) => update("ca", event.target.value)}
              value={caId}
            >
              <option value="">Tous les CA</option>
              {caOptions.map((employee) => (
                <option key={employee.id} value={employee.id}>
                  {employee.display_name}
                </option>
              ))}
            </select>
          </label>
        )}

        {showEmployeeFilters && (
          <label className="relative flex items-center gap-2">
            <span className="sr-only">GP</span>
            <select
              className={`${controlClass} w-full`}
              disabled={metadata.isLoading || metadata.isError}
              onChange={(event) => update("gp", event.target.value)}
              value={gpId}
            >
              <option value="">Tous les GP</option>
              {gpOptions.map((employee) => (
                <option key={employee.id} value={employee.id}>
                  {employee.display_name}
                </option>
              ))}
            </select>
          </label>
        )}

        {showAgencyFilter && (
          <details
            className="relative min-w-0"
            data-testid="agency-filter"
            onToggle={(event) => {
              if (event.currentTarget.open) setDraftAgencyIds(agencyIds);
              else setDraftAgencyIds(null);
            }}
            ref={agencyDetailsRef}
          >
            <summary
              className={`${controlClass} flex w-full cursor-pointer list-none items-center gap-2`}
            >
              {agencyIds.length === 0
                ? "Toutes les agences"
                : agencyIds.length === 1
                  ? (selectedAgencyNames[0] ?? "1 agence sélectionnée")
                  : `${agencyIds.length} agences sélectionnées`}
            </summary>
            <div className="absolute z-30 mt-2 max-h-72 w-full min-w-64 overflow-y-auto rounded-xl border border-slate-200 bg-white p-2 shadow-lg">
              {agencies.map((agency) => {
                const id = agency.id ?? agency.agency_id;
                if (!id) return null;
                const checked = visibleAgencyIds.includes(id);
                return (
                  <label
                    className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-2 text-sm hover:bg-slate-50"
                    key={id}
                  >
                    <input
                      checked={checked}
                      disabled={metadata.isLoading || metadata.isError}
                      onChange={() =>
                        setDraftAgencyIds(
                          checked
                            ? visibleAgencyIds.filter((agencyId) => agencyId !== id)
                            : [...visibleAgencyIds, id],
                        )
                      }
                      type="checkbox"
                    />
                    {agency.name}
                  </label>
                );
              })}
              <div className="sticky bottom-0 mt-2 border-t border-slate-100 bg-white pt-2">
                <Button
                  className="w-full"
                  disabled={metadata.isLoading || metadata.isError}
                  onClick={() => {
                    updateAgencies(visibleAgencyIds);
                    agencyDetailsRef.current?.removeAttribute("open");
                    setDraftAgencyIds(null);
                  }}
                  type="button"
                >
                  Appliquer la sélection
                </Button>
              </div>
            </div>
          </details>
        )}

        <Button disabled={activeFilters.length === 0} onClick={reset} variant="secondary">
          <RotateCcw aria-hidden="true" size={16} />
          Réinitialiser
        </Button>
      </div>

      {customDates && (
        <div className="mt-3 flex flex-wrap gap-3 rounded-xl border border-slate-200 bg-white p-3">
          <label className="grid gap-1 text-xs font-semibold text-[var(--muted)]">
            Du mois
            <input
              aria-invalid={Boolean(customDateError)}
              className={controlClass}
              maxLength={7}
              onBlur={() => saveCustomRange(customFrom, customTo)}
              onChange={(event) => {
                const value = event.target.value;
                setCustomFrom(value);
                if (/^\d{4}-(0[1-9]|1[0-2])$/.test(value)) saveCustomRange(value, customTo);
              }}
              placeholder="AAAA-MM"
              value={customFrom}
            />
          </label>
          <label className="grid gap-1 text-xs font-semibold text-[var(--muted)]">
            Au mois
            <input
              aria-invalid={Boolean(customDateError)}
              className={controlClass}
              maxLength={7}
              onBlur={() => saveCustomRange(customFrom, customTo)}
              onChange={(event) => {
                const value = event.target.value;
                setCustomTo(value);
                if (/^\d{4}-(0[1-9]|1[0-2])$/.test(value)) saveCustomRange(customFrom, value);
              }}
              placeholder="AAAA-MM"
              value={customTo}
            />
          </label>
          {customDateError && (
            <p className="w-full text-sm text-red-700" role="alert">
              {customDateError}
            </p>
          )}
        </div>
      )}

      {activeFilters.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-2" aria-label="Filtres actifs">
          {activeFilters.map((item) => (
            <button
              className="inline-flex min-h-8 items-center gap-1.5 rounded-full bg-emerald-50 px-3 text-xs font-semibold text-emerald-900 hover:bg-emerald-100"
              key={item.key}
              onClick={() => removeFilter(item.key)}
              type="button"
            >
              {item.label}
              <X aria-hidden="true" size={13} />
            </button>
          ))}
          {metadata.isFetching && <span className="text-xs text-[var(--muted)]">Mise à jour…</span>}
        </div>
      )}

      {metadata.isError && (
        <p className="mt-3 text-sm text-amber-800" role="status">
          Les options Agence, CA et GP sont temporairement indisponibles. Le filtre Date reste
          actif.
        </p>
      )}
    </section>
  );
}
