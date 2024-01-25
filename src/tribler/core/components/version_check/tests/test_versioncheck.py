import platform
from asyncio import sleep
from dataclasses import dataclass
from ssl import SSLError
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from aiohttp import web

from tribler.core.components.restapi.rest.rest_endpoint import RESTResponse
from tribler.core.components.version_check import versioncheck_manager
from tribler.core.components.version_check.versioncheck_manager import VersionCheckManager
from tribler.core.utilities.aiohttp.exceptions import AiohttpException
from tribler.core.version import version_id

# pylint: disable=redefined-outer-name, protected-access

# Assuming this is always a newer version id
new_version = '{"name": "v1337.0"}'
first_version = '{"name": "v1.0"}'


@pytest.fixture()
async def version_check_manager(free_port: int):
    check_manager = VersionCheckManager(notifier=MagicMock(), urls=[f"http://localhost:{free_port}"])
    yield check_manager
    await check_manager.stop()


@dataclass
class ResponseSettings:
    response = new_version
    response_code = 200
    response_lag = 0  # in seconds


@pytest.fixture()
async def version_server(free_port: int, version_check_manager: VersionCheckManager):
    async def handle_version_request(_):
        settings = ResponseSettings()
        if settings.response_lag > 0:
            await sleep(settings.response_lag)
        return RESTResponse(settings.response, status=settings.response_code)

    app = web.Application()
    app.add_routes([web.get('/{tail:.*}', handle_version_request)])
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', free_port)
    await site.start()
    yield version_check_manager
    await site.stop()


async def test_start(version_check_manager: VersionCheckManager):
    """
    Test whether the periodic version lookup works as expected
    """
    version_check_manager.start()
    # We only start the version check if GIT is not in the version ID.
    assert not version_check_manager.is_pending_task_active("tribler version check")

    old_id = versioncheck_manager.version_id
    versioncheck_manager.version_id = "7.0.0"
    version_check_manager.start()
    await sleep(0.1)  # Wait a bit for the check to complete
    assert version_check_manager.is_pending_task_active("tribler version check")
    versioncheck_manager.version_id = old_id


@patch('platform.machine', Mock(return_value='machine'))
@patch('platform.system', Mock(return_value='os'))
@patch('platform.release', Mock(return_value='1'))
@patch('platform.python_version', Mock(return_value='3.0.0'))
@patch('platform.architecture', Mock(return_value=('64bit', 'FooBar')))
async def test_user_agent(version_server: VersionCheckManager):
    expected = f'Tribler/{version_id} (machine=machine; os=os 1; python=3.0.0; executable=64bit)'

    with patch('tribler.core.components.version_check.versioncheck_manager.query_uri') as mocked_query_uri:
        await version_server._check_urls()
        actual = mocked_query_uri.call_args.kwargs['headers']['User-Agent']
        assert actual == expected


@patch.object(ResponseSettings, 'response', first_version)
async def test_old_version(version_server: VersionCheckManager):
    result = await version_server._check_urls()
    assert not result


async def test_new_version(version_server: VersionCheckManager):
    result = await version_server._check_urls()
    assert result


@patch.object(ResponseSettings, 'response_code', 500)
async def test_bad_request(version_server: VersionCheckManager):
    result = await version_server._check_urls()
    assert not result


async def test_connection_error(version_check_manager: VersionCheckManager):
    version_check_manager.urls = ["http://this.will.not.exist"]
    result = await version_check_manager._check_urls()
    assert not result


@patch.object(ResponseSettings, 'response_lag', 1)  # Ensures that it takes 1 seconds to send a response
async def test_version_check_api_timeout(version_server: VersionCheckManager):
    version_server.timeout = 0.5

    # Since the time to respond is higher than the time version checker waits for response,
    # it should raise the `AiohttpException`
    with pytest.raises(AiohttpException):
        await version_server._raw_request_new_version(version_server.urls[0])


async def test_fallback_on_multiple_urls(version_server: VersionCheckManager):
    """
    Scenario: Two release API URLs. First one is a non-existing URL so is expected to fail.
    The second one is of a local webserver (http://localhost:{port}) which is configured to
    return a new version available response. Here we test if the version checking still works
    if the first URL fails.
    """
    urls = version_server.urls

    # no results
    version_server.urls = ["http://this.will.not.exist"]
    assert not await version_server._check_urls()

    # results
    version_server.urls.extend(urls)
    assert await version_server._check_urls()


@patch('platform.machine', Mock(return_value='AMD64'))
@patch('platform.system', Mock(return_value='Windows'))
@patch('platform.release', Mock(return_value='10'))
@patch('platform.python_version', Mock(return_value='3.9.1'))
@patch('platform.architecture', Mock(return_value=('64bit', 'WindowsPE')))
def test_useragent_string():
    s = VersionCheckManager._get_user_agent_string('1.2.3', platform)
    assert s == 'Tribler/1.2.3 (machine=AMD64; os=Windows 10; python=3.9.1; executable=64bit)'


async def test_check_urls_error(version_server: VersionCheckManager):
    # This test ensures that there is no Application crash in the case of failed new version request.
    # see: https://github.com/Tribler/tribler/issues/5816

    # first check that the `_check_urls` returns expected value if there is no errors
    with patch.object(VersionCheckManager, '_raw_request_new_version', AsyncMock(return_value={'name': 'mock'})):
        actual = await version_server._check_urls()
        assert actual == {'name': 'mock'}

    # second check that the `_check_urls` returns None if there is an error
    with patch.object(VersionCheckManager, '_raw_request_new_version', AsyncMock(side_effect=SSLError)):
        actual = await version_server._check_urls()
        assert not actual
