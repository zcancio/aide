"""Tests for L2/L3 orchestrator."""

from unittest.mock import AsyncMock, patch

import pytest

from backend.services.orchestrator import orchestrator


@pytest.fixture
def mock_aide():
    """Mock aide from database."""
    return {
        "id": "aide_123",
        "user_id": "user_abc",
        "title": "Test Aide",
        "state": {
            "collections": {},
            "entities": {},
            "blocks": [],
            "views": {},
            "styles": {},
            "meta": {},
            "relationships": [],
        },
    }


@pytest.fixture
def mock_conversation():
    """Mock conversation from database."""
    return {
        "id": "conv_123",
        "aide_id": "aide_123",
        "messages": [],
    }


@pytest.fixture
def mock_grocery_aide():
    """Mock aide with grocery list schema."""
    return {
        "id": "aide_456",
        "user_id": "user_abc",
        "title": "Grocery List",
        "state": {
            "collections": {
                "grocery_list": {
                    "id": "grocery_list",
                    "name": "Grocery List",
                    "schema": {
                        "name": "string",
                        "checked": "bool",
                        "store": "string?",
                    },
                }
            },
            "entities": {
                "grocery_list/item_milk": {
                    "id": "item_milk",
                    "collection": "grocery_list",
                    "fields": {
                        "name": "Milk",
                        "checked": False,
                        "store": "Whole Foods",
                    },
                },
                "grocery_list/item_eggs": {
                    "id": "item_eggs",
                    "collection": "grocery_list",
                    "fields": {
                        "name": "Eggs",
                        "checked": False,
                        "store": "Whole Foods",
                    },
                },
            },
            "blocks": [],
            "views": {},
            "styles": {},
            "meta": {"title": "Grocery List"},
            "relationships": [],
        },
    }


class TestL3Synthesis:
    """Test L3 (Sonnet) schema synthesis."""

    @pytest.mark.asyncio
    async def test_first_message_creates_schema(self, mock_aide, mock_conversation):
        """L3 creates schema from first message."""
        with (
            patch("backend.services.orchestrator.aide_repo") as mock_aide_repo,
            patch("backend.services.orchestrator.conversation_repo") as mock_conv_repo,
            patch("backend.services.orchestrator.l3_synthesizer") as mock_l3,
            patch("backend.services.orchestrator.r2_service") as mock_r2,
        ):
            mock_aide_repo.get = AsyncMock(return_value=mock_aide)
            mock_aide_repo.update_state = AsyncMock()
            mock_conv_repo.get_or_create = AsyncMock(return_value=mock_conversation)
            mock_conv_repo.add_message = AsyncMock()
            mock_r2.upload_html = AsyncMock(return_value="aide_123/index.html")

            # L3 returns primitives to create grocery list
            mock_l3.synthesize = AsyncMock(
                return_value={
                    "primitives": [
                        {
                            "type": "collection.create",
                            "payload": {
                                "id": "grocery_list",
                                "name": "Grocery List",
                                "schema": {
                                    "name": "string",
                                    "checked": "bool",
                                },
                            },
                        },
                        {
                            "type": "entity.create",
                            "payload": {
                                "collection": "grocery_list",
                                "id": "item_milk",
                                "fields": {"name": "Milk", "checked": False},
                            },
                        },
                        {
                            "type": "meta.set_title",
                            "payload": {"title": "Grocery List"},
                        },
                    ],
                    "response": "Milk added.",
                }
            )

            result = await orchestrator.process_message(
                aide_id="aide_123",
                user_id="user_abc",
                message="we need milk",
                source="web",
            )

            # Verify L3 was called (not L2)
            mock_l3.synthesize.assert_called_once()

            # Verify primitives were applied
            assert result["primitives_count"] == 3
            assert result["response"] == "Milk added."

            # Verify state was saved
            mock_aide_repo.update_state.assert_called_once()
            saved_state = mock_aide_repo.update_state.call_args[0][2]
            assert "grocery_list" in saved_state["collections"]
            assert "grocery_list/item_milk" in saved_state["entities"]

    @pytest.mark.asyncio
    async def test_image_input_routes_to_l3(self, mock_aide, mock_conversation):
        """Image input routes to L3 (vision-capable model)."""
        with (
            patch("backend.services.orchestrator.aide_repo") as mock_aide_repo,
            patch("backend.services.orchestrator.conversation_repo") as mock_conv_repo,
            patch("backend.services.orchestrator.l3_synthesizer") as mock_l3,
            patch("backend.services.orchestrator.r2_service") as mock_r2,
        ):
            mock_aide_repo.get = AsyncMock(return_value=mock_aide)
            mock_aide_repo.update_state = AsyncMock()
            mock_conv_repo.get_or_create = AsyncMock(return_value=mock_conversation)
            mock_conv_repo.add_message = AsyncMock()
            mock_r2.upload_html = AsyncMock(return_value="aide_123/index.html")

            mock_l3.synthesize = AsyncMock(return_value={"primitives": [], "response": "Receipt processed."})

            image_bytes = b"fake_image_data"

            await orchestrator.process_message(
                aide_id="aide_123",
                user_id="user_abc",
                message="process this receipt",
                source="web",
                image_data=image_bytes,
            )

            # Verify L3 was called with image
            mock_l3.synthesize.assert_called_once()
            call_args = mock_l3.synthesize.call_args
            assert call_args[1]["image_data"] == image_bytes


