import sys
import wx
import re
import os

from os.path import join
from sha import sha
from threading import Thread
from time import time, localtime, strftime
from webbrowser import open_new

from traceback import print_exc
from cStringIO import StringIO

from BitTornado.bencode import *

from Utility.constants import *

class CollaboratorsPanel(wx.Panel):
    def __init__(self, parent, dialog):
        wx.Panel.__init__(self, parent, -1)
    
        self.dialog = dialog
        self.utility = dialog.utility
        self.ABCTorrent = dialog.ABCTorrent
        self.role = 'sink'
        
        self.collaborators = dialog.collaborators
        
#        metainfo = dialog.metainfo

        self.fileList = None
        self.refresh_detail = False

        colSizer = wx.BoxSizer(wx.VERTICAL)
        
        detailSizer = wx.FlexGridSizer(cols = 2, vgap = 6)
#        detailSizer.Add(wx.StaticText(self, -1, self.utility.lang.get('role') + ':'))
#        detailSizer.Add(wx.StaticText(self, -1, self.utility.lang.get(self.role)))
        
        listButtons = wx.BoxSizer(wx.HORIZONTAL)
        
        importcollaborators = wx.Button(self, -1, self.utility.lang.get('importcollaborators'))
        self.Bind(wx.EVT_BUTTON, self.importCollaborators, importcollaborators)
        listButtons.Add(importcollaborators, 0, wx.LEFT|wx.RIGHT, 5)

        addcollaborator = wx.Button(self, -1, self.utility.lang.get('addcollaborator'))
        self.Bind(wx.EVT_BUTTON, self.addCollaborator, addcollaborator)
        listButtons.Add(addcollaborator, 0, wx.LEFT|wx.RIGHT, 5)

        colSizer.Add(listButtons, 0, wx.ALIGN_RIGHT|wx.ALL, 5)

#        collaboratorList = None
        self.roleIDs = [wx.NewId(), wx.NewId()]
        self.roleColors = [ wx.Colour(160, 160, 160), 
                            wx.Colour(255, 64, 0) ] #, 
#                            wx.Colour(0, 0, 0), 
#                            wx.Colour(64, 64, 255) ]

        #Folder File
#        detail1Sizer = wx.FlexGridSizer(cols = 1, vgap = 6)
#        detail1Sizer.Add(wx.StaticText(self, -1, self.utility.lang.get('directoryname') + info['name']))
#        detail1Sizer.Add(wx.StaticText(self, -1, self.utility.lang.get('destination') + self.ABCTorrent.dest))
#        colSizer.Add(detail1Sizer, 0, wx.ALL, 5)
            
        peer_length = 0
            
        collaboratorList = wx.ListCtrl(self, -1, wx.Point(-1, -1), (325, 100), wx.LC_REPORT)
        collaboratorList.SetAutoLayout (True)
        collaboratorList.InsertColumn(0, self.utility.lang.get('id'))
        collaboratorList.InsertColumn(1, self.utility.lang.get('IP'))
        collaboratorList.InsertColumn(2, self.utility.lang.get('port'))
        collaboratorList.InsertColumn(3, self.utility.lang.get('role'), format=wx.LIST_FORMAT_LEFT, width=30)
        collaboratorList.InsertColumn(4, self.utility.lang.get('progress'), format=wx.LIST_FORMAT_RIGHT, width=55)

        for i in range(len(self.collaborators)):
            x = wx.ListItem()
            collaboratorList.InsertItem(x)
            
#        priorities = self.ABCTorrent.filepriorities
        x = 0
        for collaborator_id in self.collaborators.keys():
            collaborator = self.collaborators[collaborator_id]
            collaboratorList.SetStringItem(x, 0, collaborator_id)
            collaboratorList.SetStringItem(x, 1, collaborator['ip'])
            collaboratorList.SetStringItem(x, 2, collaborator['port'])
            collaboratorList.SetStringItem(x, 3, collaborator['role'])
            item = self.collaboratorsList.GetItem(x)
            i = 0 # sink
            if collaborator['role'] == 'helper':
                i = 1
            item.SetTextColour(self.roleColors[i])
            collaboratorList.SetItem(item)
            x += 1

        collaboratorList.SetColumnWidth(0, wx.LIST_AUTOSIZE)
        collaboratorList.SetColumnWidth(1, wx.LIST_AUTOSIZE)
        collaboratorList.SetColumnWidth(2, 60)
        collaboratorList.SetColumnWidth(3, 200)

        colSizer.Add(collaboratorList, 1, wx.EXPAND|wx.ALL, 5)

        detailSizer.AddGrowableCol(1)
        colSizer.Add(detailSizer, 0, wx.EXPAND|wx.ALL, 5)
        
        self.SetSizer(colSizer)
        self.SetAutoLayout(True)

        if collaboratorList is not None:
            self.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.onRightClick, collaboratorList)

