# Written by Arno Bakker, heavily modified by Niels Zeilemaker
# see LICENSE.txt for license information

import sys
import threading
from Tribler.Test.API.test_seeding import TestSeeding
from Tribler.Core.simpledefs import dlstatus_strings, DLMODE_VOD, VODEVENT_START
import unittest


class TestVODSeeding(TestSeeding):

    """
    Testing seeding via new tribler API:
    """
    def setUp(self):
        TestSeeding.setUp(self)
        self.vod_event = threading.Event()

    def setup_seeder(self, filename='file2.wmv'):
        TestSeeding.setup_seeder(self, filename)

    def subtest_download(self):
        self.dscfg2.set_video_event_callback(self.downloader_vod_ready_callback)
        self.dscfg2.set_mode(DLMODE_VOD)
        TestSeeding.subtest_download(self)
        assert self.vod_event.wait(60)

    def downloader_state_callback(self, ds):
        d = ds.get_download()
        print("test: download:", repr(d.get_def().get_name()), dlstatus_strings[ds.get_status()], ds.get_progress(), file=sys.stderr)

        if ds.get_progress() > 0:
            self.downloading_event.set()

        return (1.0, False)

    def downloader_vod_ready_callback(self, d, event, params):
        if event == VODEVENT_START:
            self.vod_event.set()
