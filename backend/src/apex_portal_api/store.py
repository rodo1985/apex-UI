"""Supabase/Postgres read queries for the APEX progress portal."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

import asyncpg

from apex_portal_api.models import (
    Activity,
    DailyMetricPoint,
    DailyMetricSeries,
    DailySnapshot,
    DailySummary,
    FoodProduct,
    HistoryDay,
    HistoryResponse,
    Meal,
    MealItem,
    PortalProfile,
    TrainingPlanComparisonAdherence,
    TrainingPlanComparisonDay,
    TrainingPlanComparisonDeltas,
    TrainingPlanComparisonResponse,
    TrainingPlanComparisonTotals,
    TrainingPlanDailyMetric,
    TrainingPlanDay,
    TrainingPlanDetail,
    TrainingPlanSummary,
    TrendsResponse,
    TrendSummary,
)


class PortalStore(ABC):
    """Define the read operations required by the FastAPI portal.

    Parameters:
        None.

    Returns:
        PortalStore: Abstract contract implemented by the Postgres-backed store
            and lightweight test doubles.

    Raises:
        This abstract base class does not raise errors directly.
    """

    @abstractmethod
    async def get_default_date(self, subject: str, fallback_date: date) -> date:
        """Return the best initial date for the portal shell."""

    @abstractmethod
    async def get_profile(self, subject: str) -> PortalProfile:
        """Return the athlete context bound to the current portal."""

    @abstractmethod
    async def list_products(self, subject: str) -> list[FoodProduct]:
        """Return reusable food products for the current portal subject."""

    @abstractmethod
    async def list_training_plans(
        self,
        subject: str,
        date_from: date | None = None,
        date_to: date | None = None,
        status: str | None = None,
    ) -> list[TrainingPlanSummary]:
        """Return food and training plan headers for the current subject."""

    @abstractmethod
    async def get_training_plan(
        self,
        subject: str,
        plan_id: int,
    ) -> TrainingPlanDetail | None:
        """Return one food and training plan with its planned days."""

    @abstractmethod
    async def compare_training_plan(
        self,
        subject: str,
        plan_id: int,
    ) -> TrainingPlanComparisonResponse | None:
        """Compare one plan against actual logged data."""

    @abstractmethod
    async def get_daily_snapshot(
        self, subject: str, target_date: date
    ) -> DailySnapshot:
        """Return one day's summary, meals, and activities."""

    @abstractmethod
    async def get_history(
        self,
        subject: str,
        date_from: date,
        date_to: date,
    ) -> HistoryResponse:
        """Return day-level history rows for a date window."""

    @abstractmethod
    async def get_trends(
        self,
        subject: str,
        date_from: date,
        date_to: date,
    ) -> TrendsResponse:
        """Return trend data for a date window."""

    @abstractmethod
    async def close(self) -> None:
        """Release any underlying resources held by the store."""


