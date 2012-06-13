# Written by Niels Zeilemaker
# see LICENSE.txt for license information
#
# Handles the case where the user did a remote query and now selected one of the
# returned torrents for download. 
#

import sys
import Queue
import os

from traceback import print_exc
from random import choice
from binascii import hexlify
from tempfile import mkstemp
from time import sleep

from Tribler.Core.simpledefs import INFOHASH_LENGTH
from Tribler.Core.CacheDB.sqlitecachedb import bin2str
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Swift.SwiftDef import SwiftDef
import shutil
from Tribler.Main.globals import DefaultDownloadStartupConfig
from Tribler.Core.exceptions import DuplicateDownloadException
import atexit
from Tribler.Main.Utility.GuiDBHandler import startWorker
import urllib

DEBUG = False

class RemoteTorrentHandler:
    
    __single = None
    def __init__(self):
        if RemoteTorrentHandler.__single:
            raise RuntimeError, "RemoteTorrentHandler is singleton"
        RemoteTorrentHandler.__single = self
        
        self.registered = False
        self._searchcommunity = None
        
        self.callbacks = {}
        
        self.trequesters = {}
        self.mrequesters = {}
        self.drequesters = {}

    def getInstance(*args, **kw):
        if RemoteTorrentHandler.__single is None:
            RemoteTorrentHandler(*args, **kw)
        return RemoteTorrentHandler.__single
    getInstance = staticmethod(getInstance)

    def register(self, dispersy, session):
        self.session = session
        self.dispersy = dispersy

        from Tribler.Utilities.TimedTaskQueue import TimedTaskQueue 
        tqueue = TimedTaskQueue("RemoteTorrentHandler")
        self.scheduletask = tqueue.add_task
        self.torrent_db = session.open_dbhandler('torrents')
        
        self.drequesters[0] = MagnetRequester(self, 0)
        self.drequesters[1] = MagnetRequester(self, 1)
        self.registered = True
        
    def is_registered(self):
        return self.registered
        
    @property
    def searchcommunity(self):
        if self.registered:
            
            if not self._searchcommunity:
                from Tribler.community.search.community import SearchCommunity
                for community in self.dispersy.get_communities():
                    if isinstance(community, SearchCommunity):
                        self._searchcommunity = community
                        break
            
            return self._searchcommunity
    
    def download_torrent(self, candidate, infohash = None, roothash = None, usercallback = None, prio = 1):
        if self.registered:
            raw_lambda = lambda candidate=candidate, infohash=infohash, roothash=roothash, usercallback=usercallback, prio=prio: self._download_torrent(candidate, infohash, roothash, usercallback, prio)
            self.scheduletask(raw_lambda)
            
    def _download_torrent(self, candidate, infohash, roothash, usercallback, prio):
        if self.registered:
            assert infohash or roothash, "We need either the info or roothash"
            
            doSwiftCollect = candidate and roothash
            if doSwiftCollect:
                requesters = self.trequesters
                hash = (infohash, roothash)
                
            elif infohash:
                requesters = self.drequesters
                hash = infohash
                
                #fix prio levels to 1 and 0
                prio = min(prio, 1)
            else:
                return
            
            if usercallback:
                self.callbacks.setdefault(hash, set()).add(usercallback)
                
            #look for lowest prio requester, which already has this infohash scheduled
            requester = None
            for i in range(prio, prio + 1):
                if i in requesters and requesters[i].is_being_requested(hash):
                    requester = requesters[i]
                    break
                
            #if not found, then used/create this requester
            if not requester:
                if prio not in requesters:
                    if doSwiftCollect:
                        requesters[prio] = TorrentRequester(self, self.drequesters[1], self.session, prio)
                    else:
                        requesters[prio] = MagnetRequester(self, prio)
                requester = requesters[prio]
        
            #make request
            requester.add_request(hash, candidate)
        
            if DEBUG:
                print >>sys.stderr,'rtorrent: adding torrent request:', bin2str(infohash or ''), bin2str(roothash or ''), candidate, prio
                
    def download_torrentmessages(self, candidate, infohashes, usercallback = None, prio = 1):
        if self.registered:
            raw_lambda = lambda candidate=candidate, infohashes=infohashes, usercallback=usercallback, prio=prio: self._download_torrentmessages(candidate, infohashes, usercallback, prio)
            self.scheduletask(raw_lambda)
    
    def _download_torrentmessages(self, candidate, infohashes, usercallback, prio):
        assert all(isinstance(infohash, str) for infohash in infohashes), "INFOHASH has invalid type"
        assert all(len(infohash) == INFOHASH_LENGTH for infohash in infohashes), "INFOHASH has invalid length:"
        
        if self.registered:
            if usercallback:
                for infohash in infohashes:
                    callback = lambda infohash=infohash: usercallback(infohash)
                    self.callbacks.setdefault((infohash,None), set()).add(callback)
                    
            if prio not in self.mrequesters:
                self.mrequesters[prio] = TorrentMessageRequester(self, self.searchcommunity, prio)
            
            requester = self.mrequesters[prio]
            
            #make request
            requester.add_request(frozenset(infohashes), candidate)
            if DEBUG:
                print >>sys.stderr,'rtorrent: adding torrent messages request:', map(bin2str, infohashes), candidate, prio
   
    def has_torrent(self, infohash, callback):
        tor_col_dir = self.session.get_torrent_collecting_dir()
        startWorker(None, self._has_torrent, wargs = (infohash, tor_col_dir, callback))
        
    def _has_torrent(self, infohash, tor_col_dir, callback):
        #save torrent
        result = False
        torrent = self.torrent_db.getTorrent(infohash, ['torrent_file_name', 'swift_torrent_hash'], include_mypref = False)
        if torrent:
            if torrent.get('torrent_file_name', False) and os.path.isfile(torrent['torrent_file_name']):
                result = torrent['torrent_file_name']
            
            elif torrent.get('swift_torrent_hash', False):
                sdef = SwiftDef(torrent['swift_torrent_hash'])
                torrent_filename = os.path.join(tor_col_dir, sdef.get_roothash_as_hex())
                
                if os.path.isfile(torrent_filename):
                    self.torrent_db.updateTorrent(infohash, notify=False, torrent_file_name=torrent_filename)
                    result = torrent_filename
                    
        raw_lambda = lambda result=result: callback(result)
        self.scheduletask(raw_lambda)
    
    def save_torrent(self, tdef, callback = None):
        if self.registered:
            def do_schedule(filename):
                if not filename:
                    self._save_torrent(tdef, callback)
                elif callback:
                    startWorker(None, callback)
            
            infohash = tdef.get_infohash()
            self.has_torrent(infohash, do_schedule)
    
    def _save_torrent(self, tdef, callback = None):
        tmp_handle, tmp_filename = mkstemp()
        tdef.save(tmp_filename)
        os.close(tmp_handle)
        
        sdef, swiftpath = self._write_to_collected(tmp_filename)
        
        try:
            os.remove(tmp_filename)
        except:
            atexit.register(lambda tmp_filename=tmp_filename: os.remove(tmp_filename))
        
        def do_db(callback):
            #add this new torrent to db
            infohash = tdef.get_infohash()
            if self.torrent_db.hasTorrent(infohash):
                self.torrent_db.updateTorrent(infohash, swift_torrent_hash = sdef.get_roothash(), torrent_file_name = swiftpath)
            else:
                self.torrent_db.addExternalTorrent(tdef, extra_info = {'filename': swiftpath, 'swift_torrent_hash':sdef.get_roothash(), 'status':'good'})
            
            #notify all
            self.notify_possible_torrent_infohash(infohash, True)
            if callback:
                callback()
            
        startWorker(None, do_db, wargs = (callback, ))
    
    def _write_to_collected(self, filename):
        #calculate root-hash
        sdef = SwiftDef()
        sdef.add_content(filename)
        sdef.finalize(self.session.get_swift_path(), destdir = self.session.get_torrent_collecting_dir())
        
        mfpath = os.path.join(self.session.get_torrent_collecting_dir(),sdef.get_roothash_as_hex())
        if not os.path.exists(mfpath):
            if os.path.exists(mfpath + ".mhash"): #indicating active swift download
                download = self.session.get_download(sdef.get_roothash())
                if download:
                    self.session.remove_download(download, removestate = True)
                    sleep(1)
                else:
                    os.remove(mfpath + ".mhash")
            
            try:
                shutil.copy(filename, mfpath)
                shutil.move(filename+'.mhash', mfpath+'.mhash')
                shutil.move(filename+'.mbinmap', mfpath+'.mbinmap')
                
            except:
                print_exc()
        
        return sdef, mfpath
    
    def notify_possible_torrent_roothash(self, roothash):
        keys = self.callbacks.keys()
        for key in keys:
            if key[1] == roothash:
                handle_lambda = lambda key=key: self._handleCallback(key, True)
                self.scheduletask(handle_lambda)
        
        sdef = SwiftDef(roothash)
        swiftpath = os.path.join(self.session.get_torrent_collecting_dir(),sdef.get_roothash_as_hex())
        if os.path.exists(swiftpath):
            tdef = TorrentDef.load(swiftpath)
        
            if self.torrent_db.hasTorrent(tdef.get_infohash()):
                self.torrent_db.updateTorrent(tdef.get_infohash(), swift_torrent_hash = sdef.get_roothash(), torrent_file_name = swiftpath)
            else:
                self.torrent_db._addTorrentToDB(tdef, source = "SWIFT", extra_info = {'filename': swiftpath, 'swift_torrent_hash':roothash, 'status':'good'}, commit = True)
    
    def notify_possible_torrent_infohash(self, infohash, actualTorrent = False):
        keys = self.callbacks.keys()
        for key in keys:
            if key[0] == infohash or key == infohash:
                handle_lambda = lambda key=key, actualTorrent=actualTorrent: self._handleCallback(key, actualTorrent)
                self.scheduletask(handle_lambda)
        
    def _handleCallback(self, key, torrent = True):
        if DEBUG:
            print >>sys.stderr,'rtorrent: got torrent for:', key
        
        if key in self.callbacks:
            for usercallback in self.callbacks[key]:
                self.session.uch.perform_usercallback(usercallback)

            del self.callbacks[key]
            
            if torrent:
                for requester in self.trequesters.values():
                    if requester.is_being_requested(key):
                        requester.remove_request(key)
                        
                for requester in self.drequesters.values():
                    if requester.is_being_requested(key):
                        requester.remove_request(key)
            else:
                for requester in self.mrequesters.values():
                    if requester.is_being_requested(key):
                        requester.remove_request(key)
    
    def getQueueSize(self):
        nr_sources = nr_requests = 0
        for requester in self.trequesters.values() + self.drequesters.values():
            nr_sources += len(requester.sources)
            for infohash in requester.sources.keys():
                nr_requests += len(requester.sources.get(infohash, []))
        return nr_sources, nr_requests

