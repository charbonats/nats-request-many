from __future__ import annotations

import pytest

from nats_contrib.request_many.utils import transform


@pytest.mark.asyncio
class TestTransform:
    """Test suite for transfor function."""

    async def test_transform(self):

        class TestIteratorContext:
            def __init__(self, length: int):
                self.length = length
                self.count = 0

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                pass

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.count < self.length:
                    self.count += 1
                    return self.count
                raise StopAsyncIteration

        ctx = transform(TestIteratorContext(3), lambda x: x * 2)
        async with ctx as iterator:
            assert [x async for x in iterator] == [2, 4, 6]
