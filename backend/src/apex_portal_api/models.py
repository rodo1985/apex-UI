"""Typed API models for the APEX progress portal."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class PortalProfile(BaseModel):
    """Describe the athlete context shown in the portal header.

    Parameters:
        athlete_name: Display name for the athlete.
        subject: Supabase/MCP subject bound to the portal.
        weight_kg: Current body weight when available.
        height_cm: Current height when available.
        ftp_watts: Current cycling FTP when available.
        profile_markdown: Raw profile document from the APEX MCP schema.
        diet_goals_markdown: Raw diet goals document from the schema.
        training_goals_markdown: Raw training goals document from the schema.

    Returns:
        PortalProfile: Serializable athlete context for the portal.

    Raises:
        This model does not raise errors directly.
    """

    athlete_name: str
    subject: str
    weight_kg: float | None = None
    height_cm: float | None = None
    ftp_watts: int | None = None
    profile_markdown: str = ""
    diet_goals_markdown: str = ""
    training_goals_markdown: str = ""


class DailySummary(BaseModel):
    """Represent one day's target-vs-actual summary.

    Parameters:
        target_date: Business date covered by the summary.
        target_food_calories: Planned food calories.
        target_exercise_calories: Planned exercise calories.
        target_protein_g: Planned protein target.
        target_carbs_g: Planned carbohydrate target.
        target_fat_g: Planned fat target.
        actual_food_calories: Logged food calories.
        actual_exercise_calories: Logged exercise calories.
        actual_protein_g: Logged protein grams.
        actual_carbs_g: Logged carbohydrate grams.
        actual_fat_g: Logged fat grams.
        remaining_food_calories: Remaining food calories against the target.
        remaining_protein_g: Remaining protein grams against the target.
        remaining_carbs_g: Remaining carbohydrate grams against the target.
        remaining_fat_g: Remaining fat grams against the target.
        net_calories: Food calories minus exercise calories.
        meals_count: Number of meal headers logged that day.
        meal_items_count: Number of meal items logged that day.
        activities_count: Number of activities logged that day.

    Returns:
        DailySummary: Serializable daily review metrics.

    Raises:
        This model does not raise errors directly.
    """

    target_date: date
    target_food_calories: float | None = None
    target_exercise_calories: float | None = None
    target_protein_g: float | None = None
    target_carbs_g: float | None = None
    target_fat_g: float | None = None
    actual_food_calories: float = 0
    actual_exercise_calories: float = 0
    actual_protein_g: float = 0
    actual_carbs_g: float = 0
    actual_fat_g: float = 0
    remaining_food_calories: float | None = None
    remaining_protein_g: float | None = None
    remaining_carbs_g: float | None = None
    remaining_fat_g: float | None = None
    net_calories: float = 0
    meals_count: int = 0
    meal_items_count: int = 0
    activities_count: int = 0


class MealItem(BaseModel):
    """Describe one logged food item inside a meal.

    Parameters:
        id: Meal-item identifier.
        product_id: Optional reusable product identifier.
        ingredient_name: Display name shown to the athlete.
        grams: Logged serving size in grams.
        calories: Logged calories for the serving.
        carbs_g: Logged carbohydrate grams.
        protein_g: Logged protein grams.
        fat_g: Logged fat grams.

    Returns:
        MealItem: Serializable meal-item detail.

    Raises:
        This model does not raise errors directly.
    """

    id: int
    product_id: int | None = None
    ingredient_name: str
    grams: float
    calories: float
    carbs_g: float
    protein_g: float
    fat_g: float


class Meal(BaseModel):
    """Describe one meal header and its logged items.

    Parameters:
        id: Meal identifier.
        meal_label: Free-text meal label.
        notes_markdown: Optional meal note.
        items: Logged meal items.
        total_calories: Total calories for the meal.
        total_carbs_g: Total carbohydrate grams for the meal.
        total_protein_g: Total protein grams for the meal.
        total_fat_g: Total fat grams for the meal.

    Returns:
        Meal: Serializable meal detail with computed totals.

    Raises:
        This model does not raise errors directly.
    """

    id: int
    meal_label: str
    notes_markdown: str = ""
    items: list[MealItem] = Field(default_factory=list)
    total_calories: float = 0
    total_carbs_g: float = 0
    total_protein_g: float = 0
    total_fat_g: float = 0


class Activity(BaseModel):
    """Describe one logged activity entry.

    Parameters:
        id: Activity identifier.
        title: Human-readable activity title.
        activity_date: Business date for the activity.
        sport_type: Optional sport label such as `Run`.
        distance_meters: Optional distance in meters.
        moving_time_seconds: Optional moving duration in seconds.
        total_elevation_gain_meters: Optional elevation gain in meters.
        average_heartrate: Optional average heart rate.
        max_heartrate: Optional max heart rate.
        calories: Optional exercise calories.
        suffer_score: Optional training-load marker.
        notes_markdown: Optional free-text notes.
        external_source: Optional external provider such as `strava`.

    Returns:
        Activity: Serializable activity detail.

    Raises:
        This model does not raise errors directly.
    """

    id: int
    title: str
    activity_date: date
    sport_type: str | None = None
    distance_meters: float | None = None
    moving_time_seconds: int | None = None
    total_elevation_gain_meters: float | None = None
    average_heartrate: float | None = None
    max_heartrate: float | None = None
    calories: float | None = None
    suffer_score: float | None = None
    notes_markdown: str = ""
    external_source: str | None = None


class DailySnapshot(BaseModel):
    """Combine one day's summary, meals, and activities.

    Parameters:
        date: Business date shown on the portal.
        summary: Target-vs-actual daily summary.
        meals: Meals logged for the date.
        activities: Activities logged for the date.

    Returns:
        DailySnapshot: Full detail needed for the "Today" review view.

    Raises:
        This model does not raise errors directly.
    """

    date: date
    summary: DailySummary
    meals: list[Meal] = Field(default_factory=list)
    activities: list[Activity] = Field(default_factory=list)


class HistoryDay(BaseModel):
    """Describe one day inside the history and trend timelines.

    Parameters:
        date: Business date represented by the row.
        target_food_calories: Planned food calories.
        actual_food_calories: Logged food calories.
        actual_exercise_calories: Logged exercise calories.
        net_calories: Food calories minus exercise calories.
        actual_protein_g: Logged protein grams.
        actual_carbs_g: Logged carbohydrate grams.
        actual_fat_g: Logged fat grams.
        meals_count: Number of meals logged.
        meal_items_count: Number of meal items logged.
        activities_count: Number of activities logged.
        total_distance_meters: Total activity distance for the day.
        total_moving_time_seconds: Total moving time for the day.
        total_elevation_gain_meters: Total elevation gain for the day.
        total_suffer_score: Total training-load score for the day.

    Returns:
        HistoryDay: Lightweight day-level summary for lists and charts.

    Raises:
        This model does not raise errors directly.
    """

    date: date
    target_food_calories: float | None = None
    actual_food_calories: float = 0
    actual_exercise_calories: float = 0
    net_calories: float = 0
    actual_protein_g: float = 0
    actual_carbs_g: float = 0
    actual_fat_g: float = 0
    meals_count: int = 0
    meal_items_count: int = 0
    activities_count: int = 0
    total_distance_meters: float = 0
    total_moving_time_seconds: int = 0
    total_elevation_gain_meters: float = 0
    total_suffer_score: float = 0


class HistoryResponse(BaseModel):
    """Represent the history list returned by the backend.

    Parameters:
        date_from: Inclusive lower bound for the history window.
        date_to: Inclusive upper bound for the history window.
        days: Day summaries ordered newest first.

    Returns:
        HistoryResponse: Serializable history result for the portal.

    Raises:
        This model does not raise errors directly.
    """

    date_from: date
    date_to: date
    days: list[HistoryDay] = Field(default_factory=list)


class TrendSummary(BaseModel):
    """Represent rolled-up trend statistics for the selected window.

    Parameters:
        logged_days: Number of days with any target, meal, or activity data.
        average_food_calories: Average logged food calories across logged days.
        average_exercise_calories: Average logged exercise calories across logged days.
        total_distance_meters: Total distance across the selected window.
        total_activities: Total activities across the selected window.

    Returns:
        TrendSummary: Window-level statistics for the trend view.

    Raises:
        This model does not raise errors directly.
    """

    logged_days: int = 0
    average_food_calories: float = 0
    average_exercise_calories: float = 0
    total_distance_meters: float = 0
    total_activities: int = 0


class TrendsResponse(BaseModel):
    """Represent the trend series used by the frontend charts.

    Parameters:
        date_from: Inclusive lower bound for the trend window.
        date_to: Inclusive upper bound for the trend window.
        days: Day summaries ordered oldest first.
        summary: Rolled-up window statistics.

    Returns:
        TrendsResponse: Serializable trend result for the portal.

    Raises:
        This model does not raise errors directly.
    """

    date_from: date
    date_to: date
    days: list[HistoryDay] = Field(default_factory=list)
    summary: TrendSummary


class BootstrapResponse(BaseModel):
    """Represent the initial payload required by the portal.

    Parameters:
        generated_at: Timestamp for the response generation.
        profile: Athlete context displayed in the shell.
        snapshot: Full detail for the selected day.
        history: Initial history result.
        trends: Initial trend result.
        access_protected: Whether the backend expects a bearer token.

    Returns:
        BootstrapResponse: Initial app payload used by the React frontend.

    Raises:
        This model does not raise errors directly.
    """

    generated_at: datetime
    profile: PortalProfile
    snapshot: DailySnapshot
    history: HistoryResponse
    trends: TrendsResponse
    access_protected: bool
