from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.twisted_thread import deferred


class TestStateEndpoint(AbstractApiTest):

    @deferred(timeout=10)
    def test_get_state(self):
        """
        Testing whether the API returns a correct state when requested
        """
        self.session.lm.api_manager.root_endpoint.state_endpoint.on_tribler_exception("abcd")
        expected_json = {"state": "EXCEPTION", "last_exception": "abcd"}
        return self.do_request('state', expected_code=200, expected_json=expected_json)
