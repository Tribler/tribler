"""
This package contains code for the market community RESTful API.
"""
from twisted.web import resource

from Tribler.community.market.community import MarketCommunity


class BaseMarketEndpoint(resource.Resource):
    """
    This class can be used as a base class for all Market community endpoints.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

    def get_market_community(self):
        if not self.session.lm.market_community:
            raise RuntimeError("Market community cannot be found!")

        return self.session.lm.market_community
