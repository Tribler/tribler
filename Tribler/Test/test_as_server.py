# Written by Arno Bakker, Jie Yang
# Improved and Modified by Niels Zeilemaker
# see LICENSE.txt for license information

# Make sure the in thread reactor is installed.
import functools
import inspect
import logging
import os
import re
import shutil
import time
import unittest
from tempfile import mkdtemp
from threading import enumerate as enumerate_threads
from twisted.internet import interfaces
from twisted.internet.base import BasePort
from twisted.internet.defer import maybeDeferred, inlineCallbacks, Deferred, succeed
from twisted.internet.task import deferLater
from twisted.internet.tcp import Client
from twisted.web.http import HTTPChannel
from twisted.web.server import Site
from twisted.web.static import File

from Tribler.Core import defaults
from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.Session import Session
from Tribler.Core.SessionConfig import SessionStartupConfig
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Utilities.instrumentation import WatchDog
from Tribler.Core.Utilities.network_utils import get_random_port
from Tribler.Core.simpledefs import dlstatus_strings, DLSTATUS_SEEDING
from Tribler.Test.twisted_thread import reactor
from Tribler.Test.util.util import process_unhandled_exceptions, process_unhandled_twisted_exceptions
from Tribler.dispersy.util import blocking_call_on_reactor_thread

TESTS_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
TESTS_DATA_DIR = os.path.abspath(os.path.join(TESTS_DIR, u"data"))
TESTS_API_DIR = os.path.abspath(os.path.join(TESTS_DIR, u"API"))

defaults.sessdefaults['general']['minport'] = -1
defaults.sessdefaults['general']['maxport'] = -1
defaults.sessdefaults['dispersy']['dispersy_port'] = -1

# We disable safe seeding by default
defaults.dldefaults['downloadconfig']['safe_seeding'] = False

OUTPUT_DIR = os.path.abspath(os.environ.get('OUTPUT_DIR', 'output'))


