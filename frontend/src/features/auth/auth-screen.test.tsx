import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LoginScreen } from "./auth-screen";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("LoginScreen", () => {
  it("starts a JWT session with governed credentials", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            access: "access-token",
            access_expires_in: 900,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <LoginScreen />
      </QueryClientProvider>,
    );

    fireEvent.change(screen.getByLabelText("Nom d’utilisateur"), {
      target: { value: "central-admin" },
    });
    fireEvent.change(screen.getByLabelText("Mot de passe"), { target: { value: "secret" } });
    fireEvent.click(screen.getByRole("button", { name: "Se connecter" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [url, request] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://localhost:8000/api/auth/login/");
    expect(JSON.parse(String(request.body))).toEqual({
      username: "central-admin",
      password: "secret",
    });
  });
});
