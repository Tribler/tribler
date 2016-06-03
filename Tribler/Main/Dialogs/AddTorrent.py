# Written by Niels Zeilemaker
# see LICENSE.txt for license information

import wx
import os

from Tribler.Core.DownloadConfig import DefaultDownloadStartupConfig
from Tribler.Main.vwxGUI.widgets import _set_font
from Tribler.Main.Dialogs.CreateTorrentDialog import CreateTorrentDialog
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility


class AddTorrent(wx.Dialog):

    def __init__(self, parent, frame, libraryTorrents=None):
        wx.Dialog.__init__(self, parent, -1, 'Add an external .torrent', size=(500, 200), name="AddTorrentDialog")

        self.frame = frame
        self.guiutility = GUIUtility.getInstance()
        self.toChannel = libraryTorrents is not None
        self.defaultDLConfig = DefaultDownloadStartupConfig.getInstance()

        vSizer = wx.BoxSizer(wx.VERTICAL)

        firstLine = wx.StaticText(self, -1, 'Please use one of the provided methods to import an external .torrent')
        vSizer.Add(firstLine, 0, wx.EXPAND | wx.BOTTOM, 3)
        vSizer.AddSpacer((-1, 25))

        header = wx.StaticText(self, -1, 'Browse for local .torrent file or files')
        _set_font(header, fontweight=wx.FONTWEIGHT_BOLD)
        vSizer.Add(header, 0, wx.EXPAND | wx.BOTTOM, 3)
        vSizer.Add(
            wx.StaticText(self, -1, 'Use this option if you have downloaded a .torrent manually'), 0, wx.BOTTOM, 3)

        browseButton = wx.Button(self, -1, 'Browse')
        browseButton.Bind(wx.EVT_BUTTON, self.OnBrowse)

        browseDirectory = wx.Button(self, -1, 'Browse for Directory')
        browseDirectory.Bind(wx.EVT_BUTTON, self.OnBrowseDir)

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(browseButton, 0, wx.RIGHT, 3)
        hSizer.Add(browseDirectory)
        vSizer.Add(hSizer, 0, wx.ALIGN_RIGHT | wx.BOTTOM, 3)
        vSizer.Add(wx.StaticLine(self, -1), 0, wx.EXPAND | wx.BOTTOM, 10)

        header = wx.StaticText(self, -1, 'Url')
        _set_font(header, fontweight=wx.FONTWEIGHT_BOLD)
        vSizer.Add(header, 0, wx.EXPAND | wx.BOTTOM | wx.TOP, 3)
        vSizer.Add(wx.StaticText(self, -1, 'This could either be a http, magnet, emc, or file link'), 0, wx.BOTTOM, 3)

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.magnet = wx.TextCtrl(self, -1)
        hSizer.Add(self.magnet, 1, wx.ALIGN_CENTER_VERTICAL)
        linkButton = wx.Button(self, -1, "Add")
        linkButton.Bind(wx.EVT_BUTTON, self.OnAdd)
        hSizer.Add(linkButton, 0, wx.LEFT, 3)
        vSizer.Add(hSizer, 0, wx.EXPAND | wx.BOTTOM, 3)

        vSizer.Add(wx.StaticLine(self, -1), 0, wx.EXPAND | wx.BOTTOM, 10)
        if libraryTorrents is not None:
            if len(libraryTorrents) > 0:
                header = wx.StaticText(self, -1, 'Choose one from your library')
                _set_font(header, fontweight=wx.FONTWEIGHT_BOLD)
                vSizer.Add(header, 0, wx.EXPAND | wx.BOTTOM | wx.TOP, 3)

                torrentNames = [torrent.name for torrent in libraryTorrents]

                hSizer = wx.BoxSizer(wx.HORIZONTAL)
                self.libraryChoice = wx.Choice(self, -1, choices=torrentNames)
                self.libraryChoice.torrents = libraryTorrents
                hSizer.Add(self.libraryChoice, 1, wx.ALIGN_CENTER_VERTICAL)

                linkButton = wx.Button(self, -1, "Add")
                linkButton.Bind(wx.EVT_BUTTON, self.OnLibrary)

                hSizer.Add(linkButton, 0, wx.LEFT, 3)
                vSizer.Add(hSizer, 0, wx.EXPAND | wx.BOTTOM, 3)

            vSizer.Add(wx.StaticLine(self, -1), 0, wx.EXPAND | wx.BOTTOM, 10)
            header = wx.StaticText(self, -1, 'Create your own .torrents')
            _set_font(header, fontweight=wx.FONTWEIGHT_BOLD)
            vSizer.Add(header, 0, wx.EXPAND | wx.BOTTOM | wx.TOP, 3)
            vSizer.Add(wx.StaticText(self, -1, 'Using your own local files'), 0, wx.BOTTOM, 3)

            create = wx.Button(self, -1, 'Create')
            create.Bind(wx.EVT_BUTTON, self.OnCreate)
            vSizer.Add(create, 0, wx.ALIGN_RIGHT | wx.BOTTOM, 3)

        sizer = wx.BoxSizer()
        sizer.Add(vSizer, 1, wx.EXPAND | wx.ALL, 10)
        self.SetSizerAndFit(sizer)

    def OnAdd(self, event):
        filename = self.magnet.GetValue().strip()
        if self.frame.startDownloadFromArg(filename):
            self.EndModal(wx.ID_OK)

    def OnLibrary(self, event):
        selection = self.libraryChoice.GetCurrentSelection()
        if selection >= 0:
            torrent = self.libraryChoice.torrents[selection]

            if self.frame.startDownloadFromTorrent(torrent):
                self.EndModal(wx.ID_OK)

    def __processPaths(self, paths):
        filenames = []
        for filename in paths:
            if filename.endswith('.torrent'):
                filenames.append(filename)

        cancel = len(filenames) == 0
        if len(filenames) > 10:
            warning = wx.MessageDialog(self, "This will add %d .torrents, are you sure?" %
                                       len(filenames), "Please confirm Add", wx.OK | wx.CANCEL | wx.ICON_WARNING)
            if warning.ShowModal() != wx.ID_OK:
                cancel = True

            warning.Destroy()

        should_close_main_dialog = True

        if not cancel:
            for filename in filenames:
                if not self.frame.startDownload(filename): # Something went wrong when adding the download
                    should_close_main_dialog = False

        return should_close_main_dialog

    def OnBrowse(self, event):
        dlg = wx.FileDialog(None, "Please select the .torrent file(s).",
                            wildcard="torrent (*.torrent)|*.torrent", style=wx.FD_OPEN | wx.FD_MULTIPLE)

        path = DefaultDownloadStartupConfig.getInstance().get_dest_dir() + os.sep
        dlg.SetPath(path)

        if dlg.ShowModal() == wx.ID_OK:
            filenames = dlg.GetPaths()
            dlg.Destroy()

            if self.__processPaths(filenames):
                self.EndModal(wx.ID_OK)
        else:
            dlg.Destroy()

    def OnBrowseDir(self, event):
        dlg = wx.DirDialog(None, "Please select a directory contain the .torrent files", style=wx.wx.DD_DIR_MUST_EXIST)

        path = DefaultDownloadStartupConfig.getInstance().get_dest_dir() + os.sep
        dlg.SetPath(path)

        if dlg.ShowModal() == wx.ID_OK and os.path.isdir(dlg.GetPath()):
            filenames = [os.path.join(dlg.GetPath(), file) for file in os.listdir(dlg.GetPath())]
            dlg.Destroy()

            if self.__processPaths(filenames):
                self.EndModal(wx.ID_OK)

        dlg.Destroy()

    def OnCreate(self, event):
        configfile = os.path.join(self.guiutility.utility.session.get_state_dir(), 'recent_trackers')
        configfile2 = os.path.join(self.guiutility.utility.session.get_state_dir(), 'recent_created')
        trackers = self.guiutility.channelsearch_manager.torrent_db.getRecentlyAliveTrackers()

        dlg = CreateTorrentDialog(None, configfile, configfile2, trackers, self.toChannel)
        if dlg.ShowModal() == wx.ID_OK:
            for destdir, torrentfilename in dlg.createdTorrents:
                # Niels: important do not pass fixtorrent to startDownload, used to
                # differentiate between created and imported torrents
                self.frame.startDownload(torrentfilename=torrentfilename, destdir=destdir)

            dlg.Destroy()
            self.EndModal(wx.ID_OK)

        dlg.Destroy()
