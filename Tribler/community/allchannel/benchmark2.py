import os

import time
from twisted.internet.threads import deferToThread

import yappi
from twisted.internet.defer import inlineCallbacks, Deferred, DeferredList

from twisted.internet import reactor

import apsw


class Benchmark:
    def __init__(self):
        dburl = os.path.join(os.getcwd(), "benchmark")
        self.connection = apsw.Connection(dburl)
        cursor = self.connection.cursor()
        # Ensure to delete the old test table if it exists
        cursor.execute("DROP TABLE IF EXISTS test")
        cursor.execute("CREATE TABLE test(x,y,z)")

    def start_experiment(self):
        self.insert_stuff()
        reactor.callWhenRunning(self.run)
        reactor.run()

    def run(self):
        self.query_time()

    def tear_down(self, ignored):
        reactor.stop()

    def insert_stuff(self):
        cursor = self.connection.cursor()
        cursor.execute("BEGIN TRANSACTION;")
        for i in xrange(1000000):
            cursor.execute("insert into test values(?,?,?)", (i, float(i * 1.01), str(i)))
        cursor.execute("COMMIT;")

    @inlineCallbacks
    def query_time(self):
        blocking = False  # Asynchronous, but blocking?
        max_delay = 1  # max delay in seconds
        calls = 100  # amount of calls
        step_delay = float(float(max_delay) / float(calls))
        write_statistics = False

        # make sure the threadpool is initialized by doing a bogus call
        yield self.nice_query(0, blocking, Deferred())

        if blocking:
            calls_made = open("profiling/simple_calls_made_blocking.txt", 'w')
            calls_done = open("profiling/simple_calls_done_blocking.txt", "w")
        else:
            calls_made = open("profiling/simple_calls_made_async.txt", 'w')
            calls_done = open("profiling/simple_calls_done_async.txt", "w")

        def print_done(i, deferred):
            calls_done.write("%s %s %s\n" % (i, float(step_delay * i), int(round(time.time() * 1000))))
            deferred.callback(None)

        yappi.set_clock_type('cpu')
        yappi.start(builtins=True)

        def on_write_done(x):
            calls_made.flush()
            calls_done.flush()

        deferred_list_write = []
        deferred_list = []

        for i in xrange(calls):
            d1 = Deferred()
            d2 = Deferred()
            calls_made.write("%s %s %s\n" % (i, float(i * step_delay), int(round(time.time() * 1000))))
            reactor.callLater(float(i * step_delay), print_done, i, d1)
            reactor.callLater(float(i * step_delay), self.nice_query, i, blocking, d2)
            deferred_list_write.append(d1)
            deferred_list.append(d1)
            deferred_list.append(d2)

        DeferredList(deferred_list_write).addCallback(on_write_done)
        DeferredList(deferred_list).addCallback(self.tear_down)

        # yappi.stop()
        #
        # stats = yappi.get_func_stats()
        # stats.sort("tsub").print_all(columns={0:("name",100), 1:("ncall", 12), 2:("tsub", 10), 3:("ttot", 10), 4:("tavg",10)})
        #
        # if write_statistics:
        #     name = "profiling/simple_benchmark_%s_%s.pstat" % (calls, time.strftime("%d-%m-%Y-%H-%M-%S"))
        #     stats.sort("tsub").save(name, type="pstat")
        #
        # calls_made.flush()
        # calls_done.flush()

    @inlineCallbacks
    def nice_query(self, i, blocking, deferred):
        cursor = self.connection.cursor()
        sql = u"SELECT COUNT(*) FROM test WHERE x > ? AND z like ?"
        if blocking:
            result = yield cursor.execute(sql, (i, "%3%"))
        else:
            result = yield deferToThread(cursor.execute, sql, (i, "%3%"))
        deferred.callback(None)


if __name__ == "__main__":
    b = Benchmark()
    b.start_experiment()
