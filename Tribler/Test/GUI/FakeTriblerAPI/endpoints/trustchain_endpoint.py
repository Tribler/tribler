from __future__ import absolute_import

import json
from binascii import hexlify
from random import randint

from twisted.web import resource

from Tribler.Test.GUI.FakeTriblerAPI import tribler_utils


class TrustchainEndpoint(resource.Resource):

    def __init__(self):
        resource.Resource.__init__(self)

        child_handler_dict = {"statistics": TrustchainStatsEndpoint}

        for path, child_cls in child_handler_dict.items():
            self.putChild(path, child_cls())


class TrustchainStatsEndpoint(resource.Resource):
    """
    This class handles requests regarding the TrustChain community information.
    """

    def render_GET(self, _request):
        last_block = tribler_utils.tribler_data.trustchain_blocks[-1]

        return json.dumps({'statistics': {
            "id": hexlify('a' * 20),
            "total_blocks": len(tribler_utils.tribler_data.trustchain_blocks),
            "total_down": last_block.total_down,
            "total_up": last_block.total_up,
            "peers_that_pk_helped": randint(10, 50),
            "peers_that_helped_pk": randint(10, 50),
            "latest_block": last_block.to_dictionary()
        }})
