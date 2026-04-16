"""Store-level tests for the APEX progress portal backend."""

from __future__ import annotations

import asyncio

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

        assert "FROM food_products" in query
        assert args == ("athlete-1",)
        return [
            {
                "id": 7,
                "name": "Greek yogurt",
                "default_serving_g": 170.0,
                "calories_per_100g": 97.4,
                "carbs_g_per_100g": 3.6,
                "protein_g_per_100g": 9.8,
                "fat_g_per_100g": 5.0,
            }
        ]

    store._fetch = fake_fetch  # type: ignore[method-assign]

    products = asyncio.run(store.list_products("athlete-1"))

    assert len(products) == 1
    assert products[0].name == "Greek yogurt"
    assert products[0].default_serving_g == 170.0
    assert products[0].fat_g_per_100g == 5.0
