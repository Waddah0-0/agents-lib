import styles from "./Mark.module.css";

/**
 * The margin mark: a page of notes in an ink tile, one line highlighted. It says what the
 * product does: agents read your code and mark the evidence. Fixed brand colours, so it looks
 * the same in light and dark mode.
 */
export function Mark({ size = 32 }: { size?: number }) {
  return (
    <svg className={styles.mark} width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="9" fill="#00574f" />
      <rect x="7" y="8.5" width="15" height="3" rx="1.5" fill="#fff8ef" opacity="0.92" />
      <rect className={styles.highlight} x="5.5" y="14" width="20" height="5" rx="2.2" fill="#ffd162" />
      <rect x="7" y="15" width="12" height="3" rx="1.5" fill="#00574f" opacity="0.85" />
      <rect x="7" y="21.5" width="10" height="3" rx="1.5" fill="#fff8ef" opacity="0.92" />
    </svg>
  );
}
