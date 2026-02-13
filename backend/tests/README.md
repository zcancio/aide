# AIde Tests

## Running Tests Locally

Tests require a PostgreSQL database with the AIde schema.

### Setup

1. **Create a test database:**
   ```bash
   createdb aide_test
   ```

2. **Set environment variables:**
   ```bash
   export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/aide_test"
   export JWT_SECRET="your-test-jwt-secret-min-32-chars"
   export RESEND_API_KEY="test-resend-key"
   export STRIPE_SECRET_KEY="test-stripe-key"
   export STRIPE_WEBHOOK_SECRET="test-webhook-secret"
   ```

3. **Run migrations:**
   ```bash
   alembic upgrade head
   ```

4. **Run tests:**
   ```bash
   ./run_tests.sh
   ```

   Or run specific test files:
   ```bash
   ./run_tests.sh backend/tests/test_auth.py -v
   ```

## Test Structure

- `conftest.py` - Pytest configuration and fixtures
- `test_db.py` - Database connection and RLS policy tests
- `test_auth.py` - Authentication flow tests (magic links, JWT, sessions)

## CI/CD

In CI environments without a database, tests will fail with connection errors.
This is expected. Tests should be run in environments with access to a PostgreSQL database.

For Railway deployments, tests can run against a separate test database instance.
