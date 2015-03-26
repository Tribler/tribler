import os
import sys
import json
import time
import random
import argparse
import threading
import cherrypy

from traceback import print_exc
from collections import defaultdict, deque

from twisted.internet.task import LoopingCall
from twisted.internet.stdio import StandardIO
from twisted.protocols.basic import LineReceiver
from twisted.internet.threads import blockingCallFromThread

from Tribler.community.tunnel.tunnel_community import TunnelSettings
from Tribler.Core.SessionConfig import SessionStartupConfig
from Tribler.Core.Session import Session
from Tribler.Core.Utilities.twisted_thread import reactor
from Tribler.Core.permid import read_keypair
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Main.globals import DefaultDownloadStartupConfig
from Tribler.community.tunnel.hidden_community import HiddenTunnelCommunity

import logging.config
#logging.config.fileConfig("logger.conf")

try:
    import yappi
except ImportError:
    print >> sys.stderr, "Yappi not installed, profiling options won't be available"

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

    def build_history(self):
        self.history_stats.append(self.get_stats())

    def stats_handler(self, candidate, stats, message):
        now = int(time.time())
        print '@%d' % now, message.candidate.get_member().mid.encode('hex'), json.dumps(stats)

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
        config.set_state_dir(os.path.join(BASE_DIR, ".Tribler-%d") % self.settings.socks_listen_ports[0])
        config.set_torrent_checking(False)
        config.set_multicast_local_peer_discovery(False)
        config.set_megacache(False)
        config.set_dispersy(True)
        config.set_mainline_dht(True)
        config.set_torrent_collecting(False)
        config.set_libtorrent(True)
        config.set_dht_torrent_collecting(False)
        config.set_enable_torrent_search(False)
        config.set_videoplayer(False)
        config.set_dispersy_port(self.dispersy_port)
        self.session = Session(config)
        upgrader = self.session.prestart()
        while not upgrader.is_done:
            time.sleep(0.1)
        self.session.start()
        print >> sys.stderr, "Using port %d" % self.session.get_dispersy_port()

    def start(self):
        def start_community():
            if self.crawl_keypair_filename:
                keypair = read_keypair(self.crawl_keypair_filename)
                member = self.dispersy.get_member(private_key=self.dispersy.crypto.key_to_bin(keypair))
                cls = TunnelCommunityCrawler
            else:
                member = self.dispersy.get_new_member(u"curve25519")
                cls = HiddenTunnelCommunity
            self.community = self.dispersy.define_auto_load(cls, member, (self.session, self.settings), load=True)[0]

            self.session.set_anon_proxy_settings(
                2, ("127.0.0.1", self.session.get_tunnel_community_socks5_listen_ports()))

        blockingCallFromThread(reactor, start_community)

        self.session.set_download_states_callback(self.download_states_callback, False)

    def download_states_callback(self, dslist):
        try:
            self.community.monitor_downloads(dslist)
        except:
            print_exc()

        return (4.0, [])

    def stop(self):
        self.session.uch.perform_usercallback(self._stop)

    def _stop(self):
        if self.clean_messages_lc:
            self.clean_messages_lc.stop()
            self.clean_messages_lc = None

        if self.build_history_lc:
            self.build_history_lc.stop()
            self.build_history_lc = None

        if self.session:
            session_shutdown_start = time.time()
            waittime = 60
            self.session.shutdown()
            while not self.session.has_shutdown():
                diff = time.time() - session_shutdown_start
                assert diff < waittime, "Took too long for Session to shutdown"
                print >> sys.stderr, "ONEXIT Waiting for Session to shutdown, will wait for %d more seconds" % (
                    waittime - diff)
                time.sleep(1)
            print >> sys.stderr, "Session is shutdown"
            Session.del_instance()

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

    def __init__(self, anon_tunnel, profile):
        self.anon_tunnel = anon_tunnel
        self.profile = profile

    def lineReceived(self, line):
        anon_tunnel = self.anon_tunnel
        profile = self.profile

        if line == 'threads':
            for thread in threading.enumerate():
                print "%s \t %d" % (thread.name, thread.ident)
        elif line == 'p':
            if profile:
                for func_stats in yappi.get_func_stats().sort("subtime")[:50]:
                    print "YAPPI: %10dx  %10.3fs" % (func_stats.ncall, func_stats.tsub), func_stats.name
            else:
                print >> sys.stderr, "Profiling disabled!"

        elif line == 'P':
            if profile:
                filename = 'callgrindc_%d.yappi' % anon_tunnel.dispersy.lan_address[1]
                yappi.get_func_stats().save(filename, type='callgrind')
            else:
                print >> sys.stderr, "Profiling disabled!"

        elif line == 't':
            if profile:
                yappi.get_thread_stats().sort("totaltime").print_all()

            else:
                print >> sys.stderr, "Profiling disabled!"

        elif line == 'c':
            print "========\nCircuits\n========\nid\taddress\t\t\t\t\tgoal\thops\tIN (MB)\tOUT (MB)"
            for circuit_id, circuit in anon_tunnel.community.circuits.items():
                print "%d\t%s:%d\t%d\t%d\t\t%.2f\t\t%.2f" % (circuit_id, circuit.first_hop[0],
                                                             circuit.first_hop[1], circuit.goal_hops,
                                                             len(circuit.hops),
                                                             circuit.bytes_down / 1024.0 / 1024.0,
                                                             circuit.bytes_up / 1024.0 / 1024.0)

        elif line.startswith('s'):
            cur_path = os.getcwd()
            line_split = line.split(' ')
            filename = 'test_file' if len(line_split) == 1 else line_split[1]

            if not os.path.exists(filename):
                print "Creating torrent..",
                with open(filename, 'wb') as fp:
                    fp.write(os.urandom(50 * 1024 * 1024))
                tdef = TorrentDef()
                tdef.add_content(os.path.join(cur_path, filename))
                tdef.set_tracker("udp://fake.net/announce")
                tdef.set_private()
                tdef.set_anonymous()
                tdef.finalize()
                tdef.save(os.path.join(cur_path, filename + '.torrent'))
            else:
                print "Loading existing torrent..",
                tdef = TorrentDef.load(filename + '.torrent')
            print "done, infohash of torrent: %s" % (tdef.get_infohash().encode('hex')[:10])

            defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
            dscfg = defaultDLConfig.copy()
            dscfg.set_hops(2)
            dscfg.set_dest_dir(cur_path)

            anon_tunnel.session.uch.perform_usercallback(lambda: anon_tunnel.session.start_download(tdef, dscfg))

        elif line.startswith('d'):
            line_split = line.split(' ')
            filename = 'test_file' if len(line_split) == 1 else line_split[1]

            print "Loading torrent..",
            tdef = TorrentDef.load(filename + '.torrent')
            print "done"

            defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
            dscfg = defaultDLConfig.copy()
            dscfg.set_hops(2)
            dscfg.set_dest_dir(os.path.join(os.getcwd(), 'downloader%s' % anon_tunnel.session.get_dispersy_port()))

            def start_download():
                def cb(ds):
                    print 'Download infohash=%s, down=%s, progress=%s, status=%s, seedpeers=%s' % (tdef.get_infohash().encode('hex')[:10], 
                                                      ds.get_current_speed('down'), 
                                                      ds.get_progress(), 
                                                      ds.get_status(), 
                                                      sum(ds.get_num_seeds_peers()))
                    return 1.0, False
                download = anon_tunnel.session.start_download(tdef, dscfg)
                download.set_state_callback(cb, delay=1)

            anon_tunnel.session.uch.perform_usercallback(start_download)

        elif line == 'q':
            anon_tunnel.stop()
            return

        elif line == 'r':
            print "circuit\t\t\tdirection\tcircuit\t\t\tTraffic (MB)"

            from_to = anon_tunnel.community.relay_from_to

            for key in from_to.keys():
                relay = from_to[key]

                print "%s-->\t%s\t\t%.2f" % ((key[0], key[1]), (relay.sock_addr, relay.circuit_id),
                                             relay.bytes[1] / 1024.0 / 1024.0,)


