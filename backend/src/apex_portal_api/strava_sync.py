"""Simple Strava pull job for syncing recent activities into APEX."""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg
import httpx

from apex_portal_api.config import Settings

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS strava_oauth_tokens (
    user_id TEXT PRIMARY KEY,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.activities (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    strava_id TEXT,
    sport TEXT NOT NULL,
    name TEXT NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    duration_seconds INTEGER NOT NULL DEFAULT 0,
    distance_m DOUBLE PRECISION NOT NULL DEFAULT 0,
    elevation_m DOUBLE PRECISION NOT NULL DEFAULT 0,
    avg_power_w DOUBLE PRECISION,
    normalized_power_w DOUBLE PRECISION,
    avg_hr INTEGER,
    max_hr INTEGER,
    tss DOUBLE PRECISION NOT NULL DEFAULT 0,
    intensity_factor DOUBLE PRECISION,
    calories DOUBLE PRECISION NOT NULL DEFAULT 0,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.activities
    ADD COLUMN IF NOT EXISTS user_id TEXT,
    ADD COLUMN IF NOT EXISTS strava_id TEXT,
    ADD COLUMN IF NOT EXISTS sport TEXT,
    ADD COLUMN IF NOT EXISTS name TEXT,
    ADD COLUMN IF NOT EXISTS start_time TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS duration_seconds INTEGER,
    ADD COLUMN IF NOT EXISTS distance_m DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS elevation_m DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS avg_power_w DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS normalized_power_w DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS avg_hr INTEGER,
    ADD COLUMN IF NOT EXISTS max_hr INTEGER,
    ADD COLUMN IF NOT EXISTS tss DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS intensity_factor DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS calories DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

CREATE UNIQUE INDEX IF NOT EXISTS uq_activities_user_strava_id
    ON public.activities (user_id, strava_id);

CREATE INDEX IF NOT EXISTS idx_activities_user_start_time
    ON public.activities (user_id, start_time DESC);
"""

UPSERT_ACTIVITY_SQL = """
INSERT INTO public.activities (
    id,
    user_id,
    strava_id,
    sport,
    name,
    start_time,
    duration_seconds,
    distance_m,
    elevation_m,
    avg_power_w,
    normalized_power_w,
    avg_hr,
    max_hr,
    tss,
    intensity_factor,
    calories,
    metadata_json,
    created_at
) VALUES (
    $1,
    $2,
    $3,
    $4,
    $5,
    $6,
    $7,
    $8,
    $9,
    $10,
    $11,
    $12,
    $13,
    $14,
    $15,
    $16,
    $17::jsonb,
    NOW()
)
ON CONFLICT (user_id, strava_id) DO UPDATE SET
    sport = EXCLUDED.sport,
    name = EXCLUDED.name,
    start_time = EXCLUDED.start_time,
    duration_seconds = EXCLUDED.duration_seconds,
    distance_m = EXCLUDED.distance_m,
    elevation_m = EXCLUDED.elevation_m,
    avg_power_w = EXCLUDED.avg_power_w,
    normalized_power_w = EXCLUDED.normalized_power_w,
    avg_hr = EXCLUDED.avg_hr,
    max_hr = EXCLUDED.max_hr,
    tss = EXCLUDED.tss,
    intensity_factor = EXCLUDED.intensity_factor,
    calories = EXCLUDED.calories,
    metadata_json = EXCLUDED.metadata_json
"""


class StravaSyncError(RuntimeError):
    """Represent a recoverable Strava sync failure."""


@dataclass(slots=True)
class StravaTokenBundle:
    """Store the short-lived Strava access token and rotated refresh token.

    Parameters:
        access_token: Short-lived bearer token used for Strava API calls.
        refresh_token: Latest refresh token returned by Strava.
        expires_at: UTC timestamp describing when the access token expires.

    Returns:
        StravaTokenBundle: Parsed token payload ready for persistence.
    """

    access_token: str
    refresh_token: str
    expires_at: datetime


@dataclass(slots=True)
class NormalizedStravaActivity:
    """Represent one Strava activity mapped into `public.activities`.

    Parameters:
        id: Stable primary key used by `public.activities`.
        strava_id: Stable Strava activity identifier.
        sport: Normalized APEX sport taxonomy value.
        name: Human-readable activity title.
        start_time: UTC timestamp of the activity start.
        duration_seconds: Moving or elapsed duration in seconds.
        distance_m: Distance in meters.
        elevation_m: Elevation gain in meters.
        avg_power_w: Optional average power in watts.
        normalized_power_w: Optional weighted average power in watts.
        avg_hr: Optional average heart rate.
        max_hr: Optional max heart rate.
        tss: Best-effort training-load number from Strava.
        intensity_factor: Optional intensity factor when already available.
        calories: Best-effort calories or kilojoules value from Strava.
        metadata_json: Extra structured metadata stored for provenance.

    Returns:
        NormalizedStravaActivity: Row payload ready for Postgres upsert.
    """

    id: str
    strava_id: str
    sport: str
    name: str
    start_time: datetime
    duration_seconds: int
    distance_m: float
    elevation_m: float
    avg_power_w: float | None = None
    normalized_power_w: float | None = None
    avg_hr: int | None = None
    max_hr: int | None = None
    tss: float = 0.0
    intensity_factor: float | None = None
    calories: float = 0.0
    metadata_json: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class StravaSyncResult:
    """Describe one completed Strava sync run.

    Parameters:
        user_id: APEX app-level user id that received the upserts.
        token_source: Whether the refresh token came from env or Postgres.
        lookback_hours: Configured trailing Strava window for the sync run.
        fetched_activity_ids: Activity identifiers seen in the recent window.
        upserted_activity_ids: Activity identifiers written into Postgres.
        started_at: UTC timestamp when the run started.
        completed_at: UTC timestamp when the run completed.

    Returns:
        StravaSyncResult: Serializable summary for CLI and cron responses.
    """

    user_id: str
    token_source: str
    lookback_hours: int
    fetched_activity_ids: list[int]
    upserted_activity_ids: list[int]
    started_at: datetime
    completed_at: datetime

    def to_response(self) -> dict[str, Any]:
        """Serialize the sync result into JSON-friendly values.

        Parameters:
            None.

        Returns:
            dict[str, Any]: Summary payload suitable for API responses.

        Raises:
            This helper does not raise errors directly.
        """

        return {
            "status": "ok",
            "user_id": self.user_id,
            "token_source": self.token_source,
            "lookback_hours": self.lookback_hours,
            "fetched_activity_ids": self.fetched_activity_ids,
            "upserted_activity_ids": self.upserted_activity_ids,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
        }


class StravaClient:
    """Call only the Strava endpoints needed for the lightweight sync job.

    Parameters:
        settings: Runtime settings containing client credentials and timeout.

    Returns:
        StravaClient: Small HTTP wrapper for refresh and activity requests.
    """

    token_url = "https://www.strava.com/oauth/token"
    api_base_url = "https://www.strava.com/api/v3"

    def __init__(self, settings: Settings) -> None:
        """Store the shared runtime settings for later requests.

        Parameters:
            settings: Runtime settings used by the Strava requests.

        Returns:
            None.

        Raises:
            This initializer does not raise errors directly.
        """

        self._settings = settings

    async def refresh_access_token(self, refresh_token: str) -> StravaTokenBundle:
        """Exchange the latest refresh token for a short-lived access token.

        Parameters:
            refresh_token: Latest known Strava refresh token for the athlete.

        Returns:
            StravaTokenBundle: Rotated token bundle returned by Strava.

        Raises:
            StravaSyncError: Raised when the response is incomplete or invalid.
        """

        response = await self._request(
            "POST",
            self.token_url,
            data={
                "client_id": self._settings.strava_client_id,
                "client_secret": self._settings.strava_client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        )

        try:
            return StravaTokenBundle(
                access_token=str(response["access_token"]),
                refresh_token=str(response["refresh_token"]),
                expires_at=datetime.fromtimestamp(int(response["expires_at"]), tz=UTC),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise StravaSyncError(
                "Strava token refresh returned an unexpected payload."
            ) from error

    async def list_activity_ids(
        self,
        access_token: str,
        *,
        after: datetime,
        per_page: int = 100,
    ) -> list[int]:
        """Return recent Strava activity identifiers within the lookback window.

        Parameters:
            access_token: Active Strava bearer token.
            after: Lower UTC time bound sent to Strava.
            per_page: Number of activity summaries requested per page.

        Returns:
            list[int]: Recent activity identifiers ordered by Strava recency.

        Raises:
            StravaSyncError: Raised when Strava responds with invalid data.
        """

        page = 1
        activity_ids: list[int] = []

        while True:
            response = await self._request(
                "GET",
                f"{self.api_base_url}/athlete/activities",
                access_token=access_token,
                params={
                    "after": int(after.timestamp()),
                    "page": page,
                    "per_page": per_page,
                },
            )
            if not isinstance(response, list):
                raise StravaSyncError(
                    "Strava activity list returned an unexpected payload."
                )
            if not response:
                break

            for item in response:
                activity_id = item.get("id")
                if activity_id is not None:
                    activity_ids.append(int(activity_id))

            if len(response) < per_page:
                break
            page += 1

        return _dedupe_activity_ids(activity_ids)

    async def get_activity(self, access_token: str, activity_id: int) -> dict[str, Any]:
        """Fetch the detailed Strava payload for one activity.

        Parameters:
            access_token: Active Strava bearer token.
            activity_id: Stable Strava activity identifier.

        Returns:
            dict[str, Any]: Raw activity payload from Strava.

        Raises:
            StravaSyncError: Raised when Strava returns a non-object payload.
        """

        response = await self._request(
            "GET",
            f"{self.api_base_url}/activities/{activity_id}",
            access_token=access_token,
            params={"include_all_efforts": "false"},
        )
        if not isinstance(response, dict):
            raise StravaSyncError(
                f"Strava activity {activity_id} returned an unexpected payload."
            )
        return response

    async def _request(
        self,
        method: str,
        url: str,
        *,
        access_token: str | None = None,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> Any:
        """Send one HTTP request to Strava and return the parsed JSON body.

        Parameters:
            method: HTTP method used for the request.
            url: Fully qualified Strava URL.
            access_token: Optional bearer token for authenticated endpoints.
            params: Optional query string values.
            data: Optional form body values.

        Returns:
            Any: Parsed JSON body returned by Strava.

        Raises:
            StravaSyncError: Raised when the request fails or Strava returns
                an error response.
        """

        headers: dict[str, str] = {}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        try:
            async with httpx.AsyncClient(
                timeout=self._settings.strava_request_timeout_seconds
            ) as client:
                response = await client.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    data=data,
                )
        except httpx.HTTPError as error:
            raise StravaSyncError(f"Strava request failed: {error}") from error

        if response.status_code >= 400:
            raise StravaSyncError(
                f"Strava API request failed with status {response.status_code}: "
                f"{response.text}"
            )

        return response.json()


class StravaSyncStore:
    """Read and write the tiny amount of Postgres state needed for the sync.

    Parameters:
        database_url: Asyncpg-compatible Postgres connection string.
        portal_user_id: Optional explicit athlete user id for the APEX tables.

    Returns:
        StravaSyncStore: Postgres-backed store for tokens and activities.
    """

    def __init__(self, database_url: str, portal_user_id: str | None = None) -> None:
        """Store connection details for lazy pool creation.

        Parameters:
            database_url: Asyncpg-compatible Postgres connection string.
            portal_user_id: Optional explicit APEX user id for the sync target.

        Returns:
            None.

        Raises:
            This initializer does not raise errors directly.
        """

        self._database_url = database_url
        self._portal_user_id = portal_user_id
        self._resolved_user_id = portal_user_id
        self._pool: asyncpg.Pool | None = None
        self._pool_lock = asyncio.Lock()
        self._user_id_lock = asyncio.Lock()

    async def close(self) -> None:
        """Close the shared asyncpg pool when the sync finishes.

        Parameters:
            None.

        Returns:
            None.

        Raises:
            Exception: Propagated if the asyncpg pool fails to close.
        """

        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def ensure_schema(self) -> None:
        """Create the minimal Strava token table and activity index when missing.

        Parameters:
            None.

        Returns:
            None.

        Raises:
            Exception: Propagated when Postgres rejects the schema SQL.
        """

        await self._execute(SCHEMA_SQL)

    async def resolve_user_id(self) -> str:
        """Return the APEX app-level user id used by `public.activities`.

        Parameters:
            None.

        Returns:
            str: Resolved app-level user id for the single-athlete sync target.

        Raises:
            StravaSyncError: Raised when the database cannot resolve a unique
                athlete automatically.
        """

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
                """
            )

            if len(rows) == 1:
                self._resolved_user_id = str(rows[0]["user_id"])
                return self._resolved_user_id

            if not rows:
                raise StravaSyncError(
                    "Unable to resolve an APEX user id from Postgres. Set "
                    "APEX_PORTAL_USER_ID in backend/.env."
                )

            raise StravaSyncError(
                "Multiple APEX user ids are present in Postgres. Set "
                "APEX_PORTAL_USER_ID in backend/.env."
            )

    async def get_tokens(self, user_id: str) -> StravaTokenBundle | None:
        """Return the latest stored Strava tokens for the target athlete.

        Parameters:
            user_id: APEX app-level user id for the athlete.

        Returns:
            StravaTokenBundle | None: Stored tokens or `None` before bootstrap.

        Raises:
            Exception: Propagated when Postgres queries fail.
        """

        row = await self._fetchrow(
            """
            SELECT access_token, refresh_token, expires_at
            FROM strava_oauth_tokens
            WHERE user_id = $1
            """,
            user_id,
        )
        if row is None:
            return None

        return StravaTokenBundle(
            access_token=str(row["access_token"]),
            refresh_token=str(row["refresh_token"]),
            expires_at=row["expires_at"].astimezone(UTC),
        )

    async def save_tokens(self, user_id: str, tokens: StravaTokenBundle) -> None:
        """Persist the latest rotated Strava tokens for future sync runs.

        Parameters:
            user_id: APEX app-level user id for the athlete.
            tokens: Latest access and refresh token payload from Strava.

        Returns:
            None.

        Raises:
            Exception: Propagated when Postgres writes fail.
        """

        await self._execute(
            """
            INSERT INTO strava_oauth_tokens (
                user_id,
                access_token,
                refresh_token,
                expires_at,
                created_at,
                updated_at
            ) VALUES (
                $1,
                $2,
                $3,
                $4,
                NOW(),
                NOW()
            )
            ON CONFLICT (user_id) DO UPDATE SET
                access_token = EXCLUDED.access_token,
                refresh_token = EXCLUDED.refresh_token,
                expires_at = EXCLUDED.expires_at,
                updated_at = NOW()
            """,
            user_id,
            tokens.access_token,
            tokens.refresh_token,
            tokens.expires_at,
        )

    async def upsert_activities(
        self,
        user_id: str,
        activities: list[NormalizedStravaActivity],
    ) -> list[int]:
        """Upsert the normalized Strava activities into `public.activities`.

        Parameters:
            user_id: APEX app-level user id for the athlete.
            activities: Normalized Strava activity payloads ready for Postgres.

        Returns:
            list[int]: Stable Strava activity identifiers written in this batch.

        Raises:
            Exception: Propagated when Postgres writes fail.
        """

        unique_activities = {
            int(activity.strava_id): activity for activity in activities
        }
        if not unique_activities:
            return []

        rows = [
            (
                activity.id,
                user_id,
                activity.strava_id,
                activity.sport,
                activity.name,
                activity.start_time,
                activity.duration_seconds,
                activity.distance_m,
                activity.elevation_m,
                activity.avg_power_w,
                activity.normalized_power_w,
                activity.avg_hr,
                activity.max_hr,
                activity.tss,
                activity.intensity_factor,
                activity.calories,
                json.dumps(activity.metadata_json),
            )
            for activity in unique_activities.values()
        ]
        await self._executemany(UPSERT_ACTIVITY_SQL, rows)
        return list(unique_activities)

    async def _get_pool(self) -> asyncpg.Pool:
        """Return the lazily created asyncpg connection pool.

        Parameters:
            None.

        Returns:
            asyncpg.Pool: Shared pool used by the sync store.

        Raises:
            Exception: Propagated when the pool cannot be created.
        """

        if self._pool is not None:
            return self._pool

        async with self._pool_lock:
            if self._pool is None:
                self._pool = await asyncpg.create_pool(
                    self._database_url,
                    min_size=1,
                    max_size=3,
                    command_timeout=30,
                    # Supabase transaction poolers and asyncpg's statement
                    # cache do not work together especially well, so we keep
                    # the cache disabled to match the repo's existing setup.
                    statement_cache_size=0,
                )

        return self._pool

    async def _execute(self, query: str, *args: object) -> str:
        """Execute one SQL statement and return asyncpg's status string.

        Parameters:
            query: SQL statement to execute.
            *args: Positional parameters bound to the SQL statement.

        Returns:
            str: Asyncpg status string such as `INSERT 0 1`.

        Raises:
            Exception: Propagated when the database execution fails.
        """

        pool = await self._get_pool()
        async with pool.acquire() as connection:
            return await connection.execute(query, *args)

    async def _executemany(
        self,
        query: str,
        args: list[tuple[object, ...]],
    ) -> None:
        """Execute one SQL statement for many argument tuples.

        Parameters:
            query: SQL statement executed for every row tuple.
            args: Positional argument tuples for the SQL statement.

        Returns:
            None.

        Raises:
            Exception: Propagated when the database execution fails.
        """

        pool = await self._get_pool()
        async with pool.acquire() as connection:
            await connection.executemany(query, args)

    async def _fetch(self, query: str, *args: object) -> list[asyncpg.Record]:
        """Fetch many rows from Postgres.

        Parameters:
            query: SQL query to execute.
            *args: Positional parameters bound to the SQL query.

        Returns:
            list[asyncpg.Record]: Result rows returned by Postgres.

        Raises:
            Exception: Propagated when the database query fails.
        """

        pool = await self._get_pool()
        async with pool.acquire() as connection:
            return await connection.fetch(query, *args)

    async def _fetchrow(
        self,
        query: str,
        *args: object,
    ) -> asyncpg.Record | None:
        """Fetch one optional row from Postgres.

        Parameters:
            query: SQL query to execute.
            *args: Positional parameters bound to the SQL query.

        Returns:
            asyncpg.Record | None: First result row or `None`.

        Raises:
            Exception: Propagated when the database query fails.
        """

        pool = await self._get_pool()
        async with pool.acquire() as connection:
            return await connection.fetchrow(query, *args)


async def run_strava_sync(
    settings: Settings,
    *,
    store: StravaSyncStore | None = None,
    client: StravaClient | None = None,
    now: datetime | None = None,
) -> StravaSyncResult:
    """Refresh Strava tokens, fetch recent activities, and upsert them.

    Parameters:
        settings: Runtime settings for Postgres and Strava.
        store: Optional store override used by tests.
        client: Optional Strava client override used by tests.
        now: Optional fixed clock value used by tests.

        Returns:
            StravaSyncResult: Summary describing the completed sync run.

        Raises:
            StravaSyncError: Raised when credentials are missing or when the
                sync cannot determine its target athlete.
            Exception: Propagated when Postgres or HTTP calls fail unexpectedly.
    """

    started_at = now or datetime.now(tz=UTC)
    resolved_store = store or StravaSyncStore(
        settings.database_url,
        portal_user_id=settings.portal_user_id,
    )
    resolved_client = client or StravaClient(settings)
    close_store_after_run = store is None

    try:
        await resolved_store.ensure_schema()
        user_id = await resolved_store.resolve_user_id()
        _require_strava_api_credentials(settings)

        stored_tokens = await resolved_store.get_tokens(user_id)
        token_source = "database" if stored_tokens is not None else "environment"
        refresh_token = (
            stored_tokens.refresh_token
            if stored_tokens is not None
            else settings.strava_refresh_token
        )
        if not refresh_token:
            raise StravaSyncError(
                "No Strava refresh token is available. Set STRAVA_REFRESH_TOKEN "
                "for the first run so the sync can bootstrap Postgres token state."
            )

        refreshed_tokens = await resolved_client.refresh_access_token(refresh_token)
        await resolved_store.save_tokens(user_id, refreshed_tokens)

        lookback_hours = max(settings.strava_sync_lookback_hours, 1)
        after = started_at - timedelta(hours=lookback_hours)
        activity_ids = await resolved_client.list_activity_ids(
            refreshed_tokens.access_token,
            after=after,
        )

        normalized_activities = []
        for activity_id in activity_ids:
            detail = await resolved_client.get_activity(
                refreshed_tokens.access_token,
                activity_id,
            )
            normalized_activities.append(
                normalize_strava_activity(user_id=user_id, detail=detail)
            )

        upserted_activity_ids = await resolved_store.upsert_activities(
            user_id,
            normalized_activities,
        )

        return StravaSyncResult(
            user_id=user_id,
            token_source=token_source,
            lookback_hours=lookback_hours,
            fetched_activity_ids=activity_ids,
            upserted_activity_ids=upserted_activity_ids,
            started_at=started_at,
            completed_at=datetime.now(tz=UTC),
        )
    finally:
        if close_store_after_run:
            await resolved_store.close()


def normalize_strava_activity(
    *,
    user_id: str,
    detail: dict[str, Any],
) -> NormalizedStravaActivity:
    """Map one Strava activity payload into the APEX activity table shape.

    Parameters:
        user_id: APEX app-level user id for the athlete.
        detail: Raw activity payload returned by Strava.

    Returns:
        NormalizedStravaActivity: Normalized activity row ready for Postgres.

    Raises:
        StravaSyncError: Raised when the Strava payload is missing key fields.
    """

    try:
        activity_id = int(detail["id"])
        start_time = datetime.fromisoformat(
            str(detail["start_date"]).replace("Z", "+00:00")
        ).astimezone(UTC)
    except (KeyError, TypeError, ValueError) as error:
        raise StravaSyncError(
            "A Strava activity payload was missing `id` or `start_date`."
        ) from error

    return NormalizedStravaActivity(
        id=f"strava:{user_id}:{activity_id}",
        strava_id=str(activity_id),
        sport=map_strava_sport(detail.get("sport_type") or detail.get("type")),
        name=str(detail.get("name") or f"Strava activity {activity_id}"),
        start_time=start_time,
        duration_seconds=int(
            detail.get("moving_time") or detail.get("elapsed_time") or 0
        ),
        distance_m=float(detail.get("distance") or 0.0),
        elevation_m=float(detail.get("total_elevation_gain") or 0.0),
        avg_power_w=_maybe_float(detail.get("average_watts")),
        normalized_power_w=_maybe_float(detail.get("weighted_average_watts")),
        avg_hr=_maybe_int(detail.get("average_heartrate")),
        max_hr=_maybe_int(detail.get("max_heartrate")),
        tss=_extract_training_load(detail),
        intensity_factor=_maybe_float(detail.get("intensity_factor")),
        calories=_extract_calories(detail),
        metadata_json=build_activity_metadata(detail),
    )


def map_strava_sport(sport_type: object | None) -> str:
    """Translate Strava sport labels into the APEX activity taxonomy.

    Parameters:
        sport_type: Raw `sport_type` or `type` value from Strava.

    Returns:
        str: Normalized APEX sport value.

    Raises:
        This helper does not raise errors directly.
    """

    normalized = str(sport_type or "").lower()
    if "ride" in normalized or "cycle" in normalized:
        return "cycling"
    if normalized in {"run", "trailrun"}:
        return "running"
    if normalized == "walk":
        return "walking"
    if normalized == "hike":
        return "hiking"
    if normalized == "swim":
        return "swimming"
    if normalized in {"weighttraining", "weightsession", "workout"}:
        return "strength"
    return "default"


def build_activity_metadata(detail: dict[str, Any]) -> dict[str, Any]:
    """Return the structured metadata kept beside the normalized activity row.

    Parameters:
        detail: Raw activity payload returned by Strava.

    Returns:
        dict[str, Any]: Small metadata payload for provenance and debugging.

    Raises:
        This helper does not raise errors directly.
    """

    return {
        "source": "strava",
        "timezone": detail.get("timezone"),
        "manual": bool(detail.get("manual", False)),
        "trainer": bool(detail.get("trainer", False)),
        "commute": bool(detail.get("commute", False)),
        "is_private": bool(detail.get("private", False)),
        "external_id": detail.get("external_id"),
        "gear_id": detail.get("gear_id"),
        "average_speed_m_s": _maybe_float(detail.get("average_speed")),
        "max_speed_m_s": _maybe_float(detail.get("max_speed")),
        "relative_effort": _maybe_float(detail.get("relative_effort")),
        "strava_url": f"https://www.strava.com/activities/{detail['id']}",
    }


def _extract_calories(detail: dict[str, Any]) -> float:
    """Return the best available calorie-like value from Strava.

    Parameters:
        detail: Raw activity payload returned by Strava.

    Returns:
        float: Calories or kilojoules value, defaulting to zero.

    Raises:
        This helper does not raise errors directly.
    """

    return float(detail.get("kilojoules") or detail.get("calories") or 0.0)


def _extract_training_load(detail: dict[str, Any]) -> float:
    """Return the simplest available training-load marker from Strava.

    Parameters:
        detail: Raw activity payload returned by Strava.

    Returns:
        float: `suffer_score`, `relative_effort`, or zero when absent.

    Raises:
        This helper does not raise errors directly.
    """

    return float(detail.get("suffer_score") or detail.get("relative_effort") or 0.0)


def _maybe_float(value: object | None) -> float | None:
    """Convert one optional numeric value into `float`.

    Parameters:
        value: Candidate numeric value from Strava.

    Returns:
        float | None: Parsed float or `None`.

    Raises:
        ValueError: Raised when `value` is non-numeric text.
    """

    if value is None:
        return None
    return float(value)


def _maybe_int(value: object | None) -> int | None:
    """Convert one optional numeric value into `int`.

    Parameters:
        value: Candidate numeric value from Strava.

    Returns:
        int | None: Parsed integer or `None`.

    Raises:
        ValueError: Raised when `value` is non-numeric text.
    """

    if value is None:
        return None
    return int(round(float(value)))


def _dedupe_activity_ids(activity_ids: list[int]) -> list[int]:
    """Return stable unique activity ids while preserving Strava ordering.

    Parameters:
        activity_ids: Activity identifiers collected from Strava pages.

    Returns:
        list[int]: Unique activity identifiers in first-seen order.

    Raises:
        This helper does not raise errors directly.
    """

    seen: set[int] = set()
    unique_ids: list[int] = []
    for activity_id in activity_ids:
        if activity_id in seen:
            continue
        seen.add(activity_id)
        unique_ids.append(activity_id)
    return unique_ids


def _require_strava_api_credentials(settings: Settings) -> None:
    """Validate the Strava app credentials required on every sync run.

    Parameters:
        settings: Runtime settings containing Strava environment values.

    Returns:
        None.

    Raises:
        StravaSyncError: Raised when the Strava client id or secret is missing.
    """

    missing_variables = [
        name
        for name, value in (
            ("STRAVA_CLIENT_ID", settings.strava_client_id),
            ("STRAVA_CLIENT_SECRET", settings.strava_client_secret),
        )
        if not value
    ]
    if missing_variables:
        raise StravaSyncError(
            "Strava sync is not configured. Set "
            + ", ".join(missing_variables)
            + " in backend/.env or the deployment environment."
        )


async def _async_main() -> int:
    """Run the sync from the command line and print a JSON summary.

    Parameters:
        None.

    Returns:
        int: Process exit code.

    Raises:
        This helper does not raise errors directly because it converts failures
        into stderr output and a non-zero exit code.
    """

    try:
        result = await run_strava_sync(Settings.load())
    except Exception as error:  # pragma: no cover - exercised by manual use.
        print(str(error), file=sys.stderr)
        return 1

    print(json.dumps(result.to_response(), indent=2))
    return 0


def main() -> int:
    """Provide a small synchronous entrypoint for `python -m`.

    Parameters:
        None.

    Returns:
        int: Process exit code returned by the async runner.

    Raises:
        This helper does not raise errors directly.
    """

    return asyncio.run(_async_main())


if __name__ == "__main__":
    raise SystemExit(main())
