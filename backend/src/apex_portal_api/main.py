"""FastAPI application for the APEX progress portal."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from apex_portal_api.config import Settings
from apex_portal_api.models import (
    BootstrapResponse,
    DailySnapshot,
    FoodProductsResponse,
    HistoryResponse,
    ProductUsageTrendsResponse,
    TrendsResponse,
)
from apex_portal_api.store import PortalStore, PostgresPortalStore, resolve_window


def create_app(
    settings: Settings | None = None,
    store: PortalStore | None = None,
) -> FastAPI:
    """Create the FastAPI application with injected settings and store.

    Parameters:
        settings: Optional pre-built settings, useful in tests.
        store: Optional store override, mainly useful in tests.

    Returns:
        FastAPI: Fully configured portal application.

    Raises:
        ValidationError: Propagated when required settings are missing.

    Example:
        >>> app = create_app()
        >>> app.title
        'APEX Progress Portal API'
    """

    resolved_settings = settings or Settings.load()
    resolved_store = store or PostgresPortalStore(
        database_url=resolved_settings.database_url,
        athlete_name_override=resolved_settings.portal_athlete_name,
        portal_user_id=resolved_settings.portal_user_id,
        portal_timezone=resolved_settings.portal_timezone,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        """Close the shared store when the ASGI app shuts down.

        Parameters:
            _: Current FastAPI application instance.

        Returns:
            AsyncIterator[None]: FastAPI lifespan context manager.

        Raises:
            Exception: Propagated if the underlying store fails to close.
        """

        yield
        await resolved_store.close()

    app = FastAPI(
        title="APEX Progress Portal API",
        version="0.1.0",
        summary="Read-only API for reviewing APEX progress data.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origins,
        allow_methods=["GET"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app.state.settings = resolved_settings
    app.state.store = resolved_store

    def current_store() -> PortalStore:
        """Return the configured store instance for the current app.

        Parameters:
            None.

        Returns:
            PortalStore: Read-only store used by the API routes.

        Raises:
            This helper does not raise errors directly.
        """

        return resolved_store

    def require_access(
        authorization: str | None = Header(default=None),
    ) -> None:
        """Enforce the optional bearer token configured for the portal.

        Parameters:
            authorization: Raw `Authorization` header from the request.

        Returns:
            None.

        Raises:
            HTTPException: Raised when a configured token is missing or invalid.
        """

        expected_token = resolved_settings.portal_access_token
        if not expected_token:
            return

        if authorization != f"Bearer {expected_token}":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="A valid portal access token is required.",
            )

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Return a simple backend health payload.

        Parameters:
            None.

        Returns:
            dict[str, str]: Small health payload for monitoring and deploy checks.

        Raises:
            This route does not raise errors directly.
        """

        return {"status": "ok"}

    @app.get("/portal/bootstrap", response_model=BootstrapResponse)
    async def bootstrap_portal(
        target_date: date | None = Query(default=None),
        history_days: int = Query(default=28, ge=7, le=180),
        trend_days: int = Query(default=84, ge=14, le=365),
        _: None = Depends(require_access),
        store_dependency: PortalStore = Depends(current_store),
    ) -> BootstrapResponse:
        """Return the initial payload required by the React portal.

        Parameters:
            target_date: Optional business date to load in the primary view.
            history_days: Number of days to include in the initial history view.
            trend_days: Number of days to include in the initial trend view.
            _: Access-control dependency for the optional bearer token.
            store_dependency: Store dependency injected by FastAPI.

        Returns:
            BootstrapResponse: Initial shell, day, history, and trend payload.

        Raises:
            HTTPException: Propagated by the access dependency when unauthorized.
            Exception: Propagated by the backing store when queries fail.
        """

        requested_date = target_date or _today_in_timezone(
            resolved_settings.portal_timezone
        )
        reference_date = (
            target_date
            if target_date is not None
            else await store_dependency.get_default_date(
                resolved_settings.portal_subject,
                requested_date,
            )
        )
        history_from, history_to = resolve_window(reference_date, history_days)
        trends_from, trends_to = resolve_window(reference_date, trend_days)

        profile = await store_dependency.get_profile(resolved_settings.portal_subject)
        snapshot = await store_dependency.get_daily_snapshot(
            resolved_settings.portal_subject,
            reference_date,
        )
        history = await store_dependency.get_history(
            resolved_settings.portal_subject,
            history_from,
            history_to,
        )
        trends = await store_dependency.get_trends(
            resolved_settings.portal_subject,
            trends_from,
            trends_to,
        )

        return BootstrapResponse(
            generated_at=datetime.now(tz=ZoneInfo("UTC")),
            profile=profile,
            snapshot=snapshot,
            history=history,
            trends=trends,
            access_protected=bool(resolved_settings.portal_access_token),
        )

    @app.get("/portal/day", response_model=DailySnapshot)
    async def get_day(
        target_date: date = Query(...),
        _: None = Depends(require_access),
        store_dependency: PortalStore = Depends(current_store),
    ) -> DailySnapshot:
        """Return the detailed snapshot for one selected day.

        Parameters:
            target_date: Business date to inspect.
            _: Access-control dependency for the optional bearer token.
            store_dependency: Store dependency injected by FastAPI.

        Returns:
            DailySnapshot: Daily summary, meals, and activities.

        Raises:
            HTTPException: Propagated by the access dependency when unauthorized.
            Exception: Propagated by the backing store when queries fail.
        """

        return await store_dependency.get_daily_snapshot(
            resolved_settings.portal_subject,
            target_date,
        )

    @app.get("/portal/products", response_model=FoodProductsResponse)
    async def get_products(
        date_to: date | None = Query(default=None),
        window_days: int = Query(default=30, ge=7, le=365),
        _: None = Depends(require_access),
        store_dependency: PortalStore = Depends(current_store),
    ) -> FoodProductsResponse:
        """Return the reusable food products bound to the current subject.

        Parameters:
            date_to: Optional inclusive upper bound for the usage window.
            window_days: Number of days to include in the trailing usage window.
            _: Access-control dependency for the optional bearer token.
            store_dependency: Store dependency injected by FastAPI.

        Returns:
            FoodProductsResponse: Read-only product catalog rows.

        Raises:
            HTTPException: Propagated by the access dependency when unauthorized.
            Exception: Propagated by the backing store when queries fail.
        """

        requested_date = date_to or _today_in_timezone(
            resolved_settings.portal_timezone
        )
        reference_date = (
            date_to
            if date_to is not None
            else await store_dependency.get_default_date(
                resolved_settings.portal_subject,
                requested_date,
            )
        )
        window_date_from, window_date_to = resolve_window(reference_date, window_days)
        return FoodProductsResponse(
            window_date_from=window_date_from,
            window_date_to=window_date_to,
            window_days=window_days,
            items=await store_dependency.list_products(
                resolved_settings.portal_subject,
                reference_date,
                window_days,
            ),
        )

    @app.get("/portal/history", response_model=HistoryResponse)
    async def get_history(
        date_to: date | None = Query(default=None),
        days: int = Query(default=28, ge=7, le=180),
        _: None = Depends(require_access),
        store_dependency: PortalStore = Depends(current_store),
    ) -> HistoryResponse:
        """Return the day-level history view for a window ending on `date_to`.

        Parameters:
            date_to: Optional inclusive upper bound, defaults to today's date.
            days: Number of days to include.
            _: Access-control dependency for the optional bearer token.
            store_dependency: Store dependency injected by FastAPI.

        Returns:
            HistoryResponse: Newest-first day rows for the history panel.

        Raises:
            HTTPException: Propagated by the access dependency when unauthorized.
            Exception: Propagated by the backing store when queries fail.
        """

        requested_date = date_to or _today_in_timezone(
            resolved_settings.portal_timezone
        )
        reference_date = (
            date_to
            if date_to is not None
            else await store_dependency.get_default_date(
                resolved_settings.portal_subject,
                requested_date,
            )
        )
        date_from, safe_date_to = resolve_window(reference_date, days)
        return await store_dependency.get_history(
            resolved_settings.portal_subject,
            date_from,
            safe_date_to,
        )

    @app.get("/portal/trends", response_model=TrendsResponse)
    async def get_trends(
        date_to: date | None = Query(default=None),
        days: int = Query(default=84, ge=14, le=365),
        _: None = Depends(require_access),
        store_dependency: PortalStore = Depends(current_store),
    ) -> TrendsResponse:
        """Return trend data for a window ending on `date_to`.

        Parameters:
            date_to: Optional inclusive upper bound, defaults to today's date.
            days: Number of days to include.
            _: Access-control dependency for the optional bearer token.
            store_dependency: Store dependency injected by FastAPI.

        Returns:
            TrendsResponse: Oldest-first day rows plus rolled-up metrics.

        Raises:
            HTTPException: Propagated by the access dependency when unauthorized.
            Exception: Propagated by the backing store when queries fail.
        """

        requested_date = date_to or _today_in_timezone(
            resolved_settings.portal_timezone
        )
        reference_date = (
            date_to
            if date_to is not None
            else await store_dependency.get_default_date(
                resolved_settings.portal_subject,
                requested_date,
            )
        )
        date_from, safe_date_to = resolve_window(reference_date, days)
        return await store_dependency.get_trends(
            resolved_settings.portal_subject,
            date_from,
            safe_date_to,
        )

    @app.get(
        "/portal/product-usage/trends",
        response_model=ProductUsageTrendsResponse,
    )
    async def get_product_usage_trends(
        product_id: str = Query(..., min_length=1),
        date_to: date | None = Query(default=None),
        days: int = Query(default=84, ge=14, le=365),
        _: None = Depends(require_access),
        store_dependency: PortalStore = Depends(current_store),
    ) -> ProductUsageTrendsResponse:
        """Return product-usage trend data for one reusable food product.

        Parameters:
            product_id: Product identifier to aggregate.
            date_to: Optional inclusive upper bound, defaults to today's date.
            days: Number of days to include.
            _: Access-control dependency for the optional bearer token.
            store_dependency: Store dependency injected by FastAPI.

        Returns:
            ProductUsageTrendsResponse: Oldest-first usage rows plus summary.

        Raises:
            HTTPException: Propagated by the access dependency when unauthorized.
            Exception: Propagated by the backing store when queries fail.
        """

        requested_date = date_to or _today_in_timezone(
            resolved_settings.portal_timezone
        )
        reference_date = (
            date_to
            if date_to is not None
            else await store_dependency.get_default_date(
                resolved_settings.portal_subject,
                requested_date,
            )
        )
        date_from, safe_date_to = resolve_window(reference_date, days)
        return await store_dependency.get_product_usage_trends(
            resolved_settings.portal_subject,
            product_id,
            date_from,
            safe_date_to,
        )

    return app


