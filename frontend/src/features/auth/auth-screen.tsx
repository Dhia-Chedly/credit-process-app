"use client";

import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/client";

import { useLogin, useRegister } from "./queries";

const inputClass =
  "mt-1 min-h-11 w-full rounded-lg border border-[var(--border)] bg-white px-3 text-sm outline-none focus:border-[var(--brand)] focus:ring-2 focus:ring-emerald-100";

function errorText(error: unknown) {
  return error instanceof ApiError ? error.message : "The request could not be completed.";
}

export function LoginScreen() {
  const [registering, setRegistering] = useState(false);
  const login = useLogin();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  if (registering) return <RegisterScreen onSignIn={() => setRegistering(false)} />;

  function submit(event: FormEvent) {
    event.preventDefault();
    login.mutate({ username, password });
  }

  return (
    <main className="grid min-h-screen place-items-center bg-slate-950 px-4">
      <form className="w-full max-w-md rounded-2xl bg-white p-7 shadow-2xl" onSubmit={submit}>
        <p className="text-sm font-semibold text-emerald-700">Credit Operations Platform</p>
        <h1 className="mt-2 text-2xl font-bold text-slate-950">Se connecter</h1>
        <p className="mt-2 text-sm text-slate-600">Connectez-vous à votre espace de pilotage.</p>
        <label className="mt-6 block text-sm font-medium">
          Nom d’utilisateur
          <input
            autoComplete="username"
            className={inputClass}
            onChange={(event) => setUsername(event.target.value)}
            required
            value={username}
          />
        </label>
        <label className="mt-4 block text-sm font-medium">
          Mot de passe
          <input
            autoComplete="current-password"
            className={inputClass}
            onChange={(event) => setPassword(event.target.value)}
            required
            type="password"
            value={password}
          />
        </label>
        {login.isError ? (
          <p className="mt-4 text-sm text-red-700">{errorText(login.error)}</p>
        ) : null}
        <Button className="mt-6 w-full" disabled={login.isPending} type="submit">
          {login.isPending ? "Connexion…" : "Se connecter"}
        </Button>
        <p className="mt-5 text-center text-sm text-slate-600">
          Vous n’avez pas de compte ?{" "}
          <button
            className="font-semibold text-emerald-700 hover:underline"
            onClick={() => setRegistering(true)}
            type="button"
          >
            Créer un compte
          </button>
        </p>
      </form>
    </main>
  );
}

function RegisterScreen({ onSignIn }: { onSignIn: () => void }) {
  const register = useRegister();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const mismatch = Boolean(confirmation && password !== confirmation);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!mismatch) {
      register.mutate({ username, password, password_confirmation: confirmation });
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-slate-950 px-4">
      <form className="w-full max-w-md rounded-2xl bg-white p-7 shadow-2xl" onSubmit={submit}>
        <p className="text-sm font-semibold text-emerald-700">Credit Operations Platform</p>
        <h1 className="mt-2 text-2xl font-bold text-slate-950">Créer un compte</h1>
        <p className="mt-2 text-sm text-slate-600">
          Choisissez un nom d’utilisateur et un mot de passe robuste.
        </p>
        <label className="mt-6 block text-sm font-medium">
          Nom d’utilisateur
          <input
            autoComplete="username"
            className={inputClass}
            onChange={(event) => setUsername(event.target.value)}
            required
            value={username}
          />
        </label>
        <label className="mt-4 block text-sm font-medium">
          Mot de passe
          <input
            autoComplete="new-password"
            className={inputClass}
            onChange={(event) => setPassword(event.target.value)}
            required
            type="password"
            value={password}
          />
        </label>
        <label className="mt-4 block text-sm font-medium">
          Confirmer le mot de passe
          <input
            autoComplete="new-password"
            className={inputClass}
            onChange={(event) => setConfirmation(event.target.value)}
            required
            type="password"
            value={confirmation}
          />
        </label>
        {mismatch ? (
          <p className="mt-3 text-sm text-red-700">Les mots de passe ne correspondent pas.</p>
        ) : null}
        {register.isError ? (
          <p className="mt-3 text-sm text-red-700">{errorText(register.error)}</p>
        ) : null}
        <Button className="mt-6 w-full" disabled={mismatch || register.isPending} type="submit">
          {register.isPending ? "Création du compte…" : "Créer mon compte"}
        </Button>
        <p className="mt-5 text-center text-sm text-slate-600">
          Vous avez déjà un compte ?{" "}
          <button
            className="font-semibold text-emerald-700 hover:underline"
            onClick={onSignIn}
            type="button"
          >
            Se connecter
          </button>
        </p>
      </form>
    </main>
  );
}
