"""API tests for the APEX progress portal backend."""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from apex_portal_api.config import Settings
from apex_portal_api.main import create_app
from apex_portal_api.models import (
    Activity,
    BootstrapResponse,
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
from apex_portal_api.store import PortalStore


class FakePortalStore(PortalStore):
    """Provide deterministic read models for API tests.

    Parameters:
        None.

    Returns:
        FakePortalStore: In-memory store used by the tests.

    Raises:
        This class does not raise errors directly.
    """

    async def get_default_date(self, subject: str, fallback_date: date) -> date:
        """Return a fixed default day for routes that omit a date."""

        return date(2026, 4, 16)

    async def get_profile(self, subject: str) -> PortalProfile:
        """Return a fixed profile payload for the test subject."""

        return PortalProfile(
            athlete_name="Sergio",
            subject=subject,
            weight_kg=68,
            height_cm=170,
            ftp_watts=260,
            profile_markdown="# Sergio's Endurance Profile",
            diet_goals_markdown="Lose 0.5 kg per week",
            training_goals_markdown="Improve cycling and running",
        )

    async def get_daily_snapshot(
        self, subject: str, target_date: date
    ) -> DailySnapshot:
        """Return a fixed daily snapshot for API assertions."""

        return DailySnapshot(
            date=target_date,
            summary=DailySummary(
                target_date=target_date,
                target_food_calories=2490,
                actual_food_calories=725,
                actual_exercise_calories=976,
                actual_protein_g=42,
                actual_carbs_g=115,
                actual_fat_g=12,
                remaining_food_calories=1765,
                remaining_protein_g=108,
                remaining_carbs_g=175,
                remaining_fat_g=56,
                net_calories=-251,
                meals_count=2,
                meal_items_count=10,
                activities_count=1,
            ),
            meals=[
                Meal(
                    id="meal-1",
                    meal_label="Pre-training breakfast",
                    items=[
                        MealItem(
                            id="ingredient-1",
                            product_id="food-1",
                            ingredient_name="Oats (rolled)",
                            grams=30,
                            calories=115.2,
                            carbs_g=19.8,
                            protein_g=3.9,
                            fat_g=2.1,
                        )
                    ],
                    total_calories=115.2,
                    total_carbs_g=19.8,
                    total_protein_g=3.9,
                    total_fat_g=2.1,
                )
            ],
            activities=[
                Activity(
                    id="activity-1",
                    title="Around gran via",
                    activity_date=target_date,
                    sport_type="Run",
                    distance_meters=13020,
                    moving_time_seconds=3933,
                    total_elevation_gain_meters=127,
                    average_heartrate=151,
                    max_heartrate=165,
                    calories=976,
                    suffer_score=212,
                    notes_markdown="Tempo run",
                    external_source="strava",
                )
            ],
        )

    async def get_history(
        self,
        subject: str,
        date_from: date,
        date_to: date,
    ) -> HistoryResponse:
        """Return a small deterministic history window for tests."""

        return HistoryResponse(
            date_from=date_from,
            date_to=date_to,
            days=[
                HistoryDay(
                    date=date_to,
                    target_food_calories=2490,
                    actual_food_calories=725,
                    actual_exercise_calories=976,
                    net_calories=-251,
                    actual_protein_g=42,
                    actual_carbs_g=115,
                    actual_fat_g=12,
                    meals_count=2,
                    meal_items_count=10,
                    activities_count=1,
                    total_distance_meters=13020,
                    total_moving_time_seconds=3933,
                    total_elevation_gain_meters=127,
                    total_suffer_score=212,
                )
            ],
        )

    async def get_trends(
        self,
        subject: str,
        date_from: date,
        date_to: date,
    ) -> TrendsResponse:
        """Return a deterministic trend result for tests."""

        return TrendsResponse(
            date_from=date_from,
            date_to=date_to,
            days=[
                HistoryDay(
                    date=date_to,
                    target_food_calories=2490,
                    actual_food_calories=725,
                    actual_exercise_calories=976,
                    net_calories=-251,
                    actual_protein_g=42,
                    actual_carbs_g=115,
                    actual_fat_g=12,
                    meals_count=2,
                    meal_items_count=10,
                    activities_count=1,
                    total_distance_meters=13020,
                    total_moving_time_seconds=3933,
                    total_elevation_gain_meters=127,
                    total_suffer_score=212,
                )
            ],
            summary=TrendSummary(
                logged_days=1,
                average_food_calories=725,
                average_exercise_calories=976,
                total_distance_meters=13020,
                total_activities=1,
            ),
        )

    async def close(self) -> None:
        """Satisfy the store interface without any cleanup work."""

        return None


def build_test_client(portal_access_token: str | None = None) -> TestClient:
    """Create a configured FastAPI test client.

    Parameters:
        portal_access_token: Optional bearer token required by the app.

    Returns:
        TestClient: Ready-to-use API client for the tests.

    Raises:
        This helper does not raise errors directly.
    """

    settings = Settings(
        DATABASE_URL="postgresql://example",
        APEX_PORTAL_SUBJECT="athlete-1",
        APEX_PORTAL_ACCESS_TOKEN=portal_access_token,
        APEX_PORTAL_TIMEZONE="UTC",
        APEX_PORTAL_ATHLETE_NAME="Sergio",
    )
    app = create_app(settings=settings, store=FakePortalStore())
    return TestClient(app)


def test_bootstrap_returns_expected_shape() -> None:
    """Ensure the bootstrap route returns the combined initial payload."""

    client = build_test_client()

    response = client.get("/portal/bootstrap?target_date=2026-04-16")

    assert response.status_code == 200
    payload = BootstrapResponse.model_validate(response.json())
    assert payload.profile.athlete_name == "Sergio"
    assert payload.snapshot.summary.meals_count == 2
    assert payload.history.days[0].activities_count == 1


def test_protected_routes_require_bearer_token() -> None:
    """Ensure protected mode rejects requests without the configured token."""

    client = build_test_client(portal_access_token="secret-token")

    unauthorized = client.get("/portal/bootstrap?target_date=2026-04-16")
    authorized = client.get(
        "/portal/bootstrap?target_date=2026-04-16",
        headers={"Authorization": "Bearer secret-token"},
    )

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200


def test_history_route_uses_requested_window() -> None:
    """Ensure the history route accepts the days window query parameter."""

    client = build_test_client()

    response = client.get("/portal/history?date_to=2026-04-16&days=30")

    assert response.status_code == 200
    payload = HistoryResponse.model_validate(response.json())
    assert payload.date_to == date(2026, 4, 16)
    assert payload.days[0].total_distance_meters == 13020


def test_bootstrap_uses_store_default_date_when_target_date_is_omitted() -> None:
    """Ensure bootstrap falls back to the store-provided default day."""

    client = build_test_client()

    response = client.get("/portal/bootstrap")

    assert response.status_code == 200
    payload = BootstrapResponse.model_validate(response.json())
    assert payload.snapshot.date == date(2026, 4, 16)