#        self.Bind(wx.EVT_LEFT_DOWN, self.trackerurl, trackerUrl)

        self.refresh_details = True
        if (self.ABCTorrent.abcengine_adr is not None
            and self.ABCTorrent.abcengine_adr.dow is not None):
            self.ABCTorrent.abcengine_adr.dow.filedatflag.set()

    def importCollaborators(self, event = None):
        sys.stdout.write("importCollaborators\n")

    def addCollaborator(self, event = None):
        sys.stdout.write("addCollaborator\n")
        NewCollaboratorFrame(self.utility)

    def onRightClick(self, event):
        None
#        s = []
#        i = -1
#        while True:
#            i = self.collaboratorList.GetNextItem(i, state=wx.LIST_STATE_SELECTED)
#            if i == -1:
#                break
#            s.append(i)
#        if not s:   # just in case
#            return
#        priorities = self.ABCTorrent.filepriorities
#        oldstate = priorities[s[0]]
#        kind=wx.ITEM_RADIO
#        for i in s[1:]:
#            if priorities[i] != oldstate:
#                oldstate = None
#                kind = wx.ITEM_NORMAL
#                break
#        menu = wx.Menu()
#        menu.Append(self.priorityIDs[1], self.utility.lang.get('download_first'), kind=kind)
#        menu.Append(self.priorityIDs[2], self.utility.lang.get('download_normal'), kind=kind)
#        menu.Append(self.priorityIDs[3], self.utility.lang.get('download_later'), kind=kind)
#        menu.Append(self.priorityIDs[0], self.utility.lang.get('download_never'), kind=kind)
#        if oldstate is not None:
#            menu.Check(self.priorityIDs[oldstate+1], True)

#        def onSelection(event, self = self, s = s):
#            p = event.GetId()
#            priorities = self.ABCTorrent.filepriorities
#            for i in xrange(len(self.priorityIDs)):
#                if p == self.priorityIDs[i]:
#                    for ss in s:
#                        priorities[ss] = i-1
#                        item = self.fileList.GetItem(ss)
#                        item.SetTextColour(self.prioritycolors[i])
#                        self.fileList.SetItem(item)

#                    self.refresh_details = True
#                    self.ABCTorrent.setFilePriorities(priorities)
#                    self.fileList.Refresh()
#                    self.refresh_details = True
#                    break
            
#        for index in self.priorityIDs:
#            self.Bind(wx.EVT_MENU, onSelection, id = index)

#        self.PopupMenu(menu, event.GetPoint())    

    def comma_format(self, s):
        r = str(s)
        for i in range(len(r)-3, 0, -3):
            r = r[:i]+','+r[i:]
        return(r)
        
    def trackerurl(self, event = None):
#        sys.stderr.write("open tracker?\n")
        if self.turl is not None:
            try:
                Thread(target = open_new(self.turl)).start()
            except:
                data = StringIO()
                print_exc(file = data)
                sys.stderr.write(data.getvalue())
#        else:
#            sys.stderr.write("self.turl is None?\n")

