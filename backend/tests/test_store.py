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

    store._fetch = fake_fetch  # type: ignore[method-assign]
    store._get_schema_variant = (  # type: ignore[method-assign]
        lambda: asyncio.sleep(0, result="normalized")
    )

    products = asyncio.run(store.list_products("athlete-1"))

    assert len(products) == 1
    assert products[0].id == "food-7"
    assert products[0].name == "Greek yogurt"
    assert products[0].default_serving_g == 170.0
    assert products[0].fat_g_per_100g == 5.0


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

    store._fetch = fake_fetch  # type: ignore[method-assign]
    store._get_schema_variant = (  # type: ignore[method-assign]
        lambda: asyncio.sleep(0, result="legacy")
    )

    products = asyncio.run(store.list_products("athlete-1"))

    assert len(products) == 1
    assert products[0].id == "7"
    assert products[0].name == "Legacy yogurt"
