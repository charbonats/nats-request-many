from __future__ import annotations

from typing import AsyncContextManager, AsyncIterator

from nats.aio.client import Client as NATSClient
from nats.aio.msg import Msg

from .executor import RequestManyExecutor
from .iterator import RequestManyIterator


class Client(NATSClient):
    def __init__(
        self,
        max_wait: float = 0.5,
    ) -> None:
        super().__init__()
        self.max_wait = max_wait

    def request_many_iter(
        self,
        subject: str,
        payload: bytes | None = None,
        headers: dict[str, str] | None = None,
        reply_inbox: str | None = None,
        max_wait: float | None = None,
        max_count: int | None = None,
        max_interval: float | None = None,
        stop_on_sentinel: bool = False,
    ) -> AsyncContextManager[AsyncIterator[Msg]]:
        """Request many responses from the same subject.

        The iterator exits without raising an error when no responses are received.

        Responses are received until one of the following conditions is met:

        - max_wait seconds have passed.
        - max_count responses have been received.
        - max_interval seconds have passed between responses.
        - A sentinel message is received and stop_on_sentinel is True.

        When any of the condition is met, the async iterator yielded by the
        context manager raises StopAsyncIteration on the next iteration.

        The subscription is started when entering the async context manager and
        stopped when exiting.

        Args:
            subject: The subject to send the request to.
            payload: The payload to send with the request.
            headers: The headers to send with the request.
            reply_inbox: The inbox to receive the responses in. A new inbox is created if None.
            max_wait: The maximum amount of time to wait for responses. 1 second by default.
            max_count: The maximum number of responses to accept. No limit by default.
            max_interval: The maximum amount of time between responses. No limit by default.
            stop_on_sentinel: Whether to stop when a sentinel message is received. False by default.
        """
        inbox = reply_inbox or self.new_inbox()
        return RequestManyIterator(
            self,
            subject,
            payload=payload,
            headers=headers,
            inbox=inbox,
            max_wait=max_wait,
            max_count=max_count,
            max_interval=max_interval,
            stop_on_sentinel=stop_on_sentinel,
        )

    async def request_many(
        self,
        subject: str,
        payload: bytes | None = None,
        headers: dict[str, str] | None = None,
        reply_inbox: str | None = None,
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

        Subscription is always stopped when the function returns.

        Args:
            subject: The subject to send the request to.
            payload: The payload to send with the request.
            headers: The headers to send with the request.
            reply_inbox: The inbox to receive the responses in. A new inbox is created if None.
            max_wait: The maximum amount of time to wait for responses. 1 second by default.
            max_count: The maximum number of responses to accept. No limit by default.
            max_interval: The maximum amount of time between responses. No limit by default.
            stop_on_sentinel: Whether to stop when a sentinel message is received. False by default.
        """
        executor = RequestManyExecutor(self, max_wait)
        return await executor(
            subject,
            reply_inbox=reply_inbox,
            payload=payload,
            headers=headers,
            max_wait=max_wait,
            max_count=max_count,
            max_interval=max_interval,
            stop_on_sentinel=stop_on_sentinel,
        )
