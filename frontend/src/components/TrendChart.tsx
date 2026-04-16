/**
 * Lightweight SVG chart used by the trends view.
 */

/**
 * Render a compact SVG line chart for one numeric series.
 *
 * Parameters:
 *   values: Numeric values in chronological order.
 *   labels: Matching labels used for the x-axis markers.
 *   accent: Stroke color for the series.
 *
 * Returns:
 *   JSX.Element: Compact SVG line chart.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
export function TrendChart({
  values,
  labels,
  accent,
}: {
  values: number[];
  labels: string[];
  accent: string;
}) {
  if (values.length === 0) {
    return <div className="chart-empty">No trend data in this window yet.</div>;
  }

  const width = 640;
  const height = 240;
  const padding = 24;
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const range = maxValue - minValue || 1;

  const points = values
    .map((value, index) => {
      const x =
        padding +
        (index / Math.max(values.length - 1, 1)) * (width - padding * 2);
      const normalizedY = (value - minValue) / range;
      const y = height - padding - normalizedY * (height - padding * 2);
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <div className="trend-chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Trend chart">
        <rect
          width={width}
          height={height}
          rx="24"
          fill="rgba(255,255,255,0.02)"
        />
        <polyline
          fill="none"
          stroke={accent}
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
          points={points}
        />
        {values.map((value, index) => {
          const x =
            padding +
            (index / Math.max(values.length - 1, 1)) * (width - padding * 2);
          const normalizedY = (value - minValue) / range;
          const y = height - padding - normalizedY * (height - padding * 2);

          return (
            <circle
              key={`${labels[index]}-${value}`}
              cx={x}
              cy={y}
              r="4"
              fill={accent}
            />
          );
        })}
      </svg>

      <div className="trend-chart-labels">
        {labels.map((label) => (
          <span key={label}>{label}</span>
        ))}
      </div>
    </div>
  );
}
