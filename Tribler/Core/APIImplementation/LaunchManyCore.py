# Written by Arno Bakker 
# see LICENSE.txt for license information

import sys
import os
import time
import copy
import sha
import pickle
import socket
import binascii
import shutil
from UserDict import DictMixin
from threading import RLock,Condition,Event,Thread,currentThread
from traceback import print_exc,print_stack
from types import StringType

from Tribler.Core.BitTornado.__init__ import createPeerID
from Tribler.Core.BitTornado.bencode import bencode,bdecode
from Tribler.Core.BitTornado.download_bt1 import BT1Download
from Tribler.Core.BitTornado.RawServer import RawServer
from Tribler.Core.BitTornado.ServerPortHandler import MultiHandler
from Tribler.Core.BitTornado.BT1.track import Tracker
from Tribler.Core.BitTornado.HTTPHandler import HTTPHandler,DummyHTTPHandler


from Tribler.Core.simpledefs import *
from Tribler.Core.exceptions import *
from Tribler.Core.Download import Download
from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.APIImplementation.SingleDownload import SingleDownload
from Tribler.Core.NATFirewall.guessip import get_my_wan_ip
from Tribler.Core.NATFirewall.UPnPThread import UPnPThread
from Tribler.Core.Overlay.SecureOverlay import SecureOverlay
from Tribler.Core.Overlay.OverlayThreadingBridge import OverlayThreadingBridge
from Tribler.Core.Overlay.OverlayApps import OverlayApps
from Tribler.Core.NATFirewall.DialbackMsgHandler import DialbackMsgHandler
from Tribler.Core.DecentralizedTracking import mainlineDHT
from Tribler.Core.DecentralizedTracking.rsconvert import RawServerConverter
from Tribler.Core.DecentralizedTracking.mainlineDHTChecker import mainlineDHTChecker
from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB
from Tribler.Core.CacheDB.MugshotManager import MugshotManager
from Tribler.Video.utils import win32_retrieve_video_play_command


from Tribler.Core.CacheDB.CacheDBHandler import *
import Tribler.Core.CacheDB.cachedb as cachedb
from Tribler.Core.Utilities.utilities import show_permid_short
from Tribler.Core.RequestPolicy import *
from Tribler.TrackerChecking.TorrentChecking import TorrentChecking
from Tribler.Core.osutils import fix_filebasename

SPECIAL_VALUE=481

DEBUG = True

# Internal classes
#

