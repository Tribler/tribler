"""
This module validates the functions defined in the TrustchainNetworkEndpoint Endpoint
"""
from binascii import unhexlify
from json import dumps
from sys import maxint

from twisted.internet.defer import inlineCallbacks, Deferred
from twisted.web import http

from Tribler.Core.Modules.restapi.trustchain_endpoint import TrustChainNetworkEndpoint
from Tribler.Core.exceptions import OperationNotEnabledByConfigurationException
from Tribler.Test.Community.AbstractTestCommunity import AbstractTestCommunity
from Tribler.community.triblerchain.community import TriblerChainCommunity
from Tribler.dispersy.util import blocking_call_on_reactor_thread
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.twisted_thread import deferred


class TestTrustchainNetworkEndpoint(AbstractApiTest, AbstractTestCommunity):
    """
    Evaluate the TrustNetworkEndpoint, the endpoint from which you can retrieve
    aggregated data from the trustchain.
    """

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, autoload_discovery=True):
        yield super(TestTrustchainNetworkEndpoint, self).setUp(autoload_discovery=autoload_discovery)

        self.tc_community = TriblerChainCommunity(self.dispersy, self.master_member, self.member)
        self.tc_community.initialize()
        self.dispersy._communities["a" * 20] = self.tc_community
        self.session.get_dispersy_instance = lambda: self.dispersy

    def set_up_endpoint_request(self, focus_node, neighbor_level, max_neighbors=1):
        """
        Create a mocked session, create a TrustchainNetworkEndpoint instance
        and create a request from the provided parameters.

        :param focus_node: node for which to request the data
        :param neighbor_level: amount of levels from this node to request
        :return: a 2-tuple of the TrustchainNetworkEndpoint and the request
        """
        mocked_session = MockObject()
        network_endpoint = TrustChainNetworkEndpoint(mocked_session)
        network_endpoint.get_tribler_chain_community = lambda: self.tc_community
        request = MockObject()
        request.setHeader = lambda header, flags: None
        request.setResponseCode = lambda status_code: None
        request.args = {"focus_node": [str(focus_node)],
                        "neighbor_level": [str(neighbor_level)],
                        "max_neighbors": [str(max_neighbors)]}
        return network_endpoint, request

    def test_get_empty_focus_node(self):
        """
        Evaluate whether the API returns a Bad Request error if the focus node is empty.
        """
        exp_message = {"error": "focus_node parameter empty"}
        network_endpoint, request = self.set_up_endpoint_request("X", 1)
        request.args["focus_node"] = [""]
        self.assertEqual(dumps(exp_message), network_endpoint.render_GET(request))

    def test_max_neighbors(self):
        """
        Evaluate whether the max_neighbors argument is correctly parsed.
        """
        network_endpoint, request = self.set_up_endpoint_request("X", 1, 4)
        self.assertEqual(4, network_endpoint.get_max_neighbors(request.args))

    def test_no_max_neighbors(self):
        """
        Evaluate whether max_neighbors return the correct default value when the argument is not present.
        """
        network_endpoint, request = self.set_up_endpoint_request("X", 1, 4)
        del request.args["max_neighbors"]
        self.assertEqual(maxint, network_endpoint.get_max_neighbors(request.args))

    def test_negative_max_neighbors(self):
        """
        Evaluate whether max_neighbors return the correct default value when the argument is negative.
        """
        network_endpoint, request = self.set_up_endpoint_request("X", 1, 4)
        request.args["max_neighbors"] = ["-1"]
        self.assertEqual(maxint, network_endpoint.get_max_neighbors(request.args))

    def test_mandatory_nodes(self):
        """
        Evaluate whether the mandatory_nodes function works correctly.
        """
        arguments = {"mandatory_nodes": ["x,y,z"]}
        expected_result = ["x", "y", "z"]
        self.assertEqual(TrustChainNetworkEndpoint.get_mandatory_nodes(arguments), expected_result)

    @staticmethod
    def setup_mock_community(public_key):
        """
        Set up a fake community to use for testing.
        :param public_key: public key of the my_member in the community
        :return: deferred object to trigger callback chain on
        """
        mock_community = MockObject()
        mock_community.my_member = MockObject()
        mock_community.my_member.public_key = unhexlify(public_key)
        mock_community.persistence = MockObject()
        mock_community.persistence.dummy_setup = False
        d = Deferred()
        mock_community.get_graph = lambda _1, _2, _3, _4: d
        TrustChainNetworkEndpoint.get_tribler_chain_community = lambda _: mock_community
        return d

    @deferred(timeout=10)
    def test_get_no_edges(self):
        """
        Evaluate whether the API passes the correct data if there are no edges returned.
        """
        d = self.setup_mock_community("0000")
        exp_message = {u"user_node": u"0000",
                       u"focus_node": u"30",
                       u"neighbor_level": 1,
                       u"nodes": [{u"public_key": u"xyz", u"total_up": 0, u"total_down": 0, u"score": 0.5}],
                       u"edges": []}
        d.callback(([{"public_key": "xyz", "total_up": 0, "total_down": 0, "score": 0.5}], []))
        return self.do_request('trustchain/network?focus_node=30&neighbor_level=1',
                               expected_code=200, expected_json=exp_message)\
            .addCallback(lambda message: self.assertEqual(message, dumps(exp_message)))

    @deferred(timeout=10)
    def test_get_edges(self):
        """
        Evaluate whether the API passes the correct data if there are edges returned.
        """
        d = self.setup_mock_community("0000")
        exp_message = {u"user_node": u"0000",
                       u"focus_node": u"30",
                       u"neighbor_level": 1,
                       u"nodes": [{u"public_key": u"xyz", u"total_up": 0, u"total_down": 0, u"score": 0.5}],
                       u"edges": [{u"from": u"xyz", u"to": u"abc", u"amount": 30}]}
        d.callback(([{"public_key": "xyz", "total_up": 0, "total_down": 0, u"score": 0.5}],
                    [{"from": "xyz", "to": "abc", "amount": 30}]))
        return self.do_request('trustchain/network?focus_node=30&neighbor_level=1',
                               expected_code=200, expected_json=exp_message) \
            .addCallback(lambda message: self.assertEqual(message, dumps(exp_message)))

    @deferred(timeout=10)
    def test_get_self(self):
        """
        Evaluate whether the API uses the own public key when public_key is set to 'self'.
        """
        d = self.setup_mock_community("0000")
        exp_message = {u"user_node": u"0000",
                       u"focus_node": u"0000",
                       u"neighbor_level": 1,
                       u"nodes": [{u"public_key": u"0000", u"total_up": 0, u"total_down": 0, u"score": 0.5,
                                   u"total_neighbors": 0}],
                       u"edges": []}
        d.callback(([{"public_key": "0000", "total_up": 0, "total_down": 0, "score": 0.5, "total_neighbors": 0}], []))
        return self.do_request('trustchain/network?focus_node=self&neighbor_level=1',
                               expected_code=200, expected_json=exp_message) \
            .addCallback(lambda message: self.assertEqual(message, dumps(exp_message)))

    @deferred(timeout=10)
    def test_negative_neighbor_level(self):
        """
        Evaluate whether the API uses neighbor level 1 when a negative number is provided.
        """
        d = self.setup_mock_community("0000")
        exp_message = {u"user_node": u"0000",
                       u"focus_node": u"0000",
                       u"neighbor_level": 1,
                       u"nodes": [{u"public_key": u"0000", u"total_up": 0, u"total_down": 0, u"score": 0.5,
                                   u"total_neighbors": 0}],
                       u"edges": []}

        d.callback(([{"public_key": "0000", "total_up": 0, "total_down": 0, "score": 0.5, "total_neighbors": 0}], []))
        return self.do_request('trustchain/network?focus_node=self&neighbor_level=-1',
                               expected_code=200, expected_json=exp_message) \
            .addCallback(lambda message: self.assertEqual(message, dumps(exp_message)))

    @deferred(timeout=10)
    def test_empty_dataset(self):
        """
        Evaluate whether the API sends a response when the dataset is not well-defined.
        """
        d = self.setup_mock_community("0000")
        exp_message = {u"user_node": u"0000",
                       u"focus_node": u"0000",
                       u"neighbor_level": 1,
                       u"nodes": [{u"public_key": u"0000", u"total_up": 0, u"total_down": 0, u"score": 0.5,
                                   u"total_neighbors": 0}],
                       u"edges": []}
        d.callback(([{"public_key": "0000", "total_up": 0, "total_down": 0, "score": 0.5, "total_neighbors": 0}], []))
        return self.do_request('trustchain/network?dataset=&focus_node=self&neighbor_level=-1',
                               expected_code=200, expected_json=exp_message) \
            .addCallback(lambda message: self.assertEqual(message, dumps(exp_message)))

    @deferred(timeout=10)
    def test_no_dataset(self):
        """
        Evaluate whether the API sends a response when the dataset is not defined.
        """
        d = self.setup_mock_community("0000")
        exp_message = {u"nodes": [{u"public_key": u"0000", u"total_down": 0, u"total_up": 0, u"score": 0.5,
                                   u"total_neighbors": 0}],
                       u"neighbor_level": 1,
                       u"user_node": u"0000",
                       u"focus_node": u"0000",
                       u"edges": []}
        d.callback(([{"public_key": "0000", "total_up": 0, "total_down": 0, "score": 0.5, "total_neighbors": 0}], []))
        return self.do_request('trustchain/network?focus_node=self&neighbor_level=-1',
                               expected_code=200, expected_json=exp_message) \
            .addCallback(lambda message: self.assertEqual(message, dumps(exp_message)))

    @deferred(timeout=10)
    def test_mc_community_exception(self):
        """
        Evaluate whether the API returns the correct error when the trustchain community can't be found.
        """
        TrustChainNetworkEndpoint.get_tribler_chain_community = lambda _:\
            (_ for _ in ()).throw(OperationNotEnabledByConfigurationException("trustchain is not enabled"))
        exp_message = {u"error": u"trustchain is not enabled"}
        return self.do_request('trustchain/network?focus_node=self',
                               expected_code=http.NOT_FOUND, expected_json=exp_message)
