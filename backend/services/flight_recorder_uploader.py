"""Flight recorder uploader — batches TurnRecords and uploads to R2 as JSONL."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime

from backend.config import settings
from backend.services.flight_recorder import TurnRecord

# Maximum records held in memory before dropping oldest
_MAX_QUEUE_SIZE = 10_000
# Upload a batch when it hits this size
_BATCH_SIZE = 100
# Or when this many seconds have elapsed since last flush
_FLUSH_INTERVAL_SECONDS = 60


class FlightRecorderUploader:
    """
    Background uploader for flight recorder data.

    Enqueue is O(1) and never blocks the caller. A background task
    drains the queue, batches records, and uploads JSONL to R2.

    Storage layout:
        aide-workspaces/flight-logs/{aide_id}/{YYYY-MM-DD}/{batch_id}.jsonl
    """

    def __init__(self) -> None:
        """Initialize uploader with bounded in-memory queue."""
        self._queue: asyncio.Queue[TurnRecord] = asyncio.Queue(maxsize=_MAX_QUEUE_SIZE)
        self._running = False

    def enqueue(self, record: TurnRecord) -> None:
        """
        Add a TurnRecord to the upload queue (non-blocking).

        If the queue is full, the oldest record is dropped and a warning is logged.

        Args:
            record: Completed TurnRecord to upload
        """
        try:
            self._queue.put_nowait(record)
        except asyncio.QueueFull:
            # Drop oldest to make room for newest
            try:
                dropped = self._queue.get_nowait()
                print(f"FlightRecorderUploader: queue full ({_MAX_QUEUE_SIZE}), dropped turn {dropped.turn_id}")
            except asyncio.QueueEmpty:
                pass
            # Try again after dropping
            try:
                self._queue.put_nowait(record)
            except asyncio.QueueFull:
                print(f"FlightRecorderUploader: failed to enqueue turn {record.turn_id}")

    async def run(self) -> None:
        """
        Background loop: drain queue and upload batches to R2.

        Runs until cancelled. Uploads a batch when it reaches _BATCH_SIZE
        records or _FLUSH_INTERVAL_SECONDS has elapsed, whichever comes first.
        """
        self._running = True
        print("FlightRecorderUploader: started")

        batch: list[TurnRecord] = []
        last_flush = asyncio.get_event_loop().time()

        while self._running:
            # Try to drain up to _BATCH_SIZE records in one go
            try:
                # Wait up to 1 second for a record before checking flush interval
                record = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                batch.append(record)
                self._queue.task_done()

                # Drain any additional records already in queue (up to batch size)
                while len(batch) < _BATCH_SIZE:
                    try:
                        record = self._queue.get_nowait()
                        batch.append(record)
                        self._queue.task_done()
                    except asyncio.QueueEmpty:
                        break

            except TimeoutError:
                pass  # No new records — check if we should flush

            # Flush if batch is full or interval elapsed
            now = asyncio.get_event_loop().time()
            should_flush = len(batch) >= _BATCH_SIZE or (batch and (now - last_flush) >= _FLUSH_INTERVAL_SECONDS)

            if should_flush and batch:
                await self._upload_batch(batch)
                batch = []
                last_flush = now

        # Final flush on shutdown
        if batch:
            await self._upload_batch(batch)

    async def flush(self) -> None:
        """Force-flush remaining queue contents (for clean shutdown)."""
        self._running = False
        batch: list[TurnRecord] = []

        while True:
            try:
                record = self._queue.get_nowait()
                batch.append(record)
                self._queue.task_done()
            except asyncio.QueueEmpty:
                break

        if batch:
            await self._upload_batch(batch)

    async def _upload_batch(self, batch: list[TurnRecord]) -> None:
        """
        Serialize a batch of TurnRecords to JSONL and upload to R2.

        Uses the first record's aide_id and current date to build the key.
        Retries once on failure. Failures do not raise — they are logged only.

        Args:
            batch: List of TurnRecords to upload as one JSONL file
        """
        if not batch:
            return

        # Group by aide_id for separate files per aide
        by_aide: dict[str, list[TurnRecord]] = {}
        for record in batch:
            by_aide.setdefault(record.aide_id, []).append(record)

        for aide_id, records in by_aide.items():
            await self._upload_aide_batch(aide_id, records)

    async def _upload_aide_batch(self, aide_id: str, records: list[TurnRecord]) -> None:
        """Upload one batch for a single aide."""
        date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        batch_id = uuid.uuid4().hex[:12]
        key = f"flight-logs/{aide_id}/{date_str}/{batch_id}.jsonl"

        # Serialize to JSONL
        try:
            lines = [json.dumps(r.to_dict(), default=str) for r in records]
            content = "\n".join(lines) + "\n"
            content_bytes = content.encode("utf-8")
        except Exception as e:
            print(f"FlightRecorderUploader: serialization error for aide {aide_id}: {e}")
            return

        # Upload with one retry
        for attempt in range(2):
            try:
                await self._put_r2(key, content_bytes)
                print(
                    f"FlightRecorderUploader: uploaded {len(records)} records "
                    f"to flight-logs/{aide_id}/{date_str}/{batch_id}.jsonl"
                )
                return
            except Exception as e:
                if attempt == 0:
                    print(f"FlightRecorderUploader: upload failed for {key} (retrying): {e}")
                    await asyncio.sleep(2)
                else:
                    print(f"FlightRecorderUploader: upload permanently failed for {key}: {e}")

    async def _put_r2(self, key: str, content: bytes) -> None:
        """
        Upload bytes to R2 workspace bucket.

        Args:
            key: R2 object key (path)
            content: Raw bytes to upload
        """
        import aioboto3

        session = aioboto3.Session()
        async with session.client(
            "s3",
            endpoint_url=settings.R2_ENDPOINT,
            aws_access_key_id=settings.R2_ACCESS_KEY,
            aws_secret_access_key=settings.R2_SECRET_KEY,
        ) as s3:
            await s3.put_object(
                Bucket=settings.R2_WORKSPACE_BUCKET,
                Key=key,
                Body=content,
                ContentType="application/x-ndjson",
            )


# Singleton instance
flight_recorder_uploader = FlightRecorderUploader()
