import json
from asyncio import sleep

from aiohttp import web

import pytest

from tribler_core.modules import versioncheck_manager
from tribler_core.modules.versioncheck_manager import VersionCheckManager
from tribler_core.restapi.rest_endpoint import RESTResponse


@pytest.fixture
async def version_check_manager(free_port, session):
    versioncheck_manager.VERSION_CHECK_URL = 'http://localhost:%s' % free_port
    version_check_manager = VersionCheckManager(session)
    yield version_check_manager
    await version_check_manager.stop()


response = None
response_code = 200


def handle_version_request(_):
    global response, response_code
    return RESTResponse(response, status=response_code)


@pytest.fixture
async def version_server(free_port):
    global response_code
    response_code = 200
    app = web.Application()
    app.add_routes([web.get('/{tail:.*}', handle_version_request)])
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', free_port)
    await site.start()
    yield free_port
    await site.stop()


@pytest.mark.asyncio
async def test_start(version_check_manager, version_server):
    """
    Test whether the periodic version lookup works as expected
    """
    global response
    response = json.dumps({'name': 'v1.0'})

    version_check_manager.start()
    # We only start the version check if GIT is not in the version ID.
    assert not version_check_manager.is_pending_task_active("tribler version check")

    import tribler_core.modules.versioncheck_manager as vcm
    old_id = vcm.version_id
    vcm.version_id = "7.0.0"
    version_check_manager.start()
    await sleep(0.1)  # Wait a bit for the check to complete
    assert version_check_manager.is_pending_task_active("tribler version check")
    vcm.version_id = old_id


@pytest.mark.asyncio
async def test_old_version(version_check_manager, version_server):
    global response
    response = json.dumps({'name': 'v1.0'})
    has_new_version = await version_check_manager.check_new_version()
    assert not has_new_version


@pytest.mark.asyncio
async def test_new_version(version_check_manager, version_server):
    global response
    response = json.dumps({'name': 'v1337.0'})
    has_new_version = await version_check_manager.check_new_version()
    assert has_new_version


@pytest.mark.asyncio
async def test_bad_request(version_check_manager, version_server):
    global response, response_code
    response = json.dumps({'name': 'v1.0'})
    response_code = 500
    has_new_version = await version_check_manager.check_new_version()
    assert not has_new_version


@pytest.mark.asyncio
async def test_connection_error(version_check_manager):
    global response
    response = json.dumps({'name': 'v1.0'})
    versioncheck_manager.VERSION_CHECK_URL = "http://this.will.not.exist"
    has_new_version = await version_check_manager.check_new_version()
    assert not has_new_version


@pytest.mark.asyncio
async def test_non_json_response(version_check_manager, version_server):
    global response
    response = 'hello world - not json'

    versioncheck_manager.check_failed = False
    with pytest.raises(ValueError):
        await version_check_manager.check_new_version()
