#!/usr/bin/env python

import asyncio
import os

import asyncio_redis
import websockets

from structlog import get_logger

CHANNEL = 'incoming-messages'
MAXSIZE = 1000

clients = {}

logger = get_logger()


def get_host_details():
    """
    Take config from the environment
    """
    host = os.environ.get('REDIS_HOST', 'redis')
    port = int(os.environ.get('REDIS_PORT', 6379))
    topic = os.environ.get('REDIS_TOPIC', 'blah')
    return host, port, topic


async def read_from_pubsub():
    host, port, topic = get_host_details()
    connection = await asyncio_redis.Connection.create(host=host, port=port)
    subscriber = await connection.start_subscribe()
    await subscriber.subscribe([topic])
    logger.info("Initialized Redis. Entering message loop")

    while True:
        reply = await subscriber.next_published()
        logger.debug("Got message", num_clients=len(clients))
        for (c_host, c_port), c in clients.items():
            try:
                c.put_nowait(reply)
            except asyncio.QueueFull:
                # The client is too slow in picking up the message most likely
                # Drop it and log at warning level. Since delivery
                # is best-effort, don't consider this to be an error.
                logger.warning("Dropping log message. Possible slow client",
                               host=c_host, port=c_port, dropped=1)

    connection.close()


async def server(websocket, path):
    clients[websocket.remote_address] = asyncio.Queue(MAXSIZE)
    q = clients[websocket.remote_address]
    while True:
        item = await q.get()
        await websocket.send(item.value)


if __name__ == '__main__':
    start_server = websockets.serve(server, '0.0.0.0', 8765)
    asyncio.get_event_loop().create_task(read_from_pubsub())
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()
