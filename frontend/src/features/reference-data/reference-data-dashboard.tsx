"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LoaderCircle, Mail, Search, Trash2, X } from "lucide-react";
import { type FormEvent, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/ui/data-state";
import { QueryErrorState } from "@/features/analytics/query-state";
import { apiFetch } from "@/lib/api/client";
import type {
  OperationalReferenceData,
  ReferenceAgency,
  ReferenceDimension,
  ReferenceEmployee,
} from "@/lib/api/contracts";
import { apiPaths } from "@/lib/api/paths";

const controlClass =
  "mt-2 min-h-11 w-full rounded-xl border border-[var(--border)] bg-white px-3 text-sm shadow-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand)]";

function normaliseSearch(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("fr-FR")
    .trim();
}

function isFallbackEmployee(employee: ReferenceEmployee) {
  return normaliseSearch(employee.name) === "inconnu";
}

function ReferenceList({
  title,
  employees,
  agenciesById,
  hasSearch,
  onSetActive,
  onSetEmail,
  removingId,
}: {
  title: string;
  employees: ReferenceEmployee[];
  agenciesById: Map<string, ReferenceAgency>;
  hasSearch: boolean;
  onSetActive: (employee: ReferenceEmployee, isActive: boolean) => void;
  onSetEmail: (employee: ReferenceEmployee) => void;
  removingId?: string;
}) {
  return (
    <section className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <h3 className="font-semibold">{title}</h3>
        <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">
          {employees.length}
        </span>
      </div>
      {employees.length === 0 ? (
        <p className="mt-4 text-sm text-[var(--muted)]">
          {hasSearch ? "Aucun résultat dans cette catégorie." : "Aucun collaborateur enregistré."}
        </p>
      ) : (
        <ul className="mt-4 divide-y divide-[var(--border)]">
          {employees.map((employee) => (
            <li className="flex items-center justify-between gap-3 py-3 text-sm" key={employee.id}>
              <div>
                <p className="font-medium">{employee.name}</p>
                <p className="mt-0.5 text-xs text-[var(--muted)]">
                  {agenciesById.get(employee.agency_id)?.name ?? "Agence inconnue"}
                </p>
                <p className="mt-0.5 text-xs text-[var(--muted)]">
                  {employee.email || "Email non renseigné"}
                </p>
              </div>
              <button
                aria-label={`Modifier l’email de ${employee.name}`}
                className="grid size-9 place-items-center rounded-lg text-[var(--brand)] hover:bg-emerald-50"
                onClick={() => onSetEmail(employee)}
                type="button"
              >
                <Mail aria-hidden size={16} />
              </button>
              {!isFallbackEmployee(employee) && (
                <button
                  aria-label={`${employee.is_active ? "Désactiver" : "Réactiver"} ${employee.name}`}
                  className="grid size-9 place-items-center rounded-lg text-red-700 hover:bg-red-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-700 disabled:opacity-50"
                  disabled={removingId === employee.id}
                  onClick={() => onSetActive(employee, !employee.is_active)}
                  type="button"
                >
                  {removingId === employee.id ? (
                    <LoaderCircle aria-hidden="true" className="animate-spin" size={16} />
                  ) : employee.is_active ? (
                    <Trash2 aria-hidden="true" size={16} />
                  ) : (
                    "Réactiver"
                  )}
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function DimensionList({
  items,
  kind,
  search,
  title,
  onCreate,
  onSetActive,
}: {
  items: ReferenceDimension[];
  kind: string;
  search: string;
  title: string;
  onCreate: (kind: string, name: string) => void;
  onSetActive: (kind: string, item: ReferenceDimension, isActive: boolean) => void;
}) {
  const [name, setName] = useState("");
  const [expanded, setExpanded] = useState(false);
  const visible = items.filter((item) =>
    normaliseSearch(item.name).includes(normaliseSearch(search)),
  );
  return (
    <section className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <h3 className="font-semibold">{title}</h3>
        <button
          aria-expanded={expanded}
          className="text-xs font-semibold text-[var(--brand)] hover:underline"
          onClick={() => setExpanded((value) => !value)}
          type="button"
        >
          {expanded ? "Réduire" : "Afficher"}
        </button>
      </div>
      <form
        className="mt-4 flex gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          if (!name.trim()) return;
          onCreate(kind, name.trim());
          setName("");
        }}
      >
        <input
          aria-label={`Ajouter ${title}`}
          className="min-h-10 min-w-0 flex-1 rounded-lg border border-[var(--border)] px-3 text-sm"
          onChange={(event) => setName(event.target.value)}
          placeholder="Ajouter une valeur"
          value={name}
        />
        <Button type="submit" variant="secondary">
          Ajouter
        </Button>
      </form>
      {expanded && (
        <ul className="mt-4 divide-y divide-[var(--border)]">
          {visible.map((item) => (
            <li className="flex items-center justify-between gap-3 py-3 text-sm" key={item.id}>
              <div>
                <p className="font-medium">{item.name}</p>
                <p className="text-xs text-[var(--muted)]">
                  {item.is_active ? "Actif" : "Inactif"} · {item.usage_count} dossier
                  {item.usage_count === 1 ? "" : "s"} historique{item.usage_count === 1 ? "" : "s"}
                </p>
              </div>
              <Button
                onClick={() => onSetActive(kind, item, !item.is_active)}
                type="button"
                variant={item.is_active ? "secondary" : "primary"}
              >
                {item.is_active ? "Désactiver" : "Réactiver"}
              </Button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function ReferenceDataDashboard() {
  const queryClient = useQueryClient();
  const [agencyName, setAgencyName] = useState("");
  const [agencyCode, setAgencyCode] = useState("");
  const [employeeName, setEmployeeName] = useState("");
  const [employeeEmail, setEmployeeEmail] = useState("");
  const [employeeAgencyId, setEmployeeAgencyId] = useState("");
  const [employeeRole, setEmployeeRole] = useState<"ca" | "gp">("ca");
  const [referenceSearch, setReferenceSearch] = useState("");
  const referenceData = useQuery({
    queryKey: ["reference-data"],
    queryFn: ({ signal }) => apiFetch<OperationalReferenceData>(apiPaths.referenceData, { signal }),
  });
  const invalidate = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["reference-data"] }),
      queryClient.invalidateQueries({ queryKey: ["analytics"] }),
    ]);
  };
  const createAgency = useMutation({
    mutationFn: ({ name, code }: { name: string; code: string }) =>
      apiFetch<ReferenceAgency>(apiPaths.referenceAgencies, {
        body: JSON.stringify({ name, code }),
        headers: { "Content-Type": "application/json" },
        method: "POST",
      }),
    onSuccess: async () => {
      setAgencyName("");
      setAgencyCode("");
      await invalidate();
    },
  });
  const createEmployee = useMutation({
    mutationFn: ({
      name,
      agency_id,
      role,
      email,
    }: {
      name: string;
      agency_id: string;
      role: "ca" | "gp";
      email: string;
    }) =>
      apiFetch<ReferenceEmployee>(apiPaths.referenceEmployees, {
        body: JSON.stringify({ name, agency_id, role, email }),
        headers: { "Content-Type": "application/json" },
        method: "POST",
      }),
    onSuccess: async () => {
      setEmployeeName("");
      setEmployeeEmail("");
      await invalidate();
    },
  });
  const createDimension = useMutation({
    mutationFn: ({ kind, name }: { kind: string; name: string }) =>
      apiFetch(apiPaths.referenceDimension(kind), {
        body: JSON.stringify({ name }),
        headers: { "Content-Type": "application/json" },
        method: "POST",
      }),
    onSuccess: invalidate,
  });
  const setDimensionActive = useMutation({
    mutationFn: ({ kind, id, is_active }: { kind: string; id: string; is_active: boolean }) =>
      apiFetch(apiPaths.referenceDimension(kind, id), {
        body: JSON.stringify({ is_active }),
        headers: { "Content-Type": "application/json" },
        method: "PATCH",
      }),
    onSuccess: invalidate,
  });
  const setAgencyActive = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      apiFetch(apiPaths.referenceAgency(id), {
        body: JSON.stringify({ is_active }),
        headers: { "Content-Type": "application/json" },
        method: "PATCH",
      }),
    onSuccess: invalidate,
  });
  const setEmployeeActive = useMutation({
    mutationFn: ({ role, id, is_active }: { role: "ca" | "gp"; id: string; is_active: boolean }) =>
      apiFetch(apiPaths.referenceEmployee(role, id), {
        body: JSON.stringify({ is_active }),
        headers: { "Content-Type": "application/json" },
        method: "PATCH",
      }),
    onSuccess: invalidate,
  });
  const updateEmployeeEmail = useMutation({
    mutationFn: ({ role, id, email }: { role: "ca" | "gp"; id: string; email: string }) =>
      apiFetch(apiPaths.referenceEmployee(role, id), {
        body: JSON.stringify({ email }),
        headers: { "Content-Type": "application/json" },
        method: "PATCH",
      }),
    onSuccess: invalidate,
  });
  const agenciesById = useMemo(
    () => new Map((referenceData.data?.agencies ?? []).map((agency) => [agency.id, agency])),
    [referenceData.data?.agencies],
  );
  const filteredReferences = useMemo(() => {
    const query = normaliseSearch(referenceSearch);
    const agencies = referenceData.data?.agencies ?? [];
    const employees = referenceData.data?.employees ?? { ca: [], gp: [] };
    const visibleEmployees = {
      ca: employees.ca.filter((employee) => !isFallbackEmployee(employee)),
      gp: employees.gp.filter((employee) => !isFallbackEmployee(employee)),
    };
    if (!query) return { agencies: [], ca: [], gp: [] };
    const matches = (value: string) => normaliseSearch(value).includes(query);
    const employeeMatches = (employee: ReferenceEmployee) =>
      matches(employee.name) || matches(agenciesById.get(employee.agency_id)?.name ?? "");
    return {
      agencies: agencies.filter((agency) => matches(agency.name)),
      ca: visibleEmployees.ca.filter(employeeMatches),
      gp: visibleEmployees.gp.filter(employeeMatches),
    };
  }, [agenciesById, referenceData.data, referenceSearch]);
  const matchingReferenceCount =
    filteredReferences.agencies.length +
    filteredReferences.ca.length +
    filteredReferences.gp.length;

  function submitAgency(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    createAgency.mutate({ name: agencyName, code: agencyCode });
  }

  function submitEmployee(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    createEmployee.mutate({
      name: employeeName,
      agency_id: employeeAgencyId,
      role: employeeRole,
      email: employeeEmail,
    });
  }

  function confirmStatusChange(name: string, usageCount: number, deactivate: boolean) {
    if (!deactivate) return true;
    return window.confirm(
      `Désactiver « ${name} » ? ${usageCount} dossier${usageCount === 1 ? "" : "s"} historique${usageCount === 1 ? "" : "s"} reste${usageCount === 1 ? "" : "nt"} visible${usageCount === 1 ? "" : "s"}. Les nouveaux imports utilisant cette valeur seront rejetés.`,
    );
  }

  return (
    <div>
      <div className="grid gap-6 xl:grid-cols-2">
        <form
          className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm"
          onSubmit={submitAgency}
        >
          <h2 className="font-semibold">Ajouter une agence</h2>
          <label className="mt-5 block text-sm font-semibold" htmlFor="agency-name">
            Nom de l’agence
          </label>
          <input
            className={controlClass}
            disabled={createAgency.isPending}
            id="agency-name"
            maxLength={120}
            onChange={(event) => setAgencyName(event.target.value)}
            required
            value={agencyName}
          />
          <label className="mt-4 block text-sm font-semibold" htmlFor="agency-code">
            Code agence
          </label>
          <input
            className={controlClass}
            disabled={createAgency.isPending}
            id="agency-code"
            inputMode="numeric"
            maxLength={4}
            onChange={(event) => setAgencyCode(event.target.value.replace(/\D/g, ""))}
            pattern="[0-9]{4}"
            placeholder="Ex. 1234"
            required
            value={agencyCode}
          />
          {createAgency.error && (
            <p className="mt-3 text-sm text-red-700" role="alert">
              {createAgency.error.message}
            </p>
          )}
          <Button className="mt-5" disabled={createAgency.isPending} type="submit">
            {createAgency.isPending && (
              <LoaderCircle aria-hidden="true" className="animate-spin" size={17} />
            )}
            Ajouter
          </Button>
        </form>

        <form
          className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm"
          onSubmit={submitEmployee}
        >
          <h2 className="font-semibold">Ajouter un CA/CAA ou un GP</h2>
          <label className="mt-5 block text-sm font-semibold" htmlFor="employee-name">
            Nom complet
          </label>
          <input
            className={controlClass}
            disabled={createEmployee.isPending}
            id="employee-name"
            maxLength={160}
            onChange={(event) => setEmployeeName(event.target.value)}
            required
            value={employeeName}
          />
          <label className="mt-4 block text-sm font-semibold" htmlFor="employee-email">
            Email professionnel
          </label>
          <input
            className={controlClass}
            disabled={createEmployee.isPending}
            id="employee-email"
            onChange={(event) => setEmployeeEmail(event.target.value)}
            placeholder="name@example.com"
            type="email"
            value={employeeEmail}
          />
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <label className="block text-sm font-semibold" htmlFor="employee-role">
              Rôle
              <select
                className={controlClass}
                disabled={createEmployee.isPending}
                id="employee-role"
                onChange={(event) => setEmployeeRole(event.target.value as "ca" | "gp")}
                value={employeeRole}
              >
                <option value="ca">CA / CAA</option>
                <option value="gp">GP</option>
              </select>
            </label>
            <label className="block text-sm font-semibold" htmlFor="employee-agency">
              Agence
              <select
                className={controlClass}
                disabled={createEmployee.isPending || referenceData.isLoading}
                id="employee-agency"
                onChange={(event) => setEmployeeAgencyId(event.target.value)}
                required
                value={employeeAgencyId}
              >
                <option value="">Sélectionner une agence</option>
                {(referenceData.data?.agencies ?? [])
                  .filter((agency) => agency.is_active)
                  .map((agency) => (
                    <option key={agency.id} value={agency.id}>
                      {agency.name}
                    </option>
                  ))}
              </select>
            </label>
          </div>
          {createEmployee.error && (
            <p className="mt-3 text-sm text-red-700" role="alert">
              {createEmployee.error.message}
            </p>
          )}
          <Button
            className="mt-5"
            disabled={createEmployee.isPending || !employeeAgencyId}
            type="submit"
          >
            {createEmployee.isPending && (
              <LoaderCircle aria-hidden="true" className="animate-spin" size={17} />
            )}
            Ajouter
          </Button>
        </form>
      </div>

      <section className="mt-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-lg font-semibold">Référentiels actuels</h2>
          </div>
          <label className="relative block sm:w-96" htmlFor="reference-search">
            <Search
              aria-hidden="true"
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted)]"
              size={18}
            />
            <span className="sr-only">Rechercher dans les référentiels</span>
            <input
              className="min-h-11 w-full rounded-xl border border-[var(--border)] bg-white py-2 pl-10 pr-10 text-sm shadow-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand)]"
              id="reference-search"
              onChange={(event) => setReferenceSearch(event.target.value)}
              placeholder="Rechercher une agence ou un nom…"
              type="search"
              value={referenceSearch}
            />
            {referenceSearch && (
              <button
                aria-label="Effacer la recherche"
                className="absolute right-2 top-1/2 grid size-8 -translate-y-1/2 place-items-center rounded-lg text-[var(--muted)] hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand)]"
                onClick={() => setReferenceSearch("")}
                type="button"
              >
                <X aria-hidden="true" size={17} />
              </button>
            )}
          </label>
        </div>
        {referenceData.isLoading ? (
          <div className="mt-4">
            <LoadingState label="Chargement des référentiels…" />
          </div>
        ) : referenceData.isError ? (
          <div className="mt-4">
            <QueryErrorState error={referenceData.error} label="Référentiels opérationnels" />
          </div>
        ) : (
          <>
            <>
              {referenceSearch.trim() ? (
                <>
                  <p className="mt-4 text-sm text-[var(--muted)]" role="status">
                    {matchingReferenceCount} résultat{matchingReferenceCount === 1 ? "" : "s"} pour
                    « {referenceSearch} »
                  </p>
                  <div className="mt-4 grid gap-6 xl:grid-cols-3">
                    <section className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm">
                      <div className="flex items-center justify-between gap-3">
                        <h3 className="font-semibold">Agences</h3>
                        <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">
                          {filteredReferences.agencies.length}
                        </span>
                      </div>
                      {filteredReferences.agencies.length === 0 ? (
                        <p className="mt-4 text-sm text-[var(--muted)]">
                          Aucun résultat dans cette catégorie.
                        </p>
                      ) : (
                        <ul className="mt-4 divide-y divide-[var(--border)]">
                          {filteredReferences.agencies.map((agency) => (
                            <li
                              className="flex items-center justify-between gap-3 py-3 text-sm"
                              key={agency.id}
                            >
                              <span className="font-medium">{agency.name}</span>
                              <button
                                aria-label={`${agency.is_active ? "Désactiver" : "Réactiver"} ${agency.name}`}
                                className="grid size-9 place-items-center rounded-lg text-red-700 hover:bg-red-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-700 disabled:opacity-50"
                                disabled={setAgencyActive.isPending}
                                onClick={() => {
                                  const isActive = !agency.is_active;
                                  if (
                                    confirmStatusChange(
                                      agency.name,
                                      agency.usage_count ?? 0,
                                      !isActive,
                                    )
                                  ) {
                                    setAgencyActive.mutate({ id: agency.id, is_active: isActive });
                                  }
                                }}
                                type="button"
                              >
                                {setAgencyActive.isPending &&
                                setAgencyActive.variables?.id === agency.id ? (
                                  <LoaderCircle
                                    aria-hidden="true"
                                    className="animate-spin"
                                    size={16}
                                  />
                                ) : agency.is_active ? (
                                  <Trash2 aria-hidden="true" size={16} />
                                ) : (
                                  "Réactiver"
                                )}
                              </button>
                            </li>
                          ))}
                        </ul>
                      )}
                    </section>
                    <ReferenceList
                      agenciesById={agenciesById}
                      employees={filteredReferences.ca}
                      hasSearch
                      onSetActive={(employee, is_active) => {
                        if (
                          confirmStatusChange(employee.name, employee.usage_count ?? 0, !is_active)
                        ) {
                          setEmployeeActive.mutate({ role: "ca", id: employee.id, is_active });
                        }
                      }}
                      onSetEmail={(employee) => {
                        const email = window.prompt("Email professionnel", employee.email);
                        if (email !== null)
                          updateEmployeeEmail.mutate({ role: "ca", id: employee.id, email });
                      }}
                      removingId={
                        !setEmployeeActive.isPending || setEmployeeActive.variables?.role !== "ca"
                          ? undefined
                          : filteredReferences.ca.find(
                              (employee) => employee.id === setEmployeeActive.variables?.id,
                            )?.id
                      }
                      title="CA / CAA"
                    />
                    <ReferenceList
                      agenciesById={agenciesById}
                      employees={filteredReferences.gp}
                      hasSearch
                      onSetActive={(employee, is_active) => {
                        if (
                          confirmStatusChange(employee.name, employee.usage_count ?? 0, !is_active)
                        ) {
                          setEmployeeActive.mutate({ role: "gp", id: employee.id, is_active });
                        }
                      }}
                      onSetEmail={(employee) => {
                        const email = window.prompt("Email professionnel", employee.email);
                        if (email !== null)
                          updateEmployeeEmail.mutate({ role: "gp", id: employee.id, email });
                      }}
                      removingId={
                        !setEmployeeActive.isPending || setEmployeeActive.variables?.role !== "gp"
                          ? undefined
                          : filteredReferences.gp.find(
                              (employee) => employee.id === setEmployeeActive.variables?.id,
                            )?.id
                      }
                      title="GP"
                    />
                  </div>
                </>
              ) : null}
            </>
          </>
        )}
      </section>
      {!referenceData.isLoading && !referenceData.isError && (
        <section className="mt-8">
          <div>
            <h2 className="text-lg font-semibold">Valeurs contrôlées</h2>
          </div>
          <div className="mt-4 grid gap-5 xl:grid-cols-2">
            <DimensionList
              items={referenceData.data?.dimensions["credit-types"] ?? []}
              kind="credit-types"
              search={referenceSearch}
              title="Types de crédit"
              onCreate={(kind, name) => createDimension.mutate({ kind, name })}
              onSetActive={(kind, item, is_active) =>
                setDimensionActive.mutate({ kind, id: item.id, is_active })
              }
            />
            <DimensionList
              items={referenceData.data?.dimensions.activities ?? []}
              kind="activities"
              search={referenceSearch}
              title="Activités"
              onCreate={(kind, name) => createDimension.mutate({ kind, name })}
              onSetActive={(kind, item, is_active) =>
                setDimensionActive.mutate({ kind, id: item.id, is_active })
              }
            />
            <DimensionList
              items={referenceData.data?.dimensions["request-types"] ?? []}
              kind="request-types"
              search={referenceSearch}
              title="Types de demande"
              onCreate={(kind, name) => createDimension.mutate({ kind, name })}
              onSetActive={(kind, item, is_active) =>
                setDimensionActive.mutate({ kind, id: item.id, is_active })
              }
            />
            <DimensionList
              items={referenceData.data?.dimensions["rejection-reasons"] ?? []}
              kind="rejection-reasons"
              search={referenceSearch}
              title="Motifs de rejet"
              onCreate={(kind, name) => createDimension.mutate({ kind, name })}
              onSetActive={(kind, item, is_active) =>
                setDimensionActive.mutate({ kind, id: item.id, is_active })
              }
            />
          </div>
        </section>
      )}
    </div>
  );
}
