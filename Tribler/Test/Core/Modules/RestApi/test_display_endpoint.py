"""
This module validates the functions defined in the Display Endpoint
"""
from json import dumps
from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Modules.restapi.display_endpoint import DisplayEndpoint
from Tribler.Test.Core.base_test import MockObject
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

    def test_get_no_edges(self):
        """
        Evaluate whether the API passes the correct data if there are no edges returned.
        """
        self.mc_community.get_graph = lambda public_key, neighbor_level: (
            [{"public_key": "xyz", "total_up": 0, "total_down": 0, "page_rank": 0.5}], [])
        exp_message = {"focus_node": "30", "neighbor_level": 1, "nodes": [{"public_key": "xyz", "total_up": 0,
                                                                           "total_down": 0, "page_rank": 0.5}],
                       "edges": []}
        mocked_session = MockObject()
        display_endpoint = DisplayEndpoint(mocked_session)
        display_endpoint.get_multi_chain_community = lambda: self.mc_community
        request = MockObject()
        request.setHeader = lambda header, flags: None
        request.args = {"focus_node": ['30'], "neighbor_level": ['1']}
        self.assertEqual(dumps(exp_message), display_endpoint.render_GET(request))

    def test_get_edges(self):
        """
        Evaluate whether the API passes the correct data if there are edges returned.
        """
        self.mc_community.get_graph = lambda public_key, neighbor_level: (
            [{"public_key": "xyz", "total_up": 0, "total_down": 0, "page_rank": 0.5}], [
                {"from": "xyz", "to": "abc", "amount": 30}])
        exp_message = {"focus_node": "30", "neighbor_level": 1, "nodes": [{"public_key": "xyz", "total_up": 0,
                                                                           "total_down": 0, "page_rank": 0.5}],
                       "edges": [{"from": "xyz", "to": "abc", "amount": 30}]}
        mocked_session = MockObject()
        display_endpoint = DisplayEndpoint(mocked_session)
        display_endpoint.get_multi_chain_community = lambda: self.mc_community
        request = MockObject()
        request.setHeader = lambda header, flags: None
        request.args = {"focus_node": ['30'], "neighbor_level": ['1']}
        self.assertEqual(dumps(exp_message), display_endpoint.render_GET(request))

    def test_get_self(self):
        """
        Evaluate whether the API uses the own public key when public_key is set to 'self'.
        """
        self.mc_community.get_graph = lambda public_key, neighbor_level: (public_key, public_key)
        exp_message = {"focus_node": "30", "neighbor_level": 1, "nodes": "self",
                       "edges": "self"}
        mocked_session = MockObject()
        display_endpoint = DisplayEndpoint(mocked_session)
        display_endpoint.get_multi_chain_community = lambda: self.mc_community
        request = MockObject()
        request.setHeader = lambda header, flags: None
        request.args = {"focus_node": ['self'], "neighbor_level": ['1']}
        self.assertNotEquals(dumps(exp_message), display_endpoint.render_GET(request))
