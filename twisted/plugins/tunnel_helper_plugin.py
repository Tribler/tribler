"""
This twistd plugin enables to start a tunnel helper headless using the twistd command.
"""
import cherrypy
import json
import logging
import logging.config
import os
import random
import signal
import sys
import threading
import time
from collections import defaultdict, deque

from twisted.application.service import MultiService, IServiceMaker
from twisted.conch import manhole_tap
from twisted.internet import reactor
from twisted.internet.stdio import StandardIO
from twisted.internet.task import LoopingCall

# Laurens(23-05-2016): As of writing, Debian stable does not have
# the globalLogPublisher in the current version of Twisted.
# So we make it a conditional import.
try:
    global_log_publisher_available = True
except:
    pass
from twisted.plugin import IPlugin
from twisted.protocols.basic import LineReceiver
from twisted.python import usage
from twisted.python.log import msg
from zope.interface import implements

from Tribler.Core.Session import Session
from Tribler.Core.SessionConfig import SessionStartupConfig
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.permid import read_keypair
from Tribler.Core.simpledefs import dlstatus_strings
from Tribler.Core.DownloadConfig import DefaultDownloadStartupConfig
from Tribler.community.tunnel.hidden_community import HiddenTunnelCommunity
from Tribler.community.tunnel.tunnel_community import TunnelSettings
from Tribler.dispersy.candidate import Candidate
from Tribler.dispersy.tool.clean_observers import clean_twisted_observers
from Tribler.dispersy.util import blockingCallFromThread


# Register yappi profiler
from Tribler.dispersy.utils import twistd_yappi


def check_socks5_port(val):
    socks5_port = int(val)
    if socks5_port <= 0:
        raise ValueError("Invalid port number")
    return socks5_port
check_socks5_port.coerceDoc = "Socks5 port must be greater than 0."

def check_introduce_port(val):
    introduce_port = int(val)
    if introduce_port <= 0:
        raise ValueError("Invalid port number")
    return introduce_port
check_introduce_port.coerceDoc = "Introduction port must be greater than 0."

def check_dispersy_port(val):
    dispersy_port = int(val)
    if dispersy_port < -1 or dispersy_port == 0:
        raise ValueError("Invalid port number")
    return dispersy_port
check_dispersy_port.coerceDoc = "Dispersy port must be greater than 0 or -1."

def check_crawler_keypair(crawl_keypair_filename):
    if crawl_keypair_filename and not os.path.exists(crawl_keypair_filename):
        raise ValueError("Crawler file does not exist")
    return crawl_keypair_filename
check_crawler_keypair.coerceDoc = "Give a path to an existing file."

def check_json_port(val):
    json_port = int(val)
    if json_port <= 0:
        raise ValueError("Invalid port number")
    return json_port
check_json_port.coerceDoc = "Json API port must be greater than 0."


class Options(usage.Options):
    optFlags = [
        ["exit", "x", "Allow being an exit-node"],
        ["multichain", "M", "Enable the multichain community"]
    ]

    optParameters = [
        ["manhole", "m", 0, "Enable manhole telnet service listening at the specified port", int],
        ["socks5", "p", None, "Socks5 port", check_socks5_port],
        ["introduce", "i", None, 'Introduce the dispersy port of another tribler instance', check_introduce_port],
        ["dispersy", "d", -1, 'Dispersy port', check_dispersy_port],
        ["crawl", "c", None, 'Enable crawler and use the keypair specified in the given filename', check_crawler_keypair],
        ["json", "j", 0, 'Enable JSON api, which will run on the provided port number ' +
         '(only available if the crawler is enabled)', check_json_port],
    ]


logging.config.fileConfig("logger.conf")
logger = logging.getLogger('TunnelMain')

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__))))


class TunnelCommunityCrawler(HiddenTunnelCommunity):
    def on_introduction_response(self, messages):
        super(TunnelCommunityCrawler, self).on_introduction_response(messages)
        handler = Tunnel.get_instance().stats_handler
        for message in messages:
            self.do_stats(message.candidate, lambda c, s, m=message: handler(c, s, m))

    def start_walking(self):
        self.register_task("take step", LoopingCall(self.take_step)).start(1.0, now=True)


