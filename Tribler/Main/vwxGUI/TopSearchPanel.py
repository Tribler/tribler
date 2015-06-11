# Written by Niels Zeilemaker
import os
import sys
import logging
import wx.animate

from Tribler import LIBRARYNAME
from Tribler.Core.simpledefs import NTFY_TORRENTS

from Tribler.Main.Utility.GuiDBTuples import CollectedTorrent, Torrent
from Tribler.Main.Utility.GuiDBHandler import startWorker, cancelWorker
from Tribler.Main.vwxGUI import forceWxThread, TRIBLER_RED, SEPARATOR_GREY, GRADIENT_LGREY, GRADIENT_DGREY
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.GuiImageManager import GuiImageManager
from Tribler.Main.vwxGUI.widgets import ActionButton, FancyPanel, TextCtrlAutoComplete, ProgressButton
from Tribler.Main.Dialogs.AddTorrent import AddTorrent
from Tribler.Main.Dialogs.RemoveTorrent import RemoveTorrent


class TopSearchPanel(FancyPanel):

    def __init__(self, parent):
        self._logger = logging.getLogger(self.__class__.__name__)

        self._logger.debug("TopSearchPanel: __init__")

        self.loaded_bitmap = None

        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility
        self.installdir = self.utility.getPath()
        self.tdb = self.utility.session.open_dbhandler(NTFY_TORRENTS)
        self.collectedTorrents = {}

        FancyPanel.__init__(self, parent, border=wx.BOTTOM)
        self.SetBorderColour(SEPARATOR_GREY)
        self.SetBackgroundColour(GRADIENT_LGREY, GRADIENT_DGREY)
        self.AddComponents()
        self.Bind(wx.EVT_SIZE, self.OnResize)

    def AddComponents(self):
        self.SetForegroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT))

        self._logger.debug("TopSearchPanel: OnCreate")

        gui_image_manager = GuiImageManager.getInstance()

        if sys.platform == 'darwin':
            self.searchField = wx.SearchCtrl(self, -1, "", style=wx.TE_PROCESS_ENTER | wx.NO_BORDER)
            self.searchField.Bind(wx.EVT_SEARCHCTRL_SEARCH_BTN, self.OnSearchKeyDown)
            self.searchField.Bind(wx.EVT_TEXT_ENTER, self.OnSearchKeyDown)
            self.searchField.SetDescriptiveText('Search Files or Channels')
            self.searchField.SetMinSize((400, 20))
        else:
            self.searchFieldPanel = FancyPanel(self, radius=5, border=wx.ALL)
            self.searchFieldPanel.SetBorderColour(SEPARATOR_GREY, highlight=TRIBLER_RED)
            self.searchField = TextCtrlAutoComplete(self.searchFieldPanel, style=wx.NO_BORDER,
                                                    entrycallback=self.complete)
            # Since we have set the style to wx.NO_BORDER, the default height will be
            # too large. Therefore, we need to set the correct height.
            _, height = self.GetTextExtent("Gg")
            self.searchField.SetMinSize((-1, height))
            self.searchFieldPanel.SetMinSize((400, 25))
            self.searchFieldPanel.SetBackgroundColour(self.searchField.GetBackgroundColour())
            self.searchField.Bind(wx.EVT_KILL_FOCUS, self.searchFieldPanel.OnKillFocus)
            self.searchField.Bind(wx.EVT_TEXT_ENTER, self.OnSearchKeyDown)

        self.go = ProgressButton(self, -1)
        self.go.SetMinSize((50, 25))
        self.go.Bind(wx.EVT_LEFT_UP, self.OnSearchKeyDown)

        ag_fname = os.path.join(self.guiutility.utility.getPath(),
                                LIBRARYNAME, 'Main', 'vwxGUI', 'images', 'search_new.gif')
        self.ag = wx.animate.GIFAnimationCtrl(self, -1, ag_fname)
        self.ag.UseBackgroundColour(True)
        self.ag.SetBackgroundColour(wx.Colour(244, 244, 244))
        self.ag.Hide()

        download_bmp = gui_image_manager.getImage(u"download.png")
        self.download_btn = ActionButton(self, -1, download_bmp)
        self.download_btn.Enable(False)
        upload_bmp = gui_image_manager.getImage(u"upload.png")
        self.upload_btn = ActionButton(self, -1, upload_bmp)
        self.upload_btn.Enable(False)
        stop_bmp = gui_image_manager.getImage(u"pause.png")
        self.stop_btn = ActionButton(self, -1, stop_bmp)
        self.stop_btn.Enable(False)
        delete_bmp = gui_image_manager.getImage(u"delete.png")
        self.delete_btn = ActionButton(self, -1, delete_bmp)
        self.delete_btn.Enable(False)
        play_bmp = gui_image_manager.getImage(u"play.png")
        self.play_btn = ActionButton(self, -1, play_bmp)
        self.play_btn.Enable(False)
        add_bmp = gui_image_manager.getImage(u"add.png")
        self.add_btn = ActionButton(self, -1, add_bmp)
        self.SetButtonHandler(self.add_btn, self.OnAdd, 'Download an external torrent.')
        settings_bmp = gui_image_manager.getImage(u"settings.png")
        self.settings_btn = ActionButton(self, -1, settings_bmp)
        self.SetButtonHandler(self.settings_btn, self.OnSettings, 'Change settings.')

        mainSizer = wx.BoxSizer(wx.HORIZONTAL)

        if sys.platform != 'darwin':
            vSizer = wx.BoxSizer(wx.VERTICAL)
            vSizer.AddStretchSpacer()
            vSizer.Add(self.searchField, 0, wx.EXPAND | wx.RESERVE_SPACE_EVEN_IF_HIDDEN | wx.LEFT | wx.RIGHT, 5)
            vSizer.AddStretchSpacer()
            self.searchFieldPanel.SetSizer(vSizer)
            vSizer.Layout()

        # Add searchbox etc.
        self.searchSizer = wx.BoxSizer(wx.VERTICAL)
        searchBoxSizer = wx.BoxSizer(wx.HORIZONTAL)
        if sys.platform == 'darwin':
            searchBoxSizer.Add(self.searchField, 1, wx.CENTER | wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        else:
            searchBoxSizer.Add(self.searchFieldPanel, 1, wx.CENTER | wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        searchBoxSizer.Add(self.go, 0, wx.CENTER | wx.LEFT | wx.RESERVE_SPACE_EVEN_IF_HIDDEN, 5)  # add searchbutton
        searchBoxSizer.Add(self.ag, 0, wx.CENTER | wx.LEFT | wx.RESERVE_SPACE_EVEN_IF_HIDDEN, 5)  # add animation
        self.searchSizer.Add(searchBoxSizer, 1, wx.EXPAND)
        # finished searchSizer, add to mainSizer
        mainSizer.Add(self.searchSizer, 0, wx.EXPAND | wx.LEFT, 10)
        mainSizer.AddSpacer((40, 0))

        # add buttons
        buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
        buttonSizer.Add(self.download_btn, 0, wx.CENTER | wx.RIGHT, 5)
        buttonSizer.Add(self.upload_btn, 0, wx.CENTER | wx.RIGHT, 5)
        buttonSizer.Add(self.stop_btn, 0, wx.CENTER | wx.RIGHT, 5)
        buttonSizer.Add(self.delete_btn, 0, wx.CENTER | wx.RIGHT, 5)
        buttonSizer.Add(self.play_btn, 0, wx.CENTER | wx.RIGHT, 5)
        buttonSizer.AddSpacer((35, 0))
        buttonSizer.AddStretchSpacer()
        buttonSizer.Add(self.add_btn, 0, wx.CENTER | wx.RIGHT, 5)
        buttonSizer.Add(self.settings_btn, 0, wx.CENTER | wx.RIGHT, 5)
        mainSizer.Add(buttonSizer, 1, wx.EXPAND)

        self.SetSizer(mainSizer)
        self.Layout()

    def OnResize(self, event):
        self.Refresh()
        event.Skip()

    def OnSearchKeyDown(self, event=None):
        if self.go.IsEnabled():
            self._logger.debug("TopSearchPanel: OnSearchKeyDown")

            if getattr(self.searchField, 'ShowDropDown', False):
                self.searchField.ShowDropDown(False)

            self.guiutility.dosearch()

            self.go.Enable(False)
            wx.CallLater(2500, self.go.Enable, True)

    def OnSettings(self, event):
        self.guiutility.ShowPage('settings')

    def OnAdd(self, event):
        dlg = AddTorrent(None, self.guiutility.frame)
        dlg.CenterOnParent()
        dlg.ShowModal()
        dlg.Destroy()

    def OnStats(self, event):
        self.guiutility.ShowPage('stats')

    def StartSearch(self):
        if getattr(self.searchField, 'ShowDropDown', False):
            self.searchField.ShowDropDown(False)
            self.guiutility.frame.searchlist.ResetBottomWindow()

        self.Freeze()
        self.go.SetValue(0)
        self.guiutility.frame.top_bg.ag.Play()
        self.guiutility.frame.top_bg.ag.Show()
        self.Thaw()

    def ShowSearching(self, max):
        if not self or not self.go:
            return
        self.go.SetRange(max + 16)

        cancelWorker(u"FakeResult")
        startWorker(None, self.FakeResult, uId=u"FakeResult", delay=0.25, workerType="guiTaskQueue")

    @forceWxThread
    def FakeResult(self, times=1):
        newValue = min(self.go.GetValue() + 1, self.go.GetRange())
        if times < 16:
            self.go.SetValue(newValue)

            startWorker(None, self.FakeResult, wargs=(times + 1,), uId=u"FakeResult", delay=0.25,
                        workerType="guiTaskQueue")

    def NewResult(self):
        maxValue = self.go.GetRange()
        newValue = min(self.go.GetValue() + 1, maxValue)
        self.guiutility.frame.top_bg.go.SetValue(newValue)

        if newValue == maxValue:
            return True
        return False

    def SetFinished(self):
        self.Freeze()
        self.ag.Stop()
        self.ag.Hide()
        self.go.SetValue(self.go.GetRange())
        self.Layout()
        self.Thaw()

    def complete(self, term):
        ignore_list = ["http://", "https://", "magnet:"]
        for ignore in ignore_list:
            if term.startswith(ignore):
                return []

        """autocompletes term."""
        if len(term) > 1:
            return self.tdb.getAutoCompleteTerms(term, max_terms=7)
        return []

    def SearchFocus(self):
        if self.guiutility.guiPage == 'home':
            if getattr(self.GetParent(), 'home', False):
                self.GetParent().home.SearchFocus()
        else:
            self.searchField.SetFocus()
            self.searchField.SelectAll()

    def AddCollectedTorrent(self, coltorrent):
        self.collectedTorrents[coltorrent.infohash] = coltorrent
        self.TorrentsChanged()

    def GetSelectedTorrents(self):
        torrents = None

        page = self.guiutility.guiPage
        if page in ['search_results', 'selectedchannel', 'playlist', 'my_files']:
            list = self.guiutility.GetSelectedPage()
            items = list.GetExpandedItems()
            torrents = [item[1].original_data for item in items if isinstance(item[1].original_data, Torrent)
                        or isinstance(item[1].original_data, CollectedTorrent)]
        return torrents

    def TorrentsChanged(self):
        self.RefreshTorrents(self.GetSelectedTorrents())

    def RefreshTorrents(self, torrents):
        inDownloads = self.guiutility.guiPage == 'my_files'

        if torrents:
            isMultiple = len(torrents) > 1
            usedCollectedTorrents = set()
            # we have 7 different states, able to resume seeding, resume downloading,
            # download, stop seeding, stop downloading, delete, or play
            # TODO(emilon): This is so ugly. At least we should use a named tuple.
            states = [0, 0, 0, 0, 0, 0, 0]
            for torrent in torrents:
                if 'stopped' in torrent.state:
                    if 'completed' in torrent.state:
                        states[0] += 1
                    else:
                        states[1] += 1

                elif not torrent.state:
                    states[2] += 1

                if 'active' in torrent.state:
                    if 'completed' in torrent.state:
                        states[3] += 1
                    else:
                        states[4] += 1

                if torrent.state or inDownloads:
                    states[5] += 1

                if "metadata" not in torrent.state and torrent.infohash in self.collectedTorrents:
                    coltorrent = self.collectedTorrents[torrent.infohash]
                    if coltorrent.isPlayable():
                        states[6] += 1

                    usedCollectedTorrents.add(torrent.infohash)
                else:
                    # If the torrent isn't collected we assume its playable and let the core cancel the VOD if it isn't.
                    states[6] += 1

            enableDownload = states[1] + states[2]
            if enableDownload:
                if isMultiple:
                    self.SetButtonHandler(
                        self.download_btn,
                        self.OnDownload,
                        'Resume downloading %d torrent(s).' %
                        enableDownload)
                elif states[1]:
                    self.SetButtonHandler(self.download_btn, self.OnResume, 'Resume downloading this torrent.')
                else:
                    self.SetButtonHandler(self.download_btn, self.OnDownload, 'Start downloading this torrent.')
            else:
                self.SetButtonHandler(self.download_btn, None)

            enableUpload = states[0]
            if enableUpload:
                if isMultiple:
                    self.SetButtonHandler(
                        self.upload_btn,
                        self.OnUpload,
                        'Resume seeding %d torrent(s).' %
                        enableUpload)
                else:
                    self.SetButtonHandler(self.upload_btn, self.OnUpload, 'Resume seeding this torrent.')
            else:
                self.SetButtonHandler(self.upload_btn, None)

            enableStop = states[3] + states[4]
            if enableStop:
                if isMultiple:
                    self.SetButtonHandler(self.stop_btn, self.OnStop, 'Stop %d torrent(s).' % enableStop)
                elif states[3]:
                    self.SetButtonHandler(self.stop_btn, self.OnStop, 'Stop seeding this torrent.')
                else:
                    self.SetButtonHandler(self.stop_btn, self.OnStop, 'Stop downloading this torrent.')
            else:
                self.SetButtonHandler(self.stop_btn, None)

            if states[5] > 1:
                self.SetButtonHandler(self.delete_btn, self.OnDelete, 'Delete %d torrent(s).' % states[5])
            elif states[5]:
                self.SetButtonHandler(self.delete_btn, self.OnDelete, 'Delete this torrent.')
            else:
                self.SetButtonHandler(self.delete_btn, None)

            if isMultiple:
                self.SetButtonHandler(self.play_btn, self.OnPlay, 'Start playing one of the selected torrents.')
            elif states[6]:
                self.SetButtonHandler(self.play_btn, self.OnPlay, 'Start playing this torrent.')
            else:
                self.SetButtonHandler(self.play_btn, None)

            for infohash in self.collectedTorrents.keys():
                if infohash not in usedCollectedTorrents:
                    del self.collectedTorrents[infohash]
        else:
            self.ClearButtonHandlers()

    def SetButtonHandler(self, button, handler=None, tooltip=None):
        button.Enable(bool(handler))
        if handler:
            button.Bind(wx.EVT_LEFT_UP, handler)
            if tooltip:
                button.SetToolTipString(tooltip)
            else:
                button.SetToolTip(None)
        else:
            button.SetToolTip(None)

    def ClearButtonHandlers(self):
        self.SetButtonHandler(self.download_btn, None)
        self.SetButtonHandler(self.upload_btn, None)
        self.SetButtonHandler(self.play_btn, None)
        self.SetButtonHandler(self.stop_btn, None)
        self.SetButtonHandler(self.delete_btn, None)

    def OnDownload(self, event=None, torrents=None):
        refresh_library = False
        torrents = torrents if torrents is not None else self.GetSelectedTorrents()
        for torrent in torrents:
            if 'stopped' in torrent.state:
                self.guiutility.library_manager.resumeTorrent(torrent)
            else:
                if self.guiutility.frame.selectedchannellist.IsShownOnScreen():
                    self.guiutility.frame.selectedchannellist.StartDownload(torrent)
                else:
                    self.guiutility.torrentsearch_manager.downloadTorrent(torrent)

                refresh_library = True

        if event:
            button = event.GetEventObject()
            button.Enable(False)
            wx.CallLater(3000, button.Enable, True)

        if refresh_library:
            wx.CallLater(1000, self.guiutility.frame.librarylist.do_or_schedule_refresh, True)

    def OnUpload(self, event):
        for torrent in self.GetSelectedTorrents():
            if 'completed' in torrent.state:
                self.guiutility.library_manager.resumeTorrent(torrent)
        if event:
            button = event.GetEventObject()
            button.Enable(False)

    def OnPlay(self, event):
        # Select the first playable torrent or not collected torrent. Return if none can be found
        torrent = None
        for t in self.GetSelectedTorrents():
            if t.infohash in self.collectedTorrents:
                coltor = self.collectedTorrents[t.infohash]
                if coltor.isPlayable():
                    torrent = coltor
                    break
            else:
                torrent = t
                break

        if not torrent:
            return

        self.guiutility.library_manager.playTorrent(torrent.infohash)

        button = event.GetEventObject()
        button.Enable(False)

    def OnResume(self, event=None):
        for torrent in self.GetSelectedTorrents():
            self.guiutility.library_manager.resumeTorrent(torrent)
        if event:
            button = event.GetEventObject()
            button.Enable(False)

    def OnStop(self, event=None):
        for torrent in self.GetSelectedTorrents():
            self.guiutility.library_manager.stopTorrent(torrent.infohash)
        if event:
            button = event.GetEventObject()
            button.Enable(False)

    def OnDelete(self, event=None, silent=False, delete=False):
        torrents = self.GetSelectedTorrents()
        if not silent:
            dlg = RemoveTorrent(None, torrents)
            button_id = dlg.ShowModal()
        else:
            button_id = wx.ID_DELETE if delete else wx.ID_DEFAULT

        refresh_library = False
        if button_id in [wx.ID_DEFAULT, wx.ID_DELETE]:
            for torrent in torrents:
                self.guiutility.library_manager.deleteTorrent(torrent, button_id == wx.ID_DELETE)
                refresh_library = True

        if not silent:
            if dlg.newName:
                if dlg.newName.IsChanged():
                    dlg2 = wx.MessageDialog(None, 'Do you want to save your changes made to this torrent?',
                                            'Save changes?', wx.YES_NO | wx.YES_DEFAULT | wx.ICON_QUESTION)
                    if dlg2.ShowModal() == wx.ID_YES:
                        self.guiutility.channelsearch_manager.modifyTorrent(torrent.channel.id,
                                                                            torrent.channeltorrent_id,
                                                                            {'name': dlg.newName.GetValue()})
                    dlg2.Destroy()
            dlg.Destroy()

        if refresh_library:
            wx.CallLater(1000, self.guiutility.frame.librarylist.do_or_schedule_refresh, True)
