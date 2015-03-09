# Written by Jelle Roozenburg, Maarten ten Brinke, Arno Bakker, Lucian Musat
# Modified by Niels Zeilemaker
# see LICENSE.txt for license information

import wx
import os
import sys
import json
import logging
from time import time

from Tribler import LIBRARYNAME

from Tribler.Category.Category import Category
from Tribler.Core.CacheDB.sqlitecachedb import forceDBThread
from Tribler.Core.Utilities.search_utils import split_into_keywords

from Tribler.Core.Video.VideoPlayer import VideoPlayer

from Tribler.Main.Utility.GuiDBHandler import startWorker, GUI_PRI_DISPERSY
from Tribler.Main.Utility.GuiDBTuples import RemoteChannel

from Tribler.Main.vwxGUI import forceWxThread
from Tribler.Main.vwxGUI.SearchGridManager import TorrentManager, ChannelManager, LibraryManager
from Tribler.Main.vwxGUI.GuiImageManager import GuiImageManager
from Tribler.Main.vwxGUI.TorrentStateManager import TorrentStateManager
from threading import Lock


class GUIUtility(object):
    __single = None
    __single_lock = Lock()

    def __init__(self, utility=None, params=None, app=None):
        if GUIUtility.__single:
            raise RuntimeError("GUIUtility is singleton")
        GUIUtility.__single = self
        self.registered = False

        self._logger = logging.getLogger(self.__class__.__name__)

        # do other init
        self.utility = utility
        self.vwxGUI_path = os.path.join(self.utility.getPath(), LIBRARYNAME, 'Main', 'vwxGUI')
        self.utility.guiUtility = self
        self.params = params
        self.frame = None
        self.app = app

        # videoplayer
        self.videoplayer = None

        # current GUI page
        self.guiPage = 'home'
        # previous pages
        self.oldpage = []

        # firewall
        self.firewall_restart = False  # ie Tribler needs to restart for the port number to be updated

        # Recall improves by 20-25% by increasing the number of peers to query to 20 from 10 !
        self.max_remote_queries = 20  # max number of remote peers to query

        self.current_search_query = ''

        self.lists = []

        from Tribler.Main.vwxGUI.list_header import ListHeaderIcon

        self.listicon = ListHeaderIcon.getInstance()

    def getInstance(*args, **kw):
        if GUIUtility.__single is None:
            GUIUtility(*args, **kw)
        return GUIUtility.__single
    getInstance = staticmethod(getInstance)

    def hasInstance():
        return GUIUtility.__single is not None
    hasInstance = staticmethod(hasInstance)

    def delInstance():
        with GUIUtility.__single_lock:
            if GUIUtility.__single and GUIUtility.__single.registered:
                GUIUtility.__single.listicon.delInstance()
                GUIUtility.__single.library_manager.delInstance()
                GUIUtility.__single.channelsearch_manager.delInstance()
                GUIUtility.__single.torrentsearch_manager.delInstance()
                GUIUtility.__single.torrentstate_manager.delInstance()

            GUIUtility.__single = None
    delInstance = staticmethod(delInstance)

    def register(self):
        if not self.registered:
            self.registered = True

            self.torrentsearch_manager = TorrentManager.getInstance(self)
            self.channelsearch_manager = ChannelManager.getInstance()
            self.library_manager = LibraryManager.getInstance(self)
            self.torrentstate_manager = TorrentStateManager.getInstance(self.utility.session)

            self.torrentsearch_manager.connect(self.utility.session, self.library_manager, self.channelsearch_manager)
            self.channelsearch_manager.connect(self.utility.session, self.library_manager, self.torrentsearch_manager)
            self.library_manager.connect(self.utility.session, self.torrentsearch_manager, self.channelsearch_manager)
            self.torrentstate_manager.connect(self.torrentsearch_manager,
                                              self.library_manager,
                                              self.channelsearch_manager)

            self.videoplayer = VideoPlayer.getInstance()
        else:
            raise RuntimeError('GuiUtility is already registered')

    def ShowPlayer(self):
        if self.frame.videoparentpanel:
            self.ShowPage('videoplayer')

    @forceWxThread
    def ShowPage(self, page, *args):
        if page == 'settings':
            from Tribler.Main.vwxGUI.settingsDialog import SettingsDialog
            dialog = SettingsDialog()

            dialog.Centre()
            dialog.ShowModal()
            dialog.Destroy()

        elif page != self.guiPage:
            self.frame.actlist.selectTab(page)

            self.frame.top_bg.ClearButtonHandlers()

            self.oldpage.append(self.guiPage)
            if len(self.oldpage) > 3:
                self.oldpage.pop(0)

            self.frame.Freeze()

            if page not in ['search_results', 'my_files', 'selectedchannel', 'playlist', 'channels']:
                self.frame.splitter.Show(False)

            if page == 'search_results':
                # Show list
                self.SetTopSplitterWindow(self.frame.searchlist)
                items = self.frame.searchlist.GetExpandedItems()
                if items:
                    self.frame.searchlist.Select(items[0][0], force=True)
                else:
                    self.frame.searchlist.ResetBottomWindow()
            elif self.guiPage == 'search_results':
                # Hide list
                self.frame.searchlist.Show(False)

            if page == 'channels':
                self.SetTopSplitterWindow(self.frame.channellist)
                items = self.frame.channellist.GetExpandedItems()
                if items:
                    self.frame.channellist.Select(items[0][0], force=True)
                else:
                    self.frame.channellist.ResetBottomWindow()

            elif self.guiPage == 'channels':
                self.frame.channellist.Show(False)

            if page == 'mychannel':
                # Show list
                self.frame.managechannel.SetChannelId(self.channelsearch_manager.channelcast_db._channel_id)
                self.frame.managechannel.Show()

            elif self.guiPage == 'mychannel':
                self.frame.managechannel.Show(False)

            if page == 'managechannel':
                self.frame.managechannel.Show()

            elif self.guiPage == 'managechannel':
                self.frame.managechannel.Show(False)

            if page == 'selectedchannel':
                self.SetTopSplitterWindow(self.frame.selectedchannellist)
                items = self.frame.selectedchannellist.GetExpandedItems()
                if items:
                    self.frame.selectedchannellist.Select(items[0][0], force=True)
                else:
                    self.frame.selectedchannellist.ResetBottomWindow()
                channelmenu = self.frame.actlist.GetItem(3)
                if channelmenu and channelmenu.expandedPanel:
                    channelmenu.expandedPanel.AddCurrentChannelLink()

            elif self.guiPage == 'selectedchannel':
                self.frame.selectedchannellist.Show(False)
                if not self.frame.splitter.IsSplit():
                    sashpos = getattr(self.frame.splitter_top_window, 'sashpos', -185)
                    self.frame.splitter.SplitHorizontally(
                        self.frame.splitter_top_window,
                        self.frame.splitter_bottom_window,
                        sashpos)

            if page == 'playlist':
                self.SetTopSplitterWindow(self.frame.playlist)
                items = self.frame.playlist.GetExpandedItems()
                if items:
                    self.frame.playlist.Select(items[0][0])
                else:
                    self.frame.playlist.ResetBottomWindow()
                channelmenu = self.frame.actlist.GetItem(3)
                if channelmenu and channelmenu.expandedPanel:
                    channelmenu.expandedPanel.AddCurrentPlaylistLink()

            elif self.guiPage == 'playlist':
                self.frame.playlist.Show(False)

            if page == 'my_files':
                # Show list
                self.SetTopSplitterWindow(self.frame.librarylist)

                # Open infohash
                if args:
                    self.frame.librarylist.GetManager().refresh_or_expand(args[0])
                else:
                    items = self.frame.librarylist.GetExpandedItems()
                    if items:
                        self.frame.librarylist.Select(items[0][0], force=True)
                    else:
                        self.frame.librarylist.ResetBottomWindow()

            elif self.guiPage == 'my_files':
                # Hide list
                self.frame.librarylist.Show(False)

            if page == 'home':
                self.frame.home.ResetSearchBox()
                self.frame.home.Show()
            elif self.guiPage == 'home':
                self.frame.home.Show(False)

            if page == 'stats':
                self.frame.stats.Show()
            elif self.guiPage == 'stats':
                self.frame.stats.Show(False)

            if page == 'networkgraph':
                self.frame.networkgraph.Show()
            elif self.guiPage == 'networkgraph':
                self.frame.networkgraph.Show(False)

            if self.frame.videoparentpanel:
                if page == 'videoplayer':
                    self.frame.videoparentpanel.Show(True)
                elif self.guiPage == 'videoplayer':
                    self.frame.videoparentpanel.Show(False)

            self.guiPage = page
            self.frame.Layout()
            self.frame.Thaw()

        # Set focus to page
        if page == 'search_results':
            self.frame.searchlist.Focus()

            if args:
                self.frame.searchlist.total_results = None
                self.frame.searchlist.SetKeywords(args[0])

        elif page == 'channels':
            self.frame.channellist.Focus()
        elif page == 'selectedchannel':
            self.frame.selectedchannellist.Focus()
        elif page == 'my_files':
            self.frame.librarylist.Focus()

    def GetSelectedPage(self):
        if self.guiPage == 'home':
            return self.frame.home

        if self.guiPage == 'search_results':
            return self.frame.searchlist

        if self.guiPage == 'channels':
            return self.frame.channellist

        if self.guiPage == 'selectedchannel':
            return self.frame.selectedchannellist

        if self.guiPage == 'mychannel':
            return self.frame.managechannel

        if self.guiPage == 'managechannel':
            return self.frame.managechannel

        if self.guiPage == 'playlist':
            return self.frame.playlist

        if self.guiPage == 'my_files':
            return self.frame.librarylist

    def SetTopSplitterWindow(self, window=None, show=True):
        while self.frame.splitter_top.GetChildren():
            self.frame.splitter_top.Detach(0)

        if window:
            self.frame.splitter_top.Add(window, 1, wx.EXPAND)
            window.Show(show)
        self.frame.splitter.Show(show)
        self.frame.splitter_top.Layout()
        self.frame.splitter_top_window.Refresh()

    def SetBottomSplitterWindow(self, panel_type):
        self.frame.splitter_bottom_window.Freeze()

        from Tribler.Main.vwxGUI.list_details import TorrentDetails, ChannelInfoPanel, LibraryDetails, ChannelDetails, PlaylistDetails, SearchInfoPanel, LibraryInfoPanel, SelectedchannelInfoPanel, PlaylistInfoPanel

        type_to_panel = {TorrentDetails.__name__: self.frame.torrentdetailspanel,
                         LibraryDetails.__name__: self.frame.librarydetailspanel,
                         ChannelDetails.__name__: self.frame.channeldetailspanel,
                         PlaylistDetails.__name__: self.frame.playlistdetailspanel,
                         SearchInfoPanel.__name__: self.frame.searchinfopanel,
                         ChannelInfoPanel.__name__: self.frame.channelinfopanel,
                         LibraryInfoPanel.__name__: self.frame.libraryinfopanel,
                         PlaylistInfoPanel.__name__: self.frame.playlistinfopanel,
                         SelectedchannelInfoPanel.__name__: self.frame.selectedchannelinfopanel}

        result = None
        for pt, pl in type_to_panel.iteritems():
            pl.Show(pt == panel_type.__name__)
            if pt == panel_type.__name__:
                result = pl
        if self.guiPage not in ['mychannel', 'home']:
            self.frame.splitter.Show(True)
        self.frame.splitter_bottom.Layout()
        self.frame.splitter_bottom_window.Thaw()
        self.frame.splitter_bottom_window.Refresh()
        return result

    def SetColumnInfo(self, itemtype, columns, hide_defaults=[]):
        # Load hidden column info
        hide_columns = self.ReadGuiSetting("hide_columns", default={})
        hide_columns = hide_columns.get(itemtype.__name__, {})
        for index, column in enumerate(columns):
            if column['name'] in hide_columns:
                column['show'] = hide_columns[column['name']]
            else:
                column['show'] = not (index in hide_defaults)

        # Load column width info
        column_sizes = self.ReadGuiSetting("column_sizes", default={})
        column_sizes = column_sizes.get(itemtype.__name__, {})
        for index, column in enumerate(columns):
            if column['name'] in column_sizes:
                column['width'] = column_sizes[column['name']]

        return columns

    def ReadGuiSetting(self, setting_name, default=None, do_json=True):
        setting_value = self.utility.read_config(setting_name, literal_eval=False)
        if do_json and setting_value:
            setting_value = json.loads(setting_value)
        elif not setting_value:
            setting_value = default
        return setting_value

    def WriteGuiSetting(self, setting_name, setting_value, do_json=True):
        self.utility.write_config(setting_name, json.dumps(setting_value) if do_json else setting_value)
        self.utility.flush_config()

    @forceWxThread
    def GoBack(self, scrollTo=None, topage=None):
        if topage:
            self.oldpage.pop()
        else:
            if len(self.oldpage) > 0:
                topage = self.oldpage.pop()
            else:
                return

        if topage == 'search_results':
            self.frame.actlist.selectTab('results')
        elif topage in ['channels', 'selectedchannel', 'mychannel']:
            self.frame.actlist.selectTab('channels')
        else:
            self.frame.actlist.selectTab(topage)

        self.ShowPage(topage)
        self.oldpage.pop()  # remove curpage from history

        if scrollTo:
            self.ScrollTo(scrollTo)

    def dosearch(self, input=None):
        if input is None:
            sf = self.frame.top_bg.searchField
            if sf is None:
                return

            input = sf.GetValue()

        if input:
            input = input.strip()
            if input == '':
                return
        else:
            return
        self.frame.top_bg.searchField.SetValue(input)

        if input.startswith("http://") or input.startswith("https://"):
            if self.frame.startDownloadFromUrl(str(input)):
                self.frame.top_bg.searchField.Clear()
                self.ShowPage('my_files')

        elif input.startswith("magnet:"):
            if self.frame.startDownloadFromMagnet(str(input)):
                self.frame.top_bg.searchField.Clear()
                self.ShowPage('my_files')

        else:
            keywords = split_into_keywords(input)
            keywords = [keyword for keyword in keywords if len(keyword) > 1]

            if len(keywords) == 0:
                self.Notify('Please enter a search term',
                            "Your search term '%s' was either to small or to general." % input,
                            icon=wx.ART_INFORMATION)

            else:
                self.frame.top_bg.StartSearch()
                self.current_search_query = keywords
                self._logger.debug("GUIUtil: searchFiles: %s %s", keywords, time())

                self.frame.searchlist.Freeze()

                self.torrentsearch_manager.setSearchKeywords(keywords)
                self.channelsearch_manager.setSearchKeywords(keywords)

                # We set oldkeywords to '', which will trigger a reset in SetKeywords (called from ShowPage).
                # This avoids calling reset twice.
                # Niels: 17-09-2012, unfortunately showpage calls show(true)
                # which results in the dirty items being refreshed.
                # We need to call Reset in order to prevent this from happening
                self.frame.searchlist.Reset()
                self.ShowPage('search_results', keywords)

                # We now have to call thaw, otherwise loading message will not be shown.
                self.frame.searchlist.Thaw()

                # Peform local search
                self.torrentsearch_manager.set_gridmgr(self.frame.searchlist.GetManager())
                self.channelsearch_manager.set_gridmgr(self.frame.searchlist.GetManager())

                def db_thread():
                    self.torrentsearch_manager.refreshGrid()

                    nr_peers_connected = self.torrentsearch_manager.searchDispersy()
                    self.channelsearch_manager.searchDispersy()
                    return nr_peers_connected

                def wx_thread(delayedResult):
                    nr_peers_connected = delayedResult.get()

                    self.frame.searchlist.SetMaxResults(nr_peers_connected + 1, keywords)
                    self.frame.searchlist.NewResult()

                startWorker(wx_thread, db_thread, priority=1024)

    @forceWxThread
    def NewResult(self):
        self.frame.searchlist.NewResult()

    @forceWxThread
    def showChannelCategory(self, category, show=True):

        manager = self.frame.channellist.GetManager()
        manager.SetCategory(category, True)

        if show:
            self.ShowPage('channels')

    @forceWxThread
    def showLibrary(self, show=True):
        manager = self.frame.librarylist.GetManager()
        manager.do_or_schedule_refresh(True)

        if show:
            self.ShowPage('my_files')

    def showChannelFromId(self, channel_id):
        def db_callback():
            channel = self.channelsearch_manager.getChannel(channel_id)
            self.showChannel(channel)

        startWorker(None, db_callback, priority=GUI_PRI_DISPERSY)

    def showChannelFromPermid(self, channel_permid):
        def db_callback():
            channel = self.channelsearch_manager.getChannelByPermid(channel_permid)
            self.showChannel(channel)

        startWorker(None, db_callback, priority=GUI_PRI_DISPERSY)

    @forceWxThread
    def showChannel(self, channel):
        if channel:
            manager = self.frame.selectedchannellist.GetManager()
            manager.refresh_if_required(channel)

            self.ShowPage('selectedchannel')

            if isinstance(channel, RemoteChannel):
                self.showChannelFromPermid(channel.permid)

    def showChannels(self):
        self.frame.actlist.selectTab('channels')
        self.ShowPage('channels')

    @forceWxThread
    def showChannelResults(self, data_channel):
        self.frame.actlist.selectTab('channels')

        def subscribe_latestupdate_sort(a, b):
            val = cmp(a.modified, b.modified)
            if val == 0:
                return cmp(a.name, b.name)
            return val

        data = data_channel.values()
        data.sort(subscribe_latestupdate_sort, reverse=True)

        manager = self.frame.channellist.GetManager()
        manager.SetCategory('searchresults')
        manager.refresh(data)

        self.ShowPage('channels')

    @forceWxThread
    def showManageChannel(self, channel):
        self.frame.managechannel.SetChannel(channel)
        self.ShowPage('managechannel')

    @forceWxThread
    def showPlaylist(self, data):
        self.frame.playlist.Set(data)
        self.ShowPage('playlist')

    def OnList(self, goto_end, event=None):
        lists = {
            'channels': self.frame.channellist,
            'selectedchannel': self.frame.selectedchannellist,
            'mychannel': self.frame.managechannel,
            'search_results': self.frame.searchlist,
            'my_files': self.frame.librarylist}
        if self.guiPage in lists and lists[self.guiPage].HasFocus():
            lists[self.guiPage].ScrollToEnd(goto_end)
        elif event:
            event.Skip()

    def ScrollTo(self, id):
        lists = {
            'channels': self.frame.channellist,
            'selectedchannel': self.frame.selectedchannellist,
            'mychannel': self.frame.managechannel,
            'search_results': self.frame.searchlist,
            'my_files': self.frame.librarylist}
        if self.guiPage in lists:
            lists[self.guiPage].ScrollToId(id)

    @forceWxThread
    def Notify(self, title, msg='', icon=wx.ART_INFORMATION):
        if sys.platform == 'win32' and not self.frame.IsShownOnScreen():
            self.frame.tbicon.Notify(title, msg, icon)
        else:
            if isinstance(icon, basestring):
                icon = wx.ArtProvider.GetBitmap(icon, wx.ART_FRAME_ICON) or \
                    GuiImageManager.getInstance().getImage(u"notify_%s.png" % icon)
            self.frame.actlist.Notify(msg or title, icon)

    def ShouldGuiUpdate(self):
        # Avoid WxPyDeadObject exception
        if self.frame and self.frame.ready:
            return self.frame.GUIupdate
        return True

    def addList(self, l):
        if l not in self.lists:
            self.lists.append(l)

    def toggleFamilyFilter(self, newState=None, setCheck=False):
        if newState is None:
            newState = not self.getFamilyFilter()

        Category.getInstance().set_family_filter(newState)
        for l in self.lists:
            if getattr(l, 'GotFilter', False):
                l.GotFilter(None)

        if setCheck:
            self.frame.SRstatusbar.ff_checkbox.SetValue(newState)

        self.frame.home.aw_panel.refreshNow()

        if newState:
            self.utility.write_config('family_filter', 1)
        else:
            self.utility.write_config('family_filter', 0)
        self.utility.flush_config()

    def getFamilyFilter(self):
        catobj = Category.getInstance()
        return catobj.family_filter_enabled()

    def set_firewall_restart(self, b):
        self.firewall_restart = b

    @forceWxThread
    def MarkAsFavorite(self, event, channel):
        if channel:
            if event:
                button = event.GetEventObject()
                button.Enable(False)
                if hasattr(button, 'selected'):
                    button.selected = False

            dlgname = 'MFdialog'
            if not self.ReadGuiSetting('show_%s' % dlgname, default=True):
                response = wx.ID_OK
            else:
                from Tribler.Main.Dialogs.ConfirmationDialog import ConfirmationDialog
                dlg = ConfirmationDialog(
                    None, dlgname, "You are about to add \'%s\' to your list of favourite channels." % channel.name,
                    "If you mark this channel as your favourite, you will be able to access its full content.")
                response = dlg.ShowModal()

            if response == wx.ID_OK:
                @forceDBThread
                def add_vote():
                    self.channelsearch_manager.favorite(channel.id)
                    wx.CallAfter(self.Notify, "Channel marked as favourite", "Marked channel '%s' as favourite" %
                                 channel.name, icon='favourite')
                    if event:
                        button.Enable(True)
                    self.RefreshChannel(channel.id)
                add_vote()
            elif event:
                button.Enable(True)

    @forceWxThread
    def RemoveFavorite(self, event, channel):
        if channel:
            if event:
                button = event.GetEventObject()
                button.Enable(False)
                if hasattr(button, 'selected'):
                    button.selected = False

            dlgname = 'RFdialog'
            if not self.ReadGuiSetting('show_%s' % dlgname, default=True):
                response = wx.ID_OK
            else:
                from Tribler.Main.Dialogs.ConfirmationDialog import ConfirmationDialog
                dlg = ConfirmationDialog(
                    None, dlgname,
                    "You are about to remove \'%s\' from your list of favourite channels." % channel.name,
                    "If you remove this channel from your favourites, "
                    "you will no longer be able to access its full content.")
                response = dlg.ShowModal()

            if response == wx.ID_OK:
                @forceDBThread
                def remove_vote():
                    self.channelsearch_manager.remove_vote(channel.id)
                    wx.CallAfter(self.Notify, "Channel removed from favourites",
                                 "Removed channel '%s' from your favourites" % channel.name,
                                 icon='favourite')
                    if event:
                        button.Enable(True)
                    self.RefreshChannel(channel.id)
                remove_vote()
            elif event:
                button.Enable(True)

    @forceWxThread
    def MarkAsSpam(self, event, channel):
        if channel:
            if event:
                button = event.GetEventObject()
                button.Enable(False)
                if hasattr(button, 'selected'):
                    button.selected = False

            dlgname = 'MSdialog'
            if not self.ReadGuiSetting('show_%s' % dlgname, default=True):
                response = wx.ID_OK
            else:
                from Tribler.Main.Dialogs.ConfirmationDialog import ConfirmationDialog
                dlg = ConfirmationDialog(None, dlgname,
                                         "You are about to report channel \'%s\' as spam." % channel.name, "")
                response = dlg.ShowModal()

            if response == wx.ID_OK:
                @forceDBThread
                def remove_vote():
                    self.channelsearch_manager.spam(channel.id)
                    wx.CallAfter(self.Notify, "Channel marked as spam", "Channel '%s' marked as spam" % channel.name)
                    if event:
                        button.Enable(True)
                    self.RefreshChannel(channel.id)
                remove_vote()
            elif event:
                button.Enable(True)

    @forceWxThread
    def RemoveSpam(self, event, channel):
        if channel:
            if event:
                button = event.GetEventObject()
                button.Enable(False)
                if hasattr(button, 'selected'):
                    button.selected = False

            dlgname = 'RSdialog'
            if not self.ReadGuiSetting('show_%s' % dlgname, default=True):
                response = wx.ID_OK
            else:
                from Tribler.Main.Dialogs.ConfirmationDialog import ConfirmationDialog
                dlg = ConfirmationDialog(None, dlgname,
                                         "You are about unmark channel \'%s\' as spam." % channel.name, "")
                response = dlg.ShowModal()

            if response == wx.ID_OK:
                @forceDBThread
                def remove_vote():
                    self.channelsearch_manager.remove_vote(channel.id)
                    wx.CallAfter(self.Notify,
                                 "Channel unmarked as spam", "Channel '%s' unmarked as spam" % channel.name)
                    if event:
                        button.Enable(True)
                    self.RefreshChannel(channel.id)
                remove_vote()
            elif event:
                button.Enable(True)

    def RefreshChannel(self, channelid):
        if self.guiPage in ['search_results', 'selectedchannel', 'channels']:

            list = self.GetSelectedPage()
            if self.guiPage == 'search_results':
                list.GetManager().refresh_partial(channelids=[channelid])
            else:
                list.GetManager().refresh_partial((channelid,))

            if self.guiPage == 'selectedchannel':
                wx.CallAfter(list.GetManager().reload, channelid)

    def SelectVideo(self, videofiles, selected_file=None):
        if len(videofiles) > 1:
            videofiles.sort()
            dialog = wx.SingleChoiceDialog(
                None,
                'Tribler currently only supports playing one file at a time.\nSelect the file you want to play.',
                'Which file do you want to play?',
                videofiles)
            if selected_file in videofiles:
                dialog.SetSelection(videofiles.index(selected_file))

            selected_file = dialog.GetStringSelection() if dialog.ShowModal() == wx.ID_OK else None
            dialog.Destroy()
            return selected_file
        elif len(videofiles) == 1:
            return videofiles[0]
