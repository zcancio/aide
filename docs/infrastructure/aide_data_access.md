# AIde — Data Access Layer

**Philosophy:** Define data shapes once. Write SQL by hand. Validate at the boundary. Log everything that matters. No magic.

---

## Principles

1. **Pydantic models are the schema.** One definition drives validation, serialization, API docs, and type checking.
2. **SQL is explicit.** Every query is visible, reviewable, and explainable. No generated SQL, no lazy loading, no N+1 surprises.
3. **Database access goes through a repository layer.** Application code never touches `conn.fetch()` directly. The repository is the only code that knows SQL exists.
4. **Every write is auditable.** Mutations go through functions that can log, validate, and enforce invariants.
5. **RLS is the last line of defense.** Even if the repository has a bug, Postgres won't return another user's data.

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│                   FastAPI Routes                 │
│  (HTTP handlers — thin, delegate immediately)    │
│                                                  │
│  @router.post("/api/aides")                      │
│  async def create_aide(req: CreateAideRequest):  │
│      aide = await aide_repo.create(user, req)    │
│      return AideResponse.from_model(aide)        │
└─────────────────────┬───────────────────────────┘
                      │
                      │  Pydantic models in, Pydantic models out
                      │
┌─────────────────────▼───────────────────────────┐
│                   Repositories                   │
│  (SQL lives here and ONLY here)                  │
│                                                  │
│  class AideRepo:                                 │
│      async def create(user, req) -> Aide         │
│      async def get(aide_id) -> Aide | None       │
│      async def list_for_user(user_id) -> [Aide]  │
│      async def update(aide_id, patch) -> Aide    │
│      async def publish(aide_id) -> Published     │
└─────────────────────┬───────────────────────────┘
                      │
                      │  asyncpg (raw SQL, parameterized)
                      │
┌─────────────────────▼───────────────────────────┐
│                  Connection Pool                 │
│  (RLS-scoped: every connection sets user_id)     │
│                                                  │
│  async with user_conn(user_id) as conn:          │
│      conn.execute("SELECT ...")                  │
└─────────────────────┬───────────────────────────┘
                      │
                      │  TLS, sslmode=require
                      │
┌─────────────────────▼───────────────────────────┐
│              Neon Postgres                        │
│  (RLS enforced, audit_log append-only)           │
└─────────────────────────────────────────────────┘
```

---

## Layer 1: Models (Pydantic)

These are your "protos." Define once, use everywhere.

```python
# backend/models/user.py
from pydantic import BaseModel, EmailStr
from datetime import datetime
from uuid import UUID
from typing import Literal


class User(BaseModel):
    """Core user model. Represents a row in the users table."""
    id: UUID
    email: EmailStr
    name: str | None = None
    tier: Literal["free", "pro"] = "free"
    stripe_customer_id: str | None = None
    stripe_sub_id: str | None = None
    turn_count: int = 0
    turn_week_start: datetime
    created_at: datetime


class UserPublic(BaseModel):
    """What the API returns. No Stripe IDs, no internal fields."""
    id: UUID
    name: str | None
    tier: Literal["free", "pro"]
    turn_count: int
    turn_week_start: datetime
    created_at: datetime
```

```python
# backend/models/aide.py
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from typing import Literal


class Aide(BaseModel):
    """Core aide model."""
    id: UUID
    user_id: UUID
    title: str = "Untitled"
    slug: str | None = None
    status: Literal["draft", "published", "archived"] = "draft"
    r2_prefix: str | None = None
    created_at: datetime
    updated_at: datetime


class CreateAideRequest(BaseModel):
    """What the client sends to create an aide."""
    title: str = Field(default="Untitled", max_length=200)


class UpdateAideRequest(BaseModel):
    """What the client sends to update an aide. All fields optional."""
    title: str | None = Field(default=None, max_length=200)
    slug: str | None = Field(default=None, max_length=100, pattern=r"^[a-z0-9-]+$")


class AideResponse(BaseModel):
    """What the API returns."""
    id: UUID
    title: str
    slug: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, aide: Aide) -> "AideResponse":
        return cls(
            id=aide.id,
            title=aide.title,
            slug=aide.slug,
            status=aide.status,
            created_at=aide.created_at,
            updated_at=aide.updated_at,
        )
```

```python
# backend/models/conversation.py
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import Any


class Message(BaseModel):
    """A single message in a conversation."""
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: datetime
    metadata: dict[str, Any] = {}


