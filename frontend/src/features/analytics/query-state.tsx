import { ApiError } from "@/lib/api/client";

import { DataState } from "@/components/ui/data-state";

export function QueryErrorState({ error, label = "analytics" }: { error: Error; label?: string }) {
  const unauthorized = error instanceof ApiError && (error.status === 401 || error.status === 403);
  return (
    <DataState
      title={unauthorized ? "Sign-in is required" : `${label} are unavailable`}
      tone="error"
    >
      {unauthorized
        ? "This view contains protected operational data. Authenticate with a permitted account and retry."
        : `${error.message} No KPI has been calculated in the browser as a fallback.`}
    </DataState>
  );
}
