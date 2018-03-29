"""
This twistd plugin enables to start a tunnel helper headless using the twistd command.
"""
import logging.config
import os
import random
import signal
import threading

from twisted.application.service import MultiService, IServiceMaker
from twisted.conch import manhole_tap
from twisted.internet import reactor
from twisted.internet.stdio import StandardIO
from twisted.internet.task import LoopingCall
from twisted.plugin import IPlugin
from twisted.protocols.basic import LineReceiver
from twisted.python import usage
from twisted.python.log import msg
from zope.interface import implements

from Tribler.Core.Config.tribler_config import TriblerConfig
from Tribler.Core.Session import Session
from Tribler.Core.simpledefs import NTFY_TUNNEL, NTFY_REMOVE
from Tribler.dispersy.tool.clean_observers import clean_twisted_observers


# Register yappi profiler
from Tribler.dispersy.utils import twistd_yappi


def check_socks5_port(val):
    socks5_port = int(val)
    if socks5_port <= 0:
        raise ValueError("Invalid port number")
    return socks5_port
check_socks5_port.coerceDoc = "Socks5 port must be greater than 0."


def check_ipv8_port(val):
    ipv8_port = int(val)
    if ipv8_port < -1 or ipv8_port == 0:
        raise ValueError("Invalid port number")
    return ipv8_port
check_ipv8_port.coerceDoc = "IPv8 port must be greater than 0 or -1."


class Options(usage.Options):
    optFlags = [
        ["exit", "x", "Allow being an exit-node"],
        ["testnet", "t", "Join the Tribler Testnet"]
    ]

    optParameters = [
        ["manhole", "m", 0, "Enable manhole telnet service listening at the specified port", int],
        ["socks5", "p", None, "Socks5 port", check_socks5_port],
        ["ipv8", "d", -1, 'IPv8 port', check_ipv8_port],
    ]


if not os.path.exists("logger.conf"):
    print "Unable to find logger.conf"
else:
    log_directory = os.path.abspath(os.environ.get('APPDATA', os.path.expanduser('~')))
    log_directory = os.path.join(log_directory, '.Tribler', 'logs')

    if not os.path.exists(log_directory):
        os.makedirs(log_directory)

    logging.info_log_file = '%s/tribler-info.log' % log_directory
    logging.error_log_file = '%s/tribler-error.log' % log_directory
    logging.config.fileConfig("logger.conf", disable_existing_loggers=False)

logger = logging.getLogger('TunnelMain')


