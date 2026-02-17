"""
Tests for PostgresStorage adapter.

Requires a running Postgres instance with the aide_files table.
"""

import os
import uuid

import asyncpg
import pytest

from engine.kernel.assembly import AideAssembly
from engine.kernel.postgres_storage import PostgresStorage
from engine.kernel.types import Blueprint, Event


@pytest.fixture
async def db_pool():
    """Create a connection pool for tests."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL not set")

    pool = await asyncpg.create_pool(database_url)
    yield pool
    await pool.close()


@pytest.fixture
async def storage(db_pool):
    """Create a PostgresStorage instance."""
    return PostgresStorage(db_pool)


@pytest.fixture
async def assembly(storage):
    """Create an AideAssembly instance with PostgresStorage."""
    return AideAssembly(storage)


class TestPostgresStorage:
    """Test PostgresStorage CRUD operations."""

    @pytest.mark.asyncio
    async def test_put_and_get(self, storage):
        """Test storing and retrieving HTML."""
        aide_id = str(uuid.uuid4())
        html = "<html><body>Test</body></html>"

        await storage.put(aide_id, html)
        retrieved = await storage.get(aide_id)

        assert retrieved == html

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, storage):
        """Test getting a nonexistent aide returns None."""
        aide_id = str(uuid.uuid4())
        result = await storage.get(aide_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_update_existing(self, storage):
        """Test updating an existing aide."""
        aide_id = str(uuid.uuid4())
        html1 = "<html><body>Version 1</body></html>"
        html2 = "<html><body>Version 2</body></html>"

        await storage.put(aide_id, html1)
        await storage.put(aide_id, html2)
        retrieved = await storage.get(aide_id)

        assert retrieved == html2

    @pytest.mark.asyncio
    async def test_delete(self, storage):
        """Test deleting an aide."""
        aide_id = str(uuid.uuid4())
        html = "<html><body>Test</body></html>"

        await storage.put(aide_id, html)
        await storage.delete(aide_id)
        retrieved = await storage.get(aide_id)

        assert retrieved is None

    @pytest.mark.asyncio
    async def test_put_published(self, storage):
        """Test storing published HTML with a slug."""
        slug = "test-slug"
        html = "<html><body>Published</body></html>"

        await storage.put_published(slug, html)
        # Published files are stored with "published:" prefix
        retrieved = await storage.get(f"published:{slug}")

        assert retrieved == html


class TestPostgresStorageWithAssembly:
    """Test PostgresStorage integration with AideAssembly."""

    @pytest.mark.asyncio
    async def test_create_and_save(self, assembly):
        """Test creating and saving an aide through assembly layer."""
        blueprint = Blueprint(
            identity="Test aide for PostgresStorage",
            voice="State reflections only.",
        )

        aide_file = await assembly.create(blueprint)
        aide_id = aide_file.aide_id

        # Save to storage
        await assembly.save(aide_file)

        # Load back
        loaded = await assembly.load(aide_id)

        assert loaded.aide_id == aide_id
        assert loaded.blueprint.identity == blueprint.identity

    @pytest.mark.asyncio
    async def test_apply_and_save(self, assembly):
        """Test applying events and saving."""
        blueprint = Blueprint(
            identity="Event test aide",
            voice="No first person.",
        )

        aide_file = await assembly.create(blueprint)
        aide_id = aide_file.aide_id

        # Create events
        events = [
            Event(
                id="evt_1",
                sequence=0,
                timestamp="2024-01-01T00:00:00Z",
                actor="test",
                source="test",
                type="meta.update",
                payload={"title": "Test Title"},
            ),
            Event(
                id="evt_2",
                sequence=0,
                timestamp="2024-01-01T00:00:01Z",
                actor="test",
                source="test",
                type="collection.create",
                payload={
                    "id": "items",
                    "name": "Items",
                    "schema": {"name": "string"},
                    "primary_field": "name",
                },
            ),
        ]

        # Apply events
        result = await assembly.apply(aide_file, events)
        assert len(result.applied) == 2
        assert len(result.rejected) == 0

        # Save
        await assembly.save(aide_file)

        # Load back and verify
        loaded = await assembly.load(aide_id)
        assert loaded.snapshot["meta"]["title"] == "Test Title"
        assert "items" in loaded.snapshot["collections"]
        assert len(loaded.events) == 2

    @pytest.mark.asyncio
    async def test_publish_and_load(self, assembly):
        """Test publishing an aide with a slug."""
        blueprint = Blueprint(
            identity="Publish test aide",
            voice="State reflections only.",
        )

        aide_file = await assembly.create(blueprint)
        await assembly.save(aide_file)

        # Publish with slug
        slug = f"test-{uuid.uuid4().hex[:8]}"
        url = await assembly.publish(aide_file, slug=slug, is_free_tier=False)

        assert url == f"https://toaide.com/p/{slug}"

    @pytest.mark.asyncio
    async def test_round_trip_with_complex_state(self, assembly):
        """Test full round-trip with complex state."""
        blueprint = Blueprint(
            identity="Complex state test",
            voice="No encouragement.",
        )

        aide_file = await assembly.create(blueprint)

        # Create complex events
        events = [
            Event(
                id="evt_1",
                sequence=0,
                timestamp="2024-01-01T00:00:00Z",
                actor="test",
                source="test",
                type="meta.update",
                payload={"title": "Grocery List"},
            ),
            Event(
                id="evt_2",
                sequence=0,
                timestamp="2024-01-01T00:00:01Z",
                actor="test",
                source="test",
                type="collection.create",
                payload={
                    "id": "groceries",
                    "name": "Items",
                    "schema": {
                        "name": "string",
                        "checked": "bool",
                    },
                    "primary_field": "name",
                },
            ),
            Event(
                id="evt_3",
                sequence=0,
                timestamp="2024-01-01T00:00:02Z",
                actor="test",
                source="test",
                type="entity.create",
                payload={
                    "collection": "groceries",
                    "id": "item_milk",
                    "fields": {"name": "Milk", "checked": False},
                },
            ),
        ]

        # Apply and save
        result = await assembly.apply(aide_file, events)
        assert len(result.applied) == 3
        await assembly.save(aide_file)

        # Load back
        loaded = await assembly.load(aide_file.aide_id)

        # Verify all state is preserved
        assert loaded.snapshot["meta"]["title"] == "Grocery List"
        assert "groceries" in loaded.snapshot["collections"]
        assert "item_milk" in loaded.snapshot["collections"]["groceries"]["entities"]
        assert len(loaded.events) == 3

        # Verify HTML can be re-parsed
        from engine.kernel.assembly import parse_aide_html

        parsed = parse_aide_html(loaded.html)
        assert parsed.snapshot is not None
        assert parsed.blueprint is not None
        assert len(parsed.events) == 3