class Conversation(BaseModel):
    """Core conversation model."""
    id: UUID
    aide_id: UUID
    messages: list[Message] = []
    created_at: datetime
    updated_at: datetime
```

### Why This Matters

- **`CreateAideRequest`** is what the client sends. It has `max_length`, `pattern` — validation happens before any SQL runs.
- **`Aide`** is the internal model. It maps 1:1 to the database row.
- **`AideResponse`** is what the API returns. It excludes `user_id` and `r2_prefix` — the client doesn't need internal implementation details.

Three shapes for three boundaries. Like protos for different services, but within one app.

---

## Layer 2: Database Connection (RLS-Scoped)

```python
# backend/db.py
import asyncpg
import os
from contextlib import asynccontextmanager
from uuid import UUID

pool: asyncpg.Pool | None = None


async def init_pool():
    """Called once at app startup."""
    global pool
    pool = await asyncpg.create_pool(
        dsn=os.environ["DATABASE_URL"],
        min_size=2,
        max_size=20,
        # Register UUID codec so asyncpg handles UUID columns natively
        init=_init_connection,
    )


async def _init_connection(conn: asyncpg.Connection):
    """Set up type codecs for each new connection."""
    await conn.set_type_codec(
        "uuid", encoder=str, decoder=lambda x: UUID(x), schema="pg_catalog"
    )


@asynccontextmanager
async def user_conn(user_id: str | UUID):
    """
    Acquire a connection scoped to a specific user via RLS.

    Every query through this connection can only see/modify
    rows belonging to this user. Enforced by Postgres, not Python.
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            # This is the critical line. It sets the RLS context.
            # All policies reference current_setting('app.user_id')
            await conn.execute(
                "SELECT set_config('app.user_id', $1, true)",
                str(user_id),
            )
            yield conn


@asynccontextmanager
async def system_conn():
    """
    Connection without user scoping. For system operations only:
    - Migrations
    - Background tasks (abuse checks, cleanup)
    - Operations that span multiple users

    Should be rare. If you're using this in a route handler, something is wrong.
    """
    async with pool.acquire() as conn:
        yield conn
```

### The Contract

- **Route handlers** always use `user_conn(user.id)` — RLS is active.
- **Background tasks** use `system_conn()` — RLS is not active, but these tasks don't return data to users.
- **Nobody** uses `pool.acquire()` directly. The `db.py` module is the only place that touches the pool.

---

## Layer 3: Repositories

Each repository owns the SQL for one domain entity. This is the only code that writes SQL.

```python
# backend/repos/aide_repo.py
import asyncpg
from uuid import UUID, uuid4
from datetime import datetime, timezone

from backend.models.aide import Aide, CreateAideRequest, UpdateAideRequest
from backend.db import user_conn, system_conn


def _row_to_aide(row: asyncpg.Record) -> Aide:
    """Convert a database row to a Pydantic model. Explicit, no magic."""
    return Aide(
        id=row["id"],
        user_id=row["user_id"],
        title=row["title"],
        slug=row["slug"],
        status=row["status"],
        r2_prefix=row["r2_prefix"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class AideRepo:
    """
    All aide-related database operations.
    Every method takes a user_id to scope the connection via RLS.
    """

    async def create(self, user_id: UUID, req: CreateAideRequest) -> Aide:
        aide_id = uuid4()
        now = datetime.now(timezone.utc)

        async with user_conn(user_id) as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO aides (id, user_id, title, r2_prefix, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $5)
                RETURNING *
                """,
                aide_id,
                user_id,
                req.title,
                f"aides/{aide_id}",
                now,
            )
            return _row_to_aide(row)

    async def get(self, user_id: UUID, aide_id: UUID) -> Aide | None:
        async with user_conn(user_id) as conn:
            row = await conn.fetchrow(
                "SELECT * FROM aides WHERE id = $1",
                aide_id,
            )
            # RLS guarantees this can only return rows owned by user_id.
            # If the aide belongs to someone else, row is None.
            return _row_to_aide(row) if row else None

    async def list_for_user(self, user_id: UUID) -> list[Aide]:
        async with user_conn(user_id) as conn:
            rows = await conn.fetch(
                "SELECT * FROM aides WHERE status != 'archived' ORDER BY updated_at DESC"
            )
            # No WHERE user_id = $1 needed. RLS handles it.
            return [_row_to_aide(row) for row in rows]

    async def update(self, user_id: UUID, aide_id: UUID, req: UpdateAideRequest) -> Aide | None:
        async with user_conn(user_id) as conn:
            # Build SET clause from non-None fields only
            updates = {}
            if req.title is not None:
                updates["title"] = req.title
            if req.slug is not None:
                updates["slug"] = req.slug

            if not updates:
                return await self.get(user_id, aide_id)

            set_clause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(updates))
            values = list(updates.values())

            row = await conn.fetchrow(
                f"""
                UPDATE aides
                SET {set_clause}, updated_at = now()
                WHERE id = $1
                RETURNING *
                """,
                aide_id,
                *values,
            )
            # RLS: if aide doesn't belong to user, row is None (update affected 0 rows)
            return _row_to_aide(row) if row else None

    async def delete(self, user_id: UUID, aide_id: UUID) -> bool:
        async with user_conn(user_id) as conn:
            result = await conn.execute(
                "DELETE FROM aides WHERE id = $1",
                aide_id,
            )
            # RLS: can only delete own aides
            return result == "DELETE 1"

    async def get_by_slug(self, slug: str) -> Aide | None:
        """Public lookup — no user scoping needed. Used for published page serving."""
        async with system_conn() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM aides WHERE slug = $1 AND status = 'published'",
                slug,
            )
            return _row_to_aide(row) if row else None

    async def count_for_user(self, user_id: UUID) -> int:
        async with user_conn(user_id) as conn:
            return await conn.fetchval("SELECT count(*) FROM aides")
            # RLS scopes this automatically
