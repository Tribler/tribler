from Tribler.dispersy.database import Database
import random
from operator import itemgetter
from collections import defaultdict
from os import path
from threading import RLock
import logging


class BarterStatistics(object):
    def __init__(self):
        self.db = None
        self._db_counter = dict()
        self._lock = RLock()
        self.bartercast = defaultdict()
        self.db_closed = True
        for t in BartercastStatisticTypes.reverse_mapping:
            self.bartercast[t] = defaultdict()
        self._logger = logging.getLogger(self.__class__.__name__)

    def dict_inc_bartercast(self, stats_type, peer, value=1):
        if not hasattr(self, "bartercast"):
                self._logger.error(u"bartercast doesn't exist in statistics")
        with self._lock:
            if peer not in self.bartercast[stats_type]:
                self.bartercast[stats_type][peer] = value
            else:
                self.bartercast[stats_type][peer] += value

    def get_top_n_bartercast_statistics(self, key, n):
        """
        Returns top n-n/2 barter cast statistics, +n/2 randomly selected statistics from the rest of the list.
        The randomly selected statistics are added to make sure that less active peers get a chance to appear in the rankings
        as well.
        @TODO check if random portion should be larger or smaller
        """
        with self._lock:
            # shouldn't happen but dont crash the program when bartercast statistics are not available
            if not hasattr(self, "bartercast"):
                self._logger.error(u"bartercast doesn't exist in statistics")
                return []
            if not key in getattr(self, "bartercast").keys():
                self._logger.error(u"%s doesn't exist in bartercast statistics" % key)
                return []
            d = getattr(self, "bartercast")[key]
            if d is not None:
                random_n = n / 2
                fixed_n = n - random_n
                sorted_list = sorted(d.items(), key=itemgetter(1), reverse=True)
                top_stats = sorted_list[0:fixed_n]
                self._logger.error("len d: %d, fixed_n: %d" % (len(d), fixed_n))
                if len(d) <= fixed_n:
                    random_stats = []
                else:
                    random_stats = random.sample(sorted_list[fixed_n:len(d)], min(random_n, len(d) - fixed_n))
                return top_stats + random_stats
            return None

    def log_interaction(self, dispersy, type, peer1, peer2, value):
        """
        Add statistic for interactions between peer1 and peer2 to the interaction log.
        """
        self._init_database(dispersy)
        self.db.execute(u"INSERT INTO interaction_log (peer1, peer2, type, value, date) values (?, ?, ?, ?, strftime('%s', 'now'))", (unicode(peer1), unicode(peer2), type, value))

    def persist(self, dispersy, key, n=1):
        """
        Persists the statistical data with name 'key' in the statistics database.
        Note: performs the database update for every n-th call. This is to somewhat control the number of
        writes for statistics that are updated often.
        """
        if not self.should_persist(key, n):
            return

        self._init_database(dispersy)
        self._logger.debug("persisting bc data")
        for t in self.bartercast:
            for peer in self.bartercast[t]:
                self.db.execute(u"INSERT OR REPLACE INTO statistic (type, peer, value) values (?, ?, ?)", (t, unicode(peer), self.bartercast[t][peer]))
        self._logger.debug("data persisted")

    def load_statistics(self, dispersy):
        """
        Loads the bartercast statistics from the sqlite database.
        """
        self._init_database(dispersy)
        data = self.db.execute(u"SELECT type, peer, value FROM statistic")
        statistics = defaultdict()
        for t in BartercastStatisticTypes.reverse_mapping:
            statistics[t] = defaultdict()
        for row in data:
            t = row[0]
            peer = row[1]
            value = row[2]
            if not t in statistics:
                statistics[t] = defaultdict()
            statistics[t][peer] = value
        self.bartercast = statistics
        return statistics

    def _init_database(self, dispersy):
        """
        Initialise database for use in this class.
        """
        if self.db is None or self.db_closed:
            self.db = StatisticsDatabase(dispersy)
            self.db.open()
            self.db_closed = False

    def should_persist(self, key, n):
        """
        Return true and reset counter for key iff the data should be persisted (for every n calls).
        Otherwise increases the counter for key. This can reduce write traffic to the database if necessary.
        """
        if key not in self._db_counter:
            self._db_counter[key] = 1
        else:
            self._db_counter[key] = self._db_counter[key] + 1
        if n <= self._db_counter[key]:
            self._db_counter[key] = 0
            return True
        return False

    def close(self):
        if self.db is not None and not self.db_closed:
            self.db.close()
            self.db_closed = True

LATEST_VERSION = 1

schema = u"""
CREATE TABLE statistic(
 id INTEGER,                            -- primary key
 type INTEGER,                            -- type of interaction
 peer TEXT,
 value INTEGER,
 PRIMARY KEY (id),
 UNIQUE (type, peer));

CREATE TABLE option(key TEXT PRIMARY KEY, value BLOB);
INSERT INTO option(key, value) VALUES('database_version', '""" + str(LATEST_VERSION) + """');

CREATE TABLE interaction_log(
 id INTEGER,                            -- primary key
 peer1 TEXT,
 peer2 TEXT,
 type INTEGER,                        -- type of interaction
 value INTEGER,
 date INTEGER,
 PRIMARY KEY (id));
"""

cleanup = u"""
DELETE FROM statistic;
"""


class StatisticsDatabase(Database):
    if __debug__:
        __doc__ = schema

    def __init__(self, dispersy):
        self._dispersy = dispersy
        super(StatisticsDatabase, self).__init__(path.join(dispersy.working_directory, u"sqlite", u"statistics.db"))

    def open(self):
        self._dispersy.database.attach_commit_callback(self.commit)
        return super(StatisticsDatabase, self).open()

    def close(self, commit=True):
        self._dispersy.database.detach_commit_callback(self.commit)
        return super(StatisticsDatabase, self).close(commit)

    def cleanup(self):
        self.executescript(cleanup)

    def check_database(self, database_version):
        assert isinstance(database_version, unicode)
        assert database_version.isdigit()
        assert int(database_version) >= 0
        database_version = int(database_version)

        # setup new database with current database_version
        if database_version < 1:
            self.executescript(schema)
            self.commit()

        else:
            # upgrade to version 2
            if database_version < 2:
                # there is no version 2 yet...
                # if __debug__: dprint("upgrade database ", database_version, " -> ", 2)
                # self.executescript(u"""UPDATE option SET value = '2' WHERE key = 'database_version';""")
                # self.commit()
                # if __debug__: dprint("upgrade database ", database_version, " -> ", 2, " (done)")
                pass

        return LATEST_VERSION


def enum(*sequential, **named):
    enums = dict(zip(sequential, range(len(sequential))), **named)
    reverse = dict((value, key) for key, value in enums.iteritems())
    enums['reverse_mapping'] = reverse
    return type('Enum', (), enums)

BartercastStatisticTypes = enum(TORRENTS_RECEIVED=1, TUNNELS_CREATED=2, \
                                TUNNELS_BYTES_SENT=3, TUNNELS_RELAY_BYTES_SENT=4, TUNNELS_EXIT_BYTES_SENT=5, \
                                TUNNELS_BYTES_RECEIVED=6, TUNNELS_RELAY_BYTES_RECEIVED=7, TUNNELS_EXIT_BYTES_RECEIVED=8)

_barter_statistics = BarterStatistics()
