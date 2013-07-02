__author__ = 'Chris'

import pickle


class ListCircuitsRequest:
    pass


class IsOnlineRequest:
    pass


class ListCircuitsResponse:
    pass


class IsOnlineResponse:
    pass


class CommandHandler(object):
    def __init__(self, socket, dispersyTunnel):
        """

        :param socket: the socket we will use to sent responses over
        :param dispersyTunnel: the dispersy tunnel we want to control
        :type socket : socket
        :type dispersyTunnel : DispersyTunnelProxy
        :return:
        """
        self.dispersyTunnel = dispersyTunnel
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

    def on_ready_request(self, source_address, request):
        is_online = len(self.dispersyTunnel.circuits) > 0
        response = IsOnlineResponse(is_online)
        self.socket.sendto(source_address, pickle.dumps(response))

    def on_list_circuits_request(self, source_address, request):
        response = ListCircuitsResponse(self.dispersyTunnel.circuits)
        self.socket.sendto(source_address, pickle.dumps(response))