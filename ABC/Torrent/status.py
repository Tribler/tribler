import sys

from Utility.constants import * #IGNORE:W0611

################################################################
#
# Class: TorrentStatus
#
# Keep track of the status of a torrent
#
################################################################        
class TorrentStatus:
    def __init__(self, torrent):
        self.torrent = torrent
        self.utility = torrent.utility
        
        # set queue status
        self.value = STATUS_QUEUE
        self.completed = False
        self.dontupdate = True # Don't update until the list item is created
        self.havedigest = None
        self.lastStopped = 0
        self.lastCheckFinished = None
        
        
    def getStatusText(self, otherValue = None):
        if otherValue:
            value = otherValue
        else:
            value = self.value
        
        if self.torrent.caller_data is not None:
            if self.torrent.caller_data.has_key('coordinator_permid'):
                permid = self.torrent.caller_data['coordinator_permid']
                peer = self.utility.peer_db.getPeer(permid)    
                if peer is not None:
                    status = "helping "+peer['name']
                    return status
        
        if self.isActive():
            if value == STATUS_PAUSE:
                status = self.utility.lang.get('pause')
            elif value == STATUS_SUPERSEED:
                status = self.utility.lang.get('superseeding')
            elif self.torrent.connection.engine is not None:
                status = self.torrent.connection.engine.btstatus
            else:
                status = self.utility.lang.get('stopping')
        elif value == STATUS_FINISHED:
            status = self.utility.lang.get('completed')
        elif value == STATUS_STOP:
            # although it's stopped. still show finished
            if self.torrent.files.progress == 100.0:
                status = self.utility.lang.get('completed')
            else:
                status = self.utility.lang.get('stop')
        elif value == STATUS_QUEUE:
            status = self.utility.lang.get('queue')
        else:
            # Most likely just not quite started yet
            status = self.utility.lang.get('waiting')
        
        return status
        
    # Is the torrent active?
    def isActive(self, working = True, checking = True, pause = True):
        engine = self.torrent.connection.engine
        if engine is not None:
            if not pause and self.value == STATUS_PAUSE:
                return False
            if working and engine.working:
                return True
            elif checking and (engine.checking or engine.waiting):
                return True
                
    # See if the torrent is checking existing data or allocating
    def isCheckingOrAllocating(self):
        # If the torrent is in its initialization stage, the progress value
        # we get from ABCEngine won't reflect the download progress
        # 
        # Note: "moving data" is a third initialization status that is listed
        #       in the BitTornado source
        ######################################################################
        if not self.utility.abcquitting and self.torrent.connection.engine is not None:
            status = self.getStatusText()
            statuslist = [ self.utility.lang.get('waiting'), 
                           self.utility.lang.get('checkingdata'), 
                           self.utility.lang.get('allocatingspace'), 
                           self.utility.lang.get('movingdata') ]
            if (status in statuslist):
                return True
        return False
        
    def isDoneUploading(self):
        finished = False
        
        uploadoption = self.torrent.connection.getSeedOption('uploadoption')
        
        # If the file isn't finished, or it's set to unlimited upload
        if self.torrent.files.progress != 100.0:
            pass

        elif (uploadoption == "1"):
            uploadtimes = self.torrent.connection.getTargetSeedingTime()
            
            if uploadtimes < 1800: #Cheat people edit config file..unlimited upload!
                pass
            elif self.torrent.connection.seedingtime >= uploadtimes:
                finished = True
        
        elif (uploadoption == "2"
            and self.torrent.getColumnValue(12) >= float(self.torrent.connection.getSeedOption('uploadratio'))):
            finished = True
            
        # Also mark as completed in case it wasn't for some reason
        if finished:
            self.value = STATUS_FINISHED
            self.completed = True
            
        elif self.value == STATUS_FINISHED:
            # Was finished before, but isn't now
            self.value = STATUS_QUEUE
            
        self.torrent.updateColumns([COL_BTSTATUS]) #GUI
        
        return finished
        
    def updateStatus(self, value, update = True):
        if value != self.value:
            self.value = value
            #print 'Status updated to', self.getStatusText()
            if update:
                self.torrent.torrentconfig.writeStatus()
                        
    def checkJustFinished(self):
        "Check if the torrent finished between the last check and now"
        
        status = self.getStatusText()
        if status in [self.utility.lang.get('completedseeding'), self.utility.lang.get('completed')] and \
            self.lastCheckFinished != status:
            self.lastCheckFinished = status
            #print 'check finished: now: (%s) %s, before: (%s) %s' % (self.value, self.getStatusText(), self.lastCheckFinished, self.getStatusText(self.lastCheckFinished))
            #print 'Torrent just finished'
            # inform library that download is finished so that it sorts
            libraryPanel = self.torrent.libraryPanel
            if libraryPanel:
               libraryPanel.abctorrentFinished(self.torrent.torrent_hash)
        
        self.lastCheckFinished = status
        
        
    def setHaveDigest(self,havedigest):
        self.havedigest = havedigest
        
    def getHaveDigest(self):
        return self.havedigest
    
    def getStatus (self):
        return self.value        
