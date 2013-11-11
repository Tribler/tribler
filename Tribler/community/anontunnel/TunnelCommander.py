import pickle
from threading import Thread, Event
from Tribler.Core.RawServer.RawServer import RawServer
from Tribler.community.anontunnel.ConnectionHandlers.CommandHandler import CreateCircuitResponse, ListCircuitsResponse, IsOnlineResponse, IsOnlineRequest, ListCircuitsRequest, CreateCircuitRequest, StartRequest, StartResponse, StopRequest, StatsRequest, StatsResponse
from Tribler.community.anontunnel.Observable import Observable

__author__ = 'Chris'


class TunnelCommander(Thread, Observable):
    def __init__(self, tunnel_address):
        """

        :param tunnel_address:
        :param raw_server:
        :type raw_server: RawServer
        :return:
        """
        Thread.__init__(self)
        Observable.__init__(self)

        timeout = 300.0
        server_done_flag = Event()
        raw_server = RawServer(server_done_flag,
                       timeout / 5.0,
                       timeout,
                       ipv6_enable=False)

        self.address = tunnel_address
        self.raw_server = raw_server
        self.udp_socket = raw_server.create_udpsocket(0, "0.0.0.0")
        self.setDaemon(False)
        raw_server.start_listening_udp(self.udp_socket, self)

    def run(self):
        self.raw_server.listen_forever(None)

    def stop(self):
        self.raw_server.doneflag.set()

    def data_came_in(self, packets):
        for packet in packets:
            (source_address, payload) = packet
            response = pickle.loads(payload)
            self.dispatch_response(source_address, response)

    def request_is_online(self):
        request = IsOnlineRequest()
        self.udp_socket.sendto(pickle.dumps(request), self.address)

    def request_list_circuits(self):
        request = ListCircuitsRequest()
        self.udp_socket.sendto(pickle.dumps(request), self.address)

    def request_circuit_create(self, first_hop):
        request = CreateCircuitRequest(first_hop)
        self.udp_socket.sendto(pickle.dumps(request), self.address)

    def request_start(self):
        request = StartRequest()
        self.udp_socket.sendto(pickle.dumps(request), self.address)

    def request_stop(self):
        request = StopRequest()
        self.udp_socket.sendto(pickle.dumps(request), self.address)

    def dispatch_response(self, source_address, response):
        if isinstance(response, CreateCircuitResponse):
            self.fire("on_create_circuit_response", circuit_id=response.circuit_id)
        elif isinstance(response, ListCircuitsResponse):
            self.fire("on_list_circuits_response", circuits=response.circuits)
        elif isinstance(response, IsOnlineResponse):
            self.fire("on_is_online_response", is_online=response.is_online)
        elif isinstance(response, StartResponse):
            self.fire("on_start_response", started=response.started)
        elif isinstance(response, StartResponse):
            self.fire("on_stop_response", started=response.started)
        elif isinstance(response, StatsResponse):
            self.fire("on_stats_response", stats=response.stats)

    def request_stats(self):
        request = StatsRequest()
        self.udp_socket.sendto(pickle.dumps(request), self.address)
