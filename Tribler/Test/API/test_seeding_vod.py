# Written by Arno Bakker, heavily modified by Niels Zeilemaker
# see LICENSE.txt for license information

from twisted.internet.defer import inlineCallbacks, Deferred

from Tribler.Test.API.test_seeding import TestSeeding
from Tribler.Core.simpledefs import dlstatus_strings, DLMODE_VOD


class TestVODSeeding(TestSeeding):

    """
    Testing seeding via new tribler API:
    """

    def setUp(self):
        super(TestVODSeeding, self).setUp()
        self.vod_deferred = Deferred()

    @inlineCallbacks
    def setup_seeder(self, filename='video.avi'):
        yield super(TestVODSeeding, self).setup_seeder(filename)

    @inlineCallbacks
    def subtest_download(self):
        self.dscfg2.set_mode(DLMODE_VOD)
        yield super(TestVODSeeding, self).subtest_download()
        yield self.vod_deferred

    def downloader_state_callback(self, ds):
        d = ds.get_download()
        self._logger.debug("download: %s %s %s %s", repr(d.get_def().get_name()),
                           dlstatus_strings[ds.get_status()], ds.get_progress(),
                           ds.get_vod_prebuffering_progress())

        if ds.get_progress() > 0:
            if not self.downloading_deferred.called:
                self.downloading_deferred.callback(None)
        if ds.get_vod_prebuffering_progress() == 1.0:
            if not self.vod_deferred.called:
                self.vod_deferred.callback(None)

        return 1.0, False
