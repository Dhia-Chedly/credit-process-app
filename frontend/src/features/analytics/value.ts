import type { AnalyticsRecord } from "@/lib/api/contracts";

export function firstValue(record: AnalyticsRecord | undefined, keys: string[]) {
  if (!record) return undefined;
  for (const key of keys) {
    const value = record[key];
    if (value !== undefined && value !== null) return value;
  }
  return undefined;
}

export function numberValue(record: AnalyticsRecord | undefined, keys: string[]) {
  const value = firstValue(record, keys);
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return undefined;
}

export function stringValue(record: AnalyticsRecord | undefined, keys: string[]) {
  const value = firstValue(record, keys);
  if (typeof value === "string") return value;
  if (typeof value === "number") return String(value);
  return undefined;
}

export function formatInteger(value: unknown) {
  const numeric = typeof value === "number" ? value : Number(value);
  return Number.isFinite(numeric) ? new Intl.NumberFormat("fr-FR").format(numeric) : "Indisponible";
}

export function formatDays(value: unknown) {
  const numeric = typeof value === "number" ? value : Number(value);
  return Number.isFinite(numeric)
    ? `${numeric.toLocaleString("fr-FR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} j`
    : "Indisponible";
}