def _today_in_timezone(timezone_name: str) -> date:
    """Return today's business date for the configured timezone.

    Parameters:
        timezone_name: IANA timezone name such as `Europe/Madrid`.

    Returns:
        date: Today's date in the configured timezone.

    Raises:
        ZoneInfoNotFoundError: Raised when the timezone is invalid.

    Example:
        >>> isinstance(_today_in_timezone("UTC"), date)
        True
    """

    return datetime.now(tz=ZoneInfo(timezone_name)).date()


def main() -> None:
    """Provide a small CLI entrypoint message for the package.

    Parameters:
        None.

    Returns:
        None.

    Raises:
        This helper does not raise errors directly.
    """

    raise SystemExit(
        "Run the API with: uv run uvicorn apex_portal_api.main:app --reload"
    )


def _create_runtime_app() -> FastAPI:
    """Create the module-level ASGI app without breaking test imports.

    Parameters:
        None.

    Returns:
        FastAPI: Runtime-ready application using real or fallback settings.

    Raises:
        This helper does not raise errors directly.
    """

    try:
        return create_app()
    except ValidationError:
        # Tests import the module before setting runtime env vars. A fallback
        # app keeps imports cheap while still requiring real env configuration
        # for any meaningful data access.
        fallback_settings = Settings(
            DATABASE_URL="postgresql://placeholder",
            APEX_PORTAL_SUBJECT="placeholder-subject",
        )
        return create_app(settings=fallback_settings)


app = _create_runtime_app()
