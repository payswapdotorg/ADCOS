"use client";

/**
 * The command palette — the console's keyboard navigation surface
 * (spec: "the palette is how an expert moves").
 *
 * Presentational by contract: it receives `items` (with ready-made
 * `onExecute` closures), filters them with the shared fuzzy matcher,
 * renders a combobox + listbox pair, and reports execution/close back
 * through `onOpenChange`. Navigation and side effects belong to the
 * mount layer (features/search/command-palette-mount), not here.
 *
 * Top-positioned Radix Dialog (spec: the palette appears near the top,
 * never center-screen). Escape closes; focus returns to the trigger
 * (Radix default); the active option follows ArrowUp/ArrowDown with
 * wrap-around and scrolls into view.
 */

import * as Dialog from "@radix-ui/react-dialog";
import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
} from "react";
import { SearchIcon } from "@/components/ui";
import { fuzzyMatch } from "@/features/search/fuzzy";
import { cn } from "@/lib/utils";

/** One palette row. `section` drives the Recent grouping. */
export interface PaletteItem {
  id: string;
  title: string;
  section: "commands" | "recent";
  icon?: ReactNode;
  keywords?: string[];
  href?: string;
  onExecute?: () => void;
}

export interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  items: PaletteItem[];
  placeholder?: string;
}

export function CommandPalette({
  open,
  onOpenChange,
  items,
  placeholder,
}: CommandPaletteProps) {
  const baseId = useId();
  const listboxId = `${baseId}-results`;
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const listRef = useRef<HTMLUListElement>(null);

  // every open starts from a clean query + first item active
  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
    }
  }, [open]);

  /** The visible items: empty query shows everything (commands first,
   * then recents — the mount layer's order); otherwise fuzzy-filtered,
   * score-descending with an alphabetical tiebreak. */
  const visible = useMemo<PaletteItem[]>(() => {
    const trimmed = query.trim();
    if (trimmed.length === 0) return items;
    return items
      .map((item) => {
        const haystack = [item.title, ...(item.keywords ?? [])].join(" ");
        return { item, score: fuzzyMatch(trimmed, haystack) };
      })
      .filter((entry): entry is { item: PaletteItem; score: number } => entry.score !== null)
      .sort(
        (a, b) => b.score - a.score || a.item.title.localeCompare(b.item.title),
      )
      .map((entry) => entry.item);
  }, [items, query]);

  const activeIndex = visible.length === 0 ? 0 : Math.min(active, visible.length - 1);

  // keep the active option in view as the keyboard moves through the list
  useEffect(() => {
    const list = listRef.current;
    if (!list) return;
    const element = list.querySelector<HTMLElement>(
      `[data-palette-index="${activeIndex}"]`,
    );
    if (element && typeof element.scrollIntoView === "function") {
      element.scrollIntoView({ block: "nearest" });
    }
  }, [activeIndex, visible]);

  function execute(item: PaletteItem): void {
    item.onExecute?.();
    onOpenChange(false);
  }

  function handleKeyDown(event: ReactKeyboardEvent<HTMLInputElement>): void {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive(visible.length === 0 ? 0 : (activeIndex + 1) % visible.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive(visible.length === 0 ? 0 : (activeIndex - 1 + visible.length) % visible.length);
    } else if (event.key === "Enter") {
      event.preventDefault();
      const item = visible[activeIndex];
      if (item) execute(item);
    }
  }

  // build the rows once: a "Recent" header before the first visible recent
  const rows: ReactNode[] = [];
  let recentHeaderRendered = false;
  for (let index = 0; index < visible.length; index += 1) {
    const item = visible[index];
    if (item.section === "recent" && !recentHeaderRendered) {
      recentHeaderRendered = true;
      rows.push(
        <li
          key="palette-recent-header"
          aria-hidden="true"
          className="px-3 pb-1 pt-2 text-2xs uppercase tracking-wide text-ink-faint"
        >
          Recent
        </li>,
      );
    }
    rows.push(
      <li
        key={item.id}
        id={`${baseId}-option-${index}`}
        role="option"
        aria-selected={index === activeIndex}
        data-palette-index={index}
        onMouseEnter={() => setActive(index)}
        onClick={() => execute(item)}
        className={cn(
          "flex cursor-pointer select-none items-center gap-2.5 rounded px-3 py-1.5 text-sm",
          index === activeIndex ? "bg-raised text-ink" : "text-ink-muted",
        )}
      >
        {item.icon ? <span className="flex shrink-0 items-center">{item.icon}</span> : null}
        <span className="truncate">{item.title}</span>
      </li>,
    );
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-canvas/70 backdrop-blur-[2px]" />
        <Dialog.Content className="fixed left-1/2 top-[15%] z-50 w-[92vw] max-w-lg -translate-x-1/2 overflow-hidden rounded-md border border-line bg-overlay shadow-[var(--shadow-panel)]">
          <Dialog.Title className="sr-only">Command palette</Dialog.Title>
          <Dialog.Description className="sr-only">
            Search registered commands and recently visited objects; Enter navigates.
          </Dialog.Description>

          <div className="flex items-center gap-2.5 border-b border-line px-3.5">
            <SearchIcon className="h-4 w-4 shrink-0 text-ink-faint" />
            <input
              role="combobox"
              aria-expanded="true"
              aria-controls={listboxId}
              aria-activedescendant={
                visible.length > 0 ? `${baseId}-option-${activeIndex}` : undefined
              }
              aria-label="Search commands and objects"
              aria-autocomplete="list"
              autoFocus
              value={query}
              placeholder={placeholder ?? "Search commands and objects…"}
              onChange={(event) => {
                setQuery(event.target.value);
                setActive(0);
              }}
              onKeyDown={handleKeyDown}
              className="h-10 flex-1 bg-transparent text-sm text-ink outline-none placeholder:text-ink-faint"
            />
            <kbd className="shrink-0 rounded border border-line px-1.5 py-px font-mono text-2xs text-ink-faint">
              esc
            </kbd>
          </div>

          <ul
            ref={listRef}
            id={listboxId}
            role="listbox"
            aria-label="Results"
            className="max-h-72 overflow-y-auto p-1"
          >
            {visible.length === 0 ? (
              <li className="px-3 py-6 text-center text-sm text-ink-faint">No matches</li>
            ) : (
              rows
            )}
          </ul>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
