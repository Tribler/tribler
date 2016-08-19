# Written by Arno Bakker, heavily modified by Niels Zeilemaker
# see LICENSE.txt for license information

import sys
import threading
from twisted.internet.defer import inlineCallbacks
from Tribler.Test.API.test_seeding import TestSeeding
from Tribler.Core.simpledefs import dlstatus_strings, DLMODE_VOD
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestVODSeeding(TestSeeding):
    """
    Testing seeding via new tribler API:
    """

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self):
        yield super(TestVODSeeding, self).setUp()
        self.vod_event = threading.Event()

    def setup_seeder(self, filename='video.avi'):
        super(TestVODSeeding, self).setup_seeder(filename)

    def subtest_download(self):
        self.dscfg2.set_mode(DLMODE_VOD)
        super(TestVODSeeding, self).subtest_download()
        assert self.vod_event.wait(60)

    def downloader_state_callback(self, ds):
        d = ds.get_download()
        self._logger.debug("download: %s %s %s %s", repr(d.get_def().get_name()),
                           dlstatus_strings[ds.get_status()], ds.get_progress(),
                           ds.get_vod_prebuffering_progress())

        if ds.get_progress() > 0:
            self.downloading_event.set()
        if ds.get_vod_prebuffering_progress() == 1.0:
            self.vod_event.set()

        return 1.0, False
