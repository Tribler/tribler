import json
from Tribler.community.anontunnel.TunnelCommander import TunnelCommander

__author__ = 'Chris'


def on_stats(event, stats):
    print json.dumps(stats)
    tc.stop()   # Stop the TunnelCommander and its thread


UDP_IP = "127.0.0.1"
UDP_PORT = 1081

tc = TunnelCommander((UDP_IP, UDP_PORT))
tc.subscribe("on_stats_response", on_stats)

tc.start()
tc.request_stats()
tc.join()