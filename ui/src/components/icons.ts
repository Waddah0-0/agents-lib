/**
 * Every Material Symbol the UI uses. The icon font is subset to exactly these
 * (scripts/fetch-fonts.mjs), so an icon must be added here before it can be used;
 * the IconName type makes TypeScript enforce that.
 */
export const ICONS = [
  "api",
  "arrow_back",
  "arrow_drop_down",
  "arrow_forward",
  "arrow_outward",
  "block",
  "check",
  "check_circle",
  "chevron_right",
  "close",
  "cloud_off",
  "content_copy",
  "contrast",
  "dark_mode",
  "data_object",
  "deployed_code",
  "download",
  "error",
  "expand_more",
  "explore_off",
  "forum",
  "history",
  "home",
  "hourglass_disabled",
  "info",
  "light_mode",
  "neurology",
  "payments",
  "play_arrow",
  "progress_activity",
  "refresh",
  "replay",
  "schedule",
  "search_off",
  "timer",
  "token",
  "tune",
  "unfold_more",
  "warning",
  "widgets",
] as const;

export type IconName = (typeof ICONS)[number];
