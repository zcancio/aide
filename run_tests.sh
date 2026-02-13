#!/bin/bash
# Test runner script with required environment variables

# Set minimal test environment variables
export DATABASE_URL="${DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/aide_test}"
export JWT_SECRET="${JWT_SECRET:-test-jwt-secret-key-for-testing-only-min-32-chars}"
export RESEND_API_KEY="${RESEND_API_KEY:-test-resend-key}"
export STRIPE_SECRET_KEY="${STRIPE_SECRET_KEY:-test-stripe-key}"
export STRIPE_WEBHOOK_SECRET="${STRIPE_WEBHOOK_SECRET:-test-webhook-secret}"

# Run pytest
python -m pytest backend/tests/ -v "$@"
