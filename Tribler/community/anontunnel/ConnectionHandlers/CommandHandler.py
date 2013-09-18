import os

__author__ = 'Chris'

import logging.config

logger = logging.getLogger(__name__)

import socket
import pickle


class ListCircuitsRequest:
    def __init__(self):
        pass


class IsOnlineRequest:
    def __init__(self):
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
    def __init__(self):
        pass


class StopResponse:
    def __init__(self, stopped):
        self.stopped = stopped


class StartRequest:
    def __init__(self):
        pass


class StartResponse:
    def __init__(self, started):
        self.started = started


class CommandHandler(object):
    def __init__(self, anon_tunnel):
        """

        :param anon_tunnel: the dispersy tunnel we want to control
        :type anon_tunnel : Tribler.AnonTunnel.AnonTunnel.AnonTunnel
        :return:
        """
        self.anon_tunnel = anon_tunnel
        self.socket = None

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
        is_online = len(self.anon_tunnel.tunnel.circuits) > 0
        response = IsOnlineResponse(is_online)

        self.socket.sendto(pickle.dumps(response), source_address)

    def on_list_circuits_request(self, source_address, request):
        response = ListCircuitsResponse(self.anon_tunnel.tunnel.circuits)

        self.socket.sendto(pickle.dumps(response), source_address)

    def on_create_circuit_request(self, source_address, request):
        circuit_id = self.anon_tunnel.tunnel.create_circuit(request.first_hop)
        response = CreateCircuitResponse(circuit_id)

        self.socket.sendto(pickle.dumps(response), source_address)

    def on_start_request(self, source_address, request):
        logger.error("Got START packet from %s:%d" % (source_address[0], source_address[1]))
        self.anon_tunnel.start()

    def on_stop_request(self, source_address, request):
        logger.error("Got STOP packet from %s:%d" % (source_address[0], source_address[1]))
        self.anon_tunnel.stop()
        os._exit(0) # TODO: very ugly but gets the job done for now

    def attach_to(self, server, port=1081):
        try:
            self.socket = server.raw_server.create_udpsocket(port, "127.0.0.1")
            server.start_listening_udp(self.socket, self)

            logger.info("Listening on CMD socket on port %d" % port)
        except socket.error:
            logger.error("Cannot listen on CMD socket on port %d, perhaps another instance is running?" % port)