# Written by Bram Cohen
# see LICENSE.txt for license information

from threading import Event

try:
    True
except:
    True = 1
    False = 0

class DownloaderFeedback:
    def __init__(self, choker, ghttpdl, hhttpdl, add_task, upfunc, downfunc,
            ratemeasure, leftfunc, file_length, finflag, sp, statistics,
            statusfunc = None, interval = None, infohash = None, voddownload=None):
        self.choker = choker
        self.ghttpdl = ghttpdl
        self.hhttpdl = hhttpdl
        self.add_task = add_task
        self.upfunc = upfunc
        self.downfunc = downfunc
        self.ratemeasure = ratemeasure
        self.leftfunc = leftfunc
        self.file_length = file_length
        self.finflag = finflag
        self.sp = sp
        self.statistics = statistics
        self.lastids = []
        self.spewdata = None
        self.infohash = infohash
        self.voddownload = voddownload
        self.doneprocessing = Event()
        self.doneprocessing.set()
        if statusfunc:
            self.autodisplay(statusfunc, interval)
        

    def _rotate(self):
        cs = self.choker.connections
        for id in self.lastids:
            for i in xrange(len(cs)):
                if cs[i].get_id() == id:
                    return cs[i:] + cs[:i]
        return cs

    def spews(self):
        l = []
        cs = self._rotate()
        self.lastids = [c.get_id() for c in cs]
        for c in cs:    # c: Connecter.Connection
            a = {}
            a['id'] = c.get_readable_id()
            a['extended_version'] = c.extended_version or ''
            a['ip'] = c.get_ip()
            if c.is_locally_initiated():
                a['port'] = c.get_port()
            else:
                a['port'] = 0
            try:
                a['optimistic'] = (c is self.choker.connections[0])
            except:
                a['optimistic'] = False
            if c.is_locally_initiated():
                a['direction'] = 'L'
            else:
                a['direction'] = 'R'
            
            a['uflushed'] = not c.backlogged()
            
            ##a['unauth_permid'] = c.get_unauth_permid()
            u = c.get_upload()
            a['uprate'] = int(u.measure.get_rate())
            a['uinterested'] = u.is_interested()
            a['uchoked'] = u.is_choked()
            a['uhasqueries'] = u.has_queries()
            
            d = c.get_download()
            a['downrate'] = int(d.measure.get_rate())
            a['dinterested'] = d.is_interested()
            a['dchoked'] = d.is_choked()
            a['snubbed'] = d.is_snubbed()
            a['utotal'] = d.connection.upload.measure.get_total()
            a['dtotal'] = d.connection.download.measure.get_total()
            if d.connection.download.have:
                a['completed'] = float(len(d.connection.download.have)-d.connection.download.have.numfalse)/float(len(d.connection.download.have))
            else:
                a['completed'] = 1.0
            a['have'] = d.connection.download.have
            # The total download speed of the peer as measured from its
            # HAVE messages.
            a['speed'] = d.connection.download.peermeasure.get_rate()
            a['g2g'] = c.use_g2g
            a['g2g_score'] = c.g2g_score()

            # RePEX: include number of pex messages in the stats
            a['pex_received'] = c.pex_received 
            
            l.append(a)                                               

        for dl in self.ghttpdl.get_downloads():
            if dl.goodseed:
                a = {}
                a['id'] = 'url list'
                a['ip'] = dl.baseurl
                a['optimistic'] = False
                a['direction'] = 'L'
                a['uprate'] = 0
                a['uinterested'] = False
                a['uchoked'] = False
                a['downrate'] = int(dl.measure.get_rate())
                a['dinterested'] = True
                a['dchoked'] = not dl.active
                a['snubbed'] = not dl.active
                a['utotal'] = None
                a['dtotal'] = dl.measure.get_total()
                a['completed'] = 1.0
                a['speed'] = None

                l.append(a)
        for dl in self.hhttpdl.get_downloads():
            if dl.goodseed:
                a = {}
                a['id'] = 'http seed'
                a['ip'] = dl.baseurl
                a['optimistic'] = False
                a['direction'] = 'L'
                a['uprate'] = 0
                a['uinterested'] = False
                a['uchoked'] = False
                a['downrate'] = int(dl.measure.get_rate())
                a['dinterested'] = True
                a['dchoked'] = not dl.active
                a['snubbed'] = not dl.active
                a['utotal'] = None
                a['dtotal'] = dl.measure.get_total()
                a['completed'] = 1.0
                a['speed'] = None

                l.append(a)
        return l


    def gather(self, displayfunc = None, getpeerlist=False):
        """ Called by SingleDownload to obtain download statistics to become the
        DownloadStates for each Download """
        s = {'stats': self.statistics.update()}
        if getpeerlist:
            s['spew'] = self.spews()
        else:
            s['spew'] = None
        s['up'] = self.upfunc()
        if self.finflag.isSet():
            s['done'] = self.file_length
            s['down'] = 0.0
            s['frac'] = 1.0
            s['wanted'] = 0
            s['time'] = 0
            s['vod'] = False
            s['vod_prebuf_frac'] = 1.0
            s['vod_playable'] = True
            s['vod_playable_after'] = 0.0
            s['vod_stats'] = {'harry':1}
            if self.voddownload is not None:
                #s['vod'] = True
                s['vod_stats'] = self.voddownload.get_stats()

#            if self.voddownload:
#                s['vod_duration'] = self.voddownload.get_duration()
#            else:
#                s['vod_duration'] = None
            return s
        s['down'] = self.downfunc()
        obtained, desired, have = self.leftfunc()
        s['done'] = obtained
        s['wanted'] = desired
        if desired > 0:
            s['frac'] = float(obtained)/desired
        else:
            s['frac'] = 1.0
        if desired == obtained:
            s['time'] = 0
        else:
            s['time'] = self.ratemeasure.get_time_left(desired-obtained)
            
        if self.voddownload is not None:
            s['vod_prebuf_frac'] = self.voddownload.get_prebuffering_progress()
            s['vod_playable'] = self.voddownload.is_playable()
            s['vod_playable_after'] = self.voddownload.get_playable_after()
            s['vod'] = True
            s['vod_stats'] = self.voddownload.get_stats()
#            s['vod_duration'] = self.voddownload.get_duration()
        else:
            s['vod_prebuf_frac'] = 0.0
            s['vod_playable'] = False
            s['vod_playable_after'] = float(2 ** 31)
            s['vod'] = False
            s['vod_stats'] = {}
#            s['vod_duration'] = None
        return s        


    def display(self, displayfunc):
        if not self.doneprocessing.isSet():
            return
        self.doneprocessing.clear()
        stats = self.gather()
        if self.finflag.isSet():
            displayfunc(dpflag = self.doneprocessing, 
                upRate = stats['up'], 
                statistics = stats['stats'], spew = stats['spew'])
        elif stats['time'] is not None:
            displayfunc(dpflag = self.doneprocessing, 
                fractionDone = stats['frac'], sizeDone = stats['done'], 
                downRate = stats['down'], upRate = stats['up'], 
                statistics = stats['stats'], spew = stats['spew'], 
                timeEst = stats['time'])
        else:
            displayfunc(dpflag = self.doneprocessing, 
                fractionDone = stats['frac'], sizeDone = stats['done'], 
                downRate = stats['down'], upRate = stats['up'], 
                statistics = stats['stats'], spew = stats['spew'])


    def autodisplay(self, displayfunc, interval):
        self.displayfunc = displayfunc
        self.interval = interval
        self._autodisplay()

    def _autodisplay(self):
        self.add_task(self._autodisplay, self.interval)
        self.display(self.displayfunc)
