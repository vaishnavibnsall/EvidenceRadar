import { useMemo, useState, type ReactNode } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import "./components.css";

export type SortDirection = "asc" | "desc";

export interface Column<T> {
  key: string;
  header: ReactNode;
  render: (row: T) => ReactNode;
  align?: "left" | "center" | "right";
  /** Enables client-side sorting for this column. */
  sortValue?: (row: T) => string | number | null;
  wrap?: boolean;
}

export interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  /** Initial client-side sort (column key + direction). */
  initialSort?: { key: string; direction: SortDirection };
  onRowClick?: (row: T) => void;
  className?: string;
}

function compareValues(a: string | number, b: string | number, direction: SortDirection): number {
  const sign = direction === "asc" ? 1 : -1;
  if (typeof a === "number" && typeof b === "number") return (a - b) * sign;
  return String(a).localeCompare(String(b)) * sign;
}

/**
 * Generic table: sticky header, zebra rows, optional sortable headers and
 * clickable rows. Sorting is client-side within the current page of data.
 */
export function DataTable<T>({
  columns,
  rows,
  rowKey,
  initialSort,
  onRowClick,
  className,
}: DataTableProps<T>) {
  const [sort, setSort] = useState<{ key: string; direction: SortDirection } | null>(
    initialSort ?? null,
  );

  const sortedRows = useMemo(() => {
    if (!sort) return rows;
    const column = columns.find((c) => c.key === sort.key);
    if (!column?.sortValue) return rows;
    const getter = column.sortValue;
    return [...rows].sort((a, b) => {
      const av = getter(a);
      const bv = getter(b);
      if (av === null || av === undefined) return 1;
      if (bv === null || bv === undefined) return -1;
      return compareValues(av, bv, sort.direction);
    });
  }, [rows, sort, columns]);

  const toggleSort = (key: string) => {
    setSort((prev) => {
      if (prev?.key !== key) return { key, direction: "desc" };
      if (prev.direction === "desc") return { key, direction: "asc" };
      return null; // third click clears sorting
    });
  };

  return (
    <div className="table-scroll">
      <table className={`data-table${className ? ` ${className}` : ""}`}>
        <thead>
          <tr>
            {columns.map((column) => {
              const active = sort?.key === column.key;
              const alignClass = column.align ? ` align-${column.align}` : "";
              const ariaSort = active
                ? sort?.direction === "asc"
                  ? "ascending"
                  : "descending"
                : undefined;
              return (
                <th key={column.key} className={alignClass.trim() || undefined} aria-sort={ariaSort}>
                  {column.sortValue ? (
                    <button
                      type="button"
                      className={`th__sort${active ? " th__sort--active" : ""}`}
                      onClick={() => toggleSort(column.key)}
                      title={`Sort by ${typeof column.header === "string" ? column.header : column.key}`}
                    >
                      {column.header}
                      {active ? (
                        sort?.direction === "asc" ? (
                          <ChevronUp size={13} aria-hidden />
                        ) : (
                          <ChevronDown size={13} aria-hidden />
                        )
                      ) : null}
                    </button>
                  ) : (
                    column.header
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sortedRows.map((row) => (
            <tr
              key={rowKey(row)}
              className={onRowClick ? "row-clickable" : undefined}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              onKeyDown={
                onRowClick
                  ? (event) => {
                      if (event.key === "Enter") onRowClick(row);
                    }
                  : undefined
              }
              tabIndex={onRowClick ? 0 : undefined}
            >
              {columns.map((column) => {
                const alignClass = column.align ? ` align-${column.align}` : "";
                const wrapClass = column.wrap ? " wrap" : "";
                return (
                  <td
                    key={column.key}
                    className={(alignClass + wrapClass).trim() || undefined}
                  >
                    {column.render(row)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
