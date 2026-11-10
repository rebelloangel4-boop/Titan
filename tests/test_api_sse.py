import asyncio
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from titan.events import event_stream
from titan.store import Database
from titan.asgi import create_app


class EventStreamTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp.name) / "events.db")

    def tearDown(self):
        self.temp.cleanup()

    def test_cursor_reconnect_replays_without_missing_events(self):
        async def scenario():
            mission_id = self.db.submit("SSE replay test", kind="analysis", payload={"values": [1]})
            stream = event_stream(self.db, cursor=0, job_id=mission_id, poll_seconds=0.01)
            first = await asyncio.wait_for(anext(stream), timeout=1)
            first_id = int(first.split("\n", 1)[0].split(": ", 1)[1])
            await stream.aclose()

            self.db.event(mission_id, "checkpoint", "second event")
            resumed = event_stream(self.db, cursor=first_id, job_id=mission_id, poll_seconds=0.01)
            second = await asyncio.wait_for(anext(resumed), timeout=1)
            await resumed.aclose()
            second_id = int(second.split("\n", 1)[0].split(": ", 1)[1])
            self.assertGreater(second_id, first_id)
            self.assertIn('"detail":"second event"', second)
        asyncio.run(scenario())

    def test_idle_stream_emits_heartbeat(self):
        async def scenario():
            stop = asyncio.Event()
            stream = event_stream(self.db, heartbeat_seconds=0.01,
                                  poll_seconds=0.002, stop_event=stop)
            frame = await asyncio.wait_for(anext(stream), timeout=1)
            await stream.aclose()
            self.assertEqual(frame, ": heartbeat\\n\\n")
        asyncio.run(scenario())

    def test_events_after_are_ascending_and_job_scoped(self):
        a = self.db.submit("job A", kind="analysis", payload={"values": [1]})
        b = self.db.submit("job B", kind="analysis", payload={"values": [2]})
        self.db.event(a, "checkpoint", "A")
        self.db.event(b, "checkpoint", "B")
        rows = self.db.events_after(0, a, 100)
        self.assertTrue(all(row["job"] == a for row in rows))
        ids = [row["id"] for row in rows]
        self.assertEqual(ids, sorted(ids))

    def test_invalid_cursor_and_limit_rejected(self):
        with self.assertRaises(ValueError):
            self.db.events_after(-1)
        with self.assertRaises(ValueError):
            self.db.events_after(0, limit=0)

    def test_asgi_rejects_unauthorized_event_stream(self):
        app = create_app(db=self.db, token="t" * 40)
        with TestClient(app) as client:
            response = client.get("/api/events")
            self.assertEqual(response.status_code, 401)

    def test_asgi_rejects_malformed_last_event_id(self):
        app = create_app(db=self.db, token="t" * 40)
        with TestClient(app) as client:
            response = client.get("/api/events", headers={
                "Authorization": "Bearer " + "t" * 40,
                "Last-Event-ID": "not-a-number",
            })
            self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
