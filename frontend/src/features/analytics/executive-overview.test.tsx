import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ExecutiveOverview } from "./executive-overview";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
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

describe("ExecutiveOverview", () => {
  it("displays backend summary values and its provisional limitation", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        if (String(input).includes("/metadata/")) {
          return Promise.resolve(response({ agencies: [], intervals: [] }));
        }
        return Promise.resolve(
          response({
            filters: { grain: "request_month" },
            completeness: {
              provisional: true,
              limitations: [
                { code: "missing_amounts", message: "Disbursed amounts are incomplete." },
              ],
            },
            summary: {
              total_requests: 100,
              funded_requests: 40,
              nonfunded_requests: 60,
              matched_requests: 45,
              rejected_requests: 10,
              open_or_unknown_requests: 50,
              financing_rate: 40,
              average_processing_days: 12.5,
              delay_sample_size: 32,
            },
          }),
        );
      }),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <ExecutiveOverview />
      </QueryClientProvider>,
    );

    const metrics = await screen.findByLabelText("Indicateurs clés");
    expect(within(metrics).getByText("100")).toBeVisible();
    expect(within(metrics).getByText("40")).toBeVisible();
    expect(within(metrics).getByText("10")).toBeVisible();
    expect(within(metrics).queryByText("60")).not.toBeInTheDocument();
    expect(await screen.findByText("Résultat des demandes")).toBeVisible();
    expect(screen.queryByText("Résumé accessible — Résultat des demandes")).not.toBeInTheDocument();
    expect(await screen.findByTestId("chart-canvas")).toBeInTheDocument();
  });
});
