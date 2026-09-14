"use client";

/**
 * AppearancePanel — the theme preference. It is the ONLY thing the
 * console persists (a UI setting, never a secret).
 */

import { useTheme } from "@/lib/design/theme";
import { cn } from "@/lib/utils";

export function AppearancePanel() {
  const { theme, setTheme } = useTheme();
  return (
    <div role="group" aria-label="Theme" className="flex gap-2">
      {(["dark", "light"] as const).map((option) => (
        <button
          key={option}
          type="button"
          aria-pressed={theme === option}
          onClick={() => setTheme(option)}
          className={cn(
            "rounded border px-3 py-1.5 text-sm",
            theme === option
              ? "border-accent bg-raised text-ink"
              : "border-line text-ink-muted hover:text-ink",
          )}
        >
          {option === "dark" ? "Dark" : "Light"}
        </button>
      ))}
    </div>
  );
}
