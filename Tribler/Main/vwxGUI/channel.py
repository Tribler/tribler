# Written by Niels Zeilemaker
import wx

import os
import sys
from time import time
import pickle
from random import sample
from traceback import print_exc
import re
from binascii import hexlify

from Tribler.Main.vwxGUI.GuiUtility import GUIUtility, forceWxThread
from Tribler.Main.vwxGUI.widgets import _set_font, NotebookPanel, SimpleNotebook, EditText, BetterText

from Tribler.Category.Category import Category
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.CacheDB.sqlitecachedb import forceDBThread

from Tribler.Main.vwxGUI import (CHANNEL_MAX_NON_FAVORITE, warnWxThread, LIST_GREY, LIST_LIGHTBLUE, LIST_DESELECTED,
                                 DEFAULT_BACKGROUND, format_time, showError)
from Tribler.Main.vwxGUI.list import BaseManager, GenericSearchList, SizeList, List
from Tribler.Main.vwxGUI.list_body import ListBody
from Tribler.Main.vwxGUI.list_footer import (CommentFooter, PlaylistFooter, ManageChannelFilesFooter,
                                             ManageChannelPlaylistFooter)
from Tribler.Main.vwxGUI.list_header import (ChannelHeader, SelectedChannelFilter, SelectedPlaylistFilter,
                                             PlaylistHeader, ManageChannelHeader, TitleHeader)
from Tribler.Main.vwxGUI.list_item import (PlaylistItem, ColumnsManager, DragItem, TorrentListItem, CommentItem,
                                           CommentActivityItem, NewTorrentActivityItem, TorrentActivityItem,
                                           ModificationActivityItem, ModerationActivityItem, MarkingActivityItem,
                                           ModificationItem, ModerationItem, ThumbnailListItem)
from Tribler.Main.vwxGUI.list_details import (AbstractDetails, SelectedchannelInfoPanel, PlaylistDetails,
                                              PlaylistInfoPanel, TorrentDetails, MyChannelPlaylist)

from Tribler.Main.Utility.GuiDBHandler import startWorker, cancelWorker, GUI_PRI_DISPERSY
from Tribler.community.channel.community import ChannelCommunity
from Tribler.Main.Utility.GuiDBTuples import Torrent, CollectedTorrent, ChannelTorrent

from Tribler.Main.Dialogs.AddTorrent import AddTorrent


class ChannelManager(BaseManager):

    def __init__(self, list):
        super(ChannelManager, self).__init__(list)

        self.channelsearch_manager = self.guiutility.channelsearch_manager
        self.library_manager = self.guiutility.library_manager

        self.Reset()

    def Reset(self):
        super(ChannelManager, self).Reset()
        if self.list.channel:
            cancelWorker("ChannelManager_refresh_list_%d" % self.list.channel.id)

        self.list.SetChannel(None)

    def refreshDirty(self):
        if 'COMPLETE_REFRESH_STATE' in self.dirtyset:
            self._refresh_list(stateChanged=True)
            self.dirtyset.clear()
        else:
            BaseManager.refreshDirty(self)

    @forceDBThread
    def reload(self, channel_id):
        channel = self.channelsearch_manager.getChannel(channel_id)
        self.refresh(channel)

    @forceWxThread
    def refresh(self, channel=None):
        if channel:
            # copy torrents if channel stays the same
            if channel == self.list.channel:
                if self.list.channel.torrents:
                    if channel.torrents:
                        channel.torrents.update(self.list.channel.torrents)
                    else:
                        channel.torrents = self.list.channel.torrents

            self.list.Reset()
            self.list.SetChannel(channel)

        self._refresh_list(channel)

    def refresh_if_required(self, channel):
        if self.list.channel != channel:
            self.refresh(channel)

    def _refresh_list(self, stateChanged=False):
        t1 = time()
        self._logger.debug("SelChannelManager complete refresh %s", t1)

        self.list.dirty = False

        def db_callback():
            channel = self.list.channel
            if channel:
                t2 = time()

                state = iamModerator = None
                if stateChanged:
                    result = channel.refreshState()
                    if result:
                        state, iamModerator = channel.refreshState()

                if self.list.channel.isDispersy():
                    nr_playlists, playlists = self.channelsearch_manager.getPlaylistsFromChannel(channel)
                    total_items, nrfiltered, torrentList = self.channelsearch_manager.getTorrentsNotInPlaylist(
                        channel, self.guiutility.getFamilyFilter())
                else:
                    playlists = []
                    total_items, nrfiltered, torrentList = self.channelsearch_manager.getTorrentsFromChannel(
                        channel, self.guiutility.getFamilyFilter())

                t3 = time()
                self._logger.debug("SelChannelManager complete refresh took %s %s %s", t3 - t1, t2 - t1, t3)

                return total_items, nrfiltered, torrentList, playlists, state, iamModerator

        def do_gui(delayedResult):
            result = delayedResult.get()
            if result:
                total_items, nrfiltered, torrentList, playlists, state, iamModerator = result
                if state is not None:
                    self.list.SetChannelState(state, iamModerator)

                self._on_data(total_items, nrfiltered, torrentList, playlists)

        if self.list.channel:
            startWorker(
                do_gui,
                db_callback,
                uId=u"ChannelManager_refresh_list_%d" %
                self.list.channel.id,
                retryOnBusy=True,
                priority=GUI_PRI_DISPERSY)

    @forceWxThread
    def _on_data(self, total_items, nrfiltered, torrents, playlists):
        # only show a small random selection of available content for non-favorite channels
        inpreview = not self.list.channel.isFavorite() and not self.list.channel.isMyChannel()
        if inpreview:
            if len(playlists) > 3:
                playlists = sample(playlists, 3)

            if len(torrents) > CHANNEL_MAX_NON_FAVORITE:
                def cmp_torrent(a, b):
                    return cmp(a.time_stamp, b.time_stamp)

                torrents = sample(torrents, CHANNEL_MAX_NON_FAVORITE)
                torrents.sort(cmp=cmp_torrent, reverse=True)

        # sometimes a channel has some torrents in the torrents variable, merge them here
        if self.list.channel.torrents:
            remoteTorrents = set(torrent.infohash for torrent in self.list.channel.torrents)
            for i in xrange(len(torrents), 0, -1):
                if torrents[i - 1].infohash in remoteTorrents:
                    torrents.pop(i - 1)

            torrents = list(self.list.channel.torrents) + torrents
            if inpreview:
                torrents = torrents[:CHANNEL_MAX_NON_FAVORITE]

        self.list.SetData(playlists, torrents)
        self._logger.debug("SelChannelManager complete refresh done")

    @forceDBThread
    def refresh_partial(self, ids):
        if self.list.channel:
            id_data = {}
            for id in ids:
                if isinstance(id, str) and len(id) == 20:
                    id_data[id] = self.channelsearch_manager.getTorrentFromChannel(self.list.channel, id)
                else:
                    id_data[id] = self.channelsearch_manager.getPlaylist(self.list.channel, id)

            def do_gui():
                for id, data in id_data.iteritems():
                    if data:
                        self.list.RefreshData(id, data)
                    else:
                        self.list.RemoveItem(id)

            wx.CallAfter(do_gui)

    @forceWxThread
    def downloadStarted(self, infohash):
        if self.list.InList(infohash):
            item = self.list.GetItem(infohash)

            torrent_details = item.GetExpandedPanel()
            if torrent_details:
                torrent_details.DownloadStarted()
            else:
                item.DoExpand()

    def torrentUpdated(self, infohash):
        if self.list.InList(infohash):
            self.do_or_schedule_partial([infohash])

    def torrentsUpdated(self, infohashes):
        infohashes = [infohash for infohash in infohashes if self.list.InList(infohash)]
        self.do_or_schedule_partial(infohashes)

    def channelUpdated(self, channel_id, stateChanged=False, modified=False):
        _channel = self.list.channel
        if _channel and _channel == channel_id:
            if _channel.isFavorite() or _channel.isMyChannel():
                # only update favorite or mychannel
                if modified:
                    self.reload(channel_id)
                else:
                    if self.list.ShouldGuiUpdate():
                        self._refresh_list(stateChanged)
                    else:
                        key = 'COMPLETE_REFRESH'
                        if stateChanged:
                            key += '_STATE'
                        self.dirtyset.add(key)
                        self.list.dirty = True

    def playlistCreated(self, channel_id):
        if self.list.channel == channel_id:
            self.do_or_schedule_refresh()

    def playlistUpdated(self, playlist_id, infohash=False, modified=False):
        if self.list.InList(playlist_id):
            if self.list.InList(infohash):  # if infohash is shown, complete refresh is necessary
                self.do_or_schedule_refresh()

            else:  # else, only update this single playlist
                self.do_or_schedule_partial([playlist_id])


