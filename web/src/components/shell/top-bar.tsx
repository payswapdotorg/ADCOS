"use client";

/**
 * The top bar — environment truth on the left, search + session on the
 * right. The palette trigger reports the platform-detected hotkey and
 * opens the SHARED palette state owned by the AppShell (never a second
 * store). Dense by design: one h-12 row, hairline bottom border, calm
 * canvas with blur so long pages scroll under it without noise.
 */

import { SearchIcon } from "@/components/ui";
import { COMMAND_PALETTE_HINT } from "@/lib/design/tokens";
import { EnvironmentIndicator } from "./environment-indicator";
import { SessionMenu } from "./session-menu";

export interface TopBarProps {
  /** Opens the command palette (state lives in the AppShell). */
  onOpenPalette: () => void;
}

export function TopBar({ onOpenPalette }: TopBarProps) {
  return (
    <header className="sticky top-0 z-20 border-b border-line bg-canvas/90 backdrop-blur">
      <div className="flex h-12 items-center justify-between gap-3 px-gutter">
        <EnvironmentIndicator />

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onOpenPalette}
            aria-label="Open command palette"
            className="flex h-8 items-center gap-2 rounded border border-line bg-raised px-2.5 text-sm text-ink-muted hover:border-line-strong hover:text-ink"
          >
            <SearchIcon className="h-3.5 w-3.5 shrink-0" />
            <span className="hidden sm:inline">Search</span>
            <kbd className="rounded border border-line-strong px-1 py-px font-mono text-2xs text-ink-faint">
              {COMMAND_PALETTE_HINT}
            </kbd>
          </button>
          <SessionMenu />
        </div>
      </div>
    </header>
  );
}