class BaseTestCase(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(BaseTestCase, self).__init__(*args, **kwargs)

        def wrap(fun):
            @functools.wraps(fun)
            def check(*argv, **kwargs):
                try:
                    result = fun(*argv, **kwargs)
                except:
                    raise
                else:
                    process_unhandled_exceptions()
                return result
            return check

        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            if name.startswith("test_"):
                setattr(self, name, wrap(method))


class AbstractServer(BaseTestCase):

    _annotate_counter = 0

    def __init__(self, *args, **kwargs):
        super(AbstractServer, self).__init__(*args, **kwargs)

        self.watchdog = WatchDog()
        self.selected_socks5_ports = set()

        # Enable Deferred debugging
        from twisted.internet.defer import setDebugging
        setDebugging(True)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, annotate=True):
        self._logger = logging.getLogger(self.__class__.__name__)

        self.session_base_dir = mkdtemp(suffix="_tribler_test_session")
        self.state_dir = os.path.join(self.session_base_dir, u"dot.Tribler")
        self.dest_dir = os.path.join(self.session_base_dir, u"TriblerDownloads")

        defaults.sessdefaults['general']['state_dir'] = self.state_dir
        defaults.dldefaults["downloadconfig"]["saveas"] = self.dest_dir

        yield self.checkReactor(phase="setUp")

        self.setUpCleanup()
        os.makedirs(self.session_base_dir)
        self.annotate_dict = {}

        self.file_server = None
        self.dscfg_seed = None

        if annotate:
            self.annotate(self._testMethodName, start=True)
        self.watchdog.start()

    def setUpCleanup(self):
        # Change to an existing dir before cleaning up.
        os.chdir(TESTS_DIR)
        shutil.rmtree(unicode(self.session_base_dir), ignore_errors=True)

    def setUpFileServer(self, port, path):
        # Create a local file server, can be used to serve local files. This is preferred over an external network
        # request in order to get files.
        resource = File(path)
        factory = Site(resource)
        self.file_server = reactor.listenTCP(port, factory)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def checkReactor(self, phase, *_):
        delayed_calls = reactor.getDelayedCalls()
        if delayed_calls:
            self._logger.error("The reactor was dirty during %s:", phase)
            for dc in delayed_calls:
                self._logger.error(">     %s" % dc)
                dc.cancel()

        has_network_selectables = False
        for item in reactor.getReaders() + reactor.getWriters():
            if isinstance(item, HTTPChannel) or isinstance(item, Client):
                has_network_selectables = True
                break

        if has_network_selectables:
            # TODO(Martijn): we wait a while before we continue the check since network selectables
            # might take some time to cleanup. I'm not sure what's causing this.
            yield deferLater(reactor, 0.2, lambda: None)

        # This is the same check as in the _cleanReactor method of Twisted's Trial
        selectable_strings = []
        for sel in reactor.removeAll():
            if interfaces.IProcessTransport.providedBy(sel):
                self._logger.error("Sending kill signal to %s", repr(sel))
                sel.signalProcess('KILL')
            selectable_strings.append(repr(sel))

        self.assertFalse(delayed_calls, "The reactor was dirty during %s" % phase)
        if Session.has_instance():
            try:
                yield Session.get_instance().shutdown()
            except:
                pass
            Session.del_instance()

            raise RuntimeError("Found a leftover session instance during %s" % phase)

        self.assertFalse(selectable_strings,
                         "The reactor has leftover readers/writers during %s: %r" % (phase, selectable_strings))

        # Check whether we have closed all the sockets
        open_readers = reactor.getReaders()
        for reader in open_readers:
            self.assertNotIsInstance(reader, BasePort,
                                     "Listening ports left on the reactor during %s: %s" % (phase, reader))

        # Check whether the threadpool is clean
        self.assertFalse(reactor.getThreadPool().working)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def tearDown(self, annotate=True):
        self.tearDownCleanup()
        if annotate:
            self.annotate(self._testMethodName, start=False)

        process_unhandled_exceptions()
        process_unhandled_twisted_exceptions()

        self.watchdog.join(2)
        if self.watchdog.is_alive():
            self._logger.critical("The WatchDog didn't stop!")
            self.watchdog.print_all_stacks()
            raise RuntimeError("Couldn't stop the WatchDog")

        if self.file_server:
            yield maybeDeferred(self.file_server.stopListening).addCallback(self.checkReactor)
        else:
            yield self.checkReactor("tearDown")

    def tearDownCleanup(self):
        self.setUpCleanup()

    def getStateDir(self, nr=0):
        state_dir = self.state_dir + (str(nr) if nr else '')
        if not os.path.exists(state_dir):
            os.mkdir(state_dir)
        return state_dir

    def getDestDir(self, nr=0):
        dest_dir = self.dest_dir + (str(nr) if nr else '')
        if not os.path.exists(dest_dir):
            os.mkdir(dest_dir)
        return dest_dir

    def annotate(self, annotation, start=True, destdir=OUTPUT_DIR):
        if not os.path.exists(destdir):
            os.makedirs(os.path.abspath(destdir))

        if start:
            self.annotate_dict[annotation] = time.time()
        else:
            filename = os.path.join(destdir, u"annotations.txt")
            if os.path.exists(filename):
                f = open(filename, 'a')
            else:
                f = open(filename, 'w')
                print >> f, "annotation start end"

            AbstractServer._annotate_counter += 1
            _annotation = re.sub('[^a-zA-Z0-9_]', '_', annotation)
            _annotation = u"%d_" % AbstractServer._annotate_counter + _annotation

            print >> f, _annotation, self.annotate_dict[annotation], time.time()
            f.close()

    def get_bucket_range_port(self):
        """
        Return the port range of the test bucket assigned.
        """
        min_base_port = 1000 if not os.environ.get("TEST_BUCKET", None) \
            else int(os.environ['TEST_BUCKET']) * 2000 + 2000
        return min_base_port, min_base_port + 2000

    def get_socks5_ports(self):
        """
        Return five random, free socks5 ports.
        This is here to make sure that tests in different buckets get assigned different SOCKS5 listen ports.
        Also, make sure that we have no duplicates in selected socks5 ports.
        """
        socks5_ports = []
        for _ in xrange(0, 5):
            min_base_port, max_base_port = self.get_bucket_range_port()
            selected_port = get_random_port(min_port=min_base_port, max_port=max_base_port)
            while selected_port in self.selected_socks5_ports:
                selected_port = get_random_port(min_port=min_base_port, max_port=max_base_port)
            self.selected_socks5_ports.add(selected_port)
            socks5_ports.append(selected_port)

        return socks5_ports


