"""Typed API models for the APEX progress portal."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

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


class FoodProduct(BaseModel):
    """Describe one reusable food product from the MCP catalog.

    Parameters:
        id: Product identifier.
        name: Product display name.
        default_serving_g: Optional common serving size in grams.
        calories_per_100g: Calories for one hundred grams.
        carbs_g_per_100g: Carbohydrate grams for one hundred grams.
        protein_g_per_100g: Protein grams for one hundred grams.
        fat_g_per_100g: Fat grams for one hundred grams.
        usage_count: Number of logged meal items that reused this product.

    Returns:
        FoodProduct: Serializable food product row for the portal table.

    Raises:
        This model does not raise errors directly.
    """

    id: str
    name: str
    default_serving_g: float | None = None
    calories_per_100g: float
    carbs_g_per_100g: float
    protein_g_per_100g: float
    fat_g_per_100g: float
    usage_count: int = 0


class FoodProductsResponse(BaseModel):
    """Represent the reusable food product list returned by the backend.

    Parameters:
        items: Food products ordered by product name.

    Returns:
        FoodProductsResponse: Serializable product list for the portal.

    Raises:
        This model does not raise errors directly.
    """

    items: list[FoodProduct] = Field(default_factory=list)


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

    id: str
    product_id: str | None = None
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

    id: str
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

    id: str
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
        target_protein_g: Planned protein target.
        target_carbs_g: Planned carbohydrate target.
        target_fat_g: Planned fat target.
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
    target_protein_g: float | None = None
    target_carbs_g: float | None = None
    target_fat_g: float | None = None
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


class DailyMetricPoint(BaseModel):
    """Represent one value from the `daily_metrics` table.

    Parameters:
        date: Business date represented by the metric row.
        value: Numeric metric value for that date.

    Returns:
        DailyMetricPoint: Serializable daily metric point for trend charts.

    Raises:
        This model does not raise errors directly.
    """

    date: date
    value: float


class DailyMetricSeries(BaseModel):
    """Group daily metric points that share the same metric type.

    Parameters:
        metric_type: Raw metric type from Supabase, for example `sleep_hours`.
        points: Chronological metric values for the selected trend window.

    Returns:
        DailyMetricSeries: Chart-ready dynamic metric series.

    Raises:
        This model does not raise errors directly.
    """

    metric_type: str
    points: list[DailyMetricPoint] = Field(default_factory=list)


class TrainingPlanSummary(BaseModel):
    """Describe one food and training plan header for list views.

    Parameters:
        id: Plan identifier.
        title: Human-readable plan title.
        start_date: First date included in the plan.
        end_date: Last date included in the plan.
        status: Lifecycle status such as draft, approved, published, archived.
        goal_markdown: Goal statement that guided the plan.
        rationale_markdown: AI rationale and assumptions.
        notes_markdown: Freeform plan notes.
        generation_context: Structured context used by the plan creator.
        days_count: Number of stored plan-day rows.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.

    Returns:
        TrainingPlanSummary: Serializable plan header for the portal.

    Raises:
        This model does not raise errors directly.
    """

    id: int
    title: str
    start_date: date
    end_date: date
    status: str
    goal_markdown: str = ""
    rationale_markdown: str = ""
    notes_markdown: str = ""
    generation_context: dict[str, Any] = Field(default_factory=dict)
    days_count: int = 0
    created_at: datetime
    updated_at: datetime


class TrainingPlanDay(BaseModel):
    """Describe one planned food and training day.

    Parameters:
        id: Plan-day identifier.
        plan_id: Parent plan identifier.
        plan_date: Calendar day represented by the row.
        day_type: Day type such as training, rest, recovery, race, or travel.
        title: Human-readable day title.
        training_summary: Short planned-training description.
        primary_sport_type: Optional sport label.
        planned_duration_seconds: Optional planned workout duration.
        planned_distance_meters: Optional planned distance.
        planned_elevation_gain_meters: Optional planned elevation gain.
        planned_training_load: Optional planned training stress/load.
        target_food_calories: Planned food calories.
        target_exercise_calories: Planned exercise calories.
        target_protein_g: Planned protein grams.
        target_carbs_g: Planned carbohydrate grams.
        target_fat_g: Planned fat grams.
        training_sessions: Structured planned workout sessions.
        fueling_plan: Structured workout fueling guidance.
        menu_plan: Structured meal/menu guidance.
        notes_markdown: Freeform day notes.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.

    Returns:
        TrainingPlanDay: Serializable plan-day row for the portal.

    Raises:
        This model does not raise errors directly.
    """

    id: int
    plan_id: int
    plan_date: date
    day_type: str
    title: str = ""
    training_summary: str = ""
    primary_sport_type: str | None = None
    planned_duration_seconds: int | None = None
    planned_distance_meters: float | None = None
    planned_elevation_gain_meters: float | None = None
    planned_training_load: float | None = None
    target_food_calories: float
    target_exercise_calories: float
    target_protein_g: float
    target_carbs_g: float
    target_fat_g: float
    training_sessions: list[dict[str, Any]] = Field(default_factory=list)
    fueling_plan: dict[str, Any] = Field(default_factory=dict)
    menu_plan: dict[str, Any] = Field(default_factory=dict)
    notes_markdown: str = ""
    created_at: datetime
    updated_at: datetime


class TrainingPlanDetail(TrainingPlanSummary):
    """Represent one plan header plus its ordered day rows.

    Parameters:
        days: Plan days ordered by `plan_date`.

    Returns:
        TrainingPlanDetail: Full plan detail payload for the portal.

    Raises:
        This model does not raise errors directly.
    """

    days: list[TrainingPlanDay] = Field(default_factory=list)


class TrainingPlanDailyMetric(BaseModel):
    """Describe one wellness metric attached to a plan comparison day.

    Parameters:
        metric_date: Date represented by the metric.
        metric_type: Metric name from `daily_metrics.metric_type`.
        value: Numeric metric value.

    Returns:
        TrainingPlanDailyMetric: Serializable daily wellness metric row.

    Raises:
        This model does not raise errors directly.
    """

    metric_date: date
    metric_type: str
    value: float


class TrainingPlanComparisonDeltas(BaseModel):
    """Represent actual-minus-planned differences for one plan day.

    Parameters:
        food_calories: Food calorie delta.
        exercise_calories: Exercise calorie delta.
        protein_g: Protein gram delta.
        carbs_g: Carbohydrate gram delta.
        fat_g: Fat gram delta.

    Returns:
        TrainingPlanComparisonDeltas: Serializable delta values.

    Raises:
        This model does not raise errors directly.
    """

    food_calories: float
    exercise_calories: float
    protein_g: float
    carbs_g: float
    fat_g: float


class TrainingPlanComparisonAdherence(BaseModel):
    """Represent adherence percentages for one plan day.

    Parameters:
        food_calories_percent: Food calorie adherence.
        exercise_calories_percent: Exercise calorie adherence.
        protein_percent: Protein adherence.
        carbs_percent: Carbohydrate adherence.
        fat_percent: Fat adherence.
        macro_average_percent: Average of available macro adherence values.

    Returns:
        TrainingPlanComparisonAdherence: Serializable adherence values.

    Raises:
        This model does not raise errors directly.
    """

    food_calories_percent: float | None = None
    exercise_calories_percent: float | None = None
    protein_percent: float | None = None
    carbs_percent: float | None = None
    fat_percent: float | None = None
    macro_average_percent: float | None = None


class TrainingPlanComparisonDay(BaseModel):
    """Combine planned, actual, delta, adherence, and wellness context.

    Parameters:
        plan_date: Calendar date being compared.
        planned: Stored plan day.
        actual: Actual daily summary from existing logs.
        daily_metrics: Wellness metrics recorded for the same date.
        deltas: Actual-minus-planned values.
        adherence: Target adherence percentages.

    Returns:
        TrainingPlanComparisonDay: Serializable planned-vs-actual day row.

    Raises:
        This model does not raise errors directly.
    """

    plan_date: date
    planned: TrainingPlanDay
    actual: DailySummary
    daily_metrics: list[TrainingPlanDailyMetric] = Field(default_factory=list)
    deltas: TrainingPlanComparisonDeltas
    adherence: TrainingPlanComparisonAdherence


class TrainingPlanComparisonTotals(BaseModel):
    """Represent plan-level totals and adherence for compared days.

    Parameters:
        planned_food_calories: Total planned food calories.
        actual_food_calories: Total actual food calories.
        planned_exercise_calories: Total planned exercise calories.
        actual_exercise_calories: Total actual exercise calories.
        planned_protein_g: Total planned protein grams.
        actual_protein_g: Total actual protein grams.
        planned_carbs_g: Total planned carbohydrate grams.
        actual_carbs_g: Total actual carbohydrate grams.
        planned_fat_g: Total planned fat grams.
        actual_fat_g: Total actual fat grams.
        food_calories_delta: Total food calorie delta.
        exercise_calories_delta: Total exercise calorie delta.
        protein_g_delta: Total protein gram delta.
        carbs_g_delta: Total carbohydrate gram delta.
        fat_g_delta: Total fat gram delta.
        food_calories_adherence_percent: Food calorie adherence for totals.
        exercise_calories_adherence_percent: Exercise adherence for totals.
        days_count: Number of compared days.

    Returns:
        TrainingPlanComparisonTotals: Serializable aggregate comparison values.

    Raises:
        This model does not raise errors directly.
    """

    planned_food_calories: float = 0
    actual_food_calories: float = 0
    planned_exercise_calories: float = 0
    actual_exercise_calories: float = 0
    planned_protein_g: float = 0
    actual_protein_g: float = 0
    planned_carbs_g: float = 0
    actual_carbs_g: float = 0
    planned_fat_g: float = 0
    actual_fat_g: float = 0
    food_calories_delta: float = 0
    exercise_calories_delta: float = 0
    protein_g_delta: float = 0
    carbs_g_delta: float = 0
    fat_g_delta: float = 0
    food_calories_adherence_percent: float | None = None
    exercise_calories_adherence_percent: float | None = None
    days_count: int = 0


class TrainingPlansResponse(BaseModel):
    """Represent the plan list returned by the backend.

    Parameters:
        items: Plan headers ordered newest first.

    Returns:
        TrainingPlansResponse: Serializable plan list.

    Raises:
        This model does not raise errors directly.
    """

    items: list[TrainingPlanSummary] = Field(default_factory=list)


class TrainingPlanComparisonResponse(BaseModel):
    """Represent a full planned-vs-actual comparison payload.

    Parameters:
        plan: Plan header being compared.
        days_count: Number of compared day rows.
        days: Per-day planned-vs-actual rows.
        totals: Plan-level totals and adherence.

    Returns:
        TrainingPlanComparisonResponse: Serializable comparison response.

    Raises:
        This model does not raise errors directly.
    """

    plan: TrainingPlanSummary
    days_count: int
    days: list[TrainingPlanComparisonDay] = Field(default_factory=list)
    totals: TrainingPlanComparisonTotals


class TrendsResponse(BaseModel):
    """Represent the trend series used by the frontend charts.

    Parameters:
        date_from: Inclusive lower bound for the trend window.
        date_to: Inclusive upper bound for the trend window.
        days: Day summaries ordered oldest first.
        daily_metrics: Dynamic metric series grouped by metric type.
        summary: Rolled-up window statistics.

    Returns:
        TrendsResponse: Serializable trend result for the portal.

    Raises:
        This model does not raise errors directly.
    """

    date_from: date
    date_to: date
    days: list[HistoryDay] = Field(default_factory=list)
    daily_metrics: list[DailyMetricSeries] = Field(default_factory=list)
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
