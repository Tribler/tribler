import json
from asyncio import CancelledError, Event, create_task
from contextlib import suppress
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientSession

from ipv8.messaging.anonymization.tunnel import Circuit

import pytest

from tribler_common.reported_error import ReportedError
from tribler_common.simpledefs import NTFY

from tribler_core.components.restapi.rest.events_endpoint import EventsEndpoint
from tribler_core.components.restapi.rest.rest_endpoint import RESTStreamResponse
from tribler_core.components.restapi.rest.rest_manager import ApiKeyMiddleware, RESTManager, error_middleware
from tribler_core.components.restapi.rest.root_endpoint import RootEndpoint
from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.notifier import Notifier
from tribler_core.version import version_id

messages_to_wait_for = set()


@pytest.fixture(name='api_port')
def fixture_api_port(free_port):
    return free_port


@pytest.fixture(name='notifier')
def fixture_notifier():
    return Notifier()


@pytest.fixture(name='endpoint')
def fixture_endpoint(notifier):
    return EventsEndpoint(notifier)


@pytest.fixture(name='reported_error')
def fixture_reported_error():
    return ReportedError('type', 'text', {})


@pytest.fixture
async def rest_manager(api_port, tmp_path, endpoint):
    config = TriblerConfig()
    config.api.http_enabled = True
    config.api.http_port = api_port
    root_endpoint = RootEndpoint(middlewares=[ApiKeyMiddleware(config.api.key), error_middleware])
    root_endpoint.add_endpoint('/events', endpoint)
    rest_manager = RESTManager(config=config.api, root_endpoint=root_endpoint, state_dir=tmp_path)

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


@pytest.mark.asyncio
@patch.object(EventsEndpoint, 'write_data')
@patch.object(EventsEndpoint, 'has_connection_to_gui', new=MagicMock(return_value=True))
async def test_on_tribler_exception_has_connection_to_gui(mocked_write_data, endpoint, reported_error):
    # test that in case of established connection to GUI, `on_tribler_exception` will work
    # as a normal endpoint function, that is call `write_data`
    endpoint.on_tribler_exception(reported_error)

    mocked_write_data.assert_called_once()
    assert not endpoint.undelivered_error


@pytest.mark.asyncio
@patch.object(EventsEndpoint, 'write_data')
@patch.object(EventsEndpoint, 'has_connection_to_gui', new=MagicMock(return_value=False))
async def test_on_tribler_exception_no_connection_to_gui(mocked_write_data, endpoint, reported_error):
    # test that if no connection to GUI, then `on_tribler_exception` will store
    # reported_error in `self.undelivered_error`
    endpoint.on_tribler_exception(reported_error)

    mocked_write_data.assert_not_called()
    assert endpoint.undelivered_error == endpoint.error_message(reported_error)


@pytest.mark.asyncio
@patch.object(EventsEndpoint, 'write_data', new=MagicMock())
@patch.object(EventsEndpoint, 'has_connection_to_gui', new=MagicMock(return_value=False))
async def test_on_tribler_exception_stores_only_first_error(endpoint, reported_error):
    # test that if no connection to GUI, then `on_tribler_exception` will store
    # only the very first `reported_error`
    first_reported_error = reported_error
    endpoint.on_tribler_exception(first_reported_error)

    second_reported_error = ReportedError('second_type', 'second_text', {})
    endpoint.on_tribler_exception(second_reported_error)

    assert endpoint.undelivered_error == endpoint.error_message(first_reported_error)


@pytest.mark.asyncio
@patch.object(EventsEndpoint, 'register_anonymous_task', new=AsyncMock(side_effect=CancelledError))
@patch.object(RESTStreamResponse, 'prepare', new=AsyncMock())
@patch.object(RESTStreamResponse, 'write', new_callable=AsyncMock)
@patch.object(EventsEndpoint, 'encode_message')
async def test_get_events_has_undelivered_error(mocked_encode_message, mocked_write, endpoint):
    # test that in case `self.undelivered_error` is not None, then it will be sent
    endpoint.undelivered_error = {'undelivered': 'error'}

    await endpoint.get_events(MagicMock())

    mocked_write.assert_called()
    mocked_encode_message.assert_called_with({'undelivered': 'error'})
    assert not endpoint.undelivered_error
