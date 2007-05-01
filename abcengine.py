import wx
import sys
from socket import inet_aton
import os

#from operator import itemgetter
from threading import Event, Timer, currentThread
from time import time, sleep
#from cStringIO import StringIO
from traceback import print_stack, print_exc
from binascii import unhexlify

from BitTornado.download_bt1 import BT1Download
from BitTornado.clock import clock

from Utility.constants import * #IGNORE:W0611
from Utility.helpers import getfreespace

from Tribler.Worldmap.peer import BTPeer
from Tribler.CacheDB.CacheDBHandler import FriendDBHandler
from Tribler.NATFirewall.DialbackMsgHandler import DialbackMsgHandler

from safeguiupdate import DelayedEventHandler
from Tribler.utilities import show_permid_short
from Tribler.Video.VideoPlayer import VideoPlayer

DEBUG = True


################################################################
#
# Class: ABCEngine
#
# This is the part of a torrent object created while it is
# active.  It handles processing of statistics and information
# from the BitTornado core.
#
################################################################
class ABCEngine(DelayedEventHandler):
    def __init__(self, torrent, myid):
        DelayedEventHandler.__init__(self)
        self.doneflag = Event()

        self.torrent = torrent
        self.queue = torrent.queue
        self.utility = torrent.utility

        self.downsize = { 'old' : torrent.files.downsize, 
                          'new' : 0.0 }
        self.upsize = { 'old' : torrent.files.upsize, 
                        'new' : 0.0 }
        
        self.spewwait = time()

        self.reannouncelast = 0
        self.lastexternalannounce = ''

        self.timers = { 'lastupload': time(), 
                        'lastdownload': time(),
                        'infrequent': None }

        self.btstatus = self.utility.lang.get('waiting')
        self.progress = torrent.files.progress
        
        self.eta = None
        self.rate = { "down" : 0.0, 
                      "up" : 0.0 }

        self.numpeers = 0
        self.numseeds = 0

        self.numconnections = 0
        self.numcopies = None
        self.peeravg = None
        self.totalspeed = 0.0
        self.numerrortracker=0
        self.lasterrortracker=0
        
        self.current_ratesetting = None
        
        self.seedingtimelastcheck = None

        # To compute mean over several last values of uprate/downrate        
        self.pastrate = { "down" : [0.0] * 20, 
                          "up" : [0.0] * 20 }
        self.meanrate = { "down" : 0.0, 
                          "up" : 0.0 }
                     
        # Keep track of if we have any connections
        self.hasConnections = False
        
        # New stuff....

        self.controller = self.utility.controller
        self.statsfunc = self.dummy_statsfunc()
        
        self.waiting = True
        self.checking = False
        self.working = False
        self.seed = False
        self.closed = False

        self.status_err = ['']
        self.status_errtime = 0
        self.status_done = 0.0
        
        self.response = self.torrent.metainfo
        hash = unhexlify(self.torrent.infohash)

        self.rawserver = self.controller.handler.newRawServer(hash, self.doneflag)

        # TODO: Workaround for multiport not reporting
        #       external_connection_made properly
        self.workarounds = { 'hasexternal': False }
        
        self.color = 'color_startup'
        self.downloadHelpers = []
        self.fileProgressPostponeCounter = 0
        self.btengine_said_reachable = False
        
        btconfig = self.utility.getBTParams()
        # 2fastbt_
        if self.torrent.caller == "helper":
            btconfig['role'] = 'helper'
            btconfig['coordinator_permid'] = self.torrent.caller_data['coordinator_permid']
            msg = self.utility.lang.get('helping_friend') + self.torrent.caller_data['friendname']
            self.errormsgCallback( msg, "status")
        else:
            btconfig['role'] = 'coordinator'
            btconfig['helpers_file'] = ''
         # _2fastbt

