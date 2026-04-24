"""Store-level tests for the APEX progress portal backend."""

from __future__ import annotations

import asyncio
from datetime import date

from apex_portal_api.store import PostgresPortalStore


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
