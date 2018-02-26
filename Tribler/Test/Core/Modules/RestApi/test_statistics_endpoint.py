import Tribler.Core.Utilities.json_util as json
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.twisted_thread import deferred


class TestStatisticsEndpoint(AbstractApiTest):

    def setUpPreSession(self):
        super(TestStatisticsEndpoint, self).setUpPreSession()
        self.config.set_dispersy_enabled(True)
        self.config.set_ipv8_enabled(True)
        self.config.set_torrent_collecting_enabled(True)

    @deferred(timeout=10)
    def test_get_tribler_statistics(self):
        """
        Testing whether the API returns a correct Tribler statistics dictionary when requested
        """
        def verify_dict(data):
            self.assertTrue(json.loads(data)["tribler_statistics"])

        self.should_check_equality = False
        return self.do_request('statistics/tribler', expected_code=200).addCallback(verify_dict)

    @deferred(timeout=10)
    def test_get_dispersy_statistics(self):
        """
        Testing whether the API returns a correct Dispersy statistics dictionary when requested
        """
        def verify_dict(data):
            self.assertTrue(json.loads(data)["dispersy_statistics"])

        self.should_check_equality = False
        return self.do_request('statistics/dispersy', expected_code=200).addCallback(verify_dict)

    @deferred(timeout=10)
    def test_get_community_statistics(self):
        """
        Testing whether the API returns a correct community statistics dictionary when requested
        """
        def verify_dict(data):
            self.assertTrue(json.loads(data)["dispersy_community_statistics"])

        self.should_check_equality = False
        return self.do_request('statistics/communities', expected_code=200).addCallback(verify_dict)
