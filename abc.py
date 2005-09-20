#########################################################################
# Author : Choopan RATTANAPOKA
# Description : Main ABC [Yet Another Bittorrent Client] python script.
#               you can run from source code by using
#               >python abc.py
#               need Python, WxPython in order to run from source code.
#########################################################################
import sys
import os
import wx
#import hotshot

from wxPython.lib.buttons import wxGenBitmapToggleButton
from threading import Thread, Semaphore
from shutil import copyfile, move
from webbrowser import open_new

from string import join as stjoin
from time import time, sleep
from traceback import print_exc
from cStringIO import StringIO

from BitTornado.zurllib import urlopen, quote, unquote

from interconn import ServerListener, ClientPassParam
from scheduler import ABCScheduler
from btmaketorrentgui import DownloadInfo
from webservice import WebDialog, WebListener

from Dialogs.closedialog import CloseDialog
from Dialogs.abcdetailframe import ABCDetailFrame
from Dialogs.aboutme import AboutMeDialog, VersionDialog
from Dialogs.abcoption import ABCOptionDialog
from Dialogs.localupload import LocalSettingDialog
if (sys.platform == 'win32'):
    from Dialogs.regdialog import RegCheckDialog

from Utility.utility import Utility
from Utility.constants import *

################################################################
# Class: FileDropTarget
#       To enable drag and drop for ABC list in main menu
################################################################
class FileDropTarget(wx.FileDropTarget): 
    def __init__(self, utility):
        # Initialize the wsFileDropTarget Object 
        wx.FileDropTarget.__init__(self) 
        # Store the Object Reference for dropped files 
        self.utility = utility
      
    def OnDropFiles(self, x, y, filenames):
        for filename in filenames:
            self.utility.AddTorrentFromFile(filename)
        return True

##############################################################
# Class : ABCList
#
# ABC List class that contains the torrent list
#
############################################################## 
class ABCList(wx.ListCtrl):
    def __init__(self, parent):
        style = wx.LC_REPORT|wx.LC_VRULES|wx.CLIP_CHILDREN
        wx.ListCtrl.__init__(self, parent, -1, style=style)
        
        self.utility = parent.utility
        
        dragdroplist = FileDropTarget(self.utility)
        self.SetDropTarget(dragdroplist)
        
        self.lastcolumnsorted = -1
        self.reversesort = False

        self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.Bind(wx.EVT_LIST_COL_END_DRAG, self.OnResizeColumn)
        self.Bind(wx.EVT_LIST_COL_RIGHT_CLICK, self.OnColRightClick)
        self.Bind(wx.EVT_LIST_COL_CLICK, self.OnColLeftClick)

        self.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.OnItemSelected)
        self.Bind(wx.EVT_LEFT_DCLICK, self.OnLeftDClick)

        self.loadColumns()
        
    def loadColumns(self):
        # Delete Old Columns (if they exist)
        #################################################
        numcol = self.GetColumnCount()
        for i in range(0, numcol):
            self.DeleteColumn(0)

        # Read status display
        ####################################
        
        # Columns that should be right-aligned:
        rightalign = [5, 9, 10, 11, 12, 17, 18, 19, 20]
        
        for rank in range(0, self.utility.guiman.getNumCol()):
            colid = self.utility.guiman.getIDfromRank(rank)
            if colid in rightalign:
                style = wx.LIST_FORMAT_RIGHT
            else:
                style = wx.LIST_FORMAT_LEFT
            text = self.utility.guiman.getTextfromRank(rank)
            width = self.utility.guiman.getValuefromRank(rank)
            # Don't allow a column to have a size of 0
            if width == 0:
                width = -1
            self.InsertColumn(rank, text, style, width)

    # Do thing when keys are pressed down
    def OnKeyDown(self, event):
        keycode = event.GetKeyCode()
        if event.CmdDown() and (keycode == 97 or keycode == 65):
            # Select all (Ctrl-A)
            self.selectAll()
        elif keycode == 399:
            self.OnItemSelected()
        
        event.Skip()

    # Save the width of the column that was just resized
    def OnResizeColumn(self, event):
        if self.utility.config.Read('savecolumnwidth', "boolean"):
            rank = event.GetColumn()
            width = self.GetColumnWidth(rank)
            colid = self.utility.guiman.getIDfromRank(rank)
            self.utility.config.Write("column" + str(colid) + "_width", width)
            self.utility.config.Flush()

    # Create a list of columns that are active/inactive
    def OnColRightClick(self, event):
        if not hasattr(self, "columnpopup"):
            self.makeColumnPopup()
            
        # Check off columns for all that are currently active
        for colid in range(4, self.utility.guiman.maxid):
            if self.utility.config.Read("column" + str(colid) + "_rank", "int") != -1:
                self.columnpopup.Check(777 + colid, True)
            else:
                self.columnpopup.Check(777 + colid, False)
        
        self.lastcolumnselected = event.GetColumn()
               
        self.PopupMenu(self.columnpopup, event.GetPosition())
        
    def OnColLeftClick(self, event):
        rank = event.GetColumn()
        colid = self.utility.guiman.getIDfromRank(rank)
        if colid == self.lastcolumnsorted:
            self.reversesort = not self.reversesort
        else:
            self.reversesort = False
        self.lastcolumnsorted = colid
        
        self.utility.queue.sortList(colid, self.reversesort)
        
    def makeColumnPopup(self):
        self.columnpopup = wx.Menu()
        
        for i in range(4, self.utility.guiman.maxid):
            text = self.utility.lang.get('column' + str(i) + '_text')
            self.columnpopup.Append(777 + i, text, text, wx.ITEM_CHECK)

        startid = 777 + 4
        endid = 777 + (self.utility.guiman.maxid - 1)

        self.Bind(wx.EVT_MENU, self.onSelectColumn, id=startid, id2=endid)

    def onSelectColumn(self, event):
        colid = event.GetId() - 777
        oldrank = self.utility.config.Read("column" + str(colid) + "_rank", "int")

        if oldrank > -1:
            # Column was deselected, don't show it now
            # (update ranks for the rest of the columns that appeared after it)
            for i in range (4, self.utility.guiman.maxid):
                temprank = self.utility.config.Read("column" + str(i) + "_rank", "int")
                if (i == colid):
                    self.utility.config.Write("column" + str(i) + "_rank", -1)
                elif (temprank > oldrank):
                    self.utility.config.Write("column" + str(i) + "_rank", temprank - 1)
                else:
                    self.utility.config.Write("column" + str(i) + "_rank", temprank)
        else:
            # Column was selected, need to show it
            # Put it after the closest column
            if hasattr(self, 'lastcolumnselected'):
                newrank = self.lastcolumnselected + 1
            # (just tack it on the end of the display)
            else:
                newrank = self.GetColumnCount()
            
            for i in range (4, self.utility.guiman.maxid):
                temprank = self.utility.config.Read("column" + str(i) + "_rank", "int")
                if (i == colid):
                    self.utility.config.Write("column" + str(i) + "_rank", newrank)
                elif (temprank >= newrank):
                    self.utility.config.Write("column" + str(i) + "_rank", temprank + 1)
                else:
                    self.utility.config.Write("column" + str(i) + "_rank", temprank)
        
        # Write changes to the config file and refresh the display
        self.utility.config.Flush()
        self.utility.frame.updateABCDisplay()
        
    def selectAll(self):
        self.updateSelected(select = range(0, self.GetItemCount()))

    def updateSelected(self, unselect = [], select = []):
        for index in unselect:
            self.SetItemState(index, 0, wx.LIST_STATE_SELECTED)
        for index in select:
            self.Select(index)
        self.SetFocus()

    def getSelected(self, firstitemonly = False, reverse = False):
        selected = []
        index = self.GetNextItem(-1, wx.LIST_NEXT_ALL, wx.LIST_STATE_SELECTED)
        while index != -1:
            selected.append(index)
            if (firstitemonly):
                return selected
            index = self.GetNextItem(index, wx.LIST_NEXT_ALL, wx.LIST_STATE_SELECTED)
        selected.sort()
        if reverse:
            selected.reverse()
        return selected

    def getTorrentSelected(self, firstitemonly = False, reverse = False):
        queue = self.utility.queue
        
        torrentselected = []
        for index in self.getSelected(firstitemonly, reverse):
            ABCTorrentTemp = queue.getABCTorrent(index = index)
            if ABCTorrentTemp is not None:
                torrentselected.append(ABCTorrentTemp)
        return torrentselected

    def OnItemSelected(self, event = None):
        if not hasattr(self, "popupmenu"):
            self.popupmenu = ABCPopupMenu(self.utility)

        selected = self.getTorrentSelected()
        if len(selected) == 0:
            return
            
        ABCTorrentTemp = selected[0]

        self.popupmenu.updatePriority(ABCTorrentTemp.prio)

        # Popup the menu.  If an item is selected then its handler
        # will be called before PopupMenu returns.
        if event is None:
            # use the position of the first selected item (key event)
            position = self.GetItemPosition(ABCTorrentTemp.listindex)
        else:
            # use the cursor position (mouse event)
            position = event.GetPosition()
        
        self.PopupMenu(self.popupmenu, position)

    def OnLeftDClick(self, event):
        event.Skip()
        self.utility.window.onDetails()

