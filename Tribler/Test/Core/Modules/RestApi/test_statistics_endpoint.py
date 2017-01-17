import json

from Tribler.Core.Utilities.twisted_thread import deferred
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest


class TestStatisticsEndpoint(AbstractApiTest):

    def setUpPreSession(self):
        super(TestStatisticsEndpoint, self).setUpPreSession()
        self.config.set_dispersy(True)
        self.config.set_torrent_collecting(True)

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
            self.assertTrue(json.loads(data)["community_statistics"])

        self.should_check_equality = False
        return self.do_request('statistics/communities', expected_code=200).addCallback(verify_dict)
