import json
from Tribler.Core.Utilities.twisted_thread import deferred
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest


class TestDebugEndpoint(AbstractApiTest):

    def setUpPreSession(self):
        super(TestDebugEndpoint, self).setUpPreSession()
        self.config.set_dispersy(True)

    @deferred(timeout=10)
    def test_get_community_statistics(self):
        """
        Testing whether the API returns a correct dictionary when the community statistics are fetched
        """
        def verify_community_statistics(result):
            json_dict = json.loads(result)
            self.assertTrue(json_dict["communities"])

        self.should_check_equality = False
        return self.do_request('debug/communities', expected_code=200).addCallback(verify_community_statistics)
