"""
AIde Assembly -- Create Empty Tests (Category 4)

Create a new aide, verify the HTML is valid, the snapshot is empty state,
the blueprint is embedded.

From the spec (aide_assembly_spec.md, "Testing Strategy"):
  "4. Create empty. Create a new aide, verify the HTML is valid, the
   snapshot is empty state, the blueprint is embedded."

This verifies:
  - create() produces valid HTML
  - Snapshot matches empty_state from reducer
  - Blueprint is correctly embedded
  - AideFile fields are properly initialized

Reference: aide_assembly_spec.md (create operation, Testing Strategy)
"""

import pytest

from engine.kernel.assembly import AideAssembly, MemoryStorage, parse_aide_html
from engine.kernel.reducer import empty_state
from engine.kernel.types import Blueprint

# ============================================================================
# Create empty aide
# ============================================================================


class TestCreateEmpty:
    """
    Verify create() produces a valid empty aide.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_create_returns_aide_file(self, assembly):
        """create() returns an AideFile with all required fields."""
        bp = Blueprint(identity="A test aide.", voice="Direct.")
        aide_file = await assembly.create(bp)

        assert aide_file.aide_id is not None
        assert len(aide_file.aide_id) > 0
        assert aide_file.snapshot is not None
        assert aide_file.events == []
        assert aide_file.blueprint is not None
        assert aide_file.html is not None
        assert aide_file.last_sequence == 0
        assert aide_file.size_bytes > 0
        assert aide_file.loaded_from == "new"

    @pytest.mark.asyncio
    async def test_create_unique_ids(self, assembly):
        """Each create() produces a unique aide_id."""
        bp = Blueprint(identity="Test")
        ids = set()

        for _ in range(10):
            aide_file = await assembly.create(bp)
            ids.add(aide_file.aide_id)

        assert len(ids) == 10  # All unique


class TestCreateHTML:
    """
    Verify the HTML produced by create() is valid.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_html_has_doctype(self, assembly):
        """Created HTML starts with DOCTYPE."""
        bp = Blueprint(identity="Test")
        aide_file = await assembly.create(bp)

        assert aide_file.html.strip().lower().startswith("<!doctype html>")

    @pytest.mark.asyncio
    async def test_html_has_structure(self, assembly):
        """Created HTML has html, head, body tags."""
        bp = Blueprint(identity="Test")
        aide_file = await assembly.create(bp)

        assert "<html" in aide_file.html
        assert "</html>" in aide_file.html
        assert "<head>" in aide_file.html
        assert "</head>" in aide_file.html
        assert "<body>" in aide_file.html
        assert "</body>" in aide_file.html

    @pytest.mark.asyncio
    async def test_html_has_main(self, assembly):
        """Created HTML has main element with aide-page class."""
        bp = Blueprint(identity="Test")
        aide_file = await assembly.create(bp)

        assert '<main class="aide-page">' in aide_file.html

    @pytest.mark.asyncio
    async def test_html_has_embedded_json(self, assembly):
        """Created HTML has embedded JSON script tags."""
        bp = Blueprint(identity="Test")
        aide_file = await assembly.create(bp)

        assert 'id="aide-blueprint"' in aide_file.html
        assert 'id="aide-state"' in aide_file.html

    @pytest.mark.asyncio
    async def test_html_is_parseable(self, assembly):
        """Created HTML can be parsed back without errors."""
        bp = Blueprint(identity="Test")
        aide_file = await assembly.create(bp)

        parsed = parse_aide_html(aide_file.html)
        assert parsed.parse_errors == []


