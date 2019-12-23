from Tribler.Core.Modules.restapi.upgrader_endpoint import SKIP_DB_UPGRADE_STR
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.tools import timeout


class TestUpgraderEndpoint(AbstractApiTest):

    @timeout(10)
    async def test_upgrader_skip(self):
        """
        Test if the API call sets the "skip DB upgrade" flag in upgrader
        """

        post_params = {SKIP_DB_UPGRADE_STR: True}
        await self.do_request('upgrader', expected_code=404, post_data=post_params, request_type='POST')

        self.skip_called = False

        def mock_skip():
            self.skip_called = True

        self.session.upgrader = MockObject()
        self.session.upgrader.skip = mock_skip

        await self.do_request('upgrader', expected_code=400, expected_json={
            u'error': u'attribute to change is missing'}, post_data={}, request_type='POST')

        await self.do_request('upgrader', expected_code=200, expected_json={SKIP_DB_UPGRADE_STR: True},
                              post_data=post_params, request_type='POST')
        self.assertTrue(self.skip_called)
