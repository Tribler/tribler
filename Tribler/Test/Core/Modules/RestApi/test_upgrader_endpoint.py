from __future__ import absolute_import

from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.tools import trial_timeout


class TestShutdownEndpoint(AbstractApiTest):


    @trial_timeout(10)
    def test_upgrader_skip(self):
        """
        Testing whether the API triggers a Tribler shutdown
        """

        self.skip_called = False

        def verify_skip_called(_):
            self.assertTrue(self.skip_called)

        def mock_skip():
            self.skip_called = True

        self.session.upgrader = MockObject()
        self.session.upgrader.skip = mock_skip

        expected_json = {"skip": True}
        return self.do_request('upgrader', expected_code=200, expected_json=expected_json, request_type='DELETE') \
            .addCallback(verify_skip_called)
