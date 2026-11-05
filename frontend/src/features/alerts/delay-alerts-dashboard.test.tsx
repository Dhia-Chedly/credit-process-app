import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DelayAlertsDashboard } from "./delay-alerts-dashboard";

const alerts = [
  {
    id: "escalated-alert",
    agency: "agency-ariana",
    agency_name: "ARIANA",
    reference: "1200/70001/P/01082026",
    application_id: "application-1",
    rule_label: "Visite bloquée",
    state: "escalated",
    state_label: "Escaladé",
    reporting_period: "2026-08-01",
    started_on: "2026-08-03",
    responsible_role: "GP",
    responsible_name: "Karim Test",
  },
  {
    id: "new-alert",
    agency: "agency-beja",
    agency_name: "BEJA",
    reference: "1300/70002/P/02082026",
    application_id: "application-2",
    rule_label: "Réception bloquée",
    state: "new",
    state_label: "Nouveau",
    reporting_period: "2026-08-01",
    started_on: "2026-08-10",
    responsible_role: "CA/CAA",
    responsible_name: "Amira Test",
  },
  {
    id: "reviewed-alert",
    agency: "agency-ariana",
    agency_name: "ARIANA",
    reference: "1200/70003/P/03082026",
    application_id: "application-3",
    rule_label: "Visite bloquée",
    state: "reviewed",
    state_label: "Consulté",
    reporting_period: "2026-08-01",
    started_on: "2026-08-06",
    responsible_role: "GP",
    responsible_name: "Karim Test",
  },
] as const;

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

describe("DelayAlertsDashboard", () => {
  it("prioritizes actionable alerts and removes a resolved alert", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "DELETE") return Promise.resolve(new Response(null, { status: 204 }));
      const url = new URL(String(input));
      const agency = url.searchParams.get("agency");
      const responsible = url.searchParams.get("responsible");
      const scopedAlerts = alerts.filter(
        (alert) =>
          (agency === null || alert.agency === agency) &&
          (responsible === null || alert.responsible_name === responsible),
      );
      const state = url.searchParams.get("state");
      const results = scopedAlerts.filter((alert) => state === null || alert.state === state);
      return Promise.resolve(
        response({
          count: results.length,
          next: null,
          previous: null,
          results,
          summary: {
            new: scopedAlerts.filter((alert) => alert.state === "new").length,
            escalated: scopedAlerts.filter((alert) => alert.state === "escalated").length,
          },
          filter_options: {
            agencies: [
              { agency_id: "agency-ariana", agency__name: "ARIANA" },
              { agency_id: "agency-beja", agency__name: "BEJA" },
            ],
            responsibles: [
              {
                agency_id: "agency-ariana",
                agency__name: "ARIANA",
                responsible_role: "GP",
                responsible_name: "Karim Test",
              },
              {
                agency_id: "agency-beja",
                agency__name: "BEJA",
                responsible_role: "CA/CAA",
                responsible_name: "Amira Test",
              },
            ],
          },
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <DelayAlertsDashboard />
      </QueryClientProvider>,
    );

    expect(await screen.findByText("1300/70002/P/02082026")).toBeVisible();
    expect(screen.queryByText("1200/70001/P/01082026")).not.toBeInTheDocument();
    expect(screen.getByText("1300/70002/P/02082026")).toBeVisible();
    expect(screen.queryByText("1200/70003/P/03082026")).not.toBeInTheDocument();

    const agencyFilter = screen.getByLabelText("Filtrer par agence");
    fireEvent.change(agencyFilter, { target: { value: "agency-beja" } });
    expect(await screen.findByRole("option", { name: "Amira Test" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Karim Test" })).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Filtrer par agence"), { target: { value: "all" } });
    const karim = await screen.findByRole("option", { name: "Karim Test — ARIANA" });
    fireEvent.change(screen.getByLabelText("Filtrer par responsable"), {
      target: { value: karim.getAttribute("value")! },
    });
    await waitFor(() =>
      expect(screen.getByLabelText("Filtrer par agence")).toHaveValue("agency-ariana"),
    );

    fireEvent.click(screen.getByRole("button", { name: /Escaladées 1/ }));
    expect(await screen.findByText("1200/70001/P/01082026")).toBeVisible();
    expect(screen.queryByText("1300/70002/P/02082026")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Résoudre l’alerte" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/delay-alerts/escalated-alert/resolve/"),
        expect.objectContaining({
          method: "DELETE",
        }),
      );
    });
  });
});
