import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AdcosApiError } from "@/lib/api/errors";
import { DataTable, type Column } from "@/components/ui/data-table";

interface Row {
  id: string;
  name: string;
  count: number;
}

// deliberately unsorted: proves sorting, not input order, drives output
const rows: Row[] = [
  { id: "row-c", name: "gamma", count: 3 },
  { id: "row-a", name: "alpha", count: 1 },
  { id: "row-b", name: "beta", count: 2 },
];

const columns: Column<Row>[] = [
  {
    key: "id",
    header: "ID",
    render: (row) => <span className="font-mono">{row.id}</span>,
  },
  { key: "name", header: "Name", sortable: true, accessor: (row) => row.name },
  {
    key: "count",
    header: "Count",
    sortable: true,
    accessor: (row) => row.count,
    align: "right",
  },
];

const rowKeys = (container: HTMLElement): string[] =>
  Array.from(
    container.querySelectorAll<HTMLElement>("tbody tr[data-row-key]"),
  ).map((tr) => tr.dataset.rowKey ?? "");

const rowElements = (container: HTMLElement): HTMLElement[] =>
  Array.from(
    container.querySelectorAll<HTMLElement>("tbody tr[data-row-key]"),
  );

describe("DataTable", () => {
  it("renders the rows with a sticky-headered table", () => {
    const { container } = render(
      <DataTable rows={rows} columns={columns} getRowKey={(row) => row.id} />,
    );
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByText("gamma")).toBeInTheDocument();
    expect(screen.getByText("alpha")).toBeInTheDocument();
    expect(screen.getByText("beta")).toBeInTheDocument();
    expect(rowKeys(container)).toEqual(["row-c", "row-a", "row-b"]);
    const thead = container.querySelector("thead");
    expect(thead?.className).toContain("sticky");
  });

  it("sorts asc then desc when a sortable header is clicked", async () => {
    const user = userEvent.setup();
    const { container } = render(
      <DataTable rows={rows} columns={columns} getRowKey={(row) => row.id} />,
    );
    const nameHeader = screen.getByRole("button", { name: /name/i });
    await user.click(nameHeader);
    expect(rowKeys(container)).toEqual(["row-a", "row-b", "row-c"]);
    expect(
      screen.getByRole("columnheader", { name: /name/i }),
    ).toHaveAttribute("aria-sort", "ascending");

    await user.click(nameHeader);
    expect(rowKeys(container)).toEqual(["row-c", "row-b", "row-a"]);
    expect(
      screen.getByRole("columnheader", { name: /name/i }),
    ).toHaveAttribute("aria-sort", "descending");
  });

  it("sorts via Enter and Space on the focused header button", async () => {
    const user = userEvent.setup();
    const { container } = render(
      <DataTable rows={rows} columns={columns} getRowKey={(row) => row.id} />,
    );
    const countHeader = screen.getByRole("button", { name: /count/i });
    countHeader.focus();
    await user.keyboard("{Enter}");
    expect(rowKeys(container)).toEqual(["row-a", "row-b", "row-c"]); // 1, 2, 3
    await user.keyboard(" ");
    expect(rowKeys(container)).toEqual(["row-c", "row-b", "row-a"]); // 3, 2, 1
  });

  it("moves row focus with ArrowDown/ArrowUp and activates with Enter", async () => {
    const user = userEvent.setup();
    const onRowActivate = vi.fn();
    const { container } = render(
      <DataTable
        rows={rows}
        columns={columns}
        getRowKey={(row) => row.id}
        onRowActivate={onRowActivate}
        rowAriaLabel={(row) => `row ${row.name}`}
      />,
    );
    const elements = rowElements(container);
    elements[0].focus();
    expect(elements[0]).toHaveFocus();

    await user.keyboard("{ArrowDown}");
    expect(rowElements(container)[1]).toHaveFocus();
    await user.keyboard("{ArrowUp}");
    expect(rowElements(container)[0]).toHaveFocus();
    await user.keyboard("{ArrowDown}");
    await user.keyboard("{ArrowDown}");
    expect(rowElements(container)[2]).toHaveFocus();

    await user.keyboard("{Enter}");
    expect(onRowActivate).toHaveBeenCalledTimes(1);
    expect(onRowActivate).toHaveBeenCalledWith(rows[2]);
    expect(rowElements(container)[2]).toHaveAttribute("aria-selected", "true");
  });

  it("renders six skeleton rows under aria-busy while loading", () => {
    const { container } = render(
      <DataTable
        rows={rows}
        columns={columns}
        getRowKey={(row) => row.id}
        loading
      />,
    );
    expect(screen.getByRole("table")).toHaveAttribute("aria-busy", "true");
    expect(container.querySelectorAll("tbody tr")).toHaveLength(6);
    expect(
      container.querySelectorAll("tbody tr[data-row-key]"),
    ).toHaveLength(0);
    expect(container.querySelector(".animate-pulse")).toBeInTheDocument();
    expect(screen.queryByText("gamma")).not.toBeInTheDocument();
  });

  it("shows the empty state when there are no rows", () => {
    render(
      <DataTable
        rows={[]}
        columns={columns}
        getRowKey={(row) => row.id}
        emptyTitle="No leases yet"
        emptyDescription="Grant a lease to see it here."
      />,
    );
    expect(screen.getByText("No leases yet")).toBeInTheDocument();
    expect(screen.getByText("Grant a lease to see it here.")).toBeInTheDocument();
  });

  it("shows the ErrorState with the VERBATIM reason and retry", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    const error = new AdcosApiError({
      status: 404,
      reason: "resource-unknown",
      message: "no such contract",
      request: { method: "GET", path: "/api/2.0/contracts/nope" },
    });
    render(
      <DataTable
        rows={rows}
        columns={columns}
        getRowKey={(row) => row.id}
        error={error}
        onRetry={onRetry}
      />,
    );
    expect(screen.getByTestId("error-reason")).toHaveTextContent(
      /^resource-unknown$/,
    );
    await user.click(screen.getByRole("button", { name: /retry/i }));
    expect(onRetry).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("gamma")).not.toBeInTheDocument();
  });
});
