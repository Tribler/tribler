import sys
import wx
from os import path

from Tribler.Core.BitTornado.bencode import bencode, bdecode

from Tribler.Main.Utility.constants import * #IGNORE:W0611


################################################################
#
# Class: SetDestDialog
#
# Used to set a torrent's destination
#
################################################################
class SetDestDialog(wx.Dialog):
    def __init__(self, torrent, parent):

        self.torrent = torrent
        self.utility = torrent.utility

        title = self.utility.lang.get('choosedowndest')
        style = wx.DEFAULT_DIALOG_STYLE

        pre = wx.PreDialog()
        pre.Create(parent, -1, title, style = style)
        self.this = pre.this

        # May be called with a torrent
        # This dialog is used :
        # 1 - to change the destination (location and name) of an existing torrent (the dialog has an apply button) :
        # 2 - to choose a new destination for a new torrent because the destination is duplicate or badly named (no apply button in this case) :
        if self.torrent.files.isFile():
            indestloc = self.torrent.files.dest
        else:
            indestloc = self.torrent.files.getProcDest(pathonly = True, checkexists = False)
        destloc = path.split(indestloc)[0]
        destname = path.split(indestloc)[1]
        self.currenttorname = self.torrent.getColumnText(COL_TITLE)
        self.torfilename = path.split(self.torrent.src)[1]
        self.newdest = ''

        outerbox = wx.BoxSizer(wx.VERTICAL)

        globalbox = wx.StaticBoxSizer(wx.StaticBox(self, -1, ''), wx.VERTICAL)

        downdestlocbox = wx.StaticBoxSizer(wx.StaticBox(self, -1, self.utility.lang.get('downdestloc')), wx.VERTICAL)
        downdestloc = wx.BoxSizer(wx.HORIZONTAL)
        self.downdestloctext = wx.TextCtrl(self, -1, destloc, wx.Point(-1, -1), wx.Size(400, -1))        
        downdestloc.Add(self.downdestloctext, 1)
        downdestlocbtn = wx.Button(self, -1, self.utility.lang.get('browsebtn'), style = wx.BU_EXACTFIT)
        downdestloc.Add(downdestlocbtn, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
        downdestlocbox.Add(downdestloc, 0, wx.EXPAND | wx.TOP, 0)

        if self.torrent.files.isFile():
            downdestnamehead = self.utility.lang.get('downfilename')
        else:
            downdestnamehead = self.utility.lang.get('downdirname')
        downdestnamebox = wx.StaticBoxSizer(wx.StaticBox(self, -1, downdestnamehead), wx.VERTICAL)
        downdestname = wx.BoxSizer(wx.HORIZONTAL)
        self.downdestnametext = wx.TextCtrl(self, -1, destname, wx.Point(-1, -1), wx.Size(400, -1))        
        downdestname.Add(self.downdestnametext, 1)
        downdestnamebtn = wx.Button(self, -1, self.utility.lang.get('browsebtn'), style = wx.BU_EXACTFIT)
        downdestname.Add(downdestnamebtn, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
        downdestnamebox.Add(downdestname, 0, wx.EXPAND | wx.TOP, 0)

        self.rentorwithdest = wx.CheckBox(self, -1, self.utility.lang.get('rentorwithdest'))
        if self.utility.config.Read('defrentorwithdest', "boolean"):
            self.rentorwithdest.SetValue(True)
        else:
            self.rentorwithdest.SetValue(False)
        downdestnamebox.Add(self.rentorwithdest, 0, wx.TOP, 3)

        globalbox.Add(downdestlocbox, 0, wx.TOP, 6)
        globalbox.Add(downdestnamebox, 0, wx.TOP | wx.EXPAND, 6)

        outerbox.Add(globalbox, 0, wx.TOP, -4)

        buttonbox = wx.BoxSizer(wx.HORIZONTAL)
        okbtn = wx.Button(self, -1, self.utility.lang.get('ok'), style = wx.BU_EXACTFIT)
        cancelbtn = wx.Button(self, -1, self.utility.lang.get('cancel'), style = wx.BU_EXACTFIT)
        applybtn = wx.Button(self, -1, self.utility.lang.get('apply'), style = wx.BU_EXACTFIT)
        buttonbox.Add(applybtn, 0, wx.ALL, 5)
        buttonbox.Add(okbtn, 0, wx.ALL, 5)
        buttonbox.Add(cancelbtn, 0, wx.ALL, 5)

        outerbox.Add(buttonbox, 0, wx.ALIGN_CENTER)

        self.SetAutoLayout(True)
        self.SetSizer(outerbox)
        self.Fit()

        # Add events
        self.Bind(wx.EVT_BUTTON, self.onChangeLocation, downdestlocbtn)
        self.Bind(wx.EVT_BUTTON, self.onChangeName, downdestnamebtn)
        self.Bind(wx.EVT_BUTTON, self.onApply, applybtn)
        self.Bind(wx.EVT_BUTTON, self.onOK, okbtn)
        self.Bind(wx.EVT_BUTTON, self.onCancel, cancelbtn)
        self.Bind(wx.EVT_CLOSE, self.onCancel)

    def getPath(self):
        return self.newdest

    def onChangeLocation(self, event):
        dlg = wx.DirDialog(self, 
                           self.utility.lang.get('choosenewdestloc'), 
                           self.downdestloctext.GetValue(), 
                           style = wx.DD_DEFAULT_STYLE | wx.DD_NEW_DIR_BUTTON)
        result = dlg.ShowModal()
        dest = dlg.GetPath()
        dlg.Destroy()
        if result == wx.ID_OK:
            self.downdestloctext.SetValue(dest)

    def onChangeName(self, event = None):
        if self.torrent.files.isFile():
            dlg = wx.FileDialog(self, 
                               self.utility.lang.get('choosenewfilename'), 
                               self.downdestloctext.GetValue(), 
                               self.downdestnametext.GetValue(), 
                               self.utility.lang.get('allfileswildcard') + ' (*.*)|*.*', 
                               wx.SAVE)
        else:
            dlg = wx.DirDialog(self, 
                              self.utility.lang.get('choosenewdirname'), 
                              path.join(self.downdestloctext.GetValue(), self.downdestnametext.GetValue()), 
                              style = wx.DD_DEFAULT_STYLE | wx.DD_NEW_DIR_BUTTON)
        result = dlg.ShowModal()
        dest = dlg.GetPath()
        dlg.Destroy()
        if result == wx.ID_OK:
            self.downdestloctext.SetValue(path.split(dest)[0])
            self.downdestnametext.SetValue(path.split(dest)[1])

    def onCancel(self, event = None):
        self.EndModal(wx.ID_CANCEL)

    def onApply(self, event = None):
        newdowndestloc = self.downdestloctext.GetValue()
        newdowndestname = self.downdestnametext.GetValue()
        # Check if file and folder names are valid ones in Windows
        if sys.platform == 'win32':
            # We erase the final '\' except for a path like 'X:\'
            newdowndestloc_orig = newdowndestloc
            if newdowndestloc and newdowndestloc[-1] == '\\' and (len(newdowndestloc) < 2 or newdowndestloc[-2] != ':'):
                newdowndestloc = newdowndestloc[:-1]
            if not self.utility.checkWinPath(self, newdowndestloc_orig):
                return False
            fixedname = self.utility.fixWindowsName(newdowndestname)
            if fixedname:
                dlg = wx.MessageDialog(self, 
                                       newdowndestname + '\n' + \
                                       self.utility.lang.get('invalidwinname') + '\n'+ \
                                       self.utility.lang.get('suggestedname') + '\n\n' + \
                                       fixedname, 
                                       self.utility.lang.get('error'), wx.ICON_ERROR)
                dlg.ShowModal()
                dlg.Destroy()
                return False

        self.newdest = path.join(newdowndestloc, newdowndestname)
        # Change the destination
        
        renamewithdest = self.rentorwithdest.GetValue()
        
        self.torrent.files.changeProcDest(self.getPath(), renamewithdest)

        return True

    def onOK(self, event = None):
        if self.onApply():
            self.EndModal(wx.ID_OK)
