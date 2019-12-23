"""
Testing as server.

Author(s): Arno Bakker, Jie Yang, Niels Zeilemaker
"""
import functools
import inspect
import logging
import os
import random
import re
import shutil
import string
import time
from asyncio import Future, current_task, get_event_loop
from threading import enumerate as enumerate_threads

from aiohttp import web

import asynctest

from configobj import ConfigObj

from Tribler.Core.Config.download_config import DownloadConfig
from Tribler.Core.Config.tribler_config import CONFIG_SPEC_PATH, TriblerConfig
from Tribler.Core.Session import Session
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Utilities.instrumentation import WatchDog
from Tribler.Core.Utilities.network_utils import get_random_port
from Tribler.Core.simpledefs import DLSTATUS_SEEDING, dlstatus_strings
from Tribler.Test.util.util import process_unhandled_exceptions, process_unhandled_twisted_exceptions

TESTS_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
TESTS_DATA_DIR = os.path.abspath(os.path.join(TESTS_DIR, u"data"))
TESTS_API_DIR = os.path.abspath(os.path.join(TESTS_DIR, u"API"))
OUTPUT_DIR = os.path.abspath(os.environ.get('OUTPUT_DIR', 'output'))


class BaseTestCase(asynctest.TestCase):

    def __init__(self, *args, **kwargs):
        super(BaseTestCase, self).__init__(*args, **kwargs)
        self.selected_ports = set()
        self._tempdirs = []
        self.maxDiff = None  # So we see full diffs when using assertEqual

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

    def tearDown(self):
        while self._tempdirs:
            temp_dir = self._tempdirs.pop()
            os.chmod(temp_dir, 0o700)
            shutil.rmtree(temp_dir, ignore_errors=False)

    def temporary_directory(self, suffix='', exist_ok=False):
        random_string = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(6))
        temp = os.path.join(TESTS_DIR, "temp", self.__class__.__name__ + suffix + random_string)
        self._tempdirs.append(temp)
        try:
            os.makedirs(temp)
        except FileExistsError as e:
            if not exist_ok:
                raise e
        return temp

    def get_bucket_range_port(self):
        """
        Return the port range of the test bucket assigned.
        """
        test_bucket = os.environ.get("TEST_BUCKET", None)
        if test_bucket is not None:
            test_bucket = int(test_bucket) + int(os.environ.get('TEST_BUCKET_OFFSET', 0))

        min_base_port = 1024 if test_bucket is None else test_bucket * 2000 + 2000
        return min_base_port, min_base_port + 2000

    def get_ports(self, count):
        """
        Return random, free ports.
        This is here to make sure that tests in different buckets get assigned different listen ports.
        Also, make sure that we have no duplicates in selected ports.
        """
        ports = []
        for _ in range(count):
            min_base_port, max_base_port = self.get_bucket_range_port()
            selected_port = get_random_port(min_port=min_base_port, max_port=max_base_port)
            while selected_port in self.selected_ports:
                selected_port = get_random_port(min_port=min_base_port, max_port=max_base_port)
            self.selected_ports.add(selected_port)
            ports.append(selected_port)
        return ports

    def get_port(self):
        return self.get_ports(1)[0]


class AbstractServer(BaseTestCase):

    _annotate_counter = 0

    def __init__(self, *args, **kwargs):
        super(AbstractServer, self).__init__(*args, **kwargs)
        get_event_loop().set_debug(True)

        self.watchdog = WatchDog()

    async def setUp(self):
        self._logger = logging.getLogger(self.__class__.__name__)

        self.session_base_dir = self.temporary_directory(suffix=u"_tribler_test_session_")
        self.state_dir = os.path.join(self.session_base_dir, u"dot.Tribler")
        self.dest_dir = os.path.join(self.session_base_dir, u"TriblerDownloads")

        self.annotate_dict = {}

        self.file_server = None
        self.dscfg_seed = None

        self.annotate(self._testMethodName, start=True)
        self.watchdog.start()
        random.seed(123)

    async def setUpFileServer(self, port, path):
        # Create a local file server, can be used to serve local files. This is preferred over an external network
        # request in order to get files.
        app = web.Application()
        app.add_routes([web.static('/', path)])
        runner = web.AppRunner(app, access_log=None)
        await runner.setup()
        self.site = web.TCPSite(runner, 'localhost', port)
        await self.site.start()

    async def checkLoop(self, phase, *_):
        from pony.orm.core import local
        if local.db_context_counter > 0:
            self._logger.error("Leftover pony db sessions found!")
        from pony.orm import db_session
        for _ in range(local.db_context_counter):
            db_session.__exit__()

        # Only in Python 3.7+..
        try:
            from asyncio import all_tasks
        except ImportError:
            return

        tasks = [t for t in all_tasks(get_event_loop()) if t is not current_task()]
        if tasks:
            self._logger.error("The event loop was dirty during %s:", phase)
        for task in tasks:
            self._logger.error(">     %s", task)

    async def tearDown(self):
        random.seed()
        self.annotate(self._testMethodName, start=False)

        process_unhandled_exceptions()
        process_unhandled_twisted_exceptions()

        self.watchdog.join(2)
        if self.watchdog.is_alive():
            self._logger.critical("The WatchDog didn't stop!")
            self.watchdog.print_all_stacks()
            raise RuntimeError("Couldn't stop the WatchDog")

        if self.file_server:
            await self.file_server.stop()
        await self.checkLoop("tearDown")

        super(AbstractServer, self).tearDown()

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
            is_file_exist = os.path.exists(filename)
            mode = 'a' if is_file_exist else 'w'

            with open(filename, mode=mode) as f:
                if not is_file_exist:
                    f.write("annotation start end\n")
                AbstractServer._annotate_counter += 1
                _annotation = re.sub('[^a-zA-Z0-9_]', '_', annotation)
                _annotation = u"%d_" % AbstractServer._annotate_counter + _annotation

                f.write("%s %s %s\n" % (_annotation, self.annotate_dict[annotation], time.time()))


