# coding: utf-8
# Written by Wendo Sabée
# Initializes the XML-RPC Server

import threading
import SocketServer

from SimpleXMLRPCServer import SimpleXMLRPCServer
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler


class RequestHandler(SimpleXMLRPCRequestHandler):
    rpc_paths = ()

class SimpleThreadedXMLRPCServer(SocketServer.ThreadingMixIn, SimpleXMLRPCServer):
    pass

class XMLRPCServer(threading.Thread):
    def __init__(self, iface="127.0.0.1", port=8000):
        """
        Constructor for the XML-RPC Server.
        :param iface: Interface that the server should listen on (default: 127.0.0.1)
        :param port: Port that the server should listen on (default: 8000)
        :return:
        """
        threading.Thread.__init__(self)

        self._server = SimpleThreadedXMLRPCServer((iface, port), requestHandler=RequestHandler, allow_none=True)
        self._server.register_introspection_functions()

        self._iface = iface
        self._port = port

    def register_function(self, funct, name=None):
        """
        Register a function for use with the XML-RPC Server.
        :param funct: Reference to the function.
        :param name: Name of the function as it is exposed to the clients.
        :return: Boolean indicating success.
        """
        self._server.register_function(funct, name)

    def start_server(self):
        """
        Start the XML-RPC Server on the interface and port specified previously.
        :return: Nothing.
        """
        self.start()

    def run(self):
        """
        Function that is run to start the XML-RPC Server.
        :return: Nothing.
        """
        self._server.serve_forever()