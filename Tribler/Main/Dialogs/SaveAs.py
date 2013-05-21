# Written by Niels Zeilemaker
# see LICENSE.txt for license information

import wx
import os
import sys
from Tribler.Main.vwxGUI.widgets import CheckSelectableListCtrl, _set_font
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler import LIBRARYNAME
from Tribler.Core.TorrentDef import TorrentDefNoMetainfo, TorrentDef
from Tribler.Main.Utility.GuiDBHandler import GUI_PRI_DISPERSY, startWorker


class SaveAs(wx.Dialog):

    def __init__(self, parent, tdef, defaultdir, defaultname, configfile, selectedFiles=None):
        wx.Dialog.__init__(self, parent, -1, 'Please specify a target directory', size=(600, 450))

        self.filehistory = wx.FileHistory(25)
        self.config = wx.FileConfig(appName="Tribler", localFilename= configfile)
        self.filehistory.Load(self.config)
        self.defaultdir = defaultdir
        self.guiutility = GUIUtility.getInstance()
        self.listCtrl = None
        self.collected = None

        if self.filehistory.GetCount() > 0:
            lastUsed = self.filehistory.GetHistoryFile(0)
        else:
            lastUsed = defaultdir

        vSizer = wx.BoxSizer(wx.VERTICAL)

        if tdef:
            line = 'Please select a directory where to save:'
        else:
            line = 'Please select a directory where to save this torrent'

        firstLine = wx.StaticText(self, -1, line)
        _set_font(firstLine, fontweight=wx.FONTWEIGHT_BOLD)
        vSizer.Add(firstLine, 0, wx.EXPAND | wx.BOTTOM, 3)

        if tdef:
            torrentName = wx.StaticText(self, -1, tdef.get_name_as_unicode())
            torrentName.SetMinSize((1, -1))
            vSizer.Add(torrentName, 0, wx.EXPAND | wx.BOTTOM |wx.RIGHT, 3)

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(wx.StaticText(self, -1, 'Save as:'), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT |wx.BOTTOM, 3)

        choices = [self.filehistory.GetHistoryFile(i) for i in range(self.filehistory.GetCount())]
        if defaultdir not in choices:
            choices.append(defaultdir)

        if defaultname:
            choices.insert(0, os.path.join(lastUsed, defaultname))
            self.dirTextCtrl = wx.ComboBox(self, -1, os.path.join(lastUsed, defaultname), choices=choices, style= wx.CB_DROPDOWN)
        else:
            self.dirTextCtrl = wx.ComboBox(self, -1, lastUsed, choices=choices, style= wx.CB_DROPDOWN)
        self.dirTextCtrl.Select(0)

        hSizer.Add(self.dirTextCtrl, 1, wx.EXPAND | wx.RIGHT |wx.BOTTOM, 3)

        browseButton = wx.Button(self, -1, 'Browse')
        browseButton.Bind(wx.EVT_BUTTON, self.OnBrowseDir)
        hSizer.Add(browseButton)

        vSizer.Add(hSizer, 0, wx.EXPAND | wx.BOTTOM, 3)

        if tdef and tdef.get_files():
            self.AddFileList(tdef, selectedFiles, vSizer, len(vSizer.GetChildren()))
        elif isinstance(tdef, TorrentDefNoMetainfo):
            text = wx.StaticText(self, -1, "Attempting to retrieve .torrent...")
            _set_font(text, size_increment=1)
            ag = wx.animate.GIFAnimationCtrl(self, -1, os.path.join(self.guiutility.utility.getPath(), LIBRARYNAME, 'Main', 'vwxGUI', 'images', 'search_new.gif'))
            ag.Play()
            sizer = wx.BoxSizer(wx.HORIZONTAL)
            sizer.AddStretchSpacer()
            sizer.Add(text, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
            sizer.Add(ag, 0, wx.ALIGN_CENTER_VERTICAL)
            sizer.AddStretchSpacer()
            vSizer.Add(sizer, 1, wx.EXPAND | wx.BOTTOM, 3)
            self.SetSize((600, 150))

            url = tdef.get_url()
            if url and url.startswith("magnet:"):
                retrieve_from_magnet = lambda: TorrentDef.retrieve_from_magnet(url, lambda tdef: wx.CallAfter(self.SetCollected, tdef))
                startWorker(None, retrieve_from_magnet, retryOnBusy=True, priority= GUI_PRI_DISPERSY)
            else:
                torrentsearch_manager = self.guiutility.torrentsearch_manager

                def do_collect(delayedResult):
                    torrent = delayedResult.get()
                    if torrent:
                        def callback():
                            torrent_filename = torrentsearch_manager.getCollectedFilename(torrent)
                            tdef = TorrentDef.load(torrent_filename)
                            wx.CallAfter(self.SetCollected, tdef)
                        torrentsearch_manager.getTorrent(torrent, callback)

                def do_db():
                    return torrentsearch_manager.getTorrentByInfohash(tdef.get_infohash())
                startWorker(do_collect, do_db, retryOnBusy=True, priority= GUI_PRI_DISPERSY)

        cancel = wx.Button(self, wx.ID_CANCEL)
        cancel.Bind(wx.EVT_BUTTON, self.OnCancel)

        ok = wx.Button(self, wx.ID_OK)
        ok.Bind(wx.EVT_BUTTON, self.OnOk)

        bSizer = wx.StdDialogButtonSizer()
        bSizer.AddButton(cancel)
        bSizer.AddButton(ok)
        bSizer.Realize()
        vSizer.Add(bSizer, 0, wx.EXPAND | wx.BOTTOM, 3)

        sizer = wx.BoxSizer()
        sizer.Add(vSizer, 1, wx.EXPAND | wx.ALL, 10)
        self.SetSizer(sizer)

    def AddFileList(self, tdef, selectedFiles, vSizer, index=None):
        vSizer.Add(wx.StaticLine(self, -1), 0, wx.EXPAND | wx.BOTTOM, 10)

        firstLine = wx.StaticText(self, -1, "Content:")
        _set_font(firstLine, fontweight=wx.FONTWEIGHT_BOLD)
        vSizer.Add(firstLine, 0, wx.BOTTOM, 3)

        vSizer.Add(wx.StaticText(self, -1, 'Use the checkboxes to choose which files to download.\nUse ctrl+a to select all/deselect all.'), 0, wx.BOTTOM, 3)

        self.listCtrl = CheckSelectableListCtrl(self)
        self.listCtrl.InsertColumn(0, 'Name')
        self.listCtrl.InsertColumn(1, 'Size', wx.LIST_FORMAT_RIGHT)

        # Add files
        def sort_by_size(a, b):
            return cmp(a[1], b[1])

        files = tdef.get_files_as_unicode_with_length()
        files.sort(sort_by_size, reverse=True)

        for filename, size in files:
            try:
                pos = self.listCtrl.InsertStringItem(sys.maxsize, filename)
            except:
                try:
                    pos = self.listCtrl.InsertStringItem(sys.maxsize, filename.decode('utf-8', 'ignore'))
                except:
                    print >> sys.stderr, "Could not format filename", self.torrent.name
            self.listCtrl.SetItemData(pos, pos)
            self.listCtrl.SetStringItem(pos, 1, self.guiutility.utility.size_format(size))

            if selectedFiles:
                self.listCtrl.CheckItem(pos, filename in selectedFiles)

        if selectedFiles == None:
            self.listCtrl.doSelectAll()

        self.listCtrl.setResizeColumn(0)
        self.listCtrl.SetColumnWidth(1, wx.LIST_AUTOSIZE)  # autosize only works after adding rows
        vSizer.Add(self.listCtrl, 1, wx.EXPAND | wx.BOTTOM, 3)

        self.listCtrl.SetFocus()

        def OnKeyUp(event):
            if event.GetKeyCode() == wx.WXK_RETURN:
                self.OnOk()
            else:
                event.Skip()
        self.listCtrl.Bind(wx.EVT_KEY_UP, OnKeyUp)

    def SetCollected(self, tdef):
        self.collected = tdef
        self.SetSize((600, 450))
        vSizer = self.GetSizer().GetItem(0).GetSizer()
        hsizer = vSizer.GetItem(len(vSizer.GetChildren()) - 2).GetSizer()
        self.Freeze()
        hsizer.Clear(deleteWindows=True)
        vSizer.Remove(hsizer)
        self.AddFileList(tdef, None, vSizer, len(vSizer.GetChildren()) - 1)
        self.Layout()
        self.Refresh()
        self.Thaw()

    def GetCollected(self):
        return self.collected

    def GetPath(self):
        return self.dirTextCtrl.GetValue().strip()

    def GetSelectedFiles(self):
        if self.listCtrl:
            selected = self.listCtrl.GetSelectedItems()
            nrSelected = len(selected)

            if nrSelected > 0 and nrSelected < self.listCtrl.GetItemCount():
                files = []
                for index in selected:
                    files.append(self.listCtrl.GetItem(index, 0).GetText())
                return files
        return None

    def OnOk(self, event=None):
        if self.listCtrl:
            nrSelected = len(self.listCtrl.GetSelectedItems())
            if nrSelected == 0:
                dlg = wx.MessageDialog(self, "Please select at least one file to be downloaded using the checkboxes.", "Please select a file to be downloaded", wx.ICON_ERROR)
                dlg.ShowModal()
                dlg.Destroy()
                return

        path = self.GetPath()
        if not os.path.exists(path) or os.path.isfile(path):
            path, _ = os.path.split(path)
        self.filehistory.AddFileToHistory(path)

        self.filehistory.Save(self.config)
        self.config.Flush()

        self.EndModal(wx.ID_OK)

    def OnCancel(self, event=None):
        self.EndModal(wx.ID_CANCEL)

    def OnBrowseDir(self, event):
        dlg = wx.DirDialog(self, "Please select a directory to save this torrent", style=wx.wx.DD_NEW_DIR_BUTTON)
        dlg.SetPath(self.defaultdir)

        if dlg.ShowModal() == wx.ID_OK and os.path.isdir(dlg.GetPath()):
            self.dirTextCtrl.SetValue(dlg.GetPath())
        dlg.Destroy()
