"""
Engine kernel test configuration.

Override asyncio settings for kernel tests which use function-scoped fixtures.
"""


# Override the session-scoped asyncio loop from pyproject.toml for kernel tests.
# Kernel tests use MemoryStorage and don't need a shared session loop.
# PostgresStorage tests that need DATABASE_URL are skipped automatically when not set.
