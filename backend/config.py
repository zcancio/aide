"""
AIde configuration — all environment variables in one place.

Read from environment at runtime. Never hardcode secrets.
"""

from __future__ import annotations

import os

# Database
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is required")

# R2 / S3 Storage
R2_ENDPOINT = os.environ.get("R2_ENDPOINT", "")
R2_ACCESS_KEY = os.environ.get("R2_ACCESS_KEY", "")
R2_SECRET_KEY = os.environ.get("R2_SECRET_KEY", "")
R2_WORKSPACE_BUCKET = os.environ.get("R2_WORKSPACE_BUCKET", "aide-workspaces")
R2_PUBLISHED_BUCKET = os.environ.get("R2_PUBLISHED_BUCKET", "aide-published")

# Email (Resend)
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")

# Auth
JWT_SECRET = os.environ.get("JWT_SECRET", "")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is required")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24

# Magic Links
MAGIC_LINK_EXPIRY_MINUTES = 15
MAGIC_LINK_RATE_LIMIT_PER_EMAIL = 5  # per hour
MAGIC_LINK_RATE_LIMIT_PER_IP = 20  # per hour

# Stripe
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

# Monitoring
SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK", "")
SENTRY_DSN = os.environ.get("SENTRY_DSN", "")

# Application
ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")
EDITOR_URL = os.environ.get("EDITOR_URL", "https://get.toaide.com")
PUBLIC_URL = os.environ.get("PUBLIC_URL", "https://toaide.com")

# Rate Limits
FREE_TIER_TURNS_PER_WEEK = 50
FREE_TIER_AIDE_LIMIT = 5
API_RATE_LIMIT_PER_MINUTE = 100  # per user
WEBSOCKET_MAX_CONNECTIONS = 5  # per user

# AI Providers (for managed API routing)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
