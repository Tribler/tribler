import json
from asyncio import CancelledError, Event, create_task
from contextlib import suppress

from aiohttp import ClientSession

from ipv8.messaging.anonymization.tunnel import Circuit

import pytest

from tribler_common.reported_error import ReportedError
from tribler_common.simpledefs import NTFY

from tribler_core.components.restapi.rest.rest_manager import ApiKeyMiddleware, RESTManager, error_middleware
from tribler_core.components.restapi.rest.root_endpoint import RootEndpoint
from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.notifier import Notifier
from tribler_core.version import version_id

messages_to_wait_for = set()


@pytest.fixture
def api_port(free_port):
    return free_port


@pytest.fixture
def notifier():
    return Notifier()


@pytest.fixture
async def rest_manager(api_port, tmp_path, notifier):
    config = TriblerConfig()
    config.api.http_enabled = True
    config.api.http_port = api_port
    root_endpoint = RootEndpoint(config, middlewares=[ApiKeyMiddleware(config.api.key), error_middleware])
    rest_manager = RESTManager(config=config.api, root_endpoint=root_endpoint, state_dir=tmp_path)
    events_endpoint = rest_manager.get_endpoint('events')
    events_endpoint.connect_notifier(notifier)

    await rest_manager.start()
    yield rest_manager
    await rest_manager.stop()


async def open_events_socket(rest_manager_, connected_event, events_up):
    global messages_to_wait_for
    port = rest_manager_.config.http_port
    url = f'http://localhost:{port}/events'
    headers = {'User-Agent': 'Tribler ' + version_id}

    async with ClientSession() as client:
        async with client.get(url, headers=headers) as response:
            # The first event message is always events_start
            await response.content.readline()
            await response.content.readline()  # Events are separated by 2 newline characters
            connected_event.set()
            while True:
                msg = await response.content.readline()
                await response.content.readline()
                messages_to_wait_for.remove(json.loads(msg[5:])["type"])
                if not messages_to_wait_for:
                    events_up.set()
                    break


@pytest.mark.asyncio
async def test_events(rest_manager, notifier):
    """
    Testing whether various events are coming through the events endpoints
    """
    global messages_to_wait_for
    connected_event = Event()
    events_up = Event()
    # await open_events_socket(rest_manager, connected_event, events_up)
    event_socket_task = create_task(open_events_socket(rest_manager, connected_event, events_up))
    await connected_event.wait()

    testdata = {
        NTFY.CHANNEL_ENTITY_UPDATED: {"state": "Complete"},
        NTFY.UPGRADER_TICK: ("bla",),
        NTFY.UPGRADER_DONE: None,
        NTFY.WATCH_FOLDER_CORRUPT_FILE: ("foo",),
        NTFY.TRIBLER_NEW_VERSION: ("123",),
        NTFY.CHANNEL_DISCOVERED: {"result": "bla"},
        NTFY.TORRENT_FINISHED: (b'a' * 10, None, False),
        NTFY.LOW_SPACE: ("",),
        NTFY.TUNNEL_REMOVE: (Circuit(1234, None), 'test'),
        NTFY.REMOTE_QUERY_RESULTS: {"query": "test"},
    }
    messages_to_wait_for = {k.value for k in testdata}
    messages_to_wait_for.add(NTFY.TRIBLER_EXCEPTION.value)
    for subject, data in testdata.items():
        if data:
            notifier.notify(subject, *data)
        else:
            notifier.notify(subject)
    rest_manager.root_endpoint.endpoints['/events'].on_tribler_exception(ReportedError('', '', {}, False))
    await events_up.wait()

    event_socket_task.cancel()
    with suppress(CancelledError):
        await event_socket_task
