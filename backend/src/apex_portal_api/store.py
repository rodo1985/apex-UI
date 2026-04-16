"""Supabase/Postgres read queries for the APEX progress portal."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Any

import asyncpg

from apex_portal_api.models import (
    Activity,
    DailySnapshot,
    DailySummary,
    HistoryDay,
    HistoryResponse,
    Meal,
    MealItem,
    PortalProfile,
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
    """Read portal data from the APEX Supabase/Postgres application schema.

    Parameters:
        database_url: Asyncpg-compatible Postgres connection string.
        athlete_name_override: Optional display-name override for the profile.
        portal_user_id: Optional explicit APEX `users.id` binding.

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
    ) -> None:
        """Store connection details for later lazy pool creation.

        Parameters:
            database_url: Asyncpg-compatible Postgres connection string.
            athlete_name_override: Optional display-name override.
            portal_user_id: Optional explicit APEX `users.id` binding.

        Returns:
            None.

        Raises:
            This initializer does not raise errors directly.
        """

        self._database_url = database_url
        self._athlete_name_override = athlete_name_override
        self._portal_user_id = portal_user_id
        self._resolved_user_id = portal_user_id
        self._pool: asyncpg.Pool | None = None
        self._pool_lock = asyncio.Lock()

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

        user_id = await self._resolve_user_id(subject)
        _, window_end = _utc_day_bounds(fallback_date)
        row = await self._fetchrow(
            """
            WITH tracked_dates AS (
                SELECT target_date AS day
                FROM daily_nutrition_targets
                WHERE user_id = $1 AND target_date <= $2
                UNION ALL
                SELECT (logged_at AT TIME ZONE 'UTC')::date AS day
                FROM meal_logs
                WHERE user_id = $1 AND logged_at < $3
                UNION ALL
                SELECT (start_time AT TIME ZONE 'UTC')::date AS day
                FROM activities
                WHERE user_id = $1 AND start_time < $3
            )
            SELECT MAX(day) AS default_day
            FROM tracked_dates
            WHERE day IS NOT NULL
            """,
            user_id,
            fallback_date,
            window_end,
        )

        return row["default_day"] if row and row["default_day"] else fallback_date

    async def get_profile(self, subject: str) -> PortalProfile:
        """Read the athlete context from the APEX and MCP profile tables.

        Parameters:
            subject: Stable subject configured for the portal.

        Returns:
            PortalProfile: Header context for the portal shell.

        Raises:
            Exception: Propagated from asyncpg when the query fails.
        """

        user_id = await self._resolve_user_id(subject)
        profile_row = await self._fetchrow(
            """
            SELECT *
            FROM user_profiles
            WHERE subject = $1
            """,
            subject,
        )
        user_row = await self._fetchrow(
            """
            SELECT
                u.id,
                u.name,
                u.email,
                u.weight_kg,
                u.height_cm,
                u.ftp,
                u.daily_calorie_target,
                u.protein_target_g,
                u.carbs_target_g,
                u.fat_target_g,
                g.description AS goal_description,
                g.phase_name,
                g.weekly_tss_target,
                g.weekly_hours_target
            FROM users u
            LEFT JOIN goals g
                ON g.user_id = u.id
            WHERE u.id = $1
            """,
            user_id,
        )

        profile_markdown = _record_text(profile_row, "profile_markdown")
        if not profile_markdown:
            profile_markdown = _build_profile_markdown(user_row)

        athlete_name = (
            self._athlete_name_override
            or _record_text(user_row, "name")
            or _extract_athlete_name(profile_markdown)
            or "Athlete"
        )

        return PortalProfile(
            athlete_name=athlete_name,
            subject=subject,
            weight_kg=_record_float(profile_row, "weight_kg")
            or _record_float(user_row, "weight_kg"),
            height_cm=_record_float(profile_row, "height_cm")
            or _record_float(user_row, "height_cm"),
            ftp_watts=_record_int(profile_row, "ftp_watts")
            or _record_int(user_row, "ftp"),
            profile_markdown=profile_markdown,
            diet_goals_markdown=_build_diet_goals_markdown(user_row),
            training_goals_markdown=_build_training_goals_markdown(user_row),
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
        """Compute target-vs-actual metrics using the APEX application schema.

        Parameters:
            subject: Stable subject configured for the portal.
            target_date: Business date to summarize.

        Returns:
            DailySummary: Daily metrics aligned with the APEX app records.

        Raises:
            Exception: Propagated from asyncpg when the summary queries fail.
        """

        user_id = await self._resolve_user_id(subject)
        window_start, window_end = _utc_day_bounds(target_date)

        target_row = await self._fetchrow(
            """
            SELECT
                calories AS target_food_calories,
                protein_g AS target_protein_g,
                carbs_g AS target_carbs_g,
                fat_g AS target_fat_g
            FROM daily_nutrition_targets
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
            FROM meal_logs ml
            LEFT JOIN meal_ingredients mi
                ON mi.meal_log_id = ml.id
            WHERE ml.user_id = $1
                AND ml.logged_at >= $2
                AND ml.logged_at < $3
            """,
            user_id,
            window_start,
            window_end,
        )
        activity_row = await self._fetchrow(
            """
            SELECT
                COALESCE(SUM(COALESCE(calories, 0)), 0) AS actual_exercise_calories,
                COUNT(id)::INTEGER AS activities_count
            FROM activities
            WHERE user_id = $1
                AND start_time >= $2
                AND start_time < $3
            """,
            user_id,
            window_start,
            window_end,
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
            target_exercise_calories=None,
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

        user_id = await self._resolve_user_id(subject)
        window_start, window_end = _utc_day_bounds(target_date)

        meal_rows = await self._fetch(
            """
            SELECT id, meal_type, meal_name, source, logged_at
            FROM meal_logs
            WHERE user_id = $1
                AND logged_at >= $2
                AND logged_at < $3
            ORDER BY logged_at ASC, id ASC
            """,
            user_id,
            window_start,
            window_end,
        )
        if not meal_rows:
            return []

        meal_ids = [str(row["id"]) for row in meal_rows]
        item_rows = await self._fetch(
            """
            SELECT
                id,
                meal_log_id,
                food_id,
                name,
                quantity_g,
                calories,
                protein_g,
                carbs_g,
                fat_g
            FROM meal_ingredients
            WHERE meal_log_id = ANY($1::varchar[])
            ORDER BY meal_log_id, id
            """,
            meal_ids,
        )

        items_by_meal: dict[str, list[MealItem]] = defaultdict(list)
        for row in item_rows:
            items_by_meal[str(row["meal_log_id"])].append(
                MealItem(
                    id=str(row["id"]),
                    product_id=str(row["food_id"]) if row["food_id"] else None,
                    ingredient_name=str(row["name"]),
                    grams=_as_float(row["quantity_g"]) or 0,
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
            # table so the portal stays aligned with the raw ingredients.
            meals.append(
                Meal(
                    id=meal_id,
                    meal_label=_build_meal_label(row),
                    notes_markdown=_build_meal_notes(row),
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

        user_id = await self._resolve_user_id(subject)
        window_start, window_end = _utc_day_bounds(target_date)

        rows = await self._fetch(
            """
            SELECT
                id,
                sport,
                name,
                distance_m,
                duration_seconds,
                elevation_m,
                avg_hr,
                max_hr,
                calories,
                tss,
                strava_id
            FROM activities
            WHERE user_id = $1
                AND start_time >= $2
                AND start_time < $3
            ORDER BY start_time ASC, id ASC
            """,
            user_id,
            window_start,
            window_end,
        )

        return [
            Activity(
                id=str(row["id"]),
                title=str(row["name"]),
                activity_date=target_date,
                sport_type=_humanize_label(_record_text(row, "sport")) or None,
                distance_meters=_as_float(row["distance_m"]),
                moving_time_seconds=_as_int(row["duration_seconds"]),
                total_elevation_gain_meters=_as_float(row["elevation_m"]),
                average_heartrate=_as_float(row["avg_hr"]),
                max_heartrate=_as_float(row["max_hr"]),
                calories=_as_float(row["calories"]),
                suffer_score=_as_float(row["tss"]),
                notes_markdown="",
                external_source="strava" if row["strava_id"] else None,
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

        user_id = await self._resolve_user_id(subject)
        window_start, window_end = _utc_day_bounds(date_from)
        _, final_window_end = _utc_day_bounds(date_to)

        rows = await self._fetch(
            """
            WITH tracked_dates AS (
                SELECT target_date AS day
                FROM daily_nutrition_targets
                WHERE user_id = $1 AND target_date BETWEEN $2 AND $3
                UNION
                SELECT (logged_at AT TIME ZONE 'UTC')::date AS day
                FROM meal_logs
                WHERE user_id = $1
                    AND logged_at >= $4
                    AND logged_at < $5
                UNION
                SELECT (start_time AT TIME ZONE 'UTC')::date AS day
                FROM activities
                WHERE user_id = $1
                    AND start_time >= $4
                    AND start_time < $5
            ),
            meal_totals AS (
                SELECT
                    (ml.logged_at AT TIME ZONE 'UTC')::date AS day,
                    COALESCE(SUM(mi.calories), 0) AS actual_food_calories,
                    COALESCE(SUM(mi.protein_g), 0) AS actual_protein_g,
                    COALESCE(SUM(mi.carbs_g), 0) AS actual_carbs_g,
                    COALESCE(SUM(mi.fat_g), 0) AS actual_fat_g,
                    COUNT(DISTINCT ml.id)::INTEGER AS meals_count,
                    COUNT(mi.id)::INTEGER AS meal_items_count
                FROM meal_logs ml
                LEFT JOIN meal_ingredients mi
                    ON mi.meal_log_id = ml.id
                WHERE ml.user_id = $1
                    AND ml.logged_at >= $4
                    AND ml.logged_at < $5
                GROUP BY (ml.logged_at AT TIME ZONE 'UTC')::date
            ),
            activity_totals AS (
                SELECT
                    (start_time AT TIME ZONE 'UTC')::date AS day,
                    COALESCE(
                        SUM(COALESCE(calories, 0)),
                        0
                    ) AS actual_exercise_calories,
                    COALESCE(
                        SUM(COALESCE(distance_m, 0)),
                        0
                    ) AS total_distance_meters,
                    COALESCE(
                        SUM(COALESCE(duration_seconds, 0)),
                        0
                    )::INTEGER AS total_moving_time_seconds,
                    COALESCE(
                        SUM(COALESCE(elevation_m, 0)),
                        0
                    ) AS total_elevation_gain_meters,
                    COALESCE(SUM(COALESCE(tss, 0)), 0) AS total_suffer_score,
                    COUNT(id)::INTEGER AS activities_count
                FROM activities
                WHERE user_id = $1
                    AND start_time >= $4
                    AND start_time < $5
                GROUP BY (start_time AT TIME ZONE 'UTC')::date
            )
            SELECT
                tracked_dates.day,
                dt.calories AS target_food_calories,
                COALESCE(mt.actual_food_calories, 0) AS actual_food_calories,
                COALESCE(
                    at.actual_exercise_calories,
                    0
                ) AS actual_exercise_calories,
                COALESCE(mt.actual_food_calories, 0)
                    - COALESCE(at.actual_exercise_calories, 0) AS net_calories,
                COALESCE(mt.actual_protein_g, 0) AS actual_protein_g,
                COALESCE(mt.actual_carbs_g, 0) AS actual_carbs_g,
                COALESCE(mt.actual_fat_g, 0) AS actual_fat_g,
                COALESCE(mt.meals_count, 0) AS meals_count,
                COALESCE(mt.meal_items_count, 0) AS meal_items_count,
                COALESCE(at.activities_count, 0) AS activities_count,
                COALESCE(at.total_distance_meters, 0) AS total_distance_meters,
                COALESCE(
                    at.total_moving_time_seconds,
                    0
                ) AS total_moving_time_seconds,
                COALESCE(
                    at.total_elevation_gain_meters,
                    0
                ) AS total_elevation_gain_meters,
                COALESCE(at.total_suffer_score, 0) AS total_suffer_score
            FROM tracked_dates
            LEFT JOIN daily_nutrition_targets dt
                ON dt.user_id = $1 AND dt.target_date = tracked_dates.day
            LEFT JOIN meal_totals mt
                ON mt.day = tracked_dates.day
            LEFT JOIN activity_totals at
                ON at.day = tracked_dates.day
            ORDER BY tracked_dates.day DESC
            """,
            user_id,
            date_from,
            date_to,
            window_start,
            final_window_end,
        )

        return [
            HistoryDay(
                date=row["day"],
                target_food_calories=_nullable_float(row, "target_food_calories"),
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

    async def _resolve_user_id(self, subject: str) -> str:
        """Resolve the APEX `users.id` bound to the configured portal.

        Parameters:
            subject: Stable subject configured for the portal.

        Returns:
            str: The matching APEX `users.id` value.

        Raises:
            RuntimeError: Raised when the user binding cannot be resolved.
            Exception: Propagated from asyncpg when the queries fail.
        """

        if self._resolved_user_id:
            return self._resolved_user_id

        profile_row = await self._fetchrow(
            """
            SELECT login
            FROM user_profiles
            WHERE subject = $1
            """,
            subject,
        )
        login_value = _record_text(profile_row, "login")
        if login_value:
            user_row = await self._fetchrow(
                """
                SELECT id
                FROM users
                WHERE id = $1 OR email = $1
                LIMIT 1
                """,
                login_value,
            )
            if user_row:
                self._resolved_user_id = str(user_row["id"])
                return self._resolved_user_id

        count_row = await self._fetchrow("SELECT COUNT(*)::INTEGER AS count FROM users")
        if _as_int(count_row["count"] if count_row else None) == 1:
            only_user_row = await self._fetchrow(
                """
                SELECT id
                FROM users
                ORDER BY created_at ASC
                LIMIT 1
                """
            )
            if only_user_row:
                self._resolved_user_id = str(only_user_row["id"])
                return self._resolved_user_id

        raise RuntimeError(
            "Unable to resolve the portal user. Set APEX_PORTAL_USER_ID to an "
            "explicit users.id value for this deployment."
        )

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


def _utc_day_bounds(target_date: date) -> tuple[datetime, datetime]:
    """Return inclusive-exclusive UTC bounds for one business day.

    Parameters:
        target_date: Calendar day to convert into UTC timestamps.

    Returns:
        tuple[datetime, datetime]: Start and end timestamps in UTC.

    Raises:
        This helper does not raise errors directly.
    """

    window_start = datetime(
        target_date.year,
        target_date.month,
        target_date.day,
        tzinfo=UTC,
    )
    window_end = window_start + timedelta(days=1)
    return window_start, window_end


def _build_profile_markdown(user_row: asyncpg.Record | None) -> str:
    """Create a lightweight profile fallback from the APEX user row.

    Parameters:
        user_row: Optional joined `users` and `goals` record.

    Returns:
        str: Markdown summary used when the MCP profile document is absent.

    Raises:
        This helper does not raise errors directly.
    """

    athlete_name = _record_text(user_row, "name") or "Athlete"
    lines = [f"# {athlete_name}'s APEX Profile", ""]

    email = _record_text(user_row, "email")
    if email:
        lines.append(f"- Email: {email}")

    weight_kg = _record_float(user_row, "weight_kg")
    if weight_kg is not None:
        lines.append(f"- Weight: {weight_kg:.1f} kg")

    height_cm = _record_int(user_row, "height_cm")
    if height_cm is not None:
        lines.append(f"- Height: {height_cm} cm")

    ftp_watts = _record_int(user_row, "ftp")
    if ftp_watts is not None:
        lines.append(f"- FTP: {ftp_watts} W")

    goal_description = _record_text(user_row, "goal_description")
    if goal_description:
        lines.append(f"- Current goal: {goal_description}")

    return "\n".join(lines).strip()


def _build_diet_goals_markdown(user_row: asyncpg.Record | None) -> str:
    """Build a compact nutrition-target summary from the APEX user row.

    Parameters:
        user_row: Optional joined `users` and `goals` record.

    Returns:
        str: Markdown block describing the stored nutrition targets.

    Raises:
        This helper does not raise errors directly.
    """

    calories = _record_int(user_row, "daily_calorie_target")
    protein = _record_int(user_row, "protein_target_g")
    carbs = _record_int(user_row, "carbs_target_g")
    fat = _record_int(user_row, "fat_target_g")

    if all(value is None for value in [calories, protein, carbs, fat]):
        return ""

    lines = ["## Nutrition targets", ""]
    if calories is not None:
        lines.append(f"- Daily calories: {calories} kcal")
    if protein is not None:
        lines.append(f"- Protein: {protein} g")
    if carbs is not None:
        lines.append(f"- Carbs: {carbs} g")
    if fat is not None:
        lines.append(f"- Fat: {fat} g")
    return "\n".join(lines)


def _build_training_goals_markdown(user_row: asyncpg.Record | None) -> str:
    """Build a compact training-goal summary from the APEX goal row.

    Parameters:
        user_row: Optional joined `users` and `goals` record.

    Returns:
        str: Markdown block describing the current training focus.

    Raises:
        This helper does not raise errors directly.
    """

    goal_description = _record_text(user_row, "goal_description")
    phase_name = _record_text(user_row, "phase_name")
    weekly_tss_target = _record_int(user_row, "weekly_tss_target")
    weekly_hours_target = _record_float(user_row, "weekly_hours_target")

    if not any([goal_description, phase_name, weekly_tss_target, weekly_hours_target]):
        return ""

    lines = ["## Training goals", ""]
    if goal_description:
        lines.append(f"- Goal: {goal_description}")
    if phase_name:
        lines.append(f"- Phase: {phase_name}")
    if weekly_tss_target is not None:
        lines.append(f"- Weekly TSS target: {weekly_tss_target}")
    if weekly_hours_target is not None:
        lines.append(f"- Weekly hours target: {weekly_hours_target:.1f} h")
    return "\n".join(lines)


def _build_meal_label(row: asyncpg.Record | None) -> str:
    """Return the best visible meal label for one meal row.

    Parameters:
        row: Optional `meal_logs` record.

    Returns:
        str: Human-readable meal title.

    Raises:
        This helper does not raise errors directly.
    """

    meal_name = _record_text(row, "meal_name")
    if meal_name:
        return meal_name

    meal_type = _humanize_label(_record_text(row, "meal_type"))
    return meal_type or "Meal"


def _build_meal_notes(row: asyncpg.Record | None) -> str:
    """Build a short note line for a meal row.

    Parameters:
        row: Optional `meal_logs` record.

    Returns:
        str: Small supporting note for the meal card.

    Raises:
        This helper does not raise errors directly.
    """

    if row is None:
        return ""

    notes: list[str] = []
    source = _humanize_label(_record_text(row, "source"))
    if source and source.lower() != "manual":
        notes.append(f"Source: {source}")

    if "logged_at" in row and row["logged_at"] is not None:
        logged_at = row["logged_at"].astimezone(UTC)
        notes.append(f"Logged {logged_at.strftime('%H:%M UTC')}")

    return " • ".join(notes)


def _humanize_label(value: str) -> str:
    """Convert an underscored storage label into display text.

    Parameters:
        value: Raw storage label such as `easy_z2`.

    Returns:
        str: Human-readable label such as `Easy Z2`.

    Raises:
        This helper does not raise errors directly.
    """

    cleaned = value.strip()
    if not cleaned:
        return ""
    return cleaned.replace("_", " ").title()


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
