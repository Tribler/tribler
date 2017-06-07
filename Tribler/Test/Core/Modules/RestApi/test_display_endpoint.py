
"""
This module validates the functions defined in the Display Endpoint
"""
from twisted.internet.defer import inlineCallbacks

from Tribler.community.multichain.community import MultiChainCommunity
from Tribler.dispersy.dispersy import Dispersy
from Tribler.dispersy.endpoint import ManualEnpoint
from Tribler.dispersy.member import DummyMember
from Tribler.dispersy.util import blocking_call_on_reactor_thread
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.twisted_thread import deferred


class TestDisplayEndpoint(AbstractApiTest):
    """
    Evaluate the DisplayEndpoint, the endpoint from which you can retrieve aggregated data from the multichain.
    """

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, autoload_discovery=True):
        yield super(TestDisplayEndpoint, self).setUp(autoload_discovery=autoload_discovery)

        self.dispersy = Dispersy(ManualEnpoint(0), self.getStateDir())
        self.dispersy._database.open()
        master_member = DummyMember(self.dispersy, 1, "a" * 20)
        self.member = self.dispersy.get_new_member(u"curve25519")

        self.mc_community = MultiChainCommunity(self.dispersy, master_member, self.member)
        self.dispersy.get_communities = lambda: [self.mc_community]
        self.session.get_dispersy_instance = lambda: self.dispersy

    @deferred(timeout=10)
    def test_get_no_focus_node(self):
        """
        Evaluate whether the API returns an Bad Request error if there is no focus node specified.
        """
        exp_message = {"error": "focus_node parameter missing"}
        return self.do_request('display?neighbor_level=1', expected_code=400, expected_json=exp_message)

    @deferred(timeout=10)
    def test_get_empty_focus_node(self):
        """
        Evaluate whether the API returns a Bad Request error if the focus node is empty.
        """
        exp_message = {"error": "focus_node parameter empty"}
        return self.do_request('display?focus_node=&neighbor_level=1', expected_code=400, expected_json=exp_message)

    @deferred(timeout=10)
    def test_get_neighbor_level_string(self):
        """
        Evaluate whether the API uses the default neighbor_level if the parameter is set to a string.
        """
        # TODO: The dummy data is now expected, make sure to rewrite test if actual implementation is used
        exp_message = {"focus_node": "xyz", "neighbor_level": 1, "nodes": [{"public_key": "xyz", "total_up": 0,
                                                                            "total_down": 0, "page_rank": 0.5}],
                       "edges": []}
        return self.do_request('display?focus_node=xyz&neighbor_level=x', expected_code=200, expected_json=exp_message)

    @deferred(timeout=10)
    def test_get_neighbor_level_zero(self):
        """
        Evaluate whether the API uses the actual neighbor_level if the parameter is set.
        """
        # TODO: The dummy data is now expected, make sure to rewrite test if actual implementation is used
        exp_message = {"focus_node": "xyz", "neighbor_level": 0, "nodes": [{"public_key": "xyz", "total_up": 0,
                                                                            "total_down": 0, "page_rank": 0.5}],
                       "edges": []}
        return self.do_request('display?focus_node=xyz&neighbor_level=0', expected_code=200, expected_json=exp_message)

    @deferred(timeout=10)
    def test_get_int_focus_node(self):
        """
        Evaluate whether the API returns a Bad Request error if the focus node is an integer.
        """
        exp_message = {"error": "focus_node was not a string"}
        return self.do_request('display?focus_node=-1&neighbor_level=1', expected_code=400, expected_json=exp_message)

        # TODO: Add method which tests:
        # Evaluate whether the API returns the information about the own node if self is used as focus_node parameter.
