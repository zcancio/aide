"""
Integration tests for the WebSocket aide endpoint.

Tests /ws/aide/{aide_id} — message input, delta streaming, stream status.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client():
    """Return a synchronous TestClient for WS testing."""
    return TestClient(app)


class TestWebSocketConnect:
    def test_websocket_accepts_connection(self, client):
        with client.websocket_connect("/ws/aide/test-aide-id"):
            # Simply connecting should work
            pass

    def test_websocket_accepts_any_aide_id(self, client):
        with client.websocket_connect("/ws/aide/some-random-id"):
            pass


class TestWebSocketMessageFlow:
    def test_message_yields_stream_start(self, client):
        with client.websocket_connect("/ws/aide/test-aide-id") as ws:
            ws.send_text(
                json.dumps(
                    {
                        "type": "message",
                        "content": "plan a graduation party",
                        "message_id": "test-msg-1",
                    }
                )
            )
            first = json.loads(ws.receive_text())
            assert first["type"] == "stream.start"
            assert first["message_id"] == "test-msg-1"

    def test_message_yields_stream_end(self, client):
        with client.websocket_connect("/ws/aide/test-aide-id") as ws:
            ws.send_text(
                json.dumps(
                    {
                        "type": "message",
                        "content": "plan a graduation party",
                        "message_id": "msg-end-test",
                    }
                )
            )
            # Drain all messages until stream.end
            messages = []
            for _ in range(100):
                msg = json.loads(ws.receive_text())
                messages.append(msg)
                if msg["type"] == "stream.end":
                    break
            else:
                pytest.fail("stream.end never received")

            end_msg = messages[-1]
            assert end_msg["type"] == "stream.end"
            assert end_msg["message_id"] == "msg-end-test"

    def test_message_yields_entity_create_deltas(self, client):
        with client.websocket_connect("/ws/aide/test-aide-id") as ws:
            ws.send_text(
                json.dumps(
                    {
                        "type": "message",
                        "content": "plan a graduation party",
                        "message_id": "delta-test",
                    }
                )
            )
            messages = []
            for _ in range(100):
                msg = json.loads(ws.receive_text())
                messages.append(msg)
                if msg["type"] == "stream.end":
                    break

            entity_creates = [m for m in messages if m["type"] == "entity.create"]
            assert len(entity_creates) >= 1, "Expected at least one entity.create delta"

    def test_entity_deltas_have_required_fields(self, client):
        with client.websocket_connect("/ws/aide/test-aide-id") as ws:
            ws.send_text(
                json.dumps(
                    {
                        "type": "message",
                        "content": "plan a graduation party",
                        "message_id": "fields-test",
                    }
                )
            )
            messages = []
            for _ in range(100):
                msg = json.loads(ws.receive_text())
                messages.append(msg)
                if msg["type"] == "stream.end":
                    break

            entity_deltas = [m for m in messages if m["type"] in ("entity.create", "entity.update", "entity.remove")]
            for delta in entity_deltas:
                assert "type" in delta
                assert "id" in delta
                assert "data" in delta

    def test_voice_deltas_delivered(self, client):
        with client.websocket_connect("/ws/aide/test-aide-id") as ws:
            ws.send_text(
                json.dumps(
                    {
                        "type": "message",
                        "content": "plan a graduation party",
                        "message_id": "voice-test",
                    }
                )
            )
            messages = []
            for _ in range(100):
                msg = json.loads(ws.receive_text())
                messages.append(msg)
                if msg["type"] == "stream.end":
                    break

            voice_deltas = [m for m in messages if m["type"] == "voice"]
            # The graduation golden file has voice events
            assert len(voice_deltas) >= 1, "Expected at least one voice delta"
            for v in voice_deltas:
                assert "text" in v
                assert isinstance(v["text"], str)

    def test_auto_generated_message_id(self, client):
        with client.websocket_connect("/ws/aide/test-aide-id") as ws:
            # No message_id in the request
            ws.send_text(json.dumps({"type": "message", "content": "test message"}))
            first = json.loads(ws.receive_text())
            assert first["type"] == "stream.start"
            # Should have generated a message_id
            assert "message_id" in first
            assert first["message_id"]


class TestWebSocketEdgeCases:
    def test_malformed_json_from_client_ignored(self, client):
        with client.websocket_connect("/ws/aide/test-aide-id") as ws:
            # Send malformed JSON — server should not crash
            ws.send_text("not valid json")
            # Then send a valid message
            ws.send_text(json.dumps({"type": "message", "content": "test", "message_id": "after-bad"}))
            first = json.loads(ws.receive_text())
            assert first["type"] == "stream.start"

    def test_wrong_message_type_ignored(self, client):
        with client.websocket_connect("/ws/aide/test-aide-id") as ws:
            # Send an unknown message type — server should not process it
            ws.send_text(json.dumps({"type": "ping"}))
            # Then send a real message
            ws.send_text(json.dumps({"type": "message", "content": "test", "message_id": "after-ping"}))
            first = json.loads(ws.receive_text())
            assert first["type"] == "stream.start"

    def test_scenario_selection_graduation(self, client):
        """Graduation keyword routes to create_graduation golden file."""
        with client.websocket_connect("/ws/aide/test") as ws:
            ws.send_text(json.dumps({"type": "message", "content": "graduation party", "message_id": "grad"}))
            messages = []
            for _ in range(100):
                msg = json.loads(ws.receive_text())
                messages.append(msg)
                if msg["type"] == "stream.end":
                    break
            entity_creates = [m for m in messages if m["type"] == "entity.create"]
            assert len(entity_creates) >= 1

    def test_scenario_selection_default(self, client):
        """Unknown content defaults to create_graduation."""
        with client.websocket_connect("/ws/aide/test") as ws:
            ws.send_text(json.dumps({"type": "message", "content": "random stuff", "message_id": "default"}))
            messages = []
            for _ in range(100):
                msg = json.loads(ws.receive_text())
                messages.append(msg)
                if msg["type"] == "stream.end":
                    break
            types = {m["type"] for m in messages}
            assert "stream.end" in types
