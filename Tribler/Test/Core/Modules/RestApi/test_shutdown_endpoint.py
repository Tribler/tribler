from twisted.internet import defer

from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.tools import trial_timeout


class TestShutdownEndpoint(AbstractApiTest):

    @trial_timeout(10)
    def test_shutdown(self):
        """
        Testing whether the API triggers a Tribler shutdown
        """
        self.orig_shutdown = self.session.shutdown
        self.shutdown_called = False

        def verify_shutdown_called(_):
            self.assertTrue(self.shutdown_called)

        def fake_shutdown():
            # Record session.shutdown was called
            self.shutdown_called = True
            # Restore original shutdown for test teardown
            self.session.shutdown = self.orig_shutdown
            return defer.Deferred()

        self.session.shutdown = fake_shutdown

        expected_json = {"shutdown": True}
        return self.do_request('shutdown', expected_code=200, expected_json=expected_json, request_type='PUT')\
            .addCallback(verify_shutdown_called)
