import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, test, vi } from "vitest";

import App from "./App";

const productsPayload = {
  items: [
    {
      id: 1,
      name: "Rolled oats",
      default_serving_g: 40,
      calories_per_100g: 384,
      carbs_g_per_100g: 66,
      protein_g_per_100g: 13,
      fat_g_per_100g: 7,
    },
  ],
};

/**
 * Build a bootstrap payload for one requested portal date.
 *
 * Parameters:
 *   targetDate: Business date to include in the mocked payload.
 *
 * Returns:
 *   object: API-shaped bootstrap payload used by the frontend tests.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
function buildBootstrapPayload(targetDate = "2026-04-16") {
  return {
    generated_at: "2026-04-16T12:00:00+00:00",
    access_protected: false,
    profile: {
      athlete_name: "Sergio",
      subject: "athlete-1",
      weight_kg: 68,
      height_cm: 170,
      ftp_watts: 260,
      profile_markdown: "# Sergio's Endurance Profile\n- Marathon focus",
      diet_goals_markdown: "Lose 0.5 kg per week",
      training_goals_markdown: "Improve cycling and running",
    },
    snapshot: {
      date: targetDate,
      summary: {
        target_date: targetDate,
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
        meals_count: 1,
        meal_items_count: 1,
        activities_count: 1,
      },
      meals: [
        {
          id: 1,
          meal_label: "Pre-training breakfast",
          notes_markdown: "Easy fuel before the run.",
          items: [
            {
              id: 1,
              product_id: 1,
              ingredient_name: "Oats (rolled)",
              grams: 30,
              calories: 115.2,
              carbs_g: 19.8,
              protein_g: 3.9,
              fat_g: 2.1,
            },
          ],
          total_calories: 115.2,
          total_carbs_g: 19.8,
          total_protein_g: 3.9,
          total_fat_g: 2.1,
        },
      ],
      activities: [
        {
          id: 1,
          title: "Around gran via",
          activity_date: targetDate,
          sport_type: "Run",
          distance_meters: 13020,
          moving_time_seconds: 3933,
          total_elevation_gain_meters: 127,
          average_heartrate: 151,
          max_heartrate: 165,
          calories: 976,
          suffer_score: 212,
          notes_markdown: "Tempo run",
          external_source: "strava",
        },
      ],
    },
    history: {
      date_from: "2026-03-20",
      date_to: targetDate,
      days: [],
    },
    trends: {
      date_from: "2026-01-24",
      date_to: targetDate,
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
}

/**
 * Mock the portal fetch flow for bootstrap and product endpoints.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   Mock instance used for later call assertions.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
function mockPortalFetch() {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const rawUrl = typeof input === "string" ? input : input.toString();
    const url = new URL(rawUrl, "http://localhost");

    if (url.pathname.endsWith("/portal/bootstrap")) {
      const targetDate =
        url.searchParams.get("target_date")?.trim() || "2026-04-16";
      return {
        ok: true,
        status: 200,
        json: async () => buildBootstrapPayload(targetDate),
      };
    }

    if (url.pathname.endsWith("/portal/products")) {
      return {
        ok: true,
        status: 200,
        json: async () => productsPayload,
      };
    }

    throw new Error(`Unexpected fetch URL: ${rawUrl}`);
  });

  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

/**
 * Mock a 401 bootstrap response for unlock-screen testing.
 *
 * Parameters:
 *   None.
 *
 * Returns:
 *   void
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
function mockUnauthorizedBootstrap() {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({
        detail: "A valid portal access token is required.",
      }),
    }),
  );
}

describe("App", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    window.sessionStorage.clear();
  });

  test("renders the updated portal shell and new nav items", async () => {
    mockPortalFetch();

    render(<App />);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Profile" })).toBeInTheDocument(),
    );

    expect(
      screen.getByRole("button", { name: "Food products" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Sergio's portal")).not.toBeInTheDocument();
    expect(screen.queryByText("Food")).not.toBeInTheDocument();
    expect(screen.getByText("Food calories")).toBeInTheDocument();
  });

  test("shows the profile view and loads products lazily", async () => {
    const fetchMock = mockPortalFetch();
    const user = userEvent.setup();

    render(<App />);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Profile" })).toBeInTheDocument(),
    );

    await user.click(screen.getByRole("button", { name: "Profile" }));
    expect(screen.getByText("Profile overview")).toBeInTheDocument();
    expect(screen.getByText("athlete-1")).toBeInTheDocument();

    expect(fetchMock).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: "Food products" }));

    await waitFor(() =>
      expect(screen.getByRole("cell", { name: "Rolled oats" })).toBeInTheDocument(),
    );

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  test("steps back one day from the date arrows", async () => {
    const fetchMock = mockPortalFetch();
    const user = userEvent.setup();

    render(<App />);

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Previous day" }),
      ).toBeInTheDocument(),
    );

    await user.click(screen.getByRole("button", { name: "Previous day" }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) =>
          url.toString().includes("target_date=2026-04-15"),
        ),
      ).toBe(true),
    );
  });

  test("toggles meal details from the collapsed accordion", async () => {
    mockPortalFetch();
    const user = userEvent.setup();

    render(<App />);

    const mealHeading = await screen.findByText("Pre-training breakfast");
    const mealCard = mealHeading.closest("details");

    expect(mealCard).not.toHaveAttribute("open");

    await user.click(mealHeading);
    expect(mealCard).toHaveAttribute("open");
    expect(screen.getByText("Oats (rolled)")).toBeInTheDocument();

    await user.click(mealHeading);
    expect(mealCard).not.toHaveAttribute("open");
  });

  test("shows the unlock screen after a 401 response", async () => {
    mockUnauthorizedBootstrap();

    render(<App />);

    await waitFor(() =>
      expect(screen.getByText("Unlock the portal")).toBeInTheDocument(),
    );
    expect(
      screen.getByPlaceholderText("Portal access token"),
    ).toBeInTheDocument();
  });
});