class TestL2Compilation:
    """Test L2 (Haiku) intent compilation."""

    @pytest.mark.asyncio
    async def test_routine_update_uses_l2(self, mock_grocery_aide, mock_conversation):
        """Routine update uses L2 (Haiku)."""
        with (
            patch("backend.services.orchestrator.aide_repo") as mock_aide_repo,
            patch("backend.services.orchestrator.conversation_repo") as mock_conv_repo,
            patch("backend.services.orchestrator.l2_compiler") as mock_l2,
            patch("backend.services.orchestrator.r2_service") as mock_r2,
        ):
            mock_aide_repo.get = AsyncMock(return_value=mock_grocery_aide)
            mock_aide_repo.update_state = AsyncMock()
            mock_conv_repo.get_or_create = AsyncMock(return_value=mock_conversation)
            mock_conv_repo.add_message = AsyncMock()
            mock_r2.upload_html = AsyncMock(return_value="aide_456/index.html")

            # L2 returns primitive to check off milk
            mock_l2.compile = AsyncMock(
                return_value={
                    "primitives": [
                        {
                            "type": "entity.update",
                            "payload": {
                                "ref": "grocery_list/item_milk",
                                "fields": {"checked": True},
                            },
                        }
                    ],
                    "response": "Milk: done.",
                    "escalate": False,
                }
            )

            result = await orchestrator.process_message(
                aide_id="aide_456",
                user_id="user_abc",
                message="got the milk",
                source="web",
            )

            # Verify L2 was called
            mock_l2.compile.assert_called_once()

            # Verify primitive was applied
            assert result["primitives_count"] == 1
            assert result["response"] == "Milk: done."

            # Verify state was updated
            mock_aide_repo.update_state.assert_called_once()
            saved_state = mock_aide_repo.update_state.call_args[0][2]
            assert saved_state["entities"]["grocery_list/item_milk"]["fields"]["checked"] is True

    @pytest.mark.asyncio
    async def test_l2_escalates_to_l3_when_needed(self, mock_grocery_aide, mock_conversation):
        """L2 escalates to L3 when field doesn't exist."""
        with (
            patch("backend.services.orchestrator.aide_repo") as mock_aide_repo,
            patch("backend.services.orchestrator.conversation_repo") as mock_conv_repo,
            patch("backend.services.orchestrator.l2_compiler") as mock_l2,
            patch("backend.services.orchestrator.l3_synthesizer") as mock_l3,
            patch("backend.services.orchestrator.r2_service") as mock_r2,
        ):
            mock_aide_repo.get = AsyncMock(return_value=mock_grocery_aide)
            mock_aide_repo.update_state = AsyncMock()
            mock_conv_repo.get_or_create = AsyncMock(return_value=mock_conversation)
            mock_conv_repo.add_message = AsyncMock()
            mock_r2.upload_html = AsyncMock(return_value="aide_456/index.html")

            # L2 signals escalation
            mock_l2.compile = AsyncMock(
                return_value={
                    "primitives": [],
                    "response": "",
                    "escalate": True,
                }
            )

            # L3 adds price field
            mock_l3.synthesize = AsyncMock(
                return_value={
                    "primitives": [
                        {
                            "type": "field.add",
                            "payload": {
                                "collection": "grocery_list",
                                "field": "price",
                                "type": "float?",
                                "default": None,
                            },
                        }
                    ],
                    "response": "",
                }
            )

            result = await orchestrator.process_message(
                aide_id="aide_456",
                user_id="user_abc",
                message="track price for each item",
                source="web",
            )

            # Verify L2 was called first
            mock_l2.compile.assert_called_once()

            # Verify L3 was called after escalation
            mock_l3.synthesize.assert_called_once()

            # Verify field was added
            assert result["primitives_count"] == 1

    @pytest.mark.asyncio
    async def test_multi_entity_update(self, mock_grocery_aide, mock_conversation):
        """L2 handles multi-entity updates."""
        with (
            patch("backend.services.orchestrator.aide_repo") as mock_aide_repo,
            patch("backend.services.orchestrator.conversation_repo") as mock_conv_repo,
            patch("backend.services.orchestrator.l2_compiler") as mock_l2,
            patch("backend.services.orchestrator.r2_service") as mock_r2,
        ):
            mock_aide_repo.get = AsyncMock(return_value=mock_grocery_aide)
            mock_aide_repo.update_state = AsyncMock()
            mock_conv_repo.get_or_create = AsyncMock(return_value=mock_conversation)
            mock_conv_repo.add_message = AsyncMock()
            mock_r2.upload_html = AsyncMock(return_value="aide_456/index.html")

            # L2 returns multiple primitives
            mock_l2.compile = AsyncMock(
                return_value={
                    "primitives": [
                        {
                            "type": "entity.update",
                            "payload": {
                                "ref": "grocery_list/item_milk",
                                "fields": {"checked": True},
                            },
                        },
                        {
                            "type": "entity.update",
                            "payload": {
                                "ref": "grocery_list/item_eggs",
                                "fields": {"checked": True},
                            },
                        },
                    ],
                    "response": "Milk, eggs: done.",
                    "escalate": False,
                }
            )

            result = await orchestrator.process_message(
                aide_id="aide_456",
                user_id="user_abc",
                message="got milk and eggs",
                source="web",
            )

            # Verify both primitives were applied
            assert result["primitives_count"] == 2
            assert result["response"] == "Milk, eggs: done."


