"""
This plugin downloads torrents from magnet link or a file
"""
import os
import shutil
import signal
import sys
import time
from datetime import date

from twisted.application.service import MultiService, IServiceMaker
from twisted.conch import manhole_tap
from twisted.internet import reactor, task
from twisted.plugin import IPlugin
from twisted.python import usage
from twisted.python.log import msg
from zope.interface import implements

from Tribler.Core.DownloadConfig import DefaultDownloadStartupConfig
from Tribler.Core.Modules.process_checker import ProcessChecker
from Tribler.Core.Session import Session
from Tribler.Core.SessionConfig import SessionStartupConfig
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Utilities import utilities

dlstatus_strings = ['DLSTATUS_ALLOCATING_DISKSPACE',
                    'DLSTATUS_WAITING4HASHCHECK',
                    'DLSTATUS_HASHCHECKING',
                    'DLSTATUS_DOWNLOADING',
                    'DLSTATUS_SEEDING',
                    'DLSTATUS_STOPPED',
                    'DLSTATUS_STOPPED_ON_ERROR',
                    'DLSTATUS_METADATA',
                    'DLSTATUS_CIRCUITS']


class Options(usage.Options):
    optParameters = [
        ["manhole", "m", 0, "Enable manhole telnet service listening at the specified port", int],
        ["statedir", "s", None, "Use an alternate statedir", str],
        ["restapi", "p", -1, "Use an alternate port for the REST API", int],
        ["dispersy", "d", -1, "Use an alternate port for Dispersy", int],
        ["libtorrent", "l", -1, "Use an alternate port for libtorrent", int],
        ["magnetlink", "g", None, "Magnet link", str],
        ["magnetfile", "f", None, "Magnet file containing magnet links", str],
        ["limit", "n", 0, "Max torrents to download from file", int],
    ]
    optFlags = [
    ]


