import { useCallback, useState } from "react";

export type Theme = "system" | "light" | "dark";

const ORDER: Theme[] = ["system", "light", "dark"];

function read(): Theme {
  try {
    const saved = localStorage.getItem("theme");
    return saved === "light" || saved === "dark" ? saved : "system";
  } catch {
    return "system";
  }
}

function apply(theme: Theme) {
  const root = document.documentElement;
  if (theme === "system") delete root.dataset.theme;
  else root.dataset.theme = theme;
  try {
    if (theme === "system") localStorage.removeItem("theme");
    else localStorage.setItem("theme", theme);
  } catch {
    // private mode: the choice lasts until the page closes
  }
}

/** The colour theme, cycled system → light → dark, with a cross-fade where supported. */
export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(read);
  const cycle = useCallback(() => {
    const next = ORDER[(ORDER.indexOf(theme) + 1) % ORDER.length] as Theme;
    const change = () => {
      apply(next);
      setTheme(next);
    };
    if (document.startViewTransition) document.startViewTransition(change);
    else change();
  }, [theme]);
  return [theme, cycle];
}
