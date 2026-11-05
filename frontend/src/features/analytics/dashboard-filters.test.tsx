import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DashboardFilters } from "./dashboard-filters";

const { replaceMock } = vi.hoisted(() => ({ replaceMock: vi.fn() }));

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({ replace: replaceMock }),
  useSearchParams: () => new URLSearchParams(),
}));

afterEach(() => {
  cleanup();
  replaceMock.mockReset();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("DashboardFilters", () => {
  it("presents month-grain filters and sends the first day contract value", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify({
              agencies: [
                { agency_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", name: "Ariana" },
                { agency_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", name: "Bizerte" },
              ],
              intervals: [],
              employees: {
                ca: [
                  {
                    id: "00000000-0000-0000-0000-000000000001",
                    display_name: "Inconnu",
                    role: "ca",
                    agency_id: "agency-1",
                    identity_status: "controlled",
                  },
                  {
                    id: "11111111-1111-1111-1111-111111111111",
                    display_name: "CA Test",
                    role: "ca",
                    agency_id: "agency-1",
                    identity_status: "controlled",
                  },
                ],
                gp: [
                  {
                    id: "00000000-0000-0000-0000-000000000002",
                    display_name: "Inconnu",
                    role: "gp",
                    agency_id: "agency-1",
                    identity_status: "controlled",
                  },
                  {
                    id: "22222222-2222-2222-2222-222222222222",
                    display_name: "GP Test",
                    role: "gp",
                    agency_id: "agency-1",
                    identity_status: "controlled",
                  },
                ],
              },
            }),
            {
              status: 200,
              headers: { "Content-Type": "application/json" },
            },
          ),
        ),
      ),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <DashboardFilters />
      </QueryClientProvider>,
    );

    const period = await screen.findByLabelText("Période");
    fireEvent.change(period, { target: { value: "custom" } });
    const monthFrom = await screen.findByLabelText("Du mois");
    expect(monthFrom.tagName).toBe("INPUT");
    fireEvent.change(monthFrom, { target: { value: "2026-05" } });
    expect(replaceMock).toHaveBeenCalledWith(expect.stringContaining("date_from=2026-05-01"), {
      scroll: false,
    });
    expect(await screen.findByRole("option", { name: "CA Test" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Inconnu" })).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("CA"), {
      target: { value: "11111111-1111-1111-1111-111111111111" },
    });
    expect(replaceMock).toHaveBeenCalledWith("/?ca=11111111-1111-1111-1111-111111111111", {
      scroll: false,
    });
    fireEvent.click(screen.getByText("Toutes les agences"));
    fireEvent.click(screen.getByLabelText("Ariana"));
    fireEvent.click(screen.getByLabelText("Bizerte"));
    fireEvent.click(screen.getByRole("button", { name: "Appliquer la sélection" }));
    expect(replaceMock).toHaveBeenLastCalledWith(
      "/?agency=aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa%2Cbbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
      { scroll: false },
    );
  });
});
