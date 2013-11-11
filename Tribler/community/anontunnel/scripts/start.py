from Tribler.community.anontunnel.TunnelCommander import TunnelCommander

__author__ = 'Chris'
UDP_IP = "127.0.0.1"
UDP_PORT = 1081

tc = TunnelCommander((UDP_IP, UDP_PORT))
tc.request_start()