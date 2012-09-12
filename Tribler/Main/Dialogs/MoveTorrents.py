# Written by Niels Zeilemaker
# see LICENSE.txt for license information

import wx
import os
import sys

from Tribler.Main.vwxGUI.widgets import CheckSelectableListCtrl,\
    _set_font

class MoveTorrents(wx.Dialog):
    def __init__(self, parent, labels, download_states):
        wx.Dialog.__init__(self, parent, -1, 'Please select the torrents you want to move', size=(750,450))
        
        self.download_states = download_states
        vSizer = wx.BoxSizer(wx.VERTICAL)
        message = 'Please select all torrents which should be moved'
        message += "\nUse ctrl+a to select all/deselect all."
        
        firstLine = wx.StaticText(self, -1, message)
        _set_font(firstLine, fontweight = wx.FONTWEIGHT_BOLD)
        vSizer.Add(firstLine, 0, wx.EXPAND|wx.BOTTOM, 3)
              
        self.listCtrl = CheckSelectableListCtrl(self)
        self.listCtrl.InsertColumn(0, 'Torrent')
        self.listCtrl.InsertColumn(1, 'Current Location')
        
        self.listCtrl.setResizeColumn(0)
        
        for i, label in enumerate(labels):
            row = self.listCtrl.InsertStringItem(sys.maxint, label)
            
            download = download_states[i].get_download()
            self.listCtrl.SetStringItem(row, 1, download.get_dest_dir())

        self.listCtrl.SetColumnWidth(1, wx.LIST_AUTOSIZE)
        vSizer.Add(self.listCtrl, 1, wx.EXPAND|wx.BOTTOM|wx.TOP, 3)

        self.destTextCtrl = wx.TextCtrl(self)
        self.browseButton = wx.Button(self, -1, 'Browse')
        self.browseButton.Bind(wx.EVT_BUTTON, self.OnBrowse)
        
        moveTo = wx.StaticText(self, -1, 'Move to:')
        _set_font(moveTo, fontweight = wx.FONTWEIGHT_BOLD)
        vSizer.Add(moveTo)
        vSizer.Add(wx.StaticText(self, -1, 'Please note that all multi-file torrents create a directory themselves.\nYour new destination should specify the base dir for all torrents.'))
        
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(self.destTextCtrl, 1, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 3)
        hSizer.Add(self.browseButton, 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 3)
        vSizer.Add(hSizer, 0, wx.EXPAND|wx.BOTTOM, 3)
        
        self.moveFiles = wx.CheckBox(self, -1, 'Move files from current destination to new destination')
        self.ignoreFiles = wx.CheckBox(self, -1, 'Do not overwrite files already existing at new destination')
        
        vSizer.Add(self.moveFiles)
        vSizer.Add(self.ignoreFiles)
        
        cancel = wx.Button(self, wx.ID_CANCEL)
        cancel.Bind(wx.EVT_BUTTON, self.OnCancel)
        
        ok = wx.Button(self, wx.ID_OK)
        ok.Bind(wx.EVT_BUTTON, self.OnOk)
        
        bSizer = wx.StdDialogButtonSizer()
        bSizer.AddButton(cancel)
        bSizer.AddButton(ok)
        bSizer.Realize()
        vSizer.Add(bSizer, 0, wx.EXPAND|wx.BOTTOM, 3)
        
        sizer = wx.BoxSizer()
        sizer.Add(vSizer, 1, wx.EXPAND|wx.ALL, 10)
        self.SetSizer(sizer)
        
    def OnBrowse(self, event = None):
        dlg = wx.DirDialog(self,"Choose a new destination directory", style = wx.DEFAULT_DIALOG_STYLE)
        if dlg.ShowModal() == wx.ID_OK:
            self.destTextCtrl.SetValue(dlg.GetPath())
                
        dlg.Destroy()
        
    def GetSettings(self):
        selectedDownloads = []
        for i in range(self.listCtrl.GetItemCount()):
            if self.listCtrl.IsSelected(i):
                selectedDownloads.append(self.download_states[i])
         
        new_dir = self.destTextCtrl.GetValue()
        moveFiles = self.moveFiles.GetValue()
        ignoreIfExists = self.ignoreFiles.GetValue()
        return selectedDownloads, new_dir, moveFiles, ignoreIfExists

    def OnOk(self, event = None):
        if self.destTextCtrl.GetValue() != '':
            self.EndModal(wx.ID_OK)
        
    def OnCancel(self, event = None):
        self.EndModal(wx.ID_CANCEL)