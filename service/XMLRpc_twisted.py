# coding: utf-8
# Written by Wendo Sabée
# Initializes the XML-RPC Server

from twisted.web import xmlrpc, server
from twisted.internet import reactor

import threading

class XMLRPCServer():

    _function_handler = None

    def __init__(self, iface="127.0.0.1", port=8000):
        """
        Constructor for the XML-RPC Server.
        :param iface: Interface that the server should listen on (default: 127.0.0.1)
        :param port: Port that the server should listen on (default: 8000)
        :return:
        """
        self._function_handler = XMLRPCHandler()

        self._iface = iface
        self._port = port

    def register_function(self, funct, name=None):
        """
        Register a function for use with the XML-RPC Server.
        :param funct: Reference to the function.
        :param name: Name of the function as it is exposed to the clients.
        :return: Boolean indicating success.
        """
        self._function_handler.register_function(funct, name)

    def start_server(self):
        """
        Start the XML-RPC Server on the interface and port specified previously.
        :return: Nothing.
        """
        reactor.listenTCP(self._port, server.Site(self._function_handler), interface=self._iface)
        #reactor.run()

class XMLRPCHandler(xmlrpc.XMLRPC):

    _functions = {}

    def __init__(self):
        xmlrpc.XMLRPC.__init__(self)

        # Add default methods
        self._functions['system.listMethods'] = self.listProcedures

    def register_function(self, funct, name):
        self._functions[name] = funct

    def lookupProcedure(self, procedurePath):
        try:
            return self._functions[procedurePath]
        except KeyError, e:
            raise xmlrpc.NoSuchFunction(self.NOT_FOUND,
                        "procedure %s not found" % procedurePath)

    def listProcedures(self):
        """
        Since we override lookupProcedure, its suggested to override
        listProcedures too.
        """
        return self._functions.keys()