from Tribler.Core.CacheDB.SqliteCacheDBHandler import VoteCastDBHandler, ChannelCastDBHandler
from Tribler.Test.Core.test_sqlitecachedbhandler import AbstractDB
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestVotecastDBHandler(AbstractDB):

    def setUp(self):
        super(TestVotecastDBHandler, self).setUp()

        self.cdb = ChannelCastDBHandler(self.session)
        self.vdb = VoteCastDBHandler(self.session)
        self.vdb.channelcast_db = self.cdb

    def tearDown(self):
        self.cdb.close()
        self.cdb = None
        self.vdb.close()
        self.vdb = None

        super(TestVotecastDBHandler, self).tearDown()

    @blocking_call_on_reactor_thread
    def test_on_votes_from_dispersy(self):
        self.vdb.my_votes = {}
        votes = [[1, None, 1, 2, 12345], [1, None, 2, -1, 12346], [2, 3, 2, -1, 12347]]
        self.vdb.on_votes_from_dispersy(votes)
        self.vdb._flush_to_database()
        self.assertEqual(self.vdb.getPosNegVotes(1), (3, 1))

        self.vdb.my_votes = None
        votes = [[4, None, 1, 2, 12346]]
        self.vdb.on_votes_from_dispersy(votes)
        self.assertEqual(self.vdb.updatedChannels, {4})

    @blocking_call_on_reactor_thread
    def test_on_remove_votes_from_dispersy(self):
        remove_votes = [[12345, 2, 3]]
        self.vdb.on_remove_votes_from_dispersy(remove_votes, False)
        self.assertEqual(self.vdb.updatedChannels, {2})
        remove_votes = [[12345, 2, 3], [12346, 1, 3]]
        self.vdb.on_remove_votes_from_dispersy(remove_votes, True)

    @blocking_call_on_reactor_thread
    def test_flush_to_database(self):
        self.assertEqual(self.vdb.getPosNegVotes(1), (7, 5))
        self.vdb.updatedChannels = {1}
        self.vdb._flush_to_database()
        self.assertEqual(self.vdb.getPosNegVotes(1), (2, 0))
        self.vdb.updatedChannels = {}
        self.vdb._flush_to_database()

    @blocking_call_on_reactor_thread
    def test_get_latest_vote_dispersy_id(self):
        self.assertEqual(self.vdb.get_latest_vote_dispersy_id(2, 5), 3)
        self.assertEqual(self.vdb.get_latest_vote_dispersy_id(1, None), 3)

    @blocking_call_on_reactor_thread
    def test_get_pos_neg_votes(self):
        self.assertEqual(self.vdb.getPosNegVotes(1), (7, 5))
        self.assertEqual(self.vdb.getPosNegVotes(2), (93, 83))
        self.assertEqual(self.vdb.getPosNegVotes(42), (0, 0))

    @blocking_call_on_reactor_thread
    def test_get_vote_on_channel(self):
        self.assertEqual(self.vdb.getVoteOnChannel(3, 6), -1)
        self.assertEqual(self.vdb.getVoteOnChannel(4, None), -1)

    @blocking_call_on_reactor_thread
    def test_get_vote_for_my_channel(self):
        self.vdb.channelcast_db._channel_id = 1
        self.assertEqual(self.vdb.getVoteForMyChannel(6), 2)

    @blocking_call_on_reactor_thread
    def test_get_dispersy_id(self):
        self.assertEqual(self.vdb.getDispersyId(2, 5), 3)
        self.assertEqual(self.vdb.getDispersyId(2, None), 3)

    @blocking_call_on_reactor_thread
    def test_get_timestamp(self):
        self.assertEqual(self.vdb.getTimestamp(2, 5), 8440)
        self.assertEqual(self.vdb.getTimestamp(2, None), 8439)

    @blocking_call_on_reactor_thread
    def test_get_my_votes(self):
        my_votes = self.vdb.getMyVotes()
        self.assertEqual(my_votes, {1: 2, 2: -1, 4: -1})
        self.assertIsNotNone(self.vdb.my_votes)
        my_votes = self.vdb.getMyVotes()
        self.assertEqual(my_votes, {1: 2, 2: -1, 4: -1})
