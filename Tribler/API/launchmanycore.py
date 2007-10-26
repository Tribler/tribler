# Written by Arno Bakker 
# see LICENSE.txt for license information

import sys
import os
import time
import copy
import sha
import socket
import pickle
import binascii
import shutil
from UserDict import DictMixin
from threading import RLock,Condition,Event,Thread,currentThread
from traceback import print_exc,print_stack
from types import StringType

from BitTornado.__init__ import createPeerID
from BitTornado.bencode import bencode,bdecode
from BitTornado.download_bt1 import BT1Download
from BitTornado.RawServer import RawServer
from BitTornado.ServerPortHandler import MultiHandler
from BitTornado.RateLimiter import RateLimiter
from BitTornado.BT1.track import Tracker
from BitTornado.HTTPHandler import HTTPHandler,DummyHTTPHandler

import triblerAPI
from Tribler.NATFirewall.guessip import get_my_wan_ip
from Tribler.NATFirewall.UPnPThread import UPnPThread
from Tribler.Overlay.SecureOverlay import SecureOverlay
from Tribler.Overlay.OverlayApps import OverlayApps
from Tribler.NATFirewall.DialbackMsgHandler import DialbackMsgHandler
from Tribler.DecentralizedTracking import mainlineDHT
from Tribler.DecentralizedTracking.rsconvert import RawServerConverter
from Tribler.API.defaults import *

# TEMP
from Tribler.Dialogs.activities import *

SPECIAL_VALUE=481

DEBUG = True

#
# Internal classes
#

