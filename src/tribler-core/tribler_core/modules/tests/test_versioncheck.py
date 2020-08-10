import json
from asyncio import sleep

from aiohttp import web

from asynctest import Mock

from tribler_core.modules import versioncheck_manager
from tribler_core.modules.versioncheck_manager import VersionCheckManager
from tribler_core.restapi.rest_endpoint import RESTResponse
from tribler_core.tests.tools.test_as_server import TestAsServer
from tribler_core.tests.tools.tools import timeout


class TestVersionCheck(TestAsServer):

    async def setUp(self):
        self.port = self.get_port()
        self.runner = None
        self.should_call_new_version_callback = False
        self.new_version_called = False
        versioncheck_manager.VERSION_CHECK_URLS = ['http://localhost:%s' % self.port]
        await super(TestVersionCheck, self).setUp()
        self.session.version_check_manager = VersionCheckManager(self.session)

        self.session.notifier.notify = Mock()

    def notifier_callback(self, subject, *args):
        self.new_version_called = True

    async def tearDown(self):
        if self.runner:
            await self.runner.shutdown()

        await super(TestVersionCheck, self).tearDown()

    async def setup_version_server(self, response, response_code=200):
        self.response = response
        self.response_code = response_code

        app = web.Application()
        app.add_routes([web.get('/{tail:.*}', self.handle_version_request)])
        self.runner = web.AppRunner(app, access_log=None)
        await self.runner.setup()
        site = web.TCPSite(self.runner, 'localhost', self.port)
        await site.start()

    def handle_version_request(self, request):
        return RESTResponse(self.response, status=self.response_code)

    async def assert_new_version_called(self):
        if self.should_call_new_version_callback:
            self.session.notifier.notify.assert_called_once()
        else:
            self.session.notifier.notify.assert_not_called()

    async def check_version(self):
        await self.session.version_check_manager.check_new_version()
        await self.assert_new_version_called()

    @timeout(10)
    async def test_start(self):
        """
        Test whether the periodic version lookup works as expected
        """
        await self.setup_version_server(json.dumps({'name': 'v1.0'}))
        self.session.version_check_manager.start()
        self.assertFalse(self.session.version_check_manager.is_pending_task_active("tribler version check"))

        import tribler_core.modules.versioncheck_manager as vcm
        vcm.version_id = "7.0.0"
        self.session.version_check_manager.start()
        await sleep(0.4)  # Wait a bit for the check to complete
        self.assertTrue(self.session.version_check_manager.is_pending_task_active("tribler version check"))

    @timeout(10)
    async def test_old_version(self):
        await self.setup_version_server(json.dumps({'name': 'v1.0'}))
        await self.check_version()

    @timeout(10)
    async def test_new_version(self):
        self.should_call_new_version_callback = True
        await self.setup_version_server(json.dumps({'name': 'v1337.0'}))
        await self.check_version()

    @timeout(20)
    async def test_bad_request(self):
        await self.setup_version_server(json.dumps({'name': 'v1.0'}), response_code=500)
        await self.check_version()

    @timeout(20)
    async def test_connection_error(self):
        await self.setup_version_server(json.dumps({'name': 'v1.0'}))
        versioncheck_manager.VERSION_CHECK_URLS = ["http://this.will.not.exist"]
        await self.check_version()

    @timeout(20)
    async def test_non_json_response(self):
        await self.setup_version_server('hello world - not json')

        versioncheck_manager.check_failed = False
        try:
            await self.check_version()
        except:
            versioncheck_manager.check_failed = True

        self.assertTrue(versioncheck_manager.check_failed)

    @timeout(10)
    async def test_version_check_timeout(self):
        await self.setup_version_server(json.dumps({'name': 'v1337.0'}))

        # Setting a timeout of 1ms, version checks should fail
        versioncheck_manager.VERSION_CHECK_TIMEOUT = 0.001
        self.should_call_new_version_callback = False
        await self.check_version()

    @timeout(20)
    async def test_fallback_on_multiple_urls(self):
        """
        Scenario: Two release API URLs. First one is a non-existing URL so is expected to fail.
        The second one is of a local webserver (http://localhost:{port}) which is configured to
        return a new version available response. Here we test if the version checking still works
        if the first URL fails.
        """
        versioncheck_manager.VERSION_CHECK_URLS = ["http://this.will.not.exist",
                                                   f"http://localhost:{self.port}"]

        # Local server which responds with a new version available on the API response
        await self.setup_version_server(json.dumps({'name': 'v1337.0'}))

        self.should_call_new_version_callback = True
        await self.check_version()
