import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";

import App from "./App";

const bootstrapPayload = {
  generated_at: "2026-04-16T12:00:00+00:00",
  access_protected: false,
  profile: {
    athlete_name: "Sergio",
    subject: "athlete-1",
    weight_kg: 68,
    height_cm: 170,
    ftp_watts: 260,
    profile_markdown: "# Sergio's Endurance Profile",
    diet_goals_markdown: "Lose 0.5 kg per week",
    training_goals_markdown: "Improve cycling and running",
  },
  snapshot: {
    date: "2026-04-16",
    summary: {
      target_date: "2026-04-16",
      target_food_calories: 2490,
      target_exercise_calories: 976,
      target_protein_g: 150,
      target_carbs_g: 290,
      target_fat_g: 68,
      actual_food_calories: 725,
      actual_exercise_calories: 976,
      actual_protein_g: 42,
      actual_carbs_g: 115,
      actual_fat_g: 12,
      remaining_food_calories: 1765,
      remaining_protein_g: 108,
      remaining_carbs_g: 175,
      remaining_fat_g: 56,
      net_calories: -251,
      meals_count: 2,
      meal_items_count: 10,
      activities_count: 1,
    },
    meals: [],
    activities: [],
  },
  history: {
    date_from: "2026-03-20",
    date_to: "2026-04-16",
    days: [],
  },
  trends: {
    date_from: "2026-01-24",
    date_to: "2026-04-16",
    days: [],
    summary: {
      logged_days: 1,
      average_food_calories: 725,
      average_exercise_calories: 976,
      total_distance_meters: 13020,
      total_activities: 1,
    },
  },
};

/**
 * Provide common fetch mocking for portal component tests.
 *
 * Parameters:
 *   payload: Mock JSON payload returned by `fetch`.
 *   status: HTTP status code used by the mock response.
 *
 * Returns:
 *   void
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
function mockFetchWithPayload(payload: unknown, status = 200) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: status >= 200 && status < 300,
      status,
      json: async () => payload,
    }),
  );
}

describe("App", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    window.sessionStorage.clear();
  });

  test("renders the loaded portal shell", async () => {
    mockFetchWithPayload(bootstrapPayload);

    render(<App />);

    await waitFor(() =>
      expect(screen.getByText("Sergio's portal")).toBeInTheDocument(),
    );
    expect(screen.getByText("Food")).toBeInTheDocument();
  });

  test("shows the unlock screen after a 401 response", async () => {
    mockFetchWithPayload(
      { detail: "A valid portal access token is required." },
      401,
    );

    render(<App />);

    await waitFor(() =>
      expect(screen.getByText("Unlock the portal")).toBeInTheDocument(),
    );
    expect(
      screen.getByPlaceholderText("Portal access token"),
    ).toBeInTheDocument();
  });
});
