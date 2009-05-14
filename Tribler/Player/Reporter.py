# Written by Jan David Mol
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
VIDEOPLAYBACK_REPORT = True
DEBUG = False

class Reporter:
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
            "peerid":     `ds.get_peerid()`,
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
    Periodically report information to a central server
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

        # the info table. one entry for each started playback
        self._info = {}

        # the event table. one entry for each VOD event
        self._event = []

        # enable or disable reporting to the http server
        self._enable_reporting = True

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
        
        # there are several urls available where reports can be
        # send. one should be picked randomly each time.

        # when a report is successfull it will stay with the same
        # reporter. when a report is unsuccessfull (could not connect)
        # it will cycle through reporters.
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
                if not (self._info or self._event):
                    # we have nothing to report... sleep
                    timeout = retry_delay
                    info = None
                    event = None
                else:
                    # copy between threads while locked
                    info = self._info
                    event = self._event

                    self._info = {}
                    self._event = []
                    self._last_report = time()

            finally:
                self._thread_lock.release()

            # add new report
            if info or event:
                if len(event) < 10:
                    # uncompressed
                    report = {"version":"1",
                              "info":info,
                              "event":event}
                else:
                    # compress
                    report = {"version":"2",
                              "info":urllib.quote(zlib.compress(repr(info), 9)),
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
                    # sending info
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

    def create_entry(self, key, piece_size=0, num_pieces=0, bitrate=0, nat="", unique=False):
        """
        Create an entry that can be updated using subsequent
        set_... calls.

        When UNIQUE we assume that KEY does not yet exist in the
        database. Otherwise a check is made.
        """
        assert type(key) is str, type(key)
        assert type(piece_size) is int, type(piece_size)
        assert type(num_pieces) is int, type(num_pieces)
        assert type(bitrate) in (int, float), type(bitrate)
        assert type(nat) is str, type(nat)
        self._thread_lock.acquire()
        try:
            if not self._enable_reporting:
                return True
            if DEBUG: print >>sys.stderr, "VideoPlaybackReporter create_entry", key
            if unique or not key in self._info:
                self._info[key] = {"timestamp":time(), "piece_size":piece_size, "num_pieces":num_pieces, "bitrate":bitrate, "nat":nat}
                return True
            else:
                return False
        finally:
            self._thread_lock.release()
            
    def set_piecesize(self, key, piece_size):
        assert type(key) is str
        assert type(piece_size) is int
        self._thread_lock.acquire()
        try:
            if not self._enable_reporting:
                return True
            if not key in self._info:
                self._info[key] = {}
            if DEBUG: print >>sys.stderr, "VideoPlaybackReporter set_piecesize", key, piece_size
            self._info[key]["piece_size"] = piece_size
        finally:
            self._thread_lock.release()

    def set_num_pieces(self, key, num_pieces):
        assert type(key) is str
        assert type(num_pieces) is int
        self._thread_lock.acquire()
        try:
            if not self._enable_reporting:
                return True
            if not key in self._info:
                self._info[key] = {}
            if DEBUG: print >>sys.stderr, "VideoPlaybackReporter set_num_pieces", key, num_pieces
            self._info[key]["num_pieces"] = num_pieces
        finally:
            self._thread_lock.release()

    def set_bitrate(self, key, bitrate):
        assert type(key) is str
        assert type(bitrate) in (int, float)
        self._thread_lock.acquire()
        try:
            if not self._enable_reporting:
                return True
            if not key in self._info:
                self._info[key] = {}
            if DEBUG: print >>sys.stderr, "VideoPlaybackReporter set_bitrate", key, bitrate
            self._info[key]["bitrate"] = bitrate
        finally:
            self._thread_lock.release()

    def set_nat(self, key, nat):
        assert type(key) is str
        assert type(nat) is str
        self._thread_lock.acquire()
        try:
            if not self._enable_reporting:
                return True
            if not key in self._info:
                self._info[key] = {}
            if DEBUG: print >>sys.stderr, "VideoPlaybackReporter set_nat", key, nat
            self._info[key]["nat"] = nat
        finally:
            self._thread_lock.release()

    def add_event(self, key, event, origin):
        assert type(key) is str
        assert type(event) is str
        assert type(origin) is str
        self._thread_lock.acquire()
        try:
            if not self._enable_reporting:
                return True
            if DEBUG: print >>sys.stderr, "VideoPlaybackReporter: add_event", key, event, origin
            self._event.append({"key":key, "timestamp":time(), "event":event, "origin":origin})
        finally:
            self._thread_lock.release()

    def flush(self):
        """
        Flush the statistics. Forces a report to be send immediately
        (regardless of what the reporting frequency that the http
        server told us)
        """
        self._thread_flush.set()

class VideoPlaybackInfoReporter(VideoPlaybackReporter):
    """
    Interface to add info from VOD statistics

    Manages the virtual playback_info table. This table contains one
    entry with info for each playback. This info contains things like:
    piecesize, nat/firewall status, etc.

    The interface of this class should match that of
    VideoPlaybackInfoDBHandler in
    Tribler.Core.CacheDB.SqliteVideoPlaybackStatsCacheDB which is used
    to report the same information through HTTP callbacks when there
    is no overlay network
    """
    pass

class VideoPlaybackEventReporter(VideoPlaybackReporter):
    """
    Interface to add and retrieve events from the database.

    Manages the virtual playback_event table. This table may contain
    several entries for events that occur during playback such as when
    it was started and when it was paused.

    The interface of this class should match that of
    VideoPlaybackEventDBHandler in
    Tribler.Core.CacheDB.SqliteVideoPlaybackStatsCacheDB which is used
    to report the same information through HTTP callbacks when there
    is no overlay network
    """
    pass 
