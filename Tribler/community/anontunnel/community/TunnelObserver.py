__author__ = 'Chris'


class TunnelObserver:
    def on_state_change(self, community, state):
        pass

    def incoming_from_tunnel(self, community, origin, data):
        pass

    def exiting_from_tunnel(self, circuit_id, candidate, destination, data):
        pass

    def on_tunnel_stats(self, community, candidate, stats):
        pass
