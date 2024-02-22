from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator

from nats.aio.client import Client
from nats.aio.msg import Msg
from nats.aio.subscription import Subscription
from nats.errors import BadSubscriptionError


class RequestManyIterator:

    def __init__(
        self,
        nc: Client,
        subject: str,
        inbox: str,
        payload: bytes | None = None,
        headers: dict[str, str] | None = None,
        max_wait: float | None = None,
        max_interval: float | None = None,
        max_count: int | None = None,
        stop_on_sentinel: bool = False,
    ) -> None:
        """Request many responses from the same subject.

        Request is sent when entering the async context manager and unsubscribed when exiting.

        The async iterator yieled by the context manager do not raise an
        error when no responses are received.

        Responses are received until one of the following conditions is met:

        - max_wait seconds have passed.
        - max_count responses have been received.
        - max_interval seconds have passed between responses.
        - A sentinel message is received and stop_on_sentinel is True.

        When any of the condition is met, the async iterator raises StopAsyncIteration on
        the next call to __anext__, and the subscription is unsubscribed on exit.

        Args:
            subject: The subject to send the request to.
            payload: The payload to send with the request.
            headers: The headers to send with the request.
            inbox: The inbox to receive the responses in. A new inbox is created if None.
            max_wait: The maximum amount of time to wait for responses. Default max wait can be configured at the instance level.
            max_count: The maximum number of responses to accept. No limit by default.
            max_interval: The maximum amount of time between responses. No limit by default.
            stop_on_sentinel: Whether to stop when a sentinel message is received. False by default.
        """
        if max_wait is None and max_interval is None:
            max_wait = 0.5
        # Save all the arguments as instance variables.
        self.nc = nc
        self.subject = subject
        self.payload = payload
        self.headers = headers
        self.inbox = inbox
        self.max_wait = max_wait
        self.max_count = max_count
        self.max_interval = max_interval
        self.stop_on_sentinel = stop_on_sentinel
        # Initialize the state of the request many iterator
        self._sub: Subscription | None = None
        self._iterator: AsyncIterator[Msg] | None = None
        self._did_unsubscribe = False
        self._total_received = 0
        self._last_received = asyncio.get_event_loop().time()
        self._tasks: list[asyncio.Task[object]] = []
        self._pending_task: asyncio.Task[Msg] | None = None

    def __aiter__(self) -> RequestManyIterator:
        """RequestManyIterator is an asynchronous iterator."""
        return self

    async def __anext__(self) -> Msg:
        """Return the next message or raise StopAsyncIteration."""
        if not self._sub:
            raise RuntimeError(
                "RequestManyIterator must be used as an async context manager"
            )
        # Exit early if we've already unsubscribed
        if self._did_unsubscribe:
            raise StopAsyncIteration
        # Exit early if we received all the messages
        if self.max_count and self._total_received == self.max_count:
            if self._sub and not self._did_unsubscribe:
                self._did_unsubscribe = True
                await _unsubscribe(self._sub)
            raise StopAsyncIteration
        # Create a task to wait for the next message
        task: asyncio.Task[Msg] = asyncio.create_task(self._iterator.__anext__())  # type: ignore
        self._pending_task = task
        # Wait for the next message or any of the other tasks to complete
        await asyncio.wait(
            [self._pending_task, *self._tasks],
            return_when=asyncio.FIRST_COMPLETED,
        )
        if self._pending_task.cancelled():
            raise StopAsyncIteration
        if not self._pending_task.done():
            self._pending_task.cancel()
            raise StopAsyncIteration
        # if err := self._pending_task.exception():
        #     raise err
        # This will raise an exception if an error occurred within the task
        msg = self._pending_task.result()
        # Check message headers
        # If the message is a 503 error, raise StopAsyncIteration
        if msg.headers and msg.headers.get("Status") == "503":
            raise StopAsyncIteration
        # Always increment the total received count
        self._total_received += 1
        # Check if this is a sentinel message
        if self.stop_on_sentinel and msg.data == b"":
            if self._sub and not self._did_unsubscribe:
                self._did_unsubscribe = True
                await _unsubscribe(self._sub)
            # In which case, raise StopAsyncIteration and don't return the message
            raise StopAsyncIteration
        # Return the message
        return msg

    async def __aenter__(self) -> RequestManyIterator:
        """Start the subscription and publish the request."""
        # Start the subscription
        sub = await self.nc.subscribe(  # pyright: ignore[reportUnknownMemberType]
            self.inbox,
            max_msgs=self.max_count or 0,
        )
        # Save the subscription and the iterator
        self._iterator = sub.messages
        self._sub = sub
        # Add a task to wait for the max_wait time if needed
        if self.max_wait:
            self._tasks.append(asyncio.create_task(asyncio.sleep(self.max_wait)))
        # Add a task to check the interval if needed
        if self.max_interval:
            interval = self.max_interval

            async def check_interval() -> None:
                while True:
                    await asyncio.sleep(interval)
                    if asyncio.get_event_loop().time() - self._last_received > interval:
                        if self._sub and not self._did_unsubscribe:
                            self._did_unsubscribe = True
                            await _unsubscribe(self._sub)
                        return

            self._tasks.append(asyncio.create_task(check_interval()))

        # Publish the request
        await self.nc.publish(
            self.subject, self.payload or b"", reply=self.inbox, headers=self.headers
        )
        # At this point the subscription is ready and all tasks are submitted
        return self

    async def __aexit__(self, *args: Any, **kwargs: Any) -> None:
        """Unsubscribe from the inbox and cancel all the tasks."""
        for task in self._tasks:
            if not task.done():
                task.cancel()
        if self._pending_task and not self._pending_task.done():
            self._pending_task.cancel()
        if self._sub and not self._did_unsubscribe:
            await _unsubscribe(self._sub)


async def _unsubscribe(sub: Subscription) -> None:
    try:
        await sub.unsubscribe()
    except BadSubscriptionError:
        # It's possible that auto-unsubscribe has already been called.
        pass
