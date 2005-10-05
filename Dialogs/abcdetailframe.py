import sys
import wx
import re
import os

import binascii

from threading import Thread
from time import time, localtime, strftime
from webbrowser import open_new

from traceback import print_exc
from cStringIO import StringIO

from ABC.GUI.list import ManagedList

from Utility.constants import * #IGNORE:W0611


################################################################
#
# Class: TorrentInfoPanel
#
# Displays BitTorrent-related information, such as trackers,
# etc.
#
################################################################
class TorrentInfoPanel(wx.Panel):
    def __init__(self, parent, dialog):
        wx.Panel.__init__(self, parent, -1)
    
        self.dialog = dialog
        self.utility = dialog.utility
        self.torrent = dialog.torrent
        
        metainfo = dialog.metainfo

        self.fileList = None
        self.refresh_detail = False

        announce = metainfo.get('announce', None)
        announce_list = metainfo.get('announce-list', None)
        http_seeds = metainfo.get('httpseeds', None)
            
        info = metainfo['info']

        piece_length = info['piece length']

        colSizer = wx.BoxSizer(wx.VERTICAL)
        
        detailSizer = wx.FlexGridSizer(cols = 2, vgap = 6, hgap = 10)        

        detailSizer.Add(wx.StaticText(self, -1, self.utility.lang.get('infohash')), 0, wx.ALIGN_CENTER_VERTICAL)
        detailSizer.Add(wx.TextCtrl(self, -1, self.torrent.infohash, style = wx.TE_READONLY), 1, wx.EXPAND)
        num_pieces = int((self.torrent.files.getSize() + piece_length - 1)/piece_length)
        
        detailSizer.Add(wx.StaticText(self, -1, self.utility.lang.get('pieces')))
        if num_pieces > 1:
            detailSizer.Add(wx.StaticText(self, -1, self.utility.lang.get('str2') % (num_pieces, self.comma_format(piece_length))))
        else:
            detailSizer.Add(wx.StaticText(self, -1, '1'))

        if 'encoding' in metainfo and metainfo['encoding'].strip():
            detailSizer.Add(wx.StaticText(self, -1, self.utility.lang.get('encoding')))
            detailSizer.Add(wx.StaticText(self, -1, metainfo['encoding']))

        if announce_list is None:
            detailSizer.Add(wx.StaticText(self, -1, self.utility.lang.get('announceurl')), 0, wx.ALIGN_CENTER_VERTICAL)
            detailSizer.Add(wx.TextCtrl(self, -1, announce, style = wx.TE_READONLY), 1, wx.EXPAND)
        else:
            detailSizer.Add(wx.StaticText(self, -1, ''))
            self.trackerList = trackerList = wx.ListCtrl(self, -1, size = (-1, 100), style = wx.LC_REPORT)
            trackerList.SetAutoLayout(True)
            trackerList.InsertColumn(0, "")
            trackerList.InsertColumn(1, self.utility.lang.get('announceurls'))

            for tier in range(len(announce_list)):
                for t in range(len(announce_list[tier])):
                    i = wx.ListItem()
                    trackerList.InsertItem(i)
            if announce is not None:
                for l in [1, 2]:
                    i = wx.ListItem()
                    trackerList.InsertItem(i)

            x = 0
            for tier in range(len(announce_list)):
                for t in range(len(announce_list[tier])):
                    if t == 0:
                        trackerList.SetStringItem(x, 0, self.utility.lang.get('tier') + str(tier)+':')
                    trackerList.SetStringItem(x, 1, announce_list[tier][t])
                    x += 1
            if announce is not None:
                trackerList.SetStringItem(x+1, 0, self.utility.lang.get('single'))
                trackerList.SetStringItem(x+1, 1, announce)
            trackerList.SetColumnWidth(0, wx.LIST_AUTOSIZE)
            trackerList.SetColumnWidth(1, wx.LIST_AUTOSIZE)
            detailSizer.Add(trackerList, 1, wx.EXPAND)
            self.trackerList.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.onAnnounceListRightClick)

        if announce is None and announce_list is not None:
            announce = announce_list[0][0]
        if announce is not None:
            detailSizer.Add(wx.StaticText(self, -1, self.utility.lang.get('likelytracker')))
            p = re.compile('(.*/)[^/]+')
            self.turl = p.sub (r'\1', announce)
            trackerUrl = wx.StaticText(self, -1, self.turl)
            trackerUrl.SetForegroundColour('Blue')
            detailSizer.Add(trackerUrl)
            trackerUrl.Bind(wx.EVT_LEFT_DOWN, self.trackerurl, trackerUrl)
            
        if http_seeds is not None:
            httpseedtext = ""
            for httpseed in http_seeds:
                httpseedtext += httpseed + "\n"
            detailSizer.Add(wx.StaticText(self, -1, self.utility.lang.get('httpseeds')))
            detailSizer.Add(wx.TextCtrl(self, -1, httpseedtext, size = (-1, 100), style = wx.TE_MULTILINE|wx.HSCROLL|wx.TE_DONTWRAP|wx.TE_READONLY), 1, wx.EXPAND)
               
        if 'creation date' in metainfo:
            detailSizer.Add(wx.StaticText(self, -1, self.utility.lang.get('creationdate')))
            try:
                datetext = strftime('%x %X', localtime(metainfo['creation date']))
            except:
                try:
                    datetext = metainfo['creation date']
                except:
                    datetext = '<cannot read date>'
            detailSizer.Add(wx.StaticText(self, -1, datetext))

        if 'created by' in metainfo and metainfo['created by'].strip():
            detailSizer.Add(wx.StaticText(self, -1, self.utility.lang.get('createdby')))
            detailSizer.Add(wx.StaticText(self, -1, metainfo['created by']))

        if 'comment' in metainfo and metainfo['comment'].strip():
            detailSizer.Add(wx.StaticText(self, -1, self.utility.lang.get('comment')))
            detailSizer.Add(wx.TextCtrl(self, -1, metainfo['comment'], style = wx.TE_MULTILINE|wx.HSCROLL|wx.TE_DONTWRAP|wx.TE_READONLY), 1, wx.EXPAND)

        detailSizer.AddGrowableCol(1)
        colSizer.Add(detailSizer, 0, wx.EXPAND|wx.ALL, 5)
        
        self.SetSizer(colSizer)
        self.SetAutoLayout(True)
       
    def onAnnCopy(self, event = None):
        # Copy the selected announce url to the clipboard
        if wx.TheClipboard.Open():
            data = wx.TextDataObject(self.trackerList.GetItem(self.trackerList.GetNextItem(-1, wx.LIST_NEXT_ALL, wx.LIST_STATE_SELECTED), 1).GetText())
            wx.TheClipboard.SetData(data)
            wx.TheClipboard.Close()

    # Popup menu for tracker list
    def onAnnounceListRightClick(self, event):
        menu = wx.Menu()
        self.utility.makePopup(menu, self.onAnnCopy, 'copybtn')
        self.PopupMenu(menu, event.GetPosition() + self.trackerList.GetPosition())

    def comma_format(self, s):
        r = str(s)
        for i in range(len(r)-3, 0, -3):
            r = r[:i]+','+r[i:]
        return(r)
        
    def trackerurl(self, event = None):
        if self.turl is not None:
            try:
                Thread(target = open_new(self.turl)).start()
            except:
                pass


