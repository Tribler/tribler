from __future__ import absolute_import

from ipv8.requestcache import NumberCache


class BalanceRequestCache(NumberCache):

    def __init__(self, community, circuit_id, balance_deferred):
        super(BalanceRequestCache, self).__init__(community.request_cache, u"balance-request", circuit_id)
        self.circuit_id = circuit_id
        self.balance_deferred = balance_deferred

    def on_timeout(self):
        pass
