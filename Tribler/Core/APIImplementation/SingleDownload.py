# Written by Arno Bakker
# Updated by George Milescu 
# see LICENSE.txt for license information

import sys
import os
import time
import copy
import pickle
import socket
import binascii
from base64 import b64encode
from types import StringType,ListType,IntType
from traceback import print_exc,print_stack
from threading import Event

from Tribler.Core.simpledefs import *
from Tribler.Core.exceptions import *
from Tribler.Core.BitTornado.__init__ import createPeerID
from Tribler.Core.BitTornado.download_bt1 import BT1Download
from Tribler.Core.BitTornado.bencode import bencode,bdecode
from Tribler.Core.Video.VideoStatus import VideoStatus
from Tribler.Core.Video.SVCVideoStatus import SVCVideoStatus
from Tribler.Core.DecentralizedTracking.repex import RePEXer
from Tribler.Core.Statistics.Status.Status import get_status_holder


SPECIAL_VALUE = 481

DEBUG = False

class SingleDownload:
    """ This class is accessed solely by the network thread """
    
    def __init__(self, infohash, metainfo, kvconfig, multihandler, get_extip_func, listenport, videoanalyserpath, vodfileindex, set_error_func, pstate, lmvodeventcallback, lmhashcheckcompletecallback, dlinstance):
        self.dow = None
        self.set_error_func = set_error_func
        self.videoinfo = None
        self.videostatus = None
        self.lmvodeventcallback = lmvodeventcallback
        self.lmhashcheckcompletecallback = lmhashcheckcompletecallback
        self.logmsgs = []
        self._hashcheckfunc = None
        self._getstatsfunc = None
        self.infohash = infohash
        self.b64_infohash = b64encode(infohash)
        self.repexer = None
        # ProxyService_
        #
        self.dlinstance = dlinstance
        #
        # _proxyService
        
        
        try:
            self.dldoneflag = Event()
            self.dlrawserver = multihandler.newRawServer(infohash,self.dldoneflag)
            self.lmvodeventcallback = lmvodeventcallback
    
            if pstate is not None:
                self.hashcheckfrac = pstate['dlstate']['progress']
            else:
                self.hashcheckfrac = 0.0
    
            self.peerid = createPeerID()
            
            # LOGGING
            event_reporter = get_status_holder("LivingLab")
            event_reporter.create_and_add_event("peerid", [self.b64_infohash, b64encode(self.peerid)])
            
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
                            videoanalyserpath,
                            self.dlinstance
                            )
        
            file = self.dow.saveAs(self.save_as)
            #if DEBUG:
            #    print >>sys.stderr,"SingleDownload: dow.saveAs returned",file
            
            # Set local filename in vodfileindex
            if vodfileindex is not None:
                # Ric: for SVC the index is a list of indexes
                index = vodfileindex['index']
                if type(index) == ListType:
                    svc = len(index) > 1
                else:
                    svc = False
                
                if svc:
                    outpathindex = self.dow.get_dest(index[0])
                else:
                    if index == -1:
                        index = 0
                    outpathindex = self.dow.get_dest(index)

                vodfileindex['outpath'] = outpathindex
                self.videoinfo = vodfileindex
                if 'live' in metainfo['info']:
                    authparams = metainfo['info']['live']
                else:
                    authparams = None
                if svc:
                    self.videostatus = SVCVideoStatus(metainfo['info']['piece length'],self.dow.files,vodfileindex,authparams)
                else:
                    self.videostatus = VideoStatus(metainfo['info']['piece length'],self.dow.files,vodfileindex,authparams)
                self.videoinfo['status'] = self.videostatus
                self.dow.set_videoinfo(vodfileindex,self.videostatus)

            #if DEBUG:
            #    print >>sys.stderr,"SingleDownload: setting vodfileindex",vodfileindex
            
            # RePEX: Start in RePEX mode
            if kvconfig['initialdlstatus'] == DLSTATUS_REPEXING:
                if pstate is not None and pstate.has_key('dlstate'):
                    swarmcache = pstate['dlstate'].get('swarmcache',{})
                else:
                    swarmcache = {}
                self.repexer = RePEXer(self.infohash, swarmcache)
            else:
                self.repexer = None
            
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
            
            # RePEX: don't start the Rerequester in RePEX mode
            repexer = self.repexer
            if repexer is None:
                self.dow.startRerequester()
            else:
                self.hook_repexer()
                
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
                print >>sys.stderr,"SingleDownload: set_max_conns_to_initiate",`self.dow.response['info']['name']`
            self.dow.setInitiate(nconns,networkcalling=True)
        if callback is not None:
            callback(nconns)


    def set_max_conns(self,nconns,callback):
        if self.dow is not None:
            if DEBUG:
                print >>sys.stderr,"SingleDownload: set_max_conns",`self.dow.response['info']['name']`
            self.dow.setMaxConns(nconns,networkcalling=True)
        if callback is not None:
            callback(nconns)
    

    #
    # For DownloadState
    #
    def get_stats(self,getpeerlist):
        logmsgs = self.logmsgs[:] # copy
        # ProxyService_
        #
        proxyservice_proxy_list = []
        proxyservice_doe_list = []
        if self.dow is not None and self.dow.proxydownloader is not None:
            proxyservice_doe_list = list(self.dow.proxydownloader.proxy.doe_nodes)
            proxyservice_proxy_list = list(self.dow.proxydownloader.doe.confirmed_proxies)
        #
        # _ProxyService

        if self._getstatsfunc is None:
            return (DLSTATUS_WAITING4HASHCHECK,None,logmsgs,proxyservice_proxy_list,proxyservice_doe_list)
        elif self._getstatsfunc == SPECIAL_VALUE:
            stats = {}
            stats['frac'] = self.hashcheckfrac
            return (DLSTATUS_HASHCHECKING,stats,logmsgs,proxyservice_proxy_list,proxyservice_doe_list)
        else:
            # RePEX: if we're repexing, set our status
            if self.repexer is not None:
                status = DLSTATUS_REPEXING
            else:
                status = None
            return (status,self._getstatsfunc(getpeerlist=getpeerlist),logmsgs,proxyservice_proxy_list,proxyservice_doe_list)

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
            # RePEX: unhook and abort RePEXer
            if self.repexer:
                repexer = self.unhook_repexer()
                repexer.repex_aborted(self.infohash, DLSTATUS_STOPPED)
            
            self.dldoneflag.set()
            self.dlrawserver.shutdown()
            
            # Niels: setting self.dow to None to prevent io-errors to call shutdown and cause a loop
            dow = self.dow
            self.dow = None
            resumedata = dow.shutdown()
            
            #if DEBUG:
            #    print >>sys.stderr,"SingleDownload: stopped dow"
                
        if self._getstatsfunc is None or self._getstatsfunc == SPECIAL_VALUE:
            # Hashchecking or waiting for while being shutdown, signal LaunchMany
            # so it can schedule a new one.
            self.lmhashcheckcompletecallback(success=False)
                
        return resumedata
    
    #
    # RePEX, Raynor Vliegendhart:
    # Restarting a running Download previously was a NoOp according to 
    # DownloadImpl, but now the decision is left up to SingleDownload.
    def restart(self, initialdlstatus=None):
        """
        Called by network thread. Called when Download was already running
        and Download.restart() was called.
        """
        if self.repexer and initialdlstatus != DLSTATUS_REPEXING:
            # kill the RePEX process
            repexer = self.unhook_repexer()
            repexer.repex_aborted(self.infohash, initialdlstatus)
        else:
            pass # NoOp, continue with download as before
    
    
    #
    # RePEX: get_swarmcache
    #
    def get_swarmcache(self):
        """
        Returns the last stored swarmcache when RePEXing otherwise None.
        
        @return A dict mapping dns to a dict with at least 'last_seen' 
        and 'pex' keys.
        """
        if self.repexer is not None:
            return self.repexer.get_swarmcache()[0]
        return None
    
    #
    # RePEX: Hooking and unhooking the RePEXer
    #
    def hook_repexer(self):
        repexer = self.repexer
        if repexer is None:
            return
        self.dow.Pause()
        
        # create Rerequester in BT1D just to be sure, but don't start it
        # (this makes sure that Encoder.rerequest != None)
        self.dow.startRerequester(paused=True)
        
        connecter, encoder = self.dow.connecter, self.dow.encoder
        connecter.repexer = repexer
        encoder.repexer = repexer
        rerequest = self.dow.createRerequester(repexer.rerequester_peers)
        repexer.repex_ready(self.infohash, connecter, encoder, rerequest)
    
    def unhook_repexer(self):
        repexer = self.repexer
        if repexer is None:
            return
        self.repexer = None
        if self.dow is not None:
            #BUG? AttributeError: BT1Download instance has no attribute 'connecter'
            connecter, encoder = self.dow.connecter, self.dow.encoder
            connecter.repexer = None
            encoder.repexer = None
            self.dow.startRerequester() # not started, so start it.
            self.dow.Unpause()
        return repexer
    
    #
    # ProxyService
    #
    def get_proxyservice_object(self, role):
        # Used by DoeMessageHandler and ProxyMessageHandler indirectly
        if self.dow is not None and self.dow.proxydownloader is not None:
            if role == PROXYSERVICE_DOE_OBJECT:
                return self.dow.proxydownloader.doe
            elif role == PROXYSERVICE_PROXY_OBJECT:
                return self.dow.proxydownloader.proxy
            else:
                return None
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
            
