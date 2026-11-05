"use client";

import {
  type ColumnDef,
  type PaginationState,
  type RowData,
  type SortingState,
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight } from "lucide-react";
import { useId, useMemo, useState } from "react";

export type DataTableColumn<TData extends RowData> = ColumnDef<TData, unknown>;

export interface DataTableProps<TData extends RowData> {
  data: ReadonlyArray<TData>;
  columns: ReadonlyArray<DataTableColumn<TData>>;
  caption: string;
  loading?: boolean;
  loadingMessage?: string;
  emptyMessage?: string;
  initialPageSize?: number;
  pageSizeOptions?: ReadonlyArray<number>;
  getRowId?: (row: TData, index: number) => string;
  className?: string;
  sortable?: boolean;
}

const controlClassName =
  "inline-flex min-h-10 items-center justify-center rounded-lg border border-[var(--border)] bg-white px-3 text-sm font-semibold transition hover:bg-slate-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--brand)] disabled:cursor-not-allowed disabled:opacity-45";

function positiveInteger(value: number, fallback: number) {
  return Number.isInteger(value) && value > 0 ? value : fallback;
}

function labelFor(header: unknown) {
  return typeof header === "string" ? header : "Détail";
}

/** A typed, sortable and paginated card collection for bounded drill-down result sets. */
export function DataTable<TData extends RowData>({
  data,
  columns,
  caption,
  loading = false,
  loadingMessage = "Chargement des fiches…",
  emptyMessage = "Aucune fiche ne correspond aux filtres sélectionnés.",
  initialPageSize = 10,
  pageSizeOptions = [10, 25, 50],
  getRowId,
  className = "",
  sortable = true,
}: DataTableProps<TData>) {
  const pageSize = positiveInteger(initialPageSize, 10);
  const [sorting, setSorting] = useState<SortingState>([]);
  const [pagination, setPagination] = useState<PaginationState>({ pageIndex: 0, pageSize });
  const pageSizeId = `${useId()}-page-size`;
  const availablePageSizes = useMemo(
    () =>
      [
        ...new Set([pageSize, ...pageSizeOptions.map((value) => positiveInteger(value, pageSize))]),
      ].sort((a, b) => a - b),
    [pageSize, pageSizeOptions],
  );
  const tableData = useMemo(() => [...data], [data]);
  const tableColumns = useMemo(() => [...columns], [columns]);

  // TanStack exposes mutable callbacks by design; this collection is not compiler-memoized.
  // eslint-disable-next-line react-hooks/incompatible-library
  const collection = useReactTable({
    data: tableData,
    columns: tableColumns,
    state: { sorting: sortable ? sorting : [], pagination },
    onSortingChange: sortable ? setSorting : undefined,
    onPaginationChange: setPagination,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getRowId,
    enableSorting: sortable,
  });

  const visibleRows = collection.getRowModel().rows;
  const pageCount = Math.max(collection.getPageCount(), 1);
  const currentPage = Math.min(collection.getState().pagination.pageIndex + 1, pageCount);
  const sortableHeaders = sortable
    ? collection.getFlatHeaders().filter((header) => header.column.getCanSort())
    : [];

  return (
    <section
      className={`rounded-2xl border border-[var(--border)] bg-slate-50/70 p-4 sm:p-5 ${className}`}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-base font-semibold">{caption}</h2>
        {sortableHeaders.length > 0 && (
          <div className="flex flex-wrap gap-2" aria-label="Trier les fiches">
            {sortableHeaders.slice(0, 4).map((header) => {
              const sorted = header.column.getIsSorted();
              return (
                <button
                  className="inline-flex min-h-9 items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 hover:border-emerald-300"
                  key={header.id}
                  onClick={header.column.getToggleSortingHandler()}
                  type="button"
                >
                  {labelFor(header.column.columnDef.header)}
                  {sorted === "asc" ? (
                    <ArrowUp aria-hidden size={13} />
                  ) : sorted === "desc" ? (
                    <ArrowDown aria-hidden size={13} />
                  ) : (
                    <ArrowUpDown aria-hidden size={13} />
                  )}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {loading ? (
        <p
          className="mt-4 rounded-xl border border-dashed border-[var(--border)] bg-white p-10 text-center text-sm text-[var(--muted)]"
          role="status"
        >
          {loadingMessage}
        </p>
      ) : visibleRows.length === 0 ? (
        <p className="mt-4 rounded-xl border border-dashed border-[var(--border)] bg-white p-10 text-center text-sm text-[var(--muted)]">
          {emptyMessage}
        </p>
      ) : (
        <div className="mt-4 grid gap-4 xl:grid-cols-2" aria-busy={loading}>
          {visibleRows.map((row) => (
            <article
              className="rounded-xl border border-[var(--border)] bg-white p-4 shadow-sm transition hover:border-emerald-200 hover:shadow-md"
              key={row.id}
            >
              <dl className="grid gap-x-5 gap-y-3 sm:grid-cols-2">
                {row.getVisibleCells().map((cell, index) => (
                  <div className={index === 0 ? "sm:col-span-2" : ""} key={cell.id}>
                    <dt className="text-[0.68rem] font-bold uppercase tracking-wider text-[var(--muted)]">
                      {labelFor(cell.column.columnDef.header)}
                    </dt>
                    <dd className="mt-1 min-w-0 text-sm text-slate-800">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </dd>
                  </div>
                ))}
              </dl>
            </article>
          ))}
        </div>
      )}

      <div className="mt-4 flex flex-col gap-3 border-t border-[var(--border)] pt-4 sm:flex-row sm:items-center sm:justify-between">
        <p aria-live="polite" className="text-sm text-[var(--muted)]">
          Page <span className="font-semibold text-[var(--foreground)]">{currentPage}</span> sur{" "}
          <span className="font-semibold text-[var(--foreground)]">{pageCount}</span> ·{" "}
          {data.length.toLocaleString("fr-FR")} fiches
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <label className="text-sm font-medium" htmlFor={pageSizeId}>
            Fiches par page
          </label>
          <select
            className={controlClassName}
            id={pageSizeId}
            onChange={(event) => collection.setPageSize(Number(event.target.value))}
            value={collection.getState().pagination.pageSize}
          >
            {availablePageSizes.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
          <button
            aria-label="Page précédente"
            className={controlClassName}
            disabled={!collection.getCanPreviousPage() || loading}
            onClick={() => collection.previousPage()}
            type="button"
          >
            <ChevronLeft aria-hidden size={18} />
          </button>
          <button
            aria-label="Page suivante"
            className={controlClassName}
            disabled={!collection.getCanNextPage() || loading}
            onClick={() => collection.nextPage()}
            type="button"
          >
            <ChevronRight aria-hidden size={18} />
          </button>
        </div>
      </div>
    </section>
  );
}
