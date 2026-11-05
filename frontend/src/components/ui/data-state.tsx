import { AlertTriangle, CircleAlert, Database, Info } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

type StateTone = "info" | "warning" | "error" | "empty";

const toneStyles: Record<StateTone, string> = {
  info: "border-blue-200 bg-blue-50 text-blue-950",
  warning: "border-amber-200 bg-amber-50 text-amber-950",
  error: "border-red-200 bg-red-50 text-red-950",
  empty: "border-slate-200 bg-slate-50 text-slate-900",
};

const icons = { info: Info, warning: AlertTriangle, error: CircleAlert, empty: Database };

export function DataState({
  title,
  children,
  tone = "info",
  compact = false,
}: {
  title: string;
  children: ReactNode;
  tone?: StateTone;
  compact?: boolean;
}) {
  const Icon = icons[tone];
  return (
    <div
      className={cn("rounded-xl border", compact ? "p-4" : "p-5 sm:p-6", toneStyles[tone])}
      role={tone === "error" ? "alert" : "status"}
    >
      <div className="flex items-start gap-3">
        <Icon aria-hidden="true" className="mt-0.5 shrink-0" size={20} />
        <div>
          <p className="font-semibold">{title}</p>
          <div className="mt-1 text-sm leading-6 opacity-85">{children}</div>
        </div>
      </div>
    </div>
  );
}

export function LoadingState({ label = "Loading dashboard data…" }: { label?: string }) {
  return (
    <div className="grid min-h-52 place-items-center rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-8">
      <div className="text-center" role="status">
        <span className="mx-auto block size-8 animate-spin rounded-full border-3 border-slate-200 border-t-[var(--brand)] motion-reduce:animate-none" />
        <p className="mt-4 text-sm font-medium text-[var(--muted)]">{label}</p>
      </div>
    </div>
  );
}
