import os
import time
from twisted.internet.task import deferLater

from twisted.internet.threads import deferToThread
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

    @inlineCallbacks
    def run(self):
        delay = [0.01, 0.02, 0.04, 0.08, 0.1]
        for d in delay:
            yield self.query_time(d, True) # One run with blocking code
            yield self.query_time(d, False) # and one without.
        self.tear_down()

    def tear_down(self):
        reactor.stop()

    def insert_stuff(self):
        cursor = self.connection.cursor()
        cursor.execute("BEGIN TRANSACTION;")
        for i in xrange(1000000):
            cursor.execute("insert into test values(?,?,?)", (i, float(i * 1.01), str(i)))
        cursor.execute("COMMIT;")

    @inlineCallbacks
    def query_time(self, call_delay, blocking):
        print "Starting %s with delay %s" % ("blocking" if blocking else "async", str(call_delay))
        calls = 100  # amount of calls

        # make sure the threadpool is initialized by doing a bogus call
        yield self.nice_query(0, blocking)

        calls_made = open("profiling/latencybenchmark_made_%s_%s_%s" % (
        "blocking" if blocking else "async", str(calls), str(call_delay)), 'w')
        calls_done = open("profiling/latencybenchmark_done_%s_%s_%s" % (
        "blocking" if blocking else "async", str(calls), str(call_delay)), "w")

        def print_done(i):
            calls_done.write("%s %s %s\n" % (i, call_delay * i * 1000, int(round(time.time() * 1000))))

        def on_write_done(ignored):
            calls_made.flush()
            calls_done.flush()

        deferred_list_write = []
        deferred_list = []

        for i in xrange(1, calls + 1):
            calls_made.write("%s %s %s\n" % (i, call_delay * i * 1000, int(round(time.time() * 1000))))
            d2 = deferLater(reactor, i * call_delay, self.nice_query, i, blocking)
            d1 = deferLater(reactor, i * call_delay, print_done, i)
            deferred_list_write.append(d1)
            deferred_list.append(d1)
            deferred_list.append(d2)

        DeferredList(deferred_list_write).addCallback(on_write_done)
        yield DeferredList(deferred_list)

    @inlineCallbacks
    def nice_query(self, i, blocking):
        cursor = self.connection.cursor()
        sql = u"SELECT COUNT(*) FROM test WHERE x > ? AND z like ?"
        if blocking:
            result = yield cursor.execute(sql, (2, "%3%"))
        else:
            result = yield deferToThread(cursor.execute, sql, (2, "%3%"))


if __name__ == "__main__":
    b = Benchmark()
    b.start_experiment()
