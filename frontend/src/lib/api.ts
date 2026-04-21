/**
 * Small fetch helpers for the APEX progress portal backend.
 */

export interface PortalProfile {
  athlete_name: string;
  subject: string;
  weight_kg: number | null;
  height_cm: number | null;
  ftp_watts: number | null;
  profile_markdown: string;
  diet_goals_markdown: string;
  training_goals_markdown: string;
}

export interface FoodProduct {
  id: string;
  name: string;
  default_serving_g: number | null;
  calories_per_100g: number;
  carbs_g_per_100g: number;
  protein_g_per_100g: number;
  fat_g_per_100g: number;
  usage: ProductUsageSummary;
}

export interface ProductUsageSummary {
  total_usage_occurrences: number;
  total_usage_days: number;
  total_grams: number;
  total_calories: number;
  window_usage_occurrences: number;
  window_usage_days: number;
  window_total_grams: number;
  window_total_calories: number;
  first_used_on: string | null;
  last_used_on: string | null;
}

export interface FoodProductsResponse {
  window_date_from: string;
  window_date_to: string;
  window_days: number;
  items: FoodProduct[];
}

export interface ProductUsageTrendDay {
  date: string;
  usage_occurrences: number;
  total_grams: number;
  total_calories: number;
}

export interface ProductUsageTrendSummary {
  logged_days: number;
  total_usage_occurrences: number;
  total_grams: number;
  total_calories: number;
  last_used_on: string | null;
}

export interface ProductUsageTrendsResponse {
  product_id: string;
  date_from: string;
  date_to: string;
  days: ProductUsageTrendDay[];
  summary: ProductUsageTrendSummary;
}

export interface DailySummary {
  target_date: string;
  target_food_calories: number | null;
  target_exercise_calories: number | null;
  target_protein_g: number | null;
  target_carbs_g: number | null;
  target_fat_g: number | null;
  actual_food_calories: number;
  actual_exercise_calories: number;
  actual_protein_g: number;
  actual_carbs_g: number;
  actual_fat_g: number;
  remaining_food_calories: number | null;
  remaining_protein_g: number | null;
  remaining_carbs_g: number | null;
  remaining_fat_g: number | null;
  net_calories: number;
  meals_count: number;
  meal_items_count: number;
  activities_count: number;
}

export interface MealItem {
  id: string;
  product_id: string | null;
  ingredient_name: string;
  grams: number;
  calories: number;
  carbs_g: number;
  protein_g: number;
  fat_g: number;
}

export interface Meal {
  id: string;
  meal_label: string;
  notes_markdown: string;
  items: MealItem[];
  total_calories: number;
  total_carbs_g: number;
  total_protein_g: number;
  total_fat_g: number;
}

export interface Activity {
  id: string;
  title: string;
  activity_date: string;
  sport_type: string | null;
  distance_meters: number | null;
  moving_time_seconds: number | null;
  total_elevation_gain_meters: number | null;
  average_heartrate: number | null;
  max_heartrate: number | null;
  calories: number | null;
  suffer_score: number | null;
  notes_markdown: string;
  external_source: string | null;
}

export interface DailySnapshot {
  date: string;
  summary: DailySummary;
  meals: Meal[];
  activities: Activity[];
}

export interface HistoryDay {
  date: string;
  target_food_calories: number | null;
  target_protein_g: number | null;
  target_carbs_g: number | null;
  target_fat_g: number | null;
  actual_food_calories: number;
  actual_exercise_calories: number;
  net_calories: number;
  actual_protein_g: number;
  actual_carbs_g: number;
  actual_fat_g: number;
  meals_count: number;
  meal_items_count: number;
  activities_count: number;
  total_distance_meters: number;
  total_moving_time_seconds: number;
  total_elevation_gain_meters: number;
  total_suffer_score: number;
}

export interface HistoryResponse {
  date_from: string;
  date_to: string;
  days: HistoryDay[];
}

export interface TrendSummary {
  logged_days: number;
  average_food_calories: number;
  average_exercise_calories: number;
  total_distance_meters: number;
  total_activities: number;
}

export interface TrendsResponse {
  date_from: string;
  date_to: string;
  days: HistoryDay[];
  summary: TrendSummary;
}

export interface BootstrapResponse {
  generated_at: string;
  profile: PortalProfile;
  snapshot: DailySnapshot;
  history: HistoryResponse;
  trends: TrendsResponse;
  access_protected: boolean;
}

