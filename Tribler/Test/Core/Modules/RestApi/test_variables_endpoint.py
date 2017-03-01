from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.twisted_thread import deferred


class TestVariablesEndpoint(AbstractApiTest):

    @deferred(timeout=10)
    def test_get_variables(self):
        """
        Testing whether the API returns a correct variables dictionary when the variables are requested
        """
        expected_json = {"variables": {"ports": self.session.selected_ports}}
        return self.do_request('variables', expected_code=200, expected_json=expected_json)
