"""
AIde Assembly -- Publish Tests (Category 6)

Publish a free-tier aide, verify footer appears. Publish a pro aide,
verify no footer.

From the spec (aide_assembly_spec.md, "Testing Strategy"):
  "6. Publish with footer. Publish a free-tier aide, verify footer
   appears. Publish a pro aide, verify no footer."

Additional behavior:
  - Publish generates a URL
  - Published HTML goes to a different bucket/slug
  - Events may be stripped for large aides (>500 events)

Reference: aide_assembly_spec.md (publish operation, Testing Strategy)
"""

import pytest

from engine.kernel.assembly import AideAssembly, MemoryStorage, parse_aide_html
from engine.kernel.types import Blueprint, Event, now_iso

# ============================================================================
# Fixtures
# ============================================================================


def make_blueprint():
    return Blueprint(
        identity="A published test aide.",
        voice="Public-facing.",
    )


def make_events(count: int) -> list[Event]:
    """Generate a specified number of entity create events."""
    events = [
        Event(
            id="evt_001",
            sequence=1,
            timestamp=now_iso(),
            actor="user_test",
            source="test",
            type="collection.create",
            payload={"id": "items", "schema": {"name": "string"}},
        ),
    ]

    for i in range(2, count + 1):
        events.append(
            Event(
                id=f"evt_{i:03d}",
                sequence=i,
                timestamp=now_iso(),
                actor="user_test",
                source="test",
                type="entity.create",
                payload={"collection": "items", "id": f"item_{i}", "fields": {"name": f"Item {i}"}},
            )
        )

    return events


# ============================================================================
# Publish basic behavior
# ============================================================================


class TestPublishBasic:
    """
    Verify basic publish behavior.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_publish_returns_url(self, assembly):
        """publish() returns a URL string."""
        aide_file = await assembly.create(make_blueprint())
        url = await assembly.publish(aide_file)

        assert url.startswith("https://toaide.com/p/")
        assert len(url) > len("https://toaide.com/p/")

    @pytest.mark.asyncio
    async def test_publish_with_custom_slug(self, assembly):
        """publish() uses provided slug in URL."""
        aide_file = await assembly.create(make_blueprint())
        url = await assembly.publish(aide_file, slug="my-custom-slug")

        assert url == "https://toaide.com/p/my-custom-slug"

    @pytest.mark.asyncio
    async def test_publish_writes_to_published_bucket(self, assembly, storage):
        """publish() writes to published storage, not workspace."""
        aide_file = await assembly.create(make_blueprint())
        await assembly.publish(aide_file, slug="test-slug")

        assert "test-slug" in storage.published
        assert aide_file.aide_id not in storage.published

    @pytest.mark.asyncio
    async def test_published_html_is_valid(self, assembly, storage):
        """Published HTML is valid and parseable."""
        aide_file = await assembly.create(make_blueprint())
        events = make_events(10)
        await assembly.apply(aide_file, events)

        await assembly.publish(aide_file, slug="valid-test")

        published_html = storage.published["valid-test"]
        assert published_html.startswith("<!DOCTYPE html>")

        parsed = parse_aide_html(published_html)
        assert parsed.parse_errors == []


# ============================================================================
# Footer behavior
# ============================================================================


class TestPublishFooter:
    """
    Verify footer appears for free tier, not for pro.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_free_tier_has_footer(self, assembly, storage):
        """Free tier publish includes footer."""
        aide_file = await assembly.create(make_blueprint())
        await assembly.publish(aide_file, slug="free-test", is_free_tier=True)

        published_html = storage.published["free-test"]
        assert "aide-footer" in published_html
        assert "Made with AIde" in published_html

    @pytest.mark.asyncio
    async def test_pro_tier_no_footer(self, assembly, storage):
        """Pro tier publish has no footer."""
        aide_file = await assembly.create(make_blueprint())
        await assembly.publish(aide_file, slug="pro-test", is_free_tier=False)

        published_html = storage.published["pro-test"]
        # Check that no footer element exists in body
        assert '<footer class="aide-footer">' not in published_html

    @pytest.mark.asyncio
    async def test_footer_in_body_not_head(self, assembly, storage):
        """Footer appears in body, not head."""
        import re

        aide_file = await assembly.create(make_blueprint())
        await assembly.publish(aide_file, slug="footer-location", is_free_tier=True)

        published_html = storage.published["footer-location"]

        # Extract body content
        body_match = re.search(r"<body[^>]*>(.*?)</body>", published_html, re.DOTALL)
        body = body_match.group(1) if body_match else ""

        assert "aide-footer" in body

    @pytest.mark.asyncio
    async def test_footer_after_main(self, assembly, storage):
        """Footer appears after main content."""
        aide_file = await assembly.create(make_blueprint())
        await assembly.publish(aide_file, slug="footer-order", is_free_tier=True)

        published_html = storage.published["footer-order"]

        main_end = published_html.find("</main>")
        footer_pos = published_html.find('<footer class="aide-footer">')

        assert main_end < footer_pos


