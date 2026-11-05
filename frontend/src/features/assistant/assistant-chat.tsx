"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { Bot, ExternalLink, LoaderCircle, Send, Sparkles, X } from "lucide-react";
import Link from "next/link";
import { type FormEvent, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api/client";
import type {
  AssistantConversationMessage,
  AssistantResponse,
  AssistantSource,
} from "@/lib/api/contracts";
import { apiPaths } from "@/lib/api/paths";
import { cn } from "@/lib/utils";

type DisplayMessage = AssistantConversationMessage & {
  id: string;
  sources?: AssistantSource[];
  links?: AssistantResponse["links"];
};

const starterQuestions = [
  "Résume le portefeuille des 12 derniers mois",
  "Quelles agences ont le plus de retards ?",
  "Résume le dernier import",
] as const;

function messageId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function AssistantChat() {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [suggestions, setSuggestions] = useState<readonly string[]>(starterQuestions);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollAnchor = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollAnchor.current?.scrollIntoView?.({ behavior: "smooth" });
  }, [messages, pending]);

  async function ask(question: string) {
    const trimmed = question.trim();
    if (!trimmed || pending) return;
    const history = messages
      .slice(-6)
      .map(({ role, content }) => ({ role, content }) satisfies AssistantConversationMessage);
    const userMessage: DisplayMessage = { id: messageId(), role: "user", content: trimmed };
    setMessages((current) => [...current, userMessage]);
    setInput("");
    setError(null);
    setPending(true);
    try {
      const response = await apiFetch<AssistantResponse>(apiPaths.assistantMessages, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: trimmed, history }),
      });
      setMessages((current) => [
        ...current,
        {
          id: messageId(),
          role: "assistant",
          content: response.answer,
          sources: response.sources,
          links: response.links,
        },
      ]);
      setSuggestions(response.suggestions);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "L’assistant est temporairement indisponible.",
      );
    } finally {
      setPending(false);
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void ask(input);
  }

  return (
    <Dialog.Root onOpenChange={setOpen} open={open}>
      <Dialog.Trigger asChild>
        <Button
          aria-label="Ouvrir l’assistant Credit Operations Platform"
          className="fixed bottom-5 right-5 z-40 h-12 rounded-full px-4 shadow-xl sm:bottom-7 sm:right-7"
        >
          <Sparkles aria-hidden="true" size={18} />
          <span className="hidden sm:inline">Assistant</span>
        </Button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-slate-950/35 backdrop-blur-[2px]" />
        <Dialog.Content className="fixed inset-y-0 right-0 z-50 flex w-full max-w-[30rem] flex-col border-l border-[var(--border)] bg-white shadow-2xl focus:outline-none">
          <header className="flex items-start justify-between border-b border-[var(--border)] px-5 py-4">
            <div className="flex gap-3">
              <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-emerald-100 text-emerald-800">
                <Bot aria-hidden="true" size={21} />
              </span>
              <div>
                <Dialog.Title className="font-bold text-slate-950">
                  Assistant Credit Operations Platform
                </Dialog.Title>
                <Dialog.Description className="mt-0.5 text-xs leading-5 text-slate-600">
                  Questions en langage naturel sur les données gouvernées. Lecture seule.
                </Dialog.Description>
              </div>
            </div>
            <Dialog.Close asChild>
              <Button aria-label="Fermer l’assistant" size="icon" variant="ghost">
                <X aria-hidden="true" size={19} />
              </Button>
            </Dialog.Close>
          </header>

          <div aria-live="polite" className="flex-1 space-y-4 overflow-y-auto px-4 py-5">
            {messages.length === 0 ? (
              <div className="rounded-2xl border border-emerald-100 bg-emerald-50 p-4 text-sm leading-6 text-emerald-950">
                Je peux résumer le portefeuille, comparer les agences, expliquer les retards et
                rejets, retrouver le parcours d’un dossier ou résumer un import.
              </div>
            ) : null}

            {messages.map((message) => (
              <article
                className={cn(
                  "max-w-[92%] rounded-2xl px-4 py-3 text-sm leading-6",
                  message.role === "user"
                    ? "ml-auto bg-slate-900 text-white"
                    : "mr-auto border border-[var(--border)] bg-slate-50 text-slate-900",
                )}
                key={message.id}
              >
                <p className="whitespace-pre-wrap">{message.content}</p>
                {message.sources?.length ? (
                  <div className="mt-3 border-t border-slate-200 pt-2 text-xs text-slate-600">
                    <p className="font-semibold text-slate-700">Sources</p>
                    {message.sources.map((source) => (
                      <p className="mt-1" key={`${source.type}-${source.label}-${source.detail}`}>
                        {source.label}
                        {source.detail ? ` · ${source.detail}` : ""}
                      </p>
                    ))}
                  </div>
                ) : null}
                {message.links?.length ? (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {message.links.map((link) => (
                      <Link
                        className="inline-flex items-center gap-1 rounded-md bg-white px-2 py-1 text-xs font-semibold text-emerald-800 underline-offset-2 hover:underline"
                        href={link.url}
                        key={`${link.url}-${link.label}`}
                        onClick={() => setOpen(false)}
                      >
                        {link.label}
                        <ExternalLink aria-hidden="true" size={12} />
                      </Link>
                    ))}
                  </div>
                ) : null}
              </article>
            ))}

            {pending ? (
              <div className="mr-auto flex items-center gap-2 rounded-2xl border border-[var(--border)] bg-slate-50 px-4 py-3 text-sm text-slate-600">
                <LoaderCircle aria-hidden="true" className="animate-spin" size={17} />
                Analyse des données…
              </div>
            ) : null}
            {error ? (
              <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
                {error}
              </div>
            ) : null}
            <div ref={scrollAnchor} />
          </div>

          <div className="border-t border-[var(--border)] bg-white p-4">
            <div className="mb-3 flex gap-2 overflow-x-auto pb-1">
              {suggestions.slice(0, 3).map((suggestion) => (
                <button
                  className="shrink-0 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-900 hover:bg-emerald-100 disabled:opacity-50"
                  disabled={pending}
                  key={suggestion}
                  onClick={() => void ask(suggestion)}
                  type="button"
                >
                  {suggestion}
                </button>
              ))}
            </div>
            <form className="flex items-end gap-2" onSubmit={submit}>
              <label className="sr-only" htmlFor="assistant-question">
                Question pour l’assistant
              </label>
              <textarea
                className="min-h-12 max-h-32 flex-1 resize-y rounded-xl border border-[var(--border)] bg-white px-3 py-2 text-sm text-slate-950 outline-none placeholder:text-slate-500 focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100"
                disabled={pending}
                id="assistant-question"
                maxLength={2000}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    event.currentTarget.form?.requestSubmit();
                  }
                }}
                placeholder="Posez une question sur Credit Operations Platform…"
                rows={2}
                value={input}
              />
              <Button
                aria-label="Envoyer la question"
                disabled={pending || !input.trim()}
                size="icon"
                type="submit"
              >
                <Send aria-hidden="true" size={18} />
              </Button>
            </form>
            <p className="mt-2 text-center text-[0.68rem] text-slate-500">
              Vérifiez les sources. N’incluez aucune donnée client. Aucune décision de crédit.
            </p>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
