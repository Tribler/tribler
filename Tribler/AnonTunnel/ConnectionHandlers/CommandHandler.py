__author__ = 'Chris'

import pickle


class ListCircuitsRequest:
    pass


class IsOnlineRequest:
    pass


class ListCircuitsResponse:
    def __init__(self, circuits):
        self.circuits = circuits


class IsOnlineResponse:
    def __init__(self, is_online):
        self.is_online = is_online


class CreateCircuitRequest:
    def __init__(self, first_hop):
        self.first_hop = first_hop


class CreateCircuitResponse:
    def __init__(self, circuit_id):
        self.circuit_id = circuit_id


class StopRequest:
    pass


class StopResponse:
    def __init__(self, stopped):
        self.stopped = stopped


class StartRequest:
    pass


class StartResponse:
    def __init__(self, started):
        self.started = started


class CommandHandler(object):
    def __init__(self, socket, dispersy_tunnel):
        """

        :param socket: the socket we will use to sent responses over
        :param dispersy_tunnel: the dispersy tunnel we want to control
        :type socket : socket
        :type dispersy_tunnel : DispersyTunnelProxy
        :return:
        """
        self.dispersy_tunnel = dispersy_tunnel
        self.socket = socket

    def data_came_in(self, packets):
        for packet in packets:
            (source_address, payload) = packet
            request = pickle.loads(payload)
            self.dispatch_request(source_address, request)

    def dispatch_request(self, source_address, request):
        if isinstance(request, ListCircuitsRequest):
            self.on_list_circuits_request(source_address, request)
        elif isinstance(request, IsOnlineRequest):
            self.on_ready_request(source_address, request)
        elif isinstance(request, StartRequest):
            self.on_start_request(source_address, request)
        elif isinstance(request, StopRequest):
            self.on_stop_request(source_address, request)
        elif isinstance(request, CreateCircuitRequest):
            self.on_create_circuit_request(source_address, request)

    def on_ready_request(self, source_address, request):
        is_online = len(self.dispersy_tunnel.circuits) > 0
        response = IsOnlineResponse(is_online)

        self.socket.sendto(pickle.dumps(response),source_address)

    def on_list_circuits_request(self, source_address, request):
        response = ListCircuitsResponse(self.dispersy_tunnel.circuits)

        self.socket.sendto(pickle.dumps(response), source_address)

    def on_create_circuit_request(self, source_address, request):
        circuit_id = self.dispersy_tunnel.create_circuit(request.first_hop)
        response = CreateCircuitResponse(circuit_id)

        self.socket.sendto(pickle.dumps(response), source_address)

    def on_start_request(self, source_address, request):
        self.dispersy_tunnel.start()

    def on_stop_request(self, source_address, request):
        self.dispersy_tunnel.stop()
        # Ugly but it gets the job done
        exit(1)