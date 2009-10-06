"""
A simple interface to a reporting tool. The basic reporter stores
events that are periodically, or when flushed, send to a central
logging server.

Currently the logging server can be either at tribler.org or our
partners at the living lab. This is determened by the
USE_LIVING_LAB_REPORTING variable.
"""

import sys, urllib, zlib
import thread
import threading
from random import shuffle
from time import time
from traceback import print_exc
from Tribler.Core.Session import Session

PHONEHOME = True
USE_LIVING_LAB_REPORTING = False

DEBUG = False

if USE_LIVING_LAB_REPORTING:
    from Tribler.Core.Statistics.Status.Status import get_status_holder
    from Tribler.Core.Statistics.Status.LivingLabReporter import LivingLabOnChangeReporter

def get_reporter_instance():
    """
    A helper class that gets the right event reporter based on some
    configuration options.
    """
    session = Session.get_instance()

    if session.get_overlay():
        # hack: we should not import this since it is not part of
        # the core nor should we import here, but otherwise we
        # will get import errors
        #
        # note: the name VideoPlaybackDBHandler is a legacy name from
        # when this reporter was solely used to report video-playback
        # statistics.
        from Tribler.Core.CacheDB.SqliteVideoPlaybackStatsCacheDB import VideoPlaybackDBHandler
        return VideoPlaybackDBHandler.get_instance()
    else:
        return EventStatusReporter.get_instance(str(time()) + ":")