class TriblerLaunchMany(Thread):
    
    def __init__(self,session,sesslock):
        """ Called only once (unless we have multiple Sessions) """
        Thread.__init__(self)
        ##self.setDaemon(True) 
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
        
        # Following two attributes set/get by network thread
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
        print "Got listen port", self.listen_port
        
        self.multihandler = MultiHandler(self.rawserver, self.sessdoneflag)
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
            mykeypair = session.keypair
            self.secure_overlay.register(self.rawserver,self.multihandler,self.listen_port,self.config['max_message_length'],mykeypair)
            self.overlay_apps = OverlayApps.getInstance()
            self.overlay_apps.register(self.secure_overlay, self, self.rawserver, config)
            # It's important we don't start listening to the network until
            # all higher protocol-handling layers are properly configured.
            self.secure_overlay.start_listening()
        
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
        except:
            print_exc()
        
        
        # APITODO
        #self.torrent_db = TorrentDBHandler()
        #self.mypref_db = MyPreferenceDBHandler()
        
        # add task for tracker checking
        if not config['torrent_checking']:
            self.rawserver.add_task(self.torrent_checking, self.torrent_checking_period)
        

    def add(self,tdef,dscfg,pstate=None):
        """ Called by any thread """
        self.sesslock.acquire()
        try:
            d = triblerAPI.Download(self.session,tdef)
            infohash = d.get_def().get_infohash() 
            
            # Check if running or saved on disk
            if infohash in self.downloads:
                raise DuplicateDownloadException()
            elif pstate is None: # not already resuming
                pstate = self.load_download_pstate_noexc(infohash)
                if pstate is not None:
                    print >>sys.stderr,"tlm: add: pstate is",dlstatus_strings[pstate['dlstate']['status']],pstate['dlstate']['progress']
                    # Override saved DownloadStartupConfig, just in case
                    pstate['dscfg'] = dscfg
            
            # Store in list of Downloads, always. 
            self.downloads[d.get_def().get_infohash()] = d
            d.setup(dscfg,pstate,self.network_engine_wrapper_created_callback,self.network_vod_playable_callback)
            return d
        finally:
            self.sesslock.release()


    def network_engine_wrapper_created_callback(self,d,sd,exc,pstate):
        """ Called by network thread """
        if exc is None:
            # Always need to call the hashcheck func, even if we're restarting
            # a download that was seeding, this is just how the BT engine works
            # We've provided the BT engine with its resumedata, so this should
            # be fast.
            #
            self.queue_for_hashcheck(sd)
            if pstate is None:
                # Checkpoint at startup
                (infohash,pstate) = d.network_checkpoint()
                self.save_download_pstate(infohash,pstate)
        
    def remove(self,d,removecontent=False):
        """ Called by any thread """
        self.sesslock.acquire()
        try:
            d.stop_remove(removestate=True,removecontent=removecontent)
            del self.downloads.remove[d.get_def().get_infohash()]
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
        print_exc

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
            self.internaltracker.parse_allowed(source='TorrentMaker')

    def set_activity(self,type):
        pass # TODO Jelle

    #
    # Torrent hash checking
    #
    def queue_for_hashcheck(self,sd):
        """ Schedule a SingleDownload for integrity check of on-disk data
        
        Called by network thread """
        if hash:
            self.hashcheck_queue.append(sd)
            # Check smallest torrents first
            self.hashcheck_queue.sort(lambda x, y: cmp(self.downloads[x].dow.datalength, self.downloads[y].dow.datalength))
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
        self.session.perform_getstate_usercallback(usercallback,dslist,self.sesscb_set_download_states_returncallback)
        
    def sesscb_set_download_states_returncallback(self,usercallback,when,newgetpeerlist):
        """ Called by SessionCallbackThread """
        if when > 0.0:
            # reschedule
            self.set_download_states_callback(usercallback,newgetpeerlist,when=when)

    #
    # Persistence methods
    #
    def load_checkpoint(self):
        """ Called by any thread """
        self.sesslock.acquire()
        try:
            dir = self.session.get_downloads_pstate_dir()
            filelist = os.listdir(dir)
            for basename in filelist:
                # Make this go on when a torrent fails to start
                filename = os.path.join(dir,basename)
                self.resume_download(filename)
        finally:
            self.sesslock.releas()


    def load_download_pstate_noexc(self,infohash):
        """ Called by any thread, assume sesslock already held """
        try:
            dir = self.session.get_downloads_pstate_dir()
            basename = binascii.hexlify(infohash)+'.pickle'
            filename = os.path.join(dir,basename)
            return self.load_download_pstate(filename)
        except Exception,e:
            # TODO: remove saved checkpoint?
            self.rawserver_nonfatalerrorfunc(e)
            return None
        
    def resume_download(self,filename):
        try:
            # TODO: filter for file not found explicitly?
            pstate = self.load_download_pstate(filename)
            
            print >>sys.stderr,"tlm: load_checkpoint: pstate is",dlstatus_strings[pstate['dlstate']['status']],pstate['dlstate']['progress']
            tdef = triblerAPI.TorrentDef._create(pstate['metainfo'])
            
            # Activate
            self.add(tdef,pstate['dscfg'],pstate)
        except Exception,e:
            # TODO: remove saved checkpoint?
            self.rawserver_nonfatalerrorfunc(e)

    
    def checkpoint(self,stop=False):
        """ Called by any thread """
        self.sesslock.acquire()
        try:
            # Even if the list of Downloads changes in the mean time this is
            # no problem. For removals, dllist will still hold a pointer to the
            # Download, and additions are no problem (just won't be included 
            # in list of states returned via callback.
            #
            dllist = self.downloads.values()
            print >>sys.stderr,"tlm: checkpointing",len(dllist)
            
            network_checkpoint_callback_lambda = lambda:self.network_checkpoint_callback(dllist,stop)
            self.rawserver.add_task(network_checkpoint_callback_lambda,0.0)
        finally:
            self.sesslock.release()
        
    def network_checkpoint_callback(self,dllist,stop):
        """ Called by network thread """
        psdict = {'version':PERSISTENTSTATE_CURRENTVERSION}
        for d in dllist:
            # Tell all downloads to stop, and save their persistent state
            # in a infohash -> pstate dict which is then passed to the user
            # for storage.
            #
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
        mainlineDHT.deinit()
        # Stop network thread
        self.sessdoneflag.set()


    def save_download_pstate(self,infohash,pstate):
        """ Called by network thread """
        basename = binascii.hexlify(infohash)+'.pickle'
        filename = os.path.join(self.session.get_downloads_pstate_dir(),basename)
        
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
        
        print >>sys.stderr,"tlm: start_upnp()"
        self.set_activity(ACT_UPNP)
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

        
    def network_vod_playable_callback(self,videoinfo,complete,mimetype,stream):
        """ Called by network thread """
        
        if mimetype is None:
            if sys.platform == 'win32':
                try:
                    file = videoinfo[1]
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
                print >>sys.stderr,"tlm: vod_playable: PiecePicker says complete, give filename"
            filename = videoinfo[3]
        else:
            if DEBUG:
                print >>sys.stderr,"vod: vod_playable: PiecePiecker says incomplete, give stream"
            filename = None
        
        # Call Session threadpool to call user's callback        
        videoinfo[4](mimetype,stream,filename)




