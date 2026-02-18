"""Tests for FlightRecorder and FlightRecorderUploader."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.flight_recorder import FlightRecorder, TurnRecord
from backend.services.flight_recorder_uploader import FlightRecorderUploader


class TestFlightRecorder:
    """Unit tests for FlightRecorder."""

    def test_start_and_end_turn_produces_record(self):
        """start_turn + end_turn produces a valid TurnRecord."""
        recorder = FlightRecorder()
        recorder.start_turn(
            turn_id="turn_abc",
            aide_id="aide_123",
            user_id="user_456",
            source="web",
            user_message="got the milk",
            snapshot_before={"version": 1, "collections": {}},
        )

        record = recorder.end_turn(
            snapshot_after={"version": 1, "collections": {"grocery": {}}},
            primitives_emitted=[{"type": "entity.update", "payload": {}}],
            primitives_applied=1,
            response_text="Milk: done.",
        )

        assert isinstance(record, TurnRecord)
        assert record.turn_id == "turn_abc"
        assert record.aide_id == "aide_123"
        assert record.user_id == "user_456"
        assert record.source == "web"
        assert record.user_message == "got the milk"
        assert record.snapshot_before == {"version": 1, "collections": {}}
        assert "grocery" in record.snapshot_after["collections"]
        assert record.primitives_applied == 1
        assert record.response_text == "Milk: done."
        assert len(record.primitives_emitted) == 1
        assert record.total_latency_ms >= 0

    def test_record_llm_call_captured(self):
        """LLM call records are included in the TurnRecord."""
        recorder = FlightRecorder()
        recorder.start_turn(
            turn_id="turn_1",
            aide_id="aide_1",
            user_id="user_1",
            source="web",
            user_message="test",
            snapshot_before={},
        )

        recorder.record_llm_call(
            shadow=False,
            model="claude-3-5-haiku-20241022",
            tier="L2",
            prompt="user prompt",
            response='{"primitives": [], "response": "ok"}',
            usage={"input_tokens": 100, "output_tokens": 20},
            latency_ms=250,
            ttft_ms=50,
            error=None,
        )

        record = recorder.end_turn(
            snapshot_after={},
            primitives_emitted=[],
            primitives_applied=0,
            response_text="ok",
        )

        assert len(record.llm_calls) == 1
        call = record.llm_calls[0]
        assert call.shadow is False
        assert call.model == "claude-3-5-haiku-20241022"
        assert call.tier == "L2"
        assert call.usage == {"input_tokens": 100, "output_tokens": 20}
        assert call.latency_ms == 250
        assert call.ttft_ms == 50
        assert call.error is None

    def test_shadow_and_production_calls_both_recorded(self):
        """Both production and shadow calls are captured."""
        recorder = FlightRecorder()
        recorder.start_turn(
            turn_id="turn_2",
            aide_id="aide_2",
            user_id="user_2",
            source="web",
            user_message="test",
            snapshot_before={},
        )

        recorder.record_llm_call(
            shadow=False,
            model="claude-sonnet-4-20250514",
            tier="L2",
            prompt="prompt",
            response="production response",
            usage={"input_tokens": 500, "output_tokens": 100},
            latency_ms=450,
            ttft_ms=80,
        )
        recorder.record_llm_call(
            shadow=True,
            model="claude-3-5-haiku-20241022",
            tier="L2",
            prompt="prompt",
            response="shadow response",
            usage={"input_tokens": 500, "output_tokens": 95},
            latency_ms=380,
            ttft_ms=60,
        )

        record = recorder.end_turn(
            snapshot_after={},
            primitives_emitted=[],
            primitives_applied=0,
            response_text="",
        )

        assert len(record.llm_calls) == 2
        production_calls = [c for c in record.llm_calls if not c.shadow]
        shadow_calls = [c for c in record.llm_calls if c.shadow]
        assert len(production_calls) == 1
        assert len(shadow_calls) == 1
        assert shadow_calls[0].model == "claude-3-5-haiku-20241022"

    def test_failed_llm_call_recorded_with_error(self):
        """Failed LLM calls are recorded with error field set."""
        recorder = FlightRecorder()
        recorder.start_turn(
            turn_id="turn_3",
            aide_id="aide_3",
            user_id="user_3",
            source="web",
            user_message="test",
            snapshot_before={},
        )

        recorder.record_llm_call(
            shadow=True,
            model="claude-3-5-haiku-20241022",
            tier="L2",
            prompt="prompt",
            response="",
            usage={"input_tokens": 0, "output_tokens": 0},
            latency_ms=100,
            ttft_ms=0,
            error="APIConnectionError: timeout",
        )

        record = recorder.end_turn(
            snapshot_after={},
            primitives_emitted=[],
            primitives_applied=0,
            response_text="",
        )

        assert record.llm_calls[0].error == "APIConnectionError: timeout"

    def test_to_dict_serialization(self):
        """TurnRecord.to_dict() produces valid JSON-serializable dict."""
        recorder = FlightRecorder()
        recorder.start_turn(
            turn_id="turn_4",
            aide_id="aide_4",
            user_id="user_4",
            source="web",
            user_message="hello",
            snapshot_before={"key": "value"},
        )
        recorder.record_llm_call(
            shadow=False,
            model="claude-sonnet-4-20250514",
            tier="L3",
            prompt="p",
            response="r",
            usage={"input_tokens": 10, "output_tokens": 5},
            latency_ms=100,
            ttft_ms=30,
        )

        record = recorder.end_turn(
            snapshot_after={"key": "updated"},
            primitives_emitted=[{"type": "meta.update", "payload": {"title": "Test"}}],
            primitives_applied=1,
            response_text="Updated.",
        )

        d = record.to_dict()

        # Must be JSON-serializable
        serialized = json.dumps(d)
        parsed = json.loads(serialized)

        assert parsed["turn_id"] == "turn_4"
        assert parsed["aide_id"] == "aide_4"
        assert len(parsed["llm_calls"]) == 1
        assert parsed["llm_calls"][0]["tier"] == "L3"
        assert parsed["primitives_applied"] == 1

    def test_total_latency_is_measured(self):
        """total_latency_ms reflects elapsed time between start_turn and end_turn."""
        import time

        recorder = FlightRecorder()
        recorder.start_turn(
            turn_id="turn_5",
            aide_id="aide_5",
            user_id="user_5",
            source="web",
            user_message="test",
            snapshot_before={},
        )

        time.sleep(0.05)  # 50ms

        record = recorder.end_turn(
            snapshot_after={},
            primitives_emitted=[],
            primitives_applied=0,
            response_text="",
        )

        assert record.total_latency_ms >= 40  # at least 40ms


class TestFlightRecorderUploader:
    """Unit tests for FlightRecorderUploader."""

    def _make_record(self, aide_id: str = "aide_test") -> TurnRecord:
        """Create a minimal TurnRecord for testing."""
        recorder = FlightRecorder()
        recorder.start_turn(
            turn_id="turn_x",
            aide_id=aide_id,
            user_id="user_x",
            source="web",
            user_message="test",
            snapshot_before={},
        )
        return recorder.end_turn(
            snapshot_after={},
            primitives_emitted=[],
            primitives_applied=0,
            response_text="",
        )

    def test_enqueue_non_blocking(self):
        """enqueue() returns immediately without blocking."""
        uploader = FlightRecorderUploader()
        record = self._make_record()

        # Should not raise
        uploader.enqueue(record)
        assert uploader._queue.qsize() == 1

    def test_queue_overflow_drops_oldest(self):
        """When queue is full, oldest record is dropped."""
        from backend.services.flight_recorder_uploader import _MAX_QUEUE_SIZE

        uploader = FlightRecorderUploader()

        # Fill queue to capacity
        for i in range(_MAX_QUEUE_SIZE):
            r = self._make_record(aide_id=f"aide_{i:05d}")
            uploader._queue.put_nowait(r)

        # This should trigger overflow logic (drop oldest, add newest)
        newest = self._make_record(aide_id="aide_newest")
        uploader.enqueue(newest)

        # Queue should still be at max size
        assert uploader._queue.qsize() == _MAX_QUEUE_SIZE

        # Newest record should be in the queue
        records_in_queue = []
        while not uploader._queue.empty():
            records_in_queue.append(uploader._queue.get_nowait())

        aide_ids = [r.aide_id for r in records_in_queue]
        assert "aide_newest" in aide_ids

    @pytest.mark.asyncio
    async def test_flush_uploads_all_pending(self):
        """flush() uploads all records still in queue."""
        uploader = FlightRecorderUploader()

        # Add 3 records
        for i in range(3):
            uploader.enqueue(self._make_record(aide_id=f"aide_{i}"))

        with patch.object(uploader, "_upload_batch", new_callable=AsyncMock) as mock_upload:
            await uploader.flush()
            mock_upload.assert_called_once()
            batch = mock_upload.call_args[0][0]
            assert len(batch) == 3

    @pytest.mark.asyncio
    async def test_upload_batch_groups_by_aide(self):
        """_upload_batch groups records by aide_id for separate files."""
        uploader = FlightRecorderUploader()

        records = [
            self._make_record(aide_id="aide_A"),
            self._make_record(aide_id="aide_B"),
            self._make_record(aide_id="aide_A"),
        ]

        with patch.object(uploader, "_upload_aide_batch", new_callable=AsyncMock) as mock_upload:
            await uploader._upload_batch(records)

            # Should be called once per unique aide_id
            assert mock_upload.call_count == 2
            calls = {call[0][0]: call[0][1] for call in mock_upload.call_args_list}
            assert len(calls["aide_A"]) == 2
            assert len(calls["aide_B"]) == 1

    @pytest.mark.asyncio
    async def test_upload_aide_batch_retries_on_failure(self):
        """_upload_aide_batch retries once on R2 failure."""
        uploader = FlightRecorderUploader()
        records = [self._make_record()]

        call_count = 0

        async def fail_first_time(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("R2 timeout")

        with patch.object(uploader, "_put_r2", side_effect=fail_first_time):
            # Should not raise even on first failure
            await uploader._upload_aide_batch("aide_test", records)

        assert call_count == 2  # initial attempt + 1 retry

    @pytest.mark.asyncio
    async def test_upload_aide_batch_drops_after_two_failures(self):
        """_upload_aide_batch drops record after 2 failures (no exception raised)."""
        uploader = FlightRecorderUploader()
        records = [self._make_record()]

        with patch.object(uploader, "_put_r2", side_effect=ConnectionError("R2 down")):
            # Should not raise
            await uploader._upload_aide_batch("aide_test", records)

    @pytest.mark.asyncio
    async def test_serialization_error_skips_record(self):
        """Serialization errors skip the batch without raising."""
        uploader = FlightRecorderUploader()
        records = [self._make_record()]

        # Patch to_dict to raise
        with patch.object(records[0], "to_dict", side_effect=ValueError("serialize error")):
            # Should not raise
            await uploader._upload_aide_batch("aide_test", records)


class TestOrchestratorFlightRecorderIntegration:
    """Test that orchestrator correctly records flight data."""

    @pytest.fixture
    def mock_aide(self):
        """Mock aide with empty state."""
        return {
            "state": {
                "version": 1,
                "meta": {},
                "collections": {},
                "relationships": [],
                "relationship_types": {},
                "constraints": [],
                "blocks": {"block_root": {"type": "root", "children": []}},
                "views": {},
                "styles": {},
                "annotations": [],
            },
            "title": "Test",
            "event_log": [],
        }

    @pytest.mark.asyncio
    async def test_process_message_enqueues_turn_record(self, mock_aide):
        """process_message produces and enqueues a TurnRecord."""
        from backend.services.orchestrator import Orchestrator

        with (
            patch("backend.services.orchestrator.l3_synthesizer") as mock_l3,
            patch("backend.services.orchestrator.r2_service") as mock_r2,
            patch("backend.services.orchestrator.flight_recorder_uploader") as mock_uploader,
        ):
            orch = Orchestrator()
            orch.aide_repo = MagicMock()
            orch.conv_repo = MagicMock()

            mock_aide_obj = MagicMock()
            mock_aide_obj.state = mock_aide["state"]
            mock_aide_obj.title = mock_aide["title"]
            mock_aide_obj.event_log = []

            orch.aide_repo.get = AsyncMock(return_value=mock_aide_obj)
            orch.aide_repo.update_state = AsyncMock()

            mock_conv_obj = MagicMock()
            mock_conv_obj.id = "conv_1"
            mock_conv_obj.messages = []

            orch.conv_repo.get_for_aide = AsyncMock(return_value=mock_conv_obj)
            orch.conv_repo.append_message = AsyncMock()

            mock_r2.upload_html = AsyncMock()

            mock_l3.synthesize = AsyncMock(return_value={"primitives": [], "response": "Noted."})

            # Shadow call also uses l3_synthesizer.system_prompt and _build_user_message
            mock_l3.system_prompt = "system"
            mock_l3._build_user_message = MagicMock(return_value="prompt")

            # Patch ai_provider at source for shadow call (imported locally inside methods)
            with patch("backend.services.ai_provider.AIProvider.call_claude", new_callable=AsyncMock) as mock_call:
                mock_call.return_value = {
                    "content": '{"primitives":[],"response":""}',
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                    "timing": {"ttft_ms": 50, "total_ms": 200},
                }

                await orch.process_message(
                    user_id="user_abc",
                    aide_id="aide_123",
                    message="first message",
                    source="web",
                )

            # Verify enqueue was called with a TurnRecord
            mock_uploader.enqueue.assert_called_once()
            record = mock_uploader.enqueue.call_args[0][0]
            assert isinstance(record, TurnRecord)
            assert record.user_message == "first message"
            assert record.source == "web"

    @pytest.mark.asyncio
    async def test_shadow_call_failure_does_not_fail_turn(self, mock_aide):
        """Shadow call failure does not propagate to the user."""
        from backend.services.orchestrator import Orchestrator

        with (
            patch("backend.services.orchestrator.l3_synthesizer") as mock_l3,
            patch("backend.services.orchestrator.r2_service") as mock_r2,
            patch("backend.services.orchestrator.flight_recorder_uploader"),
        ):
            orch = Orchestrator()
            orch.aide_repo = MagicMock()
            orch.conv_repo = MagicMock()

            mock_aide_obj = MagicMock()
            mock_aide_obj.state = mock_aide["state"]
            mock_aide_obj.title = mock_aide["title"]
            mock_aide_obj.event_log = []

            orch.aide_repo.get = AsyncMock(return_value=mock_aide_obj)
            orch.aide_repo.update_state = AsyncMock()

            mock_conv_obj = MagicMock()
            mock_conv_obj.id = "conv_1"
            mock_conv_obj.messages = []

            orch.conv_repo.get_for_aide = AsyncMock(return_value=mock_conv_obj)
            orch.conv_repo.append_message = AsyncMock()

            mock_r2.upload_html = AsyncMock()

            mock_l3.synthesize = AsyncMock(return_value={"primitives": [], "response": "Done."})
            mock_l3.system_prompt = "system"
            mock_l3._build_user_message = MagicMock(return_value="prompt")

            # Shadow call raises an exception (patched at source)
            with patch(
                "backend.services.ai_provider.AIProvider.call_claude",
                new_callable=AsyncMock,
                side_effect=Exception("shadow model down"),
            ):
                # Should not raise
                result = await orch.process_message(
                    user_id="user_abc",
                    aide_id="aide_123",
                    message="test message",
                    source="web",
                )

            # Production response still returned
            assert result["response"] == "Done."
