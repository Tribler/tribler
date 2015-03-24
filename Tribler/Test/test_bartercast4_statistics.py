from Tribler.Test.test_as_server import AbstractServer
from Tribler.dispersy.util import blocking_call_on_reactor_thread
from Tribler.community.bartercast4.statistics import BarterStatistics, BartercastStatisticTypes
from Tribler.dispersy.dispersy import Dispersy
from Tribler.dispersy.endpoint import ManualEnpoint


class TestBarterStatistics(AbstractServer):

    def setUp(self):
        super(TestBarterStatistics, self).setUp()
        self.stats = BarterStatistics()
        self._peer1 = "peer1"
        self._peer2 = "peer2"
        self._peer3 = "peer3"
        self._peer4 = "peer4"
        self._peer5 = "peer5"
        self.dispersy = Dispersy(ManualEnpoint(0), self.getStateDir())

    def test_create_db(self):
        # check that values are initialized to 0
        assert len(self.stats.bartercast[BartercastStatisticTypes.TUNNELS_EXIT_BYTES_RECEIVED]) == 0

    def test_dict_inc_bartercast(self):
        self.stats.dict_inc_bartercast(BartercastStatisticTypes.TUNNELS_EXIT_BYTES_RECEIVED, self._peer1, 5)
        assert len(self.stats.bartercast[BartercastStatisticTypes.TUNNELS_EXIT_BYTES_RECEIVED]) == 1
        assert self.stats.bartercast[BartercastStatisticTypes.TUNNELS_EXIT_BYTES_RECEIVED][self._peer1] == 5
        self.stats.dict_inc_bartercast(BartercastStatisticTypes.TUNNELS_EXIT_BYTES_RECEIVED, self._peer1, 5)
        assert len(self.stats.bartercast[BartercastStatisticTypes.TUNNELS_EXIT_BYTES_RECEIVED]) == 1
        assert self.stats.bartercast[BartercastStatisticTypes.TUNNELS_EXIT_BYTES_RECEIVED][self._peer1] == 10
        self.stats.dict_inc_bartercast(BartercastStatisticTypes.TUNNELS_EXIT_BYTES_SENT, self._peer1)
        assert len(self.stats.bartercast[BartercastStatisticTypes.TUNNELS_EXIT_BYTES_SENT]) == 1
        assert self.stats.bartercast[BartercastStatisticTypes.TUNNELS_EXIT_BYTES_SENT][self._peer1] == 1

    def test_get_top_n_bartercast_statistics(self):
        self.stats.dict_inc_bartercast(BartercastStatisticTypes.TUNNELS_EXIT_BYTES_RECEIVED, self._peer1, 5)
        self.stats.dict_inc_bartercast(BartercastStatisticTypes.TUNNELS_EXIT_BYTES_RECEIVED, self._peer2, 5)
        self.stats.dict_inc_bartercast(BartercastStatisticTypes.TUNNELS_EXIT_BYTES_RECEIVED, self._peer3, 5)
        self.stats.dict_inc_bartercast(BartercastStatisticTypes.TUNNELS_EXIT_BYTES_RECEIVED, self._peer4, 10)
        self.stats.dict_inc_bartercast(BartercastStatisticTypes.TUNNELS_EXIT_BYTES_RECEIVED, self._peer5, 15)
        assert len(self.stats.bartercast[BartercastStatisticTypes.TUNNELS_EXIT_BYTES_RECEIVED]) == 5
        top1 = self.stats.get_top_n_bartercast_statistics(BartercastStatisticTypes.TUNNELS_EXIT_BYTES_RECEIVED, 1)
        assert len(top1) == 1
        assert top1[0][0] == self._peer5
        top2 = self.stats.get_top_n_bartercast_statistics(BartercastStatisticTypes.TUNNELS_EXIT_BYTES_RECEIVED, 2)
        assert len(top2) == 2
        assert top2[0][0] == self._peer5
        top3 = self.stats.get_top_n_bartercast_statistics(BartercastStatisticTypes.TUNNELS_EXIT_BYTES_RECEIVED, 3)
        assert len(top3) == 3
        assert top3[0][0] == self._peer5
        assert top3[1][0] == self._peer4
        assert top3[2][0] == self._peer3 or top3[2][0] == self._peer2 or top3[2][0] == self._peer1

        top0 = self.stats.get_top_n_bartercast_statistics(999, 1)
        assert len(top0) == 0

    def test_should_persist(self):
        assert self.stats.should_persist(BartercastStatisticTypes.TUNNELS_EXIT_BYTES_RECEIVED, 1)
        assert not self.stats.should_persist(BartercastStatisticTypes.TUNNELS_EXIT_BYTES_SENT, 2)
        assert self.stats.should_persist(BartercastStatisticTypes.TUNNELS_EXIT_BYTES_SENT, 2)

    @blocking_call_on_reactor_thread
    def test_load_persist(self):
        self.stats.dict_inc_bartercast(BartercastStatisticTypes.TUNNELS_EXIT_BYTES_RECEIVED, self._peer1, 5)
        self.stats.dict_inc_bartercast(BartercastStatisticTypes.TUNNELS_EXIT_BYTES_RECEIVED, self._peer2, 5)
        self.stats.dict_inc_bartercast(BartercastStatisticTypes.TUNNELS_EXIT_BYTES_RECEIVED, self._peer3, 5)
        self.stats.dict_inc_bartercast(BartercastStatisticTypes.TUNNELS_EXIT_BYTES_RECEIVED, self._peer4, 10)
        self.stats.dict_inc_bartercast(BartercastStatisticTypes.TUNNELS_EXIT_BYTES_RECEIVED, self._peer5, 15)
        assert len(self.stats.bartercast[BartercastStatisticTypes.TUNNELS_EXIT_BYTES_RECEIVED]) == 5
        self.stats.persist(self.dispersy, 1)
        self.stats.db.close()
        self.stats = BarterStatistics()
        assert len(self.stats.bartercast[BartercastStatisticTypes.TUNNELS_EXIT_BYTES_RECEIVED]) == 0
        self.stats.load_statistics(self.dispersy)
        assert len(self.stats.bartercast[BartercastStatisticTypes.TUNNELS_EXIT_BYTES_RECEIVED]) == 5

    @blocking_call_on_reactor_thread
    def test_log_interaction(self):
        self.stats.log_interaction(self.dispersy, BartercastStatisticTypes.TUNNELS_EXIT_BYTES_RECEIVED,
                                   self._peer1, self._peer2, 123)

        records = self.stats.db.execute(u"SELECT type, peer1, peer2, value FROM interaction_log")
        r = records.fetchone()
        assert r[0] == BartercastStatisticTypes.TUNNELS_EXIT_BYTES_RECEIVED
        assert r[1] == self._peer1
        assert r[2] == self._peer2
        assert r[3] == 123
