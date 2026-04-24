import { useState } from "react";

/**
 * Lightweight SVG chart used by the trends view.
 */

const MAX_AXIS_LABELS = 4;

type AxisLabel = {
  index: number;
  label: string;
};

/**
 * Render a compact SVG line chart for one numeric series.
 *
 * Parameters:
 *   values: Numeric values in chronological order.
 *   labels: Matching labels used for the x-axis markers.
 *   accent: Stroke color for the series.
 *   formatValue: Callback used to format values in the point tooltip.
 *
 * Returns:
 *   JSX.Element: Compact SVG line chart.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
export function TrendChart({
  values,
  comparisonValues,
  labels,
  accent,
  comparisonAccent,
  valueLabel,
  comparisonLabel,
  formatValue,
}: {
  values: number[];
  comparisonValues?: Array<number | null>;
  labels: string[];
  accent: string;
  comparisonAccent?: string;
  valueLabel?: string;
  comparisonLabel?: string | null;
  formatValue: (value: number) => string;
}) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);

  if (values.length === 0) {
    return <div className="chart-empty">No trend data in this window yet.</div>;
  }

  const width = 640;
  const height = 240;
  const padding = 24;
  const allValues = [
    ...values,
    ...(comparisonValues?.filter((value): value is number => value !== null) ?? []),
  ];
  const minValue = Math.min(...allValues);
  const maxValue = Math.max(...allValues);
  const range = maxValue - minValue || 1;

  const chartPoints = values.map((value, index) => {
    const x =
      padding + (index / Math.max(values.length - 1, 1)) * (width - padding * 2);
    const normalizedY = (value - minValue) / range;
    const y = height - padding - normalizedY * (height - padding * 2);

    return {
      x,
      y,
      value,
      label: labels[index],
    };
  });
  const comparisonPoints = comparisonValues?.map((value, index) => {
    if (value === null) {
      return null;
    }

    const x =
      padding + (index / Math.max(values.length - 1, 1)) * (width - padding * 2);
    const normalizedY = (value - minValue) / range;
    const y = height - padding - normalizedY * (height - padding * 2);

    return {
      x,
      y,
      value,
      label: labels[index],
    };
  });

  const points = chartPoints.map((point) => `${point.x},${point.y}`).join(" ");
  const comparisonPolyline = comparisonPoints
    ?.filter((point): point is NonNullable<typeof point> => point !== null)
    .map((point) => `${point.x},${point.y}`)
    .join(" ");
  const resolvedActiveIndex =
    activeIndex === null
      ? values.length - 1
      : Math.min(activeIndex, values.length - 1);
  const activePoint = chartPoints.at(resolvedActiveIndex) ?? null;
  const activeComparisonPoint =
    comparisonPoints?.at(resolvedActiveIndex) ?? null;
  const axisLabels = getTrendAxisLabels(labels);

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
        {comparisonPolyline && comparisonAccent ? (
          <polyline
            fill="none"
            stroke={comparisonAccent}
            strokeWidth="2.5"
            strokeDasharray="7 6"
            strokeLinecap="round"
            strokeLinejoin="round"
            opacity="0.85"
            points={comparisonPolyline}
          />
        ) : null}
        {chartPoints.map((point, index) => (
          <g
            key={`${point.label}-${point.value}`}
            className="trend-chart-point"
            role="button"
            tabIndex={0}
            aria-label={`Show trend value for ${point.label}`}
            onClick={() => setActiveIndex(index)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                setActiveIndex(index);
              }
            }}
          >
            <circle
              cx={point.x}
              cy={point.y}
              r="12"
              fill="transparent"
            />
            <circle
              cx={point.x}
              cy={point.y}
              r={resolvedActiveIndex === index ? 6 : 4}
              fill={accent}
              stroke={
                resolvedActiveIndex === index ? "rgba(255,255,255,0.9)" : "none"
              }
              strokeWidth="2"
            />
          </g>
        ))}
        {comparisonPoints?.map((point, index) =>
          point !== null && comparisonAccent ? (
            <circle
              key={`target-${point.label}-${index}`}
              cx={point.x}
              cy={point.y}
              r="3.5"
              fill={comparisonAccent}
              opacity="0.95"
            />
          ) : null,
        )}
        {activePoint ? (
          <TrendTooltip
            point={activePoint}
            width={width}
            height={height}
            valueLabel={valueLabel ?? "Actual"}
            formattedValue={formatValue(activePoint.value)}
            comparisonLabel={comparisonLabel}
            formattedComparisonValue={
              activeComparisonPoint ? formatValue(activeComparisonPoint.value) : null
            }
          />
        ) : null}
      </svg>

      <div className="trend-chart-labels" aria-hidden="true">
        {axisLabels.map((axisLabel) => (
          <span
            key={`${axisLabel.label}-${axisLabel.index}`}
            data-edge={
              axisLabel.index === 0
                ? "start"
                : axisLabel.index === labels.length - 1
                  ? "end"
                  : undefined
            }
            style={{
              left: `${((chartPoints[axisLabel.index]?.x ?? padding) / width) * 100}%`,
            }}
          >
            {axisLabel.label}
          </span>
        ))}
      </div>
    </div>
  );
}

/**
 * Return the visible x-axis labels for a trend chart.
 *
 * Parameters:
 *   labels: All chronological labels that correspond to plotted points.
 *
 * Returns:
 *   AxisLabel[]: A small, evenly spaced set of labels including the endpoints.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
function getTrendAxisLabels(labels: string[]): AxisLabel[] {
  if (labels.length <= MAX_AXIS_LABELS) {
    return labels.map((label, index) => ({ index, label }));
  }

  const lastIndex = labels.length - 1;
  const selectedIndexes = new Set<number>();

  for (let slot = 0; slot < MAX_AXIS_LABELS; slot += 1) {
    selectedIndexes.add(
      Math.round((slot / (MAX_AXIS_LABELS - 1)) * lastIndex),
    );
  }

  return Array.from(selectedIndexes)
    .sort((left, right) => left - right)
    .map((index) => ({
      index,
      label: labels[index],
    }));
}

/**
 * Render a small tooltip near the active trend point.
 *
 * Parameters:
 *   point: Active chart point coordinates and label.
 *   width: Full SVG width.
 *   height: Full SVG height.
 *   formattedValue: Human-readable value for the active point.
 *
 * Returns:
 *   JSX.Element: Tooltip box rendered inside the SVG.
 *
 * Raises:
 *   This component does not raise errors directly.
 */
