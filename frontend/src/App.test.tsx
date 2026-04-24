import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, test, vi } from "vitest";

import App from "./App";

const productsPayload = {
  items: [
    {
      id: "food-2",
      name: "Almond butter",
      default_serving_g: 20,
      calories_per_100g: 614,
      carbs_g_per_100g: 19,
      protein_g_per_100g: 21,
      fat_g_per_100g: 56,
      usage_count: 9,
    },
    {
      id: "food-1",
      name: "Rolled oats",
      default_serving_g: 40,
      calories_per_100g: 384,
      carbs_g_per_100g: 66,
      protein_g_per_100g: 13,
      fat_g_per_100g: 7,
      usage_count: 22,
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
  const daySummary = {
    date: targetDate,
    target_food_calories: 2490,
    target_protein_g: 150,
    target_carbs_g: 290,
    target_fat_g: 68,
    actual_food_calories: 725,
    actual_exercise_calories: 976,
    net_calories: -251,
    actual_protein_g: 42,
    actual_carbs_g: 115,
    actual_fat_g: 12,
    meals_count: 1,
    meal_items_count: 1,
    activities_count: 1,
    total_distance_meters: 13020,
    total_moving_time_seconds: 3933,
    total_elevation_gain_meters: 127,
    total_suffer_score: 212,
  };

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
          id: "meal-1",
          meal_label: "Pre-training breakfast",
          notes_markdown: "Easy fuel before the run.",
          items: [
            {
              id: "meal-item-1",
              product_id: "food-1",
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
          id: "activity-1",
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
      days: [daySummary],
    },
    trends: {
      date_from: "2026-01-24",
      date_to: targetDate,
      days: [
        {
          ...daySummary,
          date: "2026-04-14",
          actual_food_calories: 640,
          actual_exercise_calories: 812,
          actual_protein_g: 104,
          actual_carbs_g: 201,
          actual_fat_g: 51,
          total_suffer_score: 180,
        },
        {
          ...daySummary,
          date: "2026-04-15",
          actual_food_calories: 701,
          actual_exercise_calories: 930,
          actual_protein_g: 132,
          actual_carbs_g: 248,
          actual_fat_g: 59,
          total_suffer_score: 236,
        },
        daySummary,
      ],
      daily_metrics: [
        {
          metric_type: "sleep_hours",
          points: [
            { date: "2026-04-14", value: 7.68 },
            { date: "2026-04-15", value: 7.93 },
            { date: "2026-04-16", value: 7.38 },
          ],
        },
      ],
      summary: {
        logged_days: 3,
        average_food_calories: 689,
        average_exercise_calories: 906,
        total_distance_meters: 39060,
        total_activities: 3,
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
 * Read the authorization header used by the first mocked fetch call.
 *
 * Parameters:
 *   fetchMock: Mocked global fetch function.
 *
 * Returns:
 *   string | null: Bearer authorization header when present.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
function getAuthorizationHeader(fetchMock: ReturnType<typeof vi.fn>): string | null {
  const init = fetchMock.mock.calls[0]?.[1];
  if (!init || typeof init !== "object") {
    return null;
  }

  const headers = Reflect.get(init, "headers");
  if (!headers || typeof headers !== "object") {
    return null;
  }

  return Reflect.get(headers, "Authorization") as string | null;
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

  test("uses the configured dev token when session storage is empty", async () => {
    const fetchMock = mockPortalFetch();

    render(<App />);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Profile" })).toBeInTheDocument(),
    );

    expect(getAuthorizationHeader(fetchMock)).toBe(
      `Bearer ${import.meta.env.VITE_PORTAL_ACCESS_TOKEN}`,
    );
  });

  test("renders the updated portal shell and new nav items", async () => {
    mockPortalFetch();

    render(<App />);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Profile" })).toBeInTheDocument(),
    );

    const navigation = screen.getByRole("navigation", { name: "Portal sections" });
    const navLabels = within(navigation)
      .getAllByRole("button")
      .map((button) => button.textContent?.trim());

    expect(navLabels).toEqual([
      "Today",
      "Trends",
      "Food products",
      "History",
      "Profile",
    ]);
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
    expect(screen.queryByText("athlete-1")).not.toBeInTheDocument();

    expect(fetchMock).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: "Food products" }));

    await waitFor(() =>
      expect(screen.getByRole("cell", { name: "Rolled oats" })).toBeInTheDocument(),
    );

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  test("requests the new trend windows from the toolbar", async () => {
    const fetchMock = mockPortalFetch();
    const user = userEvent.setup();

    render(<App />);

    await user.click(await screen.findByRole("button", { name: "Trends" }));
    expect(screen.getByRole("button", { name: "7d" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "30d" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "90d" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "365d" })).toBeInTheDocument();

    expect(fetchMock.mock.calls[0]?.[0].toString()).toContain("trend_days=90");

    await user.click(screen.getByRole("button", { name: "7d" }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) =>
          url.toString().includes("trend_days=7"),
        ),
      ).toBe(true),
    );
  });

  test("toggles the desktop sidebar from the shell menu button", async () => {
    mockPortalFetch();
    const user = userEvent.setup();

    const { container } = render(<App />);

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Collapse navigation menu" }),
      ).toBeInTheDocument(),
    );

    await user.click(
      screen.getByRole("button", { name: "Collapse navigation menu" }),
    );
    expect(container.querySelector(".portal-shell")).toHaveClass(
      "sidebar-collapsed",
    );

    await user.click(screen.getByRole("button", { name: "Expand navigation menu" }));
    expect(container.querySelector(".portal-shell")).toHaveClass("sidebar-open");
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
    expect(mealCard?.querySelector(".meal-summary-copy p")).toBeNull();

    await user.click(mealHeading);
    expect(mealCard).toHaveAttribute("open");
    expect(screen.getByText("Ingredient breakdown")).toBeInTheDocument();
    expect(screen.getByText("Oats (rolled)")).toBeInTheDocument();

    await user.click(mealHeading);
    expect(mealCard).not.toHaveAttribute("open");
  });

  test("shows training load in the activity card", async () => {
    mockPortalFetch();

    render(<App />);

    await waitFor(() =>
      expect(screen.getByText("Training load")).toBeInTheDocument(),
    );
    expect(screen.getByText("212")).toBeInTheDocument();
  });

  test("filters and sorts food products with the toolbar controls", async () => {
    mockPortalFetch();
    const user = userEvent.setup();

    render(<App />);

    await user.click(await screen.findByRole("button", { name: "Food products" }));

    const searchInput = await screen.findByPlaceholderText("Search by food or brand");
    expect(screen.getByLabelText("Sort")).toBeInTheDocument();
    expect(screen.getByLabelText("Direction")).toBeInTheDocument();
    const columnHeaders = screen
      .getAllByRole("columnheader")
      .map((header) => header.textContent?.replace(/\s+/g, " ").trim());

    expect(columnHeaders).toEqual([
      "Name",
      "Default serving",
      "Calories/100g",
      "Carbs/100g",
      "Protein/100g",
      "Fat/100g",
      "Usedtimes",
    ]);

    await user.type(searchInput, "oats");
    expect(screen.getByRole("cell", { name: "Rolled oats" })).toBeInTheDocument();
    expect(screen.queryByRole("cell", { name: "Almond butter" })).not.toBeInTheDocument();

    await user.clear(searchInput);
    await user.selectOptions(screen.getByLabelText("Sort"), "calories_per_100g");
    await user.selectOptions(screen.getByLabelText("Direction"), "desc");

    const dataRows = screen.getAllByRole("row").slice(1);
    expect(within(dataRows[0]).getByRole("cell", { name: "Almond butter" })).toBeInTheDocument();
    expect(within(dataRows[1]).getByRole("cell", { name: "22" })).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Sort"), "usage_count");

    const usageSortedRows = screen.getAllByRole("row").slice(1);
    expect(within(usageSortedRows[0]).getByRole("cell", { name: "Rolled oats" })).toBeInTheDocument();
  });

  test("renders history nutrition chips and trend metric toggles", async () => {
    mockPortalFetch();
    const user = userEvent.setup();

    render(<App />);

    await user.click(await screen.findByRole("button", { name: "History" }));
    await screen.findByText("725 / 2,490 kcal");
    expect(screen.getByText("42 / 150 g")).toBeInTheDocument();
    expect(screen.getByText("115 / 290 g")).toBeInTheDocument();
    expect(screen.getByText("12 / 68 g")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Trends" }));
    expect(screen.getByRole("button", { name: "Carbs intake" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Fat intake" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sleep hours" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Sleep hours" }));
    expect(screen.getByRole("heading", { name: "Sleep hours" })).toBeInTheDocument();
    expect(screen.getByText("7.4 h")).toBeInTheDocument();
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
