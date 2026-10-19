import { NavLink } from "react-router";
import { API_URL } from "../api/client";
import { useTheme } from "../lib/theme";
import { Icon } from "./Icon";
import type { IconName } from "./icons";
import { Mark } from "./Mark";
import styles from "./NavRail.module.css";

const ITEMS: { to: string; icon: IconName; label: string; end: boolean }[] = [
  { to: "/", icon: "home", label: "Home", end: true },
  { to: "/agents", icon: "widgets", label: "Agents", end: false },
  { to: "/runs", icon: "history", label: "Runs", end: false },
];

const THEME_ICON = { system: "systemTheme", light: "lightMode", dark: "darkMode" } as const;
const THEME_LABEL = { system: "Theme: system", light: "Theme: light", dark: "Theme: dark" } as const;

export function NavRail() {
  const [theme, cycleTheme] = useTheme();
  return (
    <nav className={styles.rail} aria-label="Main">
      <NavLink to="/" className={styles.brand} aria-label="Agents Library home" viewTransition>
        <Mark size={32} />
      </NavLink>
      <ul className={styles.items}>
        {ITEMS.map((item) => (
          <li key={item.to}>
            <NavLink to={item.to} end={item.end} className={styles.item} viewTransition>
              {({ isActive }) => (
                <>
                  <span className={styles.indicator}>
                    <Icon name={item.icon} duotone={isActive} />
                  </span>
                  <span className={styles.label}>{item.label}</span>
                </>
              )}
            </NavLink>
          </li>
        ))}
        <li>
          <a className={styles.item} href={`${API_URL}/docs`} target="_blank" rel="noreferrer">
            <span className={styles.indicator}>
              <Icon name="api" />
            </span>
            <span className={styles.label}>API</span>
          </a>
        </li>
      </ul>
      <button type="button" className={styles.theme} onClick={cycleTheme} title={THEME_LABEL[theme]}>
        <Icon name={THEME_ICON[theme]} />
        <span className="visually-hidden">{THEME_LABEL[theme]}</span>
      </button>
    </nav>
  );
}
