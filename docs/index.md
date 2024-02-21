# NATS Request Many



!!! warning "This is not an official NATS project"
    This is a personal project and is not endorsed by the NATS.io community. It is not guaranteed to be maintained or supported.

!!! bug "This is an experimental project"
    This project is a prototype and should not be used for anything serious. It is not tested, nor is it guaranteed to be correct.

The [nats.deno](https://github.com/nats-io/nats.deno) package ([Deno](https://deno.com/) client for NATS) provides [a simple way to request many responses from a singe NATS request](https://github.com/nats-io/nats.deno/blob/faf2c3e17ce44080b15a48af16e5e1927bf53c38/nats-base-client/nats.ts#L165).

This project is an attempt to implement the same API in Python.

## References

- The reference document I've used is this PR (not merged at the moment) [ADR-??: Request Many](https://github.com/nats-io/nats-architecture-and-design/pull/228).

- The reference implementation is in the [nats.deno package](https://github.com/nats-io/nats.deno/blob/faf2c3e17ce44080b15a48af16e5e1927bf53c38/nats-base-client/nats.ts#L165).

## How to install

<!-- termynal -->

```bash
$ pip install git+https://github.com/charbonnierg/nats-request-many.git
```

## Example usage

``` py linenums="1" title="examples/minimal.py"
from nats_contrib.request_many import Client
from nats.aio.msg import Msg

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger("request_many")


async def main():
    nc = Client()
    await nc.connect(servers="nats://localhost:4222")

    # Subscription callback
    async def cb1(msg: Msg):
        logger.info(f"sub1 received a message sub1 on {msg.subject}")
        await msg.respond(b"OK")

    async def cb2(msg: Msg):
        logger.info(f"sub2 received a message on {msg.subject}")
        await msg.respond(b"OK")

    # First subscription
    sub1 = await nc.subscribe("foo", cb=cb1, queue="queue-1")
    # Second subscription
    sub2 = await nc.subscribe("foo", cb=cb2, queue="queue-2")

    # Request many
    logger.info("sending request to subject 'foo'")
    msgs = await nc.request_many("foo", b"help", max_count=2)
    for msg in msgs:
        print(f"Received a reply: {msg.data.decode()}")

    # Request many with async iterator
    logger.info("sending request to subject 'foo'")
    async with nc.request_many_iter("foo", b"help", max_count=2) as msgs:
        async for msg in msgs:
            print(f"Received a reply: {msg.data.decode()}")

    # Unsubscribe
    await sub1.unsubscribe()
    await sub2.unsubscribe()

    # Close
    await nc.close()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
```

Run the script using:

<!-- termynal -->

``` bash
$ python examples/minimal.py

2024-02-21 03:05:16,759 - request_many - INFO - sending request to subject 'foo'
2024-02-21 03:05:16,760 - request_many - INFO - sub1 received a message sub1 on foo
2024-02-21 03:05:16,760 - request_many - INFO - sub2 received a message on foo
Received a reply: OK
Received a reply: OK
2024-02-21 03:05:16,761 - request_many - INFO - sending request to subject 'foo'
2024-02-21 03:05:16,762 - request_many - INFO - sub1 received a message sub1 on foo
2024-02-21 03:05:16,762 - request_many - INFO - sub2 received a message on foo
Received a reply: OK
Received a reply: OK
```

## Other works

- [NATS Micro](https://charbonnierg.github.io/nats-micro)
