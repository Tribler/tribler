# Written by Bram Cohen
# see LICENSE.txt for license information

from cStringIO import StringIO
from urllib import quote
from threading import Event

try:
    True
except:
    True = 1
    False = 0

class DownloaderFeedback:
    def __init__(self, choker, httpdl, add_task, upfunc, downfunc,
            ratemeasure, leftfunc, file_length, finflag, sp, statistics,
            statusfunc = None, interval = None):
        self.choker = choker
        self.httpdl = httpdl
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
        for c in cs:
            a = {}
            a['id'] = c.get_readable_id()
            a['ip'] = c.get_ip()
            a['optimistic'] = (c is self.choker.connections[0])
            if c.is_locally_initiated():
                a['direction'] = 'L'
            else:
                a['direction'] = 'R'
            u = c.get_upload()
            a['uprate'] = int(u.measure.get_rate())
            a['uinterested'] = u.is_interested()
            a['uchoked'] = u.is_choked()
            d = c.get_download()
            a['downrate'] = int(d.measure.get_rate())
            a['dinterested'] = d.is_interested()
            a['dchoked'] = d.is_choked()
            a['snubbed'] = d.is_snubbed()
            a['utotal'] = d.connection.upload.measure.get_total()
            a['dtotal'] = d.connection.download.measure.get_total()
            if len(d.connection.download.have) > 0:
                a['completed'] = float(len(d.connection.download.have)-d.connection.download.have.numfalse)/float(len(d.connection.download.have))
            else:
                a['completed'] = 1.0
            a['speed'] = d.connection.download.peermeasure.get_rate()

            l.append(a)                                               

        for dl in self.httpdl.get_downloads():
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


    def gather(self, displayfunc = None):
        s = {'stats': self.statistics.update()}
        if self.sp.isSet():
            s['spew'] = self.spews()
        else:
            s['spew'] = None
        s['up'] = self.upfunc()
        if self.finflag.isSet():
            s['done'] = self.file_length
            return s
        s['down'] = self.downfunc()
        obtained, desired = self.leftfunc()
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