################################################################
#
# Class: FileInfoPanel
#
# Displays information about the file(s) within a torrent
#
################################################################
class FileInfoPanel(wx.Panel):
    def __init__(self, parent, dialog):
        wx.Panel.__init__(self, parent, -1)
    
        self.dialog = dialog
        self.utility = dialog.utility
        self.torrent = dialog.torrent
        
        metainfo = dialog.metainfo

        self.refresh_detail = False

        info = metainfo['info']

        colSizer = wx.BoxSizer(wx.VERTICAL)
        
        detailSizer = wx.FlexGridSizer(cols = 2, vgap = 6, hgap = 10)
       
        #Folder File
        detailSizer = wx.FlexGridSizer(cols = 2, vgap = 6, hgap = 10)

        detailSizer.Add(wx.StaticText(self, -1, self.utility.lang.get('destination')), 0, wx.ALIGN_CENTER_VERTICAL)

        self.opendirbtn = wx.Button(self, -1, self.torrent.files.getProcDest(pathonly = True, checkexists = False), style = wx.BU_EXACTFIT)
        detailSizer.Add(self.opendirbtn, 0, wx.ALIGN_CENTER_VERTICAL)
        
        self.opendirbtn.Bind(wx.EVT_LEFT_DOWN, self.onDestButtonClick)
        self.opendirbtn.Bind(wx.EVT_RIGHT_DOWN, self.onDestButtonClick)
              
        if 'length' in info:
            #Single File            
            numfiles = 1
            
            name = self.utility.lang.get('filesize')
        else:
            #Folder File
            numfiles = len(info['files'])
            
            name = self.utility.lang.get('archivesize')

        detailSizer.Add(wx.StaticText(self, -1, name + ' : '))
        detailSizer.Add(wx.StaticText(self, -1, self.utility.lang.get('str1') % (self.utility.size_format(self.torrent.files.getSize()), self.comma_format(self.torrent.files.getSize()))))

        colSizer.Add(detailSizer, 0, wx.ALL, 5)

        self.fileList = fileList = FileInfoList(self)

        for i in range(numfiles):
            x = wx.ListItem()
            fileList.InsertItem(x)
        x = 0
        
        self.updateColumns()

        colSizer.Add(fileList, 1, wx.EXPAND|wx.ALL, 5)
        
        self.SetSizer(colSizer)
        self.SetAutoLayout(True)
        
        if self.torrent.status.isActive():
            self.torrent.connection.engine.dow.filedatflag.set()
            
    def onDestButtonClick(self, event):
        # Popup menu for tracker list
        menu = wx.Menu()
        self.utility.makePopup(menu, self.torrent.files.onOpenDest, 'ropendest')
        self.utility.makePopup(menu, self.onCopyPath, 'rcopypath')
        self.utility.makePopup(menu, self.onChangeDest, 'rchangedownloaddest')
        
        self.PopupMenu(menu, event.GetPosition() + self.opendirbtn.GetPosition())
        
    def onChangeDest(self, event = None):
        self.torrent.dialogs.changeDest(parent = self)
            
    def onCopyPath(self, event = None):
        # Get the filenames
        text = self.torrent.files.getSingleFileDest(0, pathonly = True, checkexists = False)
        
        # Copy the text to the clipboard
        if wx.TheClipboard.Open():
            data = wx.TextDataObject(text)
            wx.TheClipboard.SetData(data)
            wx.TheClipboard.Close()

    def updateColumns(self, columnlist = None, force = False):
        priorities = self.torrent.files.filepriorities

        info = self.dialog.metainfo['info']
        fileList = self.fileList
            
        if self.torrent.files.isFile():
            filesinfo = [info]
        else:
            filesinfo = info['files']
            
        x = 0
        try:
            for tempfile in filesinfo:
                for colid, rank in fileList.columns.active:
                    if columnlist is None or colid in columnlist:
                        fileList.SetStringItem(x, rank, self.getFileColumnText(colid, tempfile, x))
    
                p = priorities[x]
                item = self.fileList.GetItem(x)
                item.SetTextColour(self.fileList.prioritycolors[p+1])
                fileList.SetItem(item)
                x += 1
        except wx.PyDeadObjectError:
            pass

    def getFileColumnText(self, colid, tempfile, index = 0):
        text = None
        
        if colid == FILEINFO_FILENAME:
            if self.torrent.files.isFile():
                text = os.path.split(self.torrent.files.getProcDest(pathonly = False, checkexists = False))[1]
            else:
                path = ' '
                for item in tempfile['path']:
                    if (path != ''):
                        path = path + "/"
                    path = path + item
                text = path
        elif colid == FILEINFO_SIZE:
            if self.torrent.files.isFile() or self.torrent.files.filepriorities[index] != -1:
                text = self.comma_format(tempfile['length']) + ' ' + self.utility.lang.get('Byte')
        elif colid == FILEINFO_PROGRESS:
            if self.torrent.files.isFile():
                if not self.torrent.status.isCheckingOrAllocating():
                    if self.torrent.status.completed:
                        text = self.utility.lang.get('done')
                    else:
                        text = self.torrent.getColumnText(COL_PROGRESS)
            else:
                text = self.torrent.files.fileprogress[index]
        elif colid == FILEINFO_MD5:
            if 'md5sum' in tempfile:
                text = str(tempfile['md5sum'])
        elif colid == FILEINFO_CRC32:
            if 'crc32' in tempfile:
                text = str(tempfile['crc32'])
        elif colid == FILEINFO_SHA1:
            if 'sha1' in tempfile:
                text = binascii.b2a_hex(tempfile['sha1'])
        elif colid == FILEINFO_ED2K:
            if 'ed2k' in tempfile:
                text = binascii.b2a_hex(tempfile['ed2k'])
            
        if text is None:
            text = ""
            
        return text

    def comma_format(self, s):
        r = str(s)
        for i in range(len(r)-3, 0, -3):
            r = r[:i]+','+r[i:]
        return(r)



