import sys
import wx

from time import time
from traceback import print_stack

from Utility.getscrapedata import ScrapeThread
from Utility.constants import * #IGNORE:W0611
from Tribler.Video.VideoPlayer import VideoPlayer


DEBUG = False

################################################################
#
# Class: TorrentActions
#
# Handles processing of most all the user-initiated actions
# on a torrent.
#
################################################################        
class TorrentActions:
    def __init__(self, torrent):
        self.torrent = torrent
        self.utility = torrent.utility
        
        self.lastgetscrape = 0
        
        self.oldstatus = None

    def scrape(self, faildialog = False, manualscrape = False):        
        # Manual Scraping should be done no more than once per minute
        if (manualscrape):
            if (time() - self.lastgetscrape < 60):
                if faildialog:
                    dlg = wx.MessageDialog(None, self.utility.lang.get('warningscrapelessthanmin'), self.utility.lang.get('error'), wx.ICON_ERROR)
                    dlg.ShowModal()
                    dlg.Destroy()
                return False
        # Automatic Scraping can be done as often as once an hour
        elif (self.lastgetscrape != 0) and ((time() - self.lastgetscrape) < 1200):
            # Scraping again too soon
            return False

        ScrapeThread(self.utility, self.torrent, manualscrape).start()
        
        self.lastgetscrape = time()
        
        return True
    
    # pause a torrent or release it,
    # returns True if we actually did something
    def pause(self, release = False):
        torrent = self.torrent
        
        # We need to release the torrent
        if release:
            return self.pauseResume()
        
        # Pause the torrent if it isn't already paused or queued
        if torrent.status.value == STATUS_PAUSE or not torrent.status.isActive():
            return False

        self.oldstatus = torrent.status.value

        torrent.status.updateStatus(STATUS_PAUSE)

#        if torrent.connection.engine is not None and torrent.connection.engine.dow is not None:
        if torrent.status.isActive():
            torrent.connection.engine.Pause()

        torrent.updateSingleItemStatus()
        return True
        
    def pauseResume(self):
        torrent = self.torrent
        
        if torrent.status.value != STATUS_PAUSE:
            return False

        torrent.status.updateStatus(self.oldstatus)

        # pause an active process
        ###########################################
        if torrent.status.isActive():
            torrent.connection.engine.dow.Unpause()
            return True

        return False

    # stop a single torrent, returns True if we actually did something
    def stop(self):
        torrent = self.torrent

        if torrent.get_on_demand_download():
            # We was VOD-ing
            videoplayer = VideoPlayer.getInstance()
            videoplayer.vod_stopped(torrent)

        if torrent.status.value != STATUS_STOP:
            # Save last stopped
            torrent.status.lastStopped = time()
            
        if torrent.status.isDoneUploading():
            return True
        
        if torrent.status.value == STATUS_STOP:
            return False
        
        torrent.connection.stopEngine(update = False)
        
        torrent.status.updateStatus(STATUS_STOP)
        
        torrent.updateSingleItemStatus()
        
        return True
        
    # Return True if we put something into queue
    def queue(self):
        torrent = self.torrent
        
        if torrent.status.isDoneUploading():
            # Might need to return True to show something happened
            return True

        # Do nothing if already queued, stopped, or done uploading
        if torrent.status.value == STATUS_QUEUE:
            return False

        torrent.connection.stopEngine(update = False)
        
        torrent.status.updateStatus(STATUS_QUEUE)
        
        torrent.updateSingleItemStatus()
        
        return True

    def resume(self, skipcheck = False):
        torrent = self.torrent
        
        ################### Resume for On-Hold State ###########################
        if torrent.status.value == STATUS_PAUSE:
            if DEBUG:
                print >>sys.stderr,"actions: resume: pause resume"
            return self.pauseResume()

        ################## Resume for Other inactive States ##############################
        
        # Don't resume if done uploading or currently active
        if torrent.status.isDoneUploading():
            if DEBUG:
                print >>sys.stderr,"actions: resume: done uploading"
            return True
        
        if torrent.status.isActive():
            if DEBUG:
                print >>sys.stderr,"actions: resume: is active"
            return False
            
        # If the file is complete and it's finished uploading,
        # don't need to resume
        if self.torrent.status.isDoneUploading():
            if DEBUG:
                print >>sys.stderr,"actions: resume: update single item"
            self.torrent.updateSingleItemStatus()
            # This may indicate that something has changed, so return True
            return True

        torrent.status.updateStatus(STATUS_QUEUE)
#        torrent.files.skipcheck = skipcheck
        
        torrent.connection.startEngine()
        if DEBUG:
            print >>sys.stderr,"actions: resume: started engine"
        return True

    def hashCheck(self):
        torrent = self.torrent
        
        # Don't need to do hashcheck if already checking
        if torrent.status.value == STATUS_HASHCHECK:
            return False

        self.oldstatus = torrent.status.value
        
#        # (if it's currently active, wait for it to stop)
#        torrent.connection.stopEngine(waitForThread = True)
        torrent.connection.stopEngine()
        
        torrent.connection.startEngine(STATUS_HASHCHECK)

        return True

        