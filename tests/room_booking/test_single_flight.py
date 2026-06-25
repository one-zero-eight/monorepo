import asyncio

import pytest

from src.room_booking.modules.bookings.single_flight import SingleFlight


@pytest.mark.anyio
async def test_run_returns_task_result():
    sf = SingleFlight[str, str]()

    call_count = 0

    def create():
        nonlocal call_count
        call_count += 1

        async def work():
            return "ok"

        return asyncio.create_task(work())

    result = await sf.run("k", create)
    assert result == "ok"
    assert call_count == 1
    return result


@pytest.mark.anyio
async def test_same_key_dedupes_concurrent_calls():
    sf = SingleFlight[str, str]()
    create_count = 0

    def create():
        nonlocal create_count
        create_count += 1

        async def work():
            await asyncio.sleep(0.05)
            return f"result-{create_count}"

        return asyncio.create_task(work())

    t1 = asyncio.create_task(sf.run("same", create))
    await asyncio.sleep(0.01)
    t2 = asyncio.create_task(sf.run("same", create))
    r1, r2 = await asyncio.gather(t1, t2)
    assert r1 == r2
    assert create_count == 1


@pytest.mark.anyio
async def test_different_keys_create_separate_tasks():
    sf = SingleFlight[str, str]()

    def make_task(val: str):
        async def work():
            return val

        return asyncio.create_task(work())

    r1 = await sf.run("a", lambda: make_task("A"))
    r2 = await sf.run("b", lambda: make_task("B"))
    assert [r1, r2] == ["A", "B"]


@pytest.mark.anyio
async def test_after_task_done_same_key_creates_new_task():
    sf = SingleFlight[int, str]()
    create_count = 0

    def make_task():
        nonlocal create_count
        create_count += 1

        async def work():
            return create_count

        return asyncio.create_task(work())

    first = await sf.run("k", make_task)
    assert first == 1
    second = await sf.run("k", make_task)
    assert second == 2
    assert create_count == 2


@pytest.mark.anyio
async def test_use_dedup_false_always_creates_new_task():
    sf = SingleFlight[int, str]()
    create_count = 0

    def make_task():
        nonlocal create_count
        create_count += 1

        async def work():
            return create_count

        return asyncio.create_task(work())

    await sf.run("k", make_task, use_dedup=False)
    await sf.run("k", make_task, use_dedup=False)
    assert create_count == 2


@pytest.mark.anyio
async def test_exception_clears_stored_task():
    sf = SingleFlight[str, str]()

    def make_failing():
        async def work():
            raise ValueError("fail")

        return asyncio.create_task(work())

    with pytest.raises(ValueError, match="fail"):
        await sf.run("k", make_failing)

    create_count = 0

    def make_ok():
        nonlocal create_count
        create_count += 1

        async def work():
            return "ok"

        return asyncio.create_task(work())

    result = await sf.run("k", make_ok)
    assert result == "ok"
    assert create_count == 1


@pytest.mark.anyio
async def test_concurrent_different_keys_both_run():
    sf = SingleFlight[str, str]()
    order = []

    def make_task(key: str):
        async def work():
            await asyncio.sleep(0.03)
            order.append(key)
            return key

        return asyncio.create_task(work())

    r1 = asyncio.create_task(sf.run("a", lambda: make_task("a")))
    r2 = asyncio.create_task(sf.run("b", lambda: make_task("b")))
    results = await asyncio.gather(r1, r2)
    assert sorted(results) == ["a", "b"]
    assert sorted(order) == ["a", "b"]