class TorrentDownloaderService(object):
    implements(IServiceMaker, IPlugin)
    tapname = "torrent_downloader"
    description = "Torrent downloader twistd plugin, starts Tribler as a service and downloads torrent(s) from " \
                  "given magnet link or from a file containing magnet links"
    options = Options

    def __init__(self):
        """
        Initialize the variables of the TorrentDownloaderService and the logger.
        """
        self.num_downloads = 0
        self.session = None
        self._stopping = False
        self.process_checker = None
        self.magnet_link = None
        self.magnet_file = None
        self.max_torrent = 0
        self.stats = {}

    def log_incoming_remote_search(self, sock_addr, keywords):
        d = date.today()
        with open(os.path.join(self.session.get_state_dir(), 'incoming-searches-%s' % d.isoformat()), 'a') as log_file:
            log_file.write("%s %s %s %s" % (time.time(), sock_addr[0], sock_addr[1], ";".join(keywords)))

    def shutdown_process(self, shutdown_message, code=1):
        msg(shutdown_message)
        reactor.addSystemEventTrigger('after', 'shutdown', sys.exit, code)
        reactor.stop()

    def download_torrent_from_file(self, torrent_filename):
        tdef = TorrentDef.load(torrent_filename)

        defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
        dscfg = defaultDLConfig.copy()
        dscfg.set_hops(0)
        dscfg.set_dest_dir(os.path.join(os.getcwd(), 'downloader%s' % self.session.get_dispersy_port()))

        def start_download():
            def cb(ds):
                msg("[file] progress:%s, speed:%s, upload:%s" % (ds.get_progress(), ds.get_current_speed('down'),
                                                                 ds.get_current_speed('up')))
                return 1.0, False

            download = self.session.start_download_from_tdef(tdef, dscfg)
            download.set_state_callback(cb)

        reactor.callFromThread(start_download)

    def start_download(self):
        if self.magnet_link:
            self.download_torrent_from_magent(self.magnet_link)
            self.num_downloads = 1
        elif self.magnet_file:
            with open(self.magnet_file, "rb") as magnet_file:
                for magnet_link in magnet_file:
                    if 0 < self.max_torrent <= self.num_downloads:
                        msg("Torrent download limit[%d] reached" % self.max_torrent)
                        break
                    self.download_torrent_from_magent(magnet_link)
                    self.num_downloads += 1
                    msg("downloading torrent:%s", magnet_link)
        else:
            msg("No magnet link or magent file specified as argument")

    def download_torrent_from_magent(self, magnet_link):
        msg("Loading torrent done")
        (dn, xt, _) = utilities.parse_magnetlink(magnet_link)

        self.stats[xt] = dict()
        self.stats[xt]["name"] = dn
        self.stats[xt]["start_time"] = time.time()
        self.stats[xt]["max_up_speed"] = 0.0
        self.stats[xt]["max_down_speed"] = 0.0
        self.stats[xt]["status"] = 0
        self.stats[xt]["download_complete"] = False

        defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
        dscfg = defaultDLConfig.copy()
        dscfg.set_hops(0)
        dscfg.set_dest_dir(os.path.join(os.getcwd(), 'downloader%s' % self.session.get_dispersy_port()))

        def state_callback(download_state):

            current_stat = download_state.get_seeding_statistics()
            if current_stat:
                self.stats[xt]["time_seeding"] = current_stat['time_seeding']
                self.stats[xt]['total_down'] = current_stat['total_down']
                self.stats[xt]['total_up'] = current_stat['total_up']
                self.stats[xt]['ratio'] = current_stat['ratio']
                self.stats[xt]['stat_time'] = time.time()
                self.stats[xt]['progress'] = download_state.get_progress()
                self.stats[xt]['speed'] = download_state.get_current_speed('down')
                self.stats[xt]['upload'] = download_state.get_current_speed('up')

            current_up_speed = download_state.get_current_speed('up')
            if current_up_speed > self.stats[xt]["max_up_speed"]:
                self.stats[xt]["max_up_speed"] = current_up_speed

            current_down_speed = download_state.get_current_speed('down')
            if current_down_speed > self.stats[xt]["max_down_speed"]:
                self.stats[xt]["max_down_speed"] = current_down_speed

            if download_state.get_progress() == 1.0:
                msg("Download completed")
                self.stats[xt]["download_complete"] = True

            msg("[%s] progress:%s, speed:%d, upload:%d" % (self.stats[xt]["name"], download_state.get_progress(),
                                                           download_state.get_current_speed('down'),
                                                           download_state.get_current_speed('up')))

            return 1.0, False

        def start_download():
            msg("[%s] Downloading torrent" % self.stats[xt]["name"])
            download = self.session.start_download_from_uri(magnet_link, dscfg)
            download.addCallback(lambda download_state: download_state.set_state_callback(state_callback))

        reactor.callFromThread(start_download)

    def check_download_states(self):

        def print_state():
            with open("stats.txt", "a+") as output_file:
                if False not in [stat["download_complete"] for _, stat in self.stats.iteritems()]:
                    msg("All download completed. Writing the results to the file")
                    reactor.stop()
                for _, stat in self.stats.iteritems():
                    output_file.write("%s:%s" %(stat['name'], stat))
                    output_file.write("\n")

        looper = task.LoopingCall(print_state)
        looper.start(5.0)  # call every 5 seconds

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

        config = SessionStartupConfig().load()  # Load the default configuration file

        # Check if we are already running a Tribler instance
        self.process_checker = ProcessChecker()
        if self.process_checker.already_running:
            self.shutdown_process("Another Tribler instance is already using statedir %s" % config.get_state_dir())
            return

        msg("Starting Tribler")

        if options["statedir"]:
            config.set_state_dir(options["statedir"])
        else:
            temp_state_dir = "/tmp/.Tribler"
            if os.path.exists(temp_state_dir):
                shutil.rmtree(temp_state_dir)
            config.set_state_dir(temp_state_dir)

        if options["restapi"] > 0:
            config.set_http_api_enabled(True)
            config.set_http_api_port(options["restapi"])

        if options["dispersy"] > 0:
            config.set_dispersy_port(options["dispersy"])

        if options["libtorrent"] > 0:
            config.set_listen_port(options["libtorrent"])

        if options["magnetlink"]:
            self.magnet_link = options["magnetlink"]

        if options["magnetfile"]:
            self.magnet_file = options["magnetfile"]

        if options["limit"]:
            self.max_torrent = options["limit"]

        self.session = Session(config)
        self.session.start().addErrback(lambda failure: self.shutdown_process(failure.getErrorMessage()))
        msg("Tribler started")

        self.start_download()
        self.check_download_states()

    def makeService(self, options):
        """
        Construct a Torrent Downloader service.
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


service_maker = TorrentDownloaderService()
