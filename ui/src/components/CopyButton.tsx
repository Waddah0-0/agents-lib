import { useEffect, useState } from "react";
import { IconButton } from "./Button";

/** Copies `text`; the icon turns into a check for a moment to confirm. */
export function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (!copied) return;
    const timer = setTimeout(() => setCopied(false), 1600);
    return () => clearTimeout(timer);
  }, [copied]);
  return (
    <IconButton
      icon={copied ? "check" : "content_copy"}
      label={copied ? "Copied" : label}
      onClick={() => navigator.clipboard?.writeText(text).then(() => setCopied(true))}
    />
  );
}