class Requester:
    REQUEST_INTERVAL = 0.5
    
    def __init__(self, scheduletask, prio):
        self.scheduletask = scheduletask
        self.prio = prio
        
        self.queue = Queue.Queue()
        self.sources = {}
        self.canrequest = True
    
    def add_request(self, hash, candidate):
        was_empty = self.queue.empty()
        
        if hash not in self.sources:
            self.sources[hash] = set()
            
        self.sources[hash].add(candidate)
        self.queue.put(hash)
        
        if was_empty:
            self.scheduletask(self.doRequest, t = self.REQUEST_INTERVAL * self.prio)
            
    def is_being_requested(self, hash):
        return hash in self.sources
    
    def remove_request(self, hash):
        del self.sources[hash]
            
    def doRequest(self):
        try:
            madeRequest = False
            if isinstance(self.canrequest, bool):
                canRequest = self.canrequest
            else:
                canRequest = self.canrequest()
            if canRequest:
                #request new infohash from queue
                while True:
                    hash = self.queue.get_nowait()
                    
                    #check if still needed
                    if hash in self.sources: 
                        break
                    else:
                        self.queue.task_done()
                    
                try:
                    #~load balance sources
                    candidate = choice(list(self.sources[hash]))
                    self.sources[hash].remove(candidate)
                    
                    if len(self.sources[hash]) < 1:
                        del self.sources[hash]
                        
                    madeRequest = self.doFetch(hash, candidate)
                    
                #Make sure exceptions wont crash this requesting loop
                except: 
                    print_exc()
                
                self.queue.task_done()
            
            if madeRequest or not canRequest:
                self.scheduletask(self.doRequest, t = self.REQUEST_INTERVAL * self.prio)
            else:
                self.scheduletask(self.doRequest)
        except Queue.Empty:
            pass
        
    def doFetch(self, hash, candidate):
        raise NotImplementedError()

