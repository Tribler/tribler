"""
This twistd plugin enables to start a tunnel helper headless using the twistd command.
"""
from __future__ import absolute_import

import logging
import os
import re
import signal
import time
from socket import inet_aton

from twisted.application.service import IServiceMaker, MultiService
from twisted.conch import manhole_tap
from twisted.internet import reactor
from twisted.internet.task import LoopingCall
from twisted.plugin import IPlugin
from twisted.python import usage
from twisted.python.log import msg

from zope.interface import implementer

from Tribler.Core.Config.tribler_config import TriblerConfig
from Tribler.Core.Session import Session
from Tribler.Core.simpledefs import NTFY_REMOVE, NTFY_TUNNEL

logger = logging.getLogger(__name__)


def clean_twisted_observers(publisher=None):
    try:
        from twisted.logger import LogPublisher, LimitedHistoryLogObserver, globalLogPublisher
        if not publisher:
            publisher = globalLogPublisher
    except ImportError:
        logger.debug("Running an older version of twisted, no need to clean the observers")
        return

    logger.debug("Looking for rogue observers in %r", publisher._observers)

    for observer in publisher._observers:
        if isinstance(observer, LogPublisher):
            clean_twisted_observers(observer)

        elif isinstance(observer, LimitedHistoryLogObserver):
            publisher.removeObserver(observer)
            logger.debug("Removing observer %s", observer)

        else:
            logger.debug("Leaving alone observer %s", observer)


def check_api_port(val):
    api_port = int(val)
    if api_port <= 0:
        raise ValueError("Invalid port number")
    return api_port
check_api_port.coerceDoc = "Api port must be greater than 0."


def check_ipv8_port(val):
    ipv8_port = int(val)
    if ipv8_port < -1 or ipv8_port == 0:
        raise ValueError("Invalid port number")
    return ipv8_port
check_ipv8_port.coerceDoc = "IPv8 port must be greater than 0 or -1."


def check_ipv8_address(val):
    try:
        inet_aton(val)
    except:
        raise ValueError("Invalid IPv4 address")
    return val
check_ipv8_address.coerceDoc = "IPv8 listening address must be in proper IPv4 format."


def check_ipv8_bootstrap_override(val):
    parsed = re.match(r"^([\d\.]+)\:(\d+)$", val)
    if not parsed:
        raise ValueError("Invalid bootstrap address:port")

    ip, port = parsed.group(1), int(parsed.group(2))
    try:
        inet_aton(ip)
    except:
        raise ValueError("Invalid bootstrap server address")

    if not (0 < port < 65535):
        raise ValueError("Invalid bootstrap server port")
    return val
check_ipv8_bootstrap_override.coerceDoc = "IPv8 bootstrap server address must be in ipv4_addr:port format"


class Options(usage.Options):
    optFlags = [
        ["exit", "x", "Allow being an exit-node"],
        ["testnet", "t", "Join the testnet"],
        ["no-rest-api", "a", "Disable the REST api"],
        ["log-rejects", "", "Log rejects"],
        ["log-circuits", "", "Log information about circuits"]
    ]

    optParameters = [
        ["manhole", "m", 0, "Enable manhole telnet service listening at the specified port", int],
        ["ipv8_port", "d", -1, 'IPv8 port', check_ipv8_port],
        ["ipv8_address", "i", "0.0.0.0", 'IPv8 listening address', check_ipv8_address],
        ["ipv8_bootstrap_override", "b", None, "Force the usage of specific IPv8 bootstrap server (ip:port)", check_ipv8_bootstrap_override],
        ["restapi", "p", 8085, "Use an alternate port for the REST API", check_api_port],
        ["random_slots", "r", 10, "Specifies the number of random slots", int],
        ["competing_slots", "c", 20, "Specifies the number of competing slots", int],
    ]


