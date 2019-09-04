from __future__ import absolute_import


from random import choice, randint

from six.moves import xrange

from twisted.web import resource

import Tribler.Core.Utilities.json_util as json
from Tribler.Test.GUI.FakeTriblerAPI import tribler_utils


class IPv8Endpoint(resource.Resource):

    def __init__(self):
        resource.Resource.__init__(self)
        self.putChild(b"trustchain", IPv8TrustChainEndpoint())
        self.putChild(b"tunnel", IPv8TunnelEndpoint())
        self.putChild(b"dht", IPv8DHTEndpoint())
        self.putChild(b"overlays", IPv8OverlaysEndpoint())


class IPv8TrustChainEndpoint(resource.Resource):

    def __init__(self):
        resource.Resource.__init__(self)
        self.putChild(b"users", IPv8TrustChainUsersEndpoint())


class IPv8TrustChainUsersEndpoint(resource.Resource):

    def getChild(self, path, request):
        return IPv8TrustChainSpecificUserEndpoint(path)


class IPv8TrustChainSpecificUserEndpoint(resource.Resource):

    def __init__(self, _):
        resource.Resource.__init__(self)
        self.putChild(b"blocks", IPv8TrustChainSpecificUserBlocksEndpoint())


class IPv8TrustChainSpecificUserBlocksEndpoint(resource.Resource):

    def render_GET(self, _request):
        return json.twisted_dumps({"blocks": [block.to_dictionary()
                                      for block in tribler_utils.tribler_data.trustchain_blocks]})


class IPv8TunnelEndpoint(resource.Resource):

    def __init__(self):
        resource.Resource.__init__(self)
        self.putChild(b"circuits", IPv8CircuitsEndpoint())
        self.putChild(b"relays", IPv8RelaysEndpoint())
        self.putChild(b"exits", IPv8ExitsEndpoint())


class IPv8CircuitsEndpoint(resource.Resource):

    def render_GET(self, _request):
        return json.twisted_dumps({"circuits": [circuit.to_dictionary()
                                                for circuit in tribler_utils.tribler_data.tunnel_circuits]})


class IPv8RelaysEndpoint(resource.Resource):

    def render_GET(self, _request):
        return json.twisted_dumps({"relays": [relay.to_dictionary()
                                              for relay in tribler_utils.tribler_data.tunnel_relays]})


class IPv8ExitsEndpoint(resource.Resource):

    def render_GET(self, _request):
        return json.twisted_dumps({"exits": [exit_socket.to_dictionary()
                                             for exit_socket in tribler_utils.tribler_data.tunnel_exits]})


class IPv8DHTEndpoint(resource.Resource):

    def __init__(self):
        resource.Resource.__init__(self)
        self.putChild(b"statistics", IPv8DHTStatisticsEndpoint())


class IPv8DHTStatisticsEndpoint(resource.Resource):

    def render_GET(self, _request):
        return json.twisted_dumps({"statistics": tribler_utils.tribler_data.dht_stats})


class IPv8OverlaysEndpoint(resource.Resource):

    def render_GET(self, _request):
        return json.twisted_dumps({'overlays': [{
            "master_peer": ''.join(choice('0123456789abcdef') for _ in xrange(20)),
            "my_peer": ''.join(choice('0123456789abcdef') for _ in xrange(20)),
            "global_time": randint(1, 10000),
            "peers": [],
            "overlay_name": "TestOverlay"
        }]})