class TestAsServer(AbstractServer):

    """
    Parent class for testing the server-side of Tribler
    """

    async def setUp(self):
        await super(TestAsServer, self).setUp()
        self.setUpPreSession()

        self.quitting = False
        self.seeding_future = Future()
        self.seeder_session = None
        self.seed_config = None

        self.session = Session(self.config)
        self.session.upgrader_enabled = False

        await self.session.start()

        self.hisport = self.session.config.get_libtorrent_port()

        self.annotate(self._testMethodName, start=True)

    def setUpPreSession(self):
        self.config = TriblerConfig(ConfigObj(configspec=CONFIG_SPEC_PATH, default_encoding='utf-8'))
        self.config.set_default_destination_dir(self.dest_dir)
        self.config.set_state_dir(self.getStateDir())
        self.config.set_torrent_checking_enabled(False)
        self.config.set_ipv8_enabled(False)
        self.config.set_libtorrent_enabled(False)
        self.config.set_video_server_enabled(False)
        self.config.set_http_api_enabled(False)
        self.config.set_tunnel_community_enabled(False)
        self.config.set_credit_mining_enabled(False)
        self.config.set_market_community_enabled(False)
        self.config.set_popularity_community_enabled(False)
        self.config.set_dht_enabled(False)
        self.config.set_version_checker_enabled(False)
        self.config.set_libtorrent_dht_enabled(False)
        self.config.set_bitcoinlib_enabled(False)
        self.config.set_chant_enabled(False)
        self.config.set_resource_monitor_enabled(False)
        self.config.set_bootstrap_enabled(False)
        self.config.set_trustchain_enabled(False)

    async def tearDown(self):
        self.annotate(self._testMethodName, start=False)

        """ unittest test tear down code """
        if self.session is not None:
            self.session.ltmgr = None  # Just drop dead any ltmgr instance
            await self.session.shutdown()
            assert self.session.has_shutdown()
            self.session = None

        await self.stop_seeder()

        ts = enumerate_threads()
        self._logger.debug("test_as_server: Number of threads still running %d", len(ts))
        for t in ts:
            self._logger.debug("Thread still running %s, daemon: %s, instance: %s", t.getName(), t.isDaemon(), t)

        await super(TestAsServer, self).tearDown()

    def create_local_torrent(self, source_file):
        """
        This method creates a torrent from a local file and saves the torrent in the session state dir.
        Note that the source file needs to exist.
        """
        self.assertTrue(os.path.exists(source_file))

        tdef = TorrentDef()
        tdef.add_content(source_file)
        tdef.set_tracker("http://localhost/announce")
        torrent_path = os.path.join(self.session.config.get_state_dir(), "seed.torrent")
        tdef.save(torrent_filepath=torrent_path)

        return tdef, torrent_path

    async def setup_seeder(self, tdef, seed_dir, port=None):
        self.seed_config = TriblerConfig()
        self.seed_config.set_torrent_checking_enabled(False)
        self.seed_config.set_ipv8_enabled(False)
        self.seed_config.set_http_api_enabled(False)
        self.seed_config.set_libtorrent_enabled(True)
        self.seed_config.set_video_server_enabled(False)
        self.seed_config.set_tunnel_community_enabled(False)
        self.seed_config.set_market_community_enabled(False)
        self.seed_config.set_dht_enabled(False)
        self.seed_config.set_state_dir(self.getStateDir(2))
        self.seed_config.set_version_checker_enabled(False)
        self.seed_config.set_bitcoinlib_enabled(False)
        self.seed_config.set_chant_enabled(False)
        self.seed_config.set_credit_mining_enabled(False)
        self.seed_config.set_resource_monitor_enabled(False)
        self.seed_config.set_bootstrap_enabled(False)

        if port:
            self.seed_config.set_libtorrent_port(port)

        self.seeder_session = Session(self.seed_config)
        self.seeder_session.upgrader_enabled = False
        await self.seeder_session.start()
        self.dscfg_seed = DownloadConfig()
        self.dscfg_seed.set_dest_dir(seed_dir)
        download = self.seeder_session.ltmgr.add(tdef, self.dscfg_seed)
        download.set_state_callback(self.seeder_state_callback)

    async def stop_seeder(self):
        if self.seeder_session is not None:
            if self.seeder_session.ltmgr:
                self.seeder_session.ltmgr.is_shutdown_ready = lambda: True
            return await self.seeder_session.shutdown()

    def seeder_state_callback(self, ds):
        d = ds.get_download()
        self._logger.debug("seeder status: %s %s %s", repr(d.get_def().get_name()), dlstatus_strings[ds.get_status()],
                           ds.get_progress())

        if ds.get_status() == DLSTATUS_SEEDING:
            self.seeding_future.set_result(None)
            return 0.0

        return 1.0
