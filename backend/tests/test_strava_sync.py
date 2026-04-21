"""Tests for the lightweight Strava sync flow."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from apex_portal_api.config import Settings
from apex_portal_api.strava_sync import (
    NormalizedStravaActivity,
    StravaSyncStore,
    StravaTokenBundle,
    normalize_strava_activity,
    run_strava_sync,
)


def test_normalize_strava_activity_maps_core_fields() -> None:
    """Ensure the Strava normalizer maps the expected activity columns.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: Raised when the normalized shape changes unexpectedly.
    """

    detail = {
        "id": 987654321,
        "name": "Lunch Ride",
        "start_date": "2026-04-20T10:00:00Z",
        "sport_type": "Ride",
        "moving_time": 3620,
        "distance": 40250.4,
        "total_elevation_gain": 520.7,
        "average_watts": 201.3,
        "weighted_average_watts": 219.8,
        "average_heartrate": 145.3,
        "max_heartrate": 171.1,
        "kilojoules": 812.4,
        "relative_effort": 67,
        "timezone": "(GMT+01:00) Europe/Madrid",
        "manual": False,
        "trainer": False,
        "commute": True,
        "private": False,
    }

    activity = normalize_strava_activity(user_id="user-1", detail=detail)

    assert activity.id == "strava:user-1:987654321"
    assert activity.strava_id == "987654321"
    assert activity.sport == "cycling"
    assert activity.name == "Lunch Ride"
    assert activity.start_time == datetime(2026, 4, 20, 10, 0, tzinfo=UTC)
    assert activity.duration_seconds == 3620
    assert activity.distance_m == 40250.4
    assert activity.elevation_m == 520.7
    assert activity.avg_power_w == 201.3
    assert activity.normalized_power_w == 219.8
    assert activity.avg_hr == 145
    assert activity.max_hr == 171
    assert activity.tss == 67.0
    assert activity.calories == 812.4
    assert activity.metadata_json["source"] == "strava"
    assert activity.metadata_json["commute"] is True


def test_upsert_activities_uses_conflict_key_and_dedupes_batch() -> None:
    """Ensure repeated activity ids are collapsed before the SQL upsert.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: Raised when the upsert strategy changes unexpectedly.
    """

    store = StravaSyncStore("postgresql://example", portal_user_id="user-1")
    captured: dict[str, object] = {}

    async def fake_executemany(
        query: str,
        args: list[tuple[object, ...]],
    ) -> None:
        """Capture the SQL and arguments passed into the batch write.

        Parameters:
            query: SQL statement used by the store.
            args: Bound argument rows for the SQL statement.

        Returns:
            None.

        Raises:
            This helper does not raise errors directly.
        """

        captured["query"] = query
        captured["args"] = args

    store._executemany = fake_executemany  # type: ignore[method-assign]
    activity = NormalizedStravaActivity(
        id="strava:user-1:101",
        strava_id="101",
        sport="running",
        name="Track Session",
        start_time=datetime(2026, 4, 20, 8, 0, tzinfo=UTC),
        duration_seconds=1800,
        distance_m=5000.0,
        elevation_m=42.0,
        tss=55.0,
        calories=480.0,
        metadata_json={"source": "strava"},
    )

    upserted_activity_ids = asyncio.run(
        store.upsert_activities("user-1", [activity, activity])
    )

    assert "ON CONFLICT (user_id, strava_id)" in str(captured["query"])
    assert len(captured["args"]) == 1
    assert upserted_activity_ids == [101]


def test_run_strava_sync_bootstraps_tokens_and_stays_idempotent() -> None:
    """Ensure repeated sync runs reuse the rotated refresh token and upsert safely.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        AssertionError: Raised when bootstrap or idempotent behavior changes.
    """

    class FakeStore:
        """Provide a tiny in-memory store for the sync orchestration test."""

        def __init__(self) -> None:
            self.tokens: StravaTokenBundle | None = None
            self.activities: dict[str, NormalizedStravaActivity] = {}

        async def ensure_schema(self) -> None:
            """Satisfy the sync contract without touching a database."""

        async def resolve_user_id(self) -> str:
            """Return the deterministic test user id."""

            return "user-1"

        async def get_tokens(self, user_id: str) -> StravaTokenBundle | None:
            """Return the currently stored token bundle for the test user."""

            assert user_id == "user-1"
            return self.tokens

        async def save_tokens(self, user_id: str, tokens: StravaTokenBundle) -> None:
            """Persist the rotated token bundle in memory."""

            assert user_id == "user-1"
            self.tokens = tokens

        async def upsert_activities(
            self,
            user_id: str,
            activities: list[NormalizedStravaActivity],
        ) -> list[int]:
            """Store activities keyed by Strava id to emulate idempotent upserts."""

            assert user_id == "user-1"
            for activity in activities:
                self.activities[activity.strava_id] = activity
            return [int(activity.strava_id) for activity in activities]

        async def close(self) -> None:
            """Satisfy the sync contract without any cleanup work."""

            return None

    class FakeClient:
        """Return deterministic Strava responses for the orchestration test."""

        def __init__(self) -> None:
            self.refresh_calls: list[str] = []

        async def refresh_access_token(self, refresh_token: str) -> StravaTokenBundle:
            """Rotate the refresh token so the second run must use the stored value."""

            self.refresh_calls.append(refresh_token)
            return StravaTokenBundle(
                access_token=f"access-{len(self.refresh_calls)}",
                refresh_token=f"rotated-{len(self.refresh_calls)}",
                expires_at=datetime(2026, 4, 21, 12, 0, tzinfo=UTC),
            )

        async def list_activity_ids(
            self,
            access_token: str,
            *,
            after: datetime,
            per_page: int = 100,
        ) -> list[int]:
            """Return two recent activity ids for every run."""

            assert access_token.startswith("access-")
            assert after.tzinfo is UTC
            assert per_page == 100
            return [101, 102]

        async def get_activity(
            self, access_token: str, activity_id: int
        ) -> dict[str, object]:
            """Return one deterministic activity payload for each requested id."""

            assert access_token.startswith("access-")
            return {
                "id": activity_id,
                "name": f"Activity {activity_id}",
                "start_date": "2026-04-21T09:00:00Z",
                "sport_type": "Run" if activity_id == 101 else "Ride",
                "moving_time": 1800 + activity_id,
                "distance": 5000.0 + activity_id,
                "total_elevation_gain": 40.0 + activity_id,
                "average_heartrate": 150.0,
                "max_heartrate": 170.0,
                "calories": 500.0,
                "relative_effort": 45.0,
                "timezone": "(GMT+01:00) Europe/Madrid",
            }

    settings = Settings(
        DATABASE_URL="postgresql://example",
        APEX_PORTAL_SUBJECT="athlete-1",
        APEX_PORTAL_USER_ID="user-1",
        STRAVA_CLIENT_ID="12345",
        STRAVA_CLIENT_SECRET="secret-value",
        STRAVA_REFRESH_TOKEN="bootstrap-token",
        STRAVA_SYNC_LOOKBACK_HOURS=72,
    )
    store = FakeStore()
    client = FakeClient()
    fixed_now = datetime(2026, 4, 21, 10, 0, tzinfo=UTC)

    first_result = asyncio.run(
        run_strava_sync(settings, store=store, client=client, now=fixed_now)
    )
    second_result = asyncio.run(
        run_strava_sync(settings, store=store, client=client, now=fixed_now)
    )

    assert first_result.token_source == "environment"
    assert second_result.token_source == "database"
    assert client.refresh_calls == ["bootstrap-token", "rotated-1"]
    assert sorted(store.activities) == ["101", "102"]
    assert first_result.upserted_activity_ids == [101, 102]
    assert second_result.upserted_activity_ids == [101, 102]