```

```python
# backend/repos/user_repo.py
import asyncpg
from uuid import UUID

from backend.models.user import User
from backend.db import user_conn, system_conn


def _row_to_user(row: asyncpg.Record) -> User:
    return User(
        id=row["id"],
        email=row["email"],
        name=row["name"],
        tier=row["tier"],
        stripe_customer_id=row["stripe_customer_id"],
        stripe_sub_id=row["stripe_sub_id"],
        turn_count=row["turn_count"],
        turn_week_start=row["turn_week_start"],
        created_at=row["created_at"],
    )


class UserRepo:

    async def get_by_email(self, email: str) -> User | None:
        """Used during magic link verification. System conn because user context not yet established."""
        async with system_conn() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE email = $1",
                email,
            )
            return _row_to_user(row) if row else None

    async def create(self, email: str) -> User:
        """Create a new user during first magic link verification."""
        async with system_conn() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO users (email)
                VALUES ($1)
                RETURNING *
                """,
                email,
            )
            return _row_to_user(row)

    async def get(self, user_id: UUID) -> User | None:
        async with user_conn(user_id) as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
            return _row_to_user(row) if row else None

    async def increment_turns(self, user_id: UUID) -> int:
        """Increment turn count. Returns new count."""
        async with user_conn(user_id) as conn:
            return await conn.fetchval(
                """
                UPDATE users SET turn_count = turn_count + 1
                WHERE id = $1
                RETURNING turn_count
                """,
                user_id,
            )

    async def reset_turns_if_needed(self, user_id: UUID) -> None:
        """Reset weekly turn counter if 7 days have passed."""
        async with user_conn(user_id) as conn:
            await conn.execute(
                """
                UPDATE users
                SET turn_count = 0, turn_week_start = now()
                WHERE id = $1
                AND turn_week_start < now() - interval '7 days'
                """,
                user_id,
            )

    async def upgrade_to_pro(self, user_id: UUID, stripe_customer_id: str, stripe_sub_id: str) -> None:
        async with user_conn(user_id) as conn:
            await conn.execute(
                """
                UPDATE users
                SET tier = 'pro', stripe_customer_id = $2, stripe_sub_id = $3
                WHERE id = $1
                """,
                user_id,
                stripe_customer_id,
                stripe_sub_id,
            )

    async def downgrade_to_free(self, user_id: UUID) -> None:
        async with user_conn(user_id) as conn:
            await conn.execute(
                """
                UPDATE users
                SET tier = 'free', stripe_sub_id = NULL
                WHERE id = $1
                """,
                user_id,
            )
```

```python
# backend/repos/conversation_repo.py
import asyncpg
import json
from uuid import UUID, uuid4
from datetime import datetime, timezone

from backend.models.conversation import Conversation, Message
from backend.db import user_conn


def _row_to_conversation(row: asyncpg.Record) -> Conversation:
    messages_raw = row["messages"]
    # JSONB comes back as a Python list from asyncpg
    if isinstance(messages_raw, str):
        messages_raw = json.loads(messages_raw)
    messages = [Message(**m) for m in messages_raw]

    return Conversation(
        id=row["id"],
        aide_id=row["aide_id"],
        messages=messages,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class ConversationRepo:

    async def get_for_aide(self, user_id: UUID, aide_id: UUID) -> Conversation | None:
        async with user_conn(user_id) as conn:
            row = await conn.fetchrow(
                "SELECT * FROM conversations WHERE aide_id = $1 ORDER BY updated_at DESC LIMIT 1",
                aide_id,
            )
            # RLS: only returns if the aide belongs to this user
            return _row_to_conversation(row) if row else None

    async def create(self, user_id: UUID, aide_id: UUID) -> Conversation:
        async with user_conn(user_id) as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO conversations (id, aide_id)
                VALUES ($1, $2)
                RETURNING *
                """,
                uuid4(),
                aide_id,
            )
            return _row_to_conversation(row)

    async def append_message(
        self, user_id: UUID, conversation_id: UUID, message: Message
    ) -> None:
        async with user_conn(user_id) as conn:
            await conn.execute(
                """
                UPDATE conversations
                SET messages = messages || $2::jsonb,
                    updated_at = now()
                WHERE id = $1
                """,
                conversation_id,
                json.dumps([message.model_dump(mode="json")]),
            )
