import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ActivityDashboard } from "./activity-dashboard";

vi.mock("next/navigation", () => ({
  usePathname: () => "/activities",
  useRouter: () => ({ replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("echarts-for-react", () => ({ default: () => <div data-testid="chart-canvas" /> }));

function response(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("ActivityDashboard", () => {
  it("keeps raw activity labels out of the governed visual dashboard", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        if (String(input).includes("/metadata/")) {
          return Promise.resolve(response({ agencies: [], intervals: [] }));
        }
        return Promise.resolve(
          response({
            completeness: { provisional: false, limitations: [] },
            results: [
              {
                activity_label: "Agriculture",
                activity_source: "controlled",
                agency_name: "Agency A",
                total_requests: 8,
                funded_requests: 3,
              },
              {
                activity_label: "Unresolved workbook label",
                activity_source: "raw_source_label",
                agency_name: "Agency A",
                total_requests: 5,
                funded_requests: 1,
              },
            ],
          }),
        );
      }),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <ActivityDashboard />
      </QueryClientProvider>,
    );

    expect(await screen.findByText("Résultats par activité")).toBeInTheDocument();
    expect(
      screen.queryByText("Résumé accessible — Résultats par activité"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("Résumé accessible — Montant demandé par activité"),
    ).not.toBeInTheDocument();

    expect(screen.queryByText("Unresolved workbook label")).not.toBeInTheDocument();
  });
});
