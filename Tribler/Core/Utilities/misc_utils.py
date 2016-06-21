from twisted.internet.defer import inlineCallbacks
from twisted.internet.threads import deferToThread
from twisted.internet import defer


def compute_ratio(i, j):
    return u"%d / %d ~%.1f%%" % (i, j, (100.0 * i / j) if j else 0.0)

@inlineCallbacks
def printDBStats(logger, session):
    """
    Queries the sqlite_master for all tables and then, for every
    table it prints the amount of rows per table using the logger.
    """
    sqlite_db = session.sqlite_db
    tables = yield deferToThread(sqlite_db.fetchall, "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    deferlist = []

    def print_table_counts(logger, results):
        for i in range (0, len(tables)):
            logger.info("%s %s", table, results[i])

    for table, in tables:
        deferlist.append(deferToThread(sqlite_db.fetchone, "SELECT COUNT(*) FROM %s" % table))
        # self._logger.info("%s %s", table, sqlite_db.fetchone("SELECT COUNT(*) FROM %s" % table))

    results = yield defer.gatherResults(deferlist)
    print_table_counts(logger, results)