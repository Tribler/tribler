# Written by Jan David Mol
# see LICENSE.txt for license information

# Collects statistics about a download/VOD session, and sends it
# home on a regular interval.

import sys,urllib,zlib
from time import time
from traceback import print_exc

PHONEHOME = True
DEBUG = True

class Reporter:
    def __init__( self ):
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

        self.last_report_ts = 0

        # send initial information
        s = ["epoch %.2f" % (self.epoch,)]
        self.phone_home( s )

    def phone_home( self, reports ):
        """ Report status to a centralised server. """

        #if DEBUG: print >>sys.stderr,"\nreport: ".join(reports)

        # do not actually send if reporting is disabled
        if not self.do_reporting or not PHONEHOME:
            return

        # add reports to buffer
        self.buffered_reports.extend( reports )

        # only process at regular intervals
        now = time()
        if now - self.last_report_ts < self.report_interval:
            return
        self.last_report_ts = now

        # send complete buffer
        s = "\n".join(self.buffered_reports)
        self.buffered_reports = []

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
            self.do_reporting = False
        except ValueError, e:
            # page did not obtain an integer
            self.do_reporting = False
        except:
            # any other error
            print_exc(file=sys.stderr)
            self.do_reporting = False

    def report_stat( self, ds ):
        chokestr = lambda b: ["c","C"][int(bool(b))]
        intereststr = lambda b: ["i","I"][int(bool(b))]
        optstr = lambda b: ["o","O"][int(bool(b))]
        protstr = lambda b: ["bt","g2g"][int(bool(b))]

        now = time()
        arrivals = []
        departures = []
        s = ["timestamp %.2f %.2f%% swarm %s id %s" % (now-self.epoch,100.0*ds.get_progress(),`ds.get_download().get_def().get_infohash()`,ds.get_peerid(),)]

        v = ds.get_vod_stats()
        vi = ds.get_videoinfo()
        if v:
            s.append( "vod pos=%d played=%d lost=%d late=%d prebuf=%.2f stall=%.2f pp=%d,%d,%d" % (v["pos"],v["played"],v["dropped"],v["late"],v["prebuf"],v["stall"],v["pp"]["high"],v["pp"]["mid"],v["pp"]["low"]) )
        if vi:
            s.append( "vod2 live=%s bitrate=%s inpath=%s" % (vi["live"],vi["bitrate"],vi["inpath"]) )

        for p in ds.get_peerlist():
            id = p["id"]
            if id not in self.peerinfo:
                # a peer we haven't seen before
                nr = len(self.peernr)+1
                self.peernr[id] = nr
                self.peerinfo[id] = "newpeer %d %s %s:%s:%s %s" % (nr,protstr(p["g2g"]),p["direction"],p["ip"],p["port"],id)
                s.append(self.peerinfo[id])

                # newpeer implies an arrival
                self.connected[nr] = now
            else:
                nr = self.peernr[id]

                if nr not in self.connected:
                    # a peer we've seen before has arrived again
                    arrivals.append(str(nr))
                self.connected[nr] = now

            s.append("status %s %.2f%% g2g %s,%s up: %s%s%s %s %.2f down: %s%s %s %.2f" % (
                nr,
                p["completed"]*100,p["g2g_score"][0],p["g2g_score"][1],
                chokestr(p["uchoked"]),intereststr(p["uinterested"]),optstr(p["optimistic"]),p["utotal"],p["uprate"]/1024.0,
                chokestr(p["dchoked"]),intereststr(p["dinterested"]),p["dtotal"],p["downrate"]/1024.0))

        # collect departed peers and remove them from self.connected
        for k,v in self.connected.items():
            if v < now:
                departures.append(str(k))
                del self.connected[k]

        # report arrivals and departures
        if arrivals:
            s.append("arrive %s" % (" ".join(arrivals),) )
        if departures:
            s.append("depart %s" % (" ".join(departures),) )

        self.phone_home( s )