```

---

## Layer 4: Route Handlers (Thin)

Route handlers are thin. They authenticate, call the repo, and return a response. No SQL, no business logic beyond simple checks.

```python
# backend/routes/aides.py
from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID

from backend.auth import get_current_user
from backend.models.user import User
from backend.models.aide import CreateAideRequest, UpdateAideRequest, AideResponse
from backend.repos.aide_repo import AideRepo
from backend.repos.user_repo import UserRepo

router = APIRouter(prefix="/api/aides", tags=["aides"])
aide_repo = AideRepo()
user_repo = UserRepo()

FREE_AIDE_LIMIT = 5


@router.get("")
async def list_aides(user: User = Depends(get_current_user)) -> list[AideResponse]:
    aides = await aide_repo.list_for_user(user.id)
    return [AideResponse.from_model(a) for a in aides]


@router.post("", status_code=201)
async def create_aide(
    req: CreateAideRequest,
    user: User = Depends(get_current_user),
) -> AideResponse:
    if user.tier == "free":
        count = await aide_repo.count_for_user(user.id)
        if count >= FREE_AIDE_LIMIT:
            raise HTTPException(403, "Free tier limited to 5 aides. Upgrade to Pro.")

    aide = await aide_repo.create(user.id, req)
    return AideResponse.from_model(aide)


@router.get("/{aide_id}")
async def get_aide(
    aide_id: UUID,
    user: User = Depends(get_current_user),
) -> AideResponse:
    aide = await aide_repo.get(user.id, aide_id)
    if not aide:
        raise HTTPException(404, "Aide not found")
    return AideResponse.from_model(aide)


@router.patch("/{aide_id}")
async def update_aide(
    aide_id: UUID,
    req: UpdateAideRequest,
    user: User = Depends(get_current_user),
) -> AideResponse:
    aide = await aide_repo.update(user.id, aide_id, req)
    if not aide:
        raise HTTPException(404, "Aide not found")
    return AideResponse.from_model(aide)


@router.delete("/{aide_id}", status_code=204)
async def delete_aide(
    aide_id: UUID,
    user: User = Depends(get_current_user),
) -> None:
    deleted = await aide_repo.delete(user.id, aide_id)
    if not deleted:
        raise HTTPException(404, "Aide not found")
