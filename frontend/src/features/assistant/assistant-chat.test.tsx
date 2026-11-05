import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AssistantChat } from "@/features/assistant/assistant-chat";

describe("AssistantChat", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("sends a natural-language question and displays evidence links", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          answer: "Ariana compte 12 demandes sur la période.",
          sources: [
            {
              type: "analytics",
              label: "Comparaison des agences",
              detail: "2026-01-01 - 2026-09-01",
            },
          ],
          links: [{ label: "Ouvrir la comparaison réseau", url: "/agencies" }],
          suggestions: ["Afficher les principaux retards"],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    render(<AssistantChat />);

    fireEvent.click(
      screen.getByRole("button", { name: "Ouvrir l’assistant Credit Operations Platform" }),
    );
    fireEvent.change(screen.getByLabelText("Question pour l’assistant"), {
      target: { value: "Combien de demandes à Ariana ?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Envoyer la question" }));

    expect(await screen.findByText("Ariana compte 12 demandes sur la période.")).toBeVisible();
    expect(screen.getByText(/Comparaison des agences/)).toBeVisible();
    expect(screen.getByRole("link", { name: /Ouvrir la comparaison réseau/ })).toHaveAttribute(
      "href",
      "/agencies",
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const firstCall = fetchMock.mock.calls[0];
    if (!firstCall) throw new Error("Expected the assistant request.");
    const [, options] = firstCall;
    expect(options?.method).toBe("POST");
    expect(JSON.parse(String(options?.body))).toMatchObject({
      message: "Combien de demandes à Ariana ?",
      history: [],
    });
  });
});
