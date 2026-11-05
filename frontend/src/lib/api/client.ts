export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly body?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export type QueryValue = string | number | boolean | null | undefined;

let accessToken: string | null = null;
let refreshPromise: Promise<string | null> | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

function apiBaseUrl() {
  return (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api").replace(/\/$/, "");
}

export function apiUrl(path: string, query?: Record<string, QueryValue>) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const url = new URL(`${apiBaseUrl()}${normalizedPath}`);
  if (query) {
    Object.entries(query).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, String(value));
      }
    });
  }
  return url.toString();
}

function errorMessage(body: unknown, status: number) {
  if (typeof body === "object" && body !== null) {
    const detail = Reflect.get(body, "detail");
    if (typeof detail === "string") return detail;
    const file = Reflect.get(body, "file");
    if (typeof file === "string") return file;
    if (Array.isArray(file) && typeof file[0] === "string") return file[0];
  }
  return `The API request failed (${status}).`;
}

async function refreshAccessToken() {
  if (!refreshPromise) {
    refreshPromise = fetch(apiUrl("/auth/refresh/"), {
      method: "POST",
      credentials: "include",
      headers: { Accept: "application/json" },
    })
      .then(async (response) => {
        if (!response.ok) return null;
        const body = (await response.json()) as { access: string };
        accessToken = body.access;
        return body.access;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit & { query?: Record<string, QueryValue>; skipAuthRefresh?: boolean } = {},
): Promise<T> {
  const { query, headers, skipAuthRefresh = false, ...init } = options;
  const requestHeaders = new Headers(headers);
  requestHeaders.set("Accept", "application/json");
  if (accessToken && !requestHeaders.has("Authorization")) {
    requestHeaders.set("Authorization", `Bearer ${accessToken}`);
  }
  const request = () =>
    fetch(apiUrl(path, query), {
      ...init,
      credentials: "include",
      headers: requestHeaders,
    });
  let response = await request();
  if (response.status === 401 && !skipAuthRefresh && !path.startsWith("/auth/")) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      requestHeaders.set("Authorization", `Bearer ${refreshed}`);
      response = await request();
    }
  }

  const contentType = response.headers.get("content-type") ?? "";
  let body: unknown;
  if (contentType.includes("application/json")) {
    body = await response.json();
  } else {
    body = await response.text();
  }

  if (!response.ok) throw new ApiError(errorMessage(body, response.status), response.status, body);
  return body as T;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
