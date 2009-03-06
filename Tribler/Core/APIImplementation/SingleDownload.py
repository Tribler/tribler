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
from types import StringType,ListType,IntType
from traceback import print_exc,print_stack
from threading import Event

from Tribler.Core.simpledefs import *
from Tribler.Core.exceptions import *
from Tribler.Core.BitTornado.__init__ import createPeerID
from Tribler.Core.BitTornado.download_bt1 import BT1Download
from Tribler.Core.BitTornado.bencode import bencode,bdecode
from Tribler.Core.Video.VideoStatus import VideoStatus


SPECIAL_VALUE = 481

DEBUG = False

class SingleDownload:
    """ This class is accessed solely by the network thread """
    
    def __init__(self,infohash,metainfo,kvconfig,multihandler,get_extip_func,listenport,videoanalyserpath,vodfileindex,set_error_func,pstate,lmvodeventcallback,lmhashcheckcompletecallback):
        
        self.dow = None
        self.set_error_func = set_error_func
        self.videoinfo = None
        self.videostatus = None
        self.lmvodeventcallback = lmvodeventcallback
        self.lmhashcheckcompletecallback = lmhashcheckcompletecallback
        self.logmsgs = []
        self._hashcheckfunc = None
        self._getstatsfunc = None
        try:
            self.dldoneflag = Event()
            self.dlrawserver = multihandler.newRawServer(infohash,self.dldoneflag)
            self.lmvodeventcallback = lmvodeventcallback
    
            if pstate is not None:
                self.hashcheckfrac = pstate['dlstate']['progress']
            else:
                self.hashcheckfrac = 0.0
    
            self.peerid = createPeerID()
            #print >>sys.stderr,"SingleDownload: __init__: My peer ID is",`peerid`
    
            self.dow = BT1Download(self.hashcheckprogressfunc,
                            self.finishedfunc,
                            self.fatalerrorfunc, 
                            self.nonfatalerrorfunc,
                            self.logerrorfunc,
                            self.dldoneflag,
                            kvconfig,
                            metainfo, 
                            infohash,
                            self.peerid,
                            self.dlrawserver,
                            get_extip_func,
                            listenport,
                            videoanalyserpath
                            )
        
            file = self.dow.saveAs(self.save_as)
            #if DEBUG:
            #    print >>sys.stderr,"SingleDownload: dow.saveAs returned",file
            
            # Set local filename in vodfileindex
            if vodfileindex is not None:
                index = vodfileindex['index']
                if index == -1:
                    index = 0
                vodfileindex['outpath'] = self.dow.get_dest(index)
                self.videoinfo = vodfileindex
                if 'live' in metainfo['info']:
                    authparams = metainfo['info']['live']
                else:
                    authparams = None
                self.videostatus = VideoStatus(metainfo['info']['piece length'],self.dow.files,vodfileindex,authparams)
                self.videoinfo['status'] = self.videostatus
                self.dow.set_videoinfo(vodfileindex,self.videostatus)

            #if DEBUG:
            #    print >>sys.stderr,"SingleDownload: setting vodfileindex",vodfileindex
            
            if pstate is None:
                resumedata = None
            else:
                # Restarting download
                resumedata=pstate['engineresumedata']
            self._hashcheckfunc = self.dow.initFiles(resumedata=resumedata)
            
            
        except Exception,e:
            self.fatalerrorfunc(e)
    
    def get_bt1download(self):
        return self.dow
    
    def save_as(self,name,length,saveas,isdir):
        """ Return the local filename to which to save the file 'name' in the torrent """
        if DEBUG:
            print >>sys.stderr,"SingleDownload: save_as(",`name`,length,`saveas`,isdir,")"
        try:
            if not os.access(saveas,os.F_OK):
                os.mkdir(saveas)
            path = os.path.join(saveas,name)
            if isdir and not os.path.isdir(path):
                os.mkdir(path)
            return path
        except Exception,e:
            self.fatalerrorfunc(e)

    def perform_hashcheck(self,complete_callback):
        """ Called by any thread """
        if DEBUG:
            print >>sys.stderr,"SingleDownload: perform_hashcheck()" # ,self.videoinfo
        try:
            """ Schedules actually hashcheck on network thread """
            self._getstatsfunc = SPECIAL_VALUE # signal we're hashchecking
            # Already set, should be same
            self.lmhashcheckcompletecallback = complete_callback
            self._hashcheckfunc(self.lmhashcheckcompletecallback)
        except Exception,e:
            self.fatalerrorfunc(e)
            
    def hashcheck_done(self):
        """ Called by LaunchMany when hashcheck complete and the Download can be
            resumed
            
            Called by network thread
        """
        if DEBUG:
            print >>sys.stderr,"SingleDownload: hashcheck_done()"
        try:
            self.dow.startEngine(vodeventfunc = self.lmvodeventcallback)
            self._getstatsfunc = self.dow.startStats() # not possible earlier
            self.dow.startRerequester()
            self.dlrawserver.start_listening(self.dow.getPortHandler())
        except Exception,e:
            self.fatalerrorfunc(e)


    # DownloadConfigInterface methods
    def set_max_speed(self,direct,speed,callback):
        if self.dow is not None:
            if DEBUG:
                print >>sys.stderr,"SingleDownload: set_max_speed",`self.dow.response['info']['name']`,direct,speed
            if direct == UPLOAD:
                self.dow.setUploadRate(speed,networkcalling=True)
            else:
                self.dow.setDownloadRate(speed,networkcalling=True)
        if callback is not None:
            callback(direct,speed)

    def set_max_conns_to_initiate(self,nconns,callback):
        if self.dow is not None:
            if DEBUG:
                print >>sys.stderr,"SingleDownload: set_max_conns_to_initiate",`self.dow.response['info']['name']`,direct,speed
            self.dow.setInitiate(nconns,networkcalling=True)
        if callback is not None:
            callback(nconns)


    def set_max_conns(self,nconns,callback):
        if self.dow is not None:
            if DEBUG:
                print >>sys.stderr,"SingleDownload: set_max_conns",`self.dow.response['info']['name']`,direct,speed
            self.dow.setMaxConns(nconns,networkcalling=True)
        if callback is not None:
            callback(nconns)


    #
    # For DownloadState
    #
    def get_stats(self,getpeerlist):
        logmsgs = self.logmsgs[:] # copy
        coopdl_helpers = []
        coopdl_coordinator = None
        if self.dow is not None:
            if not self.dow.helper is None:
                coopdl_coordinator = self.dow.helper.get_coordinator_permid() 
            if self.dow.coordinator is not None: 
                # No coordinator when you're a helper
                peerreclist = self.dow.coordinator.network_get_asked_helpers_copy()
                for peerrec in peerreclist:
                    coopdl_helpers.append(peerrec['permid'])
        if self._getstatsfunc is None:
            return (DLSTATUS_WAITING4HASHCHECK,None,logmsgs,coopdl_helpers,coopdl_coordinator)
        elif self._getstatsfunc == SPECIAL_VALUE:
            stats = {}
            stats['frac'] = self.hashcheckfrac
            return (DLSTATUS_HASHCHECKING,stats,logmsgs,coopdl_helpers,coopdl_coordinator)
        else:
            return (None,self._getstatsfunc(getpeerlist=getpeerlist),logmsgs,coopdl_helpers,coopdl_coordinator)

    def get_infohash(self):
        return self.infohash

    #
    # Persistent State
    #
    def checkpoint(self):
        if self.dow is not None:
            return self.dow.checkpoint()
        else:
            return None
    
    def shutdown(self):
        if DEBUG:
            print >>sys.stderr,"SingleDownload: shutdown"
        resumedata = None
        if self.dow is not None:
            self.dldoneflag.set()
            self.dlrawserver.shutdown()
            resumedata = self.dow.shutdown()
            self.dow = None
            #if DEBUG:
            #    print >>sys.stderr,"SingleDownload: stopped dow"
                
        if self._getstatsfunc is None or self._getstatsfunc == SPECIAL_VALUE:
            # Hashchecking or waiting for while being shutdown, signal LaunchMany
            # so it can schedule a new one.
            self.lmhashcheckcompletecallback(success=False)
        return resumedata

    #
    # Cooperative download
    #
    def ask_coopdl_helpers(self,peerreclist):
        if self.dow is not None:
            self.dow.coordinator.network_request_help(peerreclist)

    def stop_coopdl_helpers(self,peerreclist):
        if self.dow is not None:
            self.dow.coordinator.network_stop_help(peerreclist,force=True)

    def get_coopdl_role_object(self,role):
        # Used by Coordinator/HelperMessageHandler indirectly
        if self.dow is not None:
            if role == COOPDL_ROLE_COORDINATOR:
                return self.dow.coordinator
            else:
                return self.dow.helper
        else:
            return None

    #
    # Internal methods
    #
    def hashcheckprogressfunc(self,activity = '', fractionDone = 0.0):
        """ Allegedly only used by StorageWrapper during hashchecking """
        #print >>sys.stderr,"SingleDownload::statusfunc called",activity,fractionDone
        self.hashcheckfrac = fractionDone

    def finishedfunc(self):
        """ Download is complete """
        if DEBUG:
            print >>sys.stderr,"SingleDownload::finishedfunc called: Download is complete *******************************"
        pass

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

    def logerrorfunc(self,msg):
        t = time.time()
        self.logmsgs.append((t,msg))
        
        # Keep max 10 log entries, API user should save them if he wants 
        # complete history
        if len(self.logmsgs) > 10:
            self.logmsgs.pop(0)
            
