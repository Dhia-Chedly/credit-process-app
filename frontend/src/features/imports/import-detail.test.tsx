import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

import { ImportDetail } from "./import-detail";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("ImportDetail", () => {
  it("shows only erroneous rows and highlights the wrong cells", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        const body = url.endsWith("/me/")
          ? { id: "user-1", username: "operator", capabilities: { can_import: true } }
          : url.endsWith("/issues/")
            ? {
                count: 2,
                next: null,
                previous: null,
                results: [
                  {
                    id: "issue-1",
                    severity: "error",
                    code: "unresolved_employee_identity",
                    field_name: "counsellor_name",
                    field_label: "Nom du conseiller CA/CAA",
                    message: "Technical employee resolution message.",
                    user_title: "CA/CAA introuvable ou inactif pour cette agence",
                    required_correction:
                      "Ajoutez ou activez cet employé dans les référentiels, puis réimportez le classeur corrigé.",
                    submitted_value: "Conseiller inconnu",
                    expected_format: "Nom exact d’un CA/CAA actif rattaché à cette agence.",
                    row_values: [
                      {
                        field_name: "request_date",
                        field_label: "Date de la demande",
                        value: "2026-08-20T00:00:00",
                      },
                      {
                        field_name: "amount",
                        field_label: "Montant demandé",
                        value: "15000",
                      },
                      {
                        field_name: "credit_type",
                        field_label: "Type de crédit",
                        value: null,
                      },
                      {
                        field_name: "counsellor_name",
                        field_label: "Nom du conseiller CA/CAA",
                        value: "Conseiller inconnu",
                      },
                    ],
                    action_kind: "reference_ca",
                    sheet_name: "ARIANA",
                    source_row: 18,
                    created_at: "2026-08-27T10:00:00Z",
                  },
                  {
                    id: "issue-2",
                    severity: "error",
                    code: "missing_required_value",
                    field_name: "credit_type",
                    field_label: "Type de crédit",
                    message: "The required field credit_type is blank.",
                    user_title: "Valeur obligatoire manquante",
                    required_correction:
                      "Renseignez la cellule obligatoire indiquée, puis importez le classeur corrigé.",
                    submitted_value: "",
                    expected_format: "Type de crédit présent dans les référentiels.",
                    row_values: [
                      {
                        field_name: "request_date",
                        field_label: "Date de la demande",
                        value: "2026-08-20T00:00:00",
                      },
                      {
                        field_name: "amount",
                        field_label: "Montant demandé",
                        value: "15000",
                      },
                      {
                        field_name: "credit_type",
                        field_label: "Type de crédit",
                        value: null,
                      },
                      {
                        field_name: "counsellor_name",
                        field_label: "Nom du conseiller CA/CAA",
                        value: "Conseiller inconnu",
                      },
                    ],
                    action_kind: "template",
                    sheet_name: "ARIANA",
                    source_row: 18,
                    created_at: "2026-08-27T10:00:00Z",
                  },
                ],
              }
            : {
                id: "batch-1",
                original_filename: "Etat des en cours agences 08-26.xlsx",
                workbook_type: "tb2",
                status: "partial",
                file_size: 1000,
                discovered_count: 10,
                valid_staged_count: 9,
                quarantined_count: 1,
                unmatched_count: 2,
                published_or_updated_count: 7,
                reporting_period: "2026-08-01",
                detected_agency: null,
                created_at: "2026-08-27T10:00:00Z",
                finished_at: "2026-08-27T10:01:00Z",
                error_message: "",
              };
        return Promise.resolve(
          new Response(JSON.stringify(body), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    render(
      <QueryClientProvider client={client}>
        <ImportDetail importId="batch-1" />
      </QueryClientProvider>,
    );

    expect(await screen.findByText("1 ligne doit être corrigée")).toBeVisible();
    expect(screen.getByText("7 lignes ont été importées correctement.")).toBeVisible();
    expect(screen.getByRole("heading", { name: "Feuille ARIANA" })).toBeVisible();
    expect(screen.getByRole("rowheader", { name: "18" })).toBeVisible();
    const errorCell = screen.getByLabelText("Erreur ligne 18, colonne Nom du conseiller CA/CAA");
    expect(errorCell).toHaveClass("bg-red-50");
    expect(errorCell).toHaveTextContent("Erreur : CA/CAA introuvable ou inactif");
    const missingCreditCell = screen.getByLabelText("Erreur ligne 18, colonne Type de crédit");
    expect(missingCreditCell).toHaveClass("bg-red-50");
    expect(missingCreditCell).toHaveTextContent("Cellule vide");
    expect(missingCreditCell).toHaveAttribute(
      "title",
      expect.stringContaining("Valeur obligatoire manquante"),
    );
    expect(screen.getByText("15000")).toBeVisible();
    expect(screen.getByText("20/08/2026")).toBeVisible();
    expect(screen.queryByText("2026-08-20T00:00:00")).not.toBeInTheDocument();
    expect(screen.getByText("« Conseiller inconnu »")).toBeVisible();
    expect(screen.getByText("Nom exact d’un CA/CAA actif rattaché à cette agence.")).toBeVisible();
    expect(screen.getByText("Technical employee resolution message.")).not.toBeVisible();
  });

  it("shows the backend error message prominently for a failed batch", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        const body = url.endsWith("/me/")
          ? { id: "user-1", username: "operator", capabilities: { can_import: true } }
          : url.endsWith("/issues/")
            ? { count: 0, next: null, previous: null, results: [] }
            : {
                id: "batch-2",
                original_filename: "invalid.xlsx",
                workbook_type: "tb2",
                status: "failed",
                file_size: 1000,
                discovered_count: 0,
                valid_staged_count: 0,
                quarantined_count: 0,
                unmatched_count: 0,
                published_or_updated_count: 0,
                reporting_period: null,
                detected_agency: null,
                created_at: "2026-08-27T10:00:00Z",
                finished_at: "2026-08-27T10:01:00Z",
                error_message: "Workbook does not match a supported TB1 or TB2 schema.",
              };
        return Promise.resolve(
          new Response(JSON.stringify(body), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    render(
      <QueryClientProvider client={client}>
        <ImportDetail importId="batch-2" />
      </QueryClientProvider>,
    );

    expect(await screen.findByText("L’import a échoué")).toBeVisible();
    expect(screen.getByText(/Erreur signalée : Workbook does not match/)).toBeVisible();
    expect(screen.getByText(/Cause probable : Le classeur ne respecte pas/)).toBeVisible();
    expect(screen.getByText(/Action recommandée : Comparez les colonnes/)).toBeVisible();
  });
});