class Tunnel(object):

    def __init__(self, options, ipv8_port=-1):
        self.options = options
        self.should_run = True
        self.ipv8_port = ipv8_port
        self.session = None
        self.community = None
        self.clean_messages_lc = LoopingCall(self.clean_messages)
        self.clean_messages_lc.start(1800)
        self.clean_messages_lc = LoopingCall(self.periodic_bootstrap)
        self.clean_messages_lc.start(30, now=False)

    def clean_messages(self):
        clean_twisted_observers()

    def periodic_bootstrap(self):
        self.session.lm.tunnel_community.bootstrap()

    def tribler_started(self):
        new_strategies = []
        with self.session.lm.ipv8.overlay_lock:
            for strategy, target_peers in self.session.lm.ipv8.strategies:
                if strategy.overlay == self.session.lm.tunnel_community:
                    new_strategies.append((strategy, -1))
                else:
                    new_strategies.append((strategy, target_peers))
            self.session.lm.ipv8.strategies = new_strategies

    def circuit_removed(self, _, __, ___, address):
        self.session.lm.ipv8.network.remove_by_address(address)
        self.session.lm.tunnel_community.bootstrap()

    def start(self):
        # Determine socks5 ports
        socks5_port = self.options['socks5']
        if socks5_port is not None:
            socks_listen_ports = range(socks5_port, socks5_port + 5)
        else:
            socks_listen_ports = [random.randint(1000, 65535) for _ in range(5)]

        config = TriblerConfig()
        config.set_state_dir(os.path.join(config.get_state_dir(), "tunnel-%d") % socks_listen_ports[0])
        config.set_tunnel_community_socks5_listen_ports(socks_listen_ports)
        config.set_torrent_checking_enabled(False)
        config.set_megacache_enabled(False)
        config.set_dispersy_enabled(False)
        config.set_ipv8_enabled(True)
        config.set_mainline_dht_enabled(True)
        config.set_torrent_collecting_enabled(False)
        config.set_libtorrent_enabled(False)
        config.set_video_server_enabled(False)
        config.set_dispersy_port(self.ipv8_port)
        config.set_torrent_search_enabled(False)
        config.set_channel_search_enabled(False)
        config.set_trustchain_enabled(True)
        config.set_credit_mining_enabled(False)
        config.set_market_community_enabled(False)
        config.set_mainline_dht_enabled(False)
        config.set_tunnel_community_exitnode_enabled(bool(self.options["exit"]))

        if "testnet" in self.options and self.options["testnet"]:
            config.set_ipv8_use_testnet(True)

        self.session = Session(config)
        logger.info("Using IPv8 port %d" % self.session.config.get_dispersy_port())

        self.session.notifier.add_observer(self.circuit_removed, NTFY_TUNNEL, [NTFY_REMOVE])

        return self.session.start().addCallback(self.tribler_started)

    def stop(self):
        if self.clean_messages_lc:
            self.clean_messages_lc.stop()
            self.clean_messages_lc = None

        if self.session:
            logger.info("Going to shutdown session")
            return self.session.shutdown()


class LineHandler(LineReceiver):
    delimiter = os.linesep

    def __init__(self, anon_tunnel):
        self.anon_tunnel = anon_tunnel

    def lineReceived(self, line):
        anon_tunnel = self.anon_tunnel

        if line == 'threads':
            for thread in threading.enumerate():
                logger.debug("%s \t %d", thread.name, thread.ident)
        elif line == 'c':
            logger.debug("========\nCircuits\n========\nid\taddress\t\t\t\t\tgoal\thops\tIN (MB)\tOUT (MB)\tinfohash\ttype")
            for circuit_id, circuit in anon_tunnel.community.circuits.items():
                info_hash = circuit.info_hash.encode('hex')[:10] if circuit.info_hash else '?'
                logger.debug("%d\t%s:%d\t%d\t%d\t\t%.2f\t\t%.2f\t\t%s\t%s" % circuit_id,
                                                                       circuit.first_hop[0],
                                                                       circuit.first_hop[1],
                                                                       circuit.goal_hops,
                                                                       len(circuit.hops),
                                                                       circuit.bytes_down / 1024.0 / 1024.0,
                                                                       circuit.bytes_up / 1024.0 / 1024.0,
                                                                       info_hash,
                                                                       circuit.ctype)
        elif line == 'r':
            logger.debug("circuit\t\t\tdirection\tcircuit\t\t\tTraffic (MB)")
            from_to = anon_tunnel.community.relay_from_to
            for key in from_to.keys():
                relay = from_to[key]
                logger.info("%s-->\t%s\t\t%.2f" % ((key[0], key[1]), (relay.sock_addr, relay.circuit_id),
                                                   relay.bytes[1] / 1024.0 / 1024.0,))


class TunnelHelperServiceMaker(object):
    implements(IServiceMaker, IPlugin)
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
        ipv8_port = options["ipv8"]

        tunnel = Tunnel(options, ipv8_port)
        StandardIO(LineHandler(tunnel))

        def signal_handler(sig, _):
            msg("Received shut down signal %s" % sig)
            if not self._stopping:
                self._stopping = True
                msg("Setting the tunnel should_run variable to False")
                tunnel.should_run = False
                tunnel.stop().addCallback(lambda _: reactor.stop())

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
