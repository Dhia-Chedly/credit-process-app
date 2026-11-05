import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "./app-shell";

vi.mock("next/navigation", () => ({ usePathname: () => "/" }));

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function wrapper(children: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("AppShell navigation", () => {
  it("shows the local analytics and operations navigation", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify({
              id: "central-1",
              username: "central",
              display_name: "Central Manager",
              role: { code: "system_admin", name: "Central Admin / Manager" },
              agency: null,
              employee: null,
              capabilities: {
                can_import: true,
                can_view_all_agencies: true,
                can_view_client_pii: true,
                can_approve_mappings: true,
                credit_request_scope: "all",
              },
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        ),
      ),
    );

    render(wrapper(<AppShell>Central content</AppShell>));

    expect(await screen.findByText("central")).toBeVisible();
    expect(screen.getByRole("link", { name: "Réseau" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Imports & qualité" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Collapse navigation" }));
    expect(screen.getByRole("button", { name: "Expand navigation" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Réseau" })).toBeVisible();
  });
});
