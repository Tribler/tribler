"""
This twistd plugin enables to start Tribler headless using the twistd command.
"""
from __future__ import absolute_import

import os
import re
import signal
import time
from datetime import date
from socket import inet_aton

from twisted.application.service import IServiceMaker, MultiService
from twisted.conch import manhole_tap
from twisted.internet import reactor
from twisted.plugin import IPlugin
from twisted.python import usage
from twisted.python.log import msg

from zope.interface import implements

from Tribler.Core.Config.tribler_config import TriblerConfig
from Tribler.Core.Modules.process_checker import ProcessChecker
from Tribler.Core.Session import Session


def check_ipv8_bootstrap_override(val):
    parsed = re.match(r"^([\d\.]+)\:(\d+)$", val)
    if not parsed:
        raise ValueError("Invalid bootstrap address:port")

    ip, port = parsed.group(1), int(parsed.group(2))
    try:
        inet_aton(ip)
    except:
        raise ValueError("Invalid bootstrap server address")

    if port < 0 or port > 65535:
        raise ValueError("Invalid bootstrap server port")
    return val
check_ipv8_bootstrap_override.coerceDoc = "IPv8 bootstrap server address must be in ipv4_addr:port format"


class Options(usage.Options):
    optParameters = [
        ["manhole", "m", 0, "Enable manhole telnet service listening at the specified port", int],
        ["statedir", "s", None, "Use an alternate statedir", str],
        ["restapi", "p", 8085, "Use an alternate port for the REST API", int],
        ["ipv8", "i", -1, "Use an alternate port for IPv8", int],
        ["libtorrent", "l", -1, "Use an alternate port for libtorrent", int],
        ["ipv8_bootstrap_override", "b", None, "Force the usage of specific IPv8 bootstrap server (ip:port)",
         check_ipv8_bootstrap_override]
    ]
    optFlags = [
        ["testnet", "t", "Join the testnet"]
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
        self.process_checker = None

    def log_incoming_remote_search(self, sock_addr, keywords):
        d = date.today()
        with open(os.path.join(self.session.config.get_state_dir(), 'incoming-searches-%s' % d.isoformat()), 'a') as log_file:
            log_file.write("%s %s %s %s" % (time.time(), sock_addr[0], sock_addr[1], ";".join(keywords)))

    def shutdown_process(self, shutdown_message, code=1):
        msg(shutdown_message)
        reactor.addSystemEventTrigger('after', 'shutdown', os._exit, code)
        reactor.stop()

    def start_tribler(self, options):
        """
        Main method to startup Tribler.
        """
        def on_tribler_shutdown(_):
            msg("Tribler shut down")
            reactor.stop()
            self.process_checker.remove_lock_file()

        def signal_handler(sig, _):
            msg("Received shut down signal %s" % sig)
            if not self._stopping:
                self._stopping = True
                self.session.shutdown().addCallback(on_tribler_shutdown)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        config = TriblerConfig()

        # Check if we are already running a Tribler instance
        self.process_checker = ProcessChecker()
        if self.process_checker.already_running:
            self.shutdown_process("Another Tribler instance is already using statedir %s" % config.get_state_dir())
            return

        msg("Starting Tribler")

        if options["statedir"]:
            config.set_state_dir(options["statedir"])

        if options["restapi"] > 0:
            config.set_http_api_enabled(True)
            config.set_http_api_port(options["restapi"])

        if options["ipv8"] > 0:
            config.set_ipv8_port(options["ipv8"])
        elif options["ipv8"] == 0:
            config.set_ipv8_enabled(False)

        if options["libtorrent"] != -1 and options["libtorrent"] > 0:
            config.set_libtorrent_port(options["libtorrent"])

        if options["ipv8_bootstrap_override"] is not None:
            config.set_ipv8_bootstrap_override(options["ipv8_bootstrap_override"])

        if "testnet" in options and options["testnet"]:
            config.set_testnet(True)

        self.session = Session(config)
        self.session.start().addErrback(lambda failure: self.shutdown_process(failure.getErrorMessage()))
        msg("Tribler started")

    def makeService(self, options):
        """
        Construct a Tribler service.
        """
        tribler_service = MultiService()
        tribler_service.setName("Tribler")

        manhole_namespace = {}
        if options["manhole"] > 0:
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
