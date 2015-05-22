# Written by Niels Zeilemaker
# see LICENSE.txt for license information

import wx
import wx.lib.newevent
import os
import sys
import json
import copy
import logging

from Tribler.Main.vwxGUI.widgets import CheckSelectableListCtrl, _set_font, AnonymityDialog
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler import LIBRARYNAME
from Tribler.Core.TorrentDef import TorrentDefNoMetainfo, TorrentDef
from Tribler.Main.Utility.GuiDBTuples import Torrent
from Tribler.Main.Utility.utility import size_format


CollectedEvent, EVT_COLLECTED = wx.lib.newevent.NewEvent()


class SaveAs(wx.Dialog):

    def __init__(self, parent, tdef, defaultdir, defaultname, selectedFiles=None):
        self._logger = logging.getLogger(self.__class__.__name__)
        wx.Dialog.__init__(self, parent, -1, 'Please specify a target directory', name="SaveAsDialog")

        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility
        self.tunnel_community_enabled = self.utility.session.get_tunnel_community_enabled()
        self.SetSize((600, 550 if self.tunnel_community_enabled else 450))

        self.filehistory = []
        try:
            self.filehistory = json.loads(self.utility.read_config("recent_download_history", literal_eval=False))
        except:
            pass

        self.defaultdir = defaultdir
        self.listCtrl = None
        self.collected = tdef

        lastUsed = self.filehistory[0] if self.filehistory else defaultdir

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
            vSizer.Add(torrentName, 0, wx.EXPAND | wx.BOTTOM | wx.RIGHT, 3)

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(wx.StaticText(self, -1, 'Save as:'), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT | wx.BOTTOM, 3)

        choices = copy.copy(self.filehistory)
        if defaultdir not in choices:
            choices.append(defaultdir)

        if defaultname:
            choices.insert(0, os.path.join(lastUsed, defaultname))
            self.dirTextCtrl = wx.ComboBox(self, -1, os.path.join(
                lastUsed, defaultname), choices=choices, style=wx.CB_DROPDOWN)
        else:
            self.dirTextCtrl = wx.ComboBox(self, -1, lastUsed, choices=choices, style=wx.CB_DROPDOWN)
        self.dirTextCtrl.Select(0)

        hSizer.Add(self.dirTextCtrl, 1, wx.EXPAND | wx.RIGHT | wx.BOTTOM, 3)

        browseButton = wx.Button(self, -1, 'Browse')
        browseButton.Bind(wx.EVT_BUTTON, self.OnBrowseDir)
        hSizer.Add(browseButton)

        vSizer.Add(hSizer, 0, wx.EXPAND | wx.BOTTOM, 3)

        self.cancel = wx.Button(self, wx.ID_CANCEL)
        self.cancel.Bind(wx.EVT_BUTTON, self.OnCancel)

        self.ok = wx.Button(self, wx.ID_OK)
        self.ok.Bind(wx.EVT_BUTTON, self.OnOk)

        self.anonimity_dialog = None
        if self.tunnel_community_enabled:
            self.anonimity_dialog = AnonymityDialog(self)
            vSizer.Add(self.anonimity_dialog, 0, wx.EXPAND, 3)

        self.Bind(EVT_COLLECTED, self.OnCollected)

        # Add file list
        if tdef and tdef.get_files():
            self.AddFileList(tdef, selectedFiles, vSizer, len(vSizer.GetChildren()))

        elif isinstance(tdef, TorrentDefNoMetainfo):
            self.ok_force_enabled = False
            self.OkButtonVisibility()
            text = wx.StaticText(self, -1, "Attempting to retrieve .torrent...")
            _set_font(text, size_increment=1)
            ag = wx.animate.GIFAnimationCtrl(self, -1, os.path.join(
                self.guiutility.utility.getPath(), LIBRARYNAME, 'Main', 'vwxGUI', 'images', 'search_new.gif'))
            ag.Play()
            sizer = wx.BoxSizer(wx.HORIZONTAL)
            sizer.AddStretchSpacer()
            sizer.Add(text, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
            sizer.Add(ag, 0, wx.ALIGN_CENTER_VERTICAL)
            sizer.AddStretchSpacer()
            vSizer.Add(sizer, 1, wx.EXPAND | wx.BOTTOM, 3)
            self.SetSize((600, 385 if self.tunnel_community_enabled else 185))

            # convert tdef into guidbtuple, and collect it using torrentsearch_manager.downloadTorrentfileFromPeers
            torrent = Torrent.fromTorrentDef(tdef)
            torrentsearch_manager = self.guiutility.torrentsearch_manager

            def callback(saveas_id, infohash):
                self.ok_force_enabled = True
                self.OkButtonVisibility()
                saveas = wx.FindWindowById(saveas_id)
                if saveas:
                    tdef = TorrentDef.load_from_memory(self.utility.session.lm.torrent_store.get(infohash))
                    event = CollectedEvent(tdef=tdef)
                    wx.PostEvent(saveas, event)

            cb = lambda torrent_filename, saveas_id = self.Id: callback(saveas_id, torrent_filename)
            torrentsearch_manager.downloadTorrentfileFromPeers(torrent, cb)

        bSizer = wx.StdDialogButtonSizer()
        bSizer.AddButton(self.cancel)
        bSizer.AddButton(self.ok)
        bSizer.Realize()
        vSizer.Add(bSizer, 0, wx.EXPAND | wx.BOTTOM, 3)

        sizer = wx.BoxSizer()
        sizer.Add(vSizer, 1, wx.EXPAND | wx.ALL, 10)
        self.SetSizer(sizer)

    def OkButtonVisibility(self):
        if self.UseProxies() and not self.ok_force_enabled:
            self.ok.Disable()
        else:
            self.ok.Enable()

    def AddFileList(self, tdef, selectedFiles, vSizer, index):
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
                    self._logger.error("Could not format filename %s", self.torrent.name)
            self.listCtrl.SetItemData(pos, pos)
            self.listCtrl.SetStringItem(pos, 1, size_format(size))

            if selectedFiles:
                self.listCtrl.CheckItem(pos, filename in selectedFiles)

        if selectedFiles is None:
            self.listCtrl.doSelectAll()

        self.listCtrl.setResizeColumn(0)
        self.listCtrl.SetColumnWidth(1, wx.LIST_AUTOSIZE)  # autosize only works after adding rows
        vSizer.Insert(index, self.listCtrl, 1, wx.EXPAND | wx.BOTTOM, 3)

        self.listCtrl.SetFocus()

        def OnChar(event):
            if event.GetKeyCode() == wx.WXK_RETURN:
                self.OnOk()
            else:
                event.Skip()
        self.listCtrl.Bind(wx.EVT_CHAR, OnChar)

        vSizer.Insert(index, wx.StaticText(
            self, -1, 'Use the checkboxes to choose which files to download.\nUse ctrl+a to select all/deselect all.'), 0, wx.BOTTOM, 3)

        firstLine = wx.StaticText(self, -1, "Content:")
        _set_font(firstLine, fontweight=wx.FONTWEIGHT_BOLD)
        vSizer.Insert(index, firstLine, 0, wx.BOTTOM, 3)

        vSizer.Insert(index, wx.StaticLine(self, -1), 0, wx.EXPAND | wx.BOTTOM, 10)

    def OnCollected(self, event):
        tdef = event.tdef
        self.collected = tdef
        self.SetSize((600, 575 if self.tunnel_community_enabled else 475))
        vSizer = self.GetSizer().GetItem(0).GetSizer()
        hsizer = vSizer.GetItem(len(vSizer.GetChildren()) - 2).GetSizer()
        self.Freeze()
        hsizer.Clear(deleteWindows=True)
        vSizer.Remove(hsizer)
        self.AddFileList(tdef, None, vSizer, len(vSizer.GetChildren()) - 1)

        if tdef.is_multifile_torrent():
            items = self.dirTextCtrl.GetItems()
            lastUsed = self.filehistory[0] if self.filehistory else self.defaultdir
            path = os.path.join(lastUsed, tdef.get_name_as_unicode())
            if path not in items:
                items.insert(0, path)
                self.dirTextCtrl.SetItems(items)
            self.dirTextCtrl.SetStringSelection(path)

        self.Layout()
        self.Refresh()
        self.Thaw()

    def GetCollected(self):
        return self.collected

    def GetPath(self):
        return self.dirTextCtrl.GetValue().strip().rstrip(os.path.sep)

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

    def UseHiddenservices(self):
        return self.anonimity_dialog and self.anonimity_dialog.UseHiddenServices()

    def UseProxies(self):
        return self.anonimity_dialog and self.anonimity_dialog.UseProxies()

    def GetDownloadPolicyValue(self):
        return self.anonimity_dialog and self.anonimity_dialog.GetDownloadPolicyValue()

    def OnOk(self, event=None):
        if self.listCtrl:
            nrSelected = len(self.listCtrl.GetSelectedItems())
            if nrSelected == 0:
                dlg = wx.MessageDialog(
                    self, "Please select at least one file to be downloaded using the checkboxes.", "Please select a file to be downloaded", wx.ICON_ERROR)
                dlg.ShowModal()
                dlg.Destroy()
                return

        path = self.GetPath()
        history_path = os.path.split(path)[0] if (self.collected and self.collected.is_multifile_torrent()) or \
            not os.path.exists(path) or os.path.isfile(path) else path
        if history_path in self.filehistory:
            self.filehistory.remove(history_path)
        self.filehistory.insert(0, history_path)
        self.filehistory = self.filehistory[:25]

        self.utility.write_config("recent_download_history", json.dumps(self.filehistory))
        self.utility.flush_config()

        self.EndModal(wx.ID_OK)

    def OnCancel(self, event=None):
        self.EndModal(wx.ID_CANCEL)

    def OnBrowseDir(self, event):
        dlg = wx.DirDialog(None, "Please select a directory to save this torrent", style=wx.wx.DD_NEW_DIR_BUTTON)
        dlg.SetPath(self.defaultdir)

        if dlg.ShowModal() == wx.ID_OK and os.path.isdir(dlg.GetPath()):
            self.dirTextCtrl.SetValue(dlg.GetPath())
        dlg.Destroy()
