import pickle
from Tribler.AnonTunnel import Observable
from Tribler.AnonTunnel.CommandHandler import CreateCircuitResponse, ListCircuitsResponse, IsOnlineResponse, IsOnlineRequest, ListCircuitsRequest, CreateCircuitRequest

__author__ = 'Chris'

class TunnelCommander(Observable):
    def __init__(self, tunnel_address, raw_server):
        """

        :param tunnel_address:
        :param raw_server:
        :type raw_server: RawServer
        :return:
        """
        self.address = tunnel_address
        self.raw_server = raw_server
        self.udp_socket = raw_server.create_udpsocket(0,"0.0.0.0");
        raw_server.start_listening_udp(self.udp_socket, self);

    def data_came_in(self, packets):
        for packet in packets:
            (source_address, payload) = packet
            response = pickle.loads(payload)
            self.dispatch_response(source_address, response)
            
    def requestIsOnline(self):
        request = IsOnlineRequest()
        self.udp_socket.sendto(pickle.dumps(request), self.address)

    def requestListCircuits(self):
        request = ListCircuitsRequest()
        self.udp_socket.sendto(pickle.dumps(request), self.address)

    def requestCircuitCreate(self, first_hop):
        request = CreateCircuitRequest(first_hop)
        self.udp_socket.sendto(pickle.dumps(request), self.address)

    def dispatch_response(self, source_address, response):
        if isinstance(response, CreateCircuitResponse):
            self.fire("on_create_circuit_response", circuit_id = response.circuit_id)
        elif isinstance(response, ListCircuitsResponse):
            self.fire("on_list_circuits_response", circuits = response.circuits)
        elif isinstance(response, IsOnlineResponse):
            self.fire("on_is_online_response", is_online = response.is_online)