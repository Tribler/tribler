import os
import sys
import json
import time
import random
import argparse
import threading
import cherrypy

from collections import defaultdict, deque

from twisted.internet.task import LoopingCall
from twisted.internet.stdio import StandardIO
from twisted.protocols.basic import LineReceiver
from twisted.internet.threads import blockingCallFromThread

from Tribler.community.tunnel.community import TunnelCommunity, TunnelSettings
from Tribler.Core.SessionConfig import SessionStartupConfig
from Tribler.Core.Session import Session
from Tribler.Core.Utilities.twisted_thread import reactor
from Tribler.Core.permid import read_keypair

try:
    import yappi
except ImportError:
    print >> sys.stderr, "Yappi not installed, profiling options won't be available"

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__))))


class AnonTunnel(object):
    """
    The standalone AnonTunnel application. Does not depend on Tribler Session
    or LaunchManyCore but creates all dependencies by itself.

    @param int socks5_port: the SOCKS5 port to listen on, or None to disable
    the SOCKS5 server
    @param TunnelSettings settings: the settings to pass to the ProxyCommunity
    """

    def __init__(self, settings, crawl_keypair_filename=None):
        self.settings = settings
        self.crawl_keypair_filename = crawl_keypair_filename
        self.crawl_data = defaultdict(lambda: [])
        self.crawl_message = {}
        self.current_stats = defaultdict(int)
        self.history_stats = deque(maxlen=100)
        self.start_tribler()
        self.dispersy = self.session.lm.dispersy
        self.community = None
        self.clean_messages_lc = LoopingCall(self.clean_messages).start(1800)
        self.build_history_lc = LoopingCall(self.build_history).start(60, now=True)

    def clean_messages(self):
        now = int(time.time())
        for k in self.crawl_message.keys():
            if now - 3600 > self.crawl_message[k]['time']:
                self.crawl_message.pop(k)

    def build_history(self):
        self.history_stats.append(self.current_stats.copy())

    def start_tribler(self):
        config = SessionStartupConfig()
        config.set_state_dir(os.path.join(BASE_DIR, ".Tribler-%d") % self.settings.socks_listen_port)
        config.set_torrent_checking(False)
        config.set_multicast_local_peer_discovery(False)
        config.set_megacache(False)
        config.set_dispersy(True)
        config.set_swift_proc(True)
        config.set_mainline_dht(False)
        config.set_torrent_collecting(False)
        config.set_libtorrent(False)
        config.set_dht_torrent_collecting(False)
        config.set_videoplayer(False)
        config.set_dispersy_tunnel_over_swift(True)
        config.set_dispersy_port(-1)  # select random port
        config.set_swift_tunnel_listen_port(-1)
        self.session = Session(config)
        self.session.start()
        print >> sys.stderr, "Using ports %d for dispersy and %d for swift tunnel" % \
                             (self.session.get_dispersy_port(), self.session.get_swift_tunnel_listen_port())

    def run(self):
        def start_community():
            if self.crawl_keypair_filename:
                keypair = read_keypair(self.crawl_keypair_filename)
                member = self.dispersy.get_member(private_key=self.dispersy.crypto.key_to_bin(keypair))
            else:
                member = self.dispersy.get_new_member(u"NID_secp160k1")
            self.community = self.dispersy.define_auto_load(TunnelCommunity, member, (None, self.settings),
                                                            load=True)[0]

            if self.crawl_keypair_filename:
                def on_introduction_response(messages):
                    self.community.on_introduction_response(messages)
                    for message in messages:
                        def stats_handler(candidate, stats):

                            now = int(time.time())
                            print '@%d' % now, message.candidate.get_member().mid.encode('hex'), json.dumps(stats)

                            candidate_mid = candidate.get_member().mid
                            stats = self.preprocess_stats(stats)
                            stats['time'] = now
                            stats_old = self.crawl_message.get(candidate_mid, None)
                            self.crawl_message[candidate_mid] = stats

                            if stats_old == None:
                                return

                            time_dif = float(stats['uptime'] - stats_old['uptime'])
                            if time_dif > 0:
                                for key in ['bytes_orig', 'bytes_relay', 'bytes_exit']:
                                    self.current_stats[key] = self.current_stats[key] * 0.875 + \
                                                              (((stats[key] - stats_old[key]) / time_dif) / 1024) * 0.125

                        self.community.do_stats(message.candidate, stats_handler)

                meta_message = self.community.get_meta_message(u"dispersy-introduction-response")
                meta_message._handle_callback = on_introduction_response

        blockingCallFromThread(reactor, start_community)

    def stop(self):
        if self.clean_messages_lc:
            self.clean_messages_lc.stop()
            self.clean_messages_lc = None

        if self.session:
            session_shutdown_start = time.time()
            waittime = 60
            self.session.shutdown()
            while not self.session.has_shutdown():
                diff = time.time() - session_shutdown_start
                assert diff < waittime, "Took too long for Session to shutdown"
                print >> sys.stderr, "ONEXIT Waiting for Session to shutdown, will wait for %d more seconds" % (waittime - diff)
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

    @cherrypy.expose
    def index(self, *args, **kwargs):
        # Return average statistics estimate.
        if 'callback' in kwargs:
            return kwargs['callback'] + '(' + json.dumps(self.current_stats) + ');'
        else:
            return json.dumps(self.current_stats)

    @cherrypy.expose
    def history(self, *args, **kwargs):
        # Return history of average statistics estimate.
        if 'callback' in kwargs:
            return kwargs['callback'] + '(' + json.dumps(list(self.history_stats)) + ');'
        else:
            return json.dumps(list(self.history_stats))


class LineHandler(LineReceiver):
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
        elif line == 'q':
            anon_tunnel.stop()
            os._exit(0)
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
    settings.socks_listen_port = socks5_port or random.randint(1000, 65535)
    anon_tunnel = AnonTunnel(settings, crawl_keypair_filename)
    StandardIO(LineHandler(anon_tunnel, profile))
    anon_tunnel.run()

    if crawl_keypair_filename and args.json > 0:
        cherrypy.config.update({'server.socket_host': '0.0.0.0', 'server.socket_port': args.json})
        cherrypy.quickstart(anon_tunnel)

if __name__ == "__main__":
    main(sys.argv[1:])