# ============================================================================
# Event stripping for large aides
# ============================================================================


class TestPublishEventStripping:
    """
    Verify events are stripped for large aides (>500 events).
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_small_aide_keeps_events(self, assembly, storage):
        """Aide with <500 events keeps events in published version."""
        aide_file = await assembly.create(make_blueprint())
        events = make_events(50)  # Well under 500
        await assembly.apply(aide_file, events)

        await assembly.publish(aide_file, slug="small-test")

        published_html = storage.published["small-test"]
        parsed = parse_aide_html(published_html)

        assert len(parsed.events) == 50

    @pytest.mark.asyncio
    async def test_large_aide_strips_events(self, assembly, storage):
        """Aide with >500 events has no events in published version."""
        aide_file = await assembly.create(make_blueprint())
        events = make_events(501)  # Just over 500
        await assembly.apply(aide_file, events)

        await assembly.publish(aide_file, slug="large-test")

        published_html = storage.published["large-test"]
        parsed = parse_aide_html(published_html)

        # Events should be stripped (no aide-events block)
        assert len(parsed.events) == 0

    @pytest.mark.asyncio
    async def test_stripped_events_preserves_snapshot(self, assembly, storage):
        """Stripped events still has complete snapshot."""
        aide_file = await assembly.create(make_blueprint())
        events = make_events(501)
        await assembly.apply(aide_file, events)

        await assembly.publish(aide_file, slug="snapshot-test")

        published_html = storage.published["snapshot-test"]
        parsed = parse_aide_html(published_html)

        # Snapshot should have all 500 entities
        entities = parsed.snapshot["collections"]["items"]["entities"]
        assert len(entities) == 500  # 501 events - 1 collection.create = 500 entities


class TestPublishPreservesBlueprint:
    """
    Verify blueprint is always included in published version.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_published_has_blueprint(self, assembly, storage):
        """Published version includes blueprint."""
        bp = Blueprint(identity="Unique identity for publish test.")
        aide_file = await assembly.create(bp)

        await assembly.publish(aide_file, slug="bp-test")

        published_html = storage.published["bp-test"]
        parsed = parse_aide_html(published_html)

        assert parsed.blueprint is not None
        assert parsed.blueprint.identity == bp.identity


class TestPublishSnapshot:
    """
    Verify snapshot in published version matches workspace.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_published_snapshot_matches_workspace(self, assembly, storage):
        """Published snapshot is identical to workspace snapshot."""
        import json

        aide_file = await assembly.create(make_blueprint())
        events = make_events(10)
        await assembly.apply(aide_file, events)

        # Save to workspace
        await assembly.save(aide_file)

        # Publish
        await assembly.publish(aide_file, slug="match-test")

        # Compare snapshots
        workspace_html = storage.workspace[aide_file.aide_id]
        published_html = storage.published["match-test"]

        workspace_parsed = parse_aide_html(workspace_html)
        published_parsed = parse_aide_html(published_html)

        assert json.dumps(workspace_parsed.snapshot, sort_keys=True) == json.dumps(
            published_parsed.snapshot, sort_keys=True
        )


class TestPublishSlugGeneration:
    """
    Verify slug generation when not provided.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_auto_generated_slug(self, assembly, storage):
        """Without slug, a random one is generated."""
        aide_file = await assembly.create(make_blueprint())
        url = await assembly.publish(aide_file)

        # URL should have a slug part
        slug = url.replace("https://toaide.com/p/", "")
        assert len(slug) > 0

        # Should be in published storage
        assert slug in storage.published

    @pytest.mark.asyncio
    async def test_unique_auto_slugs(self, assembly, storage):
        """Multiple publishes get unique slugs."""
        aide_file = await assembly.create(make_blueprint())

        urls = set()
        for _ in range(5):
            url = await assembly.publish(aide_file)
            urls.add(url)

        assert len(urls) == 5
