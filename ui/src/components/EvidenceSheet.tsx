/**
 * The home page illustration: a sheet of code with two lines highlighted and margin notes,
 * one for and one against, on top of a small stack of other sheets. It shows, without words,
 * what every agent does: read, mark the evidence, weigh both sides.
 */
import styles from "./EvidenceSheet.module.css";
import { Minimap } from "./Minimap";

export function EvidenceSheet() {
  return (
    <figure className={styles.stack} aria-hidden="true">
      <div className={`${styles.sheet} ${styles.back2}`} />
      <div className={`${styles.sheet} ${styles.back1}`}>
        <Minimap seed="tests/test_api.py" rows={20} />
      </div>
      <div className={`${styles.sheet} ${styles.front}`}>
        <div className={styles.head}>
          <span className={styles.file}>src/report.py</span>
          <span className={styles.score}>0.71</span>
        </div>
        <Minimap seed="src/report.py" rows={20} highlights={[3, 9]} className={styles.code} />
        <span className={`${styles.note} ${styles.noteFor}`}>
          <b>+0.42</b> comment restates the code
        </span>
        <span className={`${styles.note} ${styles.noteAgainst}`}>
          <b>−0.18</b> hand-tuned constant
        </span>
      </div>
    </figure>
  );
}
