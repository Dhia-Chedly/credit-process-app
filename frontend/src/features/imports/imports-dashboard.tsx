"use client";

import { useMutation } from "@tanstack/react-query";
import { LoaderCircle, Upload } from "lucide-react";
import { useRouter } from "next/navigation";
import { type FormEvent, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { DataState } from "@/components/ui/data-state";
import { useCurrentUser } from "@/features/auth/queries";
import { ApiError, apiFetch } from "@/lib/api/client";
import type { ImportBatch } from "@/lib/api/contracts";
import { apiPaths } from "@/lib/api/paths";

function friendlyUploadError(error: Error | null) {
  if (!(error instanceof ApiError)) return error?.message ?? "L’import n’a pas pu être lancé.";
  const code =
    typeof error.body === "object" && error.body !== null
      ? Reflect.get(error.body, "code")
      : undefined;
  const messages: Record<string, string> = {
    unsupported_extension: "Choisissez un classeur Excel au format .xlsx.",
    empty_file: "Le fichier sélectionné est vide.",
    file_too_large: "Le classeur dépasse la taille maximale autorisée.",
    invalid_container: "Le fichier est endommagé ou n’est pas un véritable classeur .xlsx.",
    invalid_workbook: "Le fichier ne contient pas une structure Excel valide.",
    encrypted_workbook: "Les classeurs protégés par mot de passe ne sont pas acceptés.",
    suspicious_compression: "Le classeur a été refusé pour des raisons de sécurité.",
  };
  return typeof code === "string" && messages[code]
    ? messages[code]
    : "Le fichier n’a pas pu être accepté. Vérifiez le modèle puis réessayez.";
}

export function ImportsDashboard() {
  const router = useRouter();
  const currentUser = useCurrentUser();
  const canUpload = currentUser.data?.capabilities?.can_import ?? true;
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const upload = useMutation({
    mutationFn: (file: File) => {
      const body = new FormData();
      body.append("file", file);
      return apiFetch<ImportBatch>(apiPaths.importBatches, { body, method: "POST" });
    },
    onSuccess: (batch) => router.push(`/imports/${batch.id}?fromUpload=1`),
  });

  function chooseFile(file?: File) {
    setFileError("");
    upload.reset();
    if (!file) {
      setSelectedFile(null);
      return;
    }
    if (!file.name.toLowerCase().endsWith(".xlsx")) {
      setSelectedFile(null);
      setFileError("Choisissez un fichier Excel avec l’extension .xlsx.");
      if (inputRef.current) inputRef.current.value = "";
      return;
    }
    setSelectedFile(file);
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedFile) {
      setFileError("Choisissez un fichier .xlsx avant l’import.");
      inputRef.current?.focus();
      return;
    }
    upload.mutate(selectedFile);
  }

  return (
    <div>
      <div>
        {canUpload ? (
          <form
            className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm sm:p-6"
            onSubmit={submit}
          >
            <label className="block text-sm font-semibold" htmlFor="workbook-file">
              Fichier Excel
            </label>
            <input
              accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              aria-invalid={Boolean(fileError || upload.error)}
              className="sr-only"
              id="workbook-file"
              onChange={(event) => chooseFile(event.target.files?.[0])}
              ref={inputRef}
              type="file"
            />
            <div className="mt-2 flex min-h-11 items-center gap-3 rounded-xl border border-[var(--border)] bg-slate-50 p-2">
              <Button
                onClick={() => inputRef.current?.click()}
                size="compact"
                type="button"
                variant="secondary"
              >
                Parcourir…
              </Button>
              <span className="truncate text-sm text-[var(--muted)]">
                {selectedFile?.name ?? "Aucun fichier sélectionné"}
              </span>
            </div>
            {(fileError || upload.error) && (
              <p className="mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-800" role="alert">
                {fileError || friendlyUploadError(upload.error)}
              </p>
            )}
            <Button className="mt-5" disabled={!selectedFile || upload.isPending} type="submit">
              {upload.isPending ? (
                <>
                  <LoaderCircle
                    aria-hidden="true"
                    className="animate-spin motion-reduce:animate-none"
                    size={17}
                  />
                  Envoi en cours…
                </>
              ) : (
                <>
                  <Upload aria-hidden="true" size={17} />
                  Importer le fichier
                </>
              )}
            </Button>
          </form>
        ) : (
          <DataState title="Accès aux imports en lecture seule" tone="info">
            Votre rôle peut consulter les lots autorisés, mais ne peut pas importer de fichier.
          </DataState>
        )}
      </div>
    </div>
  );
}