class SelectedChannelList(GenericSearchList):

    def __init__(self, parent):
        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility
        self.session = self.guiutility.utility.session
        self.channelsearch_manager = self.guiutility.channelsearch_manager

        self.display_grid = False
        self.title = None
        self.channel = None
        self.iamModerator = False
        self.my_channel = False
        self.state = ChannelCommunity.CHANNEL_CLOSED

        columns = [{'name': 'Name', 'sortAsc': True},
                   {'name': 'Torrents', 'width': '14em', 'fmt': lambda x: '?' if x == -1 else str(x)}]

        columns = self.guiutility.SetColumnInfo(PlaylistItem, columns)
        ColumnsManager.getInstance().setColumns(PlaylistItem, columns)

        self.category_names = {}
        for key, name in Category.getInstance().getCategoryNames(filter=False):
            self.category_names[key] = name
        self.category_names[None] = 'Unknown'

        GenericSearchList.__init__(self, None, wx.WHITE, [0, 0], True, borders=False, showChange=True, parent=parent)

        self.list.OnBack = self.OnBack
        self.list.Bind(wx.EVT_SHOW, lambda evt: self.notebook.SetSelection(0))

    @warnWxThread
    def _PostInit(self):
        self.notebook = SimpleNotebook(self.parent, show_single_tab=False, style=wx.NB_NOPAGETHEME)
        self.notebook.SetForegroundColour(self.parent.GetForegroundColour())
        self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.OnChange)

        contentList = wx.Panel(self.notebook)
        contentList.SetForegroundColour(self.notebook.GetForegroundColour())
        contentList.SetFocus = contentList.SetFocusIgnoringChildren

        self.header = self.CreateHeader(contentList)
        self.list = self.CreateList(contentList)

        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.Add(self.header, 0, wx.EXPAND)
        vSizer.Add(self.list, 1, wx.EXPAND)
        contentList.SetSizer(vSizer)

        self.notebook.AddPage(contentList, "Contents", tab_colour=wx.WHITE)

        self.commentList = NotebookPanel(self.notebook)
        self.commentList.SetList(CommentList(self.commentList, self, canReply=True))
        self.commentList.header.SetBackgroundColour(wx.WHITE)
        self.commentList.Show(False)

        self.activityList = NotebookPanel(self.notebook)
        self.activityList.SetList(ActivityList(self.activityList, self))
        self.activityList.header.SetBackgroundColour(wx.WHITE)
        self.activityList.Show(False)

        self.moderationList = NotebookPanel(self.notebook)
        self.moderationList.SetList(ModerationList(self.moderationList, self))
        self.moderationList.header.SetBackgroundColour(wx.WHITE)
        self.moderationList.Show(False)

        self.leftLine = wx.Panel(self.parent, size=(1, -1))
        self.rightLine = wx.Panel(self.parent, size=(1, -1))

        listSizer = wx.BoxSizer(wx.HORIZONTAL)
        listSizer.Add(self.leftLine, 0, wx.EXPAND)
        listSizer.Add(self.notebook, 1, wx.EXPAND)
        listSizer.Add(self.rightLine, 0, wx.EXPAND)

        self.top_header = self.CreateTopHeader(self.parent)
        self.Add(self.top_header, 0, wx.EXPAND)
        self.Add(listSizer, 1, wx.EXPAND)

        self.SetBackgroundColour(self.background)

        self.Layout()
        self.list.Bind(wx.EVT_SIZE, self.OnSize)

    def _special_icon(self, item):
        if not isinstance(item, PlaylistItem) and self.channel:
            if self.channel.isFavorite():
                return self.favorite, self.normal, "This torrent is part of one of your favorite channels, %s" % self.channel.name
            else:
                return self.normal, self.favorite, "This torrent is not part of one of your favorite channels"

    def CreateList(self, parent=None, listRateLimit=1):
        if not parent:
            parent = self
        return ListBody(parent, self, self.columns, self.spacers[0], self.spacers[1], self.singleSelect, self.showChange, listRateLimit=listRateLimit, grid_columns=4 if self.display_grid else 0)

    @warnWxThread
    def CreateHeader(self, parent):
        return SelectedChannelFilter(parent, self)

    @warnWxThread
    def CreateTopHeader(self, parent):
        return ChannelHeader(parent, self)

    @warnWxThread
    def Reset(self):
        self.title = None
        self.channel = None
        self.iamModerator = False
        self.my_channel = False

        if GenericSearchList.Reset(self):
            self.commentList.Reset()
            self.activityList.Reset()
            self.moderationList.Reset()

            return True
        return False

    def SetGrid(self, enable):
        self.display_grid = enable

        new_raw_data = []
        for data in (self.list.raw_data or []):
            if enable and (len(data) < 4 or data[3] == TorrentListItem):
                new_raw_data.append(list(data[:3]) + [ThumbnailListItem])
            elif not enable and data[3] == ThumbnailListItem:
                new_raw_data.append(list(data[:3]) + [TorrentListItem])
        self.list.SetData(new_raw_data)
        self.list.SetGrid(self.display_grid)

    @warnWxThread
    def SetChannel(self, channel):
        self.channel = channel

        self.Freeze()
        self.SetIds(channel)

        if channel:
            self.SetTitle(channel)

        self.Thaw()

    def SetIds(self, channel):
        if channel:
            self.my_channel = channel.isMyChannel()
        else:
            self.my_channel = False

        # Always switch to page 1 after new id
        if self.notebook.GetPageCount() > 0:
            self.notebook.SetSelection(0)

    @warnWxThread
    def SetChannelState(self, state, iamModerator):
        self.iamModerator = iamModerator
        self.state = state
        self.channel.setState(state, iamModerator)

        if state >= ChannelCommunity.CHANNEL_SEMI_OPEN:
            if self.notebook.GetPageCount() == 1:
                self.commentList.Show(True)
                self.activityList.Show(True)

                self.notebook.AddPage(self.commentList, "Comments", tab_colour=wx.WHITE)
                self.notebook.AddPage(self.activityList, "Activity", tab_colour=wx.WHITE)

            if state >= ChannelCommunity.CHANNEL_OPEN and self.notebook.GetPageCount() == 3:
                self.moderationList.Show(True)
                self.notebook.AddPage(self.moderationList, "Moderations", tab_colour=wx.WHITE)
        else:
            for i in range(self.notebook.GetPageCount(), 1, -1):
                page = self.notebook.GetPage(i - 1)
                page.Show(False)
                self.notebook.RemovePage(i - 1)

        # Update header + list ids
        self.ResetBottomWindow()
        self.top_header.SetButtons(self.channel)
        self.commentList.GetManager().SetIds(channel=self.channel)
        self.activityList.GetManager().SetIds(channel=self.channel)
        self.moderationList.GetManager().SetIds(channel=self.channel)

    @warnWxThread
    def SetTitle(self, channel):
        self.title = channel.name
        self.top_header.SetTitle(channel)
        self.Layout()

    def GetManager(self):
        if getattr(self, 'manager', None) is None:
            self.manager = ChannelManager(self)
        return self.manager

    @forceWxThread
    def SetData(self, playlists, torrents):
        SizeList.SetData(self, torrents)

        if len(playlists) > 0 or len(torrents) > 0:
            data = [(playlist.id, [playlist.name, playlist.nr_torrents, 0, 0, 0, 0], playlist, PlaylistItem, index)
                    for index, playlist in enumerate(playlists)]

            shouldDrag = len(playlists) > 0 and (self.channel.iamModerator or self.channel.isOpen())
            if shouldDrag:
                data += [(torrent.infohash, [torrent.name, torrent.length, self.category_names[torrent.category],
                                             torrent.num_seeders, torrent.num_leechers, 0, None],
                          torrent, DragItem) for torrent in torrents]
            elif self.display_grid:
                data += [(torrent.infohash, [torrent.name, torrent.length, self.category_names[torrent.category],
                                             torrent.num_seeders, torrent.num_leechers, 0, None],
                          torrent, ThumbnailListItem) for torrent in torrents]
            else:
                data += [(torrent.infohash, [torrent.name, torrent.length, self.category_names[torrent.category],
                                             torrent.num_seeders, torrent.num_leechers, 0, None],
                          torrent, TorrentListItem) for torrent in torrents]
            self.list.SetData(data)

        else:
            header = 'No torrents or playlists found.'

            if self.channel and self.channel.isOpen():
                message = 'As this is an "open" channel, '\
                          'you can add your own torrents to share them with others in this channel'
                self.list.ShowMessage(message, header=header)
            else:
                self.list.ShowMessage(header)
            self.SetNrResults(0)

    @warnWxThread
    def SetNrResults(self, nr):
        SizeList.SetNrResults(self, nr)
        if self.channel and (self.channel.isFavorite() or self.channel.isMyChannel()):
            header = 'Discovered'
        else:
            header = 'Previewing'

        if nr == 1:
            self.header.SetSubTitle(header + ' %d torrent' % nr)
        else:
            if self.channel and self.channel.isFavorite():
                self.header.SetSubTitle(header + ' %d torrents' % nr)
            else:
                self.header.SetSubTitle(header + ' %d torrents' % nr)

    @forceWxThread
    def RefreshData(self, key, data):
        List.RefreshData(self, key, data)

        if data:
            if isinstance(data, Torrent):
                if self.state == ChannelCommunity.CHANNEL_OPEN or self.iamModerator:
                    data = (data.infohash, [data.name, data.length, self.category_names[data.category],
                                            data.num_seeders, data.num_leechers, 0, None], data, DragItem)
                else:
                    data = (data.infohash, [data.name, data.length, self.category_names[data.category],
                                            data.num_seeders, data.num_leechers, 0, None], data)
            else:
                data = (data.id, [data.name, data.nr_torrents], data, PlaylistItem)
            self.list.RefreshData(key, data)

        manager = self.activityList.GetManager()
        manager.do_or_schedule_refresh()

    @warnWxThread
    def OnExpand(self, item):
        if isinstance(item, PlaylistItem):
            detailspanel = self.guiutility.SetBottomSplitterWindow(PlaylistDetails)
            detailspanel.showPlaylist(item.original_data)
            item.expandedPanel = detailspanel
        elif isinstance(item, TorrentListItem) or isinstance(item, ThumbnailListItem):
            detailspanel = self.guiutility.SetBottomSplitterWindow(TorrentDetails)
            detailspanel.setTorrent(item.original_data)
            item.expandedPanel = detailspanel

        self.top_header.header_list.DeselectAll()
        return True

    @warnWxThread
    def OnCollapse(self, item, panel, from_expand):
        if not isinstance(item, PlaylistItem) and panel:
            # detect changes
            changes = panel.GetChanged()
            if len(changes) > 0:
                dlg = wx.MessageDialog(
                    None,
                    'Do you want to save your changes made to this torrent?',
                    'Save changes?',
                    wx.YES_NO | wx.YES_DEFAULT | wx.ICON_QUESTION)
                if dlg.ShowModal() == wx.ID_YES:
                    self.OnSaveTorrent(self.channel, panel)
                dlg.Destroy()
        GenericSearchList.OnCollapse(self, item, panel, from_expand)

    @warnWxThread
    def ResetBottomWindow(self):
        _channel = self.channel

        if _channel:
            detailspanel = self.guiutility.SetBottomSplitterWindow(SelectedchannelInfoPanel)
            num_items = len(self.list.raw_data) if self.list.raw_data else 1
            detailspanel.Set(num_items, _channel.my_vote, self.state, self.iamModerator)
        else:
            self.guiutility.SetBottomSplitterWindow()

    @warnWxThread
    def OnSaveTorrent(self, channel, panel):
        changes = panel.GetChanged()
        if len(changes) > 0:
            self.channelsearch_manager.modifyTorrent(channel.id, panel.torrent.channeltorrent_id, changes)
            panel.Saved()

    @forceDBThread
    def AddTorrent(self, playlist, torrent):
        def gui_call():
            manager = self.GetManager()
            manager._refresh_list()

        self.channelsearch_manager.addPlaylistTorrent(playlist, torrent)
        wx.CallAfter(gui_call)

    @warnWxThread
    def OnRemoveFavorite(self, event):
        self.guiutility.RemoveFavorite(event, self.channel)

    @warnWxThread
    def OnFavorite(self, event=None):
        self.guiutility.MarkAsFavorite(event, self.channel)

    @warnWxThread
    def OnRemoveSpam(self, event):
        self.guiutility.RemoveSpam(event, self.channel)

    @warnWxThread
    def OnSpam(self, event):
        self.guiutility.MarkAsSpam(event, self.channel)

    @warnWxThread
    def OnManage(self, event):
        if self.channel:
            self.guiutility.showManageChannel(self.channel)

    @warnWxThread
    def OnBack(self, event):
        if self.channel:
            self.guiutility.GoBack(self.channel.id)

    @warnWxThread
    def OnSize(self, event):
        event.Skip()

    def OnChange(self, event):
        source = event.GetEventObject()
        if source == self.notebook:
            page = event.GetSelection()
            if page == 1:
                self.commentList.Show()
                self.commentList.Focus()

            elif page == 2:
                self.activityList.Show()
                self.activityList.Focus()

            elif page == 3:
                self.moderationList.Show()
                self.moderationList.Focus()

        self.UpdateSplitter()

        event.Skip()

    def OnDrag(self, dragitem):
        torrent = dragitem.original_data

        tdo = TorrentDO(torrent)
        tds = wx.DropSource(dragitem)
        tds.SetData(tdo)
        tds.DoDragDrop(True)

    @warnWxThread
    def OnCommentCreated(self, channel_id):
        if self.channel == channel_id:
            manager = self.commentList.GetManager()
            manager.new_comment()

            manager = self.activityList.GetManager()
            manager.new_activity()

        else:  # maybe channel_id is a infohash
            panel = self.list.GetExpandedItem()
            if panel:
                torDetails = panel.GetExpandedPanel()
                if torDetails:
                    torDetails.OnCommentCreated(channel_id)

    @warnWxThread
    def OnModificationCreated(self, channel_id):
        if self.channel == channel_id:
            manager = self.activityList.GetManager()
            manager.new_activity()

        else:  # maybe channel_id is a channeltorrent_id
            panel = self.list.GetExpandedItem()
            if panel:
                torDetails = panel.GetExpandedPanel()
                if torDetails:
                    torDetails.OnModificationCreated(channel_id)

    @warnWxThread
    def OnModerationCreated(self, channel_id):
        if self.channel == channel_id:
            manager = self.moderationList.GetManager()
            manager.new_moderation()

    @warnWxThread
    def OnMarkingCreated(self, channeltorrent_id):
        panel = self.list.GetExpandedItem()
        if panel:
            torDetails = panel.GetExpandedPanel()
            if torDetails:
                torDetails.OnMarkingCreated(channeltorrent_id)

    @warnWxThread
    def OnMarkTorrent(self, channel, infohash, type):
        self.channelsearch_manager.markTorrent(channel.id, infohash, type)

    def OnFilter(self, keyword):
        new_filter = keyword.lower().strip()

        self.categoryfilter = None
        if new_filter.find("category=") > -1:
            try:
                start = new_filter.find("category='")
                start = start + 10 if start >= 0 else -1
                end = new_filter.find("'", start)
                if start == -1 or end == -1:
                    category = None
                else:
                    category = new_filter[start:end]

                self.categoryfilter = category
                new_filter = new_filter[:start - 10] + new_filter[end + 1:]
            except:
                pass

        SizeList.OnFilter(self, new_filter)

    def GotFilter(self, keyword=None):
        GenericSearchList.GotFilter(self, keyword)
        self.GetManager().do_or_schedule_refresh()

    @warnWxThread
    def Select(self, key, raise_event=True, force=False):
        if isinstance(key, Torrent):
            torrent = key
            key = torrent.infohash

            if torrent.getPlaylist:
                self.guiutility.showPlaylist(torrent.getPlaylist)
                wx.CallLater(0, self.guiutility.frame.playlist.Select, key)
                return

        GenericSearchList.Select(self, key, raise_event, force)

        if self.notebook.GetPageCount() > 0:
            self.notebook.SetSelection(0)
            self.UpdateSplitter()
        self.ScrollToId(key)

    def UpdateSplitter(self):
        splitter = self.guiutility.frame.splitter
        topwindow = self.guiutility.frame.splitter_top_window
        bottomwindow = self.guiutility.frame.splitter_bottom_window
        if self.notebook.GetPageText(self.notebook.GetSelection()) == 'Contents':
            if not splitter.IsSplit():
                sashpos = getattr(self.parent, 'sashpos', -185)
                splitter.SplitHorizontally(topwindow, bottomwindow, sashpos)
        else:
            if splitter.IsSplit():
                self.parent.sashpos = splitter.GetSashPosition()
                splitter.Unsplit(bottomwindow)

    def StartDownload(self, torrent):
        def do_gui(delayedResult):
            nrdownloaded = delayedResult.get()
            if nrdownloaded:
                self._ShowFavoriteDialog(nrdownloaded)
                self.guiutility.torrentsearch_manager.downloadTorrent(torrent)

        def do_db():
            channel = self.channel
            if channel:
                return self.channelsearch_manager.getNrTorrentsDownloaded(channel.id) + 1

        if not self.channel.isFavorite():
            startWorker(do_gui, do_db, retryOnBusy=True, priority=GUI_PRI_DISPERSY)
        else:
            self.guiutility.torrentsearch_manager.downloadTorrent(torrent)

    def _ShowFavoriteDialog(self, nrdownloaded):
        dial = wx.MessageDialog(
            None,
            "You downloaded %d torrents from this Channel. "\
            "'Mark as favorite' will ensure that you will always have access to newest channel content.\n\n"\
            "Do you want to mark this channel as one of your favorites now?" % nrdownloaded,
            'Mark as Favorite?',
            wx.YES_NO | wx.YES_DEFAULT | wx.ICON_QUESTION)
        if dial.ShowModal() == wx.ID_YES:
            self.OnFavorite()

        dial.Destroy()


