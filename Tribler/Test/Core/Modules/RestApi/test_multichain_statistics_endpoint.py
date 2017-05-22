import json

from twisted.internet.defer import inlineCallbacks

from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.twisted_thread import deferred
from Tribler.community.multichain.community import MultiChainCommunity
from Tribler.dispersy.dispersy import Dispersy
from Tribler.dispersy.endpoint import ManualEnpoint
from Tribler.dispersy.member import DummyMember
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestMultichainStatisticsEndpoint(AbstractApiTest):

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, autoload_discovery=True):
        yield super(TestMultichainStatisticsEndpoint, self).setUp(autoload_discovery=autoload_discovery)

        self.dispersy = Dispersy(ManualEnpoint(0), self.getStateDir())
        self.dispersy._database.open()
        master_member = DummyMember(self.dispersy, 1, "a" * 20)
        self.member = self.dispersy.get_new_member(u"curve25519")

        self.mc_community = MultiChainCommunity(self.dispersy, master_member, self.member)
        self.dispersy.get_communities = lambda: [self.mc_community]
        self.session.get_dispersy_instance = lambda: self.dispersy
        self.session.get_enable_multichain = lambda: True

    @deferred(timeout=10)
    def test_get_statistics_no_data(self):
        """
        Testing what the API returns if no multichain community is present.
        """
        public_key = '30'
        neighbor_level = 1

        def verify_response(response):
            response_json = json.loads(response)

            self.assertIn("focus_node", response_json)
            self.assertEqual(response_json["focus_node"], public_key)
            self.assertIn("neighbor_level", response_json)
            self.assertEqual(response_json["neighbor_level"], neighbor_level)
            self.assertIn("nodes", response_json)
            list_of_nodes = [node["public_key"] for node in response_json["nodes"]]
            self.assertListEqual([public_key], list_of_nodes)
            self.assertIn("edges", response_json)
            list_of_edges = response_json["edges"]
            self.assertListEqual(list_of_edges, [])


        self.should_check_equality = False
        request = 'display?focus_node=' + public_key + '&neighbor_level=' + str(neighbor_level) + "&dataset=static"
        return self.do_request(request,
                               expected_code=200).addCallback(verify_response)

    @deferred(timeout=10)
    def test_get_statistics(self):
        """
        Testing whether the API returns the correct statistics.
        """
        public_key = '0'
        neighbor_level = 1

        def verify_response(response):
            response_json = json.loads(response)

            self.assertIn("focus_node", response_json)
            self.assertEqual(response_json["focus_node"], public_key)
            self.assertIn("neighbor_level", response_json)
            self.assertEqual(response_json["neighbor_level"], neighbor_level)
            self.assertIn("nodes", response_json)
            list_of_nodes = response_json["nodes"]
            expected_neighbors = [public_key, '1', '2', '3', '4']
            returned_neighbors = []
            for node in list_of_nodes:
                self.assertIn("public_key", node)
                self.assertIn(node["public_key"], expected_neighbors)
                returned_neighbors.append(node["public_key"])
                self.assertIn("total_up", node)
                self.assertIn("total_down", node)
                self.assertIn("page_rank", node)
            for key in expected_neighbors:
                self.assertIn(key, returned_neighbors)
            self.assertIn("edges", response_json)
            list_of_edges = response_json["edges"]
            for edge in list_of_edges:
                self.assertIn("from", edge)
                self.assertIn("to", edge)
                self.assertIn("amount", edge)

        self.should_check_equality = False
        request = 'display?focus_node=' + public_key + '&neighbor_level=' + str(neighbor_level) + "&dataset=static"
        return self.do_request(request, expected_code=200).addCallback(verify_response)
