# Written by Niels Zeilemaker
# see LICENSE.txt for license information

import wx
import os

from Tribler.Main.Dialogs.SaveAs import SaveAs
from Tribler.Main.globals import DefaultDownloadStartupConfig

class AddTorrent(wx.Dialog):
    def __init__(self, parent, frame):
        wx.Dialog.__init__(self, parent, -1, 'Add an external .torrent', size=(500,150))
        self.frame = frame
        self.defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
        
        vSizer = wx.BoxSizer(wx.VERTICAL)
        
        firstLine = wx.StaticText(self, -1, 'Please use one of the provided methods to import an external .torrent')
        vSizer.Add(firstLine, 0, wx.EXPAND|wx.BOTTOM, 3)
        vSizer.AddSpacer((-1, 25))
        
        header = wx.StaticText(self, -1, 'Browse for local .torrent file or files')
        font = header.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        header.SetFont(font)
        vSizer.Add(header, 0, wx.EXPAND|wx.BOTTOM, 3)
        vSizer.Add(wx.StaticText(self, -1, 'Use this option if you have downloaded a .torrent manually'), 0, wx.BOTTOM, 3)
        
        browseButton = wx.Button(self, -1, 'Browse')
        browseButton.Bind(wx.EVT_BUTTON, self.OnBrowse)
        vSizer.Add(browseButton, 0, wx.ALIGN_RIGHT|wx.BOTTOM, 3)
        vSizer.Add(wx.StaticLine(self, -1), 0, wx.EXPAND|wx.LEFT|wx.RIGHT, 10)
        
        header = wx.StaticText(self, -1, 'Url')
        font = header.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        header.SetFont(font)
        vSizer.Add(header, 0, wx.EXPAND|wx.BOTTOM|wx.TOP, 3)
        vSizer.Add(wx.StaticText(self, -1, 'This could either be a direct http-link (starting with http://), or a magnet link'), 0, wx.BOTTOM, 3)
        
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.magnet = wx.TextCtrl(self, -1)
        hSizer.Add(self.magnet, 1, wx.ALIGN_CENTER_VERTICAL)
        linkButton = wx.Button(self, -1, "Add")
        linkButton.Bind(wx.EVT_BUTTON, self.OnAdd)
        hSizer.Add(linkButton, 0, wx.LEFT, 3)
        vSizer.Add(hSizer, 0 , wx.EXPAND|wx.BOTTOM, 3)
        
        self.choose = wx.CheckBox(self, -1, "Let me choose a downloadlocation for these torrents")
        self.choose.SetValue(self.defaultDLConfig.get_show_saveas())
        vSizer.Add(wx.StaticLine(self, -1), 0, wx.EXPAND|wx.LEFT|wx.RIGHT, 10)
        vSizer.Add(self.choose, 0, wx.EXPAND|wx.TOP|wx.BOTTOM, 3)
        
        sizer = wx.BoxSizer()
        sizer.Add(vSizer, 1, wx.EXPAND|wx.ALL, 10)
        self.SetSizerAndFit(sizer)
        
    def OnAdd(self, event):
        input = self.magnet.GetValue().strip()
        if input.startswith("http://"):
            destdir = self.defaultDLConfig.get_dest_dir()
            if self.choose.IsChecked():
                destdir = self._GetDestPath()
                if not destdir:
                    return
                
            if self.frame.startDownloadFromUrl(str(input), destdir):
                self.EndModal(wx.ID_OK)
            
        elif input.startswith("magnet:"):
            destdir = self.defaultDLConfig.get_dest_dir()
            if self.choose.IsChecked():
                destdir = self._GetDestPath()
                if not destdir:
                    return
            
            if self.frame.startDownloadFromMagnet(str(input), destdir):
                self.EndModal(wx.ID_OK)
        
    def OnBrowse(self, event):
        dlg = wx.FileDialog(None, "Please select the .torrent file(s).", wildcard = "torrent (*.torrent)|*.torrent", style = wx.FD_OPEN|wx.FD_MULTIPLE)
        if dlg.ShowModal() == wx.ID_OK:
            filenames = dlg.GetPaths()
            dlg.Destroy()
            
            destdir = self.defaultDLConfig.get_dest_dir()
            if self.choose.IsChecked():
                destdir = self._GetDestPath()
                if not destdir:
                    return
            
            for filename in filenames:
                self.frame.startDownload(filename, fixtorrent = True, destdir = destdir)
                
            self.EndModal(wx.ID_OK)
        else:
            dlg.Destroy()
    
    def _GetDestPath(self):
        dlg = SaveAs(self, None, self.defaultDLConfig.get_dest_dir(), os.path.join(self.frame.utility.session.get_state_dir(), 'recent_download_history'))
        id = dlg.ShowModal()
        
        if id == wx.ID_OK:
            destdir = dlg.GetPath()
        else:
            destdir = None
        dlg.Destroy()
        return destdir