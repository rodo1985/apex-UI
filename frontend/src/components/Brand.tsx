import type { CSSProperties } from "react";

const COLORS = {
  teal: "#2DD4BF",
  dark: "#0D1411",
  white: "#F5F7FB",
};

/**
 * Render the APEX icon used across the portal shell and empty states.
 *
 * Parameters:
 *   size: Square icon size in pixels.
 *   mode: Visual mode for the background and stroke treatment.
 *
 * Returns:
 *   JSX.Element: Branded APEX heart-and-signal icon.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
export function ApexIcon({
  size = 56,
  mode = "dark",
}: {
  size?: number;
  mode?: "dark" | "light" | "naked";
}) {
  const stroke = mode === "light" ? COLORS.dark : COLORS.teal;
  const fill = mode === "light" ? COLORS.dark : COLORS.teal;
  const showBackground = mode !== "naked";

  return (
    <svg width={size} height={size} viewBox="0 0 72 72" fill="none" aria-hidden="true">
      {showBackground ? (
        <rect
          width="72"
          height="72"
          rx="18"
          fill={mode === "light" ? COLORS.white : COLORS.dark}
        />
      ) : null}
      <path
        d="M36 55 C35 55 13 42 13 28 C13 20.5 19 15 26 15 C30.5 15 34 17.5 36 21 C38 17.5 41.5 15 46 15 C53 15 59 20.5 59 28 C59 42 37 55 36 55 Z"
        fill={fill}
        fillOpacity={showBackground ? 0.1 : 0.15}
        stroke={stroke}
        strokeWidth="2"
      />
      <polyline
        points="18,36 24,36 29,28 33,46 36,22 39,46 44,32 48,36 54,36"
        fill="none"
        stroke={stroke}
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/**
 * Render the APEX wordmark.
 *
 * Parameters:
 *   size: Font size in pixels.
 *   style: Optional inline style override.
 *
 * Returns:
 *   JSX.Element: Styled APEX wordmark.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
export function ApexWordmark({
  size = 28,
  style,
}: {
  size?: number;
  style?: CSSProperties;
}) {
  return (
    <span className="apex-wordmark" style={{ fontSize: size, ...style }}>
      APE<span className="apex-wordmark-accent">X</span>
    </span>
  );
}

/**
 * Render the APEX icon and wordmark together.
 *
 * Parameters:
 *   size: Icon size in pixels.
 *   wordmarkSize: Wordmark font size in pixels.
 *   mode: Visual mode for the icon and text treatment.
 *
 * Returns:
 *   JSX.Element: Reusable APEX brand lockup.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
export function ApexLockup({
  size = 34,
  wordmarkSize = 22,
  mode = "dark",
}: {
  size?: number;
  wordmarkSize?: number;
  mode?: "dark" | "light" | "naked";
}) {
  return (
    <div className="apex-lockup">
      <ApexIcon size={size} mode={mode} />
      <ApexWordmark
        size={wordmarkSize}
        style={{ color: mode === "light" ? "#0A0B0D" : "#F5F7FB" }}
      />
    </div>
  );
}
