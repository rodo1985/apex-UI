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

        if "FROM public.food_items" in query:
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
                }
            ]

        assert "FROM public.meal_logs ml" in query
        assert args == (
            "user-1",
            "Europe/Madrid",
            date(2026, 3, 18),
            date(2026, 4, 16),
        )
        return [
            {
                "product_id": "food-7",
                "total_usage_occurrences": 9,
                "total_usage_days": 6,
                "total_grams": 1530.0,
                "total_calories": 1490.22,
                "window_usage_occurrences": 4,
                "window_usage_days": 3,
                "window_total_grams": 680.0,
                "window_total_calories": 662.32,
                "first_used_on": date(2026, 2, 10),
                "last_used_on": date(2026, 4, 15),
            }
        ]

    store._fetch = fake_fetch  # type: ignore[method-assign]
    store._resolve_user_id = (  # type: ignore[method-assign]
        lambda subject: asyncio.sleep(0, result="user-1")
    )
    store._get_schema_variant = (  # type: ignore[method-assign]
        lambda: asyncio.sleep(0, result="normalized")
    )

    products = asyncio.run(store.list_products("athlete-1", date(2026, 4, 16), 30))

    assert len(products) == 1
    assert products[0].id == "food-7"
    assert products[0].name == "Greek yogurt"
    assert products[0].default_serving_g == 170.0
    assert products[0].fat_g_per_100g == 5.0
    assert products[0].usage.window_usage_occurrences == 4
    assert products[0].usage.last_used_on == date(2026, 4, 15)


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

        if "FROM public.food_products" in query:
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
                }
            ]

        assert "FROM public.daily_meals dm" in query
        assert args == (
            "athlete-1",
            date(2026, 3, 18),
            date(2026, 4, 16),
        )
        return [
            {
                "product_id": "7",
                "total_usage_occurrences": 7,
                "total_usage_days": 5,
                "total_grams": 1190.0,
                "total_calories": 1159.06,
                "window_usage_occurrences": 3,
                "window_usage_days": 2,
                "window_total_grams": 510.0,
                "window_total_calories": 496.74,
                "first_used_on": date(2026, 1, 24),
                "last_used_on": date(2026, 4, 14),
            }
        ]

    store._fetch = fake_fetch  # type: ignore[method-assign]
    store._get_schema_variant = (  # type: ignore[method-assign]
        lambda: asyncio.sleep(0, result="legacy")
    )

    products = asyncio.run(store.list_products("athlete-1", date(2026, 4, 16), 30))

    assert len(products) == 1
    assert products[0].id == "7"
    assert products[0].name == "Legacy yogurt"
    assert products[0].usage.total_usage_occurrences == 7


def test_get_product_usage_trends_maps_daily_rows() -> None:
    """Ensure product-usage trend rows map into the typed response model.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: Raised when the trend query mapping changes.
    """

    store = PostgresPortalStore("postgresql://example")

    async def fake_fetch(query: str, *args: object) -> list[dict[str, object]]:
        """Return deterministic product-usage trend rows for the mapping test.

        Parameters:
            query: SQL query requested by the store.
            *args: Query arguments supplied by the caller.

        Returns:
            list[dict[str, object]]: Fake daily trend rows.

        Raises:
            AssertionError: Raised when the query or arguments differ.
        """

        assert "FROM public.meal_logs ml" in query
        assert args == (
            "user-1",
            "Europe/Madrid",
            "food-7",
            date(2026, 4, 1),
            date(2026, 4, 16),
        )
        return [
            {
                "day": date(2026, 4, 14),
                "usage_occurrences": 1,
                "total_grams": 170.0,
                "total_calories": 165.58,
            },
            {
                "day": date(2026, 4, 16),
                "usage_occurrences": 2,
                "total_grams": 255.0,
                "total_calories": 248.37,
            },
        ]

    async def fake_resolve_user_id(subject: str) -> str:
        """Return a deterministic user id for the trend mapping test.

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

    response = asyncio.run(
        store.get_product_usage_trends(
            "athlete-1",
            "food-7",
            date(2026, 4, 1),
            date(2026, 4, 16),
        )
    )

    assert response.product_id == "food-7"
    assert response.summary.logged_days == 2
    assert response.summary.total_usage_occurrences == 3
    assert response.days[0].date == date(2026, 4, 14)
