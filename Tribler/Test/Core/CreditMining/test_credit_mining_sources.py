"""
Module of Credit mining function testing.

Author(s): Mihai Capota, Ardhi Putra
"""
import os
from asyncio import Future

from pony.orm import db_session

from Tribler.Core.CreditMining.CreditMiningSource import ChannelSource
from Tribler.Test.test_as_server import TestAsServer
from Tribler.Test.tools import timeout


class TestCreditMiningSources(TestAsServer):
    """
    Class to test the credit mining sources
    """

    def setUpPreSession(self):
        super(TestCreditMiningSources, self).setUpPreSession()
        self.config.set_chant_enabled(True)

    @timeout(5)
    async def test_channel_lookup(self):
        test_future = Future()

        with db_session:
            my_channel = self.session.mds.ChannelMetadata.create_channel('test', 'test')
            self.session.mds.TorrentMetadata(origin_id=my_channel.id_, title='testtorrent', infohash=os.urandom(20))

        source = ChannelSource(self.session, my_channel.public_key, lambda *_: test_future.set_result(None))
        source.start()
        await test_future
