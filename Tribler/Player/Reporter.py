# Written by Jan David Mol, Boudewijn Schoon
# see LICENSE.txt for license information

# Collects statistics about a download/VOD session, and sends it
# home on a regular interval.

import sys,urllib,zlib,pickle
import thread
import threading
from random import shuffle
from time import time
from traceback import print_exc
from Tribler.Core.Session import Session

PHONEHOME = False
USE_LIVING_LAB_REPORTING = False

DEBUG = False

if USE_LIVING_LAB_REPORTING:
    from Tribler.Player.Status.Status import get_status_holder
    from Tribler.Player.Status.LivingLabReporter import LivingLabOnChangeReporter


class Reporter:
    """ Old Reporter class used for July 2008 trial. See below for new """
    
    def __init__( self, sconfig ):
        self.sconfig = sconfig

        # time of initialisation
        self.epoch = time()

        # mapping from peer ids to (shorter) numbers
        self.peernr = {}

        # remember static peer information, such as IP
        # self.peerinfo[id] = info string
        self.peerinfo = {}

        # remember which peers we were connected to in the last report
        # self.connected[id] = timestamp when last seen
        self.connected = {}

        # collected reports
        self.buffered_reports = []

        # whether to phone home to send collected data
        self.do_reporting = True

        # send data at this interval (seconds)
        self.report_interval = 30

        # send first report immediately
        self.last_report_ts = 0

        # record when we started (used as a session id)
        self.epoch = time()

    def phone_home( self, report ):
        """ Report status to a centralised server. """

        #if DEBUG: print >>sys.stderr,"\nreport: ".join(reports)

        # do not actually send if reporting is disabled
        if not self.do_reporting or not PHONEHOME:
            return

        # add reports to buffer
        self.buffered_reports.append( report )

        # only process at regular intervals
        now = time()
        if now - self.last_report_ts < self.report_interval:
            return
        self.last_report_ts = now

        # send complete buffer
        s = pickle.dumps( self.buffered_reports )
        self.buffered_reports = []

        if DEBUG: print >>sys.stderr,"\nreport: phoning home."
        try:
            data = zlib.compress( s, 9 ).encode("base64")
            sock = urllib.urlopen("http://swpreporter.tribler.org/reporting/report.cgi",data)
            result = sock.read()
            sock.close()

            result = int(result)

            if result == 0:
                # remote server is not recording, so don't bother sending info
                self.do_reporting = False
            else:
                self.report_interval = result
        except IOError, e:
            # error contacting server
            print_exc(file=sys.stderr)
            self.do_reporting = False
        except ValueError, e:
            # page did not obtain an integer
            print >>sys.stderr,"report: got %s" % (result,)
            print_exc(file=sys.stderr)
            self.do_reporting = False
        except:
            # any other error
            print_exc(file=sys.stderr)
            self.do_reporting = False
        if DEBUG: print >>sys.stderr,"\nreport: succes. reported %s bytes, will report again (%s) in %s seconds" % (len(data),self.do_reporting,self.report_interval)

    def report_stat( self, ds ):
        chokestr = lambda b: ["c","C"][int(bool(b))]
        intereststr = lambda b: ["i","I"][int(bool(b))]
        optstr = lambda b: ["o","O"][int(bool(b))]
        protstr = lambda b: ["bt","g2g"][int(bool(b))]
            
        now = time()
        v = ds.get_vod_stats() or { "played": 0, "stall": 0, "late": 0, "dropped": 0, "prebuf": -1, "pieces": {} }
        # Arno, 2009-09-09: method removed, was unclean
        vi = ds.get_videoinfo() or { "live": False, "inpath": "(none)", "status": None }
        vs = vi["status"]

        scfg = self.sconfig

        down_total, down_rate, up_total, up_rate = 0, 0.0, 0, 0.0
        peerinfo = {}

        for p in ds.get_peerlist():
            down_total += p["dtotal"]/1024
            down_rate  += p["downrate"]/1024.0
            up_total   += p["utotal"]/1024
            up_rate    += p["uprate"]/1024.0

            id = p["id"]
            peerinfo[id] = {
                "g2g": protstr(p["g2g"]),
                "addr": "%s:%s:%s" % (p["ip"],p["port"],p["direction"]),
                "id": id,
                "g2g_score": "%s,%s" % (p["g2g_score"][0],p["g2g_score"][1]),
                "down_str": "%s%s" % (chokestr(p["dchoked"]),intereststr(p["dinterested"])),
                "down_total": p["dtotal"]/1024,
                "down_rate": p["downrate"]/1024.0,
                "up_str": "%s%s%s" % (chokestr(p["uchoked"]),intereststr(p["uinterested"]),optstr(p["optimistic"])),
                "up_total": p["utotal"]/1024,
                "up_rate": p["uprate"]/1024.0,
            }

        if vs:
            valid_range = vs.download_range()
        else:
            valid_range = ""

        stats = {
            "timestamp":  time(),
            "epoch":      self.epoch,
            "listenport": scfg.get_listen_port(),
            "infohash":   `ds.get_download().get_def().get_infohash()`,
            "filename":   vi["inpath"],
            "peerid":     `ds.get_peerid()`,  # Arno, 2009-09-09: method removed, should be Download method
            "live":       vi["live"],
            "progress":   100.00*ds.get_progress(),
            "down_total": down_total,
            "down_rate":  down_rate,
            "up_total":   up_total,
            "up_rate":    up_rate,
            "p_played":   v["played"],
            "t_stall":    v["stall"],
            "p_late":     v["late"],
            "p_dropped":  v["dropped"],
            "t_prebuf":   v["prebuf"],
            "peers":      peerinfo.values(),
            "pieces":     v["pieces"],
            "validrange": valid_range,
        }

        self.phone_home( stats )

class VideoPlaybackReporter:
    """
    Periodically report information to a central server (either TUD or ULANC)
    """
    __single = None    # used for multi-threaded singletons pattern
    lock = thread.allocate_lock()

    @classmethod
    def get_instance(cls, *args, **kw):
        # Singleton pattern with double-checking to ensure that it can only create one object
        if VideoPlaybackReporter.__single is None:
            VideoPlaybackReporter.lock.acquire()   
            try:
                if VideoPlaybackReporter.__single is None:
                    VideoPlaybackReporter.__single = cls(*args, **kw)
            finally:
                VideoPlaybackReporter.lock.release()
        return VideoPlaybackReporter.__single
    
    def __init__(self):
        if VideoPlaybackReporter.__single is not None:
            raise RuntimeError, "VideoPlaybackReporter is singleton"

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
                    self._last_report = time()
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

                if DEBUG: print >>sys.stderr, "VideoPlaybackReporter: attempting to report,", len(reports[0]), "bytes to", reporter[2]
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
                    report_urls.sort(lambda x,y:cmp(x[0], y[0]))
                    continue

                if result.isdigit():
                    result = int(result)
                    if result == 0:
                        # remote server is not recording, so don't bother
                        # sending events
                        if DEBUG: print >>sys.stderr, "VideoPlaybackReporter: received -zero- from the HTTP server. Reporting disabled"
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
                        if DEBUG: print >>sys.stderr, "VideoPlaybackReporter: report successfull. Next report in", result, "seconds"
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
            self._thread_lock.acquire()
            try:
                # check self._enable_reporting again since this is
                # variable is shared between threads
                if not self._enable_reporting:
                    return True
                if DEBUG: print >>sys.stderr, "VideoPlaybackReporter: add_event", key, event
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