class Tunnel(object):

    def __init__(self, options):
        self.options = options
        self.should_run = True
        self.session = None
        self.community = None
        self.clean_messages_lc = LoopingCall(self.clean_messages)
        self.clean_messages_lc.start(1800)
        self.bootstrap_lc = LoopingCall(self.periodic_bootstrap)
        self.bootstrap_lc.start(30, now=False)

    def clean_messages(self):
        clean_twisted_observers()

    def periodic_bootstrap(self):
        self.session.lm.tunnel_community.bootstrap()

    def on_circuit_reject(self, reject_time, balance):
        with open(os.path.join(self.session.config.get_state_dir(), "circuit_rejects.log"), 'a') as out_file:
            time_millis = int(round(reject_time * 1000))
            out_file.write("%d,%d\n" % (time_millis, balance))

    def tribler_started(self, _):
        # Remove all logging handlers
        root_logger = logging.getLogger()
        handlers = root_logger.handlers
        for handler in handlers:
            root_logger.removeHandler(handler)
        logging.getLogger().setLevel(logging.ERROR)

        new_strategies = []
        with self.session.lm.ipv8.overlay_lock:
            for strategy, target_peers in self.session.lm.ipv8.strategies:
                if strategy.overlay == self.session.lm.tunnel_community:
                    new_strategies.append((strategy, -1))
                else:
                    new_strategies.append((strategy, target_peers))
            self.session.lm.ipv8.strategies = new_strategies

        # Register reject event handler if set
        if self.options["log-rejects"]:
            self.session.lm.tunnel_community.reject_callback = self.on_circuit_reject

    def circuit_removed(self, _, __, circuit, additional_info):
        self.session.lm.ipv8.network.remove_by_address(circuit.peer.address)
        if self.options["log-circuits"]:
            with open(os.path.join(self.session.config.get_state_dir(), "circuits.log"), 'a') as out_file:
                duration = time.time() - circuit.creation_time
                out_file.write("%d,%f,%d,%d,%s\n" % (circuit.circuit_id, duration, circuit.bytes_up, circuit.bytes_down,
                                                     additional_info))

    def start(self):
        # Determine ipv8 port
        ipv8_port = -1
        if self.options["ipv8_port"] != -1:
            ipv8_port = self.options["ipv8_port"]
        elif "HELPER_INDEX" in os.environ and "HELPER_BASE" in os.environ:
            base_port = int(os.environ["HELPER_BASE"])
            ipv8_port = base_port + int(os.environ["HELPER_INDEX"]) * 5

        config = TriblerConfig()
        config.set_state_dir(os.path.join(config.get_state_dir(), "tunnel-%d") % ipv8_port)
        config.set_tunnel_community_socks5_listen_ports([])
        config.set_tunnel_community_random_slots(self.options["random_slots"])
        config.set_tunnel_community_competing_slots(self.options["competing_slots"])
        config.set_torrent_checking_enabled(False)
        config.set_ipv8_enabled(True)
        config.set_libtorrent_enabled(False)
        config.set_video_server_enabled(False)
        config.set_ipv8_port(ipv8_port)
        config.set_ipv8_address(self.options["ipv8_address"])
        config.set_trustchain_enabled(True)
        config.set_credit_mining_enabled(False)
        config.set_market_community_enabled(False)
        config.set_dht_enabled(True)
        config.set_tunnel_community_exitnode_enabled(bool(self.options["exit"]))
        config.set_popularity_community_enabled(False)
        config.set_testnet(bool(self.options["testnet"]))
        config.set_chant_enabled(False)

        if not self.options['no-rest-api']:
            config.set_http_api_enabled(True)
            api_port = self.options["restapi"]
            if "HELPER_INDEX" in os.environ and "HELPER_BASE" in os.environ:
                api_port = int(os.environ["HELPER_BASE"]) + 10000 + int(os.environ["HELPER_INDEX"])
            config.set_http_api_port(api_port)

        if self.options["ipv8_bootstrap_override"] is not None:
            config.set_ipv8_bootstrap_override(self.options["ipv8_bootstrap_override"])

        self.session = Session(config)
        self.session.notifier.add_observer(self.circuit_removed, NTFY_TUNNEL, [NTFY_REMOVE])

        return self.session.start().addCallback(self.tribler_started)

    def stop(self):
        if self.clean_messages_lc:
            self.clean_messages_lc.stop()
            self.clean_messages_lc = None
        if self.bootstrap_lc:
            self.bootstrap_lc.stop()
            self.bootstrap_lc = None

        if self.session:
            return self.session.shutdown()


@implementer(IPlugin, IServiceMaker)
class TunnelHelperServiceMaker(object):
    tapname = "tunnel_helper"
    description = "Tunnel Helper twistd plugin, starts a (hidden) tunnel as a service."
    options = Options

    def __init__(self):
        """
        Initialize the variables of this service and the logger.
        """
        self._stopping = False

    def start_tunnel(self, options):
        """
        Main method to startup a tunnel helper and add a signal handler.
        """

        tunnel = Tunnel(options)

        def signal_handler(sig, _):
            msg("Received shut down signal %s" % sig)
            if not self._stopping:
                self._stopping = True
                msg("Setting the tunnel should_run variable to False")
                tunnel.should_run = False
                tunnel.stop().addBoth(lambda _: reactor.stop())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        tunnel.start()

    def makeService(self, options):
        """
        Construct a tunnel helper service.
        """

        tunnel_helper_service = MultiService()
        tunnel_helper_service.setName("Tunnel_helper")

        manhole_namespace = {}
        if options["manhole"]:
            port = options["manhole"]
            manhole = manhole_tap.makeService({
                'namespace': manhole_namespace,
                'telnetPort': 'tcp:%d:interface=127.0.0.1' % port,
                'sshPort': None,
                'passwd': os.path.join(os.path.dirname(__file__), 'passwd'),
            })
            tunnel_helper_service.addService(manhole)

        reactor.callWhenRunning(self.start_tunnel, options)

        return tunnel_helper_service


service_maker = TunnelHelperServiceMaker()
