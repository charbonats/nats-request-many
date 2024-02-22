from __future__ import annotations

import asyncio
import contextlib
from typing import AsyncIterator, Awaitable, Callable

import pytest
import pytest_asyncio
from async_timeout import timeout
from nats.aio.msg import Msg
from nats_contrib.test_server import NATSD

from nats_contrib.request_many import Client as NATS


@pytest.mark.asyncio
class RequestManyTestSetup:
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self, nats_server: NATSD, nats_client: NATS) -> AsyncIterator[None]:
        self.nats_server = nats_server
        self.nats_client = nats_client
        self.test_stack = contextlib.AsyncExitStack()
        async with self.test_stack:
            yield None


class TestRequestMany(RequestManyTestSetup):
    """Test suite for request_many method."""

    @pytest.mark.parametrize(
        ["max_wait", "max_interval"],
        [
            (None, None),
            (0.1, None),
            (None, 0.1),
            (0.1, 0.1),
        ],
    )
    async def test_request_many_no_responder(
        self, max_wait: float | None, max_interval: float | None
    ) -> None:
        async with timeout(0.05):
            # Request many without a responder and big timeout
            messages = await self.nats_client.request_many(
                "not.a.subject.with.listener",
                max_wait=max_wait,
                max_interval=max_interval,
            )
        # No messages should be received
        assert messages == []

    async def test_request_many_single_responder(self) -> None:
        # Define a handler function
        async def responder(msg: Msg) -> None:
            await msg.respond(b"OK")

        # Create service
        sub = await self.nats_client.subscribe("subject.with.listener", cb=responder)
        # Unsubscribe when done
        self.test_stack.push_async_callback(sub.unsubscribe)
        async with timeout(0.2):
            # Request many with a single responder
            msg, *rest = await self.nats_client.request_many(
                "subject.with.listener", max_wait=0.1
            )
        # One message should be received
        assert len(rest) == 0
        # Message should be the expected one
        assert msg.data == b"OK"

    async def test_request_many_multiple_responders(self) -> None:
        # Define a handler function
        def make_responder(index: int) -> Callable[[Msg], Awaitable[None]]:
            async def responder(msg: Msg) -> None:
                await msg.respond(f"{index}".encode())

            return responder

        # Create services
        subs = [
            await self.nats_client.subscribe(
                "subject.with.listener", cb=make_responder(i)
            )
            for i in range(5)
        ]
        # Unsubscribe when done
        for sub in subs:
            self.test_stack.push_async_callback(sub.unsubscribe)
        # Request many with multiple responders
        # Task should not reach timeout
        async with timeout(0.2):
            msgs = await self.nats_client.request_many(
                "subject.with.listener", max_wait=0.1
            )
        # All messages should be received
        assert len(msgs) == 5
        # All messages should be the expected one
        assert set(msg.data for msg in msgs) == {b"0", b"1", b"2", b"3", b"4"}

    async def test_request_many_max_count_not_reached(self) -> None:
        # Define a handler function
        async def responder(msg: Msg) -> None:
            await msg.respond(b"OK")

        # Create service
        sub = await self.nats_client.subscribe("subject.with.listener", cb=responder)
        # Unsubscribe when done
        self.test_stack.push_async_callback(sub.unsubscribe)
        async with timeout(0.2):
            # Request many with a single responder
            msgs = await self.nats_client.request_many(
                "subject.with.listener", max_wait=0.1, max_count=5
            )
        # One message should be received
        assert len(msgs) == 1
        # Message should be the expected one
        assert msgs[0].data == b"OK"

    async def test_request_many_max_count_reached(self) -> None:
        # Define a handler function
        async def responder(msg: Msg) -> None:
            await msg.respond(b"OK")

        # Create service
        sub = await self.nats_client.subscribe("subject.with.listener", cb=responder)
        # Unsubscribe when done
        self.test_stack.push_async_callback(sub.unsubscribe)
        async with timeout(0.2):
            # Request many with a single responder
            msgs = await self.nats_client.request_many(
                "subject.with.listener", max_wait=0.1, max_count=1
            )
        # One message should be received
        assert len(msgs) == 1
        # Message should be the expected one
        assert msgs[0].data == b"OK"

    async def test_request_many_max_count_reached_multiple_responders(self) -> None:
        # Define a handler function
        def make_responder(index: int) -> Callable[[Msg], Awaitable[None]]:
            async def responder(msg: Msg) -> None:
                await msg.respond(f"{index}".encode())

            return responder

        # Create services
        subs = [
            await self.nats_client.subscribe(
                "subject.with.listener", cb=make_responder(i)
            )
            for i in range(3)
        ]
        # Unsubscribe when done
        for sub in subs:
            self.test_stack.push_async_callback(sub.unsubscribe)
        # Request many with multiple responders
        # Task should not reach timeout
        async with timeout(0.2):
            msgs = await self.nats_client.request_many(
                "subject.with.listener", max_wait=0.1, max_count=3
            )
        # All messages should be received
        assert len(msgs) == 3
        # All messages should be the expected one
        assert set(msg.data for msg in msgs) == {b"0", b"1", b"2"}

    async def test_request_many_max_interval_reached(self) -> None:
        # Define a handler function
        async def first_responder(msg: Msg) -> None:
            await msg.respond(b"OK")

        async def second_responder(msg: Msg) -> None:
            await asyncio.sleep(0.2)
            await msg.respond(b"OK")

        # Create service
        for resp in [first_responder, second_responder]:
            sub = await self.nats_client.subscribe("subject.with.listener", cb=resp)
            # Unsubscribe when done
            self.test_stack.push_async_callback(sub.unsubscribe)

        async with timeout(0.1):
            # Request many with a single responder
            msgs = await self.nats_client.request_many(
                "subject.with.listener", max_interval=0.01
            )
        # One message should be received
        assert len(msgs) == 1
        # Message should be the expected one
        assert msgs[0].data == b"OK"

    async def test_request_many_custom_inbox(self) -> None:
        # Define a handler function
        async def responder(msg: Msg) -> None:
            await msg.respond(b"OK")

        # Create service
        sub = await self.nats_client.subscribe("subject.with.listener", cb=responder)
        # Unsubscribe when done
        self.test_stack.push_async_callback(sub.unsubscribe)
        async with timeout(0.2):
            # Request many with a single responder
            msgs = await self.nats_client.request_many(
                "subject.with.listener", max_wait=0.1, reply_inbox="custom.inbox"
            )
        # One message should be received
        assert len(msgs) == 1
        # Message should be the expected one
        assert msgs[0].data == b"OK"
        assert msgs[0].subject == "custom.inbox"

    async def test_request_many_sentinel(self) -> None:
        async def first_responder(msg: Msg) -> None:
            await msg.respond(b"OK")

        async def other_responder(msg: Msg) -> None:
            await msg.respond(b"")

        # Create service
        sub = await self.nats_client.subscribe(
            "subject.with.listener", cb=first_responder
        )
        # Unsubscribe when done
        self.test_stack.push_async_callback(sub.unsubscribe)
        for _ in range(5):
            sub = await self.nats_client.subscribe(
                "subject.with.listener", cb=other_responder
            )
            # Unsubscribe when done
            self.test_stack.push_async_callback(sub.unsubscribe)

        async with timeout(0.2):
            # Request many with a single responder
            msgs = await self.nats_client.request_many(
                "subject.with.listener", max_wait=0.1, stop_on_sentinel=True
            )
        # One message should be received
        assert len(msgs) == 1
        # Message should be the expected one
        assert msgs[0].data == b"OK"
