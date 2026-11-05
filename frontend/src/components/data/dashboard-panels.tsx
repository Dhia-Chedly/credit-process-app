interface RankingItem {
  id: string;
  label: string;
  value: number | null;
  detail?: string;
}

export function RankingPanel({
  title,
  description,
  items,
  valueLabel,
  onSelect,
  emptyMessage = "Aucune donnée fiable n’est disponible pour ce classement.",
}: {
  title: string;
  description?: string;
  items: RankingItem[];
  valueLabel: string;
  onSelect?: (id: string) => void;
  emptyMessage?: string;
}) {
  const maximum = Math.max(...items.map((item) => item.value ?? 0), 1);
  return (
    <section className="rounded-2xl border border-[var(--border)] bg-white p-5 shadow-sm">
      <h2 className="text-lg font-semibold">{title}</h2>
      {description && <p className="mt-1 text-sm leading-6 text-[var(--muted)]">{description}</p>}
      <div className="mt-5 space-y-4">
        {items.length === 0 ? (
          <p className="rounded-xl border border-dashed border-[var(--border)] bg-slate-50 p-6 text-center text-sm text-[var(--muted)]">
            {emptyMessage}
          </p>
        ) : (
          items.map((item, index) => {
            const content = (
              <>
                <span className="flex items-center justify-between gap-3 text-sm">
                  <span className="min-w-0 truncate font-semibold">
                    <span className="mr-2 text-slate-400">{index + 1}.</span>
                    {item.label}
                  </span>
                  <span className="shrink-0 tabular-nums">
                    {item.value?.toLocaleString("fr-FR") ?? "—"} {valueLabel}
                  </span>
                </span>
                <span className="mt-2 block h-2 overflow-hidden rounded-full bg-slate-100">
                  <span
                    className="block h-full rounded-full bg-[var(--brand)]"
                    style={{ width: `${Math.max(((item.value ?? 0) / maximum) * 100, 2)}%` }}
                  />
                </span>
                {item.detail && (
                  <span className="mt-1.5 block text-xs text-[var(--muted)]">{item.detail}</span>
                )}
              </>
            );
            return onSelect ? (
              <button
                className="block w-full rounded-lg text-left focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[var(--brand)]"
                key={item.id}
                onClick={() => onSelect(item.id)}
                type="button"
              >
                {content}
              </button>
            ) : (
              <div key={item.id}>{content}</div>
            );
          })
        )}
      </div>
    </section>
  );
}