################################################################
#
# Class: FileInfoList
#
# Used by multi-file torrents to display information about
# each of the files.
#
################################################################
class FileInfoList(ManagedList):
    def __init__(self, parent):        
        style = wx.LC_REPORT
        
        prefix = 'fileinfo'
        minid = 0
        maxid = 7
        rightalign = [FILEINFO_SIZE, FILEINFO_PROGRESS]
        centeralign = []

        exclude = []

        ManagedList.__init__(self, parent, style, prefix, minid, maxid, exclude, rightalign, centeralign)
        
        self.torrent = parent.torrent

        self.priorityIDs = [wx.NewId(), wx.NewId(), wx.NewId(), wx.NewId()]
        self.prioritycolors = [ wx.Colour(160, 160, 160), 
                                wx.Colour(255, 64, 0), 
                                wx.Colour(0, 0, 0), 
                                wx.Colour(64, 64, 255) ]

        self.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.onItemSelected)
        self.Bind(wx.EVT_LEFT_DCLICK, self.onOpenFileDest)
        self.Bind(wx.EVT_KEY_DOWN, self.onKeyDown)

    def onKeyDown(self, event):
        keycode = event.GetKeyCode()
        if event.CmdDown():
            if keycode == ord('a') or keycode == ord('A'):
                # Select all files (CTRL-A)
                self.selectAll()
            elif keycode == ord('x') or keycode == ord('X'):
                # Invert file selection (CTRL-X)
                self.invertSelection()
            elif keycode == ord('c') or keycode == ord('C'):
                self.onCopyFilename()
        elif keycode == 399:
            # Open right-click menu (windows menu key)
            self.onItemSelected()

        event.Skip()     

    def onOpenFileDest(self, event = None):
        for index in self.getSelected(firstitemonly = True):
            self.torrent.files.onOpenFileDest(index = index)
        
    def onOpenDest(self, event = None):
        for index in self.getSelected(firstitemonly = True):
            self.torrent.files.onOpenFileDest(index = index, pathonly = True)

    # Copy the filenames for one or more files
    def onCopyFilename(self, event = None, pathonly = False):
        # Get the filenames
        text = ""
        count = 0
        for index in self.getSelected():
            if count > 0:
                text += "\n"
            text += self.torrent.files.getSingleFileDest(index, pathonly, checkexists = False)
            count += 1
        
        # Copy the text to the clipboard
        if wx.TheClipboard.Open():
            data = wx.TextDataObject(text)
            wx.TheClipboard.SetData(data)
            wx.TheClipboard.Close()

    # Copy just the paths for files
    def onCopyPath(self, event = None):
        self.onCopyFilename(pathonly = True)

    def makePriorityMenu(self):
        s = self.getSelected()
        if not s:
            return None

        priorities = self.torrent.files.filepriorities
        oldstate = priorities[s[0]]
        kind = wx.ITEM_RADIO
        for i in s[1:]:
            if priorities[i] != oldstate:
                oldstate = None
                kind = wx.ITEM_NORMAL
                break
            
        menu = wx.Menu()
        menu.Append(self.priorityIDs[1], self.utility.lang.get('download_first'), kind=kind)
        menu.Append(self.priorityIDs[2], self.utility.lang.get('download_normal'), kind=kind)
        menu.Append(self.priorityIDs[3], self.utility.lang.get('download_later'), kind=kind)
        menu.Append(self.priorityIDs[0], self.utility.lang.get('download_never'), kind=kind)
        if oldstate is not None:
            menu.Check(self.priorityIDs[oldstate+1], True)

        def onSelection(event, self = self, s = s):
            p = event.GetId()
            priorities = self.torrent.files.filepriorities
            for i in xrange(len(self.priorityIDs)):
                if p == self.priorityIDs[i]:
                    for ss in s:
                        priorities[ss] = i-1
                        item = self.GetItem(ss)
                        item.SetTextColour(self.prioritycolors[i])
                        self.SetItem(item)

                    self.torrent.files.setFilePriorities(priorities)
                    self.Refresh()
                    break
            
        for index in self.priorityIDs:
            self.Bind(wx.EVT_MENU, onSelection, id = index)
        
        return menu

    def onItemSelected(self, event = None):
        s = self.getSelected()

        if not s:   # just in case
            return

        menu = wx.Menu()
        
        self.utility.makePopup(menu, self.onCopyFilename, 'rcopyfilename')
        self.utility.makePopup(menu, self.onCopyPath, 'rcopypath')
        self.utility.makePopup(menu, self.onOpenDest, 'ropendest')
        self.utility.makePopup(menu, self.onOpenFileDest, 'ropenfiledest')

        # Add the priority submenu if this is a multi-file torrent
        if not self.torrent.files.isFile():
            prioritymenu = self.makePriorityMenu()
            if prioritymenu is not None:
                menu.AppendMenu(-1, self.utility.lang.get('rpriosetting'), prioritymenu)

        # Popup the menu.  If an item is selected then its handler
        # will be called before PopupMenu returns.
        if event is None:
            # use the position of the first selected item (key event)
            position = self.GetItemPosition(s[0])
        else:
            # use the cursor position (mouse event)
            position = event.GetPoint()

        self.PopupMenu(menu, position)
 
        
