"""API tests for the APEX progress portal backend."""

from __future__ import annotations

from datetime import UTC, date, datetime

from fastapi.testclient import TestClient

from apex_portal_api.config import Settings
from apex_portal_api.main import create_app
from apex_portal_api.models import (
    Activity,
    BootstrapResponse,
    DailyMetricPoint,
    DailyMetricSeries,
    DailySnapshot,
    DailySummary,
    FoodProduct,
    FoodProductsResponse,
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
    TrainingPlansResponse,
    TrainingPlanSummary,
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
                            id="meal-item-1",
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

    async def list_products(self, subject: str) -> list[FoodProduct]:
        """Return a small reusable product catalog for the test subject."""

        return [
            FoodProduct(
                id="food-1",
                name="Rolled oats",
                default_serving_g=40,
                calories_per_100g=384,
                carbs_g_per_100g=66,
                protein_g_per_100g=13,
                fat_g_per_100g=7,
                usage_count=22,
            )
        ]

    async def list_training_plans(
        self,
        subject: str,
        date_from: date | None = None,
        date_to: date | None = None,
        status: str | None = None,
    ) -> list[TrainingPlanSummary]:
        """Return a small deterministic training plan list for tests."""

        plan = build_test_plan_summary()
        if status is not None and plan.status != status:
            return []
        if date_from is not None and plan.end_date < date_from:
            return []
        if date_to is not None and plan.start_date > date_to:
            return []
        return [plan]

    async def get_training_plan(
        self,
        subject: str,
        plan_id: int,
    ) -> TrainingPlanDetail | None:
        """Return one deterministic training plan for tests."""

        if plan_id != 1:
            return None

        return TrainingPlanDetail(
            **build_test_plan_summary().model_dump(),
            days=[build_test_plan_day()],
        )

    async def compare_training_plan(
        self,
        subject: str,
        plan_id: int,
    ) -> TrainingPlanComparisonResponse | None:
        """Return one deterministic plan comparison for tests."""

        if plan_id != 1:
            return None

        planned = build_test_plan_day()
        actual = DailySummary(
            target_date=planned.plan_date,
            target_food_calories=2800,
            target_exercise_calories=1200,
            target_protein_g=150,
            target_carbs_g=360,
            target_fat_g=75,
            actual_food_calories=2600,
            actual_exercise_calories=1100,
            actual_protein_g=145,
            actual_carbs_g=330,
            actual_fat_g=80,
            remaining_food_calories=200,
            remaining_protein_g=5,
            remaining_carbs_g=30,
            remaining_fat_g=-5,
            net_calories=1500,
            meals_count=1,
            meal_items_count=1,
            activities_count=1,
        )
        return TrainingPlanComparisonResponse(
            plan=build_test_plan_summary(),
            days_count=1,
            days=[
                TrainingPlanComparisonDay(
                    plan_date=planned.plan_date,
                    planned=planned,
                    actual=actual,
                    daily_metrics=[
                        TrainingPlanDailyMetric(
                            metric_date=planned.plan_date,
                            metric_type="sleep_hours",
                            value=7.5,
                        )
                    ],
                    deltas=TrainingPlanComparisonDeltas(
                        food_calories=-200,
                        exercise_calories=-100,
                        protein_g=-5,
                        carbs_g=-30,
                        fat_g=5,
                    ),
                    adherence=TrainingPlanComparisonAdherence(
                        food_calories_percent=92.9,
                        exercise_calories_percent=91.7,
                        protein_percent=96.7,
                        carbs_percent=91.7,
                        fat_percent=93.3,
                        macro_average_percent=93.9,
                    ),
                )
            ],
            totals=TrainingPlanComparisonTotals(
                planned_food_calories=2800,
                actual_food_calories=2600,
                planned_exercise_calories=1200,
                actual_exercise_calories=1100,
                planned_protein_g=150,
                actual_protein_g=145,
                planned_carbs_g=360,
                actual_carbs_g=330,
                planned_fat_g=75,
                actual_fat_g=80,
                food_calories_delta=-200,
                exercise_calories_delta=-100,
                protein_g_delta=-5,
                carbs_g_delta=-30,
                fat_g_delta=5,
                food_calories_adherence_percent=92.9,
                exercise_calories_adherence_percent=91.7,
                days_count=1,
            ),
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
                    target_protein_g=150,
                    target_carbs_g=290,
                    target_fat_g=68,
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
                    target_protein_g=150,
                    target_carbs_g=290,
                    target_fat_g=68,
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
            daily_metrics=[
                DailyMetricSeries(
                    metric_type="sleep_hours",
                    points=[
                        DailyMetricPoint(date=date_to, value=7.5),
                    ],
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


def build_test_plan_summary() -> TrainingPlanSummary:
    """Build a deterministic food and training plan header for tests.

    Parameters:
        None.

    Returns:
        TrainingPlanSummary: Fixed plan summary payload.

    Raises:
        This helper does not raise errors directly.
    """

    timestamp = datetime(2026, 6, 28, 18, 0, tzinfo=UTC)
    return TrainingPlanSummary(
        id=1,
        title="Next week endurance block",
        start_date=date(2026, 7, 6),
        end_date=date(2026, 7, 12),
        status="published",
        goal_markdown="Lose weight while keeping long-run quality.",
        rationale_markdown="Estimated from similar long runs.",
        notes_markdown="Use conservative load estimates.",
        generation_context={"source": "pytest"},
        days_count=1,
        created_at=timestamp,
        updated_at=timestamp,
    )


def build_test_plan_day() -> TrainingPlanDay:
    """Build a deterministic training-plan day for tests.

    Parameters:
        None.

    Returns:
        TrainingPlanDay: Fixed planned day payload.

    Raises:
        This helper does not raise errors directly.
    """

    timestamp = datetime(2026, 6, 28, 18, 0, tzinfo=UTC)
    return TrainingPlanDay(
        id=10,
        plan_id=1,
        plan_date=date(2026, 7, 6),
        day_type="training",
        title="Long aerobic run",
        training_summary="2 hour easy run with steady fueling.",
        primary_sport_type="run",
        planned_duration_seconds=7200,
        planned_distance_meters=20000,
        planned_elevation_gain_meters=250,
        planned_training_load=120,
        target_food_calories=2800,
        target_exercise_calories=1200,
        target_protein_g=150,
        target_carbs_g=360,
        target_fat_g=75,
        training_sessions=[
            {"sport_type": "run", "duration_seconds": 7200, "intensity": "easy"}
        ],
        fueling_plan={"during": "60 g carbs/hour"},
        menu_plan={"breakfast": "oats and banana"},
        notes_markdown="Use conservative load estimate.",
        created_at=timestamp,
        updated_at=timestamp,
    )


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
    assert payload.history.days[0].target_protein_g == 150
    assert payload.trends.days[0].target_carbs_g == 290


def test_protected_routes_require_bearer_token() -> None:
    """Ensure protected mode rejects requests without the configured token."""

    client = build_test_client(portal_access_token="secret-token")

    unauthorized = client.get("/portal/bootstrap?target_date=2026-04-16")
    authorized = client.get(
        "/portal/bootstrap?target_date=2026-04-16",
        headers={"Authorization": "Bearer secret-token"},
    )
    products_unauthorized = client.get("/portal/products")
    products_authorized = client.get(
        "/portal/products",
        headers={"Authorization": "Bearer secret-token"},
    )
    plans_unauthorized = client.get("/portal/plans")
    plans_authorized = client.get(
        "/portal/plans",
        headers={"Authorization": "Bearer secret-token"},
    )

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert products_unauthorized.status_code == 401
    assert products_authorized.status_code == 200
    assert plans_unauthorized.status_code == 401
    assert plans_authorized.status_code == 200


def test_history_route_uses_requested_window() -> None:
    """Ensure the history route accepts the days window query parameter."""

    client = build_test_client()

    response = client.get("/portal/history?date_to=2026-04-16&days=30")

    assert response.status_code == 200
    payload = HistoryResponse.model_validate(response.json())
    assert payload.date_to == date(2026, 4, 16)
    assert payload.days[0].total_distance_meters == 13020


def test_trends_route_accepts_one_week_window() -> None:
    """Ensure the trends route accepts the one-week window query parameter."""

    client = build_test_client()

    response = client.get("/portal/trends?date_to=2026-04-16&days=7")

    assert response.status_code == 200
    payload = TrendsResponse.model_validate(response.json())
    assert payload.date_to == date(2026, 4, 16)
    assert payload.summary.logged_days == 1


def test_bootstrap_uses_store_default_date_when_target_date_is_omitted() -> None:
    """Ensure bootstrap falls back to the store-provided default day."""

    client = build_test_client()

    response = client.get("/portal/bootstrap")

    assert response.status_code == 200
    payload = BootstrapResponse.model_validate(response.json())
    assert payload.snapshot.date == date(2026, 4, 16)
    assert payload.trends.daily_metrics[0].metric_type == "sleep_hours"


def test_products_route_returns_expected_shape() -> None:
    """Ensure the products route returns the configured food catalog rows."""

    client = build_test_client()

    response = client.get("/portal/products")

    assert response.status_code == 200
    payload = FoodProductsResponse.model_validate(response.json())
    assert payload.items[0].name == "Rolled oats"
    assert payload.items[0].protein_g_per_100g == 13
    assert payload.items[0].usage_count == 22


def test_plans_route_returns_expected_shape() -> None:
    """Ensure the training plans route returns plan header rows."""

    client = build_test_client()

    response = client.get("/portal/plans?status=published")

    assert response.status_code == 200
    payload = TrainingPlansResponse.model_validate(response.json())
    assert payload.items[0].title == "Next week endurance block"
    assert payload.items[0].days_count == 1
    assert payload.items[0].generation_context["source"] == "pytest"


def test_plan_detail_route_returns_days() -> None:
    """Ensure the plan detail route returns ordered planned days."""

    client = build_test_client()

    response = client.get("/portal/plans/1")

    assert response.status_code == 200
    payload = TrainingPlanDetail.model_validate(response.json())
    assert payload.days[0].title == "Long aerobic run"
    assert payload.days[0].training_sessions[0]["sport_type"] == "run"
    assert payload.days[0].target_carbs_g == 360


def test_plan_comparison_route_returns_deltas_and_metrics() -> None:
    """Ensure the comparison route returns planned-vs-actual context."""

    client = build_test_client()

    response = client.get("/portal/plans/1/comparison")

    assert response.status_code == 200
    payload = TrainingPlanComparisonResponse.model_validate(response.json())
    assert payload.days_count == 1
    assert payload.days[0].deltas.food_calories == -200
    assert payload.days[0].deltas.exercise_calories == -100
    assert payload.days[0].daily_metrics[0].metric_type == "sleep_hours"
    assert payload.totals.food_calories_adherence_percent == 92.9


def test_missing_plan_routes_return_404() -> None:
    """Ensure missing plan detail and comparison routes return 404."""

    client = build_test_client()

    detail = client.get("/portal/plans/999")
    comparison = client.get("/portal/plans/999/comparison")

    assert detail.status_code == 404
    assert comparison.status_code == 404