```

---

## What This Gets You

### Like Google's Approach

| Google | AIde |
|--------|------|
| Proto definitions | Pydantic models |
| Generated code from .proto files | Pydantic validation + FastAPI schema generation |
| No ORM — direct Spanner API | No ORM — direct asyncpg |
| Type-safe at compile time | Type-safe via Pydantic + mypy |
| Schema evolution via proto compatibility rules | Schema evolution via Alembic migrations |
| Access through service layer only | Access through repository layer only |
| RPC boundaries between services | Function boundaries between layers |

### Unlike Google (and why that's fine)

| Google | AIde | Why |
|--------|------|-----|
| Protobuf binary serialization | JSON serialization | You have one service, not thousands. JSON is fine. |
| gRPC between services | HTTP/WebSocket | One service. No need for gRPC. |
| Spanner (global, distributed) | Neon Postgres (single region) | You don't need global consistency for < 50K users. |
| Thousands of engineers need compile-time contracts | One engineer needs runtime validation | Pydantic gives you runtime checks which are sufficient. |

### Security Properties

```
1. Route handler calls aide_repo.get(user.id, aide_id)
2. Repo opens user_conn(user.id) which sets RLS context
3. SQL runs: SELECT * FROM aides WHERE id = $1
4. Postgres RLS adds: AND user_id = current_setting('app.user_id')
5. Row returned only if it belongs to this user

Even if a route handler accidentally passes the wrong aide_id,
RLS prevents cross-user data access at the database level.
```

### Auditability

Every mutation goes through a repo method. Adding logging is one decorator:

```python
# backend/repos/base.py
import functools
import logging

logger = logging.getLogger("aide.repo")

def log_mutation(func):
    """Decorator for repo methods that modify data."""
    @functools.wraps(func)
    async def wrapper(self, user_id, *args, **kwargs):
        result = await func(self, user_id, *args, **kwargs)
        logger.info(
            "mutation",
            extra={
                "method": func.__name__,
                "repo": self.__class__.__name__,
                "user_id": str(user_id),
            },
        )
        return result
    return wrapper
```

```python
# Usage in repo
class AideRepo:
    @log_mutation
    async def create(self, user_id: UUID, req: CreateAideRequest) -> Aide:
        ...

    @log_mutation
    async def delete(self, user_id: UUID, aide_id: UUID) -> bool:
        ...
```

---

## File Structure

```
backend/
├── main.py                  # FastAPI app, lifespan, Sentry init
├── db.py                    # Connection pool, user_conn(), system_conn()
├── auth.py                  # JWT verification, get_current_user dependency
├── models/
│   ├── __init__.py
│   ├── user.py              # User, UserPublic
│   ├── aide.py              # Aide, CreateAideRequest, UpdateAideRequest, AideResponse
│   ├── conversation.py      # Conversation, Message
│   └── published.py         # PublishedVersion
├── repos/
│   ├── __init__.py
│   ├── base.py              # log_mutation decorator
│   ├── user_repo.py         # UserRepo
│   ├── aide_repo.py         # AideRepo
│   ├── conversation_repo.py # ConversationRepo
│   └── publish_repo.py      # PublishRepo
├── routes/
│   ├── __init__.py
│   ├── aides.py             # CRUD endpoints
│   ├── conversations.py     # WebSocket chat
│   ├── publish.py           # Publish/unpublish
│   ├── auth_routes.py       # OAuth callback, logout
│   └── admin.py             # /stats, /health
├── services/
│   ├── __init__.py
│   ├── ai_provider.py       # LLM abstraction (Anthropic, OpenAI, Gemini)
│   ├── r2.py                # Cloudflare R2 file operations
│   └── stripe_service.py    # Stripe webhook handling
└── middleware/
    ├── __init__.py
    ├── usage.py             # Turn tracking, abuse detection
    └── sentry_context.py    # Anonymous user context for Sentry
```

### The Rules

- **`models/`** — Pure data definitions. No imports from `db`, `repos`, or `routes`.
- **`repos/`** — SQL lives here. Imports from `models/` and `db`. Never imported by `models/`.
- **`routes/`** — HTTP handlers. Imports from `repos/` and `models/`. Never writes SQL.
- **`services/`** — External integrations (R2, Stripe, AI). No SQL, no HTTP handling.
- **`middleware/`** — Cross-cutting concerns. Thin.

Dependency flows one way: `routes → repos → db`, `routes → services`. No cycles.

---

## Migration Strategy

Use Alembic for schema migrations, but keep them hand-written. No autogenerate.

```python
# alembic/versions/001_initial.py
"""Initial schema."""

from alembic import op
import sqlalchemy as sa

