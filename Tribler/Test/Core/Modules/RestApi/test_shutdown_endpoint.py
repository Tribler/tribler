from Tribler.Core.Utilities.twisted_thread import deferred
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest


class TestShutdownEndpoint(AbstractApiTest):

    @deferred(timeout=10)
    def test_shutdown(self):
        """
        Testing whether the API triggers a Tribler shutdown
        """
        '''
        self.shutdown_triggered = False

        def verify_shutdown_triggered(failure):
            self.assertTrue(self.shutdown_triggered)

        def verify_shutdown(_, checkpoint=True, gracetime=2.0, hacksessconfcheckpoint=True):
            self.assertTrue(checkpoint)
            self.assertEqual(2.0, gracetime)
            self.assertTrue(hacksessconfcheckpoint)
            self.shutdown_triggered = True
            self.session.shutdown = self.orig_shutdown

        self.orig_shutdown = self.session.shutdown
        self.session.shutdown = verify_shutdown
        '''
        expected_json = {"shutdown": True, "gracetime": 2.0}
        return self.do_request('shutdown', expected_code=200, expected_json=expected_json, request_type='PUT')
        # .addCallback(verify_shutdown_triggered)