class TorrentRequester(Requester):
    MAGNET_TIMEOUT = 5.0
    SWIFT_CANCEL = 30.0
    
    def __init__(self, remote_th, magnet_requester, session, prio):
        Requester.__init__(self, remote_th.scheduletask, prio)
        
        self.remote_th = remote_th
        self.magnet_requester = magnet_requester
        self.session = session
        
        defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
        self.dscfg = defaultDLConfig.copy()
        self.dscfg.set_dest_dir(session.get_torrent_collecting_dir())
    
    
    def doFetch(self, hash, candidate):
        infohash, roothash = hash
        
        raw_lambda = lambda filename, hash=hash, candidate=candidate: self._doFetch(filename, hash, candidate)
        self.remote_th.has_torrent(infohash, raw_lambda)
    
    def _doFetch(self, filename, hash, candidate):
        infohash, roothash = hash
        
        if filename:
            self.remote_th.notify_possible_torrent_infohash(infohash, True)
            self.remote_th.notify_possible_torrent_infohash(hash, True)
            
        elif candidate:
            ip,port = candidate.sock_addr
            if not candidate.tunnel:
                port = 7758
                
            if DEBUG:
                print >>sys.stderr,"rtorrent: requesting torrent", hash, ip, port
            
            doMagnet = self.prio <= 1
            
            sdef = SwiftDef(roothash, tracker="%s:%d"%(ip,port))
            dcfg = self.dscfg.copy()
            try:
                #hide download from gui
                download = self.session.start_download(sdef, dcfg, hidden=True)
                
                state_lambda = lambda ds, infohash=infohash, roothash=roothash, doMagnet=doMagnet: self.check_progress(ds, infohash, roothash, doMagnet)
                download.set_state_callback(state_lambda, getpeerlist=False, delay=self.SWIFT_CANCEL)
            
            except DuplicateDownloadException:
                download = self.session.get_download(roothash)
                download.add_peer((ip,port))
        
            #schedule a magnet lookup after X seconds
            if doMagnet:
                magnet_lambda = lambda infohash=infohash: self.magnet_requester.add_request(infohash, None)
                self.scheduletask(magnet_lambda, t = self.MAGNET_TIMEOUT * (self.prio))
            return True
            
    def check_progress(self, ds, infohash, roothash, didMagnet):
        d = ds.get_download()
        cdef = d.get_def()
        if ds.get_progress() == 0:
            remove_lambda = lambda d=d: self._remove_donwload(d)
            self.scheduletask(remove_lambda)
            
            if not didMagnet:
                if DEBUG:
                    print >>sys.stderr,"rtorrent: switching to magnet for", cdef.get_name(), bin2str(infohash)
                self.magnet_requester.add_request(infohash, None)
            return (0,False)
        
        elif ds.get_progress() == 1:
            remove_lambda = lambda d=d: self._remove_donwload(d, False)
            self.scheduletask(remove_lambda)
            
            if DEBUG:
                print >>sys.stderr,"rtorrent: swift finished for", cdef.get_name()
            
            self.remote_th.notify_possible_torrent_roothash(roothash)
            return (0,False)
    
        return (5.0, True)
    
    def _remove_donwload(self, d, removestate = True):
        # Arno, 2012-05-30: Make sure .mbinmap is written
        if not removestate and d.get_def().get_def_type() == 'swift':
            d.checkpoint()
        self.session.remove_download(d, removestate = removestate)
            
