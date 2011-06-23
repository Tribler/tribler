# Written by John Hoffman, George Milescu
# see LICENSE.txt for license information

import sys
from random import randint
from urlparse import urlparse
from httplib import HTTPConnection
import urllib
import time
from threading import Thread,currentThread,Lock
from traceback import print_exc, print_stack
from collections import deque 

from Tribler.Core.BitTornado.__init__ import product_name,version_short
from Tribler.Core.BitTornado.bitfield import Bitfield
from Tribler.Core.Utilities.utilities import show_permid_short, show_permid
from Tribler.Core.BitTornado.CurrentRateMeasure import Measure
from Tribler.Core.Utilities.timeouturlopen import find_proxy
from Tribler.Core.simpledefs import *

from Tribler.Core.ProxyService.Doe import Doe
from Tribler.Core.ProxyService.Proxy import Proxy
from Tribler.Core.ProxyService.RatePredictor import ExpSmoothRatePredictor

DEBUG = False

PROXY_DLDR_PERIODIC_CHECK = 3 # the interval (in seconds) used to check if all requested pieces have arrived
EXPIRE_TIME = 20 # the minimal time (in seconds) each request has to be handled
SHORT_TERM_MEASURE_INTERVAL = 10 # the time interval (in seconds) for which a download is measured
MAX_NO_PROXIES = 4 # the maximum number of used proxies 

VERSION = product_name+'/'+version_short

class haveComplete:
    def complete(self):
        return True
    def __getitem__(self, x):
        return True
haveall = haveComplete()

