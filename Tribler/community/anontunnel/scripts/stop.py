from threading import Event

from Tribler.community.anontunnel.ConnectionHandlers.CommandHandler import StartRequest
from Tribler.community.anontunnel.TunnelCommander import TunnelCommander
from Tribler.Core.RawServer.RawServer import RawServer


__author__ = 'Chris'

request = StartRequest()
UDP_IP = "127.0.0.1"
UDP_PORT = 1081

timeout = 300.0
server_done_flag = Event()
raw_server = RawServer(server_done_flag,
                       timeout / 5.0,
                       timeout,
                       ipv6_enable=False)

tc = TunnelCommander((UDP_IP, UDP_PORT), raw_server)
tc.request_stop()