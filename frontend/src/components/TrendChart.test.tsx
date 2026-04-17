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
});
