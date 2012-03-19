# Written by John Hoffman
# Updated by George Milescu
# see LICENSE.txt for license information

# Patched by Diego Andres Rabaioli.
# This is the HTTPDownloader class that implements the GetRight
# style WebSeeding technique. Compared to the John Hoffman's style it
# doesn't require any web server support.However the biggest gap (see
# http://www.bittorrent.org/beps/bep_0019.html) is not taken into
# account when requesting pieces.

import sys
from random import randint
from urlparse import urlparse
from httplib import HTTPConnection
import urllib
from threading import Thread,currentThread,Lock
from traceback import print_exc, print_stack 

from Tribler.Core.BitTornado.__init__ import product_name,version_short
from Tribler.Core.BitTornado.CurrentRateMeasure import Measure
from Tribler.Core.Utilities.timeouturlopen import find_proxy

DEBUG = False

EXPIRE_TIME = 60 * 60

VERSION = product_name+'/'+version_short

class haveComplete:
    def complete(self):
        return True
    def __getitem__(self, x):
        return True
haveall = haveComplete()

class SingleDownload():

    def __init__(self, downloader, url, video_support_policy):
        self.downloader = downloader
        self.baseurl = url
        
        try:
            (self.scheme, self.netloc, path, pars, query, fragment) = urlparse(url)
        except:
            self.downloader.errorfunc('cannot parse http seed address: '+url)
            return
        if self.scheme != 'http':
            self.downloader.errorfunc('http seed url not http: '+url)
            return

        # Arno, 2010-03-08: Make proxy aware
        self.proxyhost = find_proxy(url)
        try:
            if self.proxyhost is None:
                self.connection = HTTPConnection(self.netloc)
            else:
                self.connection = HTTPConnection(self.proxyhost)
        except:
            self.downloader.errorfunc('cannot connect to http seed: '+url)
            return
        
        self.seedurl = path
        self.measure = Measure(downloader.max_rate_period)
        self.index = None
        self.piece_size = self.downloader.storage._piecelen( 0 )
        self.total_len = self.downloader.storage.total_length
        self.url = ''
        self.requests = []
        self.request_size = 0
        self.endflag = False
        self.error = None
        self.retry_period = 30
        self._retry_period = None
        self.errorcount = 0
        self.goodseed = False
        self.active = False
        self.cancelled = False
        # HTTP Video Support
        self.request_lock = Lock()
        self.video_support_policy     = video_support_policy  # Niels: 08-03-2012 using svc_video or play_video in download_bt1
        self.video_support_enabled    = False # Don't start immediately with support
        self.video_support_speed      = 0.0   # Start with the faster rescheduling speed
        self.video_support_slow_start = False # If enabled delay the first request (give chance to peers to give bandwidth)
        
        # Arno, 2010-04-07: Wait 1 second before using HTTP seed. TODO good policy
        # If Video Support policy is not eneabled then use Http seed normaly
        if not self.video_support_policy:
            self.resched(1)
            

    def resched(self, len = None):
        if self.video_support_policy:
            if ( not self.video_support_enabled ) or self.video_support_slow_start:
                return
        if len is None:
            len = self.retry_period
        if self.errorcount > 3:
            len = min(1.0,len) * (self.errorcount - 2)

        # Arno, 2010-04-07: If immediately, don't go via queue. Actual work is
        # done by other thread, so no worries of hogging NetworkThread. 
        if len > 0: 
            self.downloader.rawserver.add_task(self.download, len)
        else:
            self.download() 

    def _want(self, index):
        if self.endflag:
            return self.downloader.storage.do_I_have_requests(index)
        else:
            return self.downloader.storage.is_unstarted(index)

    def download(self):
        from Tribler.Core.Session import Session
        session = Session.get_instance()
        session.uch.perform_usercallback(self._download)

    def _download(self):
        self.request_lock.acquire()
        if DEBUG:
            print "http-sdownload: download()"

        self.cancelled = False
        if self.downloader.picker.am_I_complete():
            self.downloader.downloads.remove(self)
            return
        self.index = self.downloader.picker.next(haveall, self._want, self)

        if self.index is None:
            self.resched(0.01)
            return

        if ( self.index is None and not self.endflag
                     and not self.downloader.peerdownloader.has_downloaders() ):
            self.endflag = True
            self.index = self.downloader.picker.next(haveall, self._want, self)
        if self.index is None:
            self.endflag = True
            self.resched()
        else:
            self.url = self.seedurl
            start = self.piece_size * self.index
            end   = start + self.downloader.storage._piecelen( self.index ) - 1
            self.request_range = '%d-%d' % ( start, end )
            self._get_requests()
            # Just overwrite other blocks and don't ask for ranges.
            self._request()
            # Diego : 2010-05-19 : Moving thread creation on _download and not on
            # _request anymore. One Lock handles sync problems between threads performing
            # new requests before the previous response is read.
            """
            # Arno, 2010-04-07: Use threads from pool to Download, more efficient
            # than creating a new one for every piece.
            from Tribler.Core.Session import Session
            session = Session.get_instance()
            session.uch.perform_usercallback(self._request)
            # Diego
            rq = Thread(target = self._request)
            rq.setName( "GetRightHTTPDownloader"+rq.getName() )
            rq.setDaemon(True)
            rq.start()
            """
            self.active = True

    def _request(self):
        import encodings.ascii
        import encodings.punycode
        import encodings.idna
        
        self.error = None
        self.received_data = None
        try:
            #print >>sys.stderr, 'HTTP piece ', self.index
            if self.proxyhost is None:
                realurl = self.url
            else: 
                realurl = self.scheme+'://'+self.netloc+self.url

            self.connection.request( 'GET', realurl, None,
                                {'Host': self.netloc, 'User-Agent': VERSION, 'Range' : 'bytes=%s' % self.request_range } )

            r = self.connection.getresponse()
            self.connection_status = r.status
            self.received_data = r.read()
            
        except Exception, e:
            print_exc()
            
            self.error = 'error accessing http seed: '+str(e)
            try:
                self.connection.close()
            except:
                pass
            try:
                self.connection = HTTPConnection(self.netloc)
            except:
                self.connection = None  # will cause an exception and retry next cycle
        self.downloader.rawserver.add_task(self.request_finished)

    def request_finished(self):
        self.active = False
        if self.error is not None:
            if self.goodseed:
                self.downloader.errorfunc(self.error)
            self.errorcount += 1
        if self.received_data:
            self.errorcount = 0
            if not self._got_data():
                self.received_data = None
        if not self.received_data:
            self._release_requests()
            self.downloader.peerdownloader.piece_flunked(self.index)
        self.request_lock.release()
        if self._retry_period is not None:
            self.resched(self._retry_period)
            self._retry_period = None
            return
        self.resched()

    def _got_data(self):
        if self.connection_status == 503:   # seed is busy
            try:
                self.retry_period = max(int(self.received_data), 5)
            except:
                pass
            return False
        
        if self.connection_status != 200 and self.connection_status != 206: # 206 = partial download OK
            self.errorcount += 1
            return False
        # Arno,  2010-04-07: retry_period set to 0 for faster DL speeds
        # Diego, 2010-04-16: retry_period set depending on the level of support asked by the MovieOnDemandTransporter
        self._retry_period = self.video_support_speed

        if len(self.received_data) != self.request_size:
            if self.goodseed:
                self.downloader.errorfunc('corrupt data from http seed - redownloading')
            return False
        self.measure.update_rate(len(self.received_data))
        self.downloader.measurefunc(len(self.received_data))
        if self.cancelled:
            return False
        if not self._fulfill_requests():
            return False
        if not self.goodseed:
            self.goodseed = True
            self.downloader.seedsfound += 1
        if self.downloader.storage.do_I_have(self.index):
            self.downloader.picker.complete(self.index)
            self.downloader.peerdownloader.check_complete(self.index)
            self.downloader.gotpiecefunc(self.index)
        return True
    
    def _get_requests(self):
        self.requests = []
        self.request_size = 0L
        while self.downloader.storage.do_I_have_requests(self.index):
            r = self.downloader.storage.new_request(self.index)
            self.requests.append(r)
            self.request_size += r[1]
        self.requests.sort()

    def _fulfill_requests(self):
        start = 0L
        success = True
        while self.requests:
            begin, length = self.requests.pop(0)
