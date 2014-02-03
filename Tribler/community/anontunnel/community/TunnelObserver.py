__author__ = 'Chris'


class TunnelObserver:
    def on_state_change(self, community, state):
        pass

    def on_tunnel_data(self, community, origin, data):
        pass

    def on_tunnel_stats(self, community, candidate, stats):
        pass
