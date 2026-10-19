import { useId } from "react";
import { shapePath } from "./AgentShape";

const CLOVER = shapePath({ lobes: 4, depth: 0.2, turn: 45 });

/** The app mark: an M3 clover filled with a soft blend of Google's four colours. */
export function Mark({ size = 32 }: { size?: number }) {
  const id = useId().replaceAll(":", "");
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" aria-hidden="true">
      <defs>
        <clipPath id={`clip${id}`}>
          <path d={CLOVER} />
        </clipPath>
        <filter id={`blur${id}`} x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="14" />
        </filter>
      </defs>
      <g clipPath={`url(#clip${id})`}>
        <rect width="100" height="100" fill="#4285f4" />
        <g filter={`url(#blur${id})`}>
          <circle cx="18" cy="20" r="34" fill="#4285f4" />
          <circle cx="84" cy="22" r="30" fill="#ea4335" />
          <circle cx="82" cy="84" r="30" fill="#fbbc04" />
          <circle cx="18" cy="84" r="30" fill="#34a853" />
        </g>
      </g>
    </svg>
  );
}