class PostgresPortalStore(PortalStore):
    """Read portal data from the APEX MCP Postgres schema.

    Parameters:
        database_url: Asyncpg-compatible Postgres connection string.
        athlete_name_override: Optional display-name override for the profile.

    Returns:
        PostgresPortalStore: Query helper used by the FastAPI routes.

    Raises:
        This class does not raise errors directly during initialization.

    Example:
        >>> store = PostgresPortalStore("postgresql://example")
        >>> isinstance(store, PostgresPortalStore)
        True
    """

    def __init__(
        self,
        database_url: str,
        athlete_name_override: str | None = None,
        portal_user_id: str | None = None,
        portal_timezone: str = "Europe/Madrid",
    ) -> None:
        """Store connection details for later lazy pool creation.

        Parameters:
            database_url: Asyncpg-compatible Postgres connection string.
            athlete_name_override: Optional display-name override.
            portal_user_id: Optional explicit app-level user id.
            portal_timezone: IANA timezone used for daily grouping.

        Returns:
            None.

        Raises:
            This initializer does not raise errors directly.
        """

        self._database_url = database_url
        self._athlete_name_override = athlete_name_override
        self._portal_user_id = portal_user_id
        self._portal_timezone = portal_timezone
        self._pool: asyncpg.Pool | None = None
        self._pool_lock = asyncio.Lock()
        self._resolved_user_id: str | None = portal_user_id
        self._user_id_lock = asyncio.Lock()
        self._schema_variant: str | None = None
        self._schema_variant_lock = asyncio.Lock()

    async def get_default_date(self, subject: str, fallback_date: date) -> date:
        """Return the best initial day to open in the portal.

        Parameters:
            subject: Stable subject configured for the portal.
            fallback_date: Date used when no tracked data exists yet.

        Returns:
            date: Latest tracked day up to `fallback_date`, or the fallback.

        Raises:
            Exception: Propagated from asyncpg when the query fails.
        """

        schema_variant = await self._get_schema_variant()

        if schema_variant == "legacy":
            row = await self._fetchrow(
                """
                WITH tracked_dates AS (
                    SELECT target_date AS day
                    FROM public.daily_targets
                    WHERE subject = $1 AND target_date <= $2
                    UNION ALL
                    SELECT meal_date AS day
                    FROM public.daily_meals
                    WHERE subject = $1 AND meal_date <= $2
                    UNION ALL
                    SELECT activity_date AS day
                    FROM public.activity_entries
                    WHERE subject = $1 AND activity_date <= $2
                )
                SELECT MAX(day) AS default_day
                FROM tracked_dates
                WHERE day IS NOT NULL
                """,
                subject,
                fallback_date,
            )
        else:
            user_id = await self._resolve_user_id(subject)
            row = await self._fetchrow(
                """
                WITH tracked_dates AS (
                    SELECT target_date AS day
                    FROM public.daily_nutrition_targets
                    WHERE user_id = $1 AND target_date <= $3
                    UNION ALL
                    SELECT timezone($2, logged_at)::date AS day
                    FROM public.meal_logs
                    WHERE user_id = $1 AND timezone($2, logged_at)::date <= $3
                    UNION ALL
                    SELECT timezone($2, start_time)::date AS day
                    FROM public.activities
                    WHERE user_id = $1 AND timezone($2, start_time)::date <= $3
                )
                SELECT MAX(day) AS default_day
                FROM tracked_dates
                WHERE day IS NOT NULL
                """,
                user_id,
                self._portal_timezone,
                fallback_date,
            )

        default_day = (
            row["default_day"] if row and row["default_day"] else fallback_date
        )
        daily_metric_day = await self._get_latest_daily_metric_date(
            subject,
            fallback_date,
        )
        if daily_metric_day and daily_metric_day > default_day:
            return daily_metric_day

        return default_day

    async def get_profile(self, subject: str) -> PortalProfile:
        """Read the athlete context from the MCP profile row.

        Parameters:
            subject: Stable subject configured for the portal.

        Returns:
            PortalProfile: Header context for the portal shell.

        Raises:
            Exception: Propagated from asyncpg when the query fails.
        """

        row = await self._fetchrow(
            """
            SELECT *
            FROM public.user_profiles
            WHERE subject = $1
            """,
            subject,
        )
        profile_markdown = _record_text(row, "profile_markdown")

        athlete_name = (
            self._athlete_name_override
            or _extract_athlete_name(profile_markdown)
            or "Athlete"
        )

        return PortalProfile(
            athlete_name=athlete_name,
            subject=subject,
            weight_kg=_record_float(row, "weight_kg"),
            height_cm=_record_float(row, "height_cm"),
            ftp_watts=_record_int(row, "ftp_watts"),
            profile_markdown=profile_markdown,
            diet_goals_markdown=_record_text(row, "diet_goals_markdown"),
            training_goals_markdown=_record_text(row, "training_goals_markdown"),
        )

    async def list_products(self, subject: str) -> list[FoodProduct]:
        """Read reusable food products for the configured portal subject.

        Parameters:
            subject: Stable subject configured for the portal.

        Returns:
            list[FoodProduct]: Product rows ordered by name and id.

        Raises:
            Exception: Propagated from asyncpg when the query fails.
        """

        schema_variant = await self._get_schema_variant()
        table_name = "food_products" if schema_variant == "legacy" else "food_items"
        usage_count_column = (
            "usage_count"
            if await self._table_has_column(table_name, "usage_count")
            else "0"
        )

        if schema_variant == "legacy":
            rows = await self._fetch(
                f"""
                SELECT
                    id,
                    name,
                    default_serving_g,
                    calories_per_100g,
                    carbs_g_per_100g,
                    protein_g_per_100g,
                    fat_g_per_100g,
                    {usage_count_column} AS usage_count
                FROM public.food_products
                WHERE subject = $1
                ORDER BY LOWER(name), id
                """,
                subject,
            )
        else:
            rows = await self._fetch(
                f"""
                SELECT
                    id,
                    name,
                    serving_size AS default_serving_g,
                    CASE
                        WHEN serving_unit = 'g' AND serving_size > 0
                            THEN calories * 100.0 / serving_size
                        ELSE calories
                    END AS calories_per_100g,
                    CASE
                        WHEN serving_unit = 'g' AND serving_size > 0
                            THEN carbs_g * 100.0 / serving_size
                        ELSE carbs_g
                    END AS carbs_g_per_100g,
                    CASE
                        WHEN serving_unit = 'g' AND serving_size > 0
                            THEN protein_g * 100.0 / serving_size
                        ELSE protein_g
                    END AS protein_g_per_100g,
                    CASE
                        WHEN serving_unit = 'g' AND serving_size > 0
                            THEN fat_g * 100.0 / serving_size
                        ELSE fat_g
                    END AS fat_g_per_100g,
                    {usage_count_column} AS usage_count
                FROM public.food_items
                ORDER BY LOWER(name), id
                """,
            )

        return [
            FoodProduct(
                id=str(row["id"]),
                name=str(row["name"]),
                default_serving_g=_as_float(row["default_serving_g"]),
                calories_per_100g=_as_float(row["calories_per_100g"]) or 0,
                carbs_g_per_100g=_as_float(row["carbs_g_per_100g"]) or 0,
                protein_g_per_100g=_as_float(row["protein_g_per_100g"]) or 0,
                fat_g_per_100g=_as_float(row["fat_g_per_100g"]) or 0,
                usage_count=_as_int(row["usage_count"]) or 0,
            )
            for row in rows
        ]

    async def list_training_plans(
        self,
        subject: str,
        date_from: date | None = None,
        date_to: date | None = None,
        status: str | None = None,
    ) -> list[TrainingPlanSummary]:
        """Read food and training plan headers for the configured subject.

        Parameters:
            subject: Stable subject configured for the portal.
            date_from: Optional inclusive lower date bound for overlapping plans.
            date_to: Optional inclusive upper date bound for overlapping plans.
            status: Optional lifecycle status filter.

        Returns:
            list[TrainingPlanSummary]: Plan headers ordered newest first.

        Raises:
            Exception: Propagated from asyncpg when the query fails.
        """

        if not await self._training_plan_tables_available():
            return []

        filters = ["p.subject = $1"]
        args: list[object] = [subject]

        if date_from is not None:
            args.append(date_from)
            filters.append(f"p.end_date >= ${len(args)}")

        if date_to is not None:
            args.append(date_to)
            filters.append(f"p.start_date <= ${len(args)}")

        if status is not None:
            args.append(status)
            filters.append(f"p.status = ${len(args)}")

        rows = await self._fetch(
            f"""
            SELECT
                p.id,
                p.title,
                p.start_date,
                p.end_date,
                p.status,
                p.goal_markdown,
                p.rationale_markdown,
                p.notes_markdown,
                p.generation_context,
                p.created_at,
                p.updated_at,
                COUNT(d.id)::INTEGER AS days_count
            FROM public.training_plans p
            LEFT JOIN public.training_plan_days d
                ON d.subject = p.subject AND d.plan_id = p.id
            WHERE {' AND '.join(filters)}
            GROUP BY p.id
            ORDER BY p.start_date DESC, p.id DESC
            """,
            *args,
        )
        return [_training_plan_summary_from_row(row) for row in rows]

    async def get_training_plan(
        self,
        subject: str,
        plan_id: int,
    ) -> TrainingPlanDetail | None:
        """Read one food and training plan with its planned day rows.

        Parameters:
            subject: Stable subject configured for the portal.
            plan_id: Plan identifier to load.

        Returns:
            TrainingPlanDetail | None: Plan detail when found.

        Raises:
            Exception: Propagated from asyncpg when the query fails.
        """

        if not await self._training_plan_tables_available():
            return None

        plan_row = await self._fetchrow(
            """
            SELECT
                p.id,
                p.title,
                p.start_date,
                p.end_date,
                p.status,
                p.goal_markdown,
                p.rationale_markdown,
                p.notes_markdown,
                p.generation_context,
                p.created_at,
                p.updated_at,
                COUNT(d.id)::INTEGER AS days_count
            FROM public.training_plans p
            LEFT JOIN public.training_plan_days d
                ON d.subject = p.subject AND d.plan_id = p.id
            WHERE p.subject = $1 AND p.id = $2
            GROUP BY p.id
            """,
            subject,
            plan_id,
        )
        if plan_row is None:
            return None

        day_rows = await self._fetch(
            """
            SELECT
                id,
                plan_id,
                plan_date,
                day_type,
                title,
                training_summary,
                primary_sport_type,
                planned_duration_seconds,
                planned_distance_meters,
                planned_elevation_gain_meters,
                planned_training_load,
                target_food_calories,
                target_exercise_calories,
                target_protein_g,
                target_carbs_g,
                target_fat_g,
                training_sessions,
                fueling_plan,
                menu_plan,
                notes_markdown,
                created_at,
                updated_at
            FROM public.training_plan_days
            WHERE subject = $1 AND plan_id = $2
            ORDER BY plan_date ASC, id ASC
            """,
            subject,
            plan_id,
        )
        return TrainingPlanDetail(
            **_training_plan_summary_from_row(plan_row).model_dump(),
            days=[_training_plan_day_from_row(row) for row in day_rows],
        )

    async def compare_training_plan(
        self,
        subject: str,
        plan_id: int,
    ) -> TrainingPlanComparisonResponse | None:
        """Compare one plan's intended days with actual logged outcomes.

        Parameters:
            subject: Stable subject configured for the portal.
            plan_id: Plan identifier to compare.

        Returns:
            TrainingPlanComparisonResponse | None: Comparison when the plan exists.

        Raises:
            Exception: Propagated from asyncpg when the query fails.
        """

        plan = await self.get_training_plan(subject, plan_id)
        if plan is None:
            return None

        comparison_days: list[TrainingPlanComparisonDay] = []
        totals = _empty_training_plan_comparison_totals()

        for planned_day in plan.days:
            actual = await self._get_daily_summary(subject, planned_day.plan_date)
            daily_metrics = await self._get_daily_metrics_for_day(
                subject,
                planned_day.plan_date,
            )
            comparison = _build_training_plan_day_comparison(
                planned_day,
                actual,
                daily_metrics,
            )
            _add_training_plan_comparison_totals(totals, comparison)
            comparison_days.append(comparison)

        plan_summary = TrainingPlanSummary(
            **plan.model_dump(exclude={"days"}),
        )
        return TrainingPlanComparisonResponse(
            plan=plan_summary,
            days_count=len(comparison_days),
            days=comparison_days,
            totals=_finalize_training_plan_comparison_totals(
                totals,
                len(comparison_days),
            ),
        )

    async def get_daily_snapshot(
        self, subject: str, target_date: date
    ) -> DailySnapshot:
        """Read one day with summary, meals, and activities.

        Parameters:
            subject: Stable subject configured for the portal.
            target_date: Business date to review.

        Returns:
            DailySnapshot: Detailed portal view for the selected day.

        Raises:
            Exception: Propagated from asyncpg when the queries fail.
        """

        summary = await self._get_daily_summary(subject, target_date)
        meals = await self._get_meals_for_day(subject, target_date)
        activities = await self._get_activities_for_day(subject, target_date)
        return DailySnapshot(
            date=target_date,
            summary=summary,
            meals=meals,
            activities=activities,
        )

    async def get_history(
        self,
        subject: str,
        date_from: date,
        date_to: date,
    ) -> HistoryResponse:
        """Read a newest-first list of day-level review rows.

        Parameters:
            subject: Stable subject configured for the portal.
            date_from: Inclusive lower date bound.
            date_to: Inclusive upper date bound.

        Returns:
            HistoryResponse: Day-level summaries for the selected window.

        Raises:
            Exception: Propagated from asyncpg when the history query fails.
        """

        days = await self._get_history_days(subject, date_from, date_to)
        return HistoryResponse(date_from=date_from, date_to=date_to, days=days)

    async def get_trends(
        self,
        subject: str,
        date_from: date,
        date_to: date,
    ) -> TrendsResponse:
        """Read an oldest-first series plus rolled-up window metrics.

        Parameters:
            subject: Stable subject configured for the portal.
            date_from: Inclusive lower date bound.
            date_to: Inclusive upper date bound.

        Returns:
            TrendsResponse: Chart-ready day series and summary metrics.

        Raises:
            Exception: Propagated from asyncpg when the history query fails.
        """

        history_days = await self._get_history_days(subject, date_from, date_to)
        daily_metrics = await self._get_daily_metric_series(
            subject,
            date_from,
            date_to,
        )
        ordered_days = list(reversed(history_days))
        logged_days = len(ordered_days)
        average_food = (
            round(
                sum(day.actual_food_calories for day in ordered_days) / logged_days, 2
            )
            if logged_days
            else 0
        )
        average_exercise = (
            round(
                sum(day.actual_exercise_calories for day in ordered_days) / logged_days,
                2,
            )
            if logged_days
            else 0
        )
        summary = TrendSummary(
            logged_days=logged_days,
            average_food_calories=average_food,
            average_exercise_calories=average_exercise,
            total_distance_meters=round(
                sum(day.total_distance_meters for day in ordered_days),
                2,
            ),
            total_activities=sum(day.activities_count for day in ordered_days),
        )
        return TrendsResponse(
            date_from=date_from,
            date_to=date_to,
            days=ordered_days,
            daily_metrics=daily_metrics,
            summary=summary,
        )

    async def close(self) -> None:
        """Release the asyncpg pool when the app shuts down.

        Parameters:
            None.

        Returns:
            None.

        Raises:
            Exception: Propagated from asyncpg when pool close fails.
        """

        if self._pool is None:
            return

        await self._pool.close()
        self._pool = None

    async def _get_daily_summary(self, subject: str, target_date: date) -> DailySummary:
        """Compute target-vs-actual metrics using the MCP schema semantics.

        Parameters:
            subject: Stable subject configured for the portal.
            target_date: Business date to summarize.

        Returns:
            DailySummary: Daily metrics aligned with the MCP server logic.

        Raises:
            Exception: Propagated from asyncpg when the summary queries fail.
        """

        schema_variant = await self._get_schema_variant()

        if schema_variant == "legacy":
            target_row = await self._fetchrow(
                """
                SELECT
                    target_food_calories,
                    target_exercise_calories,
                    target_protein_g,
                    target_carbs_g,
                    target_fat_g
                FROM public.daily_targets
                WHERE subject = $1 AND target_date = $2
                """,
                subject,
                target_date,
            )
            meal_row = await self._fetchrow(
                """
                SELECT
                    COALESCE(SUM(mi.calories), 0) AS actual_food_calories,
                    COALESCE(SUM(mi.protein_g), 0) AS actual_protein_g,
                    COALESCE(SUM(mi.carbs_g), 0) AS actual_carbs_g,
                    COALESCE(SUM(mi.fat_g), 0) AS actual_fat_g,
                    COUNT(DISTINCT dm.id)::INTEGER AS meals_count,
                    COUNT(mi.id)::INTEGER AS meal_items_count
                FROM public.daily_meals dm
                LEFT JOIN public.meal_items mi
                    ON mi.subject = dm.subject AND mi.meal_id = dm.id
                WHERE dm.subject = $1 AND dm.meal_date = $2
                """,
                subject,
                target_date,
            )
            activity_row = await self._fetchrow(
                """
                SELECT
                    COALESCE(SUM(COALESCE(calories, 0)), 0) AS actual_exercise_calories,
                    COUNT(id)::INTEGER AS activities_count
                FROM public.activity_entries
                WHERE subject = $1 AND activity_date = $2
                """,
                subject,
                target_date,
            )
        else:
            user_id = await self._resolve_user_id(subject)
            target_row = await self._fetchrow(
                """
                SELECT
                    calories AS target_food_calories,
                    NULL::DOUBLE PRECISION AS target_exercise_calories,
                    protein_g AS target_protein_g,
                    carbs_g AS target_carbs_g,
                    fat_g AS target_fat_g
                FROM public.daily_nutrition_targets
                WHERE user_id = $1 AND target_date = $2
                """,
                user_id,
                target_date,
            )
            meal_row = await self._fetchrow(
                """
                SELECT
                    COALESCE(SUM(mi.calories), 0) AS actual_food_calories,
                    COALESCE(SUM(mi.protein_g), 0) AS actual_protein_g,
                    COALESCE(SUM(mi.carbs_g), 0) AS actual_carbs_g,
                    COALESCE(SUM(mi.fat_g), 0) AS actual_fat_g,
                    COUNT(DISTINCT ml.id)::INTEGER AS meals_count,
                    COUNT(mi.id)::INTEGER AS meal_items_count
                FROM public.meal_logs ml
                LEFT JOIN public.meal_ingredients mi
                    ON mi.meal_log_id = ml.id
                WHERE ml.user_id = $1
                    AND timezone($2, ml.logged_at)::date = $3
                """,
                user_id,
                self._portal_timezone,
                target_date,
            )
            activity_row = await self._fetchrow(
                """
                SELECT
                    COALESCE(SUM(COALESCE(calories, 0)), 0) AS actual_exercise_calories,
                    COUNT(id)::INTEGER AS activities_count
                FROM public.activities
                WHERE user_id = $1
                    AND timezone($2, start_time)::date = $3
                """,
                user_id,
                self._portal_timezone,
                target_date,
            )

        actual_food_calories = _as_float(meal_row["actual_food_calories"]) or 0
        actual_exercise_calories = (
            _as_float(activity_row["actual_exercise_calories"]) or 0
        )

        target_food = _nullable_float(target_row, "target_food_calories")
        target_protein = _nullable_float(target_row, "target_protein_g")
        target_carbs = _nullable_float(target_row, "target_carbs_g")
        target_fat = _nullable_float(target_row, "target_fat_g")

        return DailySummary(
            target_date=target_date,
            target_food_calories=target_food,
            target_exercise_calories=_nullable_float(
                target_row,
                "target_exercise_calories",
            ),
            target_protein_g=target_protein,
            target_carbs_g=target_carbs,
            target_fat_g=target_fat,
            actual_food_calories=actual_food_calories,
            actual_exercise_calories=actual_exercise_calories,
            actual_protein_g=_as_float(meal_row["actual_protein_g"]) or 0,
            actual_carbs_g=_as_float(meal_row["actual_carbs_g"]) or 0,
            actual_fat_g=_as_float(meal_row["actual_fat_g"]) or 0,
            remaining_food_calories=_remaining_value(target_food, actual_food_calories),
            remaining_protein_g=_remaining_value(
                target_protein,
                _as_float(meal_row["actual_protein_g"]) or 0,
            ),
            remaining_carbs_g=_remaining_value(
                target_carbs,
                _as_float(meal_row["actual_carbs_g"]) or 0,
            ),
            remaining_fat_g=_remaining_value(
                target_fat,
                _as_float(meal_row["actual_fat_g"]) or 0,
            ),
            net_calories=round(actual_food_calories - actual_exercise_calories, 2),
            meals_count=_as_int(meal_row["meals_count"]) or 0,
            meal_items_count=_as_int(meal_row["meal_items_count"]) or 0,
            activities_count=_as_int(activity_row["activities_count"]) or 0,
        )

    async def _get_meals_for_day(self, subject: str, target_date: date) -> list[Meal]:
        """Read meal headers and their items for one day.

        Parameters:
            subject: Stable subject configured for the portal.
            target_date: Business date to inspect.

        Returns:
            list[Meal]: Meals ordered by creation id.

        Raises:
            Exception: Propagated from asyncpg when the queries fail.
        """

        schema_variant = await self._get_schema_variant()

        if schema_variant == "legacy":
            meal_rows = await self._fetch(
                """
                SELECT id, meal_label, notes_markdown
                FROM public.daily_meals
                WHERE subject = $1 AND meal_date = $2
                ORDER BY id
                """,
                subject,
                target_date,
            )
        else:
            user_id = await self._resolve_user_id(subject)
            meal_rows = await self._fetch(
                """
                SELECT
                    id,
                    COALESCE(
                        NULLIF(TRIM(meal_name), ''),
                        NULLIF(TRIM(meal_type), ''),
                        'Meal'
                    ) AS meal_label,
                    '' AS notes_markdown
                FROM public.meal_logs
                WHERE user_id = $1
                    AND timezone($2, logged_at)::date = $3
                ORDER BY logged_at, id
                """,
                user_id,
                self._portal_timezone,
                target_date,
            )
        if not meal_rows:
            return []

        meal_ids = [str(row["id"]) for row in meal_rows]
        if schema_variant == "legacy":
            item_rows = await self._fetch(
                """
                SELECT
                    id,
                    meal_id,
                    product_id,
                    ingredient_name,
                    grams,
                    calories,
                    carbs_g,
                    protein_g,
                    fat_g
                FROM public.meal_items
                WHERE subject = $1 AND meal_id = ANY($2::bigint[])
                ORDER BY meal_id, id
                """,
                subject,
                [int(meal_id) for meal_id in meal_ids],
            )
        else:
            item_rows = await self._fetch(
                """
                SELECT
                    id,
                    meal_log_id AS meal_id,
                    food_id AS product_id,
                    name AS ingredient_name,
                    quantity_g AS grams,
                    calories,
                    carbs_g,
                    protein_g,
                    fat_g
                FROM public.meal_ingredients
                WHERE meal_log_id = ANY($1::VARCHAR[])
                ORDER BY meal_id, id
                """,
                meal_ids,
            )

        items_by_meal: dict[str, list[MealItem]] = defaultdict(list)
        for row in item_rows:
            items_by_meal[str(row["meal_id"])].append(
                MealItem(
                    id=str(row["id"]),
                    product_id=_as_optional_str(row["product_id"]),
                    ingredient_name=str(row["ingredient_name"]),
                    grams=_as_float(row["grams"]) or 0,
                    calories=_as_float(row["calories"]) or 0,
                    carbs_g=_as_float(row["carbs_g"]) or 0,
                    protein_g=_as_float(row["protein_g"]) or 0,
                    fat_g=_as_float(row["fat_g"]) or 0,
                )
            )

        meals: list[Meal] = []
        for row in meal_rows:
            meal_id = str(row["id"])
            items = items_by_meal.get(meal_id, [])

            # The totals are recomputed here rather than trusted from another
            # table or SQL view so the portal stays aligned with the raw source
            # of truth in `meal_items`.
            meals.append(
                Meal(
                    id=meal_id,
                    meal_label=str(row["meal_label"]),
                    notes_markdown=str(row["notes_markdown"] or ""),
                    items=items,
                    total_calories=round(sum(item.calories for item in items), 2),
                    total_carbs_g=round(sum(item.carbs_g for item in items), 2),
                    total_protein_g=round(sum(item.protein_g for item in items), 2),
                    total_fat_g=round(sum(item.fat_g for item in items), 2),
                )
            )

        return meals

    async def _get_activities_for_day(
        self,
        subject: str,
        target_date: date,
    ) -> list[Activity]:
        """Read activities for one day.

        Parameters:
            subject: Stable subject configured for the portal.
            target_date: Business date to inspect.

        Returns:
            list[Activity]: Activities ordered by id.

        Raises:
            Exception: Propagated from asyncpg when the query fails.
        """

        schema_variant = await self._get_schema_variant()

        if schema_variant == "legacy":
            rows = await self._fetch(
                """
                SELECT
                    id,
                    title,
                    activity_date,
                    sport_type,
                    distance_meters,
                    moving_time_seconds,
                    total_elevation_gain_meters,
                    average_heartrate,
                    max_heartrate,
                    calories,
                    suffer_score,
                    notes_markdown,
                    external_source
                FROM public.activity_entries
                WHERE subject = $1 AND activity_date = $2
                ORDER BY id
                """,
                subject,
                target_date,
            )
        else:
            user_id = await self._resolve_user_id(subject)
            rows = await self._fetch(
                """
                SELECT
                    id,
                    name AS title,
                    timezone($2, start_time)::date AS activity_date,
                    INITCAP(sport) AS sport_type,
                    distance_m AS distance_meters,
                    duration_seconds AS moving_time_seconds,
                    elevation_m AS total_elevation_gain_meters,
                    avg_hr AS average_heartrate,
                    max_hr AS max_heartrate,
                    calories,
                    tss AS suffer_score,
                    notes_markdown,
                    CASE
                        WHEN strava_id IS NOT NULL THEN 'strava'
                        ELSE metadata_json->>'source'
                    END AS external_source
                FROM (
                    SELECT
                        id,
                        name,
                        start_time,
                        sport,
                        distance_m,
                        duration_seconds,
                        elevation_m,
                        avg_hr,
                        max_hr,
                        calories,
                        tss,
                        ''::TEXT AS notes_markdown,
                        strava_id,
                        metadata_json
                    FROM public.activities
                    WHERE user_id = $1
                        AND timezone($2, start_time)::date = $3
                ) activity_rows
                ORDER BY activity_date, id
                """,
                user_id,
                self._portal_timezone,
                target_date,
            )

        return [
            Activity(
                id=str(row["id"]),
                title=str(row["title"]),
                activity_date=row["activity_date"],
                sport_type=str(row["sport_type"]) if row["sport_type"] else None,
                distance_meters=_as_float(row["distance_meters"]),
                moving_time_seconds=_as_int(row["moving_time_seconds"]),
                total_elevation_gain_meters=_as_float(
                    row["total_elevation_gain_meters"]
                ),
                average_heartrate=_as_float(row["average_heartrate"]),
                max_heartrate=_as_float(row["max_heartrate"]),
                calories=_as_float(row["calories"]),
                suffer_score=_as_float(row["suffer_score"]),
                notes_markdown=str(row["notes_markdown"] or ""),
                external_source=str(row["external_source"])
                if row["external_source"]
                else None,
            )
            for row in rows
        ]

    async def _get_history_days(
        self,
        subject: str,
        date_from: date,
        date_to: date,
    ) -> list[HistoryDay]:
        """Read day-level summary rows across a date window.

        Parameters:
            subject: Stable subject configured for the portal.
            date_from: Inclusive lower date bound.
            date_to: Inclusive upper date bound.

        Returns:
            list[HistoryDay]: Newest-first day rows for review and charting.

        Raises:
            Exception: Propagated from asyncpg when the query fails.
        """

        schema_variant = await self._get_schema_variant()

        if schema_variant == "legacy":
            rows = await self._fetch(
                """
                WITH tracked_dates AS (
                    SELECT target_date AS day
                    FROM public.daily_targets
                    WHERE subject = $1 AND target_date BETWEEN $2 AND $3
                    UNION
                    SELECT meal_date AS day
                    FROM public.daily_meals
                    WHERE subject = $1 AND meal_date BETWEEN $2 AND $3
                    UNION
                    SELECT activity_date AS day
                    FROM public.activity_entries
                    WHERE subject = $1 AND activity_date BETWEEN $2 AND $3
                ),
                meal_totals AS (
                    SELECT
                        dm.meal_date AS day,
                        COALESCE(SUM(mi.calories), 0) AS actual_food_calories,
                        COALESCE(SUM(mi.protein_g), 0) AS actual_protein_g,
                        COALESCE(SUM(mi.carbs_g), 0) AS actual_carbs_g,
                        COALESCE(SUM(mi.fat_g), 0) AS actual_fat_g,
                        COUNT(DISTINCT dm.id)::INTEGER AS meals_count,
                        COUNT(mi.id)::INTEGER AS meal_items_count
                    FROM public.daily_meals dm
                    LEFT JOIN public.meal_items mi
                        ON mi.subject = dm.subject AND mi.meal_id = dm.id
                    WHERE dm.subject = $1 AND dm.meal_date BETWEEN $2 AND $3
                    GROUP BY dm.meal_date
                ),
                activity_totals AS (
                    SELECT
                        activity_date AS day,
                        COALESCE(SUM(COALESCE(calories, 0)), 0)
                            AS actual_exercise_calories,
                        COALESCE(SUM(COALESCE(distance_meters, 0)), 0)
                            AS total_distance_meters,
                        COALESCE(SUM(COALESCE(moving_time_seconds, 0)), 0)::INTEGER
                            AS total_moving_time_seconds,
                        COALESCE(
                            SUM(COALESCE(total_elevation_gain_meters, 0)),
                            0
                        ) AS total_elevation_gain_meters,
                        COALESCE(SUM(COALESCE(suffer_score, 0)), 0)
                            AS total_suffer_score,
                        COUNT(id)::INTEGER AS activities_count
                    FROM public.activity_entries
                    WHERE subject = $1 AND activity_date BETWEEN $2 AND $3
                    GROUP BY activity_date
                )
                SELECT
                    tracked_dates.day,
                    dt.target_food_calories,
                    dt.target_protein_g,
                    dt.target_carbs_g,
                    dt.target_fat_g,
                    COALESCE(mt.actual_food_calories, 0) AS actual_food_calories,
                    COALESCE(at.actual_exercise_calories, 0)
                        AS actual_exercise_calories,
                    COALESCE(mt.actual_food_calories, 0)
                        - COALESCE(at.actual_exercise_calories, 0) AS net_calories,
                    COALESCE(mt.actual_protein_g, 0) AS actual_protein_g,
                    COALESCE(mt.actual_carbs_g, 0) AS actual_carbs_g,
                    COALESCE(mt.actual_fat_g, 0) AS actual_fat_g,
                    COALESCE(mt.meals_count, 0) AS meals_count,
                    COALESCE(mt.meal_items_count, 0) AS meal_items_count,
                    COALESCE(at.activities_count, 0) AS activities_count,
                    COALESCE(at.total_distance_meters, 0) AS total_distance_meters,
                    COALESCE(at.total_moving_time_seconds, 0)
                        AS total_moving_time_seconds,
                    COALESCE(at.total_elevation_gain_meters, 0)
                        AS total_elevation_gain_meters,
                    COALESCE(at.total_suffer_score, 0) AS total_suffer_score
                FROM tracked_dates
                LEFT JOIN public.daily_targets dt
                    ON dt.subject = $1 AND dt.target_date = tracked_dates.day
                LEFT JOIN meal_totals mt
                    ON mt.day = tracked_dates.day
                LEFT JOIN activity_totals at
                    ON at.day = tracked_dates.day
                ORDER BY tracked_dates.day DESC
                """,
                subject,
                date_from,
                date_to,
            )
        else:
            rows = await self._fetch(
                """
                WITH tracked_dates AS (
                    SELECT target_date AS day
                    FROM public.daily_nutrition_targets
                    WHERE user_id = $1 AND target_date BETWEEN $3 AND $4
                    UNION
                    SELECT timezone($2, logged_at)::date AS day
                    FROM public.meal_logs
                    WHERE user_id = $1
                        AND timezone($2, logged_at)::date BETWEEN $3 AND $4
                    UNION
                    SELECT timezone($2, start_time)::date AS day
                    FROM public.activities
                    WHERE user_id = $1
                        AND timezone($2, start_time)::date BETWEEN $3 AND $4
                ),
                meal_totals AS (
                    SELECT
                        timezone($2, ml.logged_at)::date AS day,
                        COALESCE(SUM(mi.calories), 0) AS actual_food_calories,
                        COALESCE(SUM(mi.protein_g), 0) AS actual_protein_g,
                        COALESCE(SUM(mi.carbs_g), 0) AS actual_carbs_g,
                        COALESCE(SUM(mi.fat_g), 0) AS actual_fat_g,
                        COUNT(DISTINCT ml.id)::INTEGER AS meals_count,
                        COUNT(mi.id)::INTEGER AS meal_items_count
                    FROM public.meal_logs ml
                    LEFT JOIN public.meal_ingredients mi
                        ON mi.meal_log_id = ml.id
                    WHERE ml.user_id = $1
                        AND timezone($2, ml.logged_at)::date BETWEEN $3 AND $4
                    GROUP BY timezone($2, ml.logged_at)::date
                ),
                activity_totals AS (
                    SELECT
                        timezone($2, start_time)::date AS day,
                        COALESCE(SUM(COALESCE(calories, 0)), 0)
                            AS actual_exercise_calories,
                        COALESCE(SUM(COALESCE(distance_meters, 0)), 0)
                            AS total_distance_meters,
                        COALESCE(
                            SUM(COALESCE(moving_time_seconds, 0)),
                            0
                        )::INTEGER AS total_moving_time_seconds,
                        COALESCE(
                            SUM(COALESCE(total_elevation_gain_meters, 0)),
                            0
                        ) AS total_elevation_gain_meters,
                        COALESCE(SUM(COALESCE(suffer_score, 0)), 0)
                            AS total_suffer_score,
                        COUNT(id)::INTEGER AS activities_count
                    FROM (
                        SELECT
                            id,
                            start_time,
                            calories,
                            distance_m AS distance_meters,
                            duration_seconds AS moving_time_seconds,
                            elevation_m AS total_elevation_gain_meters,
                            tss AS suffer_score
                        FROM public.activities
                        WHERE user_id = $1
                            AND timezone($2, start_time)::date BETWEEN $3 AND $4
                    ) activity_rows
                    GROUP BY timezone($2, start_time)::date
                )
                SELECT
                    tracked_dates.day,
                    dt.calories AS target_food_calories,
                    dt.protein_g AS target_protein_g,
                    dt.carbs_g AS target_carbs_g,
                    dt.fat_g AS target_fat_g,
                    COALESCE(mt.actual_food_calories, 0) AS actual_food_calories,
                    COALESCE(at.actual_exercise_calories, 0)
                        AS actual_exercise_calories,
                    COALESCE(mt.actual_food_calories, 0)
                        - COALESCE(at.actual_exercise_calories, 0) AS net_calories,
                    COALESCE(mt.actual_protein_g, 0) AS actual_protein_g,
                    COALESCE(mt.actual_carbs_g, 0) AS actual_carbs_g,
                    COALESCE(mt.actual_fat_g, 0) AS actual_fat_g,
                    COALESCE(mt.meals_count, 0) AS meals_count,
                    COALESCE(mt.meal_items_count, 0) AS meal_items_count,
                    COALESCE(at.activities_count, 0) AS activities_count,
                    COALESCE(at.total_distance_meters, 0) AS total_distance_meters,
                    COALESCE(at.total_moving_time_seconds, 0)
                        AS total_moving_time_seconds,
                    COALESCE(at.total_elevation_gain_meters, 0)
                        AS total_elevation_gain_meters,
                    COALESCE(at.total_suffer_score, 0) AS total_suffer_score
                FROM tracked_dates
                LEFT JOIN public.daily_nutrition_targets dt
                    ON dt.user_id = $1 AND dt.target_date = tracked_dates.day
                LEFT JOIN meal_totals mt
                    ON mt.day = tracked_dates.day
                LEFT JOIN activity_totals at
                    ON at.day = tracked_dates.day
                ORDER BY tracked_dates.day DESC
                """,
                await self._resolve_user_id(subject),
                self._portal_timezone,
                date_from,
                date_to,
            )

        return [
            HistoryDay(
                date=row["day"],
                target_food_calories=_nullable_float(row, "target_food_calories"),
                target_protein_g=_nullable_float(row, "target_protein_g"),
                target_carbs_g=_nullable_float(row, "target_carbs_g"),
                target_fat_g=_nullable_float(row, "target_fat_g"),
                actual_food_calories=_as_float(row["actual_food_calories"]) or 0,
                actual_exercise_calories=_as_float(row["actual_exercise_calories"])
                or 0,
                net_calories=round(_as_float(row["net_calories"]) or 0, 2),
                actual_protein_g=_as_float(row["actual_protein_g"]) or 0,
                actual_carbs_g=_as_float(row["actual_carbs_g"]) or 0,
                actual_fat_g=_as_float(row["actual_fat_g"]) or 0,
                meals_count=_as_int(row["meals_count"]) or 0,
                meal_items_count=_as_int(row["meal_items_count"]) or 0,
                activities_count=_as_int(row["activities_count"]) or 0,
                total_distance_meters=_as_float(row["total_distance_meters"]) or 0,
                total_moving_time_seconds=_as_int(row["total_moving_time_seconds"])
                or 0,
                total_elevation_gain_meters=_as_float(
                    row["total_elevation_gain_meters"]
                )
                or 0,
                total_suffer_score=_as_float(row["total_suffer_score"]) or 0,
            )
            for row in rows
        ]

    async def _get_daily_metric_series(
        self,
        subject: str,
        date_from: date,
        date_to: date,
    ) -> list[DailyMetricSeries]:
        """Read dynamic daily metrics grouped by metric type.

        Parameters:
            subject: Stable subject configured for the portal.
            date_from: Inclusive lower date bound.
            date_to: Inclusive upper date bound.

        Returns:
            list[DailyMetricSeries]: Chronological metric series for trend charts.

        Raises:
            Exception: Propagated from asyncpg when the query fails.
        """

        if not await self._table_has_column("daily_metrics", "metric_type"):
            return []

        rows = await self._fetch(
            """
            SELECT
                metric_type,
                metric_date,
                AVG(value) AS value
            FROM public.daily_metrics
            WHERE subject = $1
                AND metric_date BETWEEN $2 AND $3
            GROUP BY metric_type, metric_date
            ORDER BY LOWER(metric_type), metric_type, metric_date
            """,
            subject,
            date_from,
            date_to,
        )

        grouped_points: dict[str, list[DailyMetricPoint]] = defaultdict(list)
        for row in rows:
            metric_type = str(row["metric_type"] or "").strip()
            metric_value = _as_float(row["value"])
            if not metric_type or metric_value is None:
                continue

            grouped_points[metric_type].append(
                DailyMetricPoint(
                    date=row["metric_date"],
                    value=metric_value,
                )
            )

        return [
            DailyMetricSeries(metric_type=metric_type, points=points)
            for metric_type, points in sorted(
                grouped_points.items(),
                key=lambda item: item[0].lower(),
            )
            if points
        ]

    async def _get_daily_metrics_for_day(
        self,
        subject: str,
        target_date: date,
    ) -> list[TrainingPlanDailyMetric]:
        """Read daily metrics attached to one comparison day.

        Parameters:
            subject: Stable subject configured for the portal.
            target_date: Business date to inspect.

        Returns:
            list[TrainingPlanDailyMetric]: Metric rows ordered by metric type.

        Raises:
            Exception: Propagated from asyncpg when the query fails.
        """

        if not await self._table_has_column("daily_metrics", "metric_type"):
            return []

        rows = await self._fetch(
            """
            SELECT
                metric_date,
                metric_type,
                AVG(value) AS value
            FROM public.daily_metrics
            WHERE subject = $1 AND metric_date = $2
            GROUP BY metric_date, metric_type
            ORDER BY LOWER(metric_type), metric_type
            """,
            subject,
            target_date,
        )

        metrics: list[TrainingPlanDailyMetric] = []
        for row in rows:
            metric_type = str(row["metric_type"] or "").strip()
            metric_value = _as_float(row["value"])
            if not metric_type or metric_value is None:
                continue

            metrics.append(
                TrainingPlanDailyMetric(
                    metric_date=row["metric_date"],
                    metric_type=metric_type,
                    value=metric_value,
                )
            )

        return metrics

    async def _get_latest_daily_metric_date(
        self,
        subject: str,
        fallback_date: date,
    ) -> date | None:
        """Return the latest dynamic metric date up to a fallback date.

        Parameters:
            subject: Stable subject configured for the portal.
            fallback_date: Latest date allowed for default-day selection.

        Returns:
            date | None: Latest daily metric date, or `None` when unavailable.

        Raises:
            Exception: Propagated from asyncpg when the query fails.
        """

        if not await self._table_has_column("daily_metrics", "metric_date"):
            return None

        row = await self._fetchrow(
            """
            SELECT MAX(metric_date) AS default_day
            FROM public.daily_metrics
            WHERE subject = $1 AND metric_date <= $2
            """,
            subject,
            fallback_date,
        )
        return row["default_day"] if row and row["default_day"] else None

    async def _training_plan_tables_available(self) -> bool:
        """Return whether the optional food and training plan tables exist.

        Parameters:
            None.

        Returns:
            bool: `True` when both plan tables are present.

        Raises:
            Exception: Propagated from asyncpg when metadata lookup fails.
        """

        return await self._table_has_column(
            "training_plans",
            "id",
        ) and await self._table_has_column("training_plan_days", "id")

    async def _fetchrow(self, query: str, *args: object) -> asyncpg.Record | None:
        """Run one-row SQL after ensuring the pool exists.

        Parameters:
            query: SQL query to execute.
            *args: Positional query arguments.

        Returns:
            asyncpg.Record | None: The matching row, if present.

        Raises:
            Exception: Propagated from asyncpg when the query fails.
        """

        pool = await self._get_pool()
        async with pool.acquire() as connection:
            return await connection.fetchrow(query, *args)

    async def _fetch(self, query: str, *args: object) -> list[asyncpg.Record]:
        """Run a multi-row SQL query after ensuring the pool exists.

        Parameters:
            query: SQL query to execute.
            *args: Positional query arguments.

        Returns:
            list[asyncpg.Record]: Returned rows.

        Raises:
            Exception: Propagated from asyncpg when the query fails.
        """

        pool = await self._get_pool()
        async with pool.acquire() as connection:
            return await connection.fetch(query, *args)

    async def _get_pool(self) -> asyncpg.Pool:
        """Create or reuse the asyncpg pool for the current process.

        Parameters:
            None.

        Returns:
            asyncpg.Pool: Shared connection pool.

        Raises:
            Exception: Propagated from asyncpg when pool creation fails.
        """

        if self._pool is not None:
            return self._pool

        async with self._pool_lock:
            if self._pool is None:
                self._pool = await asyncpg.create_pool(
                    dsn=self._database_url,
                    min_size=1,
                    max_size=5,
                    command_timeout=30,
                    # Supabase transaction poolers do not work well with
                    # asyncpg's statement cache, so we keep it disabled to
                    # match the MCP server compatibility setup.
                    statement_cache_size=0,
                )

        return self._pool

    async def _resolve_user_id(self, subject: str) -> str:
        """Resolve the Supabase app-level user id for one portal subject.

        Parameters:
            subject: Portal subject configured in the environment.

        Returns:
            str: Resolved `public.*` user id used by the wellness tables.

        Raises:
            RuntimeError: Raised when the database contains multiple users and
                no explicit `APEX_PORTAL_USER_ID` is configured.
        """

        schema_variant = await self._get_schema_variant()
        if schema_variant == "legacy":
            raise RuntimeError(
                "The connected portal database uses the legacy subject-based "
                "schema and does not require user-id resolution."
            )

        if self._resolved_user_id is not None:
            return self._resolved_user_id

        async with self._user_id_lock:
            if self._resolved_user_id is not None:
                return self._resolved_user_id

            rows = await self._fetch(
                """
                SELECT DISTINCT user_id
                FROM (
                    SELECT user_id
                    FROM public.daily_nutrition_targets
                    WHERE user_id IS NOT NULL
                    UNION
                    SELECT user_id
                    FROM public.meal_logs
                    WHERE user_id IS NOT NULL
                    UNION
                    SELECT user_id
                    FROM public.activities
                    WHERE user_id IS NOT NULL
                ) candidate_users
                ORDER BY user_id
                """,
            )

            if len(rows) == 1:
                self._resolved_user_id = str(rows[0]["user_id"])
                return self._resolved_user_id

            # The current portal config is subject-based because that is what
            # the upstream MCP layer uses. The newer Supabase wellness tables
            # are keyed by `user_id`, so we prefer an explicit config value
            # when more than one athlete exists in the same database.
            raise RuntimeError(
                "Unable to resolve a unique Supabase user id for "
                f"subject '{subject}'. Set APEX_PORTAL_USER_ID in "
                "backend/.env to choose the correct athlete."
            )

    async def _get_schema_variant(self) -> str:
        """Detect which wellness schema is available in the current database.

        Parameters:
            None.

        Returns:
            str: Either `legacy` or `normalized`.

        Raises:
            RuntimeError: Raised when neither known schema is available.
        """

        if self._schema_variant is not None:
            return self._schema_variant

        async with self._schema_variant_lock:
            if self._schema_variant is not None:
                return self._schema_variant

            row = await self._fetchrow(
                """
                SELECT
                    EXISTS (
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_schema = 'public'
                            AND table_name = 'daily_targets'
                    ) AS has_legacy_targets,
                    EXISTS (
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_schema = 'public'
                            AND table_name = 'daily_nutrition_targets'
                    ) AS has_normalized_targets
                """
            )

            if row and row["has_legacy_targets"]:
                self._schema_variant = "legacy"
            elif row and row["has_normalized_targets"]:
                self._schema_variant = "normalized"
            else:
                raise RuntimeError(
                    "Unable to find a supported APEX wellness schema in the "
                    "connected database."
                )

            return self._schema_variant

    async def _table_has_column(self, table_name: str, column_name: str) -> bool:
        """Return whether a public table exposes a specific column.

        Parameters:
            table_name: Public table name to inspect.
            column_name: Column name expected by a newer schema revision.

        Returns:
            bool: `True` when the column exists in `public.<table_name>`.

        Raises:
            Exception: Propagated from asyncpg when metadata lookup fails.
        """

        row = await self._fetchrow(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                    AND table_name = $1
                    AND column_name = $2
            ) AS has_column
            """,
            table_name,
            column_name,
        )
        return bool(row and row["has_column"])


def _extract_athlete_name(profile_markdown: str) -> str | None:
    """Derive a compact athlete name from the profile markdown title.

    Parameters:
        profile_markdown: Stored profile markdown from `user_profiles`.

    Returns:
        str | None: Best-effort athlete name, or `None` when unavailable.

    Raises:
        This helper does not raise errors directly.

    Example:
        >>> _extract_athlete_name("# Sergio's Endurance Profile")
        'Sergio'
    """

    for raw_line in profile_markdown.splitlines():
        line = raw_line.strip()
        if not line.startswith("#"):
            continue

        heading = line.lstrip("#").strip()
        if heading.endswith("'s Endurance Profile"):
            return heading.removesuffix("'s Endurance Profile").strip()
        if heading:
            return heading

    return None


def _training_plan_summary_from_row(row: Any) -> TrainingPlanSummary:
    """Map a database row into a plan summary model.

    Parameters:
        row: Database row containing plan header fields.

    Returns:
        TrainingPlanSummary: Typed plan summary.

    Raises:
        KeyError: Raised when required row fields are missing.
    """

    return TrainingPlanSummary(
        id=int(row["id"]),
        title=str(row["title"] or ""),
        start_date=row["start_date"],
        end_date=row["end_date"],
        status=str(row["status"] or "draft"),
        goal_markdown=str(row["goal_markdown"] or ""),
        rationale_markdown=str(row["rationale_markdown"] or ""),
        notes_markdown=str(row["notes_markdown"] or ""),
        generation_context=_as_json_object(row["generation_context"]),
        days_count=_as_int(row["days_count"]) or 0,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _training_plan_day_from_row(row: Any) -> TrainingPlanDay:
    """Map a database row into a plan-day model.

    Parameters:
        row: Database row containing plan-day fields.

    Returns:
        TrainingPlanDay: Typed plan-day payload.

    Raises:
        KeyError: Raised when required row fields are missing.
    """

    return TrainingPlanDay(
        id=int(row["id"]),
        plan_id=int(row["plan_id"]),
        plan_date=row["plan_date"],
        day_type=str(row["day_type"] or "training"),
        title=str(row["title"] or ""),
        training_summary=str(row["training_summary"] or ""),
        primary_sport_type=_as_optional_str(row["primary_sport_type"]),
        planned_duration_seconds=_as_int(row["planned_duration_seconds"]),
        planned_distance_meters=_as_float(row["planned_distance_meters"]),
        planned_elevation_gain_meters=_as_float(
            row["planned_elevation_gain_meters"]
        ),
        planned_training_load=_as_float(row["planned_training_load"]),
        target_food_calories=_as_float(row["target_food_calories"]) or 0,
        target_exercise_calories=_as_float(row["target_exercise_calories"]) or 0,
        target_protein_g=_as_float(row["target_protein_g"]) or 0,
        target_carbs_g=_as_float(row["target_carbs_g"]) or 0,
        target_fat_g=_as_float(row["target_fat_g"]) or 0,
        training_sessions=_as_json_object_list(row["training_sessions"]),
        fueling_plan=_as_json_object(row["fueling_plan"]),
        menu_plan=_as_json_object(row["menu_plan"]),
        notes_markdown=str(row["notes_markdown"] or ""),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _build_training_plan_day_comparison(
    planned_day: TrainingPlanDay,
    actual: DailySummary,
    daily_metrics: list[TrainingPlanDailyMetric],
) -> TrainingPlanComparisonDay:
    """Compare one planned day with one actual daily summary.

    Parameters:
        planned_day: Stored food and training plan day.
        actual: Computed daily actuals from existing logs.
        daily_metrics: Wellness metric rows for the same day.

    Returns:
        TrainingPlanComparisonDay: Typed planned-vs-actual comparison row.

    Raises:
        This helper does not raise errors directly.
    """

    protein_adherence = _adherence_percent(
        actual.actual_protein_g,
        planned_day.target_protein_g,
    )
    carbs_adherence = _adherence_percent(
        actual.actual_carbs_g,
        planned_day.target_carbs_g,
    )
    fat_adherence = _adherence_percent(
        actual.actual_fat_g,
        planned_day.target_fat_g,
    )
    macro_scores = [
        score
        for score in (protein_adherence, carbs_adherence, fat_adherence)
        if score is not None
    ]

    return TrainingPlanComparisonDay(
        plan_date=planned_day.plan_date,
        planned=planned_day,
        actual=actual,
        daily_metrics=daily_metrics,
        deltas=TrainingPlanComparisonDeltas(
            food_calories=round(
                actual.actual_food_calories - planned_day.target_food_calories,
                2,
            ),
            exercise_calories=round(
                actual.actual_exercise_calories
                - planned_day.target_exercise_calories,
                2,
            ),
            protein_g=round(
                actual.actual_protein_g - planned_day.target_protein_g,
                2,
            ),
            carbs_g=round(actual.actual_carbs_g - planned_day.target_carbs_g, 2),
            fat_g=round(actual.actual_fat_g - planned_day.target_fat_g, 2),
        ),
        adherence=TrainingPlanComparisonAdherence(
            food_calories_percent=_adherence_percent(
                actual.actual_food_calories,
                planned_day.target_food_calories,
            ),
            exercise_calories_percent=_adherence_percent(
                actual.actual_exercise_calories,
                planned_day.target_exercise_calories,
            ),
            protein_percent=protein_adherence,
            carbs_percent=carbs_adherence,
            fat_percent=fat_adherence,
            macro_average_percent=(
                round(sum(macro_scores) / len(macro_scores), 1)
                if macro_scores
                else None
            ),
        ),
    )


def _adherence_percent(actual: float, planned: float) -> float | None:
    """Return a simple target adherence score from 0 through 100.

    Parameters:
        actual: Actual logged value.
        planned: Planned target value.

    Returns:
        float | None: Rounded adherence percent, or `None` for empty targets.

    Raises:
        This helper does not raise errors directly.
    """

    if planned <= 0:
        return None
    return round(max(0.0, 100.0 - abs(actual - planned) / planned * 100.0), 1)


def _empty_training_plan_comparison_totals() -> dict[str, float]:
    """Return accumulator fields for plan comparison totals.

    Parameters:
        None.

    Returns:
        dict[str, float]: Zeroed numeric accumulator.

    Raises:
        This helper does not raise errors directly.
    """

    return {
        "planned_food_calories": 0.0,
        "actual_food_calories": 0.0,
        "planned_exercise_calories": 0.0,
        "actual_exercise_calories": 0.0,
        "planned_protein_g": 0.0,
        "actual_protein_g": 0.0,
        "planned_carbs_g": 0.0,
        "actual_carbs_g": 0.0,
        "planned_fat_g": 0.0,
        "actual_fat_g": 0.0,
    }


def _add_training_plan_comparison_totals(
    totals: dict[str, float],
    comparison: TrainingPlanComparisonDay,
) -> None:
    """Add one day comparison to plan-level totals.

    Parameters:
        totals: Mutable accumulator returned by
            `_empty_training_plan_comparison_totals`.
        comparison: One compared plan day.

    Returns:
        None.

    Raises:
        This helper does not raise errors directly.
    """

    totals["planned_food_calories"] += comparison.planned.target_food_calories
    totals["actual_food_calories"] += comparison.actual.actual_food_calories
    totals["planned_exercise_calories"] += (
        comparison.planned.target_exercise_calories
    )
    totals["actual_exercise_calories"] += (
        comparison.actual.actual_exercise_calories
    )
    totals["planned_protein_g"] += comparison.planned.target_protein_g
    totals["actual_protein_g"] += comparison.actual.actual_protein_g
    totals["planned_carbs_g"] += comparison.planned.target_carbs_g
    totals["actual_carbs_g"] += comparison.actual.actual_carbs_g
    totals["planned_fat_g"] += comparison.planned.target_fat_g
    totals["actual_fat_g"] += comparison.actual.actual_fat_g


def _finalize_training_plan_comparison_totals(
    totals: dict[str, float],
    days_count: int,
) -> TrainingPlanComparisonTotals:
    """Return rounded totals and plan-level adherence fields.

    Parameters:
        totals: Accumulated numeric totals.
        days_count: Number of compared days.

    Returns:
        TrainingPlanComparisonTotals: Typed aggregate comparison payload.

    Raises:
        This helper does not raise errors directly.
    """

    return TrainingPlanComparisonTotals(
        planned_food_calories=round(totals["planned_food_calories"], 2),
        actual_food_calories=round(totals["actual_food_calories"], 2),
        planned_exercise_calories=round(
            totals["planned_exercise_calories"],
            2,
        ),
        actual_exercise_calories=round(totals["actual_exercise_calories"], 2),
        planned_protein_g=round(totals["planned_protein_g"], 2),
        actual_protein_g=round(totals["actual_protein_g"], 2),
        planned_carbs_g=round(totals["planned_carbs_g"], 2),
        actual_carbs_g=round(totals["actual_carbs_g"], 2),
        planned_fat_g=round(totals["planned_fat_g"], 2),
        actual_fat_g=round(totals["actual_fat_g"], 2),
        food_calories_delta=round(
            totals["actual_food_calories"] - totals["planned_food_calories"],
            2,
        ),
        exercise_calories_delta=round(
            totals["actual_exercise_calories"]
            - totals["planned_exercise_calories"],
            2,
        ),
        protein_g_delta=round(
            totals["actual_protein_g"] - totals["planned_protein_g"],
            2,
        ),
        carbs_g_delta=round(
            totals["actual_carbs_g"] - totals["planned_carbs_g"],
            2,
        ),
        fat_g_delta=round(
            totals["actual_fat_g"] - totals["planned_fat_g"],
            2,
        ),
        food_calories_adherence_percent=_adherence_percent(
            totals["actual_food_calories"],
            totals["planned_food_calories"],
        ),
        exercise_calories_adherence_percent=_adherence_percent(
            totals["actual_exercise_calories"],
            totals["planned_exercise_calories"],
        ),
        days_count=days_count,
    )


def _as_json_object(value: object | None) -> dict[str, Any]:
    """Return a JSON object when the database value has object shape.

    Parameters:
        value: Raw JSONB-compatible database value.

    Returns:
        dict[str, Any]: JSON object, or an empty object for other shapes.

    Raises:
        This helper does not raise errors directly.
    """

    if isinstance(value, dict):
        return value
    return {}


def _as_json_object_list(value: object | None) -> list[dict[str, Any]]:
    """Return a list of JSON objects from a raw JSONB-compatible value.

    Parameters:
        value: Raw JSONB-compatible database value.

    Returns:
        list[dict[str, Any]]: List containing only object-shaped entries.

    Raises:
        This helper does not raise errors directly.
    """

    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _nullable_float(row: Any, key: str) -> float | None:
    """Read an optional float-like value from a row.

    Parameters:
        row: Database row or `None`.
        key: Column name to inspect.

    Returns:
        float | None: Parsed float when present.

    Raises:
        This helper does not raise errors directly.
    """

    if row is None:
        return None
    return _as_float(row[key])


def _record_text(row: asyncpg.Record | None, key: str) -> str:
    """Read a text value from a record only when the column exists.

    Parameters:
        row: Optional asyncpg record returned by a query.
        key: Column name to inspect.

    Returns:
        str: Text value when present, otherwise an empty string.

    Raises:
        This helper does not raise errors directly.
    """

    if row is None or key not in row:
        return ""
    return str(row[key] or "")


def _record_float(row: asyncpg.Record | None, key: str) -> float | None:
    """Read a float-like value from a record only when the column exists.

    Parameters:
        row: Optional asyncpg record returned by a query.
        key: Column name to inspect.

    Returns:
        float | None: Parsed numeric value when present.

    Raises:
        This helper does not raise errors directly.
    """

    if row is None or key not in row:
        return None
    return _as_float(row[key])


def _as_optional_str(value: object) -> str | None:
    """Convert an optional database value into a string.

    Parameters:
        value: Raw database value.

    Returns:
        str | None: String value when present.

    Raises:
        This helper does not raise errors directly.
    """

    if value is None:
        return None
    return str(value)


def _record_int(row: asyncpg.Record | None, key: str) -> int | None:
    """Read an integer-like value from a record only when the column exists.

    Parameters:
        row: Optional asyncpg record returned by a query.
        key: Column name to inspect.

    Returns:
        int | None: Parsed integer value when present.

    Raises:
        This helper does not raise errors directly.
    """

    if row is None or key not in row:
        return None
    return _as_int(row[key])


def _remaining_value(target: float | None, actual: float) -> float | None:
    """Return a rounded remaining value when a target exists.

    Parameters:
        target: Optional target value.
        actual: Actual logged value.

    Returns:
        float | None: Rounded target minus actual value.

    Raises:
        This helper does not raise errors directly.
    """

    if target is None:
        return None
    return round(target - actual, 2)


def _as_float(value: object | None) -> float | None:
    """Convert a database scalar to `float` when possible.

    Parameters:
        value: Raw database value.

    Returns:
        float | None: Parsed float, or `None`.

    Raises:
        This helper does not raise errors directly.
    """

    if value is None:
        return None
    return float(value)


def _as_int(value: object | None) -> int | None:
    """Convert a database scalar to `int` when possible.

    Parameters:
        value: Raw database value.

    Returns:
        int | None: Parsed integer, or `None`.

    Raises:
        This helper does not raise errors directly.
    """

    if value is None:
        return None
    return int(value)


def resolve_window(end_date: date, days: int) -> tuple[date, date]:
    """Return an inclusive date window ending on `end_date`.

    Parameters:
        end_date: Inclusive upper bound for the window.
        days: Number of calendar days to include.

    Returns:
        tuple[date, date]: Inclusive `(date_from, date_to)` window.

    Raises:
        ValueError: If `days` is less than one.

    Example:
        >>> resolve_window(date(2026, 4, 16), 3)
        (datetime.date(2026, 4, 14), datetime.date(2026, 4, 16))
    """

    if days < 1:
        raise ValueError("days must be greater than zero.")

    return end_date - timedelta(days=days - 1), end_date