class SingleDownload():

    def __init__(self, proxydownloader, proxy_permid):
        self.downloader = proxydownloader
        self.proxy_permid = proxy_permid
        
        self.connection = None
        
        self.measure = Measure(self.downloader.max_rate_period)
        self.active_requests = {} # dictionary with all  indexes currently being downloaded. Key: index, value: timestamp (the moment when the piece was requested)
        self.piece_size = self.downloader.storage._piecelen(0)
        self.total_len = self.downloader.storage.total_length
        self.requests = {} # dictionary of lists: requests[index] contains a list of all reserved chunks
        self.request_size = {} # dictionary of piece sizes
        self.received_data = {} # a dictionary of piece data
        self.endflag = False
        self.error = None
        self.retry_period = 0 #30
        self._retry_period = None
        self.errorcount = 0
        self.active = False
        self.cancelled = False
        self.numpieces = self.downloader.numpieces
        
        self.proxy_have = Bitfield(self.downloader.numpieces)
        
        self.first_piece_request=True
        
        # boudewijn: VOD needs a download measurement that is not
        # averaged over a 'long' period. downloader.max_rate_period is
        # (by default) 20 seconds because this matches the unchoke
        # policy.
        self.short_term_measure = Measure(SHORT_TERM_MEASURE_INTERVAL)

        # boudewijn: each download maintains a counter for the number
        # of high priority piece requests that did not get any
        # responce within x seconds.
        self.bad_performance_counter = 0

        # HTTP Video Support
        self.request_lock = Lock()
        self.video_support_policy     = False  # TODO : get from constructor parameters
        self.video_support_enabled    = False # Don't start immediately with support
        self.video_support_speed      = 0.0   # Start with the faster rescheduling speed
        self.video_support_slow_start = False # If enabled delay the first request (give chance to peers to give bandwidth)
        # Arno, 2010-04-07: Wait 1 second before using HTTP seed. TODO good policy
        # If Video Support policy is not eneabled then use Http seed normaly
        if not self.video_support_policy:
            self.resched(1)

    def resched(self, len = None):
        """ Schedule a new piece to be downloaded via proxy
        
        @param len: schedule delay
        """
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
        """ TODO:
        
        @param index: TODO:
        """
        # if the piece is downloading or already downloaded
        if index in self.downloader.allocated_pieces.keys():
            return False
        
        #return self.downloader.storage.do_I_have_requests(index)

        # TODO: endflag behavior
        if self.endflag:
            return self.downloader.storage.do_I_have_requests(index)
        else:
            return self.downloader.storage.is_unstarted(index)
        

    def download(self):
        """ Download one piece
        """
        from Tribler.Core.Session import Session
        session = Session.get_instance()
        session.uch.perform_usercallback(self._download)

    def _download(self):
        """ Download one piece
        """
        #self.request_lock.acquire()
        if DEBUG:
            print "proxy-sdownload: _download()"

        if self.first_piece_request:
            slots=self.numpieces/40 # 2.5%
            self.first_piece_request = False
        else:
            slots=1

        self.cancelled = False

        for p in range(slots):
            if self.downloader.picker.am_I_complete():
                if self in self.downloader.downloads:
                    self.downloader.downloads.remove(self)
                if DEBUG:
                    print "proxy-sdownload: _download: i_am_complete, return"
                return
            
            # Use the lock to make sure the same piece index is not generated simultaneously by two threads
            self.downloader.get_next_piece_lock.acquire()
            try:
                new_index = self.downloader.picker.next(self.proxy_have, self._want, self)
        
                if new_index is None:
                    self.endflag = False
                    self.first_piece_request = True
                    
                    self.resched(1)
                    if DEBUG:
                        print "proxy-sdownload: _download: picker returned none, return"
                    return
                else:
                    # save the index-permid pair
                    self.downloader.allocated_pieces[new_index] = self.proxy_permid
                    
                    self.active_requests[new_index] = time.time()
                    # i have a valid index
        
                    # reserve the new_index piece
                    # reserve all available (previously not reserved by anyone) chunks in new_index
                    self._get_requests(new_index)
                    
                    if DEBUG:
                        print "proxy-sdownload: _download: requesting piece", new_index, "to proxy"
                    # Send request to proxy
                    # Just overwrite other blocks and don't ask for ranges.
                    self._request(new_index)
            finally:
                self.downloader.get_next_piece_lock.release()
            
        self.active = True

    def _request(self, index):
        """ Request the piece index to the proxy
        """

        import encodings.ascii
        import encodings.punycode
        import encodings.idna
        
        self.error = None
        self.received_data[index] = None
        try:
            if DEBUG:
                print >>sys.stderr, 'ProxyDownloader: _request: piece ', index

            self.downloader.doe.send_download_piece(index, self.proxy_permid)
        except Exception, e:
            print_exc()    
            self.error = 'error accessing proxy seed: '+str(e)
        
    def request_finished(self, index):
        """ Called after the requested data arrived
        
        Called from Doe.got_piece_data
        """
        self.active = False

        if self.error is not None:
            self.errorcount += 1

        if self.received_data[index]:
            self.errorcount = 0
            if not self._got_data(index):
                self.received_data[index] = None
        
        if not self.received_data[index]:
            self._release_requests(index)
            self.downloader.btdownloader.piece_flunked(index)

        # TODO: handle robustness in a more elegant way
        try:
            del(self.active_requests[index])
        except:
            pass
        try:
            del(self.requests[index])
        except:
            pass
        try:
            del(self.request_size[index])
        except:
            pass
        try:
            del(self.received_data[index])
        except:
            pass
        
        #self.request_lock.release()
        if self._retry_period is not None:
            self.resched(self._retry_period)
            self._retry_period = None
            return
        self.resched()

    def _got_data(self, index):
        """ Pass the received data to the storage module and update the bittorrent engine data structures
        """
        
        # Diego, 2010-04-16: retry_period set depending on the level of support asked by the MovieOnDemandTransporter
        # TODO: update _retry_perion, if necessary
        #self._retry_period = self.video_support_speed

        if len(self.received_data[index]) != self.request_size[index]:
            self.downloader.errorfunc('corrupt data from proxy - redownloading')
            
            # unmark the piece to be redownloaded in the future
            try:
                del(self.downloader.allocated_pieces[index])
            except:
                pass 
            
            return False
        
        self.measure.update_rate(len(self.received_data[index]))
        self.short_term_measure.update_rate(len(self.received_data[index]))
        self.downloader.measurefunc(len(self.received_data[index]))
        if self.bad_performance_counter:
            self.bad_performance_counter -= 1
        
        if self.cancelled:
            return False
        
        if not self._fulfill_requests(index):
            return False
        
        if self.downloader.storage.do_I_have(index):
            self.downloader.picker.complete(index)
            self.downloader.peerdownloader.check_complete(index)
            self.downloader.gotpiecefunc(index)

        # Mark the piece as downloaded
        self.downloader.allocated_pieces[index] = None
        return True
    
    def _get_requests(self, index):
        """ Reserve all chunks in self.piece
        """
        
        # Reserve all chunks in the index piece
        self.requests[index] = []
        self.request_size[index] = 0L
        # reserve all available (previously not reserved by anyone) chunks
        while self.downloader.storage.do_I_have_requests(index):
            # reserve another chunk
            r = self.downloader.storage.new_request(index)
            self.requests[index].append(r)
            self.request_size[index] += r[1]
        self.requests[index].sort()

    def _fulfill_requests(self, index):
        """ Save the received data on the disk using the storage module interface
        """
        if len(self.requests[index]) == 0:
            return False
        
        start = 0L
        success = True
        while self.requests[index]:
            begin, length = self.requests[index].pop(0)

            if not self.downloader.storage.piece_came_in(index, begin, [], self.received_data[index][start:start+length], length):
                success = False
                break
            
            start += length
        return success

    def _release_requests(self, index):
        """ Cancel the reservation for all chunks in self.piece
        """

        for begin, length in self.requests[index]:
            self.downloader.storage.request_lost(index, begin, length)
        self.requests[index] = []

    def slow_start_wake_up(self):
        """ TODO:
        """

        self.video_support_slow_start = False
        self.resched(0)

    def is_slow_start(self):
        """ TODO:
        """

        return self.video_support_slow_start

    def start_video_support(self, level = 0.0, sleep_time = None):
        """ Level indicates how fast a new request is scheduled and therefore the level of support required.
        0 = maximum support. (immediate rescheduling)
        1 ~= 0.01 seconds between each request
        2 ~= 0.1 seconds between each request
        and so on... at the moment just level 0 is asked. To be noted that level is a float!
        """
        
        if DEBUG:
            print >>sys.stderr,"GetRightHTTPDownloader: START"
        
        self.video_support_speed = 0.001 * ((10 ** level)-1)
        
        if not self.video_support_enabled:
            self.video_support_enabled = True
            if sleep_time:
                if not self.video_support_slow_start:
                    self.video_support_slow_start = True
                    self.downloader.rawserver.add_task(self.slow_start_wake_up, sleep_time)
            else:
                self.resched(self.video_support_speed)

    def stop_video_support(self):
        """ TODO:
        """

        if DEBUG:
            print >>sys.stderr,"GetRightHTTPDownloader: STOP"

        if not self.video_support_enabled:
            return

        self.video_support_enabled = False

    def is_video_support_enabled(self):
        """ TODO:
        """
        return self.video_support_enabled
    
    
    def get_rate(self):
        """ TODO:
        """
        return self.measure.get_rate()

    def get_short_term_rate(self):
        """ TODO:
        """
        return self.short_term_measure.get_rate()

    
