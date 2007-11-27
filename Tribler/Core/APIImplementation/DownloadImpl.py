# Written by Arno Bakker 
# see LICENSE.txt for license information

import sys
import os
import copy
import binascii
from traceback import print_exc,print_stack
from threading import RLock,Condition,Event,Thread,currentThread

from Tribler.Core.DownloadState import DownloadState
from Tribler.Core.simpledefs import *
from Tribler.Core.osutils import *
from Tribler.Core.APIImplementation.SingleDownload import SingleDownload
from Tribler.Core.Utilities.unicode import metainfoname2unicode


DEBUG = True

class DownloadImpl:
    
    def __init__(self,session,tdef):
        self.dllock = RLock()
        # just enough so error saving and get_state() works
        self.error = None
        self.sd = None # hack
        # To be able to return the progress of a stopped torrent, how far it got.
        self.progressbeforestop = 0.0
        self.filepieceranges = []

        # Copy tdef, so we get an infohash
        self.session = session
        self.tdef = tdef.copy()
        self.tdef.readonly = True

    #
    # Creating a Download
    #
    def setup(self,dcfg=None,pstate=None,lmcreatedcallback=None,lmvodplayablecallback=None):
        """
        Create a Download object. Used internally by Session. Copies tdef and 
        dcfg and binds them to this download.
        
        in: 
        tdef = unbound TorrentDef
        dcfg = unbound DownloadStartupConfig or None (in which case 
        DownloadStartupConfig.get_copy_of_default() is called and the result 
        becomes the (bound) config of this Download.
        """
        try:
            self.dllock.acquire() # not really needed, no other threads know of it
            
            # See if internal tracker used
            itrackerurl = self.session.get_internal_tracker_url()
            infohash = self.tdef.get_infohash()
            metainfo = self.tdef.get_metainfo()
            usingitracker = False
            
            print >>sys.stderr,"Download: setup: internal tracker?",metainfo['announce'],itrackerurl,"#"

            if itrackerurl.endswith('/'):
                slashless = itrackerurl[:-1]
            else:
                slashless = itrackerurl
            if metainfo['announce'] == itrackerurl or metainfo['announce'] == slashless:
                usingitracker = True
            elif 'announce-list' in metainfo:
                for tier in metainfo['announce-list']:
                    if itrackerurl in tier or slashless in tier:
                         usingitracker = True
                         break
                     
            if usingitracker:
                print >>sys.stderr,"Download: setup: Using internal tracker"
                # Copy .torrent to state_dir/itracker so the tracker thread 
                # finds it and accepts peer registrations for it.
                # 
                trackerdir = self.session.get_internal_tracker_dir()
                basename = binascii.hexlify(infohash)+'.torrent' # ignore .tribe stuff, not vital
                filename = os.path.join(trackerdir,basename)
                self.tdef.save(filename)
                # Bring to attention of Tracker thread
                self.session.lm.tracker_rescan_dir()
            else:
                print >>sys.stderr,"Download: setup: Not using internal tracker"
            
            # Copy dlconfig, from default if not specified
            if dcfg is None:
                cdcfg = DownloadStartupConfig()
            else:
                cdcfg = dcfg
            self.dlconfig = copy.copy(cdcfg.dlconfig)
            # Copy sessconfig into dlconfig, such that BitTornado.BT1.Connecter, etc.
            # knows whether overlay is on, etc.
            #
            for (k,v) in self.session.get_current_startup_config_copy().sessconfig.iteritems():
                self.dlconfig.setdefault(k,v)
    
            self.set_filepieceranges()
    
            # Things that only exist at runtime
            self.dlruntimeconfig= {}
            # We want to remember the desired rates and the actual assigned quota
            # rates by the RateManager
            self.dlruntimeconfig['max_desired_upload_rate'] = self.dlconfig['max_upload_rate'] 
            self.dlruntimeconfig['max_desired_download_rate'] = self.dlconfig['max_download_rate']
    
    
            print >>sys.stderr,"Download: setup: get_max_desired",self.dlruntimeconfig['max_desired_upload_rate']

            if pstate is None or pstate['dlstate']['status'] != DLSTATUS_STOPPED:
                # Also restart on STOPPED_ON_ERROR, may have been transient
                self.create_engine_wrapper(lmcreatedcallback,pstate,lmvodplayablecallback)
                
            self.dllock.release()
        except Exception,e:
            print_exc()
            self.set_error(e)
            self.dllock.release()

    def create_engine_wrapper(self,lmcreatedcallback,pstate,lmvodplayablecallback):
        """ Called by any thread, assume dllock already acquired """
        if DEBUG:
            print >>sys.stderr,"Download: create_engine_wrapper()"
        
        # all thread safe
        infohash = self.get_def().get_infohash()
        metainfo = copy.deepcopy(self.get_def().get_metainfo())
        
        # H4xor this so the 'name' field is safe
        (namekey,uniname) = metainfoname2unicode(metainfo)
        self.correctedinfoname = fix_filebasename(uniname)
        metainfo['info'][namekey] = metainfo['info']['name'] = self.correctedinfoname 
        
        multihandler = self.session.lm.multihandler
        listenport = self.session.get_listen_port()
        vapath = self.session.get_video_analyser_path()

        # Note: BT1Download is started with copy of d.dlconfig, not direct access
        # Set IP to report to tracker. 
        self.dlconfig['ip'] = self.session.lm.get_ext_ip()
        kvconfig = copy.copy(self.dlconfig)

        # Define which file to DL in VOD mode
        if self.dlconfig['mode'] == DLMODE_VOD:
            vod_usercallback_wrapper = lambda mimetype,stream,filename:self.session.uch.perform_vod_usercallback(self,self.dlconfig['vod_usercallback'],mimetype,stream,filename)
            
            if 'files' in metainfo['info'] and len(self.dlconfig['selected_files']) == 0:
                # Multi-file torrent, but no file selected
                raise VODNoFileSelectedInMultifileTorrentException() 
            
            if len(self.dlconfig['selected_files']) == 0:
                # single-file torrent
                file = self.get_def().get_name()
                idx = -1
                bitrate = self.get_def().get_bitrate(None)
                live = self.get_def().get_live(None)
            else:
                # multi-file torrent
                file = self.dlconfig['selected_files'][0]
                idx = self.get_def().get_index_of_file_in_files(file)
                bitrate = self.get_def().get_bitrate(file)
                live = self.get_def().get_live(file)
            vodfileindex = {'index':idx,'inpath':file,'bitrate':bitrate,'live':live,'usercallback':vod_usercallback_wrapper}
        else:
            vodfileindex = {'index':-1,'inpath':None,'bitrate':0.0,'live':False,'usercallback':None}

        vodfileindex['outpath'] = None
        
        # Delegate creation of engine wrapper to network thread
        network_create_engine_wrapper_lambda = lambda:self.network_create_engine_wrapper(infohash,metainfo,kvconfig,multihandler,listenport,vapath,vodfileindex,lmcreatedcallback,pstate,lmvodplayablecallback)
        self.session.lm.rawserver.add_task(network_create_engine_wrapper_lambda,0) 
        

    def network_create_engine_wrapper(self,infohash,metainfo,kvconfig,multihandler,listenport,vapath,vodfileindex,lmcallback,pstate,lmvodplayablecallback):
        """ Called by network thread """
        self.dllock.acquire()
        try:
            self.sd = SingleDownload(infohash,metainfo,kvconfig,multihandler,listenport,vapath,vodfileindex,self.set_error,pstate,lmvodplayablecallback)
            sd = self.sd
            exc = self.error
            if lmcallback is not None:
                lmcallback(self,sd,exc,pstate)
        finally:
            self.dllock.release()

    #
    # Public method
    #
    def get_def(self):
        # No lock because attrib immutable and return value protected
        return self.tdef

    #
    # Retrieving DownloadState
    #
    def set_state_callback(self,usercallback,getpeerlist=False):
        """ Called by any thread """
        self.dllock.acquire()
        try:
            network_get_state_lambda = lambda:self.network_get_state(usercallback,getpeerlist)
            # First time on general rawserver
            self.session.lm.rawserver.add_task(network_get_state_lambda,0.0)
        finally:
            self.dllock.release()


    def network_get_state(self,usercallback,getpeerlist,sessioncalling=False):
        """ Called by network thread """
        self.dllock.acquire()
        try:
            if self.sd is None:
                ds = DownloadState(self,DLSTATUS_STOPPED,self.error,self.progressbeforestop)
            else:
                (status,stats,logmsgs) = self.sd.get_stats(getpeerlist)
                ds = DownloadState(self,status,self.error,None,stats=stats,filepieceranges=self.filepieceranges,logmsgs=logmsgs)
                self.progressbeforestop = ds.get_progress()
            
                #print >>sys.stderr,"STATS",stats
            
            if sessioncalling:
                return ds

            # Invoke the usercallback function via a new thread.
            # After the callback is invoked, the return values will be passed to
            # the returncallback for post-callback processing.
            self.session.uch.perform_getstate_usercallback(usercallback,ds,self.sesscb_get_state_returncallback)
        finally:
            self.dllock.release()


    def sesscb_get_state_returncallback(self,usercallback,when,newgetpeerlist):
        """ Called by SessionCallbackThread """
        self.dllock.acquire()
        try:
            if when > 0.0:
                # Schedule next invocation, either on general or DL specific
                # TODO: ensure this continues when dl is stopped. Should be OK.
                network_get_state_lambda = lambda:self.network_get_state(usercallback,newgetpeerlist)
                if self.sd is None:
                    self.session.lm.rawserver.add_task(network_get_state_lambda,when)
                else:
                    self.sd.dlrawserver.add_task(network_get_state_lambda,when)
        finally:
            self.dllock.release()

    #
    # Download stop/resume
    #
    def stop(self):
        """ Called by any thread """
        self.stop_remove(removestate=False,removecontent=False)

    def stop_remove(self,removestate=False,removecontent=False):
        self.dllock.acquire()
        try:
            if self.sd is not None:
                network_stop_lambda = lambda:self.network_stop(removestate,removecontent)
                self.session.lm.rawserver.add_task(network_stop_lambda,0.0)
            # No exception if already stopped, for convenience
        finally:
            self.dllock.release()

    def network_stop(self,removestate,removecontent):
        """ Called by network thread """
        self.dllock.acquire()
        try:
            infohash = self.tdef.get_infohash() 
            pstate = self.network_get_persistent_state() 
            pstate['engineresumedata'] = self.sd.shutdown()
            
            # Offload the removal of the content and other disk cleanup to another thread
            if removestate:
                self.session.uch.perform_removestate_callback(infohash,self.correctedinfoname,removecontent,self.dlconfig['saveas'])
            
            return (infohash,pstate)
        finally:
            self.dllock.release()

        
    def restart(self):
        """ Called by any thread """
        # Must schedule the hash check via lm. In some cases we have batch stops
        # and restarts, e.g. we have stop all-but-one & restart-all for VOD)
        self.dllock.acquire()
        try:
            if self.sd is None:
                self.error = None # assume fatal error is reproducible
                # TODO: if seeding don't re-hashcheck
                self.create_engine_wrapper(self.session.lm.network_engine_wrapper_created_callback,pstate=None)
            # No exception if already started, for convenience
        finally:
            self.dllock.release()

    #
    # Config parameters that only exists at runtime 
    #
    def set_max_desired_speed(self,direct,speed):
        print >>sys.stderr,"Download: set_max_desired_speed",direct,speed
        #if speed < 10:
        #    print_stack()
        
        self.dllock.acquire()
        if direct == UPLOAD:
            self.dlruntimeconfig['max_desired_upload_rate'] = speed
        else:
            self.dlruntimeconfig['max_desired_download_rate'] = speed
        self.dllock.release()

    def get_max_desired_speed(self,direct):
        self.dllock.acquire()
        try:
            if direct == UPLOAD:
                print >>sys.stderr,"Download: get_max_desired_speed: get_max_desired",self.dlruntimeconfig['max_desired_upload_rate']
                return self.dlruntimeconfig['max_desired_upload_rate']
            else:
                return self.dlruntimeconfig['max_desired_download_rate']
        finally:
            self.dllock.release()

    #
    # Persistence
    #
    def network_checkpoint(self):
        """ Called by network thread """
        self.dllock.acquire()
        try:
            pstate = self.network_get_persistent_state() 
            pstate['engineresumedata'] = self.sd.checkpoint()
            return (self.tdef.get_infohash(),pstate)
        finally:
            self.dllock.release()
        

    def network_get_persistent_state(self):
        """ Assume dllock already held """
        pstate = {}
        pstate['version'] = PERSISTENTSTATE_CURRENTVERSION
        pstate['metainfo'] = self.tdef.get_metainfo() # assumed immutable
        dlconfig = copy.copy(self.dlconfig)
        # Reset unpicklable params
        dlconfig['vod_usercallback'] = None
        dlconfig['dlmode'] = DLMODE_NORMAL # no callback, no VOD
        pstate['dlconfig'] = dlconfig

        pstate['dlstate'] = {}
        ds = self.network_get_state(None,False,sessioncalling=True)
        pstate['dlstate']['status'] = ds.get_status()
        pstate['dlstate']['progress'] = ds.get_progress()
        
        print >>sys.stderr,"Download: netw_get_pers_state: status",dlstatus_strings[ds.get_status()],"progress",ds.get_progress()
        
        pstate['engineresumedata'] = None
        return pstate

    #
    # Internal methods
    #
    def set_error(self,e):
        self.dllock.acquire()
        self.error = e
        self.dllock.release()


    def set_filepieceranges(self):
        """ Determine which file maps to which piece ranges for progress info """
        
        print >>sys.stderr,"Download: set_filepieceranges:",self.dlconfig['selected_files']
        
        if len(self.dlconfig['selected_files']) > 0:
            if 'files' not in self.tdef.metainfo['info']:
                raise ValueError("Selected more than 1 file, but torrent is single-file torrent")
            
            files = self.tdef.metainfo['info']['files']
            piecesize = self.tdef.metainfo['info']['piece length']
            
            total = 0L
            for i in xrange(len(files)):
                path = files[i]['path']
                length = files[i]['length']
                filename = pathlist2filename(path)
                
                print >>sys.stderr,"Download: set_filepieceranges: Torrent file",filename,"in",self.dlconfig['selected_files']

                if filename in self.dlconfig['selected_files'] and length > 0:
                    
                    range = (offset2piece(total,piecesize), offset2piece(total + length,piecesize),filename)
                    
                    print >>sys.stderr,"Download: set_filepieceranges: Torrent file range append",range
                    
                    self.filepieceranges.append(range)
                total += length
        else:
            self.filepieceranges = None 