'''
class DetailPanel(wx.Panel):
    def __init__(self, parent, dialog):
        wx.Panel.__init__(self, parent, -1)
    
        self.dialog = dialog
        self.utility = dialog.utility
        self.ABCTorrent = dialog.ABCTorrent
        
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
        
        try:    # get system font width
            fw = wx.SystemSettings_GetFont(wx.SYS_DEFAULT_GUI_FONT).GetPointSize()+1
        except:
            fw = wx.SystemSettings_GetFont(wx.SYS_SYSTEM_FONT).GetPointSize()+1

        self.spewList = wx.ListCtrl(self, -1, style = wx.LC_REPORT|wx.LC_HRULES|wx.LC_VRULES)

        colSizer.Add(self.spewList, 1, wx.EXPAND|wx.ALL, 5)

        self.storagestats1 = StaticText('')
        self.storagestats2 = StaticText('')
        colSizer.Add(self.storagestats1, 0, wx.ALL, 5)
        colSizer.Add(self.storagestats2, 0, wx.ALL, 5)

        self.createSpewListColumns(fw)

        # Grab initial values from ABCTorrent:
        self.updateFromABCTorrent()

        self.SetSizer(colSizer)
        self.SetAutoLayout(True)

    def createSpewListColumns(self, fw):
        self.spewList.InsertColumn(0, self.utility.lang.get('spewoptunchoke'), format=wx.LIST_FORMAT_CENTER, width=fw*2)
        self.spewList.InsertColumn(1, self.utility.lang.get('spewIP'), width=fw*11)
        self.spewList.InsertColumn(2, self.utility.lang.get('spewlr'), format=wx.LIST_FORMAT_CENTER, width=fw*3)
        self.spewList.InsertColumn(3, self.utility.lang.get('up'), format=wx.LIST_FORMAT_RIGHT, width=fw*6)
        self.spewList.InsertColumn(4, self.utility.lang.get('spewinterested'), format=wx.LIST_FORMAT_CENTER, width=fw*2)
        self.spewList.InsertColumn(5, self.utility.lang.get('spewchoking'), format=wx.LIST_FORMAT_CENTER, width=fw*2)
        self.spewList.InsertColumn(6, self.utility.lang.get('down'), format=wx.LIST_FORMAT_RIGHT, width=fw*6)
        self.spewList.InsertColumn(7, self.utility.lang.get('spewinteresting'), format=wx.LIST_FORMAT_CENTER, width=fw*2)
        self.spewList.InsertColumn(8, self.utility.lang.get('spewchoecked'), format=wx.LIST_FORMAT_CENTER, width=fw*2)
        self.spewList.InsertColumn(9, self.utility.lang.get('spewsnubbed'), format=wx.LIST_FORMAT_CENTER, width=fw*2)
        self.spewList.InsertColumn(10, self.utility.lang.get('spewdownloaded'), format=wx.LIST_FORMAT_RIGHT, width=fw*7)
        self.spewList.InsertColumn(11, self.utility.lang.get('spewuploaded'), format=wx.LIST_FORMAT_RIGHT, width=fw*7)
        self.spewList.InsertColumn(12, self.utility.lang.get('spewcompleted'), format=wx.LIST_FORMAT_RIGHT, width=fw*6)
        self.spewList.InsertColumn(13, self.utility.lang.get('spewpeerdownloadspeed'), format=wx.LIST_FORMAT_RIGHT, width=fw*6)

    def updateFromABCTorrent(self):
        if self.utility.abcquitting:
            return

        try:
            self.downsize.SetLabel(self.ABCTorrent.getColumnText(18))
            self.upsize.SetLabel(self.ABCTorrent.getColumnText(19))
            if self.ABCTorrent.progress != 100.0:
                self.seedtitle.SetLabel(self.utility.lang.get('dnumconnectedseed'))
            else:
                self.seedtitle.SetLabel(self.utility.lang.get('dseenseed'))
            self.totalspeed.SetLabel(self.ABCTorrent.getColumnText(20))
            self.avgprogress.SetLabel(self.ABCTorrent.getColumnText(17))
            self.numseed.SetLabel(self.ABCTorrent.getColumnText(14))
            self.numpeer.SetLabel(self.ABCTorrent.getColumnText(15))
            self.numcopy.SetLabel(self.ABCTorrent.getColumnText(16))
            port = self.ABCTorrent.listen_port
            if port is not None:
                self.portused.SetLabel(str(port))
        except wx.PyDeadObjectError:
            pass
'''
         
