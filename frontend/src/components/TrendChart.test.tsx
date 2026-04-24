import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test } from "vitest";

import { TrendChart } from "./TrendChart";

describe("TrendChart", () => {
  test("shows the clicked day value and target overlay in the chart tooltip", async () => {
    const user = userEvent.setup();

    render(
      <TrendChart
        values={[120, 180, 150]}
        comparisonValues={[150, 175, 160]}
        labels={["Apr 14", "Apr 15", "Apr 16"]}
        accent="#16A34A"
        comparisonAccent="#CBD5E1"
        valueLabel="Achieved"
        comparisonLabel="Target"
        formatValue={(value) => `${value} kcal`}
      />,
    );

    await user.click(screen.getByLabelText("Show trend value for Apr 14"));

    expect(screen.getByText("120 kcal")).toBeInTheDocument();
    expect(screen.getByText("150 kcal")).toBeInTheDocument();
    expect(screen.getByText("Target")).toBeInTheDocument();
  });

  test("keeps a long mobile trend window from rendering every axis label", () => {
    const labels = Array.from({ length: 84 }, (_, index) => `Day ${index + 1}`);

    const { container } = render(
      <TrendChart
        values={labels.map((_, index) => index + 100)}
        comparisonValues={labels.map(() => 180)}
        labels={labels}
        accent="#16A34A"
        comparisonAccent="#CBD5E1"
        valueLabel="Achieved"
        comparisonLabel="Target"
        formatValue={(value) => `${value} kcal`}
      />,
    );

    const visibleAxisLabels = container.querySelectorAll(
      ".trend-chart-labels span",
    );
    const visibleAxisLabelText = Array.from(visibleAxisLabels).map(
      (labelElement) => labelElement.textContent,
    );

    expect(visibleAxisLabels).toHaveLength(4);
    expect(visibleAxisLabelText).toContain("Day 1");
    expect(visibleAxisLabelText).toContain("Day 84");
    expect(
      screen.getByLabelText("Show trend value for Day 84"),
    ).toBeInTheDocument();
  });
});
