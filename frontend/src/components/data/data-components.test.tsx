import type { ColumnDef } from "@tanstack/react-table";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AccessibleEChart } from "./accessible-echart";
import { DataTable } from "./data-table";

vi.mock("echarts-for-react", () => ({
  default: () => <div data-testid="echarts-canvas" />,
}));

afterEach(cleanup);

describe("AccessibleEChart", () => {
  it("keeps an accessible card summary available for simple series", async () => {
    render(
      <AccessibleEChart
        categories={["North", "South"]}
        description="Applications received by operating area."
        series={[{ name: "Applications", data: [14, 8] }]}
        title="Demand by area"
      />,
    );

    expect(screen.getByRole("heading", { name: "Demand by area" })).toBeVisible();
    const fallback = screen.getByText("Résumé accessible — Demand by area").closest("details");
    expect(fallback).not.toBeNull();
    expect(within(fallback!).getAllByText("Applications")[0]).toBeInTheDocument();
    expect(within(fallback!).getByText("14")).toBeInTheDocument();
    expect(await screen.findByTestId("echarts-canvas")).toBeInTheDocument();
  });

  it("renders an explicit empty state without fabricating a summary", () => {
    render(
      <AccessibleEChart
        categories={[]}
        description="Average processing time by agency."
        emptyMessage="No delay observations."
        series={[]}
        title="Processing delays"
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent("No delay observations.");
    expect(screen.queryByText("Résumé accessible — Processing delays")).not.toBeInTheDocument();
  });
});

interface AgencyRow {
  id: string;
  agency: string;
  applications: number;
}

const columns: ColumnDef<AgencyRow, unknown>[] = [
  { accessorKey: "agency", header: "Agency" },
  { accessorKey: "applications", header: "Applications" },
];

describe("DataTable", () => {
  it("sorts and paginates bounded drill-down rows", () => {
    render(
      <DataTable
        caption="Agency drill-down"
        columns={columns}
        data={[
          { id: "a", agency: "Ariana", applications: 8 },
          { id: "b", agency: "Bizerte", applications: 14 },
        ]}
        getRowId={(row) => row.id}
        initialPageSize={1}
        pageSizeOptions={[1, 2]}
      />,
    );

    const collection = screen
      .getByRole("heading", { name: "Agency drill-down" })
      .closest("section");
    expect(collection).not.toBeNull();
    expect(within(collection!).getByText("Ariana")).toBeVisible();
    expect(within(collection!).queryByText("Bizerte")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Page suivante" }));
    expect(within(collection!).getByText("Bizerte")).toBeVisible();

    fireEvent.change(screen.getByLabelText("Fiches par page"), { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: "Applications" }));
    expect(within(collection!).getAllByRole("article")[0]).toHaveTextContent("Bizerte");
    fireEvent.click(screen.getByRole("button", { name: "Applications" }));
    expect(within(collection!).getAllByRole("article")[0]).toHaveTextContent("Ariana");
  });

  it("announces loading and renders an explicit empty state", () => {
    const { rerender } = render(
      <DataTable caption="Applications" columns={columns} data={[]} loading />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Chargement des fiches…");

    rerender(<DataTable caption="Applications" columns={columns} data={[]} />);
    expect(screen.getByText("Aucune fiche ne correspond aux filtres sélectionnés.")).toBeVisible();
  });
});