class SingleDownload:
    """ This class is accessed solely by the network thread """
    
    def __init__(self,infohash,metainfo,kvconfig,multihandler,listenport,videoanalyserpath,vodfileindex,set_error_func,pstate,lmvodplayablecallback):
        
        self.dow = None
        self.set_error_func = set_error_func
        try:
            self.dldoneflag = Event()
            
            self.dlrawserver = multihandler.newRawServer(infohash,self.dldoneflag)
            self.lmvodplayablecallback = lmvodplayablecallback
    
            """
            class BT1Download:    
                def __init__(self, statusfunc, finfunc, errorfunc, excfunc, doneflag, 
                     config, response, infohash, id, rawserver, port, play_video,
                     videoinfo, progressinf, videoanalyserpath, appdataobj = None, dht = None):
            """
            self.dow = BT1Download(self.hashcheckprogressfunc,
                            self.finishedfunc,
                            self.fatalerrorfunc, 
                            self.nonfatalerrorfunc,
                            self.dldoneflag,
                            kvconfig,
                            metainfo, 
                            infohash,
                            createPeerID(),
                            self.dlrawserver,
                            listenport,
                            videoanalyserpath
                            )
        
            file = self.dow.saveAs(self.save_as)
            
            # Set local filename in vodfileindex
            if vodfileindex is not None:
                index = vodfileindex[0]
                if index == -1:
                    index = 0
                vodfileindex[3] = self.dow.get_dest(index)
            self.dow.set_videoinfo(vodfileindex)

            print >>sys.stderr,"SingleDownload: setting vodfileindex",vodfileindex
            
            self._hashcheckfunc = None
            if pstate is None:
                resumedata = None
            else:
                # Restarting download
                resumedata=pstate['engineresumedata']
            self._hashcheckfunc = self.dow.initFiles(resumedata=resumedata)
            self._getstatsfunc = None
            if pstate is not None:
                self.hashcheckfrac = pstate['dlstate']['progress']
            else:
                self.hashcheckfrac = 0.0
            
        except Exception,e:
            self.fatalerrorfunc(e)
    
    
    def save_as(self,name,length,saveas,isdir):
        """ Return the local filename to which to save the file 'name' in the torrent """
        print >>sys.stderr,"SingleDownload: save_as(",name,length,saveas,isdir,")"
        try:
            path = os.path.join(saveas,name)
            if isdir and not os.path.isdir(path):
                os.mkdir(path)
            return path
        except Exception,e:
            self.fatalerrorfunc(e)

    def perform_hashcheck(self,complete_callback):
        """ Called by any thread """
        print >>sys.stderr,"SingleDownload: hashcheck()",self._hashcheckfunc
        try:
            """ Schedules actually hashcheck on network thread """
            self._getstatsfunc = SPECIAL_VALUE # signal we're hashchecking
            self._hashcheckfunc(complete_callback)
        except Exception,e:
            self.fatalerrorfunc(e)
            
    def hashcheck_done(self):
        """ Called by LaunchMany when hashcheck complete and the Download can be
            resumed
            
            Called by network thread
        """
        print >>sys.stderr,"SingleDownload: hashcheck_done()"
        try:
            self.dow.startEngine(vodplayablefunc = self.lmvodplayablecallback)
            self._getstatsfunc = self.dow.startStats() # not possible earlier
            self.dow.startRerequester()
            self.dlrawserver.start_listening(self.dow.getPortHandler())
        except Exception,e:
            self.fatalerrorfunc(e)


    # DownloadConfigInterface methods
    def set_max_speed(self,direct,speed,callback):
        if self.dow is not None:
            #print >>sys.stderr,"SingleDownload: set_max_speed",`self.dow.response['info']['name']`,direct,speed
            if direct == UPLOAD:
                self.dow.setUploadRate(speed)
            else:
                self.dow.setDownloadRate(speed)
        callback(direct,speed)


    def get_stats(self,getpeerlist):  
        if self._getstatsfunc is None:
            return (DLSTATUS_WAITING4HASHCHECK,None)
        elif self._getstatsfunc == SPECIAL_VALUE:
            stats = {}
            stats['frac'] = self.hashcheckfrac
            return (DLSTATUS_HASHCHECKING,stats)
        else:
            return (None,self._getstatsfunc(getpeerlist=getpeerlist))

    #
    #
    #
    def checkpoint(self):
        if self.dow is not None:
            return self.dow.checkpoint()
        else:
            return None
    
    def shutdown(self):
        resumedata = None
        if self.dow is not None:
            self.dldoneflag.set()
            self.dlrawserver.shutdown()
            resumedata = self.dow.shutdown()
            self.dow = None
        return resumedata

    #
    # Internal methods
    #
    def hashcheckprogressfunc(self,activity = '', fractionDone = 0.0):
        """ Allegedly only used by StorageWrapper during hashchecking """
        #print >>sys.stderr,"SingleDownload::statusfunc called",activity,fractionDone
        self.hashcheckfrac = fractionDone

    def finishedfunc(self):
        """ Download is complete """
        print >>sys.stderr,"SingleDownload::finishedfunc called *******************************"

    def fatalerrorfunc(self,data):
        print >>sys.stderr,"SingleDownload::fatalerrorfunc called",data
        if type(data) == StringType:
            print >>sys.stderr,"LEGACY CORE FATAL ERROR",data
            print_stack()
            self.set_error_func(TriblerLegacyException(data))
        else:
            print_exc()
            self.set_error_func(data)
        self.shutdown()

    def nonfatalerrorfunc(self,e):
        print >>sys.stderr,"SingleDownload::nonfatalerrorfunc called",e
        # Could log this somewhere, or phase it out (only used in Rerequester)
