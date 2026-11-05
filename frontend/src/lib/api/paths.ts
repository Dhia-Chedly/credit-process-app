export type DashboardEndpoint =
  | "activities"
  | "agencies"
  | "delays"
  | "employees"
  | "metadata"
  | "overview"
  | "pipeline"
  | "products-requests"
  | "rejections";

export type DashboardResultsEndpoint = Exclude<
  DashboardEndpoint,
  "delays" | "metadata" | "overview"
>;

function resourceDetail(collection: string, id: string) {
  return `/${collection}/${encodeURIComponent(id)}/`;
}

export const apiPaths = {
  assistantMessages: "/assistant/messages/",
  creditRequest: (id: string) => resourceDetail("credit-requests", id),
  creditRequests: "/credit-requests/",
  dashboard: (endpoint: DashboardEndpoint) => `/dashboard/${endpoint}/`,
  importBatch: (id: string) => resourceDetail("import-batches", id),
  importBatchIssues: (id: string) => `${resourceDetail("import-batches", id)}issues/`,
  importBatchRetry: (id: string) => `${resourceDetail("import-batches", id)}retry/`,
  importBatches: "/import-batches/",
  register: "/auth/register/",
  login: "/auth/login/",
  logout: "/auth/logout/",
  me: "/me/",
  referenceAgencies: "/reference-data/agencies/",
  referenceAgency: (id: string) => resourceDetail("reference-data/agencies", id),
  referenceData: "/reference-data/",
  referenceEmployees: "/reference-data/employees/",
  referenceEmployee: (role: "ca" | "gp", id: string) =>
    `/reference-data/employees/${role}/${encodeURIComponent(id)}/`,
  referenceDimension: (kind: string, id?: string) =>
    id === undefined
      ? `/reference-data/dimensions/${encodeURIComponent(kind)}/`
      : `/reference-data/dimensions/${encodeURIComponent(kind)}/${encodeURIComponent(id)}/`,
} as const;
