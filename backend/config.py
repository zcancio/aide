"""
AIde configuration — all environment variables in one place.

Read from environment at runtime. Never hardcode secrets.
"""

from __future__ import annotations

import os


class Settings:
    """Application settings from environment variables."""

    # Database
    DATABASE_URL: str = os.environ.get("DATABASE_URL", "")

    # R2 / S3 Storage
    R2_ENDPOINT: str = os.environ.get("R2_ENDPOINT", "")
    R2_ACCESS_KEY: str = os.environ.get("R2_ACCESS_KEY", "")
    R2_SECRET_KEY: str = os.environ.get("R2_SECRET_KEY", "")
    R2_WORKSPACE_BUCKET: str = os.environ.get("R2_WORKSPACE_BUCKET", "aide-workspaces")
    R2_PUBLISHED_BUCKET: str = os.environ.get("R2_PUBLISHED_BUCKET", "aide-published")

    # Email (Resend)
    RESEND_API_KEY: str = os.environ.get("RESEND_API_KEY", "")

    # Auth
    JWT_SECRET: str = os.environ.get("JWT_SECRET", "")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = 24

    # Magic Links
    MAGIC_LINK_EXPIRY_MINUTES: int = 15
    MAGIC_LINK_RATE_LIMIT_PER_EMAIL: int = 5  # per hour
    MAGIC_LINK_RATE_LIMIT_PER_IP: int = 20  # per hour

    # Stripe
    STRIPE_SECRET_KEY: str = os.environ.get("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET: str = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

    # Monitoring
    SLACK_WEBHOOK: str = os.environ.get("SLACK_WEBHOOK", "")
    SENTRY_DSN: str = os.environ.get("SENTRY_DSN", "")

    # Application
    ENVIRONMENT: str = os.environ.get("ENVIRONMENT", "development")
    EDITOR_URL: str = os.environ.get("EDITOR_URL", "https://get.toaide.com")
    PUBLIC_URL: str = os.environ.get("PUBLIC_URL", "https://toaide.com")

    # Rate Limits
    FREE_TIER_TURNS_PER_WEEK: int = 50
    FREE_TIER_AIDE_LIMIT: int = 5
    API_RATE_LIMIT_PER_MINUTE: int = 100  # per user
    WEBSOCKET_MAX_CONNECTIONS: int = 5  # per user

    # AI Providers (for managed API routing)
    ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
    GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")


# Singleton instance
settings = Settings()

# Validate required settings
if not settings.DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is required")
if not settings.JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is required")