class ABCPopupMenu(wx.Menu):
    def __init__(self, utility):
        wx.Menu.__init__(self)
        
        self.utility = utility
        self.window = utility.window
        
        self.items = {}

        # Make a right-click menu
        ################################        
        self.items['resume'] = self.makePopup(self.window.onResume, 'rResume')
        self.items['stop'] = self.makePopup(self.window.onStop, 'rStop')
        self.items['pause'] = self.makePopup(self.window.onPause, 'rPause')
        self.items['queue'] = self.makePopup(self.window.onQueue, 'rQueue')
        self.items['hashcheck'] = self.makePopup(self.window.onHashCheck, 'rHashCheck')
        
        self.AppendSeparator()
        
        self.items['remove'] = self.makePopup(self.window.onRemove, 'rRemoveTorrent')
        self.items['removefile'] = self.makePopup(self.window.onRemoveFile, 'rRemoveTorrentandFile')
        self.items['extract'] = self.makePopup(self.window.onExtractFromList, 'rextractfromlist')
        self.items['clearmessage'] = self.makePopup(self.window.onClearMessage, 'rclearmessage')
        
        self.AppendSeparator()

        self.items['localupload'] = self.makePopup(self.window.onLocalSetting, 'rlocaluploadsetting')

        # Fix ID for Priority menu

        rpriorities = [ self.utility.lang.get('rhighest'), 
                        self.utility.lang.get('rhigh'), 
                        self.utility.lang.get('rnormal'), 
                        self.utility.lang.get('rlow'), 
                        self.utility.lang.get('rlowest') ]

        self.items['prioritysubmenu'] = wx.Menu()
        prioID = []
        for i in range(0, 5):
            newid = wx.NewId()
            prioID.append(newid)
            self.Bind(wx.EVT_MENU, self.window.onChangePrio, id = newid)
            priority = rpriorities[i]
            self.items['prioritysubmenu'].Append(newid, priority, priority, wx.ITEM_RADIO)
        self.items['prioID'] = prioID

        self.AppendMenu(-1, self.utility.lang.get('rpriosetting'), self.items['prioritysubmenu'])

        self.AppendSeparator()

        self.items['superseed'] = self.makePopup(self.window.onSuperSeed, 'rsuperseedmode')
        
        self.AppendSeparator()
        
        self.items['opendest'] = self.makePopup(self.window.onOpenDest, 'ropendest')
        self.items['changedest'] = self.makePopup(self.window.onChangeDownloadDest, 'rchangedownloaddest')
        
        self.AppendSeparator()
        
        self.items['scrape'] = self.makePopup(self.window.onDisplayScrape, 'rcurrentseedpeer')
        self.items['details'] = self.makePopup(self.window.onDetails, 'rtorrentdetail')

    def makePopup(self, event = None, label = ""):
        text = self.utility.lang.get(label)
        
        newid = wx.NewId()
        if event is not None:
            self.Bind(wx.EVT_MENU, event, id=newid)
        self.Append(newid, text)
        return newid
        
    def updatePriority(self, prio = None):
        if prio is None:
            prio = self.utility.config.Read('defaultpriority')
        
        oldid = self.items['prioID'][prio]
        self.items['prioritysubmenu'].Check(oldid, True)  

##############################################################
# Class : ABCPanel
#
# Main ABC Panel class
############################################################## 
class ABCPanel(wx.Panel):
    def __init__(self, parent, params):
        style = wx.CLIP_CHILDREN
        wx.Panel.__init__(self, parent, -1, style = style)

        #Debug Output.
        sys.stdout.write('Preparing GUI.\n');
        
        self.utility    = parent.utility
        self.utility.window = self
               
        # List of deleting torrents events that occur when the URM or the upload rate
        # distribution are running (in CyclicalTasks).
        # Such events are stored and then played when the URM and the upload rate distribution end.
        # postponedevents is a list of tupples : each tupple contains the method of ABCPanel to be called to
        # deal with the event and the event.
        self.postponedevents = []

        #Manual Bittorrent Adding UI
        ##############################
        colSizer = wx.BoxSizer(wx.VERTICAL)
                
        # Start the scheduler before creating the ListCtrl
        self.queue  = ABCScheduler(self.utility)

        # List Control Display UI
        ###############################
        self.list = ABCList(self)
        self.utility.list = self.list

        colSizer.Add(self.list, 1, wx.EXPAND|wx.ALL, 2)
        
        # Wait until after creating the list to start CyclicalTasks in the scheduler
        self.queue.CyclicalTasks()
        self.queue.InfrequentCyclicalTasks(False)