# 2fastbt_
            if not self.downloader.storage.piece_came_in(self.index, begin, [],
                            self.received_data[start:start+length], length):
# _2fastbt
                success = False
                break
            start += length
        return success

    def _release_requests(self):
        for begin, length in self.requests:
            self.downloader.storage.request_lost(self.index, begin, length)
        self.requests = []

    def _request_ranges(self):
        s = ''
        begin, length = self.requests[0]
        for begin1, length1 in self.requests[1:]:
            if begin + length == begin1:
                length += length1
                continue
            else:
                if s:
                    s += ','
                s += str(begin)+'-'+str(begin+length-1)
                begin, length = begin1, length1
        if s:
            s += ','
        s += str(begin)+'-'+str(begin+length-1)
        return s

    def slow_start_wake_up( self ):
        self.video_support_slow_start = False
        self.resched(0)

    def is_slow_start( self ):
        return self.video_support_slow_start

    def start_video_support( self, level = 0.0, sleep_time = None ):
        '''
        Level indicates how fast a new request is scheduled and therefore the level of support required.
        0 = maximum support. (immediate rescheduling)
        1 ~= 0.01 seconds between each request
        2 ~= 0.1 seconds between each request
        and so on... at the moment just level 0 is asked. To be noted that level is a float!
        '''
        
        if DEBUG:
            print >>sys.stderr,"GetRightHTTPDownloader: START"
        self.video_support_speed = 0.001 * ( ( 10 ** level ) - 1 )
        if not self.video_support_enabled:
            self.video_support_enabled = True
            if sleep_time:
                if not self.video_support_slow_start:
                    self.video_support_slow_start = True
                    self.downloader.rawserver.add_task( self.slow_start_wake_up, sleep_time )
            else:
                self.resched( self.video_support_speed )

    def stop_video_support( self ):
        if DEBUG:
            print >>sys.stderr,"GetRightHTTPDownloader: STOP"
        if not self.video_support_enabled:
            return
        self.video_support_enabled = False

    def is_video_support_enabled( self ):
        return self.video_support_enabled

    