################################################################
#
# Class: DetailPanel
#
# Displays network information related to how much has been
# downloaded/uploaded, along with a listing of peers
# (if connected).
#
################################################################
class DetailPanel(wx.Panel):
    def __init__(self, parent, dialog):
        wx.Panel.__init__(self, parent, -1)
    
        self.dialog = dialog
        self.utility = dialog.utility
        self.torrent = dialog.torrent
        
        colSizer = wx.BoxSizer(wx.VERTICAL)
       
        detailSizer = wx.FlexGridSizer(cols = 2, vgap = 6, hgap = 100)
        colSizer.Add (detailSizer, 0, wx.ALIGN_CENTER|wx.ALL, 5)
        leftdetailSizer  = wx.FlexGridSizer(cols = 2, vgap = 3, hgap = 5)
        rightdetailSizer = wx.FlexGridSizer(cols = 2, vgap = 3, hgap = 5)
        detailSizer.Add(leftdetailSizer)
        detailSizer.Add(rightdetailSizer)

        # # SEED
        ###################
        self.seedtitle = wx.StaticText(self, -1, "")
        self.numseed   = wx.StaticText(self, -1, "")
        leftdetailSizer.Add(self.seedtitle)
        leftdetailSizer.Add(self.numseed)
        
        # # Peers
        ###################
        self.numpeer   = wx.StaticText(self, -1, "")
        leftdetailSizer.Add(wx.StaticText(self, -1, self.utility.lang.get('dnumconnectedpeer')))
        leftdetailSizer.Add(self.numpeer)

        # # Seeing Copies
        ##################
        self.numcopy  = wx.StaticText(self, -1, "")
        rightdetailSizer.Add(wx.StaticText(self, -1, self.utility.lang.get('dseeingcopies')))
        rightdetailSizer.Add(self.numcopy)
        
        # Avg peer
        ##################
        self.avgprogress  = wx.StaticText(self, -1, "")
        rightdetailSizer.Add(wx.StaticText(self, -1, self.utility.lang.get('davgpeerprogress')))
        rightdetailSizer.Add(self.avgprogress)
                
        # Download Size
        ##################
        self.downsize  = wx.StaticText(self, -1, "")
        leftdetailSizer.Add(wx.StaticText(self, -1, self.utility.lang.get('ddownloadedsize')))
        leftdetailSizer.Add(self.downsize)
        
        # Upload Size
        ##################
        self.upsize = wx.StaticText(self, -1, "")
        rightdetailSizer.Add(wx.StaticText(self, -1, self.utility.lang.get('duploadedsize')))
        rightdetailSizer.Add(self.upsize)

        # Total Speed
        ##################
        self.totalspeed  = wx.StaticText(self, -1, "")
        leftdetailSizer.Add(wx.StaticText(self, -1, self.utility.lang.get('dtotalspeed')))
        leftdetailSizer.Add(self.totalspeed)

        # Port Used
        ##################
        self.portused = wx.StaticText(self, -1, "")
        rightdetailSizer.Add(wx.StaticText(self, -1, self.utility.lang.get('dportused')))
        rightdetailSizer.Add(self.portused)

        # Shad0w Advance display
        #####################
        def StaticText(text):
            return wx.StaticText(self, -1, text, style = wx.ALIGN_LEFT)

        self.spewList = SpewList(self)

        colSizer.Add(self.spewList, 1, wx.EXPAND|wx.ALL, 5)

        self.storagestats1 = StaticText('')
        self.storagestats2 = StaticText('')
        colSizer.Add(self.storagestats1, 0, wx.ALL, 5)
        colSizer.Add(self.storagestats2, 0, wx.ALL, 5)

        # Grab initial values from ABCTorrent:
        self.updateFromABCTorrent()

        self.SetSizer(colSizer)
        self.SetAutoLayout(True)

    ######################################
    # Update on-the-fly
    ######################################
    def updateColumns(self, force = False):
        # Update display in column?
        pass

    def updateFromABCTorrent(self):
        if self.utility.abcquitting:
            return
        try:
            self.downsize.SetLabel(self.torrent.getColumnText(COL_DLSIZE))
            self.upsize.SetLabel(self.torrent.getColumnText(COL_ULSIZE))
            if not self.torrent.status.completed:
                self.seedtitle.SetLabel(self.utility.lang.get('dnumconnectedseed'))
            else:
                self.seedtitle.SetLabel(self.utility.lang.get('dseenseed'))
            self.totalspeed.SetLabel(self.torrent.getColumnText(COL_TOTALSPEED))
            self.avgprogress.SetLabel(self.torrent.getColumnText(COL_PEERPROGRESS))
            self.numseed.SetLabel(self.torrent.getColumnText(COL_SEEDS))
            self.numpeer.SetLabel(self.torrent.getColumnText(COL_PEERS))
            self.numcopy.SetLabel(self.torrent.getColumnText(COL_COPIES))
            if self.torrent.status.isActive():
                port = self.utility.controller.listen_port
                if port is not None:
                    self.portused.SetLabel(str(port))
        except wx.PyDeadObjectError:
            pass


################################################################
#
# Class: SpewList
#
# Displays a listing of peers (if connected).
#
################################################################
class SpewList(ManagedList):
    def __init__(self, parent):
        style = wx.LC_REPORT|wx.LC_HRULES|wx.LC_VRULES
        
        prefix = 'spew'
        minid = 0
        maxid = 14
        rightalign = [SPEW_UP, 
                      SPEW_DOWN, 
                      SPEW_DLSIZE, 
                      SPEW_ULSIZE, 
                      SPEW_PEERPROGRESS, 
                      SPEW_PEERSPEED]
        centeralign = [SPEW_UNCHOKE, 
                       SPEW_LR, 
                       SPEW_INTERESTED, 
                       SPEW_CHOKING, 
                       SPEW_INTERESTING, 
                       SPEW_CHOKED, 
                       SPEW_SNUBBED]

        exclude = []      

        ManagedList.__init__(self, parent, style, prefix, minid, maxid, exclude, rightalign, centeralign)
    

################################################################
#
# Class: MessageLogPanel
#
# Displays the errors that a torrent has encountered
#
################################################################
class MessageLogPanel(wx.Panel):
    def __init__(self, parent, dialog):
        wx.Panel.__init__(self, parent, -1)
    
        self.dialog = dialog
        self.utility = dialog.utility
        self.torrent = dialog.torrent
        
        colSizer = wx.BoxSizer(wx.VERTICAL)

        self.msgtext = wx.TextCtrl(self, -1, style = wx.TE_MULTILINE|wx.TE_READONLY|wx.TE_DONTWRAP|wx.TE_RICH)
        
        colSizer.Add(self.msgtext, 1, wx.EXPAND|wx.ALL, 5)
        
        logButtons = wx.BoxSizer(wx.HORIZONTAL)
        
        clearlog = wx.Button(self, -1, self.utility.lang.get('clearlog'))
        self.Bind(wx.EVT_BUTTON, self.clearLog, clearlog)
        logButtons.Add(clearlog, 0, wx.LEFT|wx.RIGHT, 5)

        savelog = wx.Button(self, -1, self.utility.lang.get('savelog'))
        self.Bind(wx.EVT_BUTTON, self.saveLog, savelog)
        logButtons.Add(savelog, 0, wx.LEFT|wx.RIGHT, 5)
        
        colSizer.Add(logButtons, 0, wx.ALIGN_RIGHT|wx.ALL, 5)

        # Grab initial values from ABCTorrent:
        self.updateMessageLog()

        self.SetSizer(colSizer)
        self.SetAutoLayout(True)
        
    def clearLog(self, event = None):
        self.torrent.messages["log"] = []
        self.updateMessageLog()
        
    def saveLog(self, event = None):
        # Ask where to save the file to
        defaultdir = self.utility.getLastDir("log")
        
        dlg = wx.FileDialog(self.dialog, 
                            message = self.utility.lang.get('savelogas'), 
                            defaultDir = defaultdir, 
                            defaultFile = self.torrent.files.filename + ".log", 
                            wildcard = self.utility.lang.get('logfileswildcard') + ' (*.log)|*.log', 
                            style = wx.SAVE)
        dlg.Raise()
        result = dlg.ShowModal()
        dlg.Destroy()
        
        if result != wx.ID_OK:
            return
        
        dest = dlg.GetPath()
            
        self.utility.lastdir['log'] = os.path.dirname(dest)

        # Generate the combined log text
        logtext = ""
        for entry in self.torrent.messages["log"]:
            msgdate = strftime('%x', localtime(entry[0]))
            msgtime = strftime('%X', localtime(entry[0]))
            message = entry[1]
            msgtype = entry[2]
            
            combined = msgdate + " " + msgtime + " - " + message
            
            logtext += combined + "\n"
            
        # Write the file
        try:
            logfile = open(dest, "w")
            logfile.write(logtext)
            logfile.close()
        except:
            data = StringIO()
            print_exc(file = data)

            dialog = wx.MessageDialog(self.dialog, 
                                      self.utility.lang.get('error_savelog') + "\n" + data.getvalue(), 
                                      self.utility.lang.get('error'), 
                                      wx.ICON_ERROR)
            dialog.ShowModal()
            dialog.Destroy()
        
    def updateMessageLog(self):
        if self.utility.abcquitting:
            return

        try:
            self.msgtext.Clear()
            for entry in self.torrent.messages["log"]:
                msgdate = strftime('%x', localtime(entry[0]))
                msgtime = strftime('%X', localtime(entry[0]))
                message = entry[1]
                msgtype = entry[2]
                
                combined = msgdate + " " + msgtime + " - " + message
                
                if msgtype == "error":
                    color = wx.Colour(200, 0, 0)
                else:
                    color = wx.Colour(0, 0, 0)
    
                self.msgtext.SetInsertionPointEnd()
                before = self.msgtext.GetInsertionPoint()
                
                self.msgtext.AppendText(combined + "\n")
                
                self.msgtext.SetInsertionPointEnd()
                after = self.msgtext.GetInsertionPoint()
                
                self.msgtext.SetStyle(before, after, wx.TextAttr(color))
        except wx.PyDeadObjectError:
            pass


