import type { ImportBatch } from "@/lib/api/contracts";

export const IMPORT_STATUS_LABELS: Record<ImportBatch["status"], string> = {
  uploaded: "Fichier reçu",
  queued: "En attente de traitement",
  processing: "Traitement en cours",
  completed: "Accepté",
  partial: "Partiellement accepté",
  failed: "Rejeté",
};

export function failedImportGuidance(message: string) {
  if (message.includes("worker queue")) {
    return {
      explanation: "Le service de traitement est temporairement indisponible.",
      action:
        "Réessayez dans quelques minutes. Si le problème persiste, contactez un administrateur.",
    };
  }
  if (message.includes("supported TB1 or TB2 schema")) {
    return {
      explanation: "Le classeur ne respecte pas les en-têtes exacts du modèle de suivi attendu.",
      action: "Comparez les colonnes au modèle officiel, corrigez le fichier, puis réimportez-le.",
    };
  }
  if (message.includes("readable XLSX")) {
    return {
      explanation: "Le fichier Excel est endommagé ou ne peut pas être lu.",
      action: "Ouvrez-le dans Excel, enregistrez une nouvelle copie .xlsx, puis réessayez.",
    };
  }
  if (message.includes("processing limit")) {
    return {
      explanation: "Le classeur dépasse une limite de traitement autorisée.",
      action: "Réduisez sa taille ou contactez un administrateur pour vérifier les limites.",
    };
  }
  return {
    explanation: "Le classeur n’a pas pu être traité.",
    action: "Réessayez une fois. Si l’échec se répète, contactez un administrateur.",
  };
}
