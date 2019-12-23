from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.tools import timeout


class TestStateEndpoint(AbstractApiTest):

    @timeout(10)
    async def test_get_state(self):
        """
        Testing whether the API returns a correct state when requested
        """
        self.session.api_manager.root_endpoint.endpoints['/state'].on_tribler_exception("abcd")
        expected_json = {"state": "EXCEPTION", "last_exception": "abcd", "readable_state": "Started"}
        await self.do_request('state', expected_code=200, expected_json=expected_json)
