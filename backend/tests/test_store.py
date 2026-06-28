"""Store-level tests for the APEX progress portal backend."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime

from apex_portal_api.models import (
    DailySummary,
    TrainingPlanDailyMetric,
    TrainingPlanDay,
    TrainingPlanDetail,
    TrainingPlanSummary,
)
from apex_portal_api.store import PostgresPortalStore


def build_plan_row(days_count: int = 1) -> dict[str, object]:
    """Build a fake training plan row for store mapping tests.

    Parameters:
        days_count: Number of planned days to expose in the row.

    Returns:
        dict[str, object]: Database-shaped training plan row.

    Raises:
        This helper does not raise errors directly.
    """

    timestamp = datetime(2026, 6, 28, 18, 0, tzinfo=UTC)
    return {
        "id": 1,
        "title": "Next week endurance block",
        "start_date": date(2026, 7, 6),
        "end_date": date(2026, 7, 12),
        "status": "published",
        "goal_markdown": "Lose weight while keeping long-run quality.",
        "rationale_markdown": "Estimated from similar long runs.",
        "notes_markdown": "Use conservative load estimates.",
        "generation_context": {"source": "pytest"},
        "days_count": days_count,
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def build_plan_day_row() -> dict[str, object]:
    """Build a fake training-plan day row for store mapping tests.

    Parameters:
        None.

    Returns:
        dict[str, object]: Database-shaped training-plan day row.

    Raises:
        This helper does not raise errors directly.
    """

    timestamp = datetime(2026, 6, 28, 18, 0, tzinfo=UTC)
    return {
        "id": 10,
        "plan_id": 1,
        "plan_date": date(2026, 7, 6),
        "day_type": "training",
        "title": "Long aerobic run",
        "training_summary": "2 hour easy run with steady fueling.",
        "primary_sport_type": "run",
        "planned_duration_seconds": 7200,
        "planned_distance_meters": 20000.0,
        "planned_elevation_gain_meters": 250.0,
        "planned_training_load": 120.0,
        "target_food_calories": 2800.0,
        "target_exercise_calories": 1200.0,
        "target_protein_g": 150.0,
        "target_carbs_g": 360.0,
        "target_fat_g": 75.0,
        "training_sessions": [{"sport_type": "run", "duration_seconds": 7200}],
        "fueling_plan": {"during": "60 g carbs/hour"},
        "menu_plan": {"breakfast": "oats and banana"},
        "notes_markdown": "Use conservative load estimate.",
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def test_list_products_maps_food_product_rows() -> None:
    """Ensure product rows are converted into typed portal models.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: Raised when the row mapping changes unexpectedly.
    """

    store = PostgresPortalStore("postgresql://example")

    async def fake_fetch(query: str, *args: object) -> list[dict[str, object]]:
        """Return deterministic product rows for the mapping test.

        Parameters:
            query: SQL query requested by the store.
            *args: Query arguments supplied by the caller.

        Returns:
            list[dict[str, object]]: Fake food product rows.

        Raises:
            AssertionError: Raised when the subject argument is unexpected.
        """

        assert "FROM public.food_items" in query
        assert "usage_count AS usage_count" in query
        assert args == ()
        return [
            {
                "id": "food-7",
                "name": "Greek yogurt",
                "default_serving_g": 170.0,
                "calories_per_100g": 97.4,
                "carbs_g_per_100g": 3.6,
                "protein_g_per_100g": 9.8,
                "fat_g_per_100g": 5.0,
                "usage_count": 14,
            }
        ]

    store._fetch = fake_fetch  # type: ignore[method-assign]
    store._get_schema_variant = (  # type: ignore[method-assign]
        lambda: asyncio.sleep(0, result="normalized")
    )
    store._table_has_column = (  # type: ignore[method-assign]
        lambda table_name, column_name: asyncio.sleep(0, result=True)
    )

    products = asyncio.run(store.list_products("athlete-1"))

    assert len(products) == 1
    assert products[0].id == "food-7"
    assert products[0].name == "Greek yogurt"
    assert products[0].default_serving_g == 170.0
    assert products[0].fat_g_per_100g == 5.0
    assert products[0].usage_count == 14


def test_list_products_defaults_usage_count_when_column_is_missing() -> None:
    """Ensure product rows stay readable before the usage-count migration lands.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: Raised when the fallback query stops returning zero.
    """

    store = PostgresPortalStore("postgresql://example")

    async def fake_fetch(query: str, *args: object) -> list[dict[str, object]]:
        """Return deterministic product rows for the fallback mapping test.

        Parameters:
            query: SQL query requested by the store.
            *args: Query arguments supplied by the caller.

        Returns:
            list[dict[str, object]]: Fake product rows with fallback usage count.

        Raises:
            AssertionError: Raised when the fallback SQL changes unexpectedly.
        """

        assert "0 AS usage_count" in query
        assert args == ()
        return [
            {
                "id": "food-8",
                "name": "Banana",
                "default_serving_g": 118.0,
                "calories_per_100g": 89.0,
                "carbs_g_per_100g": 23.0,
                "protein_g_per_100g": 1.1,
                "fat_g_per_100g": 0.3,
                "usage_count": 0,
            }
        ]

    store._fetch = fake_fetch  # type: ignore[method-assign]
    store._get_schema_variant = (  # type: ignore[method-assign]
        lambda: asyncio.sleep(0, result="normalized")
    )
    store._table_has_column = (  # type: ignore[method-assign]
        lambda table_name, column_name: asyncio.sleep(0, result=False)
    )

    products = asyncio.run(store.list_products("athlete-1"))

    assert len(products) == 1
    assert products[0].name == "Banana"
    assert products[0].usage_count == 0


def test_daily_metric_series_groups_rows_by_metric_type() -> None:
    """Ensure daily metrics are grouped into chart-ready series.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: Raised when dynamic metrics stop grouping correctly.
    """

    store = PostgresPortalStore("postgresql://example")

    async def fake_fetch(query: str, *args: object) -> list[dict[str, object]]:
        """Return deterministic daily metric rows for the grouping test.

        Parameters:
            query: SQL query requested by the store.
            *args: Query arguments supplied by the caller.

        Returns:
            list[dict[str, object]]: Fake daily metric rows.

        Raises:
            AssertionError: Raised when the query or arguments change.
        """

        assert "FROM public.daily_metrics" in query
        assert "GROUP BY metric_type, metric_date" in query
        assert args == ("athlete-1", date(2026, 4, 12), date(2026, 4, 14))
        return [
            {
                "metric_type": "sleep_hours",
                "metric_date": date(2026, 4, 12),
                "value": 7.28,
            },
            {
                "metric_type": "sleep_hours",
                "metric_date": date(2026, 4, 13),
                "value": 8.37,
            },
            {
                "metric_type": "readiness_score",
                "metric_date": date(2026, 4, 13),
                "value": 82.0,
            },
        ]

    store._fetch = fake_fetch  # type: ignore[method-assign]
    store._table_has_column = (  # type: ignore[method-assign]
        lambda table_name, column_name: asyncio.sleep(0, result=True)
    )

    series = asyncio.run(
        store._get_daily_metric_series(
            "athlete-1",
            date(2026, 4, 12),
            date(2026, 4, 14),
        )
    )

    assert [metric.metric_type for metric in series] == [
        "readiness_score",
        "sleep_hours",
    ]
    assert series[1].points[0].date == date(2026, 4, 12)
    assert series[1].points[0].value == 7.28
    assert series[1].points[1].value == 8.37


def test_daily_metric_series_returns_empty_when_table_is_missing() -> None:
    """Ensure missing `daily_metrics` support does not break trends.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: Raised when missing metadata no longer returns empty.
    """

    store = PostgresPortalStore("postgresql://example")

    store._table_has_column = (  # type: ignore[method-assign]
        lambda table_name, column_name: asyncio.sleep(0, result=False)
    )

    series = asyncio.run(
        store._get_daily_metric_series(
            "athlete-1",
            date(2026, 4, 12),
            date(2026, 4, 14),
        )
    )

    assert series == []


def test_default_date_considers_latest_daily_metric_date() -> None:
    """Ensure dynamic metrics can anchor the default trend window.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: Raised when daily metrics stop influencing defaults.
    """

    store = PostgresPortalStore("postgresql://example")

    async def fake_fetchrow(query: str, *args: object) -> dict[str, object]:
        """Return an older tracked day for the default-date query.

        Parameters:
            query: SQL query requested by the store.
            *args: Query arguments supplied by the caller.

        Returns:
            dict[str, object]: Fake aggregate default-day row.

        Raises:
            AssertionError: Raised when the query or arguments change.
        """

        assert "MAX(day) AS default_day" in query
        assert args == ("athlete-1", date(2026, 4, 24))
        return {"default_day": date(2026, 4, 21)}

    store._fetchrow = fake_fetchrow  # type: ignore[method-assign]
    store._get_schema_variant = (  # type: ignore[method-assign]
        lambda: asyncio.sleep(0, result="legacy")
    )
    store._get_latest_daily_metric_date = (  # type: ignore[method-assign]
        lambda subject, fallback_date: asyncio.sleep(0, result=date(2026, 4, 23))
    )

    default_date = asyncio.run(
        store.get_default_date("athlete-1", date(2026, 4, 24))
    )

    assert default_date == date(2026, 4, 23)


def test_get_history_days_maps_macro_targets() -> None:
    """Ensure history rows include target macros from daily targets.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: Raised when target fields are not mapped correctly.
    """

    store = PostgresPortalStore("postgresql://example")

    async def fake_fetch(query: str, *args: object) -> list[dict[str, object]]:
        """Return one deterministic history row for the mapping test.

        Parameters:
            query: SQL query requested by the store.
            *args: Query arguments supplied by the caller.

        Returns:
            list[dict[str, object]]: Fake history rows with macro targets.

        Raises:
            AssertionError: Raised when the query or arguments differ.
        """

        assert "target_protein_g" in query
        assert args == (
            "user-1",
            "Europe/Madrid",
            date(2026, 4, 1),
            date(2026, 4, 16),
        )
        return [
            {
                "day": date(2026, 4, 16),
                "target_food_calories": 2490.0,
                "target_protein_g": 150.0,
                "target_carbs_g": 290.0,
                "target_fat_g": 68.0,
                "actual_food_calories": 725.0,
                "actual_exercise_calories": 976.0,
                "net_calories": -251.0,
                "actual_protein_g": 42.0,
                "actual_carbs_g": 115.0,
                "actual_fat_g": 12.0,
                "meals_count": 2,
                "meal_items_count": 10,
                "activities_count": 1,
                "total_distance_meters": 13020.0,
                "total_moving_time_seconds": 3933,
                "total_elevation_gain_meters": 127.0,
                "total_suffer_score": 212.0,
            }
        ]

    async def fake_resolve_user_id(subject: str) -> str:
        """Return a deterministic user id for the history mapping test.

        Parameters:
            subject: Portal subject passed into the store helper.

        Returns:
            str: Fake Supabase user id.

        Raises:
            AssertionError: Raised when the test subject changes unexpectedly.
        """

        assert subject == "athlete-1"
        return "user-1"

    store._fetch = fake_fetch  # type: ignore[method-assign]
    store._resolve_user_id = fake_resolve_user_id  # type: ignore[method-assign]
    store._get_schema_variant = (  # type: ignore[method-assign]
        lambda: asyncio.sleep(0, result="normalized")
    )

    history_days = asyncio.run(
        store._get_history_days("athlete-1", date(2026, 4, 1), date(2026, 4, 16))
    )

    assert len(history_days) == 1
    assert history_days[0].target_protein_g == 150.0
    assert history_days[0].target_carbs_g == 290.0
    assert history_days[0].target_fat_g == 68.0


def test_legacy_list_products_uses_subject_scoped_table() -> None:
    """Ensure legacy-schema product rows still map into portal models.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: Raised when the legacy query changes unexpectedly.
    """

    store = PostgresPortalStore("postgresql://example")

    async def fake_fetch(query: str, *args: object) -> list[dict[str, object]]:
        """Return deterministic legacy product rows for the mapping test.

        Parameters:
            query: SQL query requested by the store.
            *args: Query arguments supplied by the caller.

        Returns:
            list[dict[str, object]]: Fake legacy product rows.

        Raises:
            AssertionError: Raised when the query or subject changes.
        """

        assert "FROM public.food_products" in query
        assert "usage_count AS usage_count" in query
        assert args == ("athlete-1",)
        return [
            {
                "id": 7,
                "name": "Legacy yogurt",
                "default_serving_g": 170.0,
                "calories_per_100g": 97.4,
                "carbs_g_per_100g": 3.6,
                "protein_g_per_100g": 9.8,
                "fat_g_per_100g": 5.0,
                "usage_count": 8,
            }
        ]

    store._fetch = fake_fetch  # type: ignore[method-assign]
    store._get_schema_variant = (  # type: ignore[method-assign]
        lambda: asyncio.sleep(0, result="legacy")
    )
    store._table_has_column = (  # type: ignore[method-assign]
        lambda table_name, column_name: asyncio.sleep(0, result=True)
    )

    products = asyncio.run(store.list_products("athlete-1"))

    assert len(products) == 1
    assert products[0].id == "7"
    assert products[0].name == "Legacy yogurt"
    assert products[0].usage_count == 8


def test_list_training_plans_maps_days_count_and_filters() -> None:
    """Ensure plan list rows map into typed summaries with filters."""

    store = PostgresPortalStore("postgresql://example")

    async def fake_fetch(query: str, *args: object) -> list[dict[str, object]]:
        """Return deterministic training plan rows for the mapping test."""

        assert "FROM public.training_plans p" in query
        assert "COUNT(d.id)::INTEGER AS days_count" in query
        assert args == (
            "athlete-1",
            date(2026, 7, 1),
            date(2026, 7, 31),
            "published",
        )
        return [build_plan_row(days_count=7)]

    store._fetch = fake_fetch  # type: ignore[method-assign]
    store._training_plan_tables_available = (  # type: ignore[method-assign]
        lambda: asyncio.sleep(0, result=True)
    )

    plans = asyncio.run(
        store.list_training_plans(
            "athlete-1",
            date_from=date(2026, 7, 1),
            date_to=date(2026, 7, 31),
            status="published",
        )
    )

    assert len(plans) == 1
    assert plans[0].title == "Next week endurance block"
    assert plans[0].days_count == 7
    assert plans[0].generation_context["source"] == "pytest"


def test_get_training_plan_maps_child_days_and_json_fields() -> None:
    """Ensure plan detail rows include ordered planned days and JSON fields."""

    store = PostgresPortalStore("postgresql://example")

    async def fake_fetchrow(query: str, *args: object) -> dict[str, object]:
        """Return one deterministic plan header row."""

        assert "FROM public.training_plans p" in query
        assert args == ("athlete-1", 1)
        return build_plan_row(days_count=1)

    async def fake_fetch(query: str, *args: object) -> list[dict[str, object]]:
        """Return one deterministic plan day row."""

        assert "FROM public.training_plan_days" in query
        assert args == ("athlete-1", 1)
        return [build_plan_day_row()]

    store._fetchrow = fake_fetchrow  # type: ignore[method-assign]
    store._fetch = fake_fetch  # type: ignore[method-assign]
    store._training_plan_tables_available = (  # type: ignore[method-assign]
        lambda: asyncio.sleep(0, result=True)
    )

    plan = asyncio.run(store.get_training_plan("athlete-1", 1))

    assert plan is not None
    assert plan.days_count == 1
    assert plan.days[0].training_sessions[0]["duration_seconds"] == 7200
    assert plan.days[0].fueling_plan["during"] == "60 g carbs/hour"
    assert plan.days[0].menu_plan["breakfast"] == "oats and banana"


def test_compare_training_plan_computes_deltas_totals_and_metrics() -> None:
    """Ensure comparison math matches the MCP planned-vs-actual semantics."""

    store = PostgresPortalStore("postgresql://example")
    plan_day = TrainingPlanDay(**build_plan_day_row())
    plan = TrainingPlanDetail(
        **TrainingPlanSummary(**build_plan_row(days_count=1)).model_dump(),
        days=[plan_day],
    )

    async def fake_get_training_plan(
        subject: str,
        plan_id: int,
    ) -> TrainingPlanDetail:
        """Return one deterministic plan detail."""

        assert subject == "athlete-1"
        assert plan_id == 1
        return plan

    async def fake_get_daily_summary(
        subject: str,
        target_date: date,
    ) -> DailySummary:
        """Return deterministic actuals for one comparison day."""

        assert subject == "athlete-1"
        assert target_date == date(2026, 7, 6)
        return DailySummary(
            target_date=target_date,
            target_food_calories=2800.0,
            target_exercise_calories=1200.0,
            target_protein_g=150.0,
            target_carbs_g=360.0,
            target_fat_g=75.0,
            actual_food_calories=2600.0,
            actual_exercise_calories=1100.0,
            actual_protein_g=145.0,
            actual_carbs_g=330.0,
            actual_fat_g=80.0,
            remaining_food_calories=200.0,
            remaining_protein_g=5.0,
            remaining_carbs_g=30.0,
            remaining_fat_g=-5.0,
            net_calories=1500.0,
            meals_count=1,
            meal_items_count=1,
            activities_count=1,
        )

    async def fake_get_daily_metrics_for_day(
        subject: str,
        target_date: date,
    ) -> list[TrainingPlanDailyMetric]:
        """Return deterministic wellness metric context."""

        assert subject == "athlete-1"
        assert target_date == date(2026, 7, 6)
        return [
            TrainingPlanDailyMetric(
                metric_date=target_date,
                metric_type="sleep_hours",
                value=7.5,
            )
        ]

    store.get_training_plan = fake_get_training_plan  # type: ignore[method-assign]
    store._get_daily_summary = fake_get_daily_summary  # type: ignore[method-assign]
    store._get_daily_metrics_for_day = (  # type: ignore[method-assign]
        fake_get_daily_metrics_for_day
    )

    comparison = asyncio.run(store.compare_training_plan("athlete-1", 1))

    assert comparison is not None
    assert comparison.days_count == 1
    assert comparison.days[0].deltas.food_calories == -200.0
    assert comparison.days[0].deltas.exercise_calories == -100.0
    assert comparison.days[0].deltas.carbs_g == -30.0
    assert comparison.days[0].adherence.food_calories_percent == 92.9
    assert comparison.days[0].daily_metrics[0].metric_type == "sleep_hours"
    assert comparison.totals.food_calories_delta == -200.0
    assert comparison.totals.exercise_calories_delta == -100.0
