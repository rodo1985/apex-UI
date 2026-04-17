/**
 * Shared formatting helpers for the APEX progress portal UI.
 */

/**
 * Format an ISO date into a readable long label.
 *
 * Parameters:
 *   isoDate: ISO calendar date such as `2026-04-16`.
 *
 * Returns:
 *   string: Localized long date label.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
export function formatLongDate(isoDate: string): string {
  return new Intl.DateTimeFormat(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(new Date(`${isoDate}T00:00:00`));
}

/**
 * Format an ISO date into a short month-day label.
 *
 * Parameters:
 *   isoDate: ISO calendar date such as `2026-04-16`.
 *
 * Returns:
 *   string: Compact month-day label.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
export function formatShortDate(isoDate: string): string {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
  }).format(new Date(`${isoDate}T00:00:00`));
}

/**
 * Format a numeric value as rounded calories.
 *
 * Parameters:
 *   value: Numeric calorie value.
 *
 * Returns:
 *   string: Rounded calorie label.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
export function formatCalories(value: number | null): string {
  if (value === null) {
    return "No target";
  }

  return `${Math.round(value).toLocaleString()} kcal`;
}

/**
 * Format an optional signed delta with an explicit plus/minus prefix.
 *
 * Parameters:
 *   value: Numeric delta to format.
 *   suffix: Unit suffix to append.
 *
 * Returns:
 *   string: Signed rounded delta label.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
export function formatSignedValue(value: number | null, suffix: string): string {
  if (value === null) {
    return "No target";
  }

  const rounded = Math.round(value);
  const prefix = rounded > 0 ? "+" : "";
  return `${prefix}${rounded.toLocaleString()} ${suffix}`;
}

/**
 * Format meters into a kilometer string.
 *
 * Parameters:
 *   meters: Optional distance in meters.
 *
 * Returns:
 *   string: Distance label in kilometers.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
export function formatDistance(meters: number | null): string {
  if (meters === null || meters === 0) {
    return "0 km";
  }

  return `${(meters / 1000).toFixed(meters >= 10000 ? 1 : 2)} km`;
}

/**
 * Format seconds into an `h m` duration label.
 *
 * Parameters:
 *   seconds: Optional duration in seconds.
 *
 * Returns:
 *   string: Readable duration label.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
export function formatDuration(seconds: number | null): string {
  if (seconds === null || seconds <= 0) {
    return "0 min";
  }

  const totalMinutes = Math.round(seconds / 60);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;

  if (hours === 0) {
    return `${minutes} min`;
  }

  return `${hours} h ${minutes} min`;
}

/**
 * Format markdown into a compact plain-text excerpt.
 *
 * Parameters:
 *   markdown: Source markdown string.
 *   maxLength: Maximum number of characters to keep.
 *
 * Returns:
 *   string: Plain-text excerpt suitable for small UI blocks.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
export function markdownToExcerpt(markdown: string, maxLength = 180): string {
  const plainText = markdown
    .replace(/^#+\s?/gm, "")
    .replace(/\*\*/g, "")
    .replace(/^- /gm, "")
    .replace(/\n+/g, " ")
    .trim();

  if (plainText.length <= maxLength) {
    return plainText;
  }

  return `${plainText.slice(0, maxLength).trimEnd()}...`;
}

/**
 * Return today's date in `YYYY-MM-DD` format for the browser locale.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   string: Current browser-local ISO date.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
export function todayIsoDate(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

/**
 * Shift an ISO calendar date by a whole number of days.
 *
 * Parameters:
 *   isoDate: Source date in `YYYY-MM-DD` format.
 *   deltaDays: Signed number of days to add to the source date.
 *
 * Returns:
 *   string: Shifted date in `YYYY-MM-DD` format.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
export function shiftIsoDate(isoDate: string, deltaDays: number): string {
  const shiftedDate = new Date(`${isoDate}T00:00:00`);
  shiftedDate.setDate(shiftedDate.getDate() + deltaDays);

  const year = shiftedDate.getFullYear();
  const month = String(shiftedDate.getMonth() + 1).padStart(2, "0");
  const day = String(shiftedDate.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}
