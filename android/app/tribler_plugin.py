"""
This twistd plugin enables to start Tribler headless using the twistd command.
"""
import logging
import os
import signal
from time import sleep

from twisted.application.service import MultiService, IServiceMaker
from twisted.conch import manhole_tap
from twisted.internet import reactor
from twisted.plugin import IPlugin
from twisted.python import usage
from twisted.python.log import msg
from zope.interface import implements

from Tribler.Core.Session import Session
from Tribler.Core.SessionConfig import SessionStartupConfig


class Options(usage.Options):
    optParameters = [
        ["manhole", "m", 0, "Enable manhole telnet service listening at the specified port", int],
        ["statedir", "s", None, "Use an alternate statedir", str],
        ["restapi", "p", 8085, "Use an alternate port for the REST API", int],
        ["dispersy", "d", -1, "Use an alternate port for Dispersy", int],
        ["libtorrent", "l", -1, "Use an alternate port for libtorrent", int],
    ]


class TriblerServiceMaker(object):
    implements(IServiceMaker, IPlugin)
    tapname = "tribler"
    description = "Tribler twistd plugin, starts Tribler as a service"
    options = Options

    def __init__(self):
        """
        Initialize the variables of the TriblerServiceMaker and the logger.
        """
        self.session = None
        self._stopping = False

    def start_tribler(self, options):
        """
        Main method to startup Tribler.
        """

        def signal_handler(sig, _):
            msg("Received shut down signal %s" % sig)
            if not self._stopping:
                self._stopping = True
                self.session.shutdown()
                msg("Tribler shut down")
                reactor.stop()
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        msg("Starting Tribler")

        config = SessionStartupConfig()

        if options["statedir"]:
            config.set_state_dir(options["statedir"])

        if options["restapi"] != 0:
            config.set_http_api_enabled(True)
            config.set_http_api_port(options["restapi"])

        if options["dispersy"] != -1:
            config.set_dispersy_port(options["dispersy"])

        if options["libtorrent"] != -1:
            config.set_listen_port(options["libtorrent"])

        self.session = Session(config)
        upgrader = self.session.prestart()
        if upgrader.failed:
            msg("The upgrader failed: .Tribler directory backed up, aborting")
            reactor.addSystemEventTrigger('after', 'shutdown', os._exit, 1)
            reactor.stop()
        else:
            self.session.start()
            msg("Tribler started")

    def makeService(self, options):
        """
        Construct a Tribler service.
        """
        tribler_service = MultiService()
        tribler_service.setName("Tribler")

        manhole_namespace = {}
        if options["manhole"]:
            port = options["manhole"]
            manhole = manhole_tap.makeService({
                'namespace': manhole_namespace,
                'telnetPort': 'tcp:%d:interface=127.0.0.1' % port,
                'sshPort': None,
                'passwd': os.path.join(os.path.dirname(__file__), 'passwd'),
            })
            tribler_service.addService(manhole)

        reactor.callWhenRunning(self.start_tribler, options)

        return tribler_service

service_maker = TriblerServiceMaker()
