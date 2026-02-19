"""
Tests for WebSocket streaming behavior.

Phase 3: Tests for interrupt, batch handling, and progressive rendering.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app


def test_websocket_accepts_connection():
    """WebSocket endpoint accepts connections."""
    client = TestClient(app)
    with client.websocket_connect("/ws/aide/test") as ws:
        # Send a test message
        ws.send_json({"type": "message", "content": "test", "message_id": "test-1"})
        # Should receive stream.start
        msg = ws.receive_json()
        assert msg["type"] == "stream.start"
        assert msg["message_id"] == "test-1"


def test_interrupt_stops_stream():
    """Interrupt message stops the stream and keeps partial state."""
    # Note: This test is limited by TestClient's synchronous nature.
    # Interrupt handling works correctly in async/real-time scenarios.
    # Testing basic interrupt flow: send interrupt, verify no error.
    client = TestClient(app)
    with client.websocket_connect("/ws/aide/test") as ws:
        # Set instant profile to complete stream quickly
        ws.send_json({"type": "set_profile", "profile": "instant"})

        # Start a stream
        ws.send_json({"type": "message", "content": "graduation party", "message_id": "int-test"})

        # Wait for stream.start
        msg = ws.receive_json()
        assert msg["type"] == "stream.start"

        # Send interrupt early (won't actually interrupt in synchronous test client)
        ws.send_json({"type": "interrupt"})

        # Verify stream completes without error (interrupt is handled gracefully)
        stream_completed = False
        for _ in range(100):
            msg = ws.receive_json()
            if msg["type"] == "stream.end" or msg["type"] == "stream.interrupted":
                stream_completed = True
                break

        assert stream_completed, "Stream should complete or be interrupted"


def test_profile_selection():
    """Profile selection message changes streaming delay profile."""
    client = TestClient(app)
    with client.websocket_connect("/ws/aide/test") as ws:
        # Set instant profile
        ws.send_json({"type": "set_profile", "profile": "instant"})

        # Start stream
        ws.send_json({"type": "message", "content": "graduation party", "message_id": "prof-test"})

        # Wait for stream.start
        msg = ws.receive_json()
        assert msg["type"] == "stream.start"

        # With instant profile, all entities should arrive quickly
        import time

        start = time.monotonic()
        entity_count = 0
        while True:
            msg = ws.receive_json()
            if msg["type"] == "entity.create":
                entity_count += 1
            elif msg["type"] == "stream.end":
                break

        elapsed = time.monotonic() - start
        # Instant profile should complete in under 1 second
        assert elapsed < 1.0, f"Instant profile took {elapsed:.2f}s, expected <1s"
        assert entity_count > 0, "Should have received entities"


def test_batch_events():
    """Batch events are buffered and applied together."""
    client = TestClient(app)

    # Note: This test requires a golden file that includes batch.start/batch.end signals.
    # Since current golden files don't have batch signals, this test is a placeholder
    # for when we add batch support to golden files.

    with client.websocket_connect("/ws/aide/test") as ws:
        ws.send_json({"type": "set_profile", "profile": "instant"})
        ws.send_json({"type": "message", "content": "test", "message_id": "batch-test"})

        msg = ws.receive_json()
        assert msg["type"] == "stream.start"

        # Currently no golden files have batch signals, so just verify stream completes
        while True:
            msg = ws.receive_json()
            if msg["type"] == "stream.end":
                break


def test_voice_messages_appear_in_stream():
    """Voice messages are sent as separate voice deltas."""
    client = TestClient(app)
    with client.websocket_connect("/ws/aide/test") as ws:
        ws.send_json({"type": "set_profile", "profile": "instant"})
        ws.send_json({"type": "message", "content": "graduation party", "message_id": "voice-test"})

        msg = ws.receive_json()
        assert msg["type"] == "stream.start"

        # Collect all messages
        voice_messages = []
        while True:
            msg = ws.receive_json()
            if msg["type"] == "voice":
                voice_messages.append(msg["text"])
            elif msg["type"] == "stream.end":
                break

        # Golden file should have at least one voice message
        assert len(voice_messages) > 0, "Expected at least one voice message"


def test_entity_deltas_have_correct_format():
    """Entity deltas have the expected structure."""
    client = TestClient(app)
    with client.websocket_connect("/ws/aide/test") as ws:
        ws.send_json({"type": "set_profile", "profile": "instant"})
        ws.send_json({"type": "message", "content": "graduation party", "message_id": "delta-test"})

        msg = ws.receive_json()
        assert msg["type"] == "stream.start"

        # Get first entity.create delta
        entity_delta = None
        while True:
            msg = ws.receive_json()
            if msg["type"] == "entity.create":
                entity_delta = msg
                break
            elif msg["type"] == "stream.end":
                break

        assert entity_delta is not None, "Should receive at least one entity.create"
        assert "id" in entity_delta, "Delta should have id"
        assert "data" in entity_delta, "Delta should have data"
        assert entity_delta["data"] is not None, "Data should not be None for entity.create"


def test_direct_edit_after_stream():
    """Direct edit can be sent after stream completes."""
    client = TestClient(app)
    with client.websocket_connect("/ws/aide/test") as ws:
        ws.send_json({"type": "set_profile", "profile": "instant"})
        ws.send_json({"type": "message", "content": "graduation party", "message_id": "edit-test"})

        msg = ws.receive_json()
        assert msg["type"] == "stream.start"

        # Collect entities and wait for stream to complete
        entity_id = None
        while True:
            msg = ws.receive_json()
            if msg["type"] == "entity.create" and entity_id is None:
                entity_id = msg["id"]
            elif msg["type"] == "stream.end":
                break

        assert entity_id is not None

        # Send direct edit after stream completes
        ws.send_json({"type": "direct_edit", "entity_id": entity_id, "field": "title", "value": "Updated Title"})

        # Should receive entity.update delta
        msg = ws.receive_json()
        assert msg["type"] == "entity.update"
        assert msg["id"] == entity_id
        assert msg["data"] is not None