class Tunnel(object):
    __single = None

    def __init__(self, settings, crawl_keypair_filename=None, dispersy_port=-1):
        if Tunnel.__single:
            raise RuntimeError("Tunnel is singleton")
        Tunnel.__single = self

        self.settings = settings
        self.should_run = True
        self.crawl_keypair_filename = crawl_keypair_filename
        self.dispersy_port = dispersy_port
        self.crawl_data = defaultdict(lambda: [])
        self.crawl_message = {}
        self.current_stats = [0, 0, 0]
        self.history_stats = deque(maxlen=180)
        self.start_tribler()
        self.dispersy = self.session.lm.dispersy
        self.community = None
        self.clean_messages_lc = LoopingCall(self.clean_messages)
        self.clean_messages_lc.start(1800)
        self.build_history_lc = LoopingCall(self.build_history)
        self.build_history_lc.start(60, now=True)

    def get_instance(*args, **kw):
        if Tunnel.__single is None:
            Tunnel(*args, **kw)
        return Tunnel.__single

    get_instance = staticmethod(get_instance)

    def clean_messages(self):
        now = int(time.time())
        for k in self.crawl_message.keys():
            if now - 3600 > self.crawl_message[k]['time']:
                self.crawl_message.pop(k)

        clean_twisted_observers()

    def build_history(self):
        self.history_stats.append(self.get_stats())

    def stats_handler(self, candidate, stats, message):
        now = int(time.time())
        logger.debug('@%d %r %r', now, message.candidate.get_member().mid.encode('hex'), json.dumps(stats))

        candidate_mid = candidate.get_member().mid
        stats = self.preprocess_stats(stats)
        stats['time'] = now
        stats_old = self.crawl_message.get(candidate_mid, None)
        self.crawl_message[candidate_mid] = stats

        if stats_old is None:
            return

        time_dif = float(stats['uptime'] - stats_old['uptime'])
        if time_dif > 0:
            for index, key in enumerate(['bytes_orig', 'bytes_exit', 'bytes_relay']):
                self.current_stats[index] = self.current_stats[index] * 0.875 + \
                                            (((stats[key] - stats_old[key]) / time_dif) / 1024) * 0.125

    def start_tribler(self):
        config = SessionStartupConfig()
        config.set_state_dir(os.path.join(config.get_state_dir(), "tunnel-%d") % self.settings.socks_listen_ports[0])
        config.set_torrent_checking(False)
        config.set_multicast_local_peer_discovery(False)
        config.set_megacache(False)
        config.set_dispersy(True)
        config.set_mainline_dht(True)
        config.set_torrent_collecting(False)
        config.set_libtorrent(True)
        config.set_dht_torrent_collecting(False)
        config.set_enable_torrent_search(False)
        config.set_videoserver_enabled(False)
        config.set_dispersy_port(self.dispersy_port)
        config.set_enable_torrent_search(False)
        config.set_enable_channel_search(False)
        config.set_enable_multichain(self.settings.enable_multichain)

        # We do not want to load the TunnelCommunity in the session but instead our own community
        config.set_tunnel_community_enabled(False)

        self.session = Session(config)
        upgrader = self.session.prestart()
        if upgrader.failed:
            msg("The upgrader failed: .Tribler directory backed up, aborting")
            reactor.addSystemEventTrigger('after', 'shutdown', os._exit, 1)
            reactor.stop()
        else:
            self.session.start()
            logger.info("Using Dispersy port %d" % self.session.get_dispersy_port())

    def start(self, introduce_port):
        def start_community():
            if self.crawl_keypair_filename:
                keypair = read_keypair(self.crawl_keypair_filename)
                member = self.dispersy.get_member(private_key=self.dispersy.crypto.key_to_bin(keypair))
                cls = TunnelCommunityCrawler
            else:
                if self.settings.enable_multichain:
                    from Tribler.community.multichain.community import MultiChainCommunity
                    member = self.dispersy.get_member(private_key=self.session.multichain_keypair.key_to_bin())
                    self.dispersy.define_auto_load(MultiChainCommunity, member, load=True)
                    from Tribler.community.tunnel.hidden_community_multichain import HiddenTunnelCommunityMultichain
                    cls = HiddenTunnelCommunityMultichain
                else:
                    member = self.dispersy.get_new_member(u"curve25519")
                    cls = HiddenTunnelCommunity

            self.community = self.dispersy.define_auto_load(cls, member, (self.session, self.settings), load=True)[0]

            self.session.set_anon_proxy_settings(
                2, ("127.0.0.1", self.session.get_tunnel_community_socks5_listen_ports()))
            if introduce_port:
                self.community.add_discovered_candidate(Candidate(('127.0.0.1', introduce_port), tunnel=False))

        blockingCallFromThread(reactor, start_community)

        self.session.set_download_states_callback(self.download_states_callback, interval=4.0)

    def download_states_callback(self, dslist):
        try:
            self.community.monitor_downloads(dslist)
        except:
            logger.error("Monitoring downloads failed")

        return []

    def stop(self):
        if self.clean_messages_lc:
            self.clean_messages_lc.stop()
            self.clean_messages_lc = None

        if self.build_history_lc:
            self.build_history_lc.stop()
            self.build_history_lc = None

        if self.session:
            logger.info("Going to shutdown session")
            return self.session.shutdown()

    def preprocess_stats(self, stats):
        result = defaultdict(int)
        result['uptime'] = stats['uptime']
        keys_to_from = {'bytes_orig': ('bytes_up', 'bytes_down'),
                        'bytes_exit': ('bytes_enter', 'bytes_exit'),
                        'bytes_relay': ('bytes_relay_up', 'bytes_relay_down')}
        for key_to, key_from in keys_to_from.iteritems():
            result[key_to] = sum([stats.get(k, 0) for k in key_from])
        return result

    def get_stats(self):
        return [round(f, 2) for f in self.current_stats]

    @cherrypy.expose
    def index(self, *args, **kwargs):
        # Return average statistics estimate.
        if 'callback' in kwargs:
            return kwargs['callback'] + '(' + json.dumps(self.get_stats()) + ');'
        else:
            return json.dumps(self.get_stats())

    @cherrypy.expose
    def history(self, *args, **kwargs):
        # Return history of average statistics estimate.
        if 'callback' in kwargs:
            return kwargs['callback'] + '(' + json.dumps(list(self.history_stats)) + ');'
        else:
            return json.dumps(list(self.history_stats))


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

        elif line.startswith('s'):
            cur_path = os.getcwd()
            line_split = line.split(' ')
            filename = 'test_file' if len(line_split) == 1 else line_split[1]

            if not os.path.exists(filename):
                logger.info("Creating torrent..")
                with open(filename, 'wb') as fp:
                    fp.write(os.urandom(50 * 1024 * 1024))
                tdef = TorrentDef()
                tdef.add_content(os.path.join(cur_path, filename))
                tdef.set_tracker("udp://localhost/announce")
                tdef.set_private()
                tdef.finalize()
                tdef.save(os.path.join(cur_path, filename + '.torrent'))
            else:
                logger.info("Loading existing torrent..")
                tdef = TorrentDef.load(filename + '.torrent')
            logger.info("loading torrent done, infohash of torrent: %s" % (tdef.get_infohash().encode('hex')[:10]))

            defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
            dscfg = defaultDLConfig.copy()
            dscfg.set_hops(1)
            dscfg.set_dest_dir(cur_path)

            reactor.callFromThread(anon_tunnel.session.start_download_from_tdef, tdef, dscfg)
        elif line.startswith('i'):
            # Introduce dispersy port from other main peer to this peer
            line_split = line.split(' ')
            to_introduce_ip = line_split[1]
            to_introduce_port = int(line_split[2])
            self.anon_tunnel.community.add_discovered_candidate(
                Candidate((to_introduce_ip, to_introduce_port), tunnel=False))
        elif line.startswith('d'):
            line_split = line.split(' ')
            filename = 'test_file' if len(line_split) == 1 else line_split[1]

            logger.info("Loading torrent..")
            tdef = TorrentDef.load(filename + '.torrent')
            logger.info("Loading torrent done")

            defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
            dscfg = defaultDLConfig.copy()
            dscfg.set_hops(1)
            dscfg.set_dest_dir(os.path.join(os.getcwd(), 'downloader%s' % anon_tunnel.session.get_dispersy_port()))

            def start_download():
                def cb(ds):
                    logger.info('Download infohash=%s, down=%s, progress=%s, status=%s, seedpeers=%s, candidates=%d' %
                                (tdef.get_infohash().encode('hex')[:10],
                                 ds.get_current_speed('down'),
                                 ds.get_progress(),
                                 dlstatus_strings[ds.get_status()],
                                 sum(ds.get_num_seeds_peers()),
                                 sum(1 for _ in anon_tunnel.community.dispersy_yield_verified_candidates())))
                    return 1.0, False

                download = anon_tunnel.session.start_download_from_tdef(tdef, dscfg)
                download.set_state_callback(cb)

            reactor.callFromThread(start_download)

        elif line == 'q':
            anon_tunnel.should_run = False

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

        socks5_port = options["socks5"]
        introduce_port = options["introduce"]
        dispersy_port = options["dispersy"]
        crawl_keypair_filename = options["crawl"]

        settings = TunnelSettings()

        # For disabling anonymous downloading, limiting download to hidden services only.
        settings.min_circuits = 0
        settings.max_circuits = 0

        if socks5_port is not None:
            settings.socks_listen_ports = range(socks5_port, socks5_port + 5)
        else:
            settings.socks_listen_ports = [random.randint(1000, 65535) for _ in range(5)]

        settings.become_exitnode = bool(options["exit"])
        if settings.become_exitnode:
            logger.info("Exit-node enabled")
        else:
            logger.info("Exit-node disabled")

        settings.enable_multichain = bool(options["multichain"])
        if settings.enable_multichain:
            logger.info("Multichain enabled")
        else:
            logger.info("Multichain disabled")

        tunnel = Tunnel(settings, crawl_keypair_filename, dispersy_port)
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

        tunnel.start(introduce_port)

        if crawl_keypair_filename and options["json"] > 0:
            cherrypy.config.update({'server.socket_host': '0.0.0.0', 'server.socket_port': options["json"]})
            cherrypy.quickstart(tunnel)

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
