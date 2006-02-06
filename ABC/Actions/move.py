import sys
import os
import wx

from shutil import copy, move

from ABC.Actions.actionbase import ABCAction
from Utility.helpers import stopTorrentsIfNeeded

from Utility.constants import * #IGNORE:W0611
      
        
################################
# 
################################
class MoveUp(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           'moveup.bmp', 
                           'moveup')
        
    def action(self, event = None):
        list = self.utility.window.getSelectedList()
        selected = list.getSelected()
        
        newloc = self.utility.queue.MoveItems(selected, -1)
        list.updateSelected(selected, newloc)
        

################################
# 
################################
class MoveDown(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           'movedown.bmp', 
                           'movedown')
        
    def action(self, event = None):
        list = self.utility.window.getSelectedList()
        selected = list.getSelected()

        newloc = self.utility.queue.MoveItems(selected, 1)
        list.updateSelected(selected, newloc)
        
        
################################
# 
################################
class MoveBottom(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           'movebottom.bmp', 
                           'movebottom')
        
    def action(self, event = None):
        list = self.utility.window.getSelectedList()
        selected = list.getSelected()
               
        if selected:
            numberSelected = len(selected)
            movelist = []
            for i in range(numberSelected):
                movelist.append(selected[i] - i)
            self.utility.queue.MoveItemsBottom(movelist)
            
            listSize = list.GetItemCount()
            newloc = range(listSize - 1, listSize - numberSelected - 1, -1)
            list.updateSelected(selected, newloc)
        

################################
# 
################################
class MoveTop(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           'movetop.bmp', 
                           'movetop')
        
    def action(self, event = None):
        list = self.utility.window.getSelectedList()
        selected = list.getSelected()
       
        if selected:
            numberSelected = len(selected)
            movelist = []
            for i in range(numberSelected):
                movelist.append(selected[numberSelected - i - 1] + i)
            self.utility.queue.MoveItemsTop(movelist)

            list.updateSelected(selected, range(numberSelected))


################################
# 
################################
class ClearCompleted(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           'clearcompleted.bmp', 
                           'clearallcompleted', 
                           menudesc = 'menu_clearcompleted')
        
    def action(self, event = None):
        list = self.utility.window.getSelectedList()
        if self.utility.queue.ratemanager.doneflag.isSet():
            # RateManager is running : We record the event
            # It will be run after these tasks have completed
            if list.IsEnabled():
                list.Disable()
            self.utility.window.postponedevents.append((self.action, event))
        else:
            self.utility.queue.clearAllCompleted()
            list.SetFocus()
          
            
################################
# 
################################
class AddTorrentFile(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           'addtorrent.bmp', 
                           'addtorrentfile_short', 
                           menudesc = 'menu_addtorrentfile')
                       
    def action(self, event = None):
        self.utility.queue.addtorrents.AddTorrentFile()


################################
# 
################################
class AddTorrentNonDefault(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           'addtorrentnondefault.bmp', 
                           'addtorrentfiletonondefault_short', 
                           menudesc = 'menu_addtorrentnondefault')
                           
    def action(self, event = None):
        self.utility.queue.addtorrents.AddTorrentNoneDefault()


################################
# 
################################
class AddTorrentURL(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           'addtorrenturl.bmp', 
                           'addtorrenturl_short', 
                           menudesc = 'menu_addtorrenturl')
                           
    def action(self, event = None):
        self.utility.queue.addtorrents.AddTorrentLink()
               

################################
# 
################################
class Remove(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           'delete.bmp', 
                           'tb_delete_short', 
                           longdesc = 'tb_delete_long', 
                           menudesc = 'rRemoveTorrent')
                           
    def action(self, event = None, removefiles = False):
        list = self.utility.window.getSelectedList()
        if self.utility.queue.ratemanager.doneflag.isSet():
            # RateManager is running : We record the event
            # It will be run after these tasks have completed
            if list.IsEnabled():
                list.Disable()
            if removefiles:
                self.utility.window.postponedevents.append((self.utility.actions[ACTION_REMOVEFILE].action, event))
            else:
                self.utility.window.postponedevents.append((self.action, event))
            return

        torrentselected = list.getTorrentSelected(reverse = True)
        if not torrentselected:
            return

        if removefiles:
            # Display Dialog Warning
            ##############################
            dialog = wx.MessageDialog(None, 
                                      self.utility.lang.get('confirmdeletefile'), 
                                      self.utility.lang.get('warning'), 
                                      wx.ICON_WARNING|wx.YES_NO)
            result = dialog.ShowModal()
            dialog.Destroy()
            if(result == wx.ID_NO):            
                return

        firstselected = torrentselected[-1].listindex

        # Stop all the files first
        self.utility.actionhandler.procSTOP(torrentselected)

        # Remove the torrents from the list
        # (and remove files if necessary)
        self.utility.actionhandler.procREMOVE(torrentselected, removefiles)
        
        listsize = list.GetItemCount() - 1
        
        if listsize >= 0:
            if firstselected >= listsize:
                list.Select(listsize)
            else:
                list.Select(firstselected)
        list.SetFocus()
        

