import sys
import wx
import os

from Dialogs.abcdetailframe import ABCDetailFrame
from Dialogs.setdestdlg import SetDestDialog

from Utility.constants import * #IGNORE:W0611

################################################################
#
# Class: TorrentDialogs
#
# Creates dialogs specific to an individual torrent
#
################################################################
class TorrentDialogs:
    def __init__(self, torrent):
        self.torrent = torrent
        self.utility = torrent.utility
        
        # Advanced details window
        self.details = None
    
    def stopIfNeeded(self, showDialog = True, singleTorrent = True):
        # If the torrent is already stopped, return True
        if not self.torrent.status.isActive():
            return True
            
        stopTorrent = False
            
        if showDialog:
            if singleTorrent:
                message = self.utility.lang.get('errorinactivesingle')
            else:
                message = self.utility.lang.get('errorinactivemultiple')
                
            dialog = wx.MessageDialog(None, 
                                      message, 
                                      self.utility.lang.get('warning'), 
                                      wx.YES_NO|wx.ICON_EXCLAMATION)
            result = dialog.ShowModal()
            dialog.Destroy()

            if result == wx.ID_YES:
                stopTorrent = True
                
        if not showDialog or stopTorrent:
            # Stop the torrent, then return True
            self.torrent.actions.stop()
            return True

        return False
    
    def changeDest(self, event = None, parent = None):
        if not self.stopIfNeeded():
            return

        # pop-up file dialog or dir dialog for new destination
        dialog = SetDestDialog(self.torrent, parent)
        dialog.ShowModal()
        dialog.Destroy()
       
    def setDestination(self, event = None):
        dest = self.torrent.files.dest

        sizetext = '(' + self.torrent.getColumnText(COL_SIZE) +')'
        if dest is None:
            # Use one set of strings if setting a location to start
            filetext = self.utility.lang.get('choosefiletosaveas') + sizetext
            dirtext = self.utility.lang.get('choosedirtosaveto') + sizetext
        else:
            # Use a different set of strings if we're setting a new location
            filetext = self.utility.lang.get('choosenewlocation') + sizetext
            dirtext = self.utility.lang.get('choosenewlocation') + sizetext
        
        defaultdir = self.utility.getLastDir("save")

        # What do we do if we don't have a default download location specified
        # and we call this from the webservice?
        ####################################################
        if self.torrent.files.isFile():   #1 file for this torrent
            dialog = wx.FileDialog(None, 
                                   filetext, 
                                   defaultdir, 
                                   self.torrent.files.filename, 
                                   self.utility.lang.get('allfileswildcard') + ' (*.*)|*.*', 
                                   wx.SAVE)
        else:   # Directory torrent
            dialog = wx.DirDialog(None, 
                                  dirtext, 
                                  defaultdir, 
                                  style = wx.DD_DEFAULT_STYLE | wx.DD_NEW_DIR_BUTTON)
        dialog.Raise()
        result = dialog.ShowModal()
        dialog.Destroy()
        if result != wx.ID_OK:
            return False, dest
        dest = dialog.GetPath()

        if self.torrent.files.isFile():
            # If a file, get the directory we saved the file in
            lastdir = os.path.dirname(dest)
        else:
            # If a directory, just use the directory
            lastdir = dest
        self.utility.lastdir['save'] = lastdir
                
        self.torrent.files.changeProcDest(dest)
        
        return True, dest
        
    def advancedDetails(self, event = None):
        print "advancedDetails", self
        if (self.details is not None):
            print "self.details is not None"
            try:
                self.details.Raise()
                return
            except:
                self.details.killAdv()
    
        self.details = ABCDetailFrame(self.torrent)
        