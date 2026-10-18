import { ChevronLeft, ChevronRight } from "lucide-react";
import { formatInt } from "../utils/format";
import "./components.css";

interface PaginationProps {
  offset: number;
  limit: number;
  total: number;
  onChange: (offset: number) => void;
}

export function Pagination({ offset, limit, total, onChange }: PaginationProps) {
  const page = Math.floor(offset / limit) + 1;
  const pages = Math.max(1, Math.ceil(total / limit));
  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + limit, total);

  return (
    <div className="pagination">
      <span className="pagination__info">
        Showing {formatInt(from)}–{formatInt(to)} of {formatInt(total)}
      </span>
      <div className="pagination__controls">
        <button
          type="button"
          className="btn"
          onClick={() => onChange(Math.max(0, offset - limit))}
          disabled={offset === 0}
        >
          <ChevronLeft size={15} aria-hidden />
          Prev
        </button>
        <span className="pagination__page">
          Page {formatInt(page)} / {formatInt(pages)}
        </span>
        <button
          type="button"
          className="btn"
          onClick={() => onChange(offset + limit)}
          disabled={to >= total}
        >
          Next
          <ChevronRight size={15} aria-hidden />
        </button>
      </div>
    </div>
  );
}
