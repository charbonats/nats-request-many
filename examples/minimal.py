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
