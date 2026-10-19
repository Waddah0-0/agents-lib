/**
 * The loading indicator: three lines of a page, highlighted one after another, over and over,
 * like someone skimming for the part that matters.
 */
import styles from "./Loading.module.css";

export function LoadingIndicator({ size = 48, label = "Loading" }: { size?: number; label?: string }) {
  return (
    <span className={styles.wrap} role="progressbar" aria-label={label} style={{ width: size, height: size }}>
      <span className={styles.line} style={{ width: "72%" }} />
      <span className={styles.line} style={{ width: "54%" }} />
      <span className={styles.line} style={{ width: "64%" }} />
    </span>
  );
}

/** A whole-page loading state, centred. */
export function PageLoading({ label }: { label?: string }) {
  return (
    <div className={styles.page}>
      <LoadingIndicator size={56} label={label} />
    </div>
  );
}