def upgrade():
    op.execute("""
        CREATE TABLE users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email TEXT UNIQUE NOT NULL,
            name TEXT,
            tier TEXT DEFAULT 'free' CHECK (tier IN ('free', 'pro')),
            stripe_customer_id TEXT,
            stripe_sub_id TEXT,
            turn_count INTEGER DEFAULT 0,
            turn_week_start TIMESTAMPTZ DEFAULT now(),
            created_at TIMESTAMPTZ DEFAULT now()
        );

        CREATE TABLE magic_links (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email TEXT NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            used BOOLEAN DEFAULT false,
            created_at TIMESTAMPTZ DEFAULT now()
        );
        CREATE INDEX idx_magic_links_token ON magic_links(token);
        CREATE INDEX idx_magic_links_email ON magic_links(email);
        
        CREATE TABLE aides (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID REFERENCES users(id) ON DELETE CASCADE,
            title TEXT DEFAULT 'Untitled',
            slug TEXT UNIQUE,
            status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived')),
            r2_prefix TEXT,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        );
        
        -- ... rest of schema
    """)

def downgrade():
    op.execute("DROP TABLE IF EXISTS conversations CASCADE")
    op.execute("DROP TABLE IF EXISTS aides CASCADE")
    op.execute("DROP TABLE IF EXISTS magic_links CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")
```

Why hand-written? Because autogenerated migrations hide what's changing. A migration that adds a column should be 3 lines of SQL, reviewable in a PR. Not 50 lines of generated Python that you have to squint at to understand.

---

## Testing

```python
# backend/tests/conftest.py
import pytest
import asyncpg
from uuid import uuid4

@pytest.fixture
async def test_db():
    """Create a fresh test database for each test."""
    conn = await asyncpg.connect(os.environ["TEST_DATABASE_URL"])
    # Run migrations
    # ...
    yield conn
    await conn.close()

@pytest.fixture
async def test_user(test_db):
    """Create a test user."""
    user_id = uuid4()
    await test_db.execute(
        "INSERT INTO users (id, email) VALUES ($1, $2)",
        user_id, f"test-{user_id}@example.com",
    )
    return user_id
```

```python
# backend/tests/test_aide_repo.py
async def test_create_aide(test_user):
    repo = AideRepo()
    req = CreateAideRequest(title="My Page")
    aide = await repo.create(test_user, req)
    
    assert aide.title == "My Page"
    assert aide.user_id == test_user
    assert aide.status == "draft"

async def test_rls_prevents_cross_user_access(test_user):
    """Verify that user A cannot see user B's aides."""
    repo = AideRepo()
    
    # Create aide as user A
    aide = await repo.create(test_user, CreateAideRequest(title="Secret"))
    
    # Try to access as user B
    other_user = uuid4()
    result = await repo.get(other_user, aide.id)
    
    assert result is None  # RLS blocks access
```

Tests verify the repository behavior AND the RLS policies. If someone accidentally removes an RLS policy, the cross-user test fails.

---

## RLS Exception: aide_files

The `aide_files` table **intentionally has NO RLS policies**. This is not an oversight.

### Rationale

The AIde kernel operates at the **system level**, not the user level:

- The kernel is a pure function that transforms events into state and renders HTML
- It has no concept of "users" — it works with event logs and snapshots
- Kernel operations are invoked by the orchestrator layer, which handles authentication and authorization
- The kernel itself is user-agnostic by design

### Access Control

Access control for aide files is enforced at the **orchestrator layer**:

1. **Authentication**: User identity is verified before any orchestrator operations
2. **Authorization**: The orchestrator checks that the user owns the aide before invoking kernel operations
3. **Kernel Execution**: Once authorized, kernel operations run without user scoping

This separation is intentional:
- The kernel remains a pure, testable function with no side effects
- Authentication and authorization logic stays in the orchestrator where it belongs
- The kernel can be distributed as a standalone module (Python, JS, TS) with zero dependencies

### Why No RLS?

RLS is designed for multi-tenant databases where different users share the same tables. The kernel's design doesn't fit this pattern:

- Kernel operations are **invoked by the system**, not directly by users
- The orchestrator (which has user context) decides **which** aide files to operate on
- The kernel (which has no user context) executes **how** to process those files

Adding RLS to `aide_files` would:
- Complicate kernel execution (now needs to know about user_id)
- Break the clean separation between orchestration and execution
- Violate the pure function design of the kernel

### Security Model

```
User Request → Orchestrator (auth + authz) → Kernel (pure execution)
              ↑                                ↑
              Has user context                  No user context
              Chooses which aide                Processes the aide
```

This is **intentional architecture**, not a security gap. The orchestrator is the security boundary, not the database.
