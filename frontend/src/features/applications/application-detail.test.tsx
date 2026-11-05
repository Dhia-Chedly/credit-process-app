import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApplicationDetail } from "./application-detail";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("ApplicationDetail", () => {
  it("renders only the dossier chronology", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify({
              id: "app-1",
              agency: { id: "agency-1", code: "A1", name: "Agency One" },
              display_reference: "••••1234",
              amount: "2000.000",
              amount_disbursed: null,
              credit_type: "Credit",
              request_type: "New",
              activity_category: "",
              request_date: "2026-03-01",
              disbursement_date: null,
              rejection_date: null,
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
              history_scope: "current_provenance",
              source_history: [
                {
                  id: "source-1",
                  batch_id: "batch-1",
                  original_filename: "TB1.xlsx",
                  source_kind: "tb1",
                  reporting_period: "2026-03-01",
                  sheet_name: "Sheet1",
                  source_row: 4,
                  row_status: "committed",
                  match_method: "created",
                  match_score: null,
                  source_class_authoritative: false,
                  controls_current_state: true,
                  created_at: "2026-03-02T00:00:00Z",
                },
              ],
              updated_at: "2026-03-02T00:00:00Z",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        ),
      ),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <ApplicationDetail applicationId="app-1" />
      </QueryClientProvider>,
    );

    expect(await screen.findByRole("heading", { name: "Chronologie du dossier" })).toBeVisible();
    expect(screen.getByText("01 mars 2026")).toBeVisible();
    expect(screen.getByText("Étape en cours")).toBeVisible();
    expect(screen.getByText(/GP de test/)).toBeVisible();
    expect(screen.queryByText("État consolidé actuel")).not.toBeInTheDocument();
    expect(screen.queryByText("Traçabilité des imports")).not.toBeInTheDocument();
    expect(screen.queryByText("Informations client protégées")).not.toBeInTheDocument();
  });

  it("does not show protected fields when they are returned", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify({
              id: "app-2",
              public_id: "app-2",
              agency: { id: "agency-1", code: "A1", name: "Agency One" },
              display_reference: "••••5678",
              reference: "FULL-5678",
              client_name: "Protected Client",
              client_identifier: "CLIENT-1",
              phone: "+000000000",
              address: "Protected address",
              comments: "Protected comment",
              amount: "3000.000",
              amount_disbursed: null,
              credit_type: "Credit",
              request_type: "New",
              activity_category: "Trade",
              request_date: "2026-03-01",
              disbursement_date: null,
              rejection_date: null,
              status: null,
              source_completeness: {
                matched: false,
              },
              source_history: [],
              updated_at: "2026-03-02T00:00:00Z",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        ),
      ),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <ApplicationDetail applicationId="app-2" />
      </QueryClientProvider>,
    );

    expect(await screen.findByRole("heading", { name: "Chronologie du dossier" })).toBeVisible();
    expect(screen.queryByText("FULL-5678")).not.toBeInTheDocument();
    expect(screen.queryByText("Protected Client")).not.toBeInTheDocument();
    expect(screen.queryByText("Informations client protégées")).not.toBeInTheDocument();
  });
});
