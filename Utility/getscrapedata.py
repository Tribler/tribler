import re
import binascii
import sys
import wx

from threading import Thread,Event

# The ScrapeThread calls ABCTorrent to update the info. As that updates
# the GUI, those updates must be done by the MainThread and not this
# scraping thread itself.

wxEVT_INVOKE = wx.NewEventType()

def EVT_INVOKE(win, func):
    win.Connect(-1, -1, wxEVT_INVOKE, func)
    
def DELEVT_INVOKE(win):
    win.Disconnect(-1, -1, wxEVT_INVOKE)

class InvokeEvent(wx.PyEvent):
    def __init__(self, func, args, kwargs):
        wx.PyEvent.__init__(self)
        self.SetEventType(wxEVT_INVOKE)
        self.func = func
        self.args = args
        self.kwargs = kwargs


################################################################
#
# Class: ScrapeThread
#
# Retrieves scrape data from a tracker.
#
################################################################
class ScrapeThread(Thread,wx.EvtHandler):

    def __init__(self, utility, torrent, manualscrape = False):
        Thread.__init__(self, None, None, None)
        wx.EvtHandler.__init__(self)

        self.torrent = torrent
        self.utility = utility
        self.manualscrape = manualscrape
        self.status = self.utility.lang.get('scraping')
        self.currentseed = "?"
        self.currentpeer = "?"

        self.setName( "Scrape"+self.getName() )
        self.doneflag = Event()
        EVT_INVOKE(self, self.onInvoke)

    def run(self):
        self.GetScrapeData()

    def GetScrapeData(self):
        print "scraping..."
        
        # connect scrape at tracker and get data
        # save at self.currentpeer, self.currentseed
        # if error put '?'

        # The thread itself will update the list for its scraping infos
        self.updateTorrent()
        
        metainfo = self.torrent.metainfo

        if metainfo is None:
            self.status = self.utility.lang.get('cantreadmetainfo')
            self.updateTorrent()
            return

        print "got metainfo"
        
        announce = None    
        if 'announce' in metainfo:
            announce = metainfo['announce']
        elif 'announce-list' in metainfo:
            announce_list = metainfo['announce-list']
            announce = announce_list[0][0]
        
        if announce is None:
            self.status = self.utility.lang.get('noannouncetrackerinmeta')
            self.updateTorrent()
            return
        
        print "got announce"
            
#        sys.stdout.write('Announce URL: ' + announce + '\n');

        # Does tracker support scraping?
        ix = announce.rfind('/')
        if ((ix == -1) or (announce.rfind("/announce") != ix)):
            # Tracker doesn't support scraping
            self.status = self.utility.lang.get('trackernoscrape')
            self.updateTorrent()
            return

        p = re.compile('(.*/)[^/]+')
        surl = p.sub(r'\1', announce)
        #sys.stdout.write('sURL1: ' + surl + '\n')
        #Fix this to comply with scrape standards.
        ix = announce.rindex('/')
        #tmp = 'ix: '.join(ix)
        #sys.stdout.write('ix: ' + str(ix) + '\n')
        if (ix + 9) > len(announce):
            ix2 = len(announce)
        else:
            ix2 = ix + 9
        #sys.stdout.write('ix: ' + announce[(ix + 1):(ix2)] + '\n')
        if announce[(ix + 1):(ix2)].endswith("announce", 0):
            #sys.stdout.write('!!!VALID SCRAPE URL!!!' + '\n')
            #sys.stdout.write('sURLTrue: ' + surl + 'scrape' + announce[(ix2):] + '\n');
        # fix for some private trackers (change ? to &):
            if '?' in announce[ix2:]:
                infohashprefix = '&'
            else:
                infohashprefix = '?'
            surl = surl + 'scrape' + announce[ix2:] + infohashprefix + 'info_hash='
        #end new Scrape URL Code
        info_hash_hex = self.torrent.infohash
        hashlen = len(info_hash_hex)
        for i in range(0, hashlen):
            if (i % 2 == 0):
                surl = surl + "%"
            surl = surl + info_hash_hex[i]
            
        print "tring to scrape"
            
        # connect scrape URL
        scrapedata = self.utility.getMetainfo(surl, style = "url")

        if scrapedata is None or not 'files' in scrapedata:
            self.status = self.utility.lang.get('cantgetdatafromtracker')                        
        else:
            scrapedata = scrapedata['files']
            for i in scrapedata.keys():
                if binascii.b2a_hex(i) == info_hash_hex:
                    self.currentpeer = str(scrapedata[i]['incomplete'])
                    self.currentseed = str(scrapedata[i]['complete'])
                    self.status = self.utility.lang.get('scrapingdone')
        
        self.updateTorrent()
        
        print "done scraping"


    def onInvoke(self, event):
        if ((self.doneflag is not None)
            and (not self.doneflag.isSet())):
            event.func(*event.args, **event.kwargs)

    def invokeLater(self, func, args = [], kwargs = {}):
        if ((self.doneflag is not None)
            and (not self.doneflag.isSet())):
            wx.PostEvent(self, InvokeEvent(func, args, kwargs))

    def updateTorrent(self):
        self.invokeLater(self.OnUpdateTorrent, [])


    def OnUpdateTorrent(self):
        if not self.manualscrape:
            # Don't update status information if doing an automatic scrape
            status = ""
        else:
            status = self.status
        
        # The thread itself will update the list for its scraping infos
        self.torrent.updateScrapeData(self.currentpeer, self.currentseed, status)