import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

export function MetricCard({
  label,
  value,
  note,
  icon: Icon,
  badge,
  tone = "brand",
  accent,
}: {
  label: string;
  value: ReactNode;
  note?: string;
  icon?: LucideIcon;
  badge?: string;
  tone?: "brand" | "info" | "warning" | "critical";
  accent?: "brand" | "info" | "warning" | "critical";
}) {
  const tones = {
    brand: "bg-[var(--brand-soft)] text-[var(--brand)]",
    info: "bg-blue-50 text-blue-700",
    warning: "bg-amber-50 text-amber-700",
    critical: "bg-red-50 text-red-700",
  };
  const accents = {
    brand: "border-l-emerald-600",
    info: "border-l-blue-600",
    warning: "border-l-amber-500",
    critical: "border-l-red-600",
  };
  return (
    <article
      className={`min-w-0 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5 shadow-sm ${accent ? `border-l-4 ${accents[accent]}` : ""}`}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-medium text-[var(--muted)]">{label}</p>
        {Icon && (
          <span className={`grid size-9 shrink-0 place-items-center rounded-xl ${tones[tone]}`}>
            <Icon aria-hidden="true" size={18} />
          </span>
        )}
      </div>
      <p className="mt-3 truncate text-3xl font-semibold tabular-nums" title={String(value)}>
        {value}
      </p>
      {(note || badge) && (
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs leading-5 text-[var(--muted)]">
          {badge && (
            <span className="rounded-full bg-slate-100 px-2 py-0.5 font-semibold text-slate-700">
              {badge}
            </span>
          )}
          {note && <span>{note}</span>}
        </div>
      )}
    </article>
  );
}
