from __future__ import annotations

import asyncio

from nats.aio.client import Client
from nats.aio.msg import Msg
from nats.errors import BadSubscriptionError


class RequestManyExecutor:
    def __init__(
        self,
        nc: Client,
        max_wait: float | None = None,
    ) -> None:
        self.nc = nc
        self.max_wait = max_wait or 0.5

    async def __call__(
        self,
        subject: str,
        reply_inbox: str | None = None,
        payload: bytes | None = None,
        headers: dict[str, str] | None = None,
        max_wait: float | None = None,
        max_count: int | None = None,
        max_interval: float | None = None,
        stop_on_sentinel: bool = False,
    ) -> list[Msg]:
        """Request many responses from the same subject.

        This function does not raise an error when no responses are received.

        Responses are received until one of the following conditions is met:

        - max_wait seconds have passed.
        - max_count responses have been received.
        - max_interval seconds have passed between responses.
        - A sentinel message is received and stop_on_sentinel is True.

        Args:
            subject: The subject to send the request to.
            payload: The payload to send with the request.
            headers: The headers to send with the request.
            reply_inbox: The inbox to receive the responses in. A new inbox is created if None.
            max_wait: The maximum amount of time to wait for responses. Default max wait can be configured at the instance level.
            max_count: The maximum number of responses to accept. No limit by default.
            max_interval: The maximum amount of time between responses. No limit by default.
            stop_on_sentinel: Whether to stop when a sentinel message is received. False by default.
        """
        if max_wait is None and max_interval is None:
            max_wait = self.max_wait
        # Create an inbox for the responses if one wasn't provided.
        if reply_inbox is None:
            reply_inbox = self.nc.new_inbox()
        # Create an empty list to store the responses.
        responses: list[Msg] = []
        # Get the event loop
        loop = asyncio.get_event_loop()
        # Create an event to signal when the request is complete.
        event = asyncio.Event()
        # Create a marker to indicate that a message was received
        # and the interval has passed.
        last_received = loop.time()

        # Define a callback to handle the responses.
        async def callback(msg: Msg) -> None:
            # Update the last received time.
            nonlocal last_received
            last_received = loop.time()
            # Check message headers
            # If the message is a 503 error, set the event and return.
            if msg.headers and msg.headers.get("Status") == "503":
                event.set()
                return
            # If we're stopping on a sentinel message, check for it
            # and don't append the message to the list of responses.
            if stop_on_sentinel and msg.data == b"":
                event.set()
                return
            # In all other cases, append the message to the list of responses.
            responses.append(msg)
            # And check if we've received all the responses.
            if len(responses) == max_count:
                event.set()

        # Subscribe to the inbox.
        sub = await self.nc.subscribe(  # pyright: ignore[reportUnknownMemberType]
            reply_inbox,
            cb=callback,
            max_msgs=max_count or 0,
        )
        # Initialize a list of tasks to wait for.
        tasks: list[asyncio.Task[object]] = []
        # Enter try/finally clause to ensure that the subscription is
        # unsubscribed from even if an error occurs.
        try:
            # Create task to wait for the stop event.
            tasks.append(asyncio.create_task(event.wait()))

            # Add a task to wait for the max_wait time if needed
            if max_wait:
                tasks.append(asyncio.create_task(asyncio.sleep(max_wait)))

            # Add a task to check the interval if needed
            if max_interval:

                async def check_interval() -> None:
                    nonlocal last_received
                    while True:
                        await asyncio.sleep(max_interval)
                        if loop.time() - last_received > max_interval:
                            event.set()
                            return

                tasks.append(asyncio.create_task(check_interval()))

            # At this point the subscription is ready and all tasks are submitted
            # Publish the request.
            await self.nc.publish(
                subject, payload or b"", reply=reply_inbox, headers=headers
            )
            # Wait for the first task to complete.
            await asyncio.wait(
                tasks,
                return_when=asyncio.FIRST_COMPLETED,
            )
        # Always cancel tasks and unsubscribe from the inbox.
        finally:
            # Cancel the remaining tasks as soon as first one completes.
            for task in tasks:
                if not task.done():
                    task.cancel()
            # Unsubscribe from the inbox.
            try:
                await sub.unsubscribe()
            except BadSubscriptionError:
                # It's possible that auto-unsubscribe has already been called.
                pass

        # Return the list of responses.
        return responses
