/**
 * The AI Code Detector's intro on its agent page: what it reads, how it weighs the
 * evidence, and why the answer is a range. The home page stays about the whole library.
 */
import { EvidenceSheet } from "../../components/EvidenceSheet";
import { Icon } from "../../components/Icon";
import styles from "./intro.module.css";

const METHODOLOGY = "https://github.com/Waddah0-0/margin/blob/main/docs/methodology.md";

export function DetectorIntro() {
  return (
    <section className={styles.intro} aria-label="How the AI Code Detector works">
      <div className={styles.art}>
        <EvidenceSheet />
      </div>
      <h2 className={styles.title}>
        How it <span className="marker">reads code</span>
      </h2>
      <ol className={styles.steps}>
        <li>
          <b>A local model reads a sample of files</b> and points at lines that suggest AI or a person. The
          quotes come from the file itself, never from the model.
        </li>
        <li>
          <b>Every Python, JavaScript and TypeScript file is checked</b> for habits such as comments that
          restate the code or leftover debugging.
        </li>
        <li>
          <b>The answer is a range, not a verdict</b>, with a confidence level and the reasons for it.
          Evidence for and against is shown side by side.
        </li>
      </ol>
      <p className={styles.caveat}>
        It estimates; it never proves. Use it to start a conversation, not to accuse anyone.
      </p>
      <a className={styles.link} href={METHODOLOGY} target="_blank" rel="noreferrer">
        How it scores, and how well it did in testing
        <Icon name="open" size={16} />
      </a>
    </section>
  );
}