class TorrentDO(wx.CustomDataObject):

    def __init__(self, data):
        wx.CustomDataObject.__init__(self, wx.CustomDataFormat("TORRENT"))
        self.setObject(data)

    def setObject(self, obj):
        self.SetData(pickle.dumps(obj))

    def getObject(self):
        return pickle.loads(self.GetData())


class TorrentDT(wx.PyDropTarget):

    def __init__(self, playlist, callback):
        wx.PyDropTarget.__init__(self)
        self.playlist = playlist
        self.callback = callback

        self.cdo = TorrentDO(None)
        self.SetDataObject(self.cdo)

    def OnData(self, x, y, data):
        if self.GetData():
            self.callback(self.playlist, self.cdo.getObject())


class PlaylistManager(BaseManager):

    def __init__(self, list):
        BaseManager.__init__(self, list)

        self.library_manager = self.guiutility.library_manager
        self.channelsearch_manager = self.guiutility.channelsearch_manager

    def SetPlaylist(self, playlist):
        if self.list.playlist != playlist:
            self.list.Reset()

            self.list.playlist = playlist
            self.list.SetChannel(playlist.channel)

        self.refresh()

    def Reset(self):
        BaseManager.Reset(self)

        if self.list.playlist:
            cancelWorker("PlaylistManager_refresh_list_%d" % self.list.playlist.id)

    def refresh(self):
        def db_call():
            self.list.dirty = False
            return self.channelsearch_manager.getTorrentsFromPlaylist(self.list.playlist, self.guiutility.getFamilyFilter())

        if self.list.playlist:
            startWorker(
                self._on_data,
                db_call,
                uId=u"PlaylistManager_refresh_list_%d" %
                self.list.playlist.id,
                retryOnBusy=True,
                priority=GUI_PRI_DISPERSY)

    @forceDBThread
    def refresh_partial(self, ids):
        if self.list.playlist:
            id_data = {}
            for id in ids:
                if isinstance(id, str) and len(id) == 20:
                    id_data[id] = self.channelsearch_manager.getTorrentFromPlaylist(self.list.playlist, id)

            def do_gui():
                for id, data in id_data.iteritems():
                    self.list.RefreshData(id, data)
            wx.CallAfter(do_gui)

    def _on_data(self, delayedResult):
        total_items, nrfiltered, torrents = delayedResult.get()
        torrents = self.library_manager.addDownloadStates(torrents)

        self.list.SetData([], torrents)

    def torrentUpdated(self, infohash):
        if self.list.InList(infohash):
            self.do_or_schedule_partial([infohash])

    def torrentsUpdated(self, infohashes):
        infohashes = [infohash for infohash in infohashes if self.list.InList(infohash)]
        self.do_or_schedule_partial(infohashes)

    def playlistUpdated(self, playlist_id, modified=False):
        if self.list.playlist == playlist_id:
            if modified:
                self.do_or_schedule_refresh()
            else:
                self.guiutility.GoBack()


class Playlist(SelectedChannelList):

    def __init__(self, *args, **kwargs):
        self.playlist = None
        SelectedChannelList.__init__(self, *args, **kwargs)

    def _special_icon(self, item):
        if not isinstance(item, PlaylistItem) and self.playlist and self.playlist.channel:
            if self.playlist.channel.isFavorite():
                return self.favorite, self.normal, "This torrent is part of one of your favorite channels, %s" % self.playlist.channel.name
            else:
                return self.normal, self.favorite, "This torrent is not part of one of your favorite channels"
        else:
            pass

    def GetManager(self):
        if getattr(self, 'manager', None) is None:
            self.manager = PlaylistManager(self)
        return self.manager

    @warnWxThread
    def CreateHeader(self, parent):
        return SelectedPlaylistFilter(parent, self)

    @warnWxThread
    def CreateTopHeader(self, parent):
        return PlaylistHeader(parent, self)

    def Set(self, playlist):
        self.playlist = playlist
        manager = self.GetManager()
        manager.SetPlaylist(playlist)
        if self.notebook.GetPageCount() > 0:
            self.notebook.SetSelection(0)
        if self.playlist:
            self.top_header.SetTitle(self.playlist)
            self.Layout()

    def SetTitle(self, title, description):
        header = u"%s's channel \u2192 %s" % (self.channel.name, self.playlist.name)

        self.header.SetTitle(header)
        self.header.SetStyle(self.playlist.description)
        self.Layout()

    def SetIds(self, channel):
        if channel:
            manager = self.commentList.GetManager()
            manager.SetIds(channel=channel, playlist=self.playlist)

            manager = self.activityList.GetManager()
            manager.SetIds(channel=channel, playlist=self.playlist)

            manager = self.moderationList.GetManager()
            manager.SetIds(channel=channel, playlist=self.playlist)

    def OnCommentCreated(self, key):
        SelectedChannelList.OnCommentCreated(self, key)

        if self.InList(key):
            manager = self.commentList.GetManager()
            manager.new_comment()

    def CreateFooter(self, parent):
        return PlaylistFooter(parent, radius=0, spacers=[7, 7])

    @warnWxThread
    def ResetBottomWindow(self):
        detailspanel = self.guiutility.SetBottomSplitterWindow(PlaylistInfoPanel)
        detailspanel.Set(
            len(self.list.raw_data) if self.list.raw_data else 1,
            self.playlist.channel.isFavorite() if self.playlist and self.playlist.channel else None)


class ManageChannelFilesManager(BaseManager):

    def __init__(self, list):
        BaseManager.__init__(self, list)

        self.channel = None
        self.channelsearch_manager = self.guiutility.channelsearch_manager

        self.Reset()

    def Reset(self):
        BaseManager.Reset(self)

        if self.channel:
            cancelWorker("ManageChannelFilesManager_refresh_%d" % self.channel.id)

        self.channel = None

    def refresh(self):
        def db_call():
            self.list.dirty = False
            return self.channelsearch_manager.getTorrentsFromChannel(self.channel, filterTorrents=False)

        startWorker(
            self._on_data,
            db_call,
            uId=u"ManageChannelFilesManager_refresh_%d" %
            self.channel.id,
            retryOnBusy=True,
            priority=GUI_PRI_DISPERSY)

    def _on_data(self, delayedResult):
        total_items, nrfiltered, torrentList = delayedResult.get()
        self.list.SetData(torrentList)

    def SetChannel(self, channel):
        if self.channel != channel:
            self.channel = channel
            self.do_or_schedule_refresh()

    def RemoveItems(self, infohashes):
        for infohash in infohashes:
            self.channelsearch_manager.removeTorrent(self.channel, infohash)

    def RemoveAllItems(self):
        self.channelsearch_manager.removeAllTorrents(self.channel)

    def startDownloadFromUrl(self, url, *args, **kwargs):
        try:
            tdef = TorrentDef.load_from_url(url)
            if tdef:
                return self.AddTDef(tdef)
        except:
            print_exc()

        return False

    def startDownloadFromMagnet(self, url, *args, **kwargs):
        try:
            callback = lambda meta_info: self.AddTDef(TorrentDef.load_from_dict(meta_info))
            self.guiutility.utility.session.lm.ltmgr.get_metainfo(url, callback, timeout=300)
            return True

        except:
            print_exc()
            return False

    def startDownload(self, torrentfilename, *args, **kwargs):
        try:
            # if fixtorrent not in kwargs -> new torrent created
            tdef = TorrentDef.load(torrentfilename)
            if 'fixtorrent' not in kwargs:
                download = self.guiutility.frame.startDownload(torrentfilename=torrentfilename,
                                                               destdir=kwargs.get('destdir', None))
            return self.AddTDef(tdef)

        except:
            print_exc()
        return False

    def startDownloadFromTorrent(self, torrent):
        self.channelsearch_manager.createTorrent(self.channel, torrent)
        return True

    def AddTDef(self, tdef):
        if tdef:
            self.channelsearch_manager.createTorrentFromDef(self.channel.id, tdef)
            if not self.channel.isMyChannel():
                notification = "New torrent added to %s's channel" % self.channel.name
            else:
                notification = 'New torrent added to My Channel'
            self.guiutility.Notify(notification, icon=wx.ART_INFORMATION)

            return True
        return False

    def DoExport(self, target_dir):
        if os.path.isdir(target_dir):
            _, _, torrents = self.channelsearch_manager.getTorrentsFromChannel(self.channel, filterTorrents=False)

            nr_torrents_exported = 0
            for torrent in torrents:
                torrent_data = self.channelsearch_manager.session.get_collected_torrent(torrent.infohash)
                if torrent_data is not None:
                    torrent_file_name = hexlify(torrent.infohash) + u'.torrent'
                    new_torrent_filename = os.path.join(target_dir, torrent_file_name)
                    try:
                        with open(new_torrent_filename, 'rb') as f:
                            f.write(torrent_data)
                        nr_torrents_exported += 1
                    except Exception, e:
                        self._logger.error("failed to export data to torrent file %s: %s", new_torrent_filename, e)

            self.guiutility.Notify('%d torrents exported' % nr_torrents_exported, icon=wx.ART_INFORMATION)