function TrendTooltip({
  point,
  width,
  height,
  valueLabel,
  formattedValue,
  comparisonLabel,
  formattedComparisonValue,
}: {
  point: {
    x: number;
    y: number;
    value: number;
    label: string;
  };
  width: number;
  height: number;
  valueLabel: string;
  formattedValue: string;
  comparisonLabel?: string | null;
  formattedComparisonValue?: string | null;
}) {
  const tooltipWidth = 154;
  const hasComparisonRow =
    comparisonLabel !== null &&
    comparisonLabel !== undefined &&
    formattedComparisonValue !== null &&
    formattedComparisonValue !== undefined;
  const tooltipHeight = hasComparisonRow ? 82 : 58;
  const tooltipX = Math.max(
    16,
    Math.min(point.x - tooltipWidth / 2, width - tooltipWidth - 16),
  );
  const preferredTop = point.y - tooltipHeight - 14;
  const tooltipY =
    preferredTop >= 16
      ? preferredTop
      : Math.min(point.y + 14, height - tooltipHeight - 16);

  return (
    <g className="trend-chart-tooltip" pointerEvents="none">
      <rect
        x={tooltipX}
        y={tooltipY}
        width={tooltipWidth}
        height={tooltipHeight}
        rx="14"
        fill="rgba(9, 16, 20, 0.96)"
        stroke="rgba(255,255,255,0.08)"
      />
      <text x={tooltipX + 14} y={tooltipY + 20} fill="#9AA4B7" fontSize="11">
        {point.label}
      </text>
      <text
        x={tooltipX + 14}
        y={tooltipY + 40}
        fill="#F5F7FB"
        fontSize="11"
      >
        {valueLabel}
      </text>
      <text
        x={tooltipX + 64}
        y={tooltipY + 40}
        fill="#F5F7FB"
        fontSize="15"
        fontWeight="700"
      >
        {formattedValue}
      </text>
      {hasComparisonRow ? (
        <>
          <text
            x={tooltipX + 14}
            y={tooltipY + 62}
            fill="#9AA4B7"
            fontSize="11"
          >
            {comparisonLabel}
          </text>
          <text
            x={tooltipX + 64}
            y={tooltipY + 62}
            fill="#E2E8F0"
            fontSize="14"
            fontWeight="700"
          >
            {formattedComparisonValue}
          </text>
        </>
      ) : null}
    </g>
  );
}
