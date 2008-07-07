# Written by Jan David Mol
# see LICENSE.txt for license information

# Collects statistics about a download/VOD session, and sends it
# home on a regular interval.

import sys,urllib,zlib,pickle
from time import time
from traceback import print_exc
from Tribler.Core.Session import Session

PHONEHOME = True
DEBUG = True

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
            sock = urllib.urlopen("http://swarmplayer.mininova.org/reporting/report.cgi",data)
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
        if DEBUG: print >>sys.stderr,"\nreport: succes. reported %s bytes, will report again in %s seconds" % (len(data),self.do_reporting)

    def report_stat( self, ds ):
        chokestr = lambda b: ["c","C"][int(bool(b))]
        intereststr = lambda b: ["i","I"][int(bool(b))]
        optstr = lambda b: ["o","O"][int(bool(b))]
        protstr = lambda b: ["bt","g2g"][int(bool(b))]
            
        now = time()
        v = ds.get_vod_stats() or { "played": 0, "stall": 0, "late": 0, "dropped": 0, "prebuf": -1 }
        vi = ds.get_videoinfo() or { "live": False, "inpath": "(none)" }
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
        }

        self.phone_home( stats )
