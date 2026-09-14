"use client";

/**
 * The theme toggle hook (dark-mode-first). Persists ONLY the theme
 * preference in localStorage — never any credential material
 * (non-negotiable #9). The inline script in the root layout applies
 * the class before paint to avoid a flash.
 */

import { useCallback, useEffect, useState } from "react";

export type Theme = "dark" | "light";
const STORAGE_KEY = "adcos-theme";

function currentTheme(): Theme {
  if (typeof document === "undefined") return "dark";
  return document.documentElement.classList.contains("light") ? "light" : "dark";
}

export function useTheme(): { theme: Theme; toggleTheme: () => void } {
  const [theme, setTheme] = useState<Theme>("dark");

  useEffect(() => {
    setTheme(currentTheme());
  }, []);

  const toggleTheme = useCallback(() => {
    const next: Theme = currentTheme() === "light" ? "dark" : "light";
    document.documentElement.classList.toggle("light", next === "light");
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Storage may be unavailable; the toggle still works for the session.
    }
    setTheme(next);
  }, []);

  return { theme, toggleTheme };
}
