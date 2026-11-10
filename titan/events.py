"""Non-blocking SSE event tail for SQLite-backed TITAN event history."""
import asyncio
import json
import time


async def event_stream(db, cursor=0, job_id=None, heartbeat_seconds=15,
                       poll_seconds=0.25, stop_event=None, disconnected=None):
    """Yield replayable SSE frames; all synchronous SQLite work runs off-loop."""
    if type(cursor) is not int or cursor < 0:
        raise ValueError("Invalid event cursor")
    if heartbeat_seconds <= 0 or poll_seconds <= 0:
        raise ValueError("Invalid stream timing")
    last_id = cursor
    last_heartbeat = time.monotonic()
    while stop_event is None or not stop_event.is_set():
        if disconnected is not None and await disconnected():
            return
        rows = await asyncio.to_thread(db.events_after, last_id, job_id, 100)
        if rows:
            for row in rows:
                event_id = int(row["id"])
                if event_id <= last_id:
                    continue
                payload = json.dumps(row, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
                kind = str(row.get("kind") or "message").replace("\r", "").replace("\n", "")[:80]
                yield f"id: {event_id}\nevent: {kind}\ndata: {payload}\n\n"
                last_id = event_id
            # Drain a full page immediately before sleeping, avoiding delayed replay.
            if len(rows) >= 100:
                continue
        now = time.monotonic()
        if now - last_heartbeat >= heartbeat_seconds:
            yield ": heartbeat\n\n"
            last_heartbeat = now
        if stop_event is not None:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=poll_seconds)
            except asyncio.TimeoutError:
                pass
        else:
            await asyncio.sleep(poll_seconds)