#        # TODO: setting check_hashes doesn't seem to work quite right
#        #
#        # Only do reseed resume if the size of the files matches
#        # the size that they are supposed to be
#        # (Should prevent errors in at least some cases)
#        if self.torrent.files.getSpaceNeeded(realsize = False) == 0:
#            if self.torrent.files.skipcheck or \
#               (self.torrent.status.completed and self.utility.config.Read('skipcheck', "boolean")):
#                btconfig['check_hashes'] = 0
#        self.torrent.files.skipcheck = False

        video_analyser_path = self.utility.config.Read('videoanalyserpath')

        self.dow = BT1Download(self.display, 
                               self.finished, 
                               self.error, 
                               self.controller.exchandler, 
                               self.doneflag, 
                               btconfig,
                               self.response, 
                               hash, 
                               myid, 
                               self.rawserver, 
                               self.controller.listen_port,
                               self.torrent.get_on_demand_download(),
                               self.torrent.get_videoinfo(),
                               self.torrent.get_progressinf(),
                               video_analyser_path)


    ####################################
    # BEGIN NEW STUFF (FOR SINGLE PORT)
    ####################################

    def start(self):
        # Delete the cache information if doing a hashcheck
        # (only necessary to delete the cache if fastresume is enabled)
        if ((self.torrent.status.value == STATUS_HASHCHECK) and
            self.utility.config.Read('fastresume', "boolean")):
            self.dow.appdataobj.deleteTorrentData(self.dow.infohash)
               
        if not self.dow.saveAs(self.saveAs):
            self.shutdown()
            return
        self._hashcheckfunc = self.dow.initFiles()
        
        if DEBUG:
            print >>sys.stderr,"engine: start: after initFiles"

        if not self._hashcheckfunc:
            self.shutdown()
            return

        self.controller.hashchecksched(self.torrent)
        if DEBUG:
            print >>sys.stderr,"engine: start: after hashchecksched"

    def hashcheck_start(self, donefunc):
        if DEBUG:
            print >>sys.stderr,"engine: hashcheck_start: enter"
        if self.is_dead():
            self.shutdown()
            return
        self.waiting = False
        self.checking = True
        
        # Start infrequent tasks
        self.InfrequentTasks()
        if DEBUG:
            print >>sys.stderr,"engine: start: after start infreq tasks"
        
        self._hashcheckfunc(donefunc)
        if DEBUG:
            print >>sys.stderr,"engine: start: after _hashcheckfunc call",self._hashcheckfunc

    def hashcheck_callback(self):
        self.checking = False
               
        if self.is_dead():
            self.shutdown()
            return
        
        if not self.dow.startEngine(ratelimiter = None):
            self.shutdown()
            return

        # Errors with StorageWrapper can occur deep inside MovieOnDemandTransporter
        # not easy to report that back till here, so do it like this.
        #if self.is_dead():
        #    self.shutdown()
        #    return

        self.dow.startRerequester()

        self.statsfunc = self.dow.startStats()

        if self.torrent.status.value != STATUS_HASHCHECK:
            self.torrent.status.updateStatus(STATUS_ACTIVE)

        self.torrent.files.setFilePriorities()
        self.torrent.connection.setMaxInitiate()
        
        # Set the spew flag if the detail window is shown
        if self.torrent.dialogs.details is not None:
            self.dow.spewflag.set()

        # TODO: Workaround for multiport not reporting
        #       external_connection_made properly
        self.dow.spewflag.set()
               
        self.rawserver.start_listening(self.dow.getPortHandler())
        self.working = True

    def shutdown(self):
        if DEBUG:
            print "engine: Starting shutdown"
        # Remove from the active torrents list
        try:
            del self.utility.torrents["active"][self.torrent]
        except:
            pass

        self.stop_download_help()
            
        # Cancel timer
        try:
            if self.timers['infrequent'] is not None:
                self.timers['infrequent'].cancel()
        except:
            pass

        if self.closed:
            return
        self.doneflag.set()
        try:
            if DEBUG:
                print "engine: Shutting down SingleRawServer"
            self.rawserver.shutdown()
        except:
            print_exc()
            pass

        try:
            self.dow.shutdown()
        except:
            pass
        self.waiting = False
        self.checking = False
        self.working = False
        self.closed = True

        self.controller.was_stopped(self.torrent)

    def display(self, activity = None, fractionDone = None):
        # really only used by StorageWrapper now
        self.setActivity(activity)
        if fractionDone is not None:
            self.status_done = float(fractionDone)

    def error(self, msg):
        if DEBUG:
            print "engine: Error",msg
        if self.doneflag.isSet():
            # delegate updating GUI error message to launchmany core, as
            # we're dying.
            self.controller.dying_engines_errormsg(self.torrent,msg,"error")
            self.shutdown()
        else:
            self.errormsg(msg)
        self.status_err.append(msg)
        self.status_errtime = clock()

        if self.torrent.get_on_demand_download():
            # We was VOD-ing
            videoplayer = VideoPlayer.getInstance()
            videoplayer.vod_failed(self.torrent)


    def saveAs(self, name, length, saveas, isdir):
        return self.torrent.files.dest
        
    def done(self, event = None):
        self.torrent.set()
        
    def is_dead(self):
        return self.doneflag.isSet()
        
    ####################################
    # END NEW STUFF (FOR SINGLE PORT)
    ####################################
        
    def setActivity(self, activity):
        if activity is not None:
            activities = { "checking existing data": self.utility.lang.get('checkingdata'), 
                           "allocating disk space": self.utility.lang.get('allocatingspace'), 
                           "moving data": self.utility.lang.get('movingdata') }
            self.btstatus = activities.get(activity, activity)

    def onUpdateStatus(self, fractionDone = None, 
            timeEst = None, downRate = None, upRate = None, 
            activity = None, statistics = None, spew = None, havedigest = None,
            **kws):

        self.invokeLater(self.updateStatus, [fractionDone, timeEst, downRate, upRate, activity, statistics, spew, havedigest])

        
    def updateStatus(self, fractionDone = None, timeEst = None, downRate = None, upRate = None, activity = None, statistics = None, spew = None, havedigest = None):
        # Just in case a torrent was finished
        # but now isn't
        self.torrent.status.completed = self.seed
    
        # Get scrape data every 20 minutes
        #############################################
        if self.utility.config.Read('scrape', "boolean"):
            self.torrent.actions.scrape()
       
        # Get Display Data
        #############################################
        if fractionDone is not None and not self.seed:
            self.progress = (float(fractionDone) * 100)

        self.setActivity(activity) # GUI

        if timeEst is not None:
            self.eta = timeEst
        else:
            self.eta = None
        
        if self.torrent.status.value != STATUS_PAUSE:
            if not self.seed and downRate is not None:
                self.rate['down'] = float(downRate)
                if self.rate['down'] != 0.0:
                    self.timers['lastdownload'] = time()
            else:
                self.rate['down'] = 0.0
                       
            if upRate is not None:
                self.rate['up'] = float(upRate)

                self.pastrate['up'].append(self.rate['up'])
                self.pastrate['up'].pop(0)

                if self.rate['up'] != 0.0:
                    self.timers['lastupload'] = time()

                # Compute mean uprate

                total = sum(self.pastrate['up'])
                self.meanrate['up'] = total / 20
            else:
                self.rate['up'] = 0.0

        if statistics is not None:
            self.numpeers   = statistics.numPeers
            self.numcopies  = statistics.numCopies
            self.peeravg    = statistics.percentDone

            # Update download, upload, and progress
            self.downsize['new'] = float(statistics.downTotal)
            self.upsize['new'] = float(statistics.upTotal)
            self.torrent.files.updateProgress() #GUI
            self.totalspeed = float(statistics.torrentRate)
            self.numconnections = statistics.numPeers

            if not self.seed:
                self.numseeds = statistics.numSeeds
                self.numconnections += statistics.numSeeds
            else:
                self.numseeds = statistics.numOldSeeds
        else:
            self.peeravg = None
            self.numcopies = None
        
        if self.seed:
            self.countSeedingTime()
            if self.torrent.status.isDoneUploading(): #GUI
                self.TerminateUpload()

        # Update color
        self.updateColor(statistics, spew)

        # Update text strings
        self.torrent.updateColumns([COL_PROGRESS, 
                                    COL_BTSTATUS, 
                                    COL_ETA, 
                                    COL_DLSPEED, 
                                    COL_ULSPEED, 
                                    COL_MESSAGE])
        
               
        
        if statistics is not None:
            # Share Ratio, #Seed, #Peer, #Copies, #Peer Avg Progress,
            # Download Size, Upload Size, Total Speed
            self.torrent.updateColumns([COL_RATIO, 
                                        COL_SEEDS, 
                                        COL_PEERS, 
                                        COL_COPIES, 
                                        COL_PEERPROGRESS, 
                                        COL_DLSIZE, 
                                        COL_ULSIZE, 
                                        COL_TOTALSPEED, 
                                        COL_SEEDTIME, 
                                        COL_CONNECTIONS])

        # Update progress in details window
        if statistics is not None:
            # Arno: slow down file progress update by a factor for multi-file
            # torrents. Otherwise if the torrent has many files, the client will 
            # come to a halt.
            #print "engine: #files in stats",len(statistics.filecomplete)
            if self.fileProgressPostponeCounter == 0:
                self.torrent.files.updateFileProgress(statistics)
                if getattr(statistics,"filecomplete",None) is not None:
                    self.fileProgressPostponeCounter = int(len(statistics.filecomplete)/1000)
                else:
                    self.fileProgressPostponeCounter = 0
            else:
                self.fileProgressPostponeCounter -= 1

        if spew and len(spew) > 0:
            self.updateCaches(spew)