class TorrentMessageRequester(Requester):
    
    def __init__(self, remote_th, searchcommunity, prio):
        Requester.__init__(self, remote_th.scheduletask, prio)
        self.searchcommunity = searchcommunity
    
    def doFetch(self, hashes, candidate):
        if self.searchcommunity:
            if DEBUG:
                print >>sys.stderr,"rtorrent: requesting torrent message", map(bin2str, hashes), candidate
            self.searchcommunity.create_torrent_request(hashes, candidate)
            
        return True

class MagnetRequester(Requester):
    MAX_CONCURRENT = 1
    MAGNET_RETRIEVE_TIMEOUT = 30.0
    
    def __init__(self, remote_th, prio):
        if sys.platform == 'darwin':
            #mac has severe problems with closing connections, add additional time to allow it to close connections
            self.REQUEST_INTERVAL = 15.0
        
        Requester.__init__(self, remote_th.scheduletask, prio)
        
        self.remote_th = remote_th
        self.requestedInfohashes = set()
        
        if prio == 1 and not sys.platform == 'darwin':
            self.MAX_CONCURRENT = 3
            
        self.canrequest = lambda: len(self.requestedInfohashes) < self.MAX_CONCURRENT
    
    def doFetch(self, infohash, candidate):
        raw_lambda = lambda filename, infohash=infohash, candidate=candidate: self._doFetch(filename, infohash, candidate)
        self.remote_th.has_torrent(infohash, raw_lambda)
    
    def _doFetch(self, filename, infohash, candidate):
        if filename:
            self.remote_th.notify_possible_torrent_infohash(infohash, True)
            
        elif infohash not in self.requestedInfohashes:
            self.requestedInfohashes.add(infohash)
            
            #try magnet link
            magnetlink = "magnet:?xt=urn:btih:" + hexlify(infohash)
            
            #see if we know any trackers for this magnet
            trackers = self.remote_th.torrent_db.getTracker(infohash)
            for tracker,_ in trackers:
                magnetlink += "&tr="+urllib.quote_plus(tracker)
            
            if DEBUG:
                print >> sys.stderr, 'rtorrent: requesting magnet', bin2str(infohash), self.prio, magnetlink
        
            TorrentDef.retrieve_from_magnet(magnetlink, self.__torrentdef_retrieved, self.MAGNET_RETRIEVE_TIMEOUT, max_connections = 30 if self.prio == 0 else 10)
            
            failed_lambda = lambda infohash=infohash: self.__torrentdef_failed(infohash)
            self.scheduletask(failed_lambda, t = self.MAGNET_RETRIEVE_TIMEOUT)
            return True
                
    def __torrentdef_retrieved(self, tdef):
        infohash = tdef.get_infohash()
        if DEBUG:
            print >> sys.stderr, 'rtorrent: received torrent using magnet', bin2str(infohash)
        
        self.remote_th.save_torrent(tdef)
        if infohash in self.requestedInfohashes:
            self.requestedInfohashes.remove(infohash)
        
    def __torrentdef_failed(self, infohash):
        if infohash in self.requestedInfohashes:
            self.requestedInfohashes.remove(infohash)
