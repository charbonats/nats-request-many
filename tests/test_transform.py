from __future__ import annotations

import pytest

from nats_contrib.request_many.utils import transform


class StubIteratorContext:
    def __init__(self, length: int) -> None:
        self.length = length
        self.count = 0

    async def __aenter__(self) -> StubIteratorContext:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        pass

    def __aiter__(self) -> StubIteratorContext:
        return self

    async def __anext__(self) -> int:
        if self.count < self.length:
            self.count += 1
            return self.count
        raise StopAsyncIteration


@pytest.mark.asyncio
class TestTransform:
    """Test suite for transfor function."""

    async def test_transform(self):

        ctx = transform(StubIteratorContext(3), lambda x: x * 2)
        async with ctx as iterator:
            assert [x async for x in iterator] == [2, 4, 6]

    @pytest.mark.asyncio
    async def test_transform_bad_usage(self):
        with pytest.raises(RuntimeError) as exc:
            ctx = transform(StubIteratorContext(3), lambda x: x * 2)
            async for msg in ctx:  # type: ignore
                pass

        assert (
            str(exc.value)
            == "TransformAsyncIterator must be used as an async context manager"
        )