################################
# 
################################
class RemoveFile(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           menudesc = 'rRemoveTorrentandFile')
                           
    def action(self, event = None):
        self.utility.actions[ACTION_REMOVE].action(removefiles = True)
                
        
################################
# 
################################
class ExtractFromList(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           menudesc = 'rextractfromlist')
                           
    def action(self, event = None):
        list = self.utility.window.getSelectedList()
        
        torrentselected = list.getTorrentSelected(reverse = True)
        if not torrentselected:
            return

        # All selected torrents must be inactive to proceed
        inactivestopped = stopTorrentsIfNeeded(torrentselected)
        if not inactivestopped:
            return

        firstselected = torrentselected[-1].listindex

        # Choose the destination folder
        dialog = wx.DirDialog(None, 
                              self.utility.lang.get('choosenewlocation'), 
                              '', 
                              style = wx.DD_DEFAULT_STYLE | wx.DD_NEW_DIR_BUTTON)
        result = dialog.ShowModal()
        destfolder = dialog.GetPath()
        dialog.Destroy()
        
        if result != wx.ID_OK:
            return

        removelist = []
        
        for ABCTorrentTemp in torrentselected:
            filename = os.path.split(ABCTorrentTemp.src)[1]
            destname = os.path.join(destfolder, filename)
            # Check if the file to be moved already exists in destination folder
            fileexists = os.access(destname, os.F_OK)
            if fileexists:
                message = "Torrent : " + ABCTorrentTemp.filename + \
                          "\n File : " + filename + "\n" + self.utility.lang.get('extracterrorduplicatemsg')
                dialog = wx.MessageDialog(None, 
                                          message, 
                                          self.utility.lang.get('extracterrorduplicate'), 
                                          wx.YES_NO|wx.ICON_EXCLAMATION)
                result = dialog.ShowModal()
                dialog.Destroy()
                if(result == wx.ID_NO):
                    continue

            # Move the torrent file                        
            try:
                move(ABCTorrentTemp.src, destname)
            except:
                message = "Torrent : " + ABCTorrentTemp.filename + "\n File : " + filename + "\n" + self.utility.lang.get('extracterrormoving')
                dialog = wx.MessageDialog(None, 
                                          message, 
                                          self.utility.lang.get('error'), 
                                          wx.ICON_ERROR)
                dialog.ShowModal()
                dialog.Destroy()
            else:
                # If the move ended OK, delete the torrent from the list
                removelist.append(ABCTorrentTemp)

        self.utility.actionhandler.procREMOVE(removelist)

        listsize = list.GetItemCount() - 1
        if listsize >= 0:
            if firstselected >= listsize:
                list.Select(listsize)
            else:
                list.Select(firstselected)
        
        list.SetFocus()
        
        
################################
# 
################################
class CopyFromList(ABCAction):
    def __init__(self, utility):
        ABCAction.__init__(self, 
                           utility, 
                           menudesc = 'rcopyfromlist')
                           
    def action(self, event = None):
        list = self.utility.window.getSelectedList()
        
        torrentselected = list.getTorrentSelected(reverse = True)
        if not torrentselected:
            return

        # All selected torrents must be inactive to proceed
        inactivestopped = stopTorrentsIfNeeded(torrentselected)
        if not inactivestopped:
            return

        # Choose the destination folder
        dialog = wx.DirDialog(None, 
                              self.utility.lang.get('choosenewlocation'), 
                              '', 
                              style = wx.DD_DEFAULT_STYLE | wx.DD_NEW_DIR_BUTTON)
        result = dialog.ShowModal()
        destfolder = dialog.GetPath()
        dialog.Destroy()
        
        if result != wx.ID_OK:
            return
        
        for ABCTorrentTemp in torrentselected:
            filename = os.path.split(ABCTorrentTemp.src)[1]
            destname = os.path.join(destfolder, filename)
            # Check if the file to be moved already exists in destination folder
            fileexists = os.access(destname, os.F_OK)
            if fileexists:
                message = "Torrent : " + ABCTorrentTemp.filename + \
                          "\n File : " + filename + "\n" + self.utility.lang.get('extracterrorduplicatemsg')
                dialog = wx.MessageDialog(None, 
                                          message, 
                                          self.utility.lang.get('extracterrorduplicate'), 
                                          wx.YES_NO|wx.ICON_EXCLAMATION)
                result = dialog.ShowModal()
                dialog.Destroy()
                if(result == wx.ID_NO):
                    continue

            # Move the torrent file                        
            try:
                copy(ABCTorrentTemp.src, destname)
            except:
                message = "Torrent : " + ABCTorrentTemp.filename + "\n File : " + filename + "\n" + self.utility.lang.get('extracterrormoving')
                dialog = wx.MessageDialog(None, 
                                          message, 
                                          self.utility.lang.get('error'), 
                                          wx.ICON_ERROR)
                dialog.ShowModal()
                dialog.Destroy()
                
                