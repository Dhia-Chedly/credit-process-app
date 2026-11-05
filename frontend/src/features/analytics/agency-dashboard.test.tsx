import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AgencyDashboard } from "./agency-dashboard";

vi.mock("next/navigation", () => ({
  usePathname: () => "/agencies",
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

describe("AgencyDashboard", () => {
  it("shows agency outcomes in descending volume order alongside the positioning chart", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        if (String(input).includes("/metadata/")) {
          return Promise.resolve(response({ agencies: [], employees: { ca: [], gp: [] } }));
        }
        return Promise.resolve(
          response({
            results: [
              {
                agency_name: "Agence basse",
                total_requests: 4,
                funded_requests: 1,
                rejected_requests: 1,
                open_or_unknown_requests: 2,
                financing_rate: 25,
                average_processing_days: 8,
              },
              {
                agency_name: "Agence haute",
                total_requests: 12,
                funded_requests: 6,
                rejected_requests: 2,
                open_or_unknown_requests: 4,
                financing_rate: 50,
                average_processing_days: 12,
              },
            ],
          }),
        );
      }),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <AgencyDashboard />
      </QueryClientProvider>,
    );

    expect(
      screen.queryByText("Résumé accessible — Volume et résultats par agence"),
    ).not.toBeInTheDocument();
    expect(await screen.findByText("Volume et résultats par agence")).toBeVisible();
    expect(await screen.findByText("Positionnement des agences")).toBeVisible();
  });
});