class ManageChannelPlaylistsManager(BaseManager):

    def __init__(self, list):
        BaseManager.__init__(self, list)

        self.channel = None
        self.channelsearch_manager = GUIUtility.getInstance().channelsearch_manager

        self.Reset()

    def Reset(self):
        BaseManager.Reset(self)

        if self.channel:
            cancelWorker("ManageChannelPlaylistsManager_refresh_%d" % self.channel.id)

        self.channel = None

    def refresh(self):
        def db_call():
            self.list.dirty = False
            _, playlistList = self.channelsearch_manager.getPlaylistsFromChannel(self.channel)
            return playlistList

        startWorker(
            self.list.SetDelayedData,
            db_call,
            uId=u"ManageChannelPlaylistsManager_refresh_%d" %
            self.channel.id,
            retryOnBusy=True,
            priority=GUI_PRI_DISPERSY)

    def refresh_partial(self, playlist_id):
        startWorker(
            self.list.RefreshDelayedData,
            self.channelsearch_manager.getPlaylist,
            wargs=(self.channel,
                   playlist_id),
            cargs=(playlist_id,
                   ),
            retryOnBusy=True,
            priority=GUI_PRI_DISPERSY)

    def SetChannel(self, channel):
        if channel != self.channel:
            self.channel = channel
            self.do_or_schedule_refresh()

    def RemoveItems(self, ids):
        for id in ids:
            self.channelsearch_manager.removePlaylist(self.channel, id)

    def RemoveAllItems(self):
        self.channelsearch_manager.removeAllPlaylists(self.channel)

    def GetTorrentsFromChannel(self):
        delayedResult = startWorker(None, self.channelsearch_manager.getTorrentsFromChannel, wargs=(self.channel,),
                                    wkwargs={'filterTorrents': False}, retryOnBusy=True, priority=GUI_PRI_DISPERSY)
        total_items, nrfiltered, torrentList = delayedResult.get()
        return torrentList

    def GetTorrentsNotInPlaylist(self):
        delayedResult = startWorker(None, self.channelsearch_manager.getTorrentsNotInPlaylist, wargs=(self.channel,),
                                    wkwargs={'filterTorrents': False}, retryOnBusy=True, priority=GUI_PRI_DISPERSY)
        total_items, nrfiltered, torrentList = delayedResult.get()
        return torrentList

    def GetTorrentsFromPlaylist(self, playlist):
        delayedResult = startWorker(None, self.channelsearch_manager.getTorrentsFromPlaylist, wargs=(playlist,),
                                    wkwargs={'filterTorrents': False}, retryOnBusy=True, priority=GUI_PRI_DISPERSY)
        total_items, nrfiltered, torrentList = delayedResult.get()
        return torrentList

    def createPlaylist(self, name, description, infohashes):
        startWorker(None, self.channelsearch_manager.createPlaylist,
                    wargs=(self.channel.id, name, description, infohashes),
                    retryOnBusy=True, priority=GUI_PRI_DISPERSY)

    def savePlaylist(self, playlist_id, name, description):
        startWorker(None, self.channelsearch_manager.modifyPlaylist,
                    wargs=(self.channel.id, playlist_id, name, description),
                    retryOnBusy=True, priority=GUI_PRI_DISPERSY)

    def savePlaylistTorrents(self, playlist_id, infohashes):
        startWorker(None, self.channelsearch_manager.savePlaylistTorrents,
                    wargs=(self.channel.id, playlist_id, infohashes), retryOnBusy=True, priority=GUI_PRI_DISPERSY)

    def playlistUpdated(self, playlist_id, modified=False):
        if self.list.InList(playlist_id):
            if modified:
                self.do_or_schedule_partial([playlist_id])
            else:
                self.do_or_schedule_refresh()


