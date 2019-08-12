from asyncio import get_event_loop, sleep

from Tribler.Core.Utilities.utilities import succeed
from Tribler.Test.tools import timeout
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.Core.base_test import MockObject


class TestShutdownEndpoint(AbstractApiTest):

    @timeout(10)
    async def test_shutdown(self):
        """
        Testing whether the API triggers a Tribler shutdown
        """
        self.orig_shutdown = self.session.shutdown
        self.shutdown_called = False

        def fake_shutdown():
            # Record session.shutdown was called
            self.shutdown_called = True
            # Restore original shutdown for test teardown
            self.session.shutdown = self.orig_shutdown
            loop = MockObject()
            loop.stop = lambda: None
            return succeed(loop)

        self.session.shutdown = fake_shutdown

        expected_json = {"shutdown": True}
        await self.do_request('shutdown', expected_code=200, expected_json=expected_json, request_type='PUT')
        self.assertTrue(self.shutdown_called)
