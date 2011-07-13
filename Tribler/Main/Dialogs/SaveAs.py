# Written by Niels Zeilemaker
# see LICENSE.txt for license information

import wx

class SaveAs(wx.Dialog):
    def __init__(self, parent, torrentdef, defaultdir, configfile):
        wx.Dialog.__init__(self, parent, -1, 'Please specify a target directory', size=(600,450))
        
        self.filehistory = wx.FileHistory(10)
        self.config = wx.FileConfig(appName = "Tribler", localFilename = configfile)
        self.filehistory.Load(self.config)
        
        if self.filehistory.GetCount() > 0:
            lastUsed = self.filehistory.GetHistoryFile(0)
        else:
            lastUsed = defaultdir
        
        vSizer = wx.BoxSizer(wx.VERTICAL)
        
        firstLine = wx.StaticText(self, -1, 'Please select a directory where to save:')
        font = firstLine.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        firstLine.SetFont(font)
        vSizer.Add(firstLine, 0, wx.EXPAND|wx.BOTTOM, 3)
        
        torrentName = wx.StaticText(self, -1, torrentdef.get_name())
        torrentName.SetMinSize((1, -1))
        vSizer.Add(torrentName, 0, wx.LEFT|wx.EXPAND, 10)
        
        self.dirCtrl = wx.GenericDirCtrl(self, -1, style = wx.DIRCTRL_DIR_ONLY|wx.SUNKEN_BORDER)
        self.dirCtrl.Bind(wx.EVT_TREE_SEL_CHANGED, self.OnDirChange)
        
        vSizer.Add(self.dirCtrl, 1, wx.EXPAND|wx.BOTTOM|wx.TOP, 3)
        
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(wx.StaticText(self, -1, 'Save to:'), 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 3)
        
        self.dirTextCtrl = wx.ComboBox(self, -1, lastUsed, style = wx.CB_DROPDOWN)
        for i in range(self.filehistory.GetCount()):
            self.dirTextCtrl.Append(self.filehistory.GetHistoryFile(i))
        
        if self.dirTextCtrl.FindString(defaultdir) == wx.NOT_FOUND:
            self.dirTextCtrl.Append(defaultdir)
        
        self.dirCtrl.SetDefaultPath(defaultdir)
        self.dirCtrl.SetPath(lastUsed)
        
        hSizer.Add(self.dirTextCtrl, 1, wx.EXPAND)
        vSizer.Add(hSizer, 0, wx.EXPAND|wx.BOTTOM, 3)
        
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
        sizer.Add(vSizer, 1, wx.EXPAND|wx.ALL, 5)
        self.SetSizer(sizer)
        
    def GetPath(self):
        return self.dirTextCtrl.GetValue().strip()

    def OnDirChange(self, event = None):
        self.dirTextCtrl.SetValue(self.dirCtrl.GetPath())
        
    def OnOk(self, event = None):
        self.filehistory.AddFileToHistory(self.GetPath())
        self.filehistory.Save(self.config)
        self.config.Flush()
        
        self.EndModal(wx.ID_OK)
        
    def OnCancel(self, event = None):
        self.EndModal(wx.ID_CANCEL)