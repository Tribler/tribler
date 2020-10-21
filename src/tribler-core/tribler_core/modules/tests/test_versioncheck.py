import json
from asyncio import sleep

from aiohttp import web

import pytest

from tribler_core.modules import versioncheck_manager
from tribler_core.modules.versioncheck_manager import VersionCheckManager
from tribler_core.restapi.rest_endpoint import RESTResponse

# Assuming this is always a newer version id
NEW_VERSION_ID = 'v1337.0'


@pytest.fixture(name='version_check_manager')
async def fixture_version_check_manager(free_port, session):
    versioncheck_manager.VERSION_CHECK_URLS = [f"http://localhost:{free_port}"]
    version_check_manager = VersionCheckManager(session)
    yield version_check_manager
    await version_check_manager.stop()


response = None
response_code = 200
response_lag = 0  # in seconds


async def handle_version_request(_):
    global response, response_code, response_lag  # pylint: disable=global-statement
    if response_lag > 0:
        await sleep(response_lag)
    return RESTResponse(response, status=response_code)


@pytest.fixture(name='version_server')
async def fixture_version_server(free_port):
    global response_code  # pylint: disable=global-statement
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
    global response  # pylint: disable=global-statement
    response = json.dumps({'name': 'v1.0'})

    version_check_manager.start()
    # We only start the version check if GIT is not in the version ID.
    assert not version_check_manager.is_pending_task_active("tribler version check")

    import tribler_core.modules.versioncheck_manager as vcm  # pylint: disable=reimported, import-outside-toplevel
    old_id = vcm.version_id
    vcm.version_id = "7.0.0"
    version_check_manager.start()
    await sleep(0.1)  # Wait a bit for the check to complete
    assert version_check_manager.is_pending_task_active("tribler version check")
    vcm.version_id = old_id


@pytest.mark.asyncio
async def test_old_version(version_check_manager, version_server):
    global response  # pylint: disable=global-statement
    response = json.dumps({'name': 'v1.0'})
    has_new_version = await version_check_manager.check_new_version()
    assert not has_new_version


@pytest.mark.asyncio
async def test_new_version(version_check_manager, version_server):
    global response  # pylint: disable=global-statement
    response = json.dumps({'name': NEW_VERSION_ID})
    has_new_version = await version_check_manager.check_new_version()
    assert has_new_version


@pytest.mark.asyncio
async def test_bad_request(version_check_manager, version_server):
    global response, response_code  # pylint: disable=global-statement
    response = json.dumps({'name': 'v1.0'})
    response_code = 500
    has_new_version = await version_check_manager.check_new_version()
    assert not has_new_version


@pytest.mark.asyncio
async def test_connection_error(version_check_manager):
    global response  # pylint: disable=global-statement
    response = json.dumps({'name': 'v1.0'})
    versioncheck_manager.VERSION_CHECK_URLS = ["http://this.will.not.exist"]
    has_new_version = await version_check_manager.check_new_version()
    assert not has_new_version


@pytest.mark.asyncio
async def test_non_json_response(version_check_manager, version_server):
    global response  # pylint: disable=global-statement
    response = 'hello world - not json'

    versioncheck_manager.check_failed = False
    with pytest.raises(ValueError):
        await version_check_manager.check_new_version()


@pytest.mark.asyncio
async def test_version_check_timeout(version_check_manager, version_server):
    global response  # pylint: disable=global-statement
    response = json.dumps({'name': NEW_VERSION_ID})

    import tribler_core.modules.versioncheck_manager as vcm  # pylint: disable=reimported, import-outside-toplevel
    old_timeout = vcm.VERSION_CHECK_TIMEOUT
    vcm.VERSION_CHECK_TIMEOUT = 0.001

    has_new_version = await version_check_manager.check_new_version()
    assert not has_new_version

    vcm.VERSION_CHECK_TIMEOUT = old_timeout


@pytest.mark.asyncio
async def test_version_check_api_timeout(free_port, version_check_manager, version_server):
    global response, response_lag  # pylint: disable=global-statement
    response = json.dumps({'name': NEW_VERSION_ID})
    response_lag = 2  # Ensures that it takes 2 seconds to send a response

    import tribler_core.modules.versioncheck_manager as vcm  # pylint: disable=reimported, import-outside-toplevel
    old_timeout = vcm.VERSION_CHECK_TIMEOUT
    vcm.VERSION_CHECK_TIMEOUT = 1  # version checker will wait for 1 second to get response

    version_check_url = f"http://localhost:{free_port}"
    # Since the time to respond is higher than the time version checker waits for response,
    # it should cancel the request and return False
    has_new_version = await version_check_manager.check_new_version_api(version_check_url)
    assert not has_new_version

    vcm.VERSION_CHECK_TIMEOUT = old_timeout


@pytest.mark.asyncio
async def test_fallback_on_multiple_urls(free_port, version_check_manager, version_server):
    """
    Scenario: Two release API URLs. First one is a non-existing URL so is expected to fail.
    The second one is of a local webserver (http://localhost:{port}) which is configured to
    return a new version available response. Here we test if the version checking still works
    if the first URL fails.
    """
    global response  # pylint: disable=global-statement
    response = json.dumps({'name': NEW_VERSION_ID})

    import tribler_core.modules.versioncheck_manager as vcm  # pylint: disable=reimported, import-outside-toplevel
    vcm_old_urls = vcm.VERSION_CHECK_URLS
    vcm.VERSION_CHECK_URLS = ["http://this.will.not.exist", f"http://localhost:{free_port}"]

    has_new_version = await version_check_manager.check_new_version()
    assert has_new_version

    vcm.VERSION_CHECK_URLS = vcm_old_urls