class ProxyDownloader:
    """ This class manages connects the doe and the proxy components with the BitTorrent engine.
    """

    def __init__(self, bt1_download, storage, picker, rawserver,
                 finflag, errorfunc, btdownloader,
                 max_rate_period, infohash, measurefunc, gotpiecefunc, dlinstance, scheduler):
        self.storage = storage
        self.picker = picker
        self.rawserver = rawserver
        self.finflag = finflag
        self.errorfunc = errorfunc
        self.btdownloader = btdownloader
        self.peerdownloader = btdownloader
        self.infohash = infohash
        self.max_rate_period = max_rate_period
        self.gotpiecefunc = gotpiecefunc
        self.measurefunc = measurefunc
        self.downloads = []
        self.seedsfound = 0
        self.video_support_enabled = False
        self.bt1_download = bt1_download
        self.numpieces = btdownloader.numpieces
        self.storage = btdownloader.storage
        self.scheduler = scheduler
        
        self.proxy = None
        self.doe = None
        self.rate_predictor = None
        self.dlinstance = dlinstance
        
        # allcoated_pieces maps each piece index to the permid the piece was requested to
        # if index in allocated_pieces.keys(): piece is downloading or downloaded
        # if allocated_pieces[index] = None: piece was already downloaded
        # if allocated_pieces[index] = permid: piece is currently downloading
        self.allocated_pieces = {}
        self.get_next_piece_lock = Lock()

        if DEBUG:
            print >>sys.stderr,"ProxyDownloader: proxyservice_role is",self.bt1_download.config['proxyservice_role']
      
        # Create the Doe object for this download
        self.doe = Doe(self.infohash, self.bt1_download.len_pieces, self.btdownloader, self, self.bt1_download.encoder)
        
        # Create the Proxy object
        self.proxy = Proxy(self.infohash, self.bt1_download.len_pieces, self.btdownloader, self, self.bt1_download.encoder)
        self.bt1_download.encoder.set_proxy(self.proxy)

        self.rate_predictor = ExpSmoothRatePredictor(self.bt1_download.rawserver, self.bt1_download.downmeasure, self.bt1_download.config['max_download_rate'])
        self.bt1_download.picker.set_rate_predictor(self.rate_predictor)
        self.rate_predictor.update()

        if DEBUG:
            print >>sys.stderr,"ProxyDownloader: loading complete"
        
        # notify the proxydownloader finished loading
        from Tribler.Core.Session import Session
        session = Session.get_instance()
        session.uch.notify(NTFY_PROXYDOWNLOADER, NTFY_STARTED, None, self.infohash)

        # get proxy_permids from the ProxyPeerManager and call the Doe to send Relay Requests
        self.check_proxy_supply()
        
        self.scheduler(self.dlr_periodic_check, PROXY_DLDR_PERIODIC_CHECK)

    def proxy_connection_closed(self, proxy_permid):
        """  Handles the connection closed event.
        
        Called by ProxyPeerManager.ol_connection_created_or_closed()
        
        @param proxy_permid: the permid of the proxy node for which the connection was closed 
        """

        if DEBUG:
            print >>sys.stderr, "ProxyDownloader: proxy_connection_closed for", show_permid_short(proxy_permid)

        if proxy_permid in self.doe.confirmed_proxies:
            if DEBUG:
                print >> sys.stderr, "ProxyDownloader: ol_connection_created_or_closed: confirmed proxy ol connection closed"

            dl_object = None
            for download in self.downloads:
                if download.proxy_permid == proxy_permid:
                    dl_object = download

            # 08/06/11 boudewijn: this may not always find a dl_object
            if dl_object:
                cancel_requests = {} #key=piece number, value=proxy permid
                for piece_index,time_of_request in dl_object.active_requests.items():
                    dl_object.bad_performance_counter += 1
                    cancel_requests[piece_index] = dl_object.proxy_permid

                # Cancel all requests that did not arrive yet
                if cancel_requests:
                    for index in cancel_requests:
                        try:
                            dl_object._release_requests(index)
                        except:
                            pass
                        try:
                            del(dl_object.active_requests[index])
                        except:
                            pass
                        try:
                            del(self.allocated_pieces[index])
                        except:
                            pass
                self.doe.remove_unreachable_proxy(proxy_permid)
            
        if proxy_permid in self.doe.asked_proxies:
            if DEBUG:
                print >> sys.stderr, "ProxyDownloader: ol_connection_created_or_closed: asked proxy ol connection closed"
            self.doe.remove_unreachable_proxy(proxy_permid)

    def dlr_periodic_check(self):
        """ Calls the check_outstanding_requests function and then reschedules itself
        """
        if self.dlinstance.get_proxyservice_role() != PROXYSERVICE_ROLE_DOE:
            return

        self.check_outstanding_requests(self.downloads)
        
        self.check_proxy_supply()
        
        self.scheduler(self.dlr_periodic_check, PROXY_DLDR_PERIODIC_CHECK)

    def check_proxy_supply(self):
        """ Get proxy_permids from the ProxyPeerManager and call the Doe to send Relay Requests
        """
        if self.dlinstance.get_proxyservice_role() != PROXYSERVICE_ROLE_DOE:
            return
        
        if len(self.doe.confirmed_proxies) >= MAX_NO_PROXIES:
            return
        
        proxy_list = []
        
        from Tribler.Core.Overlay.OverlayApps import OverlayApps
        overlay_apps = OverlayApps.getInstance()
        for i in range(MAX_NO_PROXIES-len(self.doe.confirmed_proxies)):
            proxy_permid =  overlay_apps.proxy_peer_manager.request_proxy(self)
            if proxy_permid is not None:
                proxy_list.append(proxy_permid)
        
        if len(proxy_list) != 0:
            self.doe.send_relay_request(proxy_list)

    def check_outstanding_requests(self, downloads):
        now = time.time()

        for download in downloads:
            cancel_requests = {} #key=piece number, value=proxy permid
            download_rate = download.get_short_term_rate()
            
            for piece_index,time_of_request in download.active_requests.items():
                # each request must be allowed at least some minimal time to be handled
                if now < time_of_request + EXPIRE_TIME:
                    continue

                if download_rate == 0:
                    # we have not received anything in the last min_delay seconds
                    if DEBUG:
                        print >>sys.stderr, "ProxyDownloader: download_rate is 0 for this connection. Canceling all piece requests"
                    download.bad_performance_counter += 1
                cancel_requests[piece_index] = download.proxy_permid
                
            # Cancel all requests that did not arrive yet
            if cancel_requests:
                for index in cancel_requests:
                    try:
                        download._release_requests(index)
                    except:
                        pass
                    try:
                        del(download.active_requests[index])
                    except:
                        pass
                    try:
                        del(self.allocated_pieces[index])
                    except:
                        pass
                    self.doe.send_cancel_downloading_piece(index, cancel_requests[index])


    def make_download(self, proxy_permid):
        """ Ads a new data channel with a proxy node.
        Used for the doe component.
        
        @param permid: The permid of the proxy
        """
        self.downloads.append(SingleDownload(self, proxy_permid))
        return self.downloads[-1]

    def get_downloads(self):
        """ Returns the list of proxy data channels (downloads)
        """
        if self.finflag.isSet():
            return []
        return self.downloads

    def cancel_piece_download(self, pieces):
        """ TODO:
        
        @param pieces: TODO:
        """
        for d in self.downloads:
            if d.active and d.index in pieces:
                d.cancelled = True

    # Diego : wrap each single http download
    def start_video_support(self, level = 0.0, sleep_time = None):
        """ TODO:
        
        @param level: TODO:
        @param sleep_time: TODO:
        """
        for d in self.downloads:
            d.start_video_support(level, sleep_time)
        self.video_support_enabled = True

    def stop_video_support(self):
        """ TODO:
        """
        for d in self.downloads:
            d.stop_video_support()
        self.video_support_enabled = False

    def is_video_support_enabled(self):
        """ TODO:
        """
        return self.video_support_enabled

    def is_slow_start(self):
        """ TODO:
        """
        for d in self.downloads:
            if d.is_slow_start():
                return True
        return False