class TriblerLaunchMany(Thread):
    
    def __init__(self,session,sesslock):
        """ Called only once (unless we have multiple Sessions) by MainThread """
        Thread.__init__(self)
        self.setDaemon(True)
        self.setName("Network"+self.getName())
        
        self.session = session
        self.sesslock = sesslock
        
        self.downloads = {} 
        config = session.sessconfig # Should be safe at startup

        self.locally_guessed_ext_ip = self.guess_ext_ip_from_local_info()
        self.upnp_ext_ip = None
        self.dialback_ext_ip = None

        # Orig
        self.sessdoneflag = Event()
        
        # Following two attributes set/get by network thread ONLY
        self.hashcheck_queue = []
        self.sdownloadtohashcheck = None
        
        # Following 2 attributes set/get by UPnPThread
        self.upnp_thread = None
        self.upnp_type = config['upnp_nat_access']


        self.rawserver = RawServer(self.sessdoneflag,
                                   config['timeout_check_interval'],
                                   config['timeout'],
                                   ipv6_enable = config['ipv6_enabled'],
                                   failfunc = self.rawserver_fatalerrorfunc,
                                   errorfunc = self.rawserver_nonfatalerrorfunc)
        self.rawserver.add_task(self.rawserver_keepalive,1)
        
        self.listen_port = self.rawserver.find_and_bind(0, 
                    config['minport'], config['maxport'], config['bind'], 
                    reuse = True,
                    ipv6_socket_style = config['ipv6_binds_v4'], 
                    randomizer = config['random_port'])
        
        if DEBUG:
            print >>sys.stderr,"tlm: Got listen port", self.listen_port
        
        self.multihandler = MultiHandler(self.rawserver, self.sessdoneflag)
        #
        # Arno: disabling out startup of torrents, need to fix this
        # to let text-mode work again.
        #
         
        # do_cache -> do_overlay -> (do_buddycast, do_download_help)
        if config['megacache']:
            # init cache db
            if config['nickname'] == '__default_name__':
                config['nickname']  = socket.gethostname()
                
            if DEBUG:
                print >>sys.stderr,'tlm: Reading Session state from',config['state_dir']
            cachedb.init(config, self.rawserver_fatalerrorfunc)

            self.peer_db        = PeerDBHandler.getInstance()
            self.torrent_db     = TorrentDBHandler.getInstance()
            self.mypref_db      = MyPreferenceDBHandler.getInstance()
            self.pref_db        = PreferenceDBHandler.getInstance()
            self.superpeer_db   = SuperPeerDBHandler.getInstance()
            self.superpeer_db.loadSuperPeers(config)
            self.friend_db      = FriendDBHandler.getInstance()
            self.bartercast_db  = BarterCastDBHandler.getInstance(self.session)
            
            
            #self.mm = MugshotManager.getInstance()
            #self.mm.register(config)
            #self.peer_db.setMugshotManager(self.mm)
        else:
            config['overlay'] = 0    # turn overlay off
            config['torrent_checking'] = 0
            self.peer_db        = None
            self.torrent_db     = None
            self.mypref_db      = None
            self.pref_db        = None
            self.superpeer_db   = None
            self.friend_db      = None
            self.bartercast_db  = None
            self.mm = None
        
        if not config['overlay']:
            config['buddycast'] = 0
            config['download_help'] = 0
            config['socnet'] = 0
            config['rquery'] = 0
            
        if config['overlay']:
            self.secure_overlay = SecureOverlay.getInstance()
            self.secure_overlay.register(self, config['overlay_max_message_length'])
            
            # Set policy for which peer requests (dl_helper, rquery) to answer and which to ignore
                        
            self.overlay_apps = OverlayApps.getInstance()
            policy = FriendsCoopDLOtherRQueryQuotumAllowAllRequestPolicy(self.session)
            
            # For the new DB layer we need to run all overlay apps in a
            # separate thread instead of the NetworkThread as before.
            self.overlay_bridge = OverlayThreadingBridge.getInstance()
            self.overlay_bridge.register_bridge(self.secure_overlay,self.overlay_apps)
            #self.overlay_bridge.add_task(self.overlay_bridge.periodic_commit, 5)
            
            self.overlay_apps.register(self.overlay_bridge,self.session,self,config,policy)
            # It's important we don't start listening to the network until
            # all higher protocol-handling layers are properly configured.
            self.overlay_bridge.start_listening()
        
        self.internaltracker = None
        if config['internaltracker']:
            self.internaltracker = Tracker(config, self.rawserver)
            self.httphandler = HTTPHandler(self.internaltracker.get, config['tracker_min_time_between_log_flushes'])
        else:
            self.httphandler = DummyHTTPHandler()
        self.multihandler.set_httphandler(self.httphandler)
        
        
        # Start up mainline DHT
        # Arno: do this in a try block, as khashmir gives a very funky
        # error when started from a .dmg (not from cmd line) on Mac. In particular
        # it complains that it cannot find the 'hex' encoding method when
        # hstr.encode('hex') is called, and hstr is a string?!
        #
        try:
            rsconvert = RawServerConverter(self.rawserver)
            # '' = host, TODO: when local bind set
            mainlineDHT.init('',self.listen_port,config['state_dir'],rawserver=rsconvert)

            # Create torrent-liveliness checker based on DHT
            c = mainlineDHTChecker.getInstance()
            c.register(mainlineDHT.dht)
        except:
            print_exc()
        
        
        # add task for tracker checking
        #if config['torrent_checking']:
        #    self.torrent_checking_period = config['torrent_checking_period']
        #    self.rawserver.add_task(self.run_torrent_check, self.torrent_checking_period)
        

    def add(self,tdef,dscfg,pstate=None,initialdlstatus=None):
        """ Called by any thread """
        self.sesslock.acquire()
        try:
            if not tdef.is_finalized():
                raise ValueError("TorrentDef not finalized")
            
            d = Download(self.session,tdef)
            infohash = d.get_def().get_infohash() 
            
            # Check if running or saved on disk
            if infohash in self.downloads:
                raise DuplicateDownloadException()
            elif pstate is None: # not already resuming
                pstate = self.load_download_pstate_noexc(infohash)
                if pstate is not None:
                    if DEBUG:
                        print >>sys.stderr,"tlm: add: pstate is",dlstatus_strings[pstate['dlstate']['status']],pstate['dlstate']['progress']
                    pass
            
            # Store in list of Downloads, always. 
            self.downloads[d.get_def().get_infohash()] = d
            d.setup(dscfg,pstate,initialdlstatus,self.network_engine_wrapper_created_callback,self.network_vod_playable_callback)
            
            def add_torrent_to_db():
                if self.torrent_db != None and self.mypref_db != None:
                    raw_filename = tdef.get_name_as_unicode()
                    torrent_dir = self.session.sessconfig['torrent_collecting_dir']
                    infohash = tdef.get_infohash()
                    hex_infohash = binascii.hexlify(infohash)
                    suffix = '__' + hex_infohash + '.torrent'
                    save_name = fix_filebasename(raw_filename, maxlen=255-len(suffix)) + suffix
                    save_path = os.path.join(torrent_dir, save_name)
                    if not os.path.exists(save_path):
                        tdef.save(save_path)
                    self.torrent_db.addExternalTorrent(save_path, '')
                    dest_path = d.get_dest_dir()    
                    # TODO: if user renamed the dest_path for single-file-torrent
                    data = {'destination_path':dest_path}
                    self.mypref_db.addMyPreference(infohash, data)

            self.overlay_bridge.add_task(add_torrent_to_db, 3)
            
            return d
        finally:
            self.sesslock.release()


    def network_engine_wrapper_created_callback(self,d,sd,exc,pstate):
        """ Called by network thread """
        if exc is None:
            # Always need to call the hashcheck func, even if we're restarting
            # a download that was seeding, this is just how the BT engine works.
            # We've provided the BT engine with its resumedata, so this should
            # be fast.
            #
            try:
                if sd is not None:
                    self.queue_for_hashcheck(sd)
                    if pstate is None and not d.get_def().get_live():
                        # Checkpoint at startup
                        (infohash,pstate) = d.network_checkpoint()
                        self.save_download_pstate(infohash,pstate)
                else:
                    raise TriblerException("tlm: network_engine_wrapper_created_callback: sd is None!")
            except Exception,e:
                # There was a bug in queue_for_hashcheck that is now fixed.
                # Leave this in place to catch unexpected errors.
                print_exc()
                d.set_error(e)
                
        
    def remove(self,d,removecontent=False):
        """ Called by any thread """
        self.sesslock.acquire()
        try:
            d.stop_remove(removestate=True,removecontent=removecontent)
            del self.downloads[d.get_def().get_infohash()]
        finally:
            self.sesslock.release()

    def get_downloads(self):
        """ Called by any thread """
        self.sesslock.acquire()
        try:
            return self.downloads.values() #copy, is mutable
        finally:
            self.sesslock.release()
    
    def rawserver_fatalerrorfunc(self,e):
        """ Called by network thread """
        if DEBUG:
            print >>sys.stderr,"TriblerLaunchMany: RawServer fatal error func called",e
        print_exc()

    def rawserver_nonfatalerrorfunc(self,e):
        """ Called by network thread """
        if DEBUG:
            print >>sys.stderr,"TriblerLaunchmany: RawServer non fatal error func called",e
            print_exc()
        # Could log this somewhere, or phase it out

    def run(self):
        """ Called only once by network thread """
        try:
            try:
                self.start_upnp()
                self.multihandler.listen_forever()
            except:
                print_exc()    
        finally:
            if self.internaltracker is not None:
                self.internaltracker.save_state()
            
            self.stop_upnp()
            self.rawserver.shutdown()

    def rawserver_keepalive(self):
        """ Hack to prevent rawserver sleeping in select() for a long time, not
        processing any tasks on its queue at startup time 
        
        Called by network thread """
        self.rawserver.add_task(self.rawserver_keepalive,1)

    #
    # TODO: called by TorrentMaker when new torrent added to itracker dir
    # Make it such that when Session.add_torrent() is called and the internal
    # tracker is used that we write a metainfo to itracker dir and call this.
    #
    def tracker_rescan_dir(self):
        if self.internaltracker is not None:
            self.internaltracker.parse_allowed(source='Session')

    #
    # Torrent hash checking
    #
    def queue_for_hashcheck(self,sd):
        """ Schedule a SingleDownload for integrity check of on-disk data
        
        Called by network thread """
        if hash:
            self.hashcheck_queue.append(sd)
            # Check smallest torrents first
            self.hashcheck_queue.sort(singledownload_size_cmp)
            
        if not self.sdownloadtohashcheck:
            self.dequeue_and_start_hashcheck()

    def dequeue_and_start_hashcheck(self):
        """ Start integriy check for first SingleDownload in queue
        
        Called by network thread """
        self.sdownloadtohashcheck = self.hashcheck_queue.pop(0)
        self.sdownloadtohashcheck.perform_hashcheck(self.hashcheck_done)

    def hashcheck_done(self):
        """ Integrity check for first SingleDownload in queue done
        
        Called by network thread """
        self.sdownloadtohashcheck.hashcheck_done()
        if self.hashcheck_queue:
            self.dequeue_and_start_hashcheck()
        else:
            self.sdownloadtohashcheck = None


    #
    # State retrieval
    #
    def set_download_states_callback(self,usercallback,getpeerlist,when=0.0):
        """ Called by any thread """
        network_set_download_states_callback_lambda = lambda:self.network_set_download_states_callback(usercallback,getpeerlist)
        self.rawserver.add_task(network_set_download_states_callback_lambda,when)
        
    def network_set_download_states_callback(self,usercallback,getpeerlist):
        """ Called by network thread """
        self.sesslock.acquire()
        try:
            # Even if the list of Downloads changes in the mean time this is
            # no problem. For removals, dllist will still hold a pointer to the
            # Download, and additions are no problem (just won't be included 
            # in list of states returned via callback.
            #
            dllist = self.downloads.values()
        finally:
            self.sesslock.release()

        dslist = []
        for d in dllist:
            ds = d.network_get_state(None,getpeerlist,sessioncalling=True)
            dslist.append(ds)
            
        # Invoke the usercallback function via a new thread.
        # After the callback is invoked, the return values will be passed to
        # the returncallback for post-callback processing.
        self.session.uch.perform_getstate_usercallback(usercallback,dslist,self.sesscb_set_download_states_returncallback)
        
    def sesscb_set_download_states_returncallback(self,usercallback,when,newgetpeerlist):
        """ Called by SessionCallbackThread """
        if when > 0.0:
            # reschedule
            self.set_download_states_callback(usercallback,newgetpeerlist,when=when)

    #
    # Persistence methods
    #
    def load_checkpoint(self,initialdlstatus=None):
        """ Called by any thread """
        self.sesslock.acquire()
        try:
            dir = self.session.get_downloads_pstate_dir()
            filelist = os.listdir(dir)
            for basename in filelist:
                # Make this go on when a torrent fails to start
                filename = os.path.join(dir,basename)
                self.resume_download(filename,initialdlstatus)
        finally:
            self.sesslock.release()


    def load_download_pstate_noexc(self,infohash):
        """ Called by any thread, assume sesslock already held """
        try:
            dir = self.session.get_downloads_pstate_dir()
            basename = binascii.hexlify(infohash)+'.pickle'
            filename = os.path.join(dir,basename)
            return self.load_download_pstate(filename)
        except Exception,e:
            # TODO: remove saved checkpoint?
            #self.rawserver_nonfatalerrorfunc(e)
            return None
        
    def resume_download(self,filename,initialdlstatus=None):
        try:
            # TODO: filter for file not found explicitly?
            pstate = self.load_download_pstate(filename)
            
            if DEBUG:
                print >>sys.stderr,"tlm: load_checkpoint: pstate is",dlstatus_strings[pstate['dlstate']['status']],pstate['dlstate']['progress']
                if pstate['engineresumedata'] is None:
                    print >>sys.stderr,"tlm: load_checkpoint: resumedata None"
                else:
                    print >>sys.stderr,"tlm: load_checkpoint: resumedata",len(pstate['engineresumedata'])
            
            tdef = TorrentDef.load_from_dict(pstate['metainfo'])
            
            # Activate
            dscfg = DownloadStartupConfig(dlconfig=pstate['dlconfig'])
            self.add(tdef,dscfg,pstate,initialdlstatus)
        except Exception,e:
            # TODO: remove saved checkpoint?
            self.rawserver_nonfatalerrorfunc(e)

    
    def checkpoint(self,stop=False):
        """ Called by any thread, assume sesslock already held """
        # Even if the list of Downloads changes in the mean time this is
        # no problem. For removals, dllist will still hold a pointer to the
        # Download, and additions are no problem (just won't be included 
        # in list of states returned via callback.
        #
        dllist = self.downloads.values()
        if DEBUG:
            print >>sys.stderr,"tlm: checkpointing",len(dllist)
        
        network_checkpoint_callback_lambda = lambda:self.network_checkpoint_callback(dllist,stop)
        self.rawserver.add_task(network_checkpoint_callback_lambda,0.0)

        
    def network_checkpoint_callback(self,dllist,stop):
        """ Called by network thread """
        psdict = {}
        for d in dllist:
            # Tell all downloads to stop, and save their persistent state
            # in a infohash -> pstate dict which is then passed to the user
            # for storage.
            #
            if DEBUG:
                print >>sys.stderr,"tlm: network checkpointing:",`d.get_def().get_name()`
            if stop:
                (infohash,pstate) = d.network_stop(False,False)
            else:
                (infohash,pstate) = d.network_checkpoint()
            psdict[infohash] = pstate

        try:
            for infohash,pstate in psdict.iteritems():
                self.save_download_pstate(infohash,pstate)
        except Exception,e:
            self.rawserver_nonfatalerrorfunc(e)

        if stop:
            self.shutdown()
            
    def shutdown(self):
        
        # Detect if megacache is enabled
        if self.peer_db is not None:
            db = SQLiteCacheDB.getInstance()
            db.commit()
        
        mainlineDHT.deinit()
        # Stop network thread
        self.sessdoneflag.set()

    def save_download_pstate(self,infohash,pstate):
        """ Called by network thread """
        basename = binascii.hexlify(infohash)+'.pickle'
        filename = os.path.join(self.session.get_downloads_pstate_dir(),basename)
        
        if DEBUG:
            print >>sys.stderr,"tlm: network checkpointing: to file",filename
        f = open(filename,"wb")
        pickle.dump(pstate,f)
        f.close()


    def load_download_pstate(self,filename):
        """ Called by any thread """
        f = open(filename,"rb")
        pstate = pickle.load(f)
        f.close()
        return pstate

    #
    # External IP address methods
    #
    def guess_ext_ip_from_local_info(self):
        """ Called at creation time """
        ip = get_my_wan_ip()
        if ip is None:
            host = socket.gethostbyname_ex(socket.gethostname())
            ipaddrlist = host[2]
            for ip in ipaddrlist:
                return ip
            return '127.0.0.1'
        else:
            return ip


    def start_upnp(self):
        """ Arno: as the UPnP discovery and calls to the firewall can be slow,
        do it in a separate thread. When it fails, it should report popup
        a dialog to inform and help the user. Or report an error in textmode.
        
        Must save type here, to handle case where user changes the type
        In that case we still need to delete the port mapping using the old mechanism
        
        Called by network thread """ 
        
        if DEBUG:
            print >>sys.stderr,"tlm: start_upnp()"
        self.set_activity(NTFY_ACT_UPNP)
        self.upnp_thread = UPnPThread(self.upnp_type,self.locally_guessed_ext_ip,self.listen_port,self.upnp_failed_callback,self.upnp_got_ext_ip_callback)
        self.upnp_thread.start()

    def stop_upnp(self):
        """ Called by network thread """
        if self.upnp_type > 0:
            self.upnp_thread.shutdown()

    def upnp_failed_callback(self,upnp_type,listenport,error_type,exc=None,listenproto='TCP'):
        """ Called by UPnP thread TODO: determine how to pass to API user 
            In principle this is a non fatal error. But it is one we wish to
            show to the user """
        print >>sys.stderr,"UPnP mode "+str(upnp_type)+" request to firewall failed with error "+str(error_type)+" Try setting a different mode in Preferences. Listen port was "+str(listenport)+", protocol"+listenproto

    def upnp_got_ext_ip_callback(self,ip):
        """ Called by UPnP thread """
        self.sesslock.acquire()
        self.upnp_ext_ip = ip
        self.sesslock.release()

    def dialback_got_ext_ip_callback(self,ip):
        """ Called by network thread """
        self.sesslock.acquire()
        self.dialback_ext_ip = ip
        self.sesslock.release()

    def get_ext_ip(self):
        """ Called by any thread """
        self.sesslock.acquire()
        try:
            if self.dialback_ext_ip is not None: # best
                return self.dialback_ext_ip # string immutable
            elif self.upnp_ext_ip is not None: # good
                return self.upnp_ext_ip 
            else: # slighly wild guess
                return self.locally_guessed_ext_ip
        finally:
            self.sesslock.release()

    #
    # Events from core meant for API user
    #
    def dialback_reachable_callback(self):
        """ Called by overlay+network thread """
        self.session.uch.notify(NTFY_REACHABLE, NTFY_INSERT, None, '')
        
        
    def set_activity(self,type, str = ''):
        """ Called by overlay + network thread """
        #print >>sys.stderr,"tlm: set_activity",type,str
        self.session.uch.notify(NTFY_ACTIVITIES, NTFY_INSERT, type, str)

        
    def network_vod_playable_callback(self,videoinfo,complete,mimetype,stream):
        """ Called by network thread """
        
        if mimetype is None:
            if sys.platform == 'win32':
                try:
                    file = videoinfo['inpath']
                    (prefix,ext) = os.path.splitext(file)
                    ext = ext.lower()
                    (mimetype,playercmd) = win32_retrieve_video_play_command(ext,'')
                except:
                    print_exc()
                    mimetype = 'video/mpeg'
            else:
                mimetype = 'video/mpeg'

        if complete:
            if DEBUG:
                print >>sys.stderr,"tlm: network_vod_playable_callback: PiecePicker says complete, give filename"
            filename = videoinfo['outpath']
        else:
            if DEBUG:
                print >>sys.stderr,"tlm: network_vod_playable_callback: PiecePiecker says incomplete, give stream"
            filename = None
        
        # Call Session threadpool to call user's callback        
        videoinfo['usercallback'](mimetype,stream,filename)

    def run_torrent_check(self):
        """ Called by network thread """
        self.rawserver.add_task(self.run_torrent_check, self.torrent_checking_period)
        #        print "torrent_checking start"
        try:
            t = TorrentChecking()        
            t.start()
        except Exception, e:
            self.rawserver_nonfatalerrorfunc(e)

    def get_coopdl_role_object(self,infohash,role):
        """ Called by network thread """
        role_object = None
        self.sesslock.acquire()
        try:
            if infohash in self.downloads:
                d = self.downloads[infohash]
                role_object = d.get_coopdl_role_object(role)
        finally:
            self.sesslock.release()
        return role_object

        
    def h4xor_reset_init_conn_counter(self):
        self.rawserver.add_task(self.network_h4xor_reset,0)
        
    def network_h4xor_reset(self):
        from Tribler.Core.BitTornado.BT1.Encrypter import incompletecounter
        print >>sys.stderr,"tlm: h4x0r Resetting outgoing TCP connection rate limiter",incompletecounter.c,"==="
        incompletecounter.c = 0


        
        
def singledownload_size_cmp(x,y):
    """ Method that compares 2 SingleDownload objects based on the size of the
        content of the BT1Download (if any) contained in them. 
    """
    if x is None and y is None:
        return 0
    elif x is None:
        return 1
    elif y is None:
        return -1
    else:
        a = x.get_bt1download()
        b = y.get_bt1download()
        if a is None and b is None:
            return 0
        elif a is None:
            return 1
        elif b is None:
            return -1
        else:
            if a.get_datalength() == b.get_datalength():
                return 0
            elif a.get_datalength() < b.get_datalength():
                return -1
            else:
                return 1

