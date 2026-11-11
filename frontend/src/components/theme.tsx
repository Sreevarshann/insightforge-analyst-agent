"use client";

import { useCallback, useSyncExternalStore } from "react";

type Theme = "dark" | "light";
const EVENT = "if-theme-change";

/** Inline script (in <head>) that applies the stored/preferred theme before first paint. */
export const themeInitScript = `(function(){try{var t=localStorage.getItem("if-theme");if(t!=="light"&&t!=="dark"){t=matchMedia("(prefers-color-scheme: light)").matches?"light":"dark"}document.documentElement.dataset.theme=t}catch(e){}})()`;

function subscribe(cb: () => void) {
  window.addEventListener(EVENT, cb);
  return () => window.removeEventListener(EVENT, cb);
}
const getSnapshot = (): Theme => (document.documentElement.dataset.theme === "light" ? "light" : "dark");
const getServerSnapshot = (): Theme => "dark";

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

export function useTheme() {
  const theme = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  const toggle = useCallback(() => {
    const next: Theme = getSnapshot() === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem("if-theme", next);
    } catch {}
    window.dispatchEvent(new Event(EVENT));
  }, []);
  return { theme, toggle };
}