class MessageLogPanel(wx.Panel):
    def __init__(self, parent, dialog):
        wx.Panel.__init__(self, parent, -1)
    
        self.dialog = dialog
        self.utility = dialog.utility
        self.ABCTorrent = dialog.ABCTorrent
        
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
        self.ABCTorrent.messagelog = []
        self.updateMessageLog()
        
    def saveLog(self, event = None):
        # Ask where to save the file to
        defaultdir = self.utility.getLastDir("log")
        
        dlg = wx.FileDialog(None, 
                            message = self.utility.lang.get('savelogas'), 
                            defaultDir = defaultdir, 
                            defaultFile = self.ABCTorrent.filename + ".log", 
                            wildcard = '*.log', 
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
        for entry in self.ABCTorrent.messagelog:
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

            dialog = wx.MessageDialog(None, 
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
            for entry in self.ABCTorrent.messagelog:
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

class CollaboratorsFrame(wx.Frame):
    def __init__(self, ABCTorrent):
        self.ABCTorrent = ABCTorrent
        self.utility = ABCTorrent.utility
        self.collaborators = {}
        self.role = 'undefined'

        size = self.getWindowSettings()
        title = self.utility.lang.get('collaborators') + " - " + self.ABCTorrent.filename
        
        wx.Frame.__init__(self, None, -1, title, size = size)

        try:
            self.SetIcon(self.utility.icon)
        except:
            pass

#        self.metainfo = self.ABCTorrent.getResponse()
#        if self.metainfo is None:
#            self.killAdv()
#            return
                   
        panel = wx.Panel(self, -1, size = size)
                   
        sizer = wx.BoxSizer(wx.VERTICAL)

        aboutTitle = wx.StaticText(panel, -1, self.ABCTorrent.filename)
        aboutTitle.SetFont(wx.Font(14, wx.DEFAULT, wx.NORMAL, wx.NORMAL, False))
        sizer.Add(aboutTitle, 0, wx.ALIGN_CENTER|wx.ALL, 5)

        sizer.Add(wx.StaticText(panel, -1, self.utility.lang.get('role') + ':' + self.utility.lang.get(self.role)))
#        sizer.Add(wx.StaticText(panel, -1, self.utility.lang.get(self.role)))

        self.notebook = wx.Notebook(panel, -1)

        self.collaboratorsPanel = CollaboratorsPanel(self.notebook, self)
        self.notebook.AddPage(self.collaboratorsPanel, self.utility.lang.get('collaborators'))

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

        startCollaborationButton = wx.Button(panel, -1, self.utility.lang.get('startcollaboration'))
        self.Bind(wx.EVT_BUTTON, self.startCollaboration, startCollaborationButton)
        buttonSizer.Add(startCollaborationButton, 0, wx.RIGHT, 8)

        joinCollaborationButton = wx.Button(panel, -1, self.utility.lang.get('joincollaboration'))
        self.Bind(wx.EVT_BUTTON, self.joinCollaboration, joinCollaborationButton)
        buttonSizer.Add(joinCollaborationButton, 0, wx.RIGHT, 8)

        okButton = wx.Button(panel, -1, self.utility.lang.get('ok'))
        self.Bind(wx.EVT_BUTTON, self.killAdv, okButton)
        buttonSizer.Add(okButton, 0, wx.LEFT, 8)

        sizer.Add(buttonSizer, 0, wx.ALIGN_CENTER|wx.ALL, 5)

        panel.SetSizer(sizer)

        self.Bind(wx.EVT_CLOSE, self.killAdv)
       
        # Set the spew flag
        if (self.ABCTorrent.abcengine_adr is not None
            and self.ABCTorrent.abcengine_adr.dow is not None):
            self.ABCTorrent.abcengine_adr.dow.spewflag.set()

        self.advextannouncebox = None

        self.Show ()

    def startCollaboration(self, event = None):
        sys.stdout.write("startCollaboration")
    
    def joinCollaboration(self, event = None):
        sys.stdout.write("joinCollaboration")
    
    def killAdv(self, event = None):
        self.ABCTorrent.detail_adr = None

        # Clear the spew flag
        if (self.ABCTorrent.abcengine_adr is not None
            and self.ABCTorrent.abcengine_adr.dow is not None):
            self.ABCTorrent.abcengine_adr.dow.spewflag.clear()
        
        if (hasattr(self, "advextannouncebox") and (self.advextannouncebox is not None)):
            try:
                self.advextannouncebox.Close()
            except wx.PyDeadObjectError:
                pass
            self.advextannouncebox = None
        try:
            self.saveWindowSettings()
            self.Destroy()
        except wx.PyDeadObjectError:
            pass
        
    def onStop(self):
        None
#        self.detailPanel.updateFromABCTorrent()

#        self.detailPanel.spewList.DeleteAllItems()
#        self.detailPanel.storagestats1.SetLabel('')
#        self.detailPanel.storagestats2.SetLabel('')

    def getWindowSettings(self):
        width = self.utility.config.Read("collaboratorswindow_width", "int")
        height = self.utility.config.Read("collaboratorswindow_height", "int")
                  
        return wx.Size(width, height)
        
    def saveWindowSettings(self):
        self.utility.lasttab['advanced'] = self.notebook.GetSelection()

        width, height = self.GetSizeTuple()
        self.utility.config.Write("collaboratorswindow_width", str(width))
        self.utility.config.Write("collaboratorswindow_height", str(height))
        self.utility.config.Flush()
        
    def bgalloc(self, event = None):
        if (self.ABCTorrent is None) or (self.ABCTorrent.abcengine_adr is None):
            return

        if (self.ABCTorrent.abcengine_adr.dow is not None):
            if self.ABCTorrent.abcengine_adr.dow.storagewrapper is not None:
                self.ABCTorrent.abcengine_adr.dow.storagewrapper.bgalloc()
                
    def getlastexternalannounce(self):
        if self.ABCTorrent.abcengine_adr is None:
            return ''
        return self.ABCTorrent.abcengine_adr.lastexternalannounce

'''
    def setlastexternalannounce(self, exannounce):
        if self.ABCTorrent.abcengine_adr is None:
            return
        self.ABCTorrent.abcengine_adr.lastexternalannounce = exannounce
'''

class NewCollaboratorFrame(wx.Frame):
    def __init__(self, utility):
        self.utility = utility
        size = self.getWindowSettings()
        title = self.utility.lang.get('addcollaborator')

        wx.Frame.__init__(self, None, -1, title, size = size)

        try:
            self.SetIcon(self.utility.icon)
        except:
            pass

        panel = wx.Panel(self, -1, size = size)
            
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer = wx.FlexGridSizer(cols = 2, vgap = 6, hgap = 6)

        sizer.Add(wx.StaticText(panel, -1, self.utility.lang.get('IP')))
        self.IPEdit = wx.TextCtrl(panel, -1)
        sizer.Add(self.IPEdit, 0, wx.ALL | wx.EXPAND, 5)

        sizer.Add(wx.StaticText(panel, -1, self.utility.lang.get('port')))
        self.portEdit = wx.TextCtrl(panel, -1)
        sizer.Add(self.portEdit, 0, wx.ALL | wx.EXPAND, 5)

        # buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
        
        cancelButton = wx.Button(panel, -1, self.utility.lang.get('cancel'))
        self.Bind(wx.EVT_BUTTON, self.killAdv, cancelButton)
        # buttonSizer.
        sizer.Add(cancelButton, 0, wx.LEFT, 8)

        okButton = wx.Button(panel, -1, self.utility.lang.get('ok'))
        self.Bind(wx.EVT_BUTTON, self.addCollaborator, okButton)
        # buttonSizer
        sizer.Add(okButton, 0, wx.LEFT, 8)

        # sizer.Add(buttonSizer, 0, wx.ALIGN_RIGHT|wx.ALL, 5)

        panel.SetSizer(sizer)

        self.Bind(wx.EVT_CLOSE, self.killAdv)

        self.Show()

    def getWindowSettings(self):
        width = self.utility.config.Read("newcollaboratorwindow_width", "int")
        height = self.utility.config.Read("newcollaboratorwindow_width", "int")
                  
        return wx.Size(width, height)

    def killAdv(self, event = None):
        try:
            self.saveWindowSettings()
            self.Destroy()
        except wx.PyDeadObjectError:
            pass
        
    def addCollaborator(self, event = None):
        sys.stdout.write("ip: " + self.IPEdit.GetValue() + " port: " + self.portEdit.GetValue() + "\n")
        self.killAdv()

    def saveWindowSettings(self):
        width, height = self.GetSizeTuple()
        self.utility.config.Write("newcollaboratorwindow_width", str(width))
        self.utility.config.Write("newcollaboratorwindow_height", str(height))
        self.utility.config.Flush()
