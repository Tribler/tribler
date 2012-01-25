# Written by Niels Zeilemaker
# see LICENSE.txt for license information

import wx
import os
import sys

from Tribler.Main.vwxGUI.tribler_topButton import SelectableListCtrl

class MoveTorrents(wx.Dialog):
    def __init__(self, parent, labels, dstates):
        wx.Dialog.__init__(self, parent, -1, 'Please select the torrents you want to move', size=(600,450))
        
        self.dstates = dstates
        
        vSizer = wx.BoxSizer(wx.VERTICAL)
        message = 'Please select all torrents which should be moved'
        message += "\nUse ctrl+a to select all/deselect all."
        
        firstLine = wx.StaticText(self, -1, message)
        font = firstLine.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        firstLine.SetFont(font)
        vSizer.Add(firstLine, 0, wx.EXPAND|wx.BOTTOM, 3)
              
        self.listCtrl = SelectableListCtrl(self)
        self.listCtrl.InsertColumn(0, 'Torrent')
        self.listCtrl.setResizeColumn(0)
        
        for label in labels:
            self.listCtrl.InsertStringItem(sys.maxint, label)
        vSizer.Add(self.listCtrl, 1, wx.EXPAND|wx.BOTTOM|wx.TOP, 3)

        self.destTextCtrl = wx.TextCtrl(self)
        self.browseButton = wx.Button(self, -1, 'Browse')
        self.browseButton.Bind(wx.EVT_BUTTON, self.OnBrowse)
        
        vSizer.Add(wx.StaticText(self, -1, 'Move to:'))
        
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
                selectedDownloads.append(self.dstates[i])
         
        new_dir = self.destTextCtrl.GetValue()
        moveFiles = self.moveFiles.GetValue()
        ignoreIfExists = self.ignoreFiles.GetValue()
        return selectedDownloads, new_dir, moveFiles, ignoreIfExists

    def OnOk(self, event = None):
        if self.destTextCtrl.GetValue() != '':
            self.EndModal(wx.ID_OK)
        
    def OnCancel(self, event = None):
        self.EndModal(wx.ID_CANCEL)