#        self.utility.bottomline = ABCBottomBar(self)
#
#        colSizer.Add(self.utility.bottomline, 0, wx.ALL|wx.EXPAND, 3)

        self.utility.bottomline2 = ABCBottomBar2(self)

        colSizer.Add(self.utility.bottomline2, 0, wx.ALL|wx.EXPAND, 3)
        
        self.SetSizer(colSizer)
        self.SetAutoLayout(True)
        
        self.list.SetFocus()

        # Read old list from torrent.lst
        ####################################
        self.queue.readTorrentList()

        # Start single instance server listenner
        ############################################
        self.serverlistener = ServerListener(self.utility)
        self.serverthread   = Thread(target = self.serverlistener.start)
        self.serverthread.setDaemon(True)
        self.serverthread.start()

        #if server start with params run it
        #####################################
        if params[0] != "":
            ClientPassParam(params[0])

        sys.stdout.write('GUI Complete.\n')
       
    def onDisplayScrape(self, event):
        # Multi-selected torrent scraping
        for ABCTorrentTemp in self.list.getTorrentSelected():
            ABCTorrentTemp.actions.scrape(faildialog = True, manualscrape = True)

    def onOpenDest(self, event):
        for ABCTorrentTemp in self.list.getTorrentSelected(firstitemonly = True):
            dest = ABCTorrentTemp.getProcDest(pathonly = True)
            if dest is None or not os.access(dest, os.R_OK):
                # Error
                dialog = wx.MessageDialog(None, self.utility.lang.get('filenotfound'), 
                                          self.utility.lang.get('error'), wx.ICON_ERROR)
                dialog.ShowModal()
                dialog.Destroy()
                self.list.SetFocus()
            else:
                Thread(target = open_new(dest)).start()
            
    def onChangeDownloadDest(self, event):
        changed = False
        
        for ABCTorrentTemp in self.list.getTorrentSelected(firstitemonly = True):
            stopped = False

            #torrent is active, error!
            if ABCTorrentTemp.isActive():
                dialog = wx.MessageDialog(None, 
                                          self.utility.lang.get('errorchangedestination') + 
                                          "\n\n" + 
                                          self.utility.lang.get('stoptorrent'), 
                                          self.utility.lang.get('warning'), wx.YES_NO|wx.ICON_EXCLAMATION)
                result = dialog.ShowModal()
                dialog.Destroy()
                if result == wx.ID_YES:
                    ABCTorrentTemp.actions.stop()
                    stopped = True
                else:
                    continue

            success, dest = ABCTorrentTemp.setDestination()
            if success:
                changed = True
            if stopped:
                ABCTorrentTemp.actions.resume()
                stopped = False
        
        if changed:
            self.queue.updateTorrentList()
            
        self.list.SetFocus()

    def onExtractFromList(self, event):
        torrentselected = self.list.getTorrentSelected(reverse = True)
        if not torrentselected:
            return

        firstselected = torrentselected[-1].listindex

        for ABCTorrentTemp in torrentselected:
            if ABCTorrentTemp.isActive():
                # Error : all selected torrents must be inactive to get extracted
                dialog = wx.MessageDialog(None, self.utility.lang.get('extracterrorinactive'), \
                                          self.utility.lang.get('error'), wx.ICON_ERROR)
                dialog.ShowModal()
                dialog.Destroy()
                return

        # Choose the destination folder
        dialog = wx.DirDialog(None, self.utility.lang.get('choosenewlocation'), '', \
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

        listsize = self.list.GetItemCount() - 1
        if listsize >= 0:
            if firstselected >= listsize:
                self.list.Select(listsize)
            else:
                self.list.Select(firstselected)
        
        self.list.SetFocus()

    def onClearMessage(self, event):
        torrentselected = self.list.getTorrentSelected()
        for ABCTorrentTemp in torrentselected:
            # For all torrents, active and inactive, we erase both the list and the message from the engine.
            # This is to avoid active torrent to be erased with a little delay (up to 2 seconds) in the list
            # by the refresh routine.
            ABCTorrentTemp.errormsg = ""
            ABCTorrentTemp.updateColumns([13])
            
        self.list.SetFocus()

    def onItemMoveTop(self, event):
        selected = self.list.getSelected()
       
        numberSelected=len(selected)
        if numberSelected != 0:
            movelist = []
            for i in range(numberSelected):
                movelist.append(selected[numberSelected - i - 1] + i)
            self.queue.MoveItemsTop(movelist)

            self.list.updateSelected(selected, range(numberSelected))

    def onItemMoveBottom(self, event):
        selected = self.list.getSelected()
               
        numberSelected=len(selected)
        if numberSelected != 0:
            movelist = []
            for i in range(numberSelected):
                movelist.append(selected[i] - i)
            self.queue.MoveItemsBottom(movelist)
            
            listSize = self.list.GetItemCount()
            newloc = range(listSize - 1, listSize - numberSelected - 1, -1)
            self.list.updateSelected(selected, newloc)           

    def onItemMoveUp(self, event):
        selected = self.list.getSelected()
        
        newloc = self.queue.MoveItems(selected, -1)
        self.list.updateSelected(selected, newloc)

    def onItemMoveDown(self, event):
        selected = self.list.getSelected()

        newloc = self.queue.MoveItems(selected, 1)
        self.list.updateSelected(selected, newloc)

    def onClearAllCompleted(self, event = None):
        if self.queue.urmdistribrunning:
            # URM or CalculateUpload are running : We record the event
            # It will be run after these tasks have completed
            if self.list.IsEnabled():
                self.list.Disable()
            self.postponedevents.append((self.onClearAllCompleted, event))
        else:
            self.queue.clearAllCompleted()
            self.list.SetFocus()

    def onSuperSeed(self, event = None):
        for ABCTorrentTemp in self.list.getTorrentSelected():
            ABCTorrentTemp.superSeed()

    def onResume(self, event = None):
        self.utility.actionhandler.procRESUME(self.list.getTorrentSelected())
        self.list.SetFocus()

    def onHashCheck(self, event = None):
        self.utility.actionhandler.procHASHCHECK(self.list.getTorrentSelected())
        self.list.SetFocus()

#    def onReseedResume(self, event = None):
#        self.onResume(event)
##        for ABCTorrentTemp in self.list.getTorrentSelected():
##            self.utility.actionhandler.procRESUME(ABCTorrentTemp, True) #Torrent, and skip hash flag
        
    def onPauseAll(self, event = None, release = True):       
        #Force All active to on-hold state
        ####################################
        if (event is None or event.IsChecked()):
            release = False

        self.utility.actionhandler.procPAUSE(release = release)

        self.list.SetFocus()

#    def onMode(self, event):
#        if (event.GetIsDown()):
#            # Automatic mode
#            self.utility.config.Write('mode', '1')
#            # The URM threshold exceeeding timers are reset
#            self.queue.ratemanager.urm_time['under'] = 0.0
#            self.queue.ratemanager.urm_time['over'] = 0.0
#            self.queue.Scheduler()
#        else:
#            # Manual mode
#            self.utility.config.Write('mode', '0')
#        # write current changes to disk
#        self.utility.config.Flush()
#        self.list.SetFocus()

    def onPause(self, event = None):
        self.utility.actionhandler.procPAUSE(self.list.getTorrentSelected())
        self.list.SetFocus()
           
    def onStopAll(self, event = None):
        self.utility.actionhandler.procSTOP()
        self.list.SetFocus()
            
    def onUnStopAll(self, event = None):
        self.utility.actionhandler.procUNSTOP()
        self.list.SetFocus()
        
    def onStop(self, event = None):
        self.utility.actionhandler.procSTOP(self.list.getTorrentSelected())
        self.list.SetFocus()

    def onQueue(self, event):
        self.utility.actionhandler.procQUEUE(self.list.getTorrentSelected())
        self.list.SetFocus()

    def onRemoveFile(self, event):
        self.onRemove(event, removefiles = True)
        
    def onRemove(self, event, removefiles = False):
        if self.queue.urmdistribrunning:
            # URM or CalculateUpload are running : We record the event
            # It will be run after these tasks have completed
            if self.list.IsEnabled():
                self.list.Disable()
            if removefiles:
                self.postponedevents.append((self.onRemoveFile, event))
            else:
                self.postponedevents.append((self.onRemove, event))
            return

        torrentselected = self.list.getTorrentSelected(reverse = True)
        if not torrentselected:
            return

        if removefiles:
            # Display Dialog Warning
            ##############################
            dialog = wx.MessageDialog(None, self.utility.lang.get('confirmdeletefile'), 
                                  self.utility.lang.get('warning'), wx.ICON_WARNING|wx.YES_NO)
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
        
        listsize = self.list.GetItemCount() - 1
        
        if listsize >= 0:
            if firstselected >= listsize:
                self.list.Select(listsize)
            else:
                self.list.Select(firstselected)
        self.list.SetFocus()
       
    def onChangePrio(self, event):
        prioIDs = self.list.popupmenu.items['prioID']
        
        prio = 0
        for i in range(0, len(prioIDs)):
            if prioIDs[i] == event.GetId():
                prio = i
                break

        for ABCTorrentTemp in self.list.getTorrentSelected():
            ABCTorrentTemp.changePriority(prio)
        self.list.SetFocus()
        
    def onLocalSetting(self, event):
        torrentselected = self.list.getTorrentSelected()
        if torrentselected:
            dialog = LocalSettingDialog(self, torrentselected)
            dialog.ShowModal()
            dialog.Destroy()
        self.list.SetFocus()

    def onDetails(self, event = None):
        for ABCTorrentTemp in self.list.getTorrentSelected():
            if (ABCTorrentTemp.detail_adr is not None):
                ABCTorrentTemp.detail_adr.killAdv()
    
            ABCTorrentTemp.detail_adr = ABCDetailFrame(ABCTorrentTemp)

# Generic statusbar class
class ABCBar(wx.ToolBar):
    def __init__(self, parent, style = None, hspacing = 0, vspacing = 0):
        self.parent = parent
        self.utility = self.parent.utility
        
        self.hspacing = hspacing
        self.vspacing = vspacing
        self.firsttime = True
        
        if style is None:
            style = wx.TB_HORIZONTAL | wx.NO_BORDER | wx.TB_FLAT | wx.TB_NODIVIDER
        wx.ToolBar.__init__(self, parent, -1, style = style)

    def addToolbarIcon(self, event, bitmap, shortdesc, longdesc = None, kind = None, bitmap2 = None):
        if longdesc is None:
            longdesc = shortdesc
        bitmap1 = self.utility.makeBitmap(bitmap)
        if (self.firsttime):
            #Find size of images so it will be dynamics
            self.SetToolBitmapSize(wx.Size(bitmap1.GetWidth() + self.hspacing, bitmap1.GetHeight() + self.vspacing))
            self.firsttime = False
        
        shorttext = self.utility.lang.get(shortdesc)
        longtext = self.utility.lang.get(longdesc)
        
        if kind is None:
            tool = self.AddSimpleTool(-1, bitmap1, shortHelpString = shorttext, longHelpString = longtext)
        else:
            if bitmap2 != None:
                bitmapalt = self.utility.makeBitmap(bitmap2)
            else:
                bitmapalt = wx.NullBitmap
            tool = self.AddCheckTool(-1, bitmap1, bmpDisabled = bitmapalt, shortHelp = shorttext, longHelp = longtext)
            
        if event is not None:
            self.Bind(wx.EVT_TOOL, event, tool)
        
        return tool
       
    def makeBitmapButton(self, bitmap, tooltip, event, trans_color = wx.Colour(200, 200, 200), toggle = False, bitmapselected = None):
        tooltiptext = self.utility.lang.get(tooltip)
        
        button_bmp = self.utility.makeBitmap(bitmap, trans_color)
        if bitmapselected:
            buttonselected_bmp = self.utility.makeBitmap(bitmapselected, trans_color)
            
        ID_BUTTON = wx.NewId()
        if (toggle):
            button_btn = wxGenBitmapToggleButton(self, ID_BUTTON, None, size=wx.Size(button_bmp.GetWidth() + 4, button_bmp.GetHeight() + 4), style = wx.NO_BORDER)
            button_btn.SetBitmapLabel(button_bmp)
            if bitmapselected:
                button_btn.SetBitmapSelected(buttonselected_bmp)
            else:
                button_btn.SetBitmapSelected(button_bmp)
        else:
            button_btn = wx.BitmapButton(self, ID_BUTTON, button_bmp, size=wx.Size(button_bmp.GetWidth()+18, button_bmp.GetHeight()+4))
        button_btn.SetToolTipString(tooltiptext)
        self.Bind(wx.EVT_BUTTON, event, button_btn)
        return button_btn

class ABCBottomBar2(wx.Panel):
    def __init__(self, parent):
        self.parent = parent
        self.utility = self.parent.utility
        
        wx.Panel.__init__(self, parent, -1)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # New option buttons
        ##################################
        
        self.utility.bottomline = ABCBottomBar(self, self.parent)

        sizer.Add(self.utility.bottomline, 0, wx.ALIGN_CENTER_VERTICAL)

        # Queue
        self.numsimtext = wx.SpinCtrl(self, size = wx.Size(60, -1))
        self.Bind(wx.EVT_SPINCTRL, self.changeNumSim, self.numsimtext)
        self.Bind(wx.EVT_TEXT, self.changeNumSim, self.numsimtext)

        sizer.Add(wx.StaticText(self, -1, self.utility.lang.get('tb_maxsim')), 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 10)
        self.queuecurrent = wx.StaticText(self, -1, "", size = wx.Size(20, -1))
        sizer.Add(self.queuecurrent, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
        sizer.Add(wx.StaticText(self, -1, " / "), 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
        sizer.Add(self.numsimtext, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)

        self.changeNumSim()

        # URM
        self.urmspinner = wx.SpinCtrl(self, size = wx.Size(60, -1))
        self.Bind(wx.EVT_SPINCTRL, self.changeURM, self.urmspinner)
        self.Bind(wx.EVT_TEXT, self.changeURM, self.urmspinner)
        
        self.urmlabel = wx.StaticText(self, -1, self.utility.lang.get('tb_urm'))
        self.urmcurrent = wx.StaticText(self, -1, "", size = wx.Size(20, -1))
        sizer.Add(self.urmlabel, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 10)
        sizer.Add(self.urmcurrent, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
        self.urmdivider = wx.StaticText(self, -1, " / ")
        sizer.Add(self.urmdivider, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
        sizer.Add(self.urmspinner, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)

        self.changeURM()
        
#        kbs = self.utility.lang.get('KB') + "/" + self.utility.lang.get('l_second')
#        
#        # Download
#        self.downspinner = wx.SpinCtrl(self, size = wx.Size(60, -1))
#        self.Bind(wx.EVT_SPINCTRL, self.changeDown, self.downspinner)
#        self.Bind(wx.EVT_TEXT, self.changeDown, self.downspinner)
#
#        sizer.Add(wx.StaticText(self, -1, "Down:"), 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 10)
#        self.downcurrent = wx.StaticText(self, -1,  "", size = wx.Size(20, -1))
#        sizer.Add(self.downcurrent, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
#        sizer.Add(wx.StaticText(self, -1, " / "), 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
#        sizer.Add(self.downspinner, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
#        sizer.Add(wx.StaticText(self, -1, kbs), 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
#
#        self.changeDown()        
#        
#        # Upload
#        self.upspinner = wx.SpinCtrl(self, size = wx.Size(60, -1))
#        self.Bind(wx.EVT_SPINCTRL, self.changeUp, self.upspinner)
#        self.Bind(wx.EVT_TEXT, self.changeUp, self.upspinner)
#
#        sizer.Add(wx.StaticText(self, -1, "Up:"), 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 10)
#        self.upcurrent = wx.StaticText(self, -1,  "", size = wx.Size(20, -1))
#        sizer.Add(self.upcurrent, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
#        sizer.Add(wx.StaticText(self, -1, " / "), 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
#        sizer.Add(self.upspinner, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
#        sizer.Add(wx.StaticText(self, -1, kbs), 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
#
#        self.changeUp()
        
        self.SetSizerAndFit(sizer)

#    def changeDown(self, event = None):
#        if event is None:
#            self.downspinner.SetRange(0, 9999)
#            self.downspinner.SetValue(self.utility.ratemanager.MaxRate("down"))
#            self.downcurrent.SetLabel(str(self.utility.queue.totals['download']))
#            return
#        
#    def changeUp(self, event = None):
#        if event is None:
#            self.upspinner.SetRange(0, 9999)
#            self.upspinner.SetValue(self.utility.ratemanager.MaxRate("up"))
#            self.upcurrent.SetLabel(str(self.utility.queue.totals['upload']))
#            return
#            
#        # Check which upload value we're using
#        # (seeding or downloading)

    def changeURM(self, event = None):
        if event is None:
            urmenabled = self.utility.config.Read('urm') == '1'
            self.urmlabel.Enable(urmenabled)
            self.urmcurrent.Enable(urmenabled)
            self.urmdivider.Enable(urmenabled)
            self.urmspinner.Enable(urmenabled)
            self.urmcurrent.SetLabel(str(self.utility.queue.counters["urm"]))
            self.urmspinner.SetRange(0, 1000)
            self.urmspinner.SetValue(self.utility.config.Read('urmmaxtorrent', "int"))
            return
            
        currentval = self.utility.config.Read('urmmaxtorrent')
        newval = self.urmspinner.GetValue()
        
        urmmin = self.urmspinner.GetMin()
        urmmax = self.urmspinner.GetMax()
        if newval < urmmin:
            newval = urmmin
            self.urmspinner.SetValue(urmmin)
        elif newval > urmmax:
            newval = urmmax
            self.urmspinner.SetValue(urmmax)
        if newval > 1000:
            newval = 1000
            
        if currentval != newval:
            self.utility.config.Write('urmmaxtorrent', newval)
            self.utility.config.Flush()
            
            if event is not None:
                self.utility.queue.updateAndInvoke(updateList = False)
            
    def changeNumSimBounds(self):
        minport = self.utility.config.Read('minport', "int")
        maxport = self.utility.config.Read('maxport', "int")
        numports = maxport - minport + 1
        
        if self.utility.config.Read('urm') == '1':
            numports = numports - self.utility.config.Read('urmmaxtorrent', "int")
        
        if numports < 0:
            numports = 0
        if numports > 1000:
            numports = 1000
        
        self.numsimtext.SetRange(0, numports)
    
    def changeNumSim(self, event = None):
        if event is None:
            self.changeNumSimBounds()
            self.queuecurrent.SetLabel(str(self.utility.queue.counters["currentproc"] - self.utility.queue.counters['urm']))
            self.numsimtext.SetValue(self.utility.config.Read('numsimdownload', "int"))
            return
            
        currentval = self.utility.config.Read('numsimdownload')
        newval = self.numsimtext.GetValue()
        
        minsim = self.numsimtext.GetMin()
        maxsim = self.numsimtext.GetMax()
        if newval < minsim:
            newval = minsim
            self.numsimtext.SetValue(minsim)
        elif newval > maxsim:
            newval = maxsim
            self.numsimtext.SetValue(maxsim)
        if newval > 1000:
            newval = 1000
        
        if currentval != newval:
            self.utility.config.Write('numsimdownload', newval)
            self.utility.config.Flush()
            
            if event is not None:
                self.utility.queue.updateAndInvoke(updateList = False)

class ABCBottomBar(ABCBar):
    def __init__(self, windowparent, parent):
        self.parent = parent
        self.utility = self.parent.utility
        
        style = wx.TB_HORIZONTAL | wx.NO_BORDER | wx.TB_FLAT | wx.TB_NODIVIDER
        ABCBar.__init__(self, windowparent, style = style, hspacing = 5)
        
        # New option buttons
        ##################################

        self.addToolbarIcon(parent.onItemMoveUp, 'moveup.bmp', 'moveup')
        self.addToolbarIcon(parent.onItemMoveDown, 'movedown.bmp', 'movedown')
        self.addToolbarIcon(parent.onItemMoveTop, 'movetop.bmp', 'movetop')
        self.addToolbarIcon(parent.onItemMoveBottom, 'movebottom.bmp', 'movebottom')
        self.AddSeparator()
        self.addToolbarIcon(parent.onClearAllCompleted, 'clearcompleted.bmp', 'clearallcompleted')
        self.AddSeparator()
        self.addToolbarIcon(parent.onPauseAll, 'pauseall.bmp', 'pauseall', kind = wx.ITEM_CHECK)
        self.addToolbarIcon(parent.onStopAll, 'stopall.bmp', 'stopall')
        self.addToolbarIcon(parent.onUnStopAll, 'unstopall.bmp', 'unstopall')
        self.AddSeparator()

        self.webbutton = self.makeBitmapButton('webservoff.bmp', 'inactive', self.toggleWebservice, toggle = True, bitmapselected = 'webservon.bmp')
        self.AddControl(self.webbutton)
        
        self.AddSeparator()
        
##        modebutton = self.makeBitmapButton('modemanual.bmp', 'mode', self.onMode, toggle = True, bitmapselected = 'modeauto.bmp')
##        bottomline.Add(modebutton, -1, wx.ALIGN_CENTER) 
##        bottomline.Add(wx.StaticText(self, -1, "    "), -1, wx.ALIGN_CENTER)
       
#        # Set mode button in correct state
#        if self.utility.config.Read('mode') == '1':
#            modebutton.SetValue(True)
#        else:
#            modebutton.SetValue(False)

        self.Realize()

        self.Fit()

#    def nullFunc(self, event = None):
#        # Dummy function here for testing
#        pass
        
    def toggleWebservice(self, event = None):
        webserver = self.utility.webserver
        
        if webserver.active:
            webserver.stop()
        else:
            webserver.start()

class ABCStatusBar(wx.StatusBar):
    def __init__(self, parent):
        wx.StatusBar.__init__(self, parent, -1)
        self.SetFieldsCount(9)
        self.SetStatusWidths([-1, 45, 35, 35, 35, 35, 50, 120, 120])
   
##############################################################
# Class : ABCTaskBarIcon
#
# Task Bar Icon
############################################################## 
class ABCTaskBarIcon(wx.TaskBarIcon):
    def __init__(self, parent):
        wx.TaskBarIcon.__init__(self)
        
        self.utility = parent.utility
        
        self.TBMENU_RESTORE = wx.NewId()
        self.ID_STOPALL = wx.NewId()
        self.ID_UNSTOPALL = wx.NewId()

        # setup a taskbar icon, and catch some events from it
        self.Bind(wx.EVT_TASKBAR_LEFT_DCLICK, parent.onTaskBarActivate)
        self.Bind(wx.EVT_MENU, parent.onTaskBarActivate, id = self.TBMENU_RESTORE)
        self.Bind(wx.EVT_MENU, parent.OnMenuExit, id = wx.ID_CLOSE)
        self.Bind(wx.EVT_MENU, self.utility.window.onStopAll, id = self.ID_STOPALL)
        self.Bind(wx.EVT_MENU, self.utility.window.onUnStopAll, id = self.ID_UNSTOPALL)
        
        self.updateIcon()
        
    def updateIcon(self):
        remove = True
        
        mintray = self.utility.config.Read('mintray', "int")
        if (mintray >= 2) or ((mintray >= 1) and self.utility.frame.IsIconized()):
            remove = False
        
        if remove and self.IsIconInstalled():
            self.RemoveIcon()
        elif not remove and not self.IsIconInstalled():
            self.SetIcon(self.utility.icon, "ABC")
        
    def CreatePopupMenu(self):        
        menu = wx.Menu()
        menu.Append(self.ID_STOPALL, self.utility.lang.get('menu_stopall'))
        menu.Append(self.ID_UNSTOPALL, self.utility.lang.get('menu_unstopall'))
        menu.AppendSeparator()
        menu.Append(self.TBMENU_RESTORE, self.utility.lang.get('showabcwindow'))
        menu.Append(wx.ID_CLOSE, self.utility.lang.get('close'))
        return menu

##############################################################
# Class : ABCToolBar
#
# Tool Bar
##############################################################         
class ABCToolBar(ABCBar):
    def __init__(self, parent):
        style = wx.TB_HORIZONTAL | wx.NO_BORDER | wx.TB_FLAT | wx.TB_TEXT | wx.CLIP_CHILDREN
        ABCBar.__init__(self, parent, style = style)
        
        self.utility = parent.utility
        
        self.makeToolBar()

    def makeToolBar(self):
        window = self.utility.window
        
        ###############################################
        # Add Tool Bar
        ###############################################
        self.addToolbarIcon(self.utility.AddTorrentFile, 
                            'addtorrent.bmp', 
                            'addtorrentfile_short')
        self.addToolbarIcon(self.utility.AddTorrentNoneDefault, 
                            'addtorrentnondefault.bmp', 
                            'addtorrentfiletonondefault_short')
        self.addToolbarIcon(self.utility.AddTorrentLink, 
                            'addtorrenturl.bmp', 
                            'addtorrenturl_short')
        self.AddSeparator()
        self.addToolbarIcon(window.onResume, 
                            'resume.bmp', 
                            'tb_resume_short', 
                            'tb_resume_long')
#        self.addToolbarIcon(window.onReseedResume,
#                            'reseedresume.bmp',
#                            'tb_reseedresume_short',
#                            'tb_reseedresume_long')
        self.addToolbarIcon(window.onPause, 
                            'pause.bmp', 
                            'tb_pause_short', 
                            'tb_pause_long')
        self.addToolbarIcon(window.onStop, 
                            'stop.bmp', 
                            'tb_stop_short', 
                            'tb_stop_long')
        self.addToolbarIcon(window.onQueue, 
                            'queue.bmp', 
                            'tb_queue_short', 
                            'tb_queue_long')
        self.addToolbarIcon(window.onRemove, 
                            'delete.bmp', 
                            'tb_delete_short', 
                            'tb_delete_long')
        self.AddSeparator()
        self.addToolbarIcon(window.onDisplayScrape, 
                            'currentseedpeer.bmp', 
                            'tb_spy_short', 'tb_spy_long')
        self.addToolbarIcon(window.onDetails, 
                            'torrentdetail.bmp', 
                            'tb_torrentdetail_short', 
                            'tb_torrentdetail_long')

        self.Realize()

class ABCMenuBar(wx.MenuBar):
    def __init__(self, parent):
        self.utility = parent.utility
        
        wx.MenuBar.__init__(self)
        
        # Create File Menu
        menu = wx.Menu()
        
        addmenu = wx.Menu()
        
        addmenu.Append(parent.registerMenuEvent(self.utility.AddTorrentFile), self.utility.lang.get('menu_addtorrentfile'))
        addmenu.Append(parent.registerMenuEvent(self.utility.AddTorrentNoneDefault), self.utility.lang.get('menu_addtorrentnondefault'))
        addmenu.Append(parent.registerMenuEvent(self.utility.AddTorrentLink), self.utility.lang.get('menu_addtorrenturl'))
        
        menu.AppendMenu(-1, self.utility.lang.get('menu_addtorrent'), addmenu)
        
        menu.Append(parent.registerMenuEvent(parent.OnMenuABCOption), self.utility.lang.get('menuabcpreference'), self.utility.lang.get('menuabcpreferencemsg'))
        menu.AppendSeparator()
        menu.Append(wx.ID_CLOSE, self.utility.lang.get('menuexit'), self.utility.lang.get('menuexitmsg'))

        self.Append(menu, self.utility.lang.get('menu_file'))
        
        # Create Actions Menu
        
        actions = wx.Menu()
        
        actions.Append(parent.registerMenuEvent(self.utility.window.onStopAll), self.utility.lang.get('menu_stopall'))
        actions.Append(parent.registerMenuEvent(self.utility.window.onUnStopAll), self.utility.lang.get('menu_unstopall'))
        actions.Append(parent.registerMenuEvent(self.utility.window.onClearAllCompleted), self.utility.lang.get('menu_clearcompleted'))
        
        self.Append(actions, self.utility.lang.get('menuaction'))

        # Create Tools Menu
        menutool = wx.Menu()

        menutool.Append(parent.registerMenuEvent(parent.OnMakeTorrent), self.utility.lang.get('menucreatetorrent'), self.utility.lang.get('menucreatetorrentmsg'))
        menutool.Append(parent.registerMenuEvent(parent.OnWebService), self.utility.lang.get('menuwebinterfaceservice'), self.utility.lang.get('menuwebinterfaceservicemsg'))

        self.Append(menutool, self.utility.lang.get('menutools'))

        # Create Advanced Menu
        menuadv = wx.Menu()
        
        menuadv.Append(parent.registerMenuEvent(parent.OnCheckLatestVersion), self.utility.lang.get('menuchecklatestversion'), self.utility.lang.get('menuchecklatestversionmsg'))       
        menuadv.Append(parent.registerMenuEvent(parent.OnMenuAbout), self.utility.lang.get('menuaboutabc'), self.utility.lang.get('menuaboutabcmsg'))

        self.Append(menuadv, self.utility.lang.get('menuversion'))

##############################################################
# Class : ABCFrame
#
# Main ABC Frame class that contains menu and menu bar management
# and contains ABCPanel
#
############################################################## 
class ABCFrame(wx.Frame):
    def __init__(self, ID, params, utility):
        self.utility = utility
        self.utility.frame = self
        
        title = self.utility.lang.get('title') + \
                " " + \
                self.utility.lang.get('version')
        
        # Get window size and position from config file
        size, position = self.getWindowSettings()
        style = wx.DEFAULT_FRAME_STYLE | wx.CLIP_CHILDREN
        wx.Frame.__init__(self, None, ID, title, position, size, style = style)
        
        self.tbicon = None

        self.abc_sb = ABCStatusBar(self)
        self.SetStatusBar(self.abc_sb)

        try:
            self.SetIcon(self.utility.icon)
        except:
            pass

        # Don't update GUI as often when iconized
        self.GUIupdaterate_fast = 0.5
        self.GUIupdaterate_slow = 2
        self.GUIupdaterate = self.GUIupdaterate_fast

        self.window = ABCPanel(self, params)

        # Menu Options
        ############################
        menuBar = ABCMenuBar(self)
        self.SetMenuBar(menuBar)

        self.tb = ABCToolBar(self)
        self.SetToolBar(self.tb)

        # Menu Events 
        ############################

        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)
        self.Bind(wx.EVT_MENU, self.OnMenuExit, id = wx.ID_CLOSE)

        # leaving here for the time being:
        # wxMSW apparently sends the event to the App object rather than
        # the top-level Frame, but there seemed to be some possibility of
        # change
        self.Bind(wx.EVT_QUERY_END_SESSION, self.OnCloseWindow)
        self.Bind(wx.EVT_END_SESSION, self.OnCloseWindow)
        
        try:
            self.tbicon = ABCTaskBarIcon(self)
        except:
            pass
        self.Bind(wx.EVT_ICONIZE, self.onIconify)
        self.Bind(wx.EVT_SET_FOCUS, self.onFocus)

        # Check webservice for autostart webservice
        #######################################################
        WebListener(self.utility)
        if self.utility.webconfig.Read("webautostart", "boolean"):
            self.utility.webserver.start()

        self.Show(True)
        
        # Check to see if ABC is associated with torrents
        #######################################################
        if (sys.platform == 'win32'):
            if self.utility.config.Read('associate', "boolean"):
                if not self.utility.regchecker.testRegistry():
                    dialog = RegCheckDialog(self)
                    dialog.ShowModal()
                    dialog.Destroy()

    def registerMenuEvent(self, event):
        newid = wx.NewId()
        self.Bind(wx.EVT_MENU, event, id = newid)
        return newid
        
    def onFocus(self, event):
        event.Skip()
        self.window.list.SetFocus()
        
#    def OnSize(self, event):
#        # This is here because the SpinCtrl in the bottom toolbar
#        # doesn't refresh properly when the window is resized
#        self.utility.bottomline.Refresh()
#        event.Skip()

    def OnWebService(self, event):
        dialog = WebDialog(self)
        dialog.ShowModal()
        dialog.Destroy()
        
    def OnMakeTorrent(self, event):
        maketorrent = DownloadInfo(self)
        maketorrent.frame.Show(True)

    def OnCheckLatestVersion(self, event):
        dialog = VersionDialog(self)
        dialog.ShowModal()
        dialog.Destroy()
#        txtcontent = ""
#        try :
#            h = urlopen('http://pingpong-abc.sourceforge.net/lastest_version.txt')
#            txtcontent = h.read()
#            h.close()
#            dialog = wx.MessageDialog(None, txtcontent , self.utility.lang.get('abclatestversion'), wx.OK|wx.ICON_INFORMATION)
#            dialog.ShowModal()
#            dialog.Destroy()
#
#        except :
#            dialog = wx.MessageDialog(None, self.utility.lang.get('cantconnectwebserver') , self.utility.lang.get('error'), wx.ICON_ERROR)
#            dialog.ShowModal()
#            dialog.Destroy()

    #######################################
    # minimize to tray bar control
    #######################################
    def onTaskBarActivate(self, event = None):
        self.Iconize(False)
        self.Show(True)
        self.Raise()
        
        if self.tbicon is not None:
            self.tbicon.updateIcon()

        self.window.list.SetFocus()

        # Resume updating GUI at normal speed
        self.GUIupdaterate = self.GUIupdaterate_fast

    def onIconify(self, event):
        if (self.utility.config.Read('mintray', "int") > 0
            and self.tbicon is not None):
            self.tbicon.updateIcon()
            self.Show(False)
#        else:
#            # If not minimizing to tray, default behavior is fine
        
        event.Skip()

        # Don't update GUI as often
        self.GUIupdaterate = self.GUIupdaterate_slow
        
    def getWindowSettings(self):
        width = self.utility.config.Read("window_width")
        height = self.utility.config.Read("window_height")
        try:
            size = wx.Size(int(width), int(height))
        except:
            size = wx.Size(710, 400)
        
        x = self.utility.config.Read("window_x")
        y = self.utility.config.Read("window_y")
        if (x == "" or y == ""):
            position = wx.DefaultPosition
        else:
            position = wx.Point(int(x), int(y))
            
        return size, position     
        
    def saveWindowSettings(self):
        width, height = self.GetSizeTuple()
        x, y = self.GetPositionTuple()
        self.utility.config.Write("window_width", width)
        self.utility.config.Write("window_height", height)
        self.utility.config.Write("window_x", x)
        self.utility.config.Write("window_y", y)

        self.utility.config.Flush()
        
    ################################
    # Display ABC Option Dialog
    ################################
    def OnMenuABCOption(self, event):
        dialog = ABCOptionDialog(self)
        dialog.ShowModal()
        dialog.Destroy()
        
    ################################
    # Display About me Dialog
    ################################
    def OnMenuAbout(self, event):
        dialog = AboutMeDialog(self)
        dialog.ShowModal()
        dialog.Destroy()
       
    ##################################
    # Close Program
    ##################################
    def OnMenuExit(self, event):
        self.Close()
               
    def OnCloseWindow(self, event):
        # Don't do anything if the event gets called twice for some reason
        if self.utility.abcquitting:
            return
        
        # Check to see if we can veto the shutdown
        # (might not be able to in case of shutting down windows)
        try:
            if event.CanVeto() and self.utility.config.Read('confirmonclose', "boolean"):
                dialog = wx.MessageDialog(None, self.utility.lang.get('confirmmsg'), self.utility.lang.get('confirm'), wx.OK|wx.CANCEL)
                result = dialog.ShowModal()
                dialog.Destroy()
                if result != wx.ID_OK:
                    event.Veto()
                    return
        except:
#            data = StringIO()
#            print_exc(file = data)
#            sys.stderr.write(data.getvalue())
            pass
            
        self.utility.abcquitting = True

        # Open up the "closing" dialog
        self.utility.closedlg = CloseDialog(self)
        self.utility.closedlg.Show(True)

        try:
            self.utility.webserver.stop()
        except:
#            data = StringIO()
#            print_exc(file = data)
#            sys.stderr.write(data.getvalue())
            pass

        try:
            # tell scheduler to close all active thread
            self.utility.queue.clearScheduler()
            self.utility.closedlg.Destroy()
        except:
#            data = StringIO()
#            print_exc(file = data)
#            sys.stderr.write(data.getvalue())
            pass

        try:
            # Restore the window before saving size and position
            # (Otherwise we'll get the size of the taskbar button and a negative position)
            self.onTaskBarActivate()
            self.saveWindowSettings()
        except:
#            data = StringIO()
#            print_exc(file = data)
#            sys.stderr.write(data.getvalue())
            pass

        try:
            if self.tbicon is not None:
                self.tbicon.RemoveIcon()
                self.tbicon.Destroy()
            self.Destroy()
        except:
#            data = StringIO()
#            print_exc(file = data)
#            sys.stderr.write(data.getvalue())
            pass
                   
    ######################################
    # Update ABC on-the-fly
    ######################################
    def updateABCDisplay(self):
        # Reload Settings
        self.utility.guiman.getColumnData()

        # Update Column name and width add, delete
        #################################################

        self.utility.list.loadColumns()

        # Update display in column for inactive torrent
        self.utility.queue.updateInactiveCol()

##############################################################
# Class : ABCApp
#
# Main ABC application class that contains ABCFrame Object
#
##############################################################
class ABCApp(wx.App):
    def __init__(self, x, params, single_instance_checker, abcpath):
        self.params = params
        self.single_instance_checker = single_instance_checker

        self.utility = Utility(self, abcpath)

        sys.stdout.write('Client Starting Up.\n')
        sys.stdout.write('Build: ' + self.utility.lang.get('build') + '\n')
        
        wx.App.__init__(self, x)

    def OnInit(self):
        self.utility.postAppInit()
        self.frame = ABCFrame(-1, self.params, self.utility)

        self.Bind(wx.EVT_QUERY_END_SESSION, self.frame.OnCloseWindow)
        self.Bind(wx.EVT_END_SESSION, self.frame.OnCloseWindow)
        
        return True

    def OnExit(self):
        del self.single_instance_checker
        tries = 0
        while not self.utility.abcdonequitting and tries < 3:
            ClientPassParam("Close Connection")
            if not self.utility.abcdonequitting:
                sleep(0.1)
                tries += 1
        
        return 0

##############################################################
#
# Main Program Start Here
#
##############################################################
def run(params = [""]):
    if len(sys.argv) > 1:
        params = sys.argv[1:]
    
    # Create single instance semaphore
    single_instance_checker = wx.SingleInstanceChecker("pingpong-abc" + str(wx.GetUserId()))

    if single_instance_checker.IsAnotherRunning():
        #Send  torrent info to abc single instance
        ClientPassParam(params[0])
    else:
        abcpath = os.path.abspath(os.path.dirname(sys.argv[0]))
        os.chdir(abcpath)

        # Launch first abc single instance
        app = ABCApp(0, params, single_instance_checker, abcpath)
        app.MainLoop()

        
if __name__ == '__main__':
#    abcpath = os.path.abspath(os.path.dirname(sys.argv[0]))
#    os.chdir(abcpath)

    run()

#    prof = hotshot.Profile("profiler_output.txt")
#
#    prof.runcall(run)
#
##    if len(sys.argv) == 1:
##        run([""], abcpath)        
##    else:
##        run(sys.argv[1:], abcpath)
#        
#    prof.close()