import type { IconName } from "./icons";

/** A Material Symbols Rounded icon. Outlined by default; filled when `fill` is set. */
export function Icon({
  name,
  fill = false,
  size,
  className,
}: {
  name: IconName;
  fill?: boolean;
  size?: number;
  className?: string;
}) {
  return (
    <span
      className={["material-symbols-rounded", name === "progress_activity" && "spin", className]
        .filter(Boolean)
        .join(" ")}
      data-fill={fill}
      style={size ? { fontSize: size } : undefined}
      aria-hidden="true"
    >
      {name}
    </span>
  );
}
