"""
Module of Credit mining function testing.

Author(s): Mihai Capota, Ardhi Putra
"""
from __future__ import absolute_import

import random

from pony.orm import db_session

from twisted.internet.defer import Deferred

from Tribler.Core.CreditMining.CreditMiningSource import ChannelSource
from Tribler.Test.test_as_server import TestAsServer
from Tribler.Test.tools import trial_timeout


class TestCreditMiningSources(TestAsServer):
    """
    Class to test the credit mining sources
    """

    def setUpPreSession(self):
        super(TestCreditMiningSources, self).setUpPreSession()
        self.config.set_chant_enabled(True)

    @trial_timeout(5)
    def test_channel_lookup(self):
        test_deferred = Deferred()

        with db_session:
            my_channel = self.session.lm.mds.ChannelMetadata.create_channel('test', 'test')
            self.session.lm.mds.TorrentMetadata(origin_id=my_channel.id_, title='testtorrent',
                                                infohash=str(random.getrandbits(160)))

        source = ChannelSource(self.session, str(my_channel.public_key), lambda *_: test_deferred.callback(None))
        source.start()
        return test_deferred