class TestAsServer(AbstractServer):

    """
    Parent class for testing the server-side of Tribler
    """

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, autoload_discovery=True):
        yield super(TestAsServer, self).setUp(annotate=False)
        self.setUpPreSession()

        self.quitting = False
        self.seeding_deferred = Deferred()
        self.seeder_session = None

        self.session = Session(self.config)

        self.tribler_started_deferred = self.session.start()
        yield self.tribler_started_deferred

        self.assertTrue(self.session.lm.initComplete)

        self.hisport = self.session.get_listen_port()

        self.annotate(self._testMethodName, start=True)

    def setUpPreSession(self):
        """ Should set self.config_path and self.config """
        self.config = SessionStartupConfig()
        self.config.set_state_dir(self.getStateDir())
        self.config.set_torrent_checking(False)
        self.config.set_multicast_local_peer_discovery(False)
        self.config.set_megacache(False)
        self.config.set_dispersy(False)
        self.config.set_mainline_dht(False)
        self.config.set_torrent_store(False)
        self.config.set_enable_torrent_search(False)
        self.config.set_enable_channel_search(False)
        self.config.set_torrent_collecting(False)
        self.config.set_libtorrent(False)
        self.config.set_dht_torrent_collecting(False)
        self.config.set_videoserver_enabled(False)
        self.config.set_enable_metadata(False)
        self.config.set_upgrader_enabled(False)
        self.config.set_http_api_enabled(False)
        self.config.set_tunnel_community_enabled(False)
        self.config.set_creditmining_enable(False)
        self.config.set_enable_multichain(False)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def tearDown(self, annotate=True):
        self.annotate(self._testMethodName, start=False)

        """ unittest test tear down code """
        if self.session is not None:
            assert self.session is Session.get_instance()
            yield self.session.shutdown()
            assert self.session.has_shutdown()
            Session.del_instance()

        yield self.stop_seeder()

        ts = enumerate_threads()
        self._logger.debug("test_as_server: Number of threads still running %d", len(ts))
        for t in ts:
            self._logger.debug("Thread still running %s, daemon: %s, instance: %s", t.getName(), t.isDaemon(), t)

        yield super(TestAsServer, self).tearDown(annotate=False)

    def create_local_torrent(self, source_file):
        '''
        This method creates a torrent from a local file and saves the torrent in the session state dir.
        Note that the source file needs to exist.
        '''
        self.assertTrue(os.path.exists(source_file))

        tdef = TorrentDef()
        tdef.add_content(source_file)
        tdef.set_tracker("http://localhost/announce")
        tdef.finalize()

        torrent_path = os.path.join(self.session.get_state_dir(), "seed.torrent")
        tdef.save(torrent_path)

        return tdef, torrent_path

    def setup_seeder(self, tdef, seed_dir):
        self.seed_config = SessionStartupConfig()
        self.seed_config.set_torrent_checking(False)
        self.seed_config.set_multicast_local_peer_discovery(False)
        self.seed_config.set_megacache(False)
        self.seed_config.set_dispersy(False)
        self.seed_config.set_mainline_dht(False)
        self.seed_config.set_torrent_store(False)
        self.seed_config.set_enable_torrent_search(False)
        self.seed_config.set_enable_channel_search(False)
        self.seed_config.set_torrent_collecting(False)
        self.seed_config.set_libtorrent(True)
        self.seed_config.set_dht_torrent_collecting(False)
        self.seed_config.set_videoserver_enabled(False)
        self.seed_config.set_enable_metadata(False)
        self.seed_config.set_upgrader_enabled(False)
        self.seed_config.set_tunnel_community_enabled(False)
        self.seed_config.set_state_dir(self.getStateDir(2))

        def start_seed_download(_):
            self.dscfg_seed = DownloadStartupConfig()
            self.dscfg_seed.set_dest_dir(seed_dir)
            d = self.seeder_session.start_download_from_tdef(tdef, self.dscfg_seed)
            d.set_state_callback(self.seeder_state_callback)

        self._logger.debug("starting to wait for download to reach seeding state")

        self.seeder_session = Session(self.seed_config, ignore_singleton=True)
        self.seeder_session.start().addCallback(start_seed_download)

        return self.seeding_deferred

    def stop_seeder(self):
        if self.seeder_session is not None:
            return self.seeder_session.shutdown()
        return succeed(None)

    def seeder_state_callback(self, ds):
        d = ds.get_download()
        self._logger.debug("seeder status: %s %s %s", repr(d.get_def().get_name()), dlstatus_strings[ds.get_status()],
                           ds.get_progress())

        if ds.get_status() == DLSTATUS_SEEDING:
            self.seeding_deferred.callback(None)
            return 0.0, False

        return 1.0, False
