import logging
from Tribler.dispersy.requestcache import NumberCache

__author__ = 'chris'


class CircuitRequestCache(NumberCache):
    @staticmethod
    def create_number(force_number=-1):
        return force_number if force_number >= 0 \
            else NumberCache.create_number()

    @staticmethod
    def create_identifier(number, force_number=-1):
        assert isinstance(number, (int, long)), type(number)
        return u"request-cache:circuit-request:%d" % (number,)

    def __init__(self, community, force_number):
        NumberCache.__init__(self, community.request_cache, force_number)
        self._logger = logging.getLogger(__name__)
        self.community = community

        self.circuit = None
        """ :type : Tribler.community.anontunnel.community.Circuit """

    @property
    def timeout_delay(self):
        return 5.0

    def on_success(self):
        from Tribler.community.anontunnel.globals \
            import CIRCUIT_STATE_READY

        if self.circuit.state == CIRCUIT_STATE_READY:
            self._logger.info("Circuit %d is ready", self.number)
            self.community.dispersy.callback.register(
                self.community.request_cache.pop, args=(self.identifier,))

    def on_timeout(self):
        from Tribler.community.anontunnel.globals \
            import CIRCUIT_STATE_READY

        if not self.circuit.state == CIRCUIT_STATE_READY:
            reason = 'timeout on CircuitRequestCache, state = %s' % \
                     self.circuit.state
            self.community.remove_circuit(self.number, reason)


class PingRequestCache(NumberCache):
    @staticmethod
    def create_number(force_number=-1):
        return force_number \
            if force_number >= 0 \
            else NumberCache.create_number()

    @staticmethod
    def create_identifier(number, force_number=-1):
        assert isinstance(number, (int, long)), type(number)
        return u"request-cache:ping-request:%d" % (number,)

    def __init__(self, community, force_number):
        NumberCache.__init__(self, community.request_cache, force_number)
        self.community = community

    @property
    def timeout_delay(self):
        return 10.0

    @property
    def cleanup_delay(self):
        return 0.0

    def on_pong(self, message):
        self.community.dispersy.callback.register(
            self.community.request_cache.pop, args=(self.identifier,))

    def on_timeout(self):
        self.community.remove_circuit(self.number, 'RequestCache')
