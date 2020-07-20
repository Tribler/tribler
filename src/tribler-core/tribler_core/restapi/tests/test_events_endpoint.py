import json
from asyncio import CancelledError, Future, ensure_future
from contextlib import suppress

from aiohttp import ClientSession

from ipv8.messaging.anonymization.tunnel import Circuit

import pytest

from tribler_common.simpledefs import NTFY

from tribler_core.version import version_id


messages_to_wait_for = set()


async def open_events_socket(session, connected_future, events_future):
    global messages_to_wait_for
    url = 'http://localhost:%s/events' % session.config.get_api_http_port()
    headers = {'User-Agent': 'Tribler ' + version_id}

    async with ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            # The first event message is always events_start
            await response.content.readline()
            await response.content.readline()  # Events are separated by 2 newline characters
            connected_future.set_result(None)
            while True:
                msg = await response.content.readline()
                await response.content.readline()
                messages_to_wait_for.remove(json.loads(msg[5:])["type"])
                if not messages_to_wait_for:
                    events_future.set_result(None)
                    break


@pytest.mark.asyncio
async def test_events(enable_api, session):
    """
    Testing whether various events are coming through the events endpoints
    """
    global messages_to_wait_for
    connected_future = Future()
    events_future = Future()
    event_socket_task = ensure_future(open_events_socket(session, connected_future, events_future))
    await connected_future

    testdata = {
        NTFY.CHANNEL_ENTITY_UPDATED: {"state": "Complete"},
        NTFY.UPGRADER_TICK: ("bla", ),
        NTFY.UPGRADER_DONE: None,
        NTFY.WATCH_FOLDER_CORRUPT_FILE: ("foo", ),
        NTFY.TRIBLER_NEW_VERSION: ("123",),
        NTFY.CHANNEL_DISCOVERED: {"result": "bla"},
        NTFY.TORRENT_FINISHED: (b'a' * 10, None, False),
        NTFY.LOW_SPACE: ("", ),
        NTFY.TUNNEL_REMOVE: (Circuit(1234, None), 'test'),
        NTFY.REMOTE_QUERY_RESULTS: {"query": "test"},
    }
    messages_to_wait_for = set(k.value for k in testdata)
    messages_to_wait_for.add(NTFY.TRIBLER_EXCEPTION.value)
    for subject, data in testdata.items():
        if data:
            session.notifier.notify(subject, *data)
        else:
            session.notifier.notify(subject)
    session.api_manager.root_endpoint.endpoints['/events'].on_tribler_exception("hi")
    await events_future

    event_socket_task.cancel()
    with suppress(CancelledError):
        await event_socket_task
