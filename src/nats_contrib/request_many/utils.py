from __future__ import annotations

from typing import Any, AsyncContextManager, AsyncIterator, Callable, Generic, TypeVar

T = TypeVar("T")
R = TypeVar("R")


def transform(
    source: AsyncContextManager[AsyncIterator[T]],
    map: Callable[[T], R],
) -> AsyncContextManager[AsyncIterator[R]]:
    """Create a new async context manager which will
    yield an async iterator that applies the map function to each value
    yielded by the source async iterator.

    It is useful for example to transform the return value of the
    `request_many_iter` method.
    """
    return TransformAsyncIterator(source, map)


class TransformAsyncIterator(Generic[T, R]):
    def __init__(
        self,
        source: AsyncContextManager[AsyncIterator[T]],
        map: Callable[[T], R],
    ) -> None:
        self.factory = source
        self.iterator: AsyncIterator[T] | None = None
        self.transform = map

    def __aiter__(self) -> TransformAsyncIterator[T, R]:
        return self

    async def __anext__(self) -> R:
        if not self.iterator:
            raise RuntimeError(
                "TransformAsyncIterator must be used as an async context manager"
            )
        next_value = await self.iterator.__anext__()
        return self.transform(next_value)

    async def __aenter__(self) -> AsyncIterator[R]:
        self.iterator = await self.factory.__aenter__()
        return self

    async def __aexit__(self, *args: Any, **kwargs: Any) -> None:
        await self.factory.__aexit__(*args, **kwargs)