class GetRightHTTPDownloader:
    def __init__(self, storage, picker, rawserver,
                 finflag, errorfunc, peerdownloader,
                 max_rate_period, infohash, measurefunc, gotpiecefunc, video_support_policy):
        self.storage = storage
        self.picker = picker
        self.rawserver = rawserver
        self.finflag = finflag
        self.errorfunc = errorfunc
        self.peerdownloader = peerdownloader
        self.infohash = infohash
        self.max_rate_period = max_rate_period
        self.gotpiecefunc = gotpiecefunc
        self.measurefunc = measurefunc
        self.downloads = []
        self.seedsfound = 0
        self.video_support_policy = video_support_policy
        self.video_support_enabled = False

    def make_download(self, url):
        self.downloads.append(SingleDownload(self, url, self.video_support_policy))
        return self.downloads[-1]

    def get_downloads(self):
        if self.finflag.isSet():
            return []
        return self.downloads

    def cancel_piece_download(self, pieces):
        for d in self.downloads:
            if d.active and d.index in pieces:
                d.cancelled = True

    # Diego : wrap each single http download
    def start_video_support( self, level = 0.0, sleep_time = None ):
        for d in self.downloads:
            d.start_video_support( level, sleep_time )
        self.video_support_enabled = True

    def stop_video_support( self ):
        for d in self.downloads:
            d.stop_video_support()
        self.video_support_enabled = False

    def is_video_support_enabled( self ):
        return self.video_support_enabled

    def is_slow_start( self ):
        for d in self.downloads:
            if d.is_slow_start():
                return True
        return False