class ManageChannel(AbstractDetails):

    def __init__(self, parent):
        AbstractDetails.__init__(self, parent)
        self.SetForegroundColour(parent.GetForegroundColour())

        self.channel = None
        self.rss_url = None

        self.guiutility = GUIUtility.getInstance()
        self.channelsearch_manager = self.guiutility.channelsearch_manager

        self.SetBackgroundColour(LIST_LIGHTBLUE)
        boxSizer = wx.BoxSizer(wx.VERTICAL)

        self.header = ManageChannelHeader(self, self)
        self.header.SetBackgroundColour(LIST_LIGHTBLUE)
        boxSizer.Add(self.header, 0, wx.EXPAND)

        self.notebook = wx.Notebook(self, style=wx.NB_NOPAGETHEME)
        self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.OnChange)

        # overview page intro
        self.overviewpage = wx.Panel(self.notebook)
        self.overviewpage.SetBackgroundColour(LIST_DESELECTED)

        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.AddSpacer((-1, 10))
        header = ""
        self.overviewheader = self._add_header(self.overviewpage, vSizer, header, spacer=10)

        text = "Channels can be used to spread torrents to other Tribler users. "
        text += "If a channel provides other Tribler users with original or popular content, then they might mark your channel as one of their favorites. "
        text += "This will help to promote your channel, because the number of users which have marked a channel as one of their favorites is used to calculate popularity. "
        text += "Additionally, when another Tribler user marks your channel as a favorite they help you distribute all the .torrent files.\n\n"
        text += "Currently three options exist to spread torrents. "
        text += "Two of them, periodically importing .torrents from an rss feed and manually adding .torrent files, are available from the 'Manage' tab.\n"
        text += "The third option is available from the torrentview after completely downloading a torrent and allows you to add a torrent to your channel with a single click."

        overviewtext = wx.StaticText(self.overviewpage, -1, text)
        vSizer.Add(overviewtext, 0, wx.EXPAND | wx.ALL, 10)

        text = "Currently your channel is not created. Please fill in  a name and description and click the create button to start spreading your torrents."
        self.createText = wx.StaticText(self.overviewpage, -1, text)
        self.createText.Hide()
        vSizer.Add(self.createText, 0, wx.EXPAND | wx.ALL, 10)

        gridSizer = wx.FlexGridSizer(0, 2, 3, 3)
        gridSizer.AddGrowableCol(1)
        gridSizer.AddGrowableRow(1)

        self.name = EditText(self.overviewpage, '')
        self.name.SetMaxLength(40)

        self.description = EditText(self.overviewpage, '', multiline=True)
        self.description.SetMaxLength(2000)
        self.description.SetMinSize((-1, 50))

        identSizer = wx.BoxSizer(wx.VERTICAL)
        self.identifier = EditText(self.overviewpage, '')
        self.identifier.SetMaxLength(40)
        self.identifier.SetEditable(False)
        self.identifierText = BetterText(
            self.overviewpage,
            -1, 'You can use this identifier to allow other to manually join this channel.\n'
            'Copy and paste it in an email and let others join by going to Favorites and "Add Favorite channel"')

        identSizer.Add(self.identifier, 0, wx.EXPAND)
        identSizer.Add(self.identifierText, 0, wx.EXPAND)

        self._add_row(self.overviewpage, gridSizer, "Name", self.name, 10)
        self._add_row(self.overviewpage, gridSizer, 'Description', self.description, 10)
        self._add_row(self.overviewpage, gridSizer, 'Identifier', identSizer, 10)
        vSizer.Add(gridSizer, 0, wx.EXPAND | wx.RIGHT, 10)

        self.saveButton = wx.Button(self.overviewpage, -1, 'Save Changes')
        self.saveButton.Bind(wx.EVT_BUTTON, self.Save)
        vSizer.Add(self.saveButton, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        self.overviewpage.SetSizer(vSizer)
        self.overviewpage.Show(False)

        # Open2Edit settings
        self.settingspage = wx.Panel(self.notebook)
        self.settingspage.SetBackgroundColour(LIST_DESELECTED)

        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.AddSpacer((-1, 10))
        header = "Community Settings"
        self._add_header(self.settingspage, vSizer, header, spacer=10)

        text = "Tribler allows you to involve your community. "
        text += "You as a channel-owner have the option to define the openness of your community. "
        text += "By choosing a more open setting, other users are allowed to do more.\n\n"

        text += "Currently three configurations exist:\n"
        text += "\tOpen, only you can define playlists and delete torrents. Other users can do everything else, ie add torrents, categorize torrents, comment etc.\n"
        text += "\tSemi-Open, only you can add new .torrents. Other users can download and comment on them.\n"
        text += "\tClosed, only you can add new .torrents. Other users can only download them."
        vSizer.Add(wx.StaticText(self.settingspage, -1, text), 0, wx.EXPAND | wx.ALL, 10)

        gridSizer = wx.FlexGridSizer(0, 2, 3, 3)
        gridSizer.AddGrowableCol(1)
        gridSizer.AddGrowableRow(1)

        self.statebox = wx.RadioBox(self.settingspage, choices=('Open', 'Semi-Open', 'Closed'), style=wx.RA_VERTICAL)
        self._add_row(self.settingspage, gridSizer, "Configuration", self.statebox)
        vSizer.Add(gridSizer, 0, wx.EXPAND | wx.RIGHT, 10)

        saveButton = wx.Button(self.settingspage, -1, 'Save Changes')
        saveButton.Bind(wx.EVT_BUTTON, self.SaveSettings)
        vSizer.Add(saveButton, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        self.settingspage.SetSizer(vSizer)
        self.settingspage.Show(False)

        # shared files page
        self.fileslist = NotebookPanel(self.notebook)
        filelist = ManageChannelFilesList(self.fileslist)
        self.fileslist.SetList(filelist)
        filelist.SetNrResults = self.header.SetNrTorrents
        self.fileslist.Show(False)

        # playlist page
        self.playlistlist = NotebookPanel(self.notebook)
        self.playlistlist.SetList(ManageChannelPlaylistList(self.playlistlist))
        self.playlistlist.Show(False)

        # manage page
        self.managepage = wx.Panel(self.notebook)
        self.managepage.SetBackgroundColour(LIST_DESELECTED)
        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.AddSpacer((-1, 10))

        # rss intro
        header = "Rss import"
        self._add_header(self.managepage, vSizer, header, spacer=10)

        text = "Rss feeds are periodically checked for new .torrent files. \nFor each item in the rss feed a .torrent file should be present in either:\n\n"
        text += "\tThe link element\n"
        text += "\tA src attribute\n"
        text += "\tA url attribute"
        manageText = wx.StaticText(self.managepage, -1, text)
        vSizer.Add(manageText, 0, wx.EXPAND | wx.ALL, 10)

        # rss
        self.gridSizer = wx.FlexGridSizer(0, 2, 3)
        self.gridSizer.AddGrowableCol(1)
        self.gridSizer.AddGrowableRow(0)

        vSizer.Add(self.gridSizer, 1, wx.EXPAND | wx.ALL, 10)
        self.managepage.SetSizer(vSizer)
        self.managepage.Show(False)

        from Tribler.Core.simpledefs import SIGNAL_RSS_FEED, SIGNAL_ON_UPDATED
        self.guiutility.utility.session.add_observer(self._on_rss_feed_updated,
                                                     SIGNAL_RSS_FEED, [SIGNAL_ON_UPDATED])

        boxSizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 5)
        self.SetSizer(boxSizer)
        self.Layout()

    def BuildRssPanel(self, parent, sizer):
        self._add_subheader(parent, sizer, "Current rss-feeds:", "(which are periodically checked)")

        rssSizer = wx.BoxSizer(wx.VERTICAL)

        if self.channel:
            my_channel_object = self.guiutility.utility.session.lm.channel_manager.get_my_channel(self.channel.id)
            urls = my_channel_object.get_rss_feed_url_list()
        else:
            urls = []

        if len(urls) > 0:
            rssPanel = wx.lib.scrolledpanel.ScrolledPanel(parent)
            rssPanel.SetBackgroundColour(LIST_DESELECTED)

            urlSizer = wx.FlexGridSizer(0, 2, 0, 5)
            urlSizer.AddGrowableCol(0)
            for url in urls:
                rsstext = wx.StaticText(rssPanel, -1, url.replace('&', '&&'))
                rsstext.SetMinSize((1, -1))

                deleteButton = wx.Button(rssPanel, -1, "Delete")
                deleteButton.url = url
                deleteButton.text = rsstext
                deleteButton.Bind(wx.EVT_BUTTON, self.OnDeleteRss)

                urlSizer.Add(rsstext, 1, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
                urlSizer.Add(deleteButton, 0, wx.ALIGN_RIGHT)

            rssPanel.SetMinSize((-1, 50))
            rssPanel.SetSizer(urlSizer)
            rssPanel.SetupScrolling(rate_y=5)
            rssSizer.Add(rssPanel, 1, wx.EXPAND)

            refresh = wx.Button(parent, -1, "Refresh all rss-feeds")
            refresh.Bind(wx.EVT_BUTTON, self.OnRefreshRss)
            rssSizer.Add(refresh, 0, wx.ALIGN_RIGHT | wx.TOP, 3)
        else:
            rssSizer.Add(wx.StaticText(parent, -1, "No rss feeds are being monitored."))

        # add-rss
        rssSizer.Add(wx.StaticText(parent, -1, "Add an rss-feed:"), 0, wx.TOP, 3)
        addSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.rss_url = wx.TextCtrl(parent)
        addButton = wx.Button(parent, -1, "Add")
        addButton.Bind(wx.EVT_BUTTON, self.OnAddRss)
        addSizer.Add(self.rss_url, 1, wx.ALIGN_CENTER_VERTICAL)
        addSizer.Add(addButton, 0, wx.LEFT | wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT, 5)
        rssSizer.Add(addSizer, 0, wx.EXPAND, 10)
        sizer.Add(rssSizer, 1, wx.EXPAND | wx.LEFT | wx.TOP | wx.BOTTOM, 10)

    def RebuildRssPanel(self):
        self.gridSizer.ShowItems(False)
        self.gridSizer.Clear()

        self.BuildRssPanel(self.managepage, self.gridSizer)
        self.managepage.Layout()

    @forceWxThread
    def SetChannel(self, channel):
        self.channel = channel

        if channel:
            self.fileslist.GetManager().SetChannel(channel)
            self.playlistlist.GetManager().SetChannel(channel)

            self.header.SetName('Management interface for %s\'s Channel' % channel.name)
            self.header.SetNrTorrents(channel.nr_torrents, channel.nr_favorites)

            if channel.isMyChannel():
                self.overviewheader.SetLabel('Welcome to the management interface for your channel.')

            self.name.SetValue(channel.name)
            self.name.originalValue = channel.name
            self.name.Enable(channel.isMyChannel())

            self.description.SetValue(channel.description)
            self.description.originalValue = channel.description
            self.description.Enable(channel.isMyChannel())

            self.identifier.SetValue(channel.dispersy_cid.encode('HEX'))
            self.identifier.Show(True)
            self.identifierText.Show(True)

            self.overviewpage.Layout()

            self.createText.Hide()
            self.saveButton.SetLabel('Save Changes')

            self.AddPage(self.notebook, self.overviewpage, "Overview", 0)

            def db_call():
                channel_state, iamModerator = self.channelsearch_manager.getChannelState(channel.id)
                return channel_state, iamModerator

            def update_panel(delayedResult):
                try:
                    channel_state, iamModerator = delayedResult.get()
                except:
                    startWorker(update_panel, db_call, delay=1.0, retryOnBusy=True, priority=GUI_PRI_DISPERSY)
                    return

                if iamModerator:
                    if iamModerator and not channel.isMyChannel():
                        self.overviewheader.SetLabel('Welcome to the management interface for this channel. '
                                                    'You can modify these setting as you have the required permissions.')

                    self.name.Enable(True)
                    self.description.Enable(True)

                    selection = channel_state
                    if selection == 0:
                        selection = 2
                    elif selection == 2:
                        selection = 0

                    self.statebox.SetSelection(selection)
                    self.AddPage(self.notebook, self.settingspage, "Settings", 1)
                else:
                    self.overviewheader.SetLabel('Welcome to the management interface for this channel. '
                        'You cannot modify any of these settings as you do not have the required permissions.')
                    self.RemovePage(self.notebook, "Settings")

                if iamModerator or channel_state == ChannelCommunity.CHANNEL_OPEN:
                    self.fileslist.SetFooter(channel_state, iamModerator)
                    self.AddPage(self.notebook, self.fileslist, "Manage torrents", 2)

                    self.playlistlist.SetFooter(channel_state, iamModerator)
                    self.AddPage(self.notebook, self.playlistlist, "Manage playlists", 3)
                else:
                    self.RemovePage(self.notebook, "Manage torrents")
                    self.RemovePage(self.notebook, "Manage playlists")

                if iamModerator:
                    self.RebuildRssPanel()
                    self.AddPage(self.notebook, self.managepage, "Manage", 4)
                else:
                    self.RemovePage(self.notebook, "Manage")

                self.Refresh()
                # self.CreateJoinChannelFile()

            startWorker(update_panel, db_call, retryOnBusy=True, priority=GUI_PRI_DISPERSY)

        else:
            self.overviewheader.SetLabel('Welcome to the management interface for your channel. '
                'You currently do not yet have a channel, create one now.')

            self.name.SetValue('')
            self.name.originalValue = ''

            self.description.SetValue('')
            self.description.originalValue = ''

            self.name.Enable(True)
            self.description.Enable(True)
            self.identifier.Show(False)
            self.identifierText.Show(False)

            self.overviewpage.Layout()

            self.header.SetName('Create your own channel')
            self.header.SetNrTorrents(0, 0)

            self.createText.Show()
            self.saveButton.SetLabel('Create Channel')

            self.AddPage(self.notebook, self.overviewpage, "Overview", 0)

            # disable all other tabs, do it in reverse as pageindexes change
            for i in range(self.notebook.GetPageCount(), 1, -1):
                page = self.notebook.GetPage(i - 1)
                page.Show(False)
                self.notebook.RemovePage(i - 1)

            self.fileslist.Reset()
            self.playlistlist.Reset()

        # Always switch to page 1 after new id
        if self.notebook.GetPageCount() > 0:
            self.notebook.SetSelection(0)

    @warnWxThread
    def Reset(self):
        self.SetChannel(None)

    @forceDBThread
    def SetChannelId(self, channel_id):
        if not (self and self.channelsearch_manager):
            return

        channel = self.channelsearch_manager.getChannel(channel_id)
        self.SetChannel(channel)

    def GetPage(self, notebook, title):
        for i in range(notebook.GetPageCount()):
            if notebook.GetPageText(i) == title:
                return i
        return None

    def AddPage(self, notebook, page, title, index):
        curindex = self.GetPage(notebook, title)
        if curindex is None:
            page.Show(True)

            index = min(notebook.GetPageCount(), index)
            notebook.InsertPage(index, page, title)

    def RemovePage(self, notebook, title):
        curindex = self.GetPage(notebook, title)
        if curindex is not None:
            page = notebook.GetPage(curindex)

            page.Show(False)
            notebook.RemovePage(curindex)

    def IsChanged(self):
        return self.name.IsChanged() or self.description.IsChanged()

    def OnChange(self, event):
        page = event.GetSelection()
        if page == self.GetPage(self.notebook, "Manage torrents"):
            self.fileslist.Show(isSelected=True)
            self.fileslist.Focus()

        elif page == self.GetPage(self.notebook, "Manage playlists"):
            self.playlistlist.Show(isSelected=True)
            self.playlistlist.Focus()
        event.Skip()

    def _on_rss_feed_updated(self, subject, change_type, object_id, rss_data):
        if rss_data['channel'].get_channel_id() != self.channel.id:
            return

        wx.CallAfter(self.RebuildRssPanel)

    def OnAddRss(self, event=None):
        url = self.rss_url.GetValue().strip()
        if len(url) > 0:
            my_channel_object = self.guiutility.utility.session.lm.channel_manager.get_my_channel(self.channel.id)
            my_channel_object.create_rss_feed(url)

    def OnDeleteRss(self, event):
        item = event.GetEventObject()

        my_channel_object = self.guiutility.utility.session.lm.channel_manager.get_my_channel(self.channel.id)
        my_channel_object.remove_rss_feed(item.url)

    def OnRefreshRss(self, event):
        # TODO(lipu): fix this

        button = event.GetEventObject()
        button.Enable(False)
        wx.CallLater(5000, button.Enable, True)

    def CreateJoinChannelFile(self):
        f = open('joinchannel', 'wb')
        f.write(self.channel.dispersy_cid)
        f.close()

    def Show(self, show=True):
        if not show:
            if self.IsChanged():
                dlg = wx.MessageDialog(
                    None,
                    'Do you want to save your changes made to this channel?',
                    'Save changes?',
                    wx.YES_NO | wx.YES_DEFAULT | wx.ICON_QUESTION)
                if dlg.ShowModal() == wx.ID_YES:
                    self.Save()

        AbstractDetails.Show(self, show)

    def Save(self, event=None):
        if self.name.GetValue():
            if self.channel:
                changes = {}
                if self.name.IsChanged():
                    changes['name'] = self.name.GetValue()
                if self.description.IsChanged():
                    changes['description'] = self.description.GetValue()

                self.channelsearch_manager.modifyChannel(self.channel.id, changes)
            else:
                self.channelsearch_manager.createChannel(self.name.GetValue(), self.description.GetValue())

            self.name.Saved()
            self.description.Saved()

            if event:
                button = event.GetEventObject()
                button.Enable(False)
                wx.CallLater(5000, button.Enable, True)

        elif sys.platform != 'darwin':
            showError(self.name)

    def SaveSettings(self, event):
        state = self.statebox.GetSelection()
        if state == 0:
            state = 2
        elif state == 2:
            state = 0

        startWorker(
            None,
            self.channelsearch_manager.setChannelState,
            wargs=(self.channel.id,
                   state),
            retryOnBusy=True,
            priority=GUI_PRI_DISPERSY)

        button = event.GetEventObject()
        button.Enable(False)
        wx.CallLater(5000, button.Enable, True)

    def playlistCreated(self, channel_id):
        if self.channel == channel_id:
            manager = self.playlistlist.GetManager()
            manager.do_or_schedule_refresh()

    def playlistUpdated(self, playlist_id, modified=False):
        manager = self.playlistlist.GetManager()
        manager.playlistUpdated(playlist_id, modified)

    def channelUpdated(self, channel_id, created=False, modified=False):
        if self.channel == channel_id:
            manager = self.fileslist.GetManager()
            manager.do_or_schedule_refresh()

            if modified:
                self.SetChannelId(channel_id)

        elif not self.channel and created:
            self.SetChannelId(channel_id)


class ManageChannelFilesList(List):

    def __init__(self, parent):
        columns = [
            {'name': 'Name', 'width': wx.LIST_AUTOSIZE, 'icon': 'checkbox', 'sortAsc': True, 'showColumname': False},
                   {'name': 'Date Added', 'width': 85, 'fmt': format_time, 'defaultSorted': True, 'showColumname': False}]

        List.__init__(self, columns, LIST_LIGHTBLUE, [0, 0], parent=parent, borders=False)

    def CreateHeader(self, parent):
        return TitleHeader(parent, self, self.columns, 0, wx.FONTWEIGHT_BOLD, 0)

    def CreateFooter(self, parent):
        return ManageChannelFilesFooter(parent, self.OnRemoveAll, self.OnRemoveSelected, self.OnAdd, self.OnExport)

    def GetManager(self):
        if getattr(self, 'manager', None) is None:
            self.manager = ManageChannelFilesManager(self)
        return self.manager

    def SetData(self, data):
        List.SetData(self, data)

        data = [(torrent.infohash, [torrent.name, torrent.time_stamp], torrent) for torrent in data]
        if len(data) > 0:
            self.list.SetData(data)
        else:
            self.list.ShowMessage('You are currently not sharing any torrents in your channel.')
            self.SetNrResults(0)

    def SetFooter(self, state, iamModerator):
        self.canDelete = iamModerator
        self.canAdd = (state == ChannelCommunity.CHANNEL_OPEN) or iamModerator

        self.footer.SetState(self.canDelete, self.canAdd)

        if self.canDelete:
            self.header.SetTitle('Use this view to add or remove torrents')
        elif self.canAdd:
            self.header.SetTitle('Use this view to add torrents')
        else:
            self.header.SetTitle('')

    def OnExpand(self, item):
        return True

    def OnRemoveAll(self, event):
        dlg = wx.MessageDialog(
            None,
            'Are you sure you want to remove all torrents from your channel?',
            'Remove torrents',
            wx.ICON_QUESTION | wx.YES_NO | wx.NO_DEFAULT)
        if dlg.ShowModal() == wx.ID_YES:
            self.GetManager().RemoveAllItems()
        dlg.Destroy()

    def OnRemoveSelected(self, event):
        dlg = wx.MessageDialog(
            None,
            'Are you sure you want to remove all selected torrents from your channel?',
            'Remove torrents',
            wx.ICON_QUESTION | wx.YES_NO | wx.NO_DEFAULT)
        if dlg.ShowModal() == wx.ID_YES:
            infohashes = [key for key, _ in self.list.GetExpandedItems()]
            self.GetManager().RemoveItems(infohashes)
        dlg.Destroy()

    def OnAdd(self, event):
        _, libraryTorrents = self.guiutility.library_manager.getHitsInCategory()

        dlg = AddTorrent(None, self.GetManager(), libraryTorrents)
        dlg.CenterOnParent()
        dlg.ShowModal()
        dlg.Destroy()

    def OnExport(self, event):
        dlg = wx.DirDialog(
            None,
            "Please select a directory to which all .torrents should be exported",
            style=wx.wx.DD_DIR_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK and os.path.isdir(dlg.GetPath()):
            self.GetManager().DoExport(dlg.GetPath())
        dlg.Destroy()


class ManageChannelPlaylistList(ManageChannelFilesList):

    def __init__(self, parent):
        columns = [{'name': 'Name',
                    'width': wx.LIST_AUTOSIZE,
                    'icon': 'checkbox',
                    'sortAsc': True,
                    'showColumname': False}]

        List.__init__(self, columns, LIST_LIGHTBLUE, [0, 0], True, parent=parent, borders=False)

    def CreateFooter(self, parent):
        return ManageChannelPlaylistFooter(parent, self.OnNew)

    def GetManager(self):
        if getattr(self, 'manager', None) is None:
            self.manager = ManageChannelPlaylistsManager(self)
        return self.manager

    @forceWxThread
    def RefreshData(self, key, playlist):
        data = (playlist.id, (playlist.name,), playlist)
        self.list.RefreshData(key, data)

    @forceWxThread
    def SetData(self, data):
        List.SetData(self, data)

        data = [(playlist.id, [playlist.name, playlist.nr_torrents, 0, 0], playlist, PlaylistItem, index)
                for index, playlist in enumerate(data)]
        if len(data) > 0:
            self.list.SetData(data)
        else:
            self.list.ShowMessage('You currently do not have any playlists in your channel.')
            self.SetNrResults(0)

    def SetFooter(self, state, iamModerator):
        self.canDelete = iamModerator
        self.canAdd = (state == ChannelCommunity.CHANNEL_OPEN) or iamModerator

        self.footer.SetState(self.canDelete, self.canAdd)

        if self.canDelete:
            self.header.SetTitle('Use this view to create, modify and delete playlists')
        elif self.canAdd:
            self.header.SetTitle('Use this view to add torrents to existing playlists')
        else:
            self.header.SetTitle('')

    def OnExpand(self, item):
        return MyChannelPlaylist(item, self.OnEdit, self.canDelete, self.OnSave, self.OnRemoveSelected, item.original_data)

    def OnCollapse(self, item, panel, from_expand):
        playlist_id = item.original_data.get('id', False)
        if playlist_id:
            if panel.IsChanged():
                dlg = wx.MessageDialog(
                    None,
                    'Do you want to save your changes made to this playlist?',
                    'Save changes?',
                    wx.YES_NO | wx.YES_DEFAULT | wx.ICON_QUESTION)
                if dlg.ShowModal() == wx.ID_YES:
                    self.OnSave(playlist_id, panel)
        ManageChannelFilesList.OnCollapse(self, item, panel, from_expand)
        self.list.Layout()

    def OnSave(self, playlist_id, panel):
        name, description, _ = panel.GetInfo()
        manager = self.GetManager()
        manager.savePlaylist(playlist_id, name, description)

    def OnNew(self, event):
        vSizer = wx.BoxSizer(wx.VERTICAL)

        dlg = wx.Dialog(
            None,
            -1,
            'Create a new playlist',
            size=(500, 300),
            style=wx.RESIZE_BORDER | wx.DEFAULT_DIALOG_STYLE)
        playlistdetails = MyChannelPlaylist(dlg, self.OnManage, can_edit=True)

        vSizer.Add(playlistdetails, 1, wx.EXPAND | wx.ALL, 3)
        vSizer.Add(dlg.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL), 0, wx.EXPAND | wx.ALL, 3)

        dlg.SetSizer(vSizer)
        if dlg.ShowModal() == wx.ID_OK:
            name, description, infohashes = playlistdetails.GetInfo()

            manager = self.GetManager()
            manager.createPlaylist(name, description, infohashes)
        dlg.Destroy()

    def OnRemoveSelected(self, playlist_id, panel):
        dlg = wx.MessageDialog(
            None, 'Are you sure you want to remove this playlist from your channel?',
            'Remove playlist',
            wx.ICON_QUESTION | wx.YES_NO | wx.NO_DEFAULT)
        if dlg.ShowModal() == wx.ID_YES:
            self.GetManager().RemoveItems([playlist_id])
        dlg.Destroy()

    def OnEdit(self, playlist):
        torrent_ids = self.OnManage(playlist)
        if torrent_ids is not None:
            manager = self.GetManager()
            manager.savePlaylistTorrents(playlist.id, torrent_ids)

    def OnManage(self, playlist):
        dlg = wx.Dialog(None, -1,
            'Manage the torrents for this playlist',
            size=(900, 500),
            style=wx.RESIZE_BORDER | wx.DEFAULT_DIALOG_STYLE)

        manager = self.GetManager()
        available = manager.GetTorrentsFromChannel()
        not_in_playlist = manager.GetTorrentsNotInPlaylist()
        if playlist.get('id', False):
            dlg.selected = manager.GetTorrentsFromPlaylist(playlist)
        else:
            dlg.selected = []

        selected_infohashes = [data.infohash for data in dlg.selected]
        dlg.available = [data for data in available if data.infohash not in selected_infohashes]
        dlg.not_in_playlist = [data for data in not_in_playlist]
        dlg.filtered_available = None

        selected_names = [torrent.name for torrent in dlg.selected]
        available_names = [torrent.name for torrent in dlg.available]

        dlg.selectedList = wx.ListBox(dlg, choices=selected_names, style=wx.LB_MULTIPLE)
        dlg.selectedList.SetMinSize((1, -1))

        dlg.availableList = wx.ListBox(dlg, choices=available_names, style=wx.LB_MULTIPLE)
        dlg.availableList.SetMinSize((1, -1))

        sizer = wx.FlexGridSizer(2, 3, 3, 3)
        sizer.AddGrowableRow(1)
        sizer.AddGrowableCol(0, 1)
        sizer.AddGrowableCol(2, 1)

        selectedText = wx.StaticText(dlg, -1, "Selected torrents")
        _set_font(selectedText, size_increment=1, fontweight=wx.FONTWEIGHT_BOLD)
        sizer.Add(selectedText, 0, wx.ALIGN_CENTER_VERTICAL)
        sizer.AddSpacer(1)

        availableText = wx.StaticText(dlg, -1, "Available torrents")
        _set_font(availableText, size_increment=1, fontweight=wx.FONTWEIGHT_BOLD)

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(availableText, 1, wx.ALIGN_CENTER_VERTICAL)

        dlg.filter = wx.SearchCtrl(dlg)
        dlg.filter.SetDescriptiveText('Search within torrents')
        dlg.filter.Bind(wx.EVT_TEXT, self.OnKey)
        dlg.filter.SetMinSize((175, -1))
        hSizer.Add(dlg.filter)
        sizer.Add(hSizer, 1, wx.EXPAND)

        sizer.Add(dlg.selectedList, 1, wx.EXPAND)

        vSizer = wx.BoxSizer(wx.VERTICAL)

        add = wx.Button(dlg, -1, "<<", style=wx.BU_EXACTFIT)
        add.SetToolTipString("Add selected torrents to playlist")
        add.Bind(wx.EVT_BUTTON, self.OnAdd)
        vSizer.Add(add)

        if self.canDelete:
            remove = wx.Button(dlg, -1, ">>", style=wx.BU_EXACTFIT)
            remove.SetToolTipString("Remove selected torrents from playlist")
            remove.Bind(wx.EVT_BUTTON, self.OnRemove)
            vSizer.Add(remove)

        sizer.Add(vSizer, 0, wx.ALIGN_CENTER_VERTICAL)

        sizer.Add(dlg.availableList, 1, wx.EXPAND)
        sizer.AddSpacer((1, 1))
        sizer.AddSpacer((1, 1))

        self.all = wx.RadioButton(dlg, -1, "Show all available torrents", style=wx.RB_GROUP)
        self.all.Bind(wx.EVT_RADIOBUTTON, self.OnRadio)
        self.all.dlg = dlg
        self.playlist = wx.RadioButton(dlg, -1, "Show torrents not yet present in a playlist")
        self.playlist.Bind(wx.EVT_RADIOBUTTON, self.OnRadio)
        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.Add(self.all)
        vSizer.Add(self.playlist)
        sizer.Add(vSizer)

        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.Add(sizer, 1, wx.TOP | wx.LEFT | wx.RIGHT | wx.EXPAND, 10)
        vSizer.AddSpacer((1, 3))
        vSizer.Add(dlg.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL), 0, wx.EXPAND | wx.BOTTOM | wx.LEFT | wx.RIGHT, 10)

        dlg.SetSizer(vSizer)

        if dlg.ShowModal() == wx.ID_OK:
            return_val = [data.infohash for data in dlg.selected]
        else:
            return_val = None

        dlg.Destroy()
        return return_val

    def OnKey(self, event):
        dlg = event.GetEventObject().GetParent()
        self._filterAvailable(dlg)

    def OnRemove(self, event):
        dlg = event.GetEventObject().GetParent()
        selected = dlg.selectedList.GetSelections()

        to_be_removed = []
        for i in selected:
            to_be_removed.append(dlg.selected[i])

        dlg.available.extend(to_be_removed)
        dlg.not_in_playlist.extend(to_be_removed)
        for item in to_be_removed:
            dlg.selected.remove(item)

        self._rebuildLists(dlg)

    def OnRadio(self, event):
        dlg = self.all.dlg
        self._filterAvailable(dlg)

    def OnAdd(self, event):
        dlg = event.GetEventObject().GetParent()
        selected = dlg.availableList.GetSelections()

        to_be_removed = []
        for i in selected:
            if dlg.filtered_available:
                to_be_removed.append(dlg.filtered_available[i])
            elif self.all.GetValue():
                to_be_removed.append(dlg.available[i])
            else:
                to_be_removed.append(dlg.not_in_playlist[i])

        dlg.selected.extend(to_be_removed)
        for item in to_be_removed:
            if self.all.GetValue():
                dlg.available.remove(item)
            else:
                dlg.not_in_playlist.remove(item)

        self._rebuildLists(dlg)

    def _filterAvailable(self, dlg):
        keyword = dlg.filter.GetValue().strip().lower()
        try:
            re.compile(keyword)
        except:  # regex incorrect
            keyword = ''

        if len(keyword) > 0:
            def match(item):
                return re.search(keyword, item.name.lower())

            if self.all.GetValue():
                filtered_contents = filter(match, dlg.available)
            else:
                filtered_contents = filter(match, dlg.not_in_playlist)
            dlg.filtered_available = filtered_contents

        elif self.all.GetValue():
            filtered_contents = dlg.available
            dlg.filtered_available = None
        else:
            filtered_contents = dlg.not_in_playlist
            dlg.filtered_available = None

        names = [torrent.name for torrent in filtered_contents]
        dlg.availableList.SetItems(names)

    def _rebuildLists(self, dlg):
        names = [torrent.name for torrent in dlg.selected]
        dlg.selectedList.SetItems(names)
        self._filterAvailable(dlg)


class CommentManager(BaseManager):

    def __init__(self, list):
        BaseManager.__init__(self, list)

        self.channelsearch_manager = GUIUtility.getInstance().channelsearch_manager

        self.Reset()

    def Reset(self):
        BaseManager.Reset(self)

        self.channel = None
        self.playlist = None
        self.channeltorrent = None

    def SetIds(self, channel, playlist=None, channeltorrent=None):
        changed = False

        if channel:
            self.channel = channel
            if self.list.header:
                self.list.header.SetTitle('Comments for this channel')

            if channel:
                self.list.EnableCommeting(channel.isSemiOpen())
            else:
                self.list.EnableCommeting(False)

            changed = True

        if playlist:
            self.playlist = playlist
            if self.list.header:
                self.list.header.SetTitle('Comments for this playlist')

            changed = True

        elif channeltorrent:
            assert isinstance(channeltorrent, ChannelTorrent) or (
                isinstance(channeltorrent, CollectedTorrent) and isinstance(channeltorrent.torrent, ChannelTorrent)), type(channeltorrent)
            self.channeltorrent = channeltorrent
            if self.list.header:
                self.list.header.SetTitle('Comments for this torrent')

            changed = True

        if changed:
            self.do_or_schedule_refresh()

    def refresh(self):
        channel = self.channel
        if self.playlist:
            channel = self.playlist.channel
        elif self.channeltorrent:
            channel = self.channeltorrent.channel

        def db_callback():
            self.list.dirty = False

            if self.playlist:
                return self.channelsearch_manager.getCommentsFromPlayList(self.playlist)
            if self.channeltorrent:
                return self.channelsearch_manager.getCommentsFromChannelTorrent(self.channeltorrent)
            return self.channelsearch_manager.getCommentsFromChannel(self.channel)

        if channel.isFavorite() or channel.isMyChannel():
            startWorker(self.list.SetDelayedData, db_callback, retryOnBusy=True, priority=GUI_PRI_DISPERSY)
        else:
            self.list.ShowPreview()
            self.list.dirty = False

    def new_comment(self):
        self.do_or_schedule_refresh()

    def addComment(self, comment):
        item = self.list.GetExpandedItem()
        if item:
            _, replycomment = item.original_data
            reply_to = replycomment.dispersy_id
        else:
            reply_to = None

        reply_after = None
        items = self.list.GetItems().values()
        if len(items) > 0:
            _, prevcomment = items[-1].original_data
            reply_after = prevcomment.dispersy_id

        def db_callback():
            if self.playlist:
                self.channelsearch_manager.createComment(
                    comment,
                    self.channel,
                    reply_to,
                    reply_after,
                    playlist=self.playlist)
            elif self.channeltorrent:
                self.channelsearch_manager.createComment(
                    comment,
                    self.channel,
                    reply_to,
                    reply_after,
                    infohash=self.channeltorrent.infohash)
            else:
                self.channelsearch_manager.createComment(comment, self.channel, reply_to, reply_after)
        startWorker(None, workerFn=db_callback, retryOnBusy=True, priority=GUI_PRI_DISPERSY)

    def removeComment(self, comment):
        self.channelsearch_manager.removeComment(comment, self.channel)


class CommentList(List):

    def __init__(self, parent, parent_list, canReply=False, quickPost=False, horizontal=False, noheader=False):
        if quickPost:
            self.quickPost = self.OnThankYou
        else:
            self.quickPost = None
        self.horizontal = horizontal
        self.noheader = noheader

        List.__init__(self, [], LIST_GREY, [10, 10], parent=parent, singleSelect=True, borders=False)
        self.parent_list = parent_list
        self.canReply = canReply

    def _PostInit(self):
        self.header = self.CreateHeader(self.parent) if not self.noheader else None
        if self.header:
            self.Add(self.header, 0, wx.EXPAND)

        self.list = self.CreateList(self.parent)
        self.footer = self.CreateFooter(self.parent)

        if self.horizontal:
            listSizer = wx.BoxSizer(wx.HORIZONTAL)

            listSizer.Add(self.footer, 0, wx.EXPAND)
            listSizer.Add(self.list, 1, wx.EXPAND)

            self.Add(listSizer, 1, wx.EXPAND)

        else:
            self.Add(self.list, 1, wx.EXPAND)
            self.Add(self.footer, 0, wx.EXPAND)

        self.SetBackgroundColour(self.background)
        self.Layout()

        self.list.Bind(wx.EVT_SIZE, self.OnSize)

    def CreateHeader(self, parent):
        return TitleHeader(parent, self, [], 0, radius=0, spacers=[10, 10])

    def CreateFooter(self, parent):
        return CommentFooter(parent, self.OnNew, self.quickPost, self.horizontal)

    def GetManager(self):
        if getattr(self, 'manager', None) is None:
            self.manager = CommentManager(self)
        return self.manager

    @forceWxThread
    def SetData(self, data):
        List.SetData(self, data)

        listData = []

        def addComments(comment, depth):
            listData.append((comment.id, [], (depth, comment), CommentItem))
            for reply in comment.replies:
                addComments(reply, depth + 1)

        for comment in data:
            addComments(comment, 0)

        if len(listData) > 0:
            self.list.SetData(listData)
        else:
            self.list.ShowMessage('No comments are found.')
            self.SetNrResults(0)

    def ShowPreview(self):
        altControl = None
        if isinstance(self.parent_list, SelectedChannelList):
            def create_button(parentPanel):
                hSizer = wx.BoxSizer(wx.HORIZONTAL)
                hSizer.AddStretchSpacer()

                button = wx.Button(parentPanel, -1, 'Mark as Favorite')
                button.Bind(wx.EVT_BUTTON, self.parent_list.OnFavorite)
                hSizer.Add(button, 0, wx.TOP, 3)
                hSizer.AddStretchSpacer()
                return hSizer

            altControl = create_button
        self.list.ShowMessage(
            'You have to mark this channel as a Favorite to start receiving comments.',
            'No comments received yet',
            altControl)

    def EnableCommeting(self, enable=True):
        self.footer.EnableCommeting(enable)

    def OnExpand(self, item):
        if self.canReply:
            self.footer.SetReply(True)
        return True

    def OnCollapse(self, item, panel, from_expand):
        List.OnCollapse(self, item, panel, from_expand)
        self.footer.SetReply(False)

    def OnNew(self, event):
        comment = self.footer.GetComment()
        self.GetManager().addComment(comment)

        self.footer.SetComment('')

    def OnThankYou(self, event):
        self.GetManager().addComment(u'Thanks for uploading')
        self.footer.SetComment('')

    def OnShowTorrent(self, torrent):
        self.parent_list.Select(torrent)

    def OnRemoveComment(self, comment):
        self.GetManager().removeComment(comment)


class ActivityManager(BaseManager):

    def __init__(self, list):
        BaseManager.__init__(self, list)

        self.channelsearch_manager = GUIUtility.getInstance().channelsearch_manager
        self.Reset()

    def Reset(self):
        BaseManager.Reset(self)

        self.channel = None
        self.playlist = None
        self.channeltorrent = None

    def SetIds(self, channel, playlist=None):
        if channel:
            self.channel = channel
            self.list.dirty = True

            self.list.header.SetTitle('Recent activity in this Channel')

        if playlist:
            self.playlist = playlist
            self.list.dirty = True

            self.list.header.SetTitle('Recent activity in this Playlist')

    def refresh(self):
        def db_callback():
            self.list.dirty = False

            if self.playlist:
                commentList = self.channelsearch_manager.getCommentsFromPlayList(self.playlist, limit=10)
                nrTorrents, _, torrentList = self.channelsearch_manager.getTorrentsFromPlaylist(self.playlist, limit=10)
                nrRecentTorrents, _, recentTorrentList = self.channelsearch_manager.getRecentTorrentsFromPlaylist(
                    self.playlist, limit=10)
                recentModifications = self.channelsearch_manager.getRecentModificationsFromPlaylist(
                    self.playlist, limit=10)
                recentModerations = self.channelsearch_manager.getRecentModerationsFromPlaylist(self.playlist, limit=10)
                recent_markings = self.channelsearch_manager.getRecentMarkingsFromPlaylist(self.playlist, limit=10)
            else:
                commentList = self.channelsearch_manager.getCommentsFromChannel(self.channel, limit=10)
                nrTorrents, _, torrentList = self.channelsearch_manager.getTorrentsFromChannel(self.channel, limit=10)
                nrRecentTorrents, _, recentTorrentList = self.channelsearch_manager.getRecentReceivedTorrentsFromChannel(
                    self.channel, limit=10)
                recentModifications = self.channelsearch_manager.getRecentModificationsFromChannel(
                    self.channel, limit=10)
                recentModerations = self.channelsearch_manager.getRecentModerationsFromChannel(self.channel, limit=10)
                recent_markings = self.channelsearch_manager.getRecentMarkingsFromChannel(self.channel, limit=10)

            return torrentList, recentTorrentList, commentList, recentModifications, recentModerations, recent_markings

        def do_gui(delayedResult):
            torrentList, recentTorrentList, commentList, recentModifications, recentModerations, recent_markings = delayedResult.get(
            )

            self.channelsearch_manager.populateWithPlaylists(torrentList)
            self.channelsearch_manager.populateWithPlaylists(recentTorrentList)
            self.list.SetData(
                commentList,
                torrentList,
                recentTorrentList,
                recentModifications,
                recentModerations,
                recent_markings)

        if self.channel.isFavorite() or self.channel.isMyChannel():
            startWorker(do_gui, db_callback, retryOnBusy=True, priority=GUI_PRI_DISPERSY)
        else:
            self.list.ShowPreview()
            self.list.dirty = False

    def new_activity(self):
        self.do_or_schedule_refresh()


class ActivityList(List):

    def __init__(self, parent, parent_list):
        List.__init__(self, [], LIST_GREY, [10, 10], parent=parent, singleSelect=True, borders=False)
        self.parent_list = parent_list
        self.channelsearch_manager = GUIUtility.getInstance().channelsearch_manager

    def CreateHeader(self, parent):
        return TitleHeader(parent, self, [], 0, radius=0, spacers=[10, 10])

    def CreateFooter(self, parent):
        return None

    def GetManager(self):
        if getattr(self, 'manager', None) is None:
            self.manager = ActivityManager(self)
        return self.manager

    @forceWxThread
    def SetData(
        self,
        comments,
     recent_torrents,
     recent_received_torrents,
     recent_modifications,
     recent_moderations,
     recent_markings):
        List.SetData(self, recent_torrents)

        # remove duplicates
        recent_torrent_infohashes = set([torrent.infohash for torrent in recent_torrents])
        recent_received_torrents = [
            torrent for torrent in recent_received_torrents if torrent.infohash not in recent_torrent_infohashes]

        # first element must be timestamp, allows for easy sorting
        data = [(comment.inserted, ("COMMENT_%d" % comment.id, (), (0, comment), CommentActivityItem))
                for comment in comments]
        data += [(torrent.inserted, (torrent.infohash, (), torrent, NewTorrentActivityItem))
                 for torrent in recent_torrents]
        data += [(torrent.inserted, (torrent.infohash, (), torrent, TorrentActivityItem))
                 for torrent in recent_received_torrents]
        data += [(modification.inserted, ("MODIFICATION_%d" % modification.id, (), modification, ModificationActivityItem))
                 for modification in recent_modifications if modification.name != "swift-url"]
        data += [(moderation.inserted, ("MODERATION_%d" % moderation.id, (), moderation, ModerationActivityItem))
                 for moderation in recent_moderations]
        data += [(marking.time_stamp, (marking.dispersy_id, (), marking, MarkingActivityItem))
                 for marking in recent_markings]
        data.sort(reverse=True)

        # removing timestamp
        data = [item for _, item in data]
        if len(data) > 0:
            self.list.SetData(data)
        else:
            self.list.ShowMessage('No recent activity is found.')

    @forceWxThread
    def ShowPreview(self):
        altControl = None
        if isinstance(self.parent_list, SelectedChannelList):
            def create_button(parentPanel):
                hSizer = wx.BoxSizer(wx.HORIZONTAL)
                hSizer.AddStretchSpacer()

                button = wx.Button(parentPanel, -1, 'Mark as Favorite')
                button.Bind(wx.EVT_BUTTON, self.parent_list.OnFavorite)
                hSizer.Add(button, 0, wx.TOP, 3)
                hSizer.AddStretchSpacer()
                return hSizer

            altControl = create_button
        self.list.ShowMessage(
            'You have to mark this channel as a Favorite to start seeing activity.',
            'No activity received yet',
            altControl)

    def OnShowTorrent(self, torrent):
        self.parent_list.Select(torrent)


class ModificationManager(BaseManager):

    def __init__(self, list):
        BaseManager.__init__(self, list)

        self.channelsearch_manager = GUIUtility.getInstance().channelsearch_manager
        self.Reset()

    def Reset(self):
        self.torrent = None

    def SetIds(self, channeltorrent):
        if channeltorrent != self.torrent:
            self.torrent = channeltorrent
            self.do_or_schedule_refresh()

    def refresh(self):
        def db_callback():
            self.list.dirty = False
            return self.channelsearch_manager.getTorrentModifications(self.torrent)

        if self.torrent.channel.isFavorite() or self.torrent.channel.isMyChannel():
            startWorker(self.list.SetDelayedData, db_callback, retryOnBusy=True, priority=GUI_PRI_DISPERSY)
        else:
            self.list.ShowPreview()
            self.list.dirty = False

    def new_modification(self):
        self.do_or_schedule_refresh()

    def OnRevertModification(self, modification, reason, warning=False):
        severity = 1 if warning else 0
        self.channelsearch_manager.revertModification(self.torrent.channel, modification, reason, severity, None)


class ModificationList(List):

    def __init__(self, parent, canModify=True):
        List.__init__(self, [], LIST_GREY, [7, 7], parent=parent, singleSelect=True, borders=False)
        self.canModify = canModify

    def CreateHeader(self, parent):
        return None

    def CreateFooter(self, parent):
        return None

    def GetManager(self):
        if getattr(self, 'manager', None) is None:
            self.manager = ModificationManager(self)
        return self.manager

    @forceWxThread
    def SetData(self, data):
        List.SetData(self, data)
        data = [(modification.id, (), modification, ModificationItem) for modification in data]

        if len(data) > 0:
            self.list.SetData(data)
        else:
            self.list.ShowMessage('No modifications are found.')
            self.SetNrResults(0)

    @forceWxThread
    def ShowPreview(self):
        self.list.ShowMessage(
            'You have to mark this channel as a Favorite to start seeing modifications.',
            'No modifications received yet')

    def OnRevertModification(self, modification):
        dlg = wx.Dialog(None, -1,
            'Revert this modification',
            size=(700, 400),
            style=wx.RESIZE_BORDER | wx.DEFAULT_DIALOG_STYLE)
        dlg.SetBackgroundColour(DEFAULT_BACKGROUND)
        vSizer = wx.BoxSizer(wx.VERTICAL)

        vSizer.Add(
            ModificationItem(dlg, dlg, '', '', modification,
                             list_selected=DEFAULT_BACKGROUND),
            0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 7)
        dlg.OnExpand = lambda a: False
        dlg.OnChange = vSizer.Layout

        why = BetterText(dlg, -1, 'Why do you want to revert this modification?')
        _set_font(why, fontweight=wx.FONTWEIGHT_BOLD)
        ori_why_colour = why.GetForegroundColour()
        vSizer.Add(why, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 7)

        reason = wx.TextCtrl(dlg, -1, style=wx.TE_MULTILINE)
        reason.SetMinSize((-1, 50))
        vSizer.Add(reason, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 7)

        def canClose(event):
            givenReason = reason.GetValue().strip()
            if givenReason == '':
                why.SetForegroundColour(wx.RED)
                wx.CallLater(500, why.SetForegroundColour, ori_why_colour)
            else:
                button = event.GetEventObject()
                dlg.EndModal(button.GetId())

        buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
        cancel = wx.Button(dlg, wx.ID_CANCEL, '')
        buttonSizer.Add(cancel)

        revertAndWarn = wx.Button(dlg, -1, 'Revent and Warn')
        revertAndWarn.Bind(wx.EVT_BUTTON, canClose)
        buttonSizer.Add(revertAndWarn)

        revert = wx.Button(dlg, -1, 'Revert')
        revert.Bind(wx.EVT_BUTTON, canClose)
        buttonSizer.Add(revert)

        vSizer.AddStretchSpacer()
        vSizer.Add(buttonSizer, 0, wx.ALIGN_RIGHT | wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.TOP, 7)

        dlg.SetSizer(vSizer)
        id = dlg.ShowModal()
        if id == revertAndWarn.GetId():
            self.GetManager().OnRevertModification(modification, reason.GetValue(), warning=True)
        elif id == revert.GetId():
            self.GetManager().OnRevertModification(modification, reason.GetValue())

        dlg.Destroy()


class ModerationManager(BaseManager):

    def __init__(self, list):
        BaseManager.__init__(self, list)

        self.channelsearch_manager = GUIUtility.getInstance().channelsearch_manager
        self.Reset()

    def Reset(self):
        self.channel = None
        self.playlist = None
        self.channeltorrent = None

    def SetIds(self, channel=None, playlist=None):
        changed = False
        if channel:
            self.channel = channel
            self.list.header.SetTitle('Recent moderations for this Channel')

            changed = True

        if playlist:
            self.playlist = playlist
            self.list.header.SetTitle('Recent moderations for this Playlist')

            changed = True

        if changed:
            self.do_or_schedule_refresh()

    def refresh(self):
        def db_callback():
            self.list.dirty = False
            if self.playlist:
                return self.channelsearch_manager.getRecentModerationsFromPlaylist(self.playlist, 25)
            return self.channelsearch_manager.getRecentModerationsFromChannel(self.channel, 25)

        if self.channel.isFavorite() or self.channel.isMyChannel():
            startWorker(self.list.SetDelayedData, db_callback, retryOnBusy=True, priority=GUI_PRI_DISPERSY)
        else:
            self.list.ShowPreview()
            self.list.dirty = False

    def new_moderation(self):
        self.do_or_schedule_refresh()


class ModerationList(List):

    def __init__(self, parent, parent_list):
        List.__init__(self, [], LIST_GREY, [10, 10], parent=parent, singleSelect=True, borders=False)
        self.parent_list = parent_list

    def CreateHeader(self, parent):
        return TitleHeader(parent, self, [], 0, radius=0, spacers=[10, 10])

    def CreateFooter(self, parent):
        return None

    def GetManager(self):
        if getattr(self, 'manager', None) is None:
            self.manager = ModerationManager(self)
        return self.manager

    @forceWxThread
    def SetData(self, data):
        List.SetData(self, data)
        data = [(moderation.id, (), moderation, ModerationItem) for moderation in data]

        if len(data) > 0:
            self.list.SetData(data)
        else:
            self.list.ShowMessage(
                'No moderations are found.\nModerations are modifications which are reverted by another peer.')
            self.SetNrResults(0)

    @forceWxThread
    def ShowPreview(self):
        altControl = None
        if isinstance(self.parent_list, SelectedChannelList):
            def create_button(parentPanel):
                hSizer = wx.BoxSizer(wx.HORIZONTAL)
                hSizer.AddStretchSpacer()

                button = wx.Button(self.list.messagePanel, -1, 'Mark as Favorite')
                button.Bind(wx.EVT_BUTTON, self.parent_list.OnFavorite)
                hSizer.Add(button, 0, wx.TOP, 3)
                hSizer.AddStretchSpacer()
                return hSizer

            altControl = create_button
        self.list.ShowMessage(
            'You have to mark this channel as a Favorite to start seeing moderations.',
            'No moderations received yet',
            altControl)

    def OnShowTorrent(self, torrent):
        self.parent_list.Select(torrent)
