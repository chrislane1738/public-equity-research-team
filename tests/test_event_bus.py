import asyncio

from backend.observability.event_bus import JobEventBus


async def test_publish_to_subscriber():
    bus = JobEventBus()
    q = bus.subscribe("job-1")
    await bus.publish("job-1", {"agent": "dcf", "type": "started"})
    event = await asyncio.wait_for(q.get(), timeout=1.0)
    assert event == {"agent": "dcf", "type": "started"}


async def test_publish_fans_out_to_multiple_subscribers():
    bus = JobEventBus()
    q1 = bus.subscribe("job-1")
    q2 = bus.subscribe("job-1")
    await bus.publish("job-1", {"x": 1})
    assert (await asyncio.wait_for(q1.get(), 1.0)) == {"x": 1}
    assert (await asyncio.wait_for(q2.get(), 1.0)) == {"x": 1}


async def test_publish_to_unknown_job_is_noop():
    bus = JobEventBus()
    await bus.publish("missing", {"x": 1})  # must not raise


async def test_unsubscribe_removes_queue():
    bus = JobEventBus()
    q = bus.subscribe("job-1")
    bus.unsubscribe("job-1", q)
    await bus.publish("job-1", {"x": 1})
    assert q.empty()


async def test_unsubscribe_last_drops_job_key():
    bus = JobEventBus()
    q = bus.subscribe("job-1")
    bus.unsubscribe("job-1", q)
    assert "job-1" not in bus._subscribers
