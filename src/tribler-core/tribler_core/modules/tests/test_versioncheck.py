import json
from asyncio import sleep

from aiohttp import web

from tribler_core.modules import versioncheck_manager
from tribler_core.modules.versioncheck_manager import VersionCheckManager
from tribler_core.restapi.rest_endpoint import RESTResponse
from tribler_core.tests.tools.test_as_server import TestAsServer
from tribler_core.tests.tools.tools import timeout


class TestVersionCheck(TestAsServer):

    async def setUp(self):
        self.port = self.get_port()
        self.site = None
        self.should_call_new_version_callback = False
        self.new_version_called = False
        versioncheck_manager.VERSION_CHECK_URL = 'http://localhost:%s' % self.port
        await super(TestVersionCheck, self).setUp()
        self.session.version_check_manager = VersionCheckManager(self.session)

        self.session.notifier.notify = self.notifier_callback

    def notifier_callback(self, subject, changeType, obj_id, *args):
        self.new_version_called = True

    async def setup_version_server(self, response, response_code=200):
        self.response = response
        self.response_code = response_code

        app = web.Application()
        app.add_routes([web.get('/{tail:.*}', self.handle_version_request)])
        runner = web.AppRunner(app, access_log=None)
        await runner.setup()
        self.site = web.TCPSite(runner, 'localhost', self.port)
        await self.site.start()

    def handle_version_request(self, request):
        return RESTResponse(self.response, status=self.response_code)

    async def assert_new_version_called(self, _res):
        self.assertTrue(self.new_version_called == self.should_call_new_version_callback)
        return await self.site.stop()

    async def check_version(self):
        await self.session.version_check_manager.check_new_version()
        self.assertTrue(self.new_version_called == self.should_call_new_version_callback)
        return await self.site.stop()

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
        versioncheck_manager.VERSION_CHECK_URL = "http://this.will.not.exist"
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
