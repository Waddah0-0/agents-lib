import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from "react";
import { Link, type LinkProps } from "react-router";
import styles from "./Button.module.css";
import { Icon } from "./Icon";
import type { IconName } from "./icons";

export type ButtonVariant = "filled" | "tonal" | "outlined" | "text" | "elevated";

interface Common {
  variant?: ButtonVariant;
  icon?: IconName;
  trailingIcon?: IconName;
  size?: "s" | "m" | "l";
  children?: ReactNode;
}

function classes(variant: ButtonVariant, size: string, extra?: string) {
  return [styles.button, styles[variant], styles[size], extra].filter(Boolean).join(" ");
}

function Content({ icon, trailingIcon, children }: Pick<Common, "icon" | "trailingIcon" | "children">) {
  return (
    <>
      {icon && <Icon name={icon} className={styles.icon} />}
      {children !== undefined && <span className={styles.label}>{children}</span>}
      {trailingIcon && <Icon name={trailingIcon} className={styles.icon} />}
    </>
  );
}

export function Button({
  variant = "filled",
  size = "m",
  icon,
  trailingIcon,
  children,
  className,
  type = "button",
  ...rest
}: Common & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button type={type} className={classes(variant, size, className)} {...rest}>
      <Content icon={icon} trailingIcon={trailingIcon}>
        {children}
      </Content>
    </button>
  );
}

export function LinkButton({
  variant = "filled",
  size = "m",
  icon,
  trailingIcon,
  children,
  className,
  ...rest
}: Common & LinkProps) {
  return (
    <Link className={classes(variant, size, typeof className === "string" ? className : undefined)} {...rest}>
      <Content icon={icon} trailingIcon={trailingIcon}>
        {children}
      </Content>
    </Link>
  );
}

export function AnchorButton({
  variant = "text",
  size = "m",
  icon,
  trailingIcon,
  children,
  className,
  ...rest
}: Common & AnchorHTMLAttributes<HTMLAnchorElement>) {
  return (
    <a className={classes(variant, size, className)} {...rest}>
      <Content icon={icon} trailingIcon={trailingIcon}>
        {children}
      </Content>
    </a>
  );
}

export function IconButton({
  icon,
  label,
  variant = "standard",
  selected,
  className,
  type = "button",
  ...rest
}: {
  icon: IconName;
  label: string;
  variant?: "standard" | "tonal" | "outlined" | "filled";
  selected?: boolean;
} & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type={type}
      className={[styles.iconButton, styles[`icon-${variant}`], className].filter(Boolean).join(" ")}
      aria-label={label}
      title={label}
      aria-pressed={selected}
      {...rest}
    >
      <Icon name={icon} fill={selected} />
    </button>
  );
}
