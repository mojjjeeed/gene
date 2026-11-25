"use client";

import { useCallback, useEffect, useSyncExternalStore } from "react";

export type Theme = "light" | "dark";

const STORAGE_KEY = "BIORESEARCH_THEME";
const listeners = new Set<() => void>();

// In-memory fallback so the toggle still works when localStorage is blocked (private mode, etc.)
let override: Theme | null = null;

function readTheme(): Theme {
  if (override) return override;
  try {
    return localStorage.getItem(STORAGE_KEY) === "dark" ? "dark" : "light";
  } catch {
    return "light";
  }
}

function subscribe(onChange: () => void) {
  listeners.add(onChange);
  const onStorage = (e: StorageEvent) => {
    if (e.key === STORAGE_KEY) {
      override = null;
      onChange();
    }
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(onChange);
    window.removeEventListener("storage", onStorage);
  };
}

/**
 * Theme state persisted in localStorage, synced across tabs, and hydration-safe
 * (server renders "light", the client switches after hydration if the user chose dark).
 */
export function useTheme() {
  const theme = useSyncExternalStore<Theme>(subscribe, readTheme, () => "light");

  const toggle = useCallback(() => {
    const next: Theme = readTheme() === "dark" ? "light" : "dark";
    override = next;
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* storage unavailable - in-memory override keeps the session working */
    }
    listeners.forEach((l) => l());
  }, []);

  // Mirror onto <html> so the page background, scrollbars and native controls follow the theme.
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    document.documentElement.style.colorScheme = theme;
  }, [theme]);

  return { theme, toggle };
}
