import { ICONS, type IconName } from "./icons";

/**
 * An icon, sized by the surrounding font size (1em) unless `size` is given. Regular weight by
 * default; `fill` for a selected state, `duotone` for the active navigation item.
 */
export function Icon({
  name,
  fill = false,
  duotone = false,
  size,
  className,
}: {
  name: IconName;
  fill?: boolean;
  duotone?: boolean;
  size?: number;
  className?: string;
}) {
  const Svg = ICONS[name];
  return (
    <Svg
      className={["icon", name === "spinner" && "spin", className].filter(Boolean).join(" ")}
      weight={fill ? "fill" : duotone ? "duotone" : "regular"}
      size={size ?? "1em"}
      aria-hidden="true"
    />
  );
}
