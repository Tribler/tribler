from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.twisted_thread import deferred


class TestAliveEndpoint(AbstractApiTest):

    @deferred(timeout=10)
    def test_get_variables(self):
        """
        Testing whether the API returns a correct alive response
        """
        expected_json = {"alive": True}
        return self.do_request('alive', expected_code=200, expected_json=expected_json)