const DEFAULT_API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

/**
 * Fetch one API endpoint and decode the JSON payload.
 *
 * Parameters:
 *   path: API path relative to the configured backend base URL.
 *   accessToken: Optional portal token forwarded as a bearer token.
 *
 * Returns:
 *   Promise<T>: Parsed JSON payload for the requested endpoint.
 *
 * Raises:
 *   Error: Raised when the backend returns a non-success response.
 */
async function requestJson<T>(
  path: string,
  accessToken: string | null,
): Promise<T> {
  const response = await fetch(`${DEFAULT_API_BASE_URL}${path}`, {
    headers: buildHeaders(accessToken),
  });

  if (!response.ok) {
    const detail = await extractErrorDetail(response);
    const error = new Error(
      detail || `Request failed with status ${response.status}.`,
    );
    Object.assign(error, { status: response.status });
    throw error;
  }

  return (await response.json()) as T;
}

/**
 * Build the request headers for one API call.
 *
 * Parameters:
 *   accessToken: Optional portal token forwarded as a bearer token.
 *
 * Returns:
 *   HeadersInit: Headers object for `fetch`.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
function buildHeaders(accessToken: string | null): HeadersInit {
  if (!accessToken) {
    return {};
  }

  return {
    Authorization: `Bearer ${accessToken}`,
  };
}

/**
 * Read the best available error detail from a failed response.
 *
 * Parameters:
 *   response: Failed `fetch` response.
 *
 * Returns:
 *   Promise<string>: Human-readable error detail when available.
 *
 * Raises:
 *   This helper does not raise errors directly.
 */
async function extractErrorDetail(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    return payload.detail ?? "";
  } catch {
    return "";
  }
}

/**
 * Load the combined bootstrap payload used by the React portal.
 *
 * Parameters:
 *   targetDate: Business date to load in the main day view.
 *   historyDays: Number of days to include in the history window.
 *   trendDays: Number of days to include in the trends window.
 *   accessToken: Optional portal access token.
 *
 * Returns:
 *   Promise<BootstrapResponse>: Combined shell, day, history, and trend data.
 *
 * Raises:
 *   Error: Raised when the backend request fails.
 */
export async function getBootstrap(
  targetDate: string,
  historyDays: number,
  trendDays: number,
  accessToken: string | null,
): Promise<BootstrapResponse> {
  const searchParams = new URLSearchParams({
    history_days: String(historyDays),
    trend_days: String(trendDays),
  });

  if (targetDate.trim()) {
    searchParams.set("target_date", targetDate);
  }

  return requestJson<BootstrapResponse>(
    `/portal/bootstrap?${searchParams.toString()}`,
    accessToken,
  );
}

/**
 * Load the reusable food product catalog for the current portal subject.
 *
 * Parameters:
 *   accessToken: Optional portal access token.
 *
 * Returns:
 *   Promise<FoodProductsResponse>: Product rows used by the table view.
 *
 * Raises:
 *   Error: Raised when the backend request fails.
 */
export async function getProducts(
  accessToken: string | null,
  dateTo: string,
  windowDays: number,
): Promise<FoodProductsResponse> {
  const searchParams = new URLSearchParams({
    window_days: String(windowDays),
  });

  if (dateTo.trim()) {
    searchParams.set("date_to", dateTo);
  }

  return requestJson<FoodProductsResponse>(
    `/portal/products?${searchParams.toString()}`,
    accessToken,
  );
}

/**
 * Load the day-level usage trend for one reusable food product.
 *
 * Parameters:
 *   productId: Product identifier to aggregate.
 *   dateTo: Inclusive upper date bound for the trend window.
 *   days: Number of days to include.
 *   accessToken: Optional portal access token.
 *
 * Returns:
 *   Promise<ProductUsageTrendsResponse>: Daily usage series and summary.
 *
 * Raises:
 *   Error: Raised when the backend request fails.
 */
export async function getProductUsageTrends(
  productId: string,
  dateTo: string,
  days: number,
  accessToken: string | null,
): Promise<ProductUsageTrendsResponse> {
  const searchParams = new URLSearchParams({
    product_id: productId,
    days: String(days),
  });

  if (dateTo.trim()) {
    searchParams.set("date_to", dateTo);
  }

  return requestJson<ProductUsageTrendsResponse>(
    `/portal/product-usage/trends?${searchParams.toString()}`,
    accessToken,
  );
}