################################################################
#
# Class: ABCDetailFrame
#
# Window that displays detailed information about the status
# of a torrent and its files
#
################################################################
class ABCDetailFrame(wx.Frame):
    def __init__(self, torrent):
        self.torrent = torrent
        self.utility = torrent.utility
        
        size = self.getWindowSettings()
        
        wx.Frame.__init__(self, None, -1, "", size = size)

        self.update = False

        try:
            self.SetIcon(self.utility.icon)
        except:
            pass

        self.metainfo = self.torrent.getResponse()
        if self.metainfo is None:
            self.killAdv()
            return
                   
        panel = wx.Panel(self, -1, size = size)
                   
        sizer = wx.BoxSizer(wx.VERTICAL)

#        self.aboutTitle = wx.StaticText(panel, -1, self.torrent.getColumnText(COL_TITLE))
        self.aboutTitle = wx.TextCtrl(panel, -1, "", style = wx.TE_CENTRE)
        
        self.aboutTitle.SetFont(wx.Font(14, wx.DEFAULT, wx.NORMAL, wx.NORMAL, False))
        sizer.Add(self.aboutTitle, 0, wx.EXPAND|wx.ALIGN_CENTER|wx.ALL, 5)

        self.notebook = wx.Notebook(panel, -1)

        self.detailPanel = DetailPanel(self.notebook, self)
        self.notebook.AddPage(self.detailPanel, self.utility.lang.get('networkinfo'))
        
        self.fileInfoPanel = FileInfoPanel(self.notebook, self)
        self.notebook.AddPage(self.fileInfoPanel, self.utility.lang.get('fileinfo'))
        
        self.torrentInfoPanel = TorrentInfoPanel(self.notebook, self)
        self.notebook.AddPage(self.torrentInfoPanel, self.utility.lang.get('torrentinfo'))
        
        self.messageLogPanel = MessageLogPanel(self.notebook, self)
        self.notebook.AddPage(self.messageLogPanel, self.utility.lang.get('messagelog'))
        
        sizer.Add(self.notebook, 1, wx.EXPAND|wx.ALL, 5)
        
        try:
            self.notebook.SetSelection(self.utility.lasttab['advanced'])
        except:
            pass
                
        # Add buttons
        #########################
        buttonSizer = wx.BoxSizer(wx.HORIZONTAL)

        scrapeButton = wx.Button(panel, -1, self.utility.lang.get('updateseedpeer'))
        self.Bind(wx.EVT_BUTTON, self.getScrape, scrapeButton)
        buttonSizer.Add(scrapeButton, 0, wx.RIGHT, 5)
        
        reannounceButton = wx.Button(panel, -1, self.utility.lang.get('manualannounce'))
        self.Bind(wx.EVT_BUTTON, self.torrent.connection.reannounce, reannounceButton)
        buttonSizer.Add(reannounceButton, 0, wx.LEFT|wx.RIGHT, 5)
        
        extannounceButton = wx.Button(panel, -1, self.utility.lang.get('externalannounce'))
        self.Bind(wx.EVT_BUTTON, self.reannounce_external, extannounceButton)
        buttonSizer.Add(extannounceButton, 0, wx.LEFT|wx.RIGHT, 5)

        bgallocButton = wx.Button(panel, -1, self.utility.lang.get('finishallocation'))
        self.Bind(wx.EVT_BUTTON, self.bgalloc, bgallocButton)
        buttonSizer.Add(bgallocButton, 0, wx.LEFT|wx.RIGHT, 5)

        okButton = wx.Button(panel, -1, self.utility.lang.get('ok'))
        self.Bind(wx.EVT_BUTTON, self.killAdv, okButton)
        buttonSizer.Add(okButton, 0, wx.LEFT, 5)

        sizer.Add(buttonSizer, 0, wx.ALIGN_CENTER|wx.ALL, 5)
        
        panel.SetSizer(sizer)
        
        self.Bind(wx.EVT_CLOSE, self.killAdv)
       
        # Set the spew flag
        if self.torrent.status.isActive():
            self.torrent.connection.engine.dow.spewflag.set()

        self.aboutTitle.Bind(wx.EVT_RIGHT_DOWN, self.onTitleMenu)
        self.aboutTitle.Bind(wx.EVT_TEXT, self.onChangeTitle)

        self.updateTorrentName()

        self.update = True

        self.Show()
            
    def reannounce_external(self, event = None):
        self.torrent.connection.reannounce_external(event, self)
        
    def getScrape(self, event = None):
        self.torrent.actions.scrape(manualscrape = True)
               
    def killAdv(self, event = None):       
        self.update = False
        
        # Remove lists from the index kept in utility:
        try:
            self.utility.lists[self.detailPanel.spewList] = False
            del self.utility.lists[self.detailPanel.spewList]
        except:
            pass
        try:
            self.utility.lists[self.fileInfoPanel.fileList] = False
            del self.utility.lists[self.fileInfoPanel.fileList]
        except:
            pass

        self.torrent.dialogs.details = None

        # Clear the spew flag
        if self.torrent.status.isActive():
            # TODO: Workaround for multiport not reporting
            #       external_connection_made properly
            if self.torrent.connection.engine.workarounds['hasexternal']:
                self.torrent.connection.engine.dow.spewflag.clear()
        
        try:
            self.saveWindowSettings()
            self.Destroy()
        except wx.PyDeadObjectError:
            pass
        
    def onStop(self):
        self.detailPanel.updateFromABCTorrent()

        self.detailPanel.spewList.DeleteAllItems()
        self.detailPanel.storagestats1.SetLabel('')
        self.detailPanel.storagestats2.SetLabel('')
        
    def onChangeTitle(self, event = None):
        self.torrent.changeTitle(self.aboutTitle.GetValue())
        self.updateTitle()
        
    #
    # Give options for changing the torrent's title
    # (hide options that are the same)
    #
    def onTitleMenu(self, event):
        menu = wx.Menu()

        original = self.torrent.getTitle("original")
        dest = self.torrent.getTitle("dest")
        torrent = self.torrent.getTitle("torrent")
        
        titlemenu = wx.Menu()
        self.utility.makePopup(titlemenu, self.changeTitleOriginal, 'originalname', bindto = menu)
        self.utility.makePopup(titlemenu, self.changeTitleOriginal, extralabel = self.torrent.getTitle("original"), bindto = menu)
        if original != dest:
            titlemenu.AppendSeparator()
            self.utility.makePopup(titlemenu, self.changeTitleDest, 'destname', bindto = menu)
            self.utility.makePopup(titlemenu, self.changeTitleDest, extralabel = self.torrent.getTitle("dest"), bindto = menu)
        if original != torrent:
            titlemenu.AppendSeparator()
            self.utility.makePopup(titlemenu, self.changeTitleTorrent, 'torrentfilename', bindto = menu)
            self.utility.makePopup(titlemenu, self.changeTitleTorrent, extralabel = self.torrent.getTitle("torrent"), bindto = menu)
        
        menu.AppendMenu(-1, self.utility.lang.get('changetitle'), titlemenu)
        
        self.PopupMenu(menu, event.GetPosition() + self.aboutTitle.GetPosition())
                
    def changeTitleOriginal(self, event = None):
        self.aboutTitle.SetValue(self.torrent.getTitle("original"))
        
    def changeTitleTorrent(self, event = None):
        self.aboutTitle.SetValue(self.torrent.getTitle("torrent"))
        
    def changeTitleDest(self, event = None):
        self.aboutTitle.SetValue(self.torrent.getTitle("dest"))

    def getWindowSettings(self):
        width = self.utility.config.Read("detailwindow_width", "int")
        height = self.utility.config.Read("detailwindow_height", "int")
                  
        return wx.Size(width, height)
        
    def saveWindowSettings(self):
        self.utility.lasttab['advanced'] = self.notebook.GetSelection()
        
        width, height = self.GetSizeTuple()
        self.utility.config.Write("detailwindow_width", str(width))
        self.utility.config.Write("detailwindow_height", str(height))
        self.utility.config.Flush()
        
    def bgalloc(self, event = None):
        if self.torrent.status.isActive():
            if self.torrent.connection.engine.dow.storagewrapper is not None:
                self.torrent.connection.engine.dow.storagewrapper.bgalloc()
                
    def updateTitle(self):
        self.SetTitle(self.utility.lang.get('torrentdetail') + " - " + self.torrent.getColumnText(COL_TITLE))
        
    def updateTorrentName(self):
        try:
            self.updateTitle()
            self.aboutTitle.SetLabel(self.torrent.getColumnText(COL_TITLE))
        except:
            pass
        info = self.metainfo['info']
        if 'length' in info:
            self.fileInfoPanel.fileList.updateColumns()