class EventStatusReporter:
    """
    Periodically report information to a central server (either TUD or
    ULANC)
    """
    __single = None    # used for multi-threaded singletons pattern
    lock = thread.allocate_lock()

    @classmethod
    def get_instance(cls, *args, **kw):
        # Singleton pattern with double-checking to ensure that it can only create one object
        if EventStatusReporter.__single is None:
            EventStatusReporter.lock.acquire()   
            try:
                if EventStatusReporter.__single is None:
                    EventStatusReporter.__single = cls(*args, **kw)
            finally:
                EventStatusReporter.lock.release()
        return EventStatusReporter.__single
    
    def __init__(self, prefix):
        if EventStatusReporter.__single is not None:
            raise RuntimeError, "EventStatusReporter is singleton"
        assert type(prefix) is str

        # the prefix is prepended to each event key
        self._prefix = prefix

        # thread-safety
        self._thread_lock = thread.allocate_lock()
        self._thread_flush = threading.Event()

        # the event table. one entry for each VOD event
        self._event = []

        # enable or disable reporting to the http server
        self._enable_reporting = PHONEHOME

        if self._enable_reporting:
            thread.start_new_thread(self._reporting_thread, ())

    def _reporting_thread(self):
        """
        Send the report on a seperate thread

        We choose not to use a lock object to protect access to
        self._enable_reporting, self._retry_delay, and
        self._report_deadline because only a single thread will write
        and the other threads will only read there variables. Python
        doesn't cause problems in this case.
        """
        # minimum retry delay. this value will grow exponentially with
        # every failure
        retry_delay = 15

        # the amount of time to sleep before the next report (or until
        # the _thread_event is set)
        timeout = retry_delay

        # a list containing all urlencoded reports that have yet been
        # send (most of the time this list will be empty, except when
        # reports could not be delivered)
        reports = []

        # local copy of the self._event when it is being reported
        event = None
        
        if USE_LIVING_LAB_REPORTING:
            # the m18 trial statistics are gathered at the 'living lab'
            session = Session.get_instance()
            living_lab_reporter = LivingLabOnChangeReporter("vod-stats-reporter")
            living_lab_reporter.set_permid(session.get_permid())
            status_holder = get_status_holder("vod-stats")
            status_holder.add_reporter(living_lab_reporter)
            status_element = status_holder.create_status_element("event", "A list containing timestamped VOD playback events", initial_value=[])

        else:
            # there are several urls available where reports can be
            # send. one should be picked randomly each time.
            #
            # when a report is successfull it will stay with the same
            # reporter. when a report is unsuccessfull (could not
            # connect) it will cycle through reporters.
            report_urls = [[0, 0, "http://reporter1.tribler.org/swarmplayer.py"],
                           [0, 0, "http://reporter2.tribler.org/swarmplayer.py"],
                           [0, 0, "http://reporter3.tribler.org/swarmplayer.py"],
                           [0, 0, "http://reporter4.tribler.org/swarmplayer.py"],
                           [0, 0, "http://reporter5.tribler.org/swarmplayer.py"],
                           [0, 0, "http://reporter6.tribler.org/swarmplayer.py"],
                           [0, 0, "http://reporter7.tribler.org/swarmplayer.py"],
                           [0, 0, "http://reporter8.tribler.org/swarmplayer.py"],
                           [0, 0, "http://reporter9.tribler.org/swarmplayer.py"]]
            shuffle(report_urls)

        while True:
            # sleep in betreen reports. will send a report immediately
            # when the flush event is set
            self._thread_flush.wait(timeout)
            self._thread_flush.clear()

            # create report
            self._thread_lock.acquire()
            try:
                if self._event:
                    # copy between threads while locked
                    event = self._event

                    self._event = []
                else:
                    # we have nothing to report... sleep
                    timeout = retry_delay
                    event = None

            finally:
                self._thread_lock.release()

            if USE_LIVING_LAB_REPORTING:
                if event:
                    try:
                        if status_element.set_value(event):
                            # Living lab's doesn't support dynamic reporting.
                            # We use 60 seconds by default
                            timeout = 60
                        else:
                            # something went wrong...
                            retry_delay *= 2
                            timeout = retry_delay
                    except:
                        # error contacting server
                        print_exc(file=sys.stderr)
                        retry_delay *= 2
                        timeout = retry_delay

            else:
                # add new report
                if event:
                    if len(event) < 10:
                        # uncompressed
                        report = {"version":"3",
                                  "created":time(),
                                  "event":event}
                    else:
                        # compress
                        report = {"version":"4",
                                  "created":time(),
                                  "event":urllib.quote(zlib.compress(repr(event), 9))}

                    reports.append(urllib.urlencode(report))

                if not reports:
                    timeout = retry_delay
                    continue

                reporter = report_urls[0]

                if DEBUG: print >> sys.stderr, "EventStatusReporter: attempting to report,", len(reports[0]), "bytes to", reporter[2]
                try:
                    sock = urllib.urlopen(reporter[2], reports[0])
                    result = sock.read()
                    sock.close()

                    # all ok? then remove the report
                    del reports[0]

                    # increase the 'good-report' counter, no need to re-order
                    reporter[1] += 1
                except:
                    # error contacting server
                    print_exc(file=sys.stderr)
                    retry_delay *= 2

                    # increase the 'bad-report' counter and order by failures
                    reporter[0] += 1
                    report_urls.sort(lambda x, y:cmp(x[0], y[0]))
                    continue

                if result.isdigit():
                    result = int(result)
                    if result == 0:
                        # remote server is not recording, so don't bother
                        # sending events
                        if DEBUG: print >> sys.stderr, "EventStatusReporter: received -zero- from the HTTP server. Reporting disabled"
                        self._thread_lock.acquire()
                        self._enable_reporting = False
                        self._thread_lock.release()

                        # close thread
                        return

                    else:
                        # I choose not to reset the retry_delay because
                        # swarmplayer sessions tend to be short. And the
                        # if there are connection failures I want as few
                        # retries as possible
                        if DEBUG: print >> sys.stderr, "EventStatusReporter: report successfull. Next report in", result, "seconds"
                        timeout = result
                else:
                    self._thread_lock.acquire()
                    self._enable_reporting = False
                    self._thread_lock.release()

                    # close thread
                    return

    def add_event(self, key, event):
        assert type(key) is str
        assert type(event) is str
        if self._enable_reporting:

            # prepend the prefix to the key
            key = self._prefix + key
            
            self._thread_lock.acquire()
            try:
                # check self._enable_reporting again since this is
                # variable is shared between threads
                if not self._enable_reporting:
                    return True
                if DEBUG: print >> sys.stderr, "EventStatusReporter: add_event", `key`, `event`
                self._event.append({"key":key, "timestamp":time(), "event":event})
            finally:
                self._thread_lock.release()

    def flush(self):
        """
        Flush the statistics. Forces a report to be send immediately
        (regardless of what the reporting frequency that the http
        server told us)
        """
        if self._enable_reporting:
            self._thread_flush.set()
