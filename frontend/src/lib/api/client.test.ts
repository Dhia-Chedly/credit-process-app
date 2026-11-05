import { afterEach, describe, expect, it, vi } from "vitest";

import { apiFetch, setAccessToken } from "./client";
import { apiPaths } from "./paths";

afterEach(() => {
  setAccessToken(null);
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("apiFetch", () => {
  it("uses an in-memory bearer token without setting a FormData content type", async () => {
    setAccessToken("short-lived-access-token");
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      void input;
      void init;
      return Promise.resolve(
        new Response(JSON.stringify({ accepted: true }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    const body = new FormData();
    body.append("file", new File(["workbook"], "test.xlsx"));

    await apiFetch(apiPaths.importBatches, { body, method: "POST" });

    const call = fetchMock.mock.calls[0];
    expect(call?.[0]).toBe("http://localhost:8000/api/import-batches/");
    const request = call?.[1] as RequestInit;
    const headers = new Headers(request.headers);
    expect(request).toMatchObject({ credentials: "include", method: "POST" });
    expect(headers.get("Authorization")).toBe("Bearer short-lived-access-token");
    expect(headers.has("Content-Type")).toBe(false);
  });
});