#        try:
            self.updateDetailWindow(statistics, spew)
#        except Exception, msg:
#            # Just in case the window gets set to "None"
#            # or is destroyed first
#            print Exception, msg
#        

        # Save summary of map of downloaded pieces
        self.torrent.status.setHaveDigest(havedigest)

        if self.torrent.status.value == STATUS_HASHCHECK and self.working:
            # Skip on ahead to the normal procedure if the torrent was active
            # before doing the hashcheck
            activevalues = [ STATUS_ACTIVE, STATUS_PAUSE, STATUS_SUPERSEED ]
            oldstatus = self.torrent.actions.oldstatus
            if not oldstatus in activevalues:
                self.shutdown()
                return
            else:
                self.torrent.status.updateStatus(STATUS_ACTIVE)
        
        
    # TODO: Workaround for multiport not reporting
    #       external_connection_made properly
    def getExternalConnectionsMade(self, spew):
        if self.workarounds['hasexternal']:
            return True
            
        # Consider at least one remote connection evidence of
        # an external connection being made
        for x in range(len(spew)):
            if spew[x]['direction'] == 'R':
                self.workarounds['hasexternal'] = True
            
                # We can clear the spewflag now...
                if self.torrent.dialogs.details is None:
                    self.dow.spewflag.clear()
                return True
            
        return False
        
    def updateColor(self, statistics = None, spew = None):
        ##################################################
        # Set colour :
        ##################################################
        color = None
        
        if currentThread().getName() != "MainThread":
            print "engine: updateColor thread",currentThread()
            print "engine: NOT MAIN THREAD"
            print_stack()

        if statistics is not None:
            externalConnectionMade = statistics.external_connection_made
        
            # TODO: Workaround for multiport not reporting
            #       external_connection_made properly
            if externalConnectionMade:
                self.workarounds['hasexternal'] = True
            else:
                externalConnectionMade = self.workarounds['hasexternal']
                if not externalConnectionMade and spew is not None:
                    externalConnectionMade = self.getExternalConnectionsMade(spew)
        
            if externalConnectionMade:
                # Arno: this means we're externally reachable
                if not self.btengine_said_reachable:
                    dmh = DialbackMsgHandler.getInstance()
                    dmh.btengine_says_reachable()
                    self.btengine_said_reachable = True

        if statistics is None: 
            color = 'color_startup' #Start up
            self.hasConnections = False
        elif statistics.numPeers + statistics.numSeeds + statistics.numOldSeeds == 0:
            if statistics.last_failed:
                #Disconnected
                color = 'color_disconnected'
            else:
                #No connections
                color = 'color_noconnections'
            self.hasConnections = False
        elif (not externalConnectionMade):
            #No incoming
            color = 'color_noincoming'
            self.hasConnections = True
        elif ((statistics.numSeeds + statistics.numOldSeeds == 0)
               and ((self.seed and statistics.numCopies < 1)
                or (not self.seed and statistics.numCopies2 < 1))):
            #No completes
            color = 'color_nocomplete'
            self.hasConnections = True
        else:
            #All Good
            color = 'color_good'
            self.hasConnections = True

        self.color = color
        self.torrent.updateColor()
    
    #
    # Things that don't need to be done on every pass through updateStatus
    #
    def InfrequentTasks(self):
        try:
            if self.timers['infrequent'] is not None:
                self.timers['infrequent'].cancel()
        except:
            pass
        
        self.CheckTimeouts()
        self.CheckDiskSpace()
        
        # Should check diskspace more frequently
        # while in the "allocating" stage
        if self.waiting or self.checking:
            nextcheck = 2
        else:
            nextcheck = 30
        
        self.timers['infrequent'] = Timer(nextcheck, self.InfrequentTasks)
        self.timers['infrequent'].start()
    
    #
    # Check to make sure that there's free diskspace
    #
    def CheckDiskSpace(self):
        threshold = self.utility.config.Read('diskfullthreshold', "int")
        
        # Disk checking is disabled
        if threshold == 0:
            return
        
        # See how much more space the torrent needs
        spaceneeded = self.torrent.files.getSpaceNeeded()
        
        # Don't need to worry if the torrent already has
        # as much space as it needs
        if spaceneeded == 0L:
            return
            
        dest = self.torrent.files.getProcDest(pathonly = True)
        if dest is None:
            # Don't bother checking for space until the
            # destination path exists
            return
            
        spaceleft = getfreespace(dest)
        if spaceleft < long((2**20) * threshold):
            message = self.utility.lang.get('diskfull') + \
                      " (" + self.utility.size_format(spaceleft) + ")"
            self.errormsg(message)
            self.actionhandlerCallback( STATUS_STOP, self.torrent )
    
    #
    # See if there's been a timeout
    #
    def CheckTimeouts(self):
        # Check to see if we need to check for timeouts
        if not self.torrent.connection.timeout or self.torrent.status.value == STATUS_PAUSE:
            return
        
        # Check no download transfer in 30 mins
        # (when this torrent is leeching torrent)
        ##########################################
        if not self.seed:
            timeoutdownload = self.utility.config.Read('timeoutdownload')
            if (timeoutdownload != 'oo'
                and (time() - self.timers['lastdownload']) > (float(timeoutdownload)*60)):
                self.ReducePrioandForceQueue()
                return

        # Check no upload transfer in 1 hour
        # (when this torrent is seeding torrent)
        ##########################################
        else:
            timeoutupload = self.utility.config.Read('timeoutupload')
            if ((timeoutupload != 'oo')
                and (time() - self.timers['lastupload']) > (float(timeoutupload)*3600)):
                self.ReducePrioandForceQueue()
                return

    def updateDetailWindow(self, statistics = None, spew = None):
        #####################################################
        # Detail Window display part
        #####################################################
        detailwin = self.torrent.dialogs.details
        if detailwin is None or not detailwin.update:
            return
        detailpanel = detailwin.detailPanel
        
        if statistics is not None:
            detailpanel.updateFromABCTorrent()
                      
        if spew is not None and (time() - self.spewwait > 1):
            self.updateSpewList(statistics, spew)

        if statistics is not None:
            detailpanel.storagestats1.SetLabel("          " + self.utility.lang.get('detailline1')
                             % (statistics.storage_active, 
                                 statistics.storage_new, 
                                 statistics.storage_dirty))
            detailpanel.storagestats2.SetLabel("          "+ self.utility.lang.get('detailline2')
                             % (statistics.storage_numcomplete, 
                                 statistics.storage_totalpieces, 
                                 statistics.storage_justdownloaded, 
                                 statistics.storage_numflunked))

    def updatePeersOnEarth(self, spew):
        """ update peer_swarm, delete non-actived peers, insert newcoming peers
        and update the position of peers in the earth panel
        note: each torrent has an abcengine
        """
        # set all peers as not alive and then only active all peers in spew
        for ip in self.torrent.peer_swarm.keys():
            self.torrent.peer_swarm[ip].active = False
        
        showearth = self.utility.config.Read('showearthpanel', "boolean")
        if showearth:
            for peer_info in spew:
                ip = peer_info['ip']
                if self.torrent.peer_swarm.has_key(ip):  # if the peer exists, active it
                    self.torrent.peer_swarm[ip].updateBTInfo(peer_info)
                    self.torrent.peer_swarm[ip].active = True
                else:   # otherwise create a new peer, add it into peer_swarm and display it
                    new_peer = BTPeer(peer_info, self.torrent, self.rawserver)
                    new_peer.updateBTInfo(peer_info)
                    self.torrent.peer_swarm[ip] = new_peer

    def updatePeerCache(self, spew):
        pass
        
    def updateFileCache(self, spew):
        pass

    def updateCaches(self, spew):
        """ update peers on earth map, peer cache and file cache """
        
        #print "update caches", len(spew), self
        showearth = self.utility.config.Read('showearthpanel', "boolean")
        if showearth:
            self.updatePeersOnEarth(spew)    
        self.updatePeerCache(spew)    # the real update is in DownloaderFeedback.update*()
        self.updateFileCache(spew)
        
    def sortSpew(self, spew, sortcol, reversed):
        tmplist = [(self.getSpewColumnValue(sortcol, line, spew), spew[line]) for \
                    line in range(len(spew))]
        tmplist.sort()
        if reversed:
            tmplist.reverse()
        return [x for (_, x) in tmplist]
        
    def updateSpewList(self, statistics = None, spew = None):
        detailwin = self.torrent.dialogs.details
        if spew is None or detailwin is None or not detailwin.update:
            return
        
        self.spewwait = time()
        spewList = detailwin.detailPanel.spewList
        columns = spewList.columns

        numcols = len(columns.active)
        # (no point in doing anything if there aren't any columns to update)
        if numcols == 0:
            return

        spewlen = len(spew) + 3

        if statistics is not None:
            kickbanlen = len(statistics.peers_kicked)+len(statistics.peers_banned)
            if kickbanlen:
                spewlen += kickbanlen + 1
            if statistics.peers_kicked:
                spewlen += 1
            if statistics.peers_banned:
                spewlen += 1
        else:
            kickbanlen = 0
        
        try:
            for x in range(spewlen-spewList.GetItemCount()):
                i = wx.ListItem()
                spewList.InsertItem(i)
            for x in range(spewlen, spewList.GetItemCount()):
                spewList.DeleteItem(len(spew) + 1)
        except wx.PyDeadObjectError:
            pass
    
        tot_uprate = 0.0
        tot_downrate = 0.0
        
        sortcol, reversed = spewList.getSortInfo()
        if sortcol >= 0:
            spew = self.sortSpew(spew, sortcol, reversed)
        
        # Disabling itemgetter sorts to remain 2.3 compatible
        # Sort by uprate first
        #spew.sort(None, key=itemgetter('uprate'))
        #spew.reverse()
        #if not self.torrent.status.completed:
            # Then sort by downrate if not complete
            #spew.sort(None, key=itemgetter('downrate'))
            #spew.reverse()

        for x in range(len(spew)):                
            for colid, rank in columns.active:
                self.updateSpewColumnText(x, rank, self.getSpewColumnText(colid, x, spew))
            
            tot_uprate += spew[x]['uprate']
            tot_downrate += spew[x]['downrate']

        x = len(spew)
        for i in range(numcols):
            self.updateSpewColumnText(x, i, '')
 
        x += 1
        for colid, rank in columns.active:
            if colid == SPEW_IP:
                text = self.utility.lang.get('TOTALS')
            else:
                text = ''                    
            self.updateSpewColumnText(x, rank, text)

        x += 1
        for colid, rank in columns.active:
            if colid == SPEW_UP:
                text = self.utility.speed_format(tot_uprate, truncate = 0)
            elif colid == SPEW_DOWN:
                text = self.utility.speed_format(tot_downrate, truncate = 0)
            elif colid == SPEW_DLSIZE and statistics is not None:
                text = self.utility.size_format(float(statistics.downTotal))
            elif colid == SPEW_ULSIZE and statistics is not None:
                text = self.utility.size_format(float(statistics.upTotal))
            else:
                text = ''                    
            self.updateSpewColumnText(x, rank, text)
 
        if kickbanlen:
            x += 1
            for i in range(numcols):
                self.updateSpewColumnText(x, i, '')

            if statistics.peers_kicked:
                x += 1
                for colid, rank in columns.active:
                    if colid == SPEW_IP:
                        text = self.utility.lang.get('KICKED')
                    else:
                        text = ''                    
                    self.updateSpewColumnText(x, rank, text)

                for ip in statistics.peers_kicked:
                    x += 1
                    for colid, rank in columns.active:
                        if colid == SPEW_IP:
                            text = ip[1]
                        else:
                            text = ''                    
                        self.updateSpewColumnText(x, rank, text)

            if statistics.peers_banned:
                x += 1
                for colid, rank in columns.active:
                    if colid == SPEW_IP:
                        text = self.utility.lang.get('BANNED')
                    else:
                        text = ''                    
                    self.updateSpewColumnText(x, rank, text)

                for ip in statistics.peers_banned:
                    x += 1
                    for colid, rank in columns.active:
                        if colid == SPEW_IP:
                            text = ip[1]
                        else:
                            text = ''                    
                        self.updateSpewColumnText(x, rank, text)
        
    def updateSpewColumnText(self, line, colid, text):
        detailwin = self.torrent.dialogs.details
        if detailwin is None or not detailwin.update:
            return

        try:
            detailwin.detailPanel.spewList.SetStringItem(line, colid, text)
        except wx.PyDeadObjectError:
            pass
                
                
    def getSpewColumnValue(self, colid, line, spew):

        if colid == SPEW_UNCHOKE:
            return spew[line]
            
        elif colid == SPEW_IP:
            try:
                ip = spew[line]['ip']
                return inet_aton(ip)
            except:
                return ''
                
            x = s.find('.')
            if x == -1:
                return 0
            iptext = s[:x] + '.' + ''.join(s[x:].split('.'))
            return eval(iptext)
            
        elif colid == SPEW_LR:
            return spew[line]['direction']
            
        elif colid == SPEW_UP:
            return spew[line]['uprate']
            
        elif colid == SPEW_INTERESTED:
            return spew[line]['uinterested']
            
        elif colid == SPEW_CHOKING:
            return spew[line]['uchoked']
            
        elif colid == SPEW_DOWN:
            return spew[line]['downrate']
            
        elif colid == SPEW_INTERESTING:
            return spew[line]['dinterested']
            
        elif colid == SPEW_CHOKED:
            return spew[line]['dchoked']
            
        elif colid == SPEW_SNUBBED:
            return spew[line]['snubbed']
            
        elif colid == SPEW_DLSIZE:
            return spew[line]['dtotal']
            
        elif colid == SPEW_ULSIZE:
            if spew[line]['utotal'] is not None:
                return spew[line]['utotal']
            else:
                return 0
                
        elif colid == SPEW_PEERPROGRESS:
            return spew[line]['completed']
            
        elif colid == SPEW_PEERSPEED:
            if spew[line]['speed'] is not None:
                return spew[line]['speed']
            else:
                return 0

        elif colid == SPEW_PERMID:
            if spew[line]['unauth_permid'] is not None:
                text = '*Tribler*'
                friends = FriendDBHandler().getFriends()
                for friend in friends:
                    #print "SPEW COMPARING friend",show_permid_short(friend['permid']),"to spew",show_permid_short(spew[line]['unauth_permid'])
                    if friend['permid'] == spew[line]['unauth_permid']:
                        text = friend['name']
                        break
                return text
            else:
                return ""
        
        return 0
            
    def getSpewColumnText(self, colid, line, spew):
        text = None
        
        starflag = { True : '*', False : ' ' }
        
        if colid == SPEW_UNCHOKE:
            text = starflag[spew[line]['optimistic']]
            
        elif colid == SPEW_IP:
            text = spew[line]['ip']
            
        elif colid == SPEW_LR:
            if spew[line]['direction'] == 'R':
                text = self.utility.lang.get('spew_direction_remote')
            else:
                text = self.utility.lang.get('spew_direction_local')
            
        elif colid == SPEW_UP:
            if spew[line]['uprate'] > 100:
                text = self.utility.speed_format(spew[line]['uprate'], truncate = 0, stopearly = "KB")
            
            
        elif colid == SPEW_INTERESTED:
            text = starflag[spew[line]['uinterested']]
            
        elif colid == SPEW_CHOKING:
            text = starflag[spew[line]['uchoked']]
            
        elif colid == SPEW_DOWN:
            if spew[line]['downrate'] > 100:
                text = self.utility.speed_format(spew[line]['downrate'], truncate = 0, stopearly = "KB")
            
        elif colid == SPEW_INTERESTING:
            text = starflag[spew[line]['dinterested']]
            
        elif colid == SPEW_CHOKED:
            text = starflag[spew[line]['dchoked']]
            
        elif colid == SPEW_SNUBBED:
            text = starflag[spew[line]['snubbed']]
            
        elif colid == SPEW_DLSIZE:
            text = self.utility.size_format(float(spew[line]['dtotal']))
            
        elif colid == SPEW_ULSIZE:
            if spew[line]['utotal'] is not None:
                text = self.utility.size_format(float(spew[line]['utotal']))
                
        elif colid == SPEW_PEERPROGRESS:
            text = '%.1f%%' % (float(int(spew[line]['completed']*1000))/10)
            
        elif colid == SPEW_PEERSPEED:
            if spew[line]['speed'] is not None:
                text = self.utility.speed_format(spew[line]['speed'], truncate = 0)

        elif colid == SPEW_PERMID:
            if spew[line]['unauth_permid'] is not None:
                text = '*Tribler*'
                friends = FriendDBHandler().getFriends()
                for friend in friends:
                    #print "SPEW COMPARING friend",show_permid_short(friend['permid']),"to spew",show_permid_short(spew[line]['unauth_permid'])
                    if friend['permid'] == spew[line]['unauth_permid']:
                        text = friend['name']
                        break
            
        if text is None:
            text = ""
            
        return text

    def errormsg(self, errormsg):
        errors = {"problem connecting to tracker": self.utility.lang.get('trackererror_problemconnecting'), 
                  "rejected by tracker": self.utility.lang.get('trackererror_rejected'), 
                  "bad data from tracker": self.utility.lang.get('trackererror_baddata') }
        
        try:
            trackererror = False

            for error in errors:
                index = errormsg.lower().find(error)
                if index != -1:
                    oldlen = len(error)
                    errormsg = errormsg[:index] + errors[error] + errormsg[index + oldlen:]
                    trackererror = True
                    break
            if trackererror:
                currenttime = time()
                if self.lasterrortracker == 0:
                    self.lasterrortracker = currenttime

                if (currenttime - self.lasterrortracker) < 120: #error with in 2 mins
                    self.numerrortracker += 1
                else:
                    self.numerrortracker = 0
                self.lasterrortracker = currenttime
        except:
            pass
        
        self.errormsgCallback(errormsg, "error")

        # If failed connecting tracker in parameter 'timeouttracker' mins
        # reduce its priority and force to queue
        ################################################################
        if self.torrent.connection.timeout and self.utility.config.Read('timeouttracker') != "oo":
            try:
                if self.numerrortracker > self.utility.config.Read('timeouttracker', "int"):
                    self.ReducePrioandForceQueue()
            except:
                pass

    def errormsgCallback(self,msg,label):
        self.invokeLater(self.onErrorMsg,[msg,label])

    def onErrorMsg(self,msg,label):
        self.torrent.changeMessage(msg, label)

    def ReducePrioandForceQueue(self):
        currentprio = self.torrent.prio
        if currentprio < 4:      #prio is not lowest
            self.changePriority(currentprio + 1)     #lower 1 prio

        self.queueMe()

    def changePriority(self,prio):
        self.invokeLater(self.torrent.changePriority,[prio])

    def countSeedingTime(self):
        now = time()
        if self.seedingtimelastcheck is None:
            lastcheck = now
        else:
            lastcheck = self.seedingtimelastcheck
        timelapse = now - lastcheck
        
        self.torrent.connection.seedingtime += timelapse
        
        if self.torrent.connection.getSeedOption('uploadoption') == "1":
            self.torrent.connection.seedingtimeleft = self.torrent.connection.getTargetSeedingTime() - self.torrent.connection.seedingtime
        elif self.torrent.connection.getSeedOption('uploadoption') == "2":
            if self.meanrate['up'] > 0:
                if self.torrent.files.downsize == 0.0 : 
                    down = self.torrent.files.floattotalsize
                else:
                    down = self.torrent.files.downsize
                up = self.torrent.files.upsize
                ratio = float(self.torrent.connection.getSeedOption('uploadratio'))
                required = ((ratio / 100.0) * down) - up
                newseedingtimeleft = required / self.meanrate['up']
                delta = max(newseedingtimeleft/10, 2)
                if abs(self.torrent.connection.seedingtimeleft - newseedingtimeleft) > delta:
                    # If timer value deviates from theoretical value by more then 10%, reset it to theoretical value
                    self.torrent.connection.seedingtimeleft = newseedingtimeleft
                else:
                    # Keep on timing
                    self.torrent.connection.seedingtimeleft -= timelapse
                if self.torrent.connection.seedingtimeleft < 0.1:
                    self.torrent.connection.seedingtimeleft = 0.1
            else:
                # Set to 366 days (= infinite)
                self.torrent.connection.seedingtimeleft = 999999999999999

        self.seedingtimelastcheck = now

    def TerminateUpload(self):
        # Terminate process
        ####################################################
        # change:   5:Progress  6:BT Status
        # clear : 8:ETA 10:DLSpeed 11:ULspeed
        #         14:#seed 15:#peer 16:#copie 17:peer avg
        #         20:total speed
        #####################################################
        self.torrent.status.completed = True
        self.progress = 100.0

        self.torrent.connection.stopEngine()
        
        self.queue.updateAndInvoke()

    def finished(self):
        # Let main thread perform GUI updates
        self.invokeLater(self.finished_callback)

    def finished_callback(self):
        self.seed = True
        
        # seeding process
        ####################################################
        # change:   5:Progress  6:BT Status
        # clear :   8:ETA 10:DLSpeed  
        #####################################################
        self.torrent.status.completed = True
        self.progress = 100.0
        self.torrent.files.updateProgress()

        self.stop_download_help()

        if self.torrent.status.isDoneUploading():
            self.TerminateUpload()
        
        # Update cols 5, 6, 8, 10
        self.torrent.updateColumns([COL_PROGRESS, 
                                    COL_BTSTATUS, 
                                    COL_ETA, 
                                    COL_DLSPEED])
        self.torrent.updateColor()

        self.queue.updateAndInvoke()
        
        # TODO: Play when download is complete, but not at startup when seeding torrents are set to
        # completion.
        if self.torrent.get_on_demand_download():
            videoplayer = VideoPlayer.getInstance()
            videoplayer.vod_download_completed(self.torrent)

            
    def failed(self):
        if self.utility.config.Read('failbehavior') == '0':
            # Stop      
            self.actionhandlerCallback( STATUS_STOP, self.torrent )
        else:
            # Queue
            self.queueMe()
                

    # Only queue if other things are waiting
    # that would start up by queuing this torrent
    def queueMe(self):       
        # See what the next torrent to start would be if we queued
        # this torrent
        inactivetorrents = self.utility.queue.getInactiveTorrents(1)
        if not inactivetorrents:
            return
        
        nexttorrent = inactivetorrents[0]
        
        # See if this torrent would be started if queued
        queuethis = False
        if (nexttorrent.prio < self.torrent.prio):
            queuethis = True
        elif (nexttorrent.prio == self.torrent.prio) and (nexttorrent.listindex < self.torrent.listindex):
            queuethis = True

        if queuethis:
            self.btstatus = self.utility.lang.get('queue')
            self.actionhandlerCallback( STATUS_QUEUE, self.torrent )

    def actionhandlerCallback(self,action,torrent):
        self.invokeLater(self.onActionhandler,[action,torrent])

    def onActionhandler(self,action,torrent):
        """ as calls to procQUEUE and procSTOP are usually by event handlers
            executed by the mainthread, let the mainthread call them here as well
            to prevent GUI update problems.
        """
        if action == STATUS_QUEUE:
            self.utility.actionhandler.procQUEUE([torrent])
        else:
            self.utility.actionhandler.procSTOP([torrent])

    def getDownloadhelpCoordinator(self):
        return self.dow.coordinator

    def stop_download_help(self):
        if self.dow.coordinator is not None:
            self.dow.coordinator.stop_all_help()

    def Pause(self):
        """ Called by ABC/Torrent/actions/TorrentActions """
        self.dow.Pause()
        
    def dummy_statsfunc(self):
        return None
    
    def get_moviestreamtransport(self):
        print >>sys.stderr,"engine: Getting OnDemandTransport from btdownload1",self.dow
        if self.dow is None:
            return None
        else:
            return self.dow.get_moviestreamtransport()