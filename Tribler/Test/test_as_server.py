# Written by Arno Bakker, Jie Yang
# Improved and Modified by Niels Zeilemaker
# see LICENSE.txt for license information

# Make sure the in thread reactor is installed.
from Tribler.Core.Utilities.twisted_thread import reactor

# importmagic: manage
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
from traceback import print_exc

from twisted.internet import interfaces
from twisted.internet.base import BasePort
from twisted.internet.defer import maybeDeferred, inlineCallbacks, Deferred, succeed
from twisted.web.server import Site
from twisted.web.static import File

from Tribler.Core.Config.tribler_config import TriblerConfig
from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.simpledefs import dlstatus_strings, DLSTATUS_SEEDING, UPLOAD
from Tribler.Core import defaults
from Tribler.Core.Session import Session
from Tribler.Core.Utilities.instrumentation import WatchDog
from Tribler.Test.util import process_unhandled_exceptions, process_unhandled_twisted_exceptions
from Tribler.dispersy.util import blocking_call_on_reactor_thread


TESTS_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
TESTS_DATA_DIR = os.path.abspath(os.path.join(TESTS_DIR, u"data"))
TESTS_API_DIR = os.path.abspath(os.path.join(TESTS_DIR, u"API"))
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

    def setUp(self, annotate=True):
        self._logger = logging.getLogger(self.__class__.__name__)

        self.session_base_dir = mkdtemp(suffix="_tribler_test_session")
        self.state_dir = os.path.join(self.session_base_dir, u"dot.Tribler")
        self.dest_dir = os.path.join(self.session_base_dir, u"TriblerDownloads")

        defaults.sessdefaults['general']['state_dir'] = self.state_dir
        defaults.dldefaults["downloadconfig"]["saveas"] = self.dest_dir

        self.checkReactor(phase="setUp")

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

    @blocking_call_on_reactor_thread
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
            return maybeDeferred(self.file_server.stopListening).addCallback(self.checkReactor)
        else:
            return self.checkReactor("tearDown")

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
        self.seed_config = None

        self.session = Session(self.config)
        upgrader = self.session.prestart()
        assert upgrader.is_done

        assert not upgrader.failed, upgrader.current_status
        self.tribler_started_deferred = self.session.start()

        yield self.tribler_started_deferred

        self.hisport = self.session.config.get_libtorrent_port()

        assert self.session.lm.initComplete

        self.annotate(self._testMethodName, start=True)

    def setUpPreSession(self):
        self.config = TriblerConfig()
        self.config.set_dispersy_port(-1)
        self.config.set_libtorrent_port(-1)
        self.config.set_state_dir(self.getStateDir())
        self.config.set_torrent_checking_enabled(False)
        self.config.set_megacache_enabled(False)
        self.config.set_dispersy_enabled(False)
        self.config.set_mainline_dht_enabled(False)
        self.config.set_torrent_store(False)
        self.config.set_torrent_search_enabled(False)
        self.config.set_channel_search_enabled(False)
        self.config.set_torrent_collecting_enabled(False)
        self.config.set_libtorrent_enabled(False)
        self.config.set_video_server_enabled(False)
        self.config.set_metadata_enabled(False)
        self.config.set_upgrader_enabled(False)
        self.config.set_http_api_enabled(False)
        self.config.set_tunnel_community_enabled(False)
        self.config.set_credit_mining_enabled(False)
        self.config.set_multichain_enabled(False)

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

        torrent_path = os.path.join(self.session.config.get_state_dir(), "seed.torrent")
        tdef.save(torrent_path)

        return tdef, torrent_path

    def setup_seeder(self, tdef, seed_dir):
        self.seed_config = TriblerConfig()
        self.seed_config.set_torrent_checking_enabled(False)
        self.seed_config.set_megacache_enabled(False)
        self.seed_config.set_dispersy_enabled(False)
        self.seed_config.set_mainline_dht_enabled(False)
        self.seed_config.set_torrent_store(False)
        self.seed_config.set_torrent_search_enabled(False)
        self.seed_config.set_channel_search_enabled(False)
        self.seed_config.set_torrent_collecting_enabled(False)
        self.seed_config.set_libtorrent_enabled(True)
        self.seed_config.set_video_server_enabled(False)
        self.seed_config.set_metadata_enabled(False)
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
        self.seeder_session.prestart()
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

    def assert_(self, boolean, reason=None, do_assert=True, tribler_session=None, dump_statistics=False):
        if not boolean:
            # print statistics if needed
            if tribler_session and dump_statistics:
                self._print_statistics(tribler_session.get_tribler_statistics())
                self._print_statistics(tribler_session.get_dispersy_statistics())
                self._print_statistics(tribler_session.get_community_statistics())

            self.quit()
            assert boolean, reason

    @blocking_call_on_reactor_thread
    def _print_statistics(self, statistics_dict):
        def _print_data_dict(data_dict, level):
            for k, v in data_dict.iteritems():
                indents = u'-' + u'-' * 2 * level

                if isinstance(v, basestring):
                    self._logger.debug(u"%s %s: %s", indents, k, v)
                elif isinstance(v, dict):
                    self._logger.debug(u"%s %s:", indents, k)
                    _print_data_dict(v, level + 1)
                else:
                    # ignore other types for the moment
                    continue
        self._logger.debug(u"========== Tribler Statistics BEGIN ==========")
        _print_data_dict(statistics_dict, 0)
        self._logger.debug(u"========== Tribler Statistics END ==========")

    def startTest(self, callback):
        self.quitting = False
        callback()

    def callLater(self, seconds, callback):
        if not self.quitting:
            if seconds:
                time.sleep(seconds)
            callback()

    def CallConditional(self, timeout, condition, callback, assert_message=None, assert_callback=None,
                        tribler_session=None, dump_statistics=False):
        t = time.time()

        def DoCheck():
            if not self.quitting:
                # only use the last two parts as the ID because the full name is too long
                test_id = self.id()
                test_id = '.'.join(test_id.split('.')[-2:])

                if time.time() - t < timeout:
                    try:
                        if condition():
                            self._logger.debug("%s - condition satisfied after %d seconds, calling callback '%s'",
                                               test_id, time.time() - t, callback.__name__)
                            callback()
                        else:
                            self.callLater(0.5, DoCheck)

                    except:
                        print_exc()
                        self.assert_(False, '%s - Condition or callback raised an exception, quitting (%s)' %
                                     (test_id, assert_message or "no-assert-msg"), do_assert=False)
                else:
                    self._logger.debug("%s - %s, condition was not satisfied in %d seconds (%s)",
                                       test_id,
                                       ('calling callback' if assert_callback else 'quitting'),
                                       timeout,
                                       assert_message or "no-assert-msg")
                    assertcall = assert_callback if assert_callback else self.assert_
                    kwargs = {}
                    if assertcall == self.assert_:
                        kwargs = {'tribler_session': tribler_session, 'dump_statistics': dump_statistics}

                    assertcall(False, "%s - %s - Condition was not satisfied in %d seconds" %
                               (test_id, assert_message, timeout), do_assert=False, **kwargs)
        self.callLater(0, DoCheck)

    def quit(self):
        self.quitting = True