class TestOrchestrationFlow:
    """Test full orchestration flow."""

    @pytest.mark.asyncio
    async def test_full_flow_with_rendering(self, mock_grocery_aide, mock_conversation):
        """Full flow: message → primitives → state → render → R2."""
        with (
            patch("backend.services.orchestrator.aide_repo") as mock_aide_repo,
            patch("backend.services.orchestrator.conversation_repo") as mock_conv_repo,
            patch("backend.services.orchestrator.l2_compiler") as mock_l2,
            patch("backend.services.orchestrator.r2_service") as mock_r2,
        ):
            mock_aide_repo.get = AsyncMock(return_value=mock_grocery_aide)
            mock_aide_repo.update_state = AsyncMock()
            mock_conv_repo.get_or_create = AsyncMock(return_value=mock_conversation)
            mock_conv_repo.add_message = AsyncMock()
            mock_r2.upload_html = AsyncMock(return_value="aide_456/index.html")

            mock_l2.compile = AsyncMock(
                return_value={
                    "primitives": [
                        {
                            "type": "entity.create",
                            "payload": {
                                "collection": "grocery_list",
                                "id": "item_bread",
                                "fields": {"name": "Bread", "checked": False},
                            },
                        }
                    ],
                    "response": "Bread added.",
                    "escalate": False,
                }
            )

            result = await orchestrator.process_message(
                aide_id="aide_456",
                user_id="user_abc",
                message="add bread",
                source="web",
            )

            # Verify state was saved
            mock_aide_repo.update_state.assert_called_once()
            saved_state = mock_aide_repo.update_state.call_args[0][2]
            assert "grocery_list/item_bread" in saved_state["entities"]

            # Verify HTML was uploaded to R2
            mock_r2.upload_html.assert_called_once()
            uploaded_html = mock_r2.upload_html.call_args[0][1]
            assert "<!DOCTYPE html>" in uploaded_html
            assert "Bread" in uploaded_html or "bread" in uploaded_html.lower()

            # Verify conversation messages were saved
            assert mock_conv_repo.add_message.call_count == 2  # user + assistant

            # Verify result
            assert result["response"] == "Bread added."
            assert result["html_url"] == "https://r2.toaide.com/aide_456/index.html"
            assert result["primitives_count"] == 1

    @pytest.mark.asyncio
    async def test_question_no_state_change(self, mock_grocery_aide, mock_conversation):
        """Questions don't mutate state."""
        with (
            patch("backend.services.orchestrator.aide_repo") as mock_aide_repo,
            patch("backend.services.orchestrator.conversation_repo") as mock_conv_repo,
            patch("backend.services.orchestrator.l2_compiler") as mock_l2,
            patch("backend.services.orchestrator.r2_service") as mock_r2,
        ):
            mock_aide_repo.get = AsyncMock(return_value=mock_grocery_aide)
            mock_aide_repo.update_state = AsyncMock()
            mock_conv_repo.get_or_create = AsyncMock(return_value=mock_conversation)
            mock_conv_repo.add_message = AsyncMock()
            mock_r2.upload_html = AsyncMock(return_value="aide_456/index.html")

            # L2 returns no primitives for question
            mock_l2.compile = AsyncMock(
                return_value={
                    "primitives": [],
                    "response": "Milk, eggs.",
                    "escalate": False,
                }
            )

            result = await orchestrator.process_message(
                aide_id="aide_456",
                user_id="user_abc",
                message="what's on the list?",
                source="web",
            )

            # Verify no primitives were applied
            assert result["primitives_count"] == 0
            assert result["response"] == "Milk, eggs."

            # State should still be saved (even if unchanged)
            mock_aide_repo.update_state.assert_called_once()
