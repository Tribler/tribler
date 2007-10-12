import sys
import os
from threading import Thread,Event

from BitTornado.RawServer import RawServer
from BitTornado.ServerPortHandler import MultiHandler
from BitTornado.RateLimiter import RateLimiter
from BitTornado.natpunch import UPnPWrapper, UPnPError
from BitTornado.BT1.track import Tracker
from BitTornado.HTTPHandler import HTTPHandler,DummyHTTPHandler

from Tribler.Overlay.SecureOverlay import SecureOverlay
from Tribler.Overlay.OverlayApps import OverlayApps

class Bindable:

    def __init__(self):
        self.bindlock = BindLock()
        self.configee = None
    
    def bind(self,lock):
        self.bindlock.set(lock)
        
    def set_configee(self,configee):
        self.configee = configee
        
    def is_bound(self):
        return self.bindlock.get()


class BindLock:
    
    def __init__(self):
        self.lock = None
        
    def acquire(self):
        if self.lock is not None:
            self.lock.acquire()
            
    def release(self):
        if self.lock is not None:
            self.lock.release()

    def set(self,lock):
        self.lock = lock
        
    def get(self):
        return self.lock


class TriblerLaunchMany(Thread):
    
    def __init__(self,scfg,lock):
        Thread.__init__(self)
        self.setDaemon(True)
        self.setName("Network"+self.getName())
        
        self.scfg = scfg
        self.lock = lock
        
        self.downloads = {}
        config = scfg.config # Should be safe at startup

        # Orig
        self.doneflag = Event()
        self.upnp_type = 0

        self.rawserver = RawServer(self.doneflag,
                                   config['timeout_check_interval'],
                                   config['timeout'],
                                   ipv6_enable = config['ipv6_enabled'],
                                   failfunc = self.failfunc,
                                   errorfunc = self.exceptionfunc)
        self.listen_port = self.rawserver.find_and_bind(0, 
                    config['minport'], config['maxport'], config['bind'], 
                    reuse = True,
                    ipv6_socket_style = config['ipv6_binds_v4'], 
                    randomizer = config['random_port'])
        print "Got listen port", self.listen_port
        
        self.ratelimiter = RateLimiter(self.rawserver.add_task, 
                                       config['upload_unit_size'])
        self.ratelimiter.set_upload_rate(config['max_upload_rate'])

        self.handler = MultiHandler(self.rawserver, self.doneflag)
        #
        # Arno: disabling out startup of torrents, need to fix this
        # to let text-mode work again.
        #

        # do_cache -> do_overlay -> (do_buddycast, do_download_help)
        if not config['cache']:
            config['overlay'] = 0    # overlay
        if not config['overlay']:
            config['buddycast'] = 0
            config['download_help'] = 0

        if config['overlay']:
            self.secure_overlay = SecureOverlay.getInstance()
            mykeypair = config['eckeypair']
            self.secure_overlay.register(self.rawserver,self.handler,self.listen_port,self.config['max_message_length'],mykeypair)
            self.overlay_apps = OverlayApps.getInstance()
            self.overlay_apps.register(self.secure_overlay, self, self.rawserver, config)
            # It's important we don't start listening to the network until
            # all higher protocol-handling layers are properly configured.
            self.secure_overlay.start_listening()
        
        self.internaltracker = None
        if config['internaltracker'] and 'trackerconf' in config:
            # TEMP ARNO TODO: make sure trackerconf also set when using btlaunchmany
            tconfig = config['trackerconf']
            self.internaltracker = Tracker(tconfig, self.rawserver)
            self.httphandler = HTTPHandler(self.internaltracker.get, tconfig['min_time_between_log_flushes'])
        else:
            self.httphandler = DummyHTTPHandler()
        self.handler.set_httphandler(self.httphandler)
        
        # APITODO
        #self.torrent_db = TorrentDBHandler()
        #self.mypref_db = MyPreferenceDBHandler()
        
        # add task for tracker checking
        if not config['torrent_checking']:
            self.rawserver.add_task(self.torrent_checking, self.torrent_checking_period)
        

    def add(self,tdef,dcfg):
        self.lock.acquire()
        try:
            d = Download(self.lock,self.scfg,self.multihandler,tdef,dcfg)
            self.downloads[d.get_def().get_infohash()] = d
        finally:
            self.lock.release()
        return d
        
    def remove(self,d):
        self.lock.acquire()
        try:
            d.stop()
            d._cleanup_disk()
            del self.downloads[d.get_def().get_infohash()]
        finally:
            self.lock.release()

    def get_downloads(self):
        self.lock.acquire()
        try:
            l = self.downloads[:] #copy, is mutable
        finally:
            self.lock.release()
        return l
    
    def failfunc(self,msg):
        print >>sys.stderr,"TriblerLaunchMany: failfunc called",msg

    def exceptionfunc(self,e):
        print >>sys.stderr,"TriblerLaunchmany: exceptfunc called",e
