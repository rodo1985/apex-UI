"""Runtime configuration for the APEX progress portal backend."""

from __future__ import annotations

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Represent the environment-driven backend settings.

    Parameters:
        database_url: Postgres connection string for the Supabase-backed schema.
        portal_subject: Subject whose data should be shown in the portal.
        portal_user_id: Optional APEX app user id bound to the portal.
        portal_access_token: Optional bearer token required by the read API.
        allowed_origins_raw: Comma-separated list of local/dev browser origins.
        portal_timezone: IANA timezone used to resolve the default business day.
        portal_athlete_name: Optional display-name override for the frontend.

    Returns:
        Settings: Validated backend runtime configuration.

    Raises:
        ValidationError: Raised by Pydantic when required values are missing.

    Example:
        >>> settings = Settings(
        ...     DATABASE_URL="postgresql://example",
        ...     APEX_PORTAL_SUBJECT="athlete-1",
        ... )
        >>> settings.portal_subject
        'athlete-1'
    """

    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        validation_alias=AliasChoices("APEX_DATABASE_URL", "DATABASE_URL")
    )
    portal_subject: str = Field(validation_alias="APEX_PORTAL_SUBJECT")
    portal_user_id: str | None = Field(
        default=None,
        validation_alias="APEX_PORTAL_USER_ID",
    )
    portal_access_token: str | None = Field(
        default=None,
        validation_alias="APEX_PORTAL_ACCESS_TOKEN",
    )
    allowed_origins_raw: str = Field(
        default="http://127.0.0.1:5173,http://localhost:5173",
        validation_alias="APEX_ALLOWED_ORIGINS",
    )
    portal_timezone: str = Field(
        default="Europe/Madrid",
        validation_alias="APEX_PORTAL_TIMEZONE",
    )
    portal_athlete_name: str | None = Field(
        default=None,
        validation_alias="APEX_PORTAL_ATHLETE_NAME",
    )

    @property
    def cors_origins(self) -> list[str]:
        """Return the configured CORS origins as a cleaned list.

        Parameters:
            None.

        Returns:
            list[str]: Browser origins allowed to reach the API directly.

        Raises:
            This property does not raise errors directly.

        Example:
            >>> Settings(
            ...     DATABASE_URL="postgresql://example",
            ...     APEX_PORTAL_SUBJECT="athlete-1",
            ...     APEX_ALLOWED_ORIGINS="http://localhost:5173, http://127.0.0.1:5173",
            ... ).cors_origins
            ['http://localhost:5173', 'http://127.0.0.1:5173']
        """

        return [
            origin.strip()
            for origin in self.allowed_origins_raw.split(",")
            if origin.strip()
        ]

    @classmethod
    def load(cls) -> Settings:
        """Load settings from the current process environment.

        Parameters:
            None.

        Returns:
            Settings: The validated runtime configuration.

        Raises:
            ValidationError: Raised when required variables are missing.

        Example:
            >>> isinstance(Settings.load(), Settings)
            True
        """

        return cls()
