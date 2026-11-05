"use client";

import type { EChartsOption } from "echarts";
import dynamic from "next/dynamic";
import { useId, useMemo } from "react";

export type ChartValue = string | number | null;
export type ChartDatasetRow = Record<string, ChartValue>;

export interface ChartColumn {
  key: string;
  label: string;
  format?: (value: ChartValue, row: ChartDatasetRow) => string;
}

export interface SimpleChartSeries {
  name: string;
  data: ReadonlyArray<number | null>;
  type?: "bar" | "line";
  color?: string;
}

interface AccessibleEChartBaseProps {
  title: string;
  description: string;
  emptyMessage?: string;
  fallbackCaption?: string;
  hideFallback?: boolean;
  height?: number;
  className?: string;
}

export interface DatasetChartProps extends AccessibleEChartBaseProps {
  dataset: ReadonlyArray<ChartDatasetRow>;
  columns: ReadonlyArray<ChartColumn>;
  options: EChartsOption;
  categories?: never;
  series?: never;
}

export interface SimpleSeriesChartProps extends AccessibleEChartBaseProps {
  categories: ReadonlyArray<string>;
  series: ReadonlyArray<SimpleChartSeries>;
  options?: EChartsOption;
  dataset?: never;
  columns?: never;
}

export type AccessibleEChartProps = DatasetChartProps | SimpleSeriesChartProps;

const EChartCanvas = dynamic(() => import("echarts-for-react"), {
  ssr: false,
  loading: () => (
    <div
      className="flex h-full min-h-72 items-center justify-center rounded-xl bg-slate-50 text-sm text-[var(--muted)]"
      role="presentation"
    >
      Preparing chart…
    </div>
  ),
});

const DEFAULT_COLORS = ["#0b6e5d", "#2563eb", "#d97706", "#7c3aed", "#dc2626"];

const AXIS_STYLE = {
  axisLine: { lineStyle: { color: "#cbd5e1" } },
  axisLabel: { color: "#64748b" },
  splitLine: { lineStyle: { color: "#e2e8f0", type: "dashed" as const } },
};

function defaultFormat(value: ChartValue) {
  if (value === null || value === "") return "—";
  if (typeof value === "number") return value.toLocaleString();
  return value;
}

function simpleSeriesTable(
  categories: ReadonlyArray<string>,
  series: ReadonlyArray<SimpleChartSeries>,
) {
  const columns: ChartColumn[] = [
    { key: "category", label: "Category" },
    ...series.map(({ name }, index) => ({ key: `series-${index}`, label: name })),
  ];
  const rows = categories.map((category, categoryIndex) => {
    const row: ChartDatasetRow = { category };
    series.forEach((item, seriesIndex) => {
      row[`series-${seriesIndex}`] = item.data[categoryIndex] ?? null;
    });
    return row;
  });

  return { columns, rows };
}

function simpleSeriesOption(
  categories: ReadonlyArray<string>,
  series: ReadonlyArray<SimpleChartSeries>,
  options: EChartsOption | undefined,
): EChartsOption {
  return {
    animationDuration: 350,
    color: DEFAULT_COLORS,
    grid: { left: 24, right: 20, top: series.length > 1 ? 48 : 24, bottom: 24, containLabel: true },
    legend: { show: series.length > 1, top: 0 },
    tooltip: { trigger: "axis" },
    ...options,
    xAxis: {
      type: "category",
      data: [...categories],
      ...AXIS_STYLE,
      axisLabel: { ...AXIS_STYLE.axisLabel, hideOverlap: true },
    },
    yAxis: { type: "value", ...AXIS_STYLE },
    series: series.map((item, index) => ({
      name: item.name,
      type: item.type ?? "bar",
      data: [...item.data],
      itemStyle: item.color ? { color: item.color } : undefined,
      lineStyle: item.color ? { color: item.color } : undefined,
      emphasis: { focus: "series" },
      color: item.color ?? DEFAULT_COLORS[index % DEFAULT_COLORS.length],
    })),
  };
}

/**
 * Renders a browser-only ECharts canvas with a semantic data table that remains available to
 * assistive technology and to people who cannot use the visual chart.
 */
export function AccessibleEChart(props: AccessibleEChartProps) {
  const generatedId = useId();
  const titleId = `${generatedId}-title`;
  const descriptionId = `${generatedId}-description`;

  const prepared = useMemo(() => {
    if (props.dataset !== undefined) {
      return {
        rows: [...props.dataset],
        columns: [...props.columns],
        option: {
          animationDuration: 350,
          animationDurationUpdate: 250,
          color: DEFAULT_COLORS,
          aria: { enabled: true },
          textStyle: { color: "#334155", fontFamily: "inherit" },
          grid: { left: 24, right: 20, top: 32, bottom: 24, containLabel: true },
          tooltip: { trigger: "axis" },
          ...props.options,
          dataset: { source: [...props.dataset] },
        } satisfies EChartsOption,
      };
    }

    const table = simpleSeriesTable(props.categories, props.series);
    return {
      rows: table.rows,
      columns: table.columns,
      option: simpleSeriesOption(props.categories, props.series, props.options),
    };
  }, [props]);

  const hasData = prepared.rows.length > 0 && prepared.columns.length > 0;
  const chartHeight = Math.max(props.height ?? 360, 240);

  return (
    <section
      aria-describedby={props.description ? descriptionId : undefined}
      aria-labelledby={titleId}
      className={`rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5 shadow-sm ${props.className ?? ""}`}
    >
      <header>
        <h2 className="text-lg font-semibold" id={titleId}>
          {props.title}
        </h2>
        {props.description && (
          <p className="mt-1 text-sm leading-6 text-[var(--muted)]" id={descriptionId}>
            {props.description}
          </p>
        )}
      </header>

      {hasData ? (
        <div aria-hidden="true" className="mt-5" style={{ height: chartHeight }}>
          <EChartCanvas
            notMerge
            option={prepared.option}
            opts={{ renderer: "canvas" }}
            style={{ height: chartHeight, width: "100%" }}
          />
        </div>
      ) : (
        <div
          className="mt-5 rounded-xl border border-dashed border-[var(--border)] bg-slate-50 px-5 py-12 text-center text-sm text-[var(--muted)]"
          role="status"
        >
          {props.emptyMessage ?? "Aucune donnée n’est disponible pour ce graphique."}
        </div>
      )}

      {!props.hideFallback && prepared.rows.length > 0 && (
        <details className="mt-4 rounded-xl border border-[var(--border)] bg-slate-50">
          <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-slate-700">
            {props.fallbackCaption ?? `Résumé accessible — ${props.title}`}
          </summary>
          <div className="grid gap-2 border-t border-[var(--border)] p-3 sm:grid-cols-2">
            {prepared.rows.slice(0, 10).map((row, rowIndex) => (
              <dl className="rounded-lg bg-white p-3 text-sm" key={rowIndex}>
                {prepared.columns.map((column) => {
                  const value = row[column.key] ?? null;
                  return (
                    <div className="flex justify-between gap-3 py-1" key={column.key}>
                      <dt className="text-[var(--muted)]">{column.label}</dt>
                      <dd className="text-right font-semibold tabular-nums">
                        {column.format ? column.format(value, row) : defaultFormat(value)}
                      </dd>
                    </div>
                  );
                })}
              </dl>
            ))}
          </div>
        </details>
      )}
    </section>
  );
}