def main(argv):
    parser = argparse.ArgumentParser(description='Anonymous Tunnel CLI interface')

    try:
        parser.add_argument('-p', '--socks5', help='Socks5 port')
        parser.add_argument('-x', '--exit', help='Allow being an exit-node')
        parser.add_argument('-d', '--dispersy', help='Dispersy port')
        parser.add_argument('-c', '--crawl', help='Enable crawler and use the keypair specified in the given filename')
        parser.add_argument('-j', '--json', help='Enable JSON api, which will run on the provided port number ' +
                                                 '(only available if the crawler is enabled)', type=int)
        parser.add_argument('-y', '--yappi', help="Profiling mode, either 'wall' or 'cpu'")
        parser.add_help = True
        args = parser.parse_args(sys.argv[1:])

    except argparse.ArgumentError:
        parser.print_help()
        sys.exit(2)

    socks5_port = int(args.socks5) if args.socks5 else None
    dispersy_port = int(args.dispersy) if args.dispersy else -1
    crawl_keypair_filename = args.crawl
    profile = args.yappi if args.yappi in ['wall', 'cpu'] else None

    if profile:
        yappi.set_clock_type(profile)
        yappi.start(builtins=True)
        print "Profiling using %s time" % yappi.get_clock_type()['type']

    if crawl_keypair_filename and not os.path.exists(crawl_keypair_filename):
        print "Could not find keypair filename", crawl_keypair_filename
        sys.exit(1)

    settings = TunnelSettings()
    if socks5_port is not None:
        settings.socks_listen_ports = range(socks5_port, socks5_port + 5)
    else:
        settings.socks_listen_ports = [random.randint(1000, 65535) for _ in range(5)]
    
    settings.become_exitnode = True if args.exit in ['true'] else False
    if settings.become_exitnode:
        print "Exit-node enabled"
    else:
        print "Exit-node disabled"
        
    settings.do_test = False
    tunnel = Tunnel(settings, crawl_keypair_filename, dispersy_port)
    StandardIO(LineHandler(tunnel, profile))
    tunnel.start()

    if crawl_keypair_filename and args.json > 0:
        cherrypy.config.update({'server.socket_host': '0.0.0.0', 'server.socket_port': args.json})
        cherrypy.quickstart(tunnel)
    else:
        while True:
            time.sleep(1)

if __name__ == "__main__":
    main(sys.argv[1:])
