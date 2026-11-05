import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApplicationsDashboard } from "./applications-dashboard";

vi.mock("next/navigation", () => ({
  usePathname: () => "/applications",
  useRouter: () => ({ replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("ApplicationsDashboard", () => {
  it("uses public IDs and shows only the requested dossier fields", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify({
              count: 2,
              next: null,
              previous: null,
              results: [
                {
                  id: "fact-1",
                  public_id: "public-1",
                  agency: { id: "agency-1", code: "A1", name: "Agency One" },
                  display_reference: "••••1111",
                  amount: "1000.000",
                  credit_type: "Working capital",
                  request_date: "2026-08-01",
                  gp_name: "GP de test",
                  status: {
                    id: "status-1",
                    code: "awaiting_visit",
                    label: "En attente de visite",
                    pipeline_stage: "waiting_visit",
                    is_terminal: false,
                    is_financed: false,
                    is_rejected: false,
                  },
                  source_completeness: {
                    matched: true,
                  },
                  updated_at: "2026-08-10T00:00:00Z",
                },
                {
                  id: "fact-2",
                  public_id: "public-2",
                  agency: { id: "agency-1", code: "A1", name: "Agency One" },
                  display_reference: "••••2222",
                  amount: null,
                  credit_type: "",
                  request_date: null,
                  gp_name: "",
                  status: null,
                  source_completeness: {
                    matched: false,
                  },
                  updated_at: "2026-08-10T00:00:00Z",
                },
              ],
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        ),
      ),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <ApplicationsDashboard />
      </QueryClientProvider>,
    );

    expect(await screen.findByRole("link", { name: "••••1111" })).toHaveAttribute(
      "href",
      "/applications/public-1",
    );
    expect(screen.getByText("En attente de visite")).toBeVisible();
    expect(screen.getByRole("combobox", { name: "Période" })).toBeVisible();
    expect(screen.queryByText("Agences")).not.toBeInTheDocument();
    expect(screen.queryByText("CA/CAA")).not.toBeInTheDocument();
    expect(screen.queryByText("GP")).not.toBeInTheDocument();
    expect(screen.queryByText("État des sources")).not.toBeInTheDocument();
    expect(screen.queryByText("Gestionnaire de portefeuille (GP)")).not.toBeInTheDocument();
    expect(screen.queryByText("Dernière consolidation")).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Agence" })).not.toBeInTheDocument();
    expect(screen.queryByText("Trier les fiches")).not.toBeInTheDocument();
  });
});