class TestCreateSnapshot:
    """
    Verify the snapshot in a created aide matches empty_state.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_snapshot_has_version(self, assembly):
        """Created snapshot has version field."""
        bp = Blueprint(identity="Test")
        aide_file = await assembly.create(bp)

        assert "version" in aide_file.snapshot
        assert aide_file.snapshot["version"] == 1

    @pytest.mark.asyncio
    async def test_snapshot_has_empty_collections(self, assembly):
        """Created snapshot has empty collections dict."""
        bp = Blueprint(identity="Test")
        aide_file = await assembly.create(bp)

        assert "collections" in aide_file.snapshot
        assert aide_file.snapshot["collections"] == {}

    @pytest.mark.asyncio
    async def test_snapshot_has_empty_blocks(self, assembly):
        """Created snapshot has block_root with empty children."""
        bp = Blueprint(identity="Test")
        aide_file = await assembly.create(bp)

        assert "blocks" in aide_file.snapshot
        assert "block_root" in aide_file.snapshot["blocks"]
        assert aide_file.snapshot["blocks"]["block_root"]["children"] == []

    @pytest.mark.asyncio
    async def test_snapshot_has_empty_views(self, assembly):
        """Created snapshot has empty views dict."""
        bp = Blueprint(identity="Test")
        aide_file = await assembly.create(bp)

        assert "views" in aide_file.snapshot
        assert aide_file.snapshot["views"] == {}

    @pytest.mark.asyncio
    async def test_snapshot_matches_empty_state(self, assembly):
        """Created snapshot structure matches empty_state() from reducer."""
        bp = Blueprint(identity="Test")
        aide_file = await assembly.create(bp)

        expected = empty_state()
        # Title may be set from identity, so compare structure
        assert set(aide_file.snapshot.keys()) == set(expected.keys())


class TestCreateBlueprint:
    """
    Verify the blueprint is correctly embedded in created aide.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_blueprint_identity_embedded(self, assembly):
        """Blueprint identity is embedded in HTML."""
        bp = Blueprint(identity="A unique test identity for verification.")
        aide_file = await assembly.create(bp)

        parsed = parse_aide_html(aide_file.html)
        assert parsed.blueprint.identity == bp.identity

    @pytest.mark.asyncio
    async def test_blueprint_voice_embedded(self, assembly):
        """Blueprint voice is embedded in HTML."""
        bp = Blueprint(identity="Test", voice="Very specific voice rules here.")
        aide_file = await assembly.create(bp)

        parsed = parse_aide_html(aide_file.html)
        assert parsed.blueprint.voice == bp.voice

    @pytest.mark.asyncio
    async def test_blueprint_prompt_embedded(self, assembly):
        """Blueprint prompt is embedded in HTML."""
        bp = Blueprint(identity="Test", prompt="A custom prompt for the aide.")
        aide_file = await assembly.create(bp)

        parsed = parse_aide_html(aide_file.html)
        assert parsed.blueprint.prompt == bp.prompt

    @pytest.mark.asyncio
    async def test_blueprint_stored_in_aide_file(self, assembly):
        """Blueprint is stored in AideFile object."""
        bp = Blueprint(identity="Test", voice="Voice", prompt="Prompt")
        aide_file = await assembly.create(bp)

        assert aide_file.blueprint.identity == bp.identity
        assert aide_file.blueprint.voice == bp.voice
        assert aide_file.blueprint.prompt == bp.prompt


class TestCreateTitle:
    """
    Verify title is derived from blueprint identity.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_title_from_first_sentence(self, assembly):
        """Title is first sentence of identity."""
        bp = Blueprint(identity="My Grocery List. Tracks family groceries.")
        aide_file = await assembly.create(bp)

        assert aide_file.snapshot["meta"]["title"] == "My Grocery List"

    @pytest.mark.asyncio
    async def test_title_truncated(self, assembly):
        """Long identity first sentence is truncated for title."""
        long_identity = "A" * 200 + ". More text."
        bp = Blueprint(identity=long_identity)
        aide_file = await assembly.create(bp)

        assert len(aide_file.snapshot["meta"]["title"]) <= 100

    @pytest.mark.asyncio
    async def test_empty_identity_no_title(self, assembly):
        """Empty identity results in no title being set."""
        bp = Blueprint(identity="")
        aide_file = await assembly.create(bp)

        # With empty identity, no title is set (meta stays empty)
        assert aide_file.snapshot["meta"] == {} or aide_file.snapshot["meta"].get("title", "") == ""


class TestCreateDoesNotSave:
    """
    Verify create() does NOT automatically save to storage.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_create_does_not_persist(self, assembly, storage):
        """create() does not write to storage automatically."""
        bp = Blueprint(identity="Test")
        aide_file = await assembly.create(bp)

        # Storage should be empty
        assert len(storage.workspace) == 0
        assert aide_file.aide_id not in storage.workspace

    @pytest.mark.asyncio
    async def test_explicit_save_required(self, assembly, storage):
        """Explicit save() is required to persist."""
        bp = Blueprint(identity="Test")
        aide_file = await assembly.create(bp)

        await assembly.save(aide_file)

        assert aide_file.aide_id in storage.workspace


class TestCreateEmptyPage:
    """
    Verify the empty page renders correctly.
    """

    @pytest.fixture
    def storage(self):
        return MemoryStorage()

    @pytest.fixture
    def assembly(self, storage):
        return AideAssembly(storage)

    @pytest.mark.asyncio
    async def test_empty_page_message(self, assembly):
        """Empty aide shows 'This page is empty.' message."""
        bp = Blueprint(identity="Test")
        aide_file = await assembly.create(bp)

        assert "aide-empty" in aide_file.html
        assert "This page is empty" in aide_file.html

    @pytest.mark.asyncio
    async def test_no_collection_html(self, assembly):
        """Empty aide has no collection/table/list HTML in main."""
        import re

        bp = Blueprint(identity="Test")
        aide_file = await assembly.create(bp)

        # Extract main content
        main_match = re.search(r'<main[^>]*>(.*?)</main>', aide_file.html, re.DOTALL)
        main = main_match.group(1) if main_match else ""

        assert "aide-table" not in main
        assert "aide-list" not in main
