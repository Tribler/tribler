# Written by Niels Zeilemaker
import wx

from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.tribler_topButton import _set_font
from Tribler.Core.API import *

from list import *
from list_footer import *
from list_header import *
from list_body import *
from list_details import *
from __init__ import *
from Tribler.Main.Utility.GuiDBHandler import startWorker

DEBUG = False

class ChannelManager():
    def __init__(self, list):
        self.list = list
        self.list.SetId(0)
        self.dirtyset = set()
        
        self.guiutility = GUIUtility.getInstance()
        self.channelsearch_manager = self.guiutility.channelsearch_manager
        self.library_manager = self.guiutility.library_manager
        
        self.my_channel_id = self.channelsearch_manager.channelcast_db._channel_id
    
    def Reset(self):
        self.dirtyset.clear()
    
    def refreshDirty(self):
        if 'COMPLETE_REFRESH' in self.dirtyset:
            self._refresh_list()
        else:
            self._refresh_partial(self.dirtyset)
        self.dirtyset.clear()

    def refresh(self, channel = None):
        if channel:
            self.list.Reset()
            self.list.SetChannel(channel)

        self._refresh_list()
        
    def _refresh_list(self):
        if DEBUG:
            print >> sys.stderr, "SelChannelManager complete refresh"
        
        def db_callback():
            self.list.dirty = False
            
            nr_playlists, playlists = self.channelsearch_manager.getPlaylistsFromChannelId(self.list.id, PLAYLIST_REQ_COLUMNS)
            total_items, nrfiltered, torrentList  = self.channelsearch_manager.getTorrentsNotInPlaylist(self.list.id, CHANNEL_REQ_COLUMNS)
            return total_items, nrfiltered, torrentList, playlists
        
        startWorker(self._on_data, db_callback, jobID = "ChannelManager_refresh_list")
        
    def _on_data(self, delayedResult):
        total_items, nrfiltered, torrents, playlists = delayedResult.get()
        
        torrents = self.library_manager.addDownloadStates(torrents)
        total_items += len(playlists)
        
        #only show a small random selection of available content for non-favorite channels
        if not self.list.channel.isFavorite() and not self.list.my_channel:
            if len(playlists) > 3:
                playlists = sample(playlists, 3)
                
            if len(torrents) > CHANNEL_MAX_NON_FAVORITE:
                torrents = sample(torrents, CHANNEL_MAX_NON_FAVORITE)
            
            total_items = len(playlists) + len(torrents)
        
        if self.list.SetData(playlists, torrents) < total_items: #some items are filtered by quickfilter (do not update total_items)
            self.list.SetNrResults(None, nrfiltered, None, None)
        else:
            self.list.SetNrResults(total_items, nrfiltered, None, None)
        
        if DEBUG:    
            print >> sys.stderr, "SelChannelManager complete refresh done"
        
    def _refresh_partial(self, infohashes):
        for infohash in infohashes:
            startWorker(self.list.RefreshDelayedData, self.channelsearch_manager.getTorrentFromChannelId, cargs=(infohash,), wargs=(self.list.id, infohash, CHANNEL_REQ_COLUMNS))
        
    def downloadStarted(self, infohash):
        if self.list.InList(infohash):
            item = self.list.GetItem(infohash)
            
            torrent_details = item.GetExpandedPanel()
            torrent_details.ShowPanel(TorrentDetails.INCOMPLETE)

    def torrentUpdated(self, infohash):
        if self.list.InList(infohash):
            if self.list.ShouldGuiUpdate():
                self._refresh_partial((infohash))
            else:
                self.dirtyset.add(infohash)
                self.list.dirty = True
            
    def channelUpdated(self, permid):
        if self.list.id == id:
            if self.list.ShouldGuiUpdate():
                self._refresh_list()
            else:
                self.dirtyset.add('COMPLETE_REFRESH')
                self.list.dirty = True

class SelectedChannelList(GenericSearchList):
    def __init__(self):
        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility
        self.channelsearch_manager = self.guiutility.channelsearch_manager 
        self.isDispersy = False
        self.title = None
        
        columns = [{'name':'Name', 'width': wx.LIST_AUTOSIZE, 'sortAsc': True, 'icon': 'tree'}, \
                   {'name':'Date Added', 'width': 85, 'fmt': self.format_time, 'defaultSorted': True}, \
                   {'name':'Size', 'width':  '8em', 'style': wx.ALIGN_RIGHT, 'fmt': self.format_size, 'sizeCol': True}, \
                   {'type':'method', 'width': wx.LIST_AUTOSIZE_USEHEADER, 'method': self.CreateRatio, 'name':'Popularity'}, \
                   {'type':'method', 'width': -1, 'method': self.CreateDownloadButton}]
        
        GenericSearchList.__init__(self, columns, LIST_GREY, [0,0], True, borders = False, showChange = True)
        
    def _PostInit(self):
        self.uelog = UserEventLogDBHandler.getInstance()

        sizer = wx.BoxSizer(wx.VERTICAL)
        self.header = ChannelHeader(self, self, [])
        self.header.SetEvents(self.OnBack)
        sizer.Add(self.header, 0, wx.EXPAND|wx.BOTTOM, 3)
        
        self.notebook = wx.Notebook(self, style = wx.NB_LEFT|wx.NO_BORDER)
        self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.OnChange)
        
        list = wx.Panel(self.notebook)
        vSizer = wx.BoxSizer(wx.VERTICAL)
        
        self.subheader = self.CreateHeader(list)
        self.subheader.SetBackgroundColour(self.background)
        self.header.ResizeColumn = self.subheader.ResizeColumn
        vSizer.Add(self.subheader, 0, wx.EXPAND)
                
        self.list = self.CreateList(list)
        vSizer.Add(self.list, 1, wx.EXPAND)
        
        list.SetSizer(vSizer)
        self.notebook.AddPage(list, "Contents")
        
        self.commentList = CommentList(self.notebook)
        self.activityList = ActivityList(self.notebook, self)
        
        sizer.Add(self.notebook, 1, wx.EXPAND|wx.LEFT|wx.RIGHT, 1)
        
        self.footer = self.CreateFooter(self)
        sizer.Add(self.footer, 0, wx.EXPAND)
        
        self.SetBackgroundColour(self.background)
        
        self.SetSizer(sizer)
        self.Layout()
        
        self.list.Bind(wx.EVT_SIZE, self.OnSize)
        self.ready = True
        
    def CreateHeader(self, parent):
        return ListHeader(parent, self, self.columns, radius = 0)
    
    def CreateList(self, parent):
        list = GenericSearchList.CreateList(self, parent)
        return list
   
    def CreateFooter(self, parent):
        footer = ChannelFooter(parent)
        footer.SetEvents(self.OnSpam, self.OnFavorite, self.OnRemoveVote, self.OnManage)
        return footer

    def SetChannel(self, channel):
        self.channel = channel
        
        self.Freeze()

        self.SetId(channel.id)
        self.SetVote(channel.my_vote)
        self.SetTitle(channel.name, channel.description)
        
        nr_torrents = channel.nr_torrents
        if not channel.isFavorite() and not self.my_channel:
            nr_torrents = min(nr_torrents, 50)
            
        self.SetNrResults(nr_torrents)
        self.SetFF(self.guiutility.getFamilyFilter())
        self.SetDispersy(channel.isDispersy())
        
        self.Thaw()

    def SetId(self, id):
        self.id = id
        if id > 0:
            self.my_channel = self.GetManager().my_channel_id == id
        
            manager = self.commentList.GetManager()
            manager.SetIds(channel_id = id)
            
            manager = self.activityList.GetManager()
            manager.SetIds(channel_id = id)
            
    def SetVote(self, vote):
        self.footer.SetStates(vote == -1, vote == 2, self.my_channel)
        
    def SetMyChannelId(self, channel_id):
        self.GetManager().my_channel_id = channel_id
    
    def SetDispersy(self, isDispersy):
        if isDispersy:
            if self.notebook.GetPageCount() == 1:
                self.notebook.AddPage(self.commentList, "Comments")
                self.notebook.AddPage(self.activityList, "Activity")
        else:
            for i in range(1, self.notebook.GetPageCount()):
                self.notebook.RemovePage(i)
        
    def SetTitle(self, title, description):
        if title != self.title:
            self.title = title
            self.header.SetTitle("%s's channel"%title)
        
        self.header.SetStyle(description)
        self.Layout()
   
    def toggleFamilyFilter(self):
        GenericSearchList.toggleFamilyFilter(self)
        manager = self.GetManager()
        manager.refresh(self.channel)
   
    def GetManager(self):
        if getattr(self, 'manager', None) == None:
            self.manager = ChannelManager(self) 
        return self.manager
    
    def SetData(self, playlists, torrents):
        List.SetData(self, torrents)
        
        t1 = time()
        
        if len(playlists) > 0 or len(torrents) > 0:
            data = [(playlist['id'],[playlist['name'], playlist['description'], playlist['nr_torrents']], playlist, PlaylistItem) for playlist in playlists]
            data += [(torrent.infohash,[torrent.name, torrent.time_stamp, torrent.length, 0, 0], torrent) for torrent in torrents]
            
            print >> sys.stderr, "SetData took", time() - t1
            return self.list.SetData(data)
        
        message =  'No torrents or playlists found.\n'
        message += 'As this is an "open" channel, you can add your own torrents to share them with others in this channel'
        self.list.ShowMessage(message)
        return 0
    
    def SetNrResults(self, nr, nr_filtered = None, nr_channels = None, keywords = None):
        if isinstance(nr, int):
            self.total_results = nr
            
            if self.channel.isFavorite() or self.my_channel:
                header = 'Discovered'
            else:
                header = 'Previewing'
            
            if self.total_results == 1:
                self.header.SetSubTitle(header+ ' %d torrent'%self.total_results)
            else:
                if self.channel.isFavorite():
                    self.header.SetSubTitle(header+' %d torrents'%self.total_results)
                else:
                    self.header.SetSubTitle(header+' %d torrents'%self.total_results)
        
        GenericSearchList.SetNrResults(self, None, nr_filtered, nr_channels, keywords)
    
    def RefreshData(self, key, data):
        List.RefreshData(self, key, data)
        
        data = (data['infohash'],[data['name'], data['time_stamp'], data['length'], 0, 0], data)
        self.list.RefreshData(key, data)
        
        item = self.list.GetItem(key)
        panel = item.GetExpandedPanel()
        if panel:
            panel.UpdateStatus()
        
        manager = self.activityList.GetManager()
        manager.refresh()
    
    def Reset(self):
        GenericSearchList.Reset(self)
        self.SetId(0)
        self.notebook.ChangeSelection(0)
    
    def OnExpand(self, item):
        if isinstance(item, PlaylistItem):
            self.guiutility.showPlaylist(item.original_data)
            return False
        
        panel = GenericSearchList.OnExpand(self, item)
        panel.ShowChannelAd(False)
        return panel

    def OnCollapse(self, item, panel):
        if not isinstance(item, PlaylistItem):
            if panel:
                #detect changes
                changes = panel.GetChanged()
                if len(changes)>0:
                    dlg = wx.MessageDialog(self, 'Do you want to save your changes made to this torrent?', 'Save changes?', wx.YES_NO | wx.YES_DEFAULT | wx.ICON_QUESTION)
                    if dlg.ShowModal() == wx.ID_YES:
                        self.OnSaveTorrent(panel)
                    dlg.Destroy()
            GenericSearchList.OnCollapse(self, item, panel)
            
    def OnSaveTorrent(self, panel):
        changes = panel.GetChanged()
        if len(changes)>0:
            self.channelsearch_manager.modifyTorrent(self.id, panel.torrent['ChannelTorrents.id'], changes)
            panel.Saved()
            
    def OnRemoveVote(self, event):
        self.channelsearch_manager.remove_vote(self.id)
        self.SetVote(0)
    
    def OnFavorite(self, event = None):
        self.channelsearch_manager.favorite(self.id)
        self.SetVote(2)
        
        #Request all items from connected peers
        if not self.channel.isDispersy():
            channelcast = BuddyCastFactory.getInstance().channelcast_core
            channelcast.updateAChannel(self.id)
        self.uelog.addEvent(message="ChannelList: user marked a channel as favorite", type = 2)
        
    def OnSpam(self, event):
        dialog = wx.MessageDialog(None, "Are you sure you want to report %s's channel as spam?" % self.title, "Report spam", wx.ICON_QUESTION | wx.YES_NO | wx.NO_DEFAULT)
        if dialog.ShowModal() == wx.ID_YES:
            self.channelsearch_manager.spam(self.id)
            self.uelog.addEvent(message="ChannelList: user marked a channel as spam", type = 2)
            
            self.SetVote(-1)
            
        dialog.Destroy()
    
    def OnManage(self, event):
        self.guiutility.showManageChannel(self.id)
    
    def OnBack(self, event):
        self.guiutility.GoBack(self.id)
        
    def OnSize(self, event):
        diff = self.subheader.GetClientSize()[0] - self.list.GetClientSize()[0]
        self.subheader.SetSpacerRight(diff)
        self.footer.SetSpacerRight(diff)
        event.Skip()
        
    def OnChange(self, event):
        page = event.GetSelection()
        if page == 1:
            self.commentList.Show()
            self.commentList.SetFocus()
        elif page == 2:
            self.activityList.Show()
            self.activityList.SetFocus()
        event.Skip()
        
    def OnCommentCreated(self, channel_id):
        if channel_id == self.id:
            manager = self.commentList.GetManager()
            manager.refresh()
            
            manager = self.activityList.GetManager()
            manager.refresh()
            
        else: #maybe channel_id is a channeltorrent_id
            panel = self.list.GetExpandedItem()
            if panel:
                torDetails = panel.GetExpandedPanel()
                if torDetails:
                    torDetails.OnCommentCreated(channel_id)
                    
    def OnModificationCreated(self, channel_id):
        if channel_id == self.id:
            manager = self.activityList.GetManager()
            manager.refresh()
            
        else: #maybe channel_id is a channeltorrent_id
            panel = self.list.GetExpandedItem()
            if panel:
                torDetails = panel.GetExpandedPanel()
                if torDetails:
                    torDetails.OnModificationCreated(channel_id)
                    
    def OnMarkTorrent(self, infohash, type):
        self.channelsearch_manager.markTorrent(self.id, infohash, type)
        
    def Select(self, key, raise_event = True):
        GenericSearchList.Select(self, key, raise_event)
        
        self.notebook.ChangeSelection(0)
        self.ScrollToId(key)
            
    def StartDownload(self, torrent):
        states = self.footer.GetStates()
        if not states[1]:
            nrdownloaded = self.channelsearch_manager.getNrTorrentsDownloaded(self.id) + 1
            if  nrdownloaded > 1:
                wx.CallAfter(self._ShowFavoriteDialog, nrdownloaded)
        
        self.uelog.addEvent(message="Torrent: torrent download from channel", type = 2)
        self.guiutility.torrentsearch_manager.downloadTorrent(torrent)
        
    def _ShowFavoriteDialog(self, nrdownloaded):
        dial = wx.MessageDialog(self, "You downloaded %d torrents from this Channel. 'Mark as favorite' will ensure that you will always have access to newest channel content.\n\nDo you want to mark this channel as one of your favorites now?"%nrdownloaded, 'Mark as Favorite?', wx.YES_NO | wx.YES_DEFAULT | wx.ICON_QUESTION)
        if dial.ShowModal() == wx.ID_YES:
            self.OnFavorite()
            self.uelog.addEvent(message="ChannelList: user clicked yes to mark as favorite", type = 2)
        else:
            self.uelog.addEvent(message="ChannelList: user clicked no to mark as favorite", type = 2)  
        dial.Destroy()

class PlaylistManager():
    def __init__(self, list):
        self.list = list
        self.list.id = 0
        
        self.guiutility = GUIUtility.getInstance()
        self.library_manager = self.guiutility.library_manager
        self.channelsearch_manager = self.guiutility.channelsearch_manager
    
    def SetPlaylistId(self, playlist_id):
        if playlist_id != self.list.id:
            self.list.Reset()
            self.list.id = playlist_id
            self.list.SetFF(self.guiutility.getFamilyFilter())
            
            self._refresh_list()
    
    def refreshDirty(self):
        self._refresh_list()
    
    def _refresh_list(self):
        def db_call():
            self.list.dirty = False
            self.channelsearch_manager.getTorrentsFromPlaylist(self.list.id, CHANNEL_REQ_COLUMNS)
            
        startWorker(self._on_data, db_call)
        
    def _on_data(self, delayedResult):
        total_items, nrfiltered, torrents = delayedResult.get()
        torrents = self.library_manager.addDownloadStates(torrents)
        
        if self.list.SetData([], torrents) < total_items: #some items are filtered by quickfilter (do not update total_items)
            self.list.SetNrResults(None, nrfiltered, None, None)
        else:
            self.list.SetNrResults(total_items, nrfiltered, None, None)        

class Playlist(SelectedChannelList):
    def __init__(self):
        SelectedChannelList.__init__(self)
        self.vote = 2
    
    def GetManager(self):
        if getattr(self, 'manager', None) == None:
            self.manager = PlaylistManager(self) 
        return self.manager
    
    def SetTitle(self, title, description):
        self.title = title
        self.header.SetTitle(title)
        self.header.SetStyle(description)
        self.Layout()
    
    def Set(self, data):
        self.SetTitle(data['name'], data['description'])
        
        manager = self.GetManager()
        manager.SetPlaylistId(data['id'])

        manager = self.commentList.GetManager()
        manager.SetIds(channel_id = data['channel_id'], playlist_id = data['id'])
        
        manager = self.activityList.GetManager()
        manager.SetIds(channel_id = data['channel_id'], playlist_id = data['id'])
    
class PlaylistItem(ListItem):
    def __init__(self, parent, parent_list, columns, data, original_data, leftSpacer = 0, rightSpacer = 0, showChange = False, list_selected = LIST_SELECTED):
        ListItem.__init__(self, parent, parent_list, columns, data, original_data, leftSpacer, rightSpacer, showChange, list_selected)
        
    def AddComponents(self, leftSpacer, rightSpacer):
        titleRow = wx.BoxSizer(wx.HORIZONTAL)
        if leftSpacer > 0:
            titleRow.AddSpacer((leftSpacer, -1))
        
        self.icontype = 'tree'
        self.expandedState = wx.StaticBitmap(self, -1, self.GetIcon(LIST_DESELECTED, 0))
        titleRow.Add(self.expandedState, 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 3)
        
        self.title = wx.StaticText(self, -1, self.data[0], style = wx.ST_NO_AUTORESIZE|wx.ST_DOTS_END)
        self.title.SetMinSize((1, -1))
        titleRow.Add(self.title, 1, wx.RESERVE_SPACE_EVEN_IF_HIDDEN|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 3)
        self.nrTorrents = wx.StaticText(self, -1, "%d Torrents"%self.data[2], style = wx.ST_NO_AUTORESIZE|wx.ST_DOTS_END)
        titleRow.Add(self.nrTorrents, 0, wx.RESERVE_SPACE_EVEN_IF_HIDDEN|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 3)

        if rightSpacer > 0:
            titleRow.AddSpacer((rightSpacer, -1))
        self.vSizer.Add(titleRow, 0, wx.EXPAND)
        
        self.desc = wx.StaticText(self, -1, self.data[1], style = wx.ST_NO_AUTORESIZE|wx.ST_DOTS_END)
        self.desc.SetMinSize((1, -1))
        self.hSizer.AddSpacer((40, -1))
        self.hSizer.Add(self.desc, 1, wx.ALL, 3)
        self.AddEvents(self)
    
class ManageChannelFilesManager():
    def __init__(self, list):
        self.list = list
        self.list.id = 0
        self.channelsearch_manager = GUIUtility.getInstance().channelsearch_manager
    
    def refreshDirty(self):
        self._refresh()
    
    def refresh_list(self):
        if self.list.IsShownOnScreen():
            self._refresh()
        else:
            self.list.dirty = True
        
    def _refresh(self):
        def db_call():
            self.list.dirty = False
            return self.channelsearch_manager.getTorrentsFromChannelId(self.list.id, CHANNEL_REQ_COLUMNS, filterTorrents = False)
        
        startWorker(self._on_data, db_call)
        
    def _on_data(self, delayedResult):
        total_items, nrfiltered, torrentList = delayedResult.get()
        self.list.SetData(torrentList)
    
    def SetChannelId(self, channel_id):
        if channel_id !=  self.list.id:
            self.list.id = channel_id
            self.list.dirty = True
    
    def RemoveItems(self, infohashes):
        """
        for infohash in infohashes:
            self.channelsearch_manager.deleteOwnTorrent(infohash)
        self.list.Reset()
        self.refresh()
        """
        pass
        
    def RemoveAllItems(self):
        """
        self.channelsearch_manager.deleteTorrentsFromPublisherId(self.channelsearch_manager.channelcast_db.my_permid)
        self.list.Reset()
        self.refresh()
        """
        pass
        
class ManageChannelPlaylistsManager():
    
    def __init__(self, list):
        self.list = list
        self.list.id = 0
        self.channelsearch_manager = GUIUtility.getInstance().channelsearch_manager
    
    def refreshDirty(self):
        self._refresh()
        
    def refresh_list(self):
        if self.list.IsShownOnScreen():
            self._refresh()
        else:
            self.list.dirty = True 
    
    def _refresh(self):
        def db_call():
            self.list.dirty = False
            return self.channelsearch_manager.getPlaylistsFromChannelId(self.list.id, PLAYLIST_REQ_COLUMNS)
        
        startWorker(self._on_data, db_call)
        
    def _refresh_partial(self, playlist_id):
        startWorker(self.list.RefreshDelayedData, self.channelsearch_manager.getPlaylist, wargs=(playlist_id, PLAYLIST_REQ_COLUMNS), cargs = (playlist_id,))
    
    def _on_data(self, delayedResult):
        _, playlistList = delayedResult.get()
        self.list.SetData(playlistList)
    
    def SetChannelId(self, channel_id):
        if channel_id != self.list.id:
            self.list.id = channel_id
            self.list.dirty = True
    
    def GetTorrentsFromChannel(self):
        delayedResult = startWorker(None, self.channelsearch_manager.getTorrentsFromChannelId, wargs = (self.list.id, CHANNEL_REQ_COLUMNS), wkwargs = {'filterTorrents' : False})
        total_items, nrfiltered, torrentList = delayedResult.get()
        return torrentList
        
    def GetTorrentsFromPlaylist(self, playlist_id):
        delayedResult = startWorker(None, self.channelsearch_manager.getTorrentsFromPlaylist, wargs = (playlist_id, CHANNEL_REQ_COLUMNS), wkwargs = {'filterTorrents' : False})
        total_items, nrfiltered, torrentList = delayedResult.get()
        return torrentList
    
    def createPlaylist(self, name, description, infohashes):
        startWorker(None, self.channelsearch_manager.createPlaylist, wargs = (self.list.id, name, description, infohashes))
    
    def savePlaylist(self, playlist_id, name, description):
        startWorker(None, self.channelsearch_manager.modifyPlaylist, wargs = (self.list.id, playlist_id, name, description))
    
    def savePlaylistTorrents(self, playlist_id, infohashes):
        startWorker(None, self.channelsearch_manager.savePlaylistTorrents, wargs = (self.list.id, playlist_id, infohashes))
    
    def playlistUpdated(self, playlist_id):
        if self.list.InList(playlist_id):
            startWorker(self.list.RefreshDelayedData, self.channelsearch_manager.getPlaylist, wargs = (playlist_id, PLAYLIST_REQ_COLUMNS), cargs = (playlist_id, ))

class ManageChannel(XRCPanel, AbstractDetails):

    def _PostInit(self):
        self.channel_id = 0
        self.guiutility = GUIUtility.getInstance()
        self.uelog = UserEventLogDBHandler.getInstance()
        self.torrentfeed = TorrentFeedThread.getInstance()
        self.channelsearch_manager = self.guiutility.channelsearch_manager
        
        self.SetBackgroundColour(LIST_BLUE)
        boxSizer = wx.BoxSizer(wx.VERTICAL)
        
        self.header = ManageChannelHeader(self, self)
        self.header.SetBackgroundColour(LIST_BLUE)
        self.header.SetEvents(self.OnBack)
        boxSizer.Add(self.header, 0, wx.EXPAND)
        
        self.notebook = wx.Notebook(self, style = wx.NB_NOPAGETHEME)
        self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.OnChange)
        
        #overview page intro
        overviewpage = wx.Panel(self.notebook)
        overviewpage.SetBackgroundColour(LIST_DESELECTED)
        
        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.AddSpacer((-1, 10))
        header =  "Welcome to the management interface for this channel. You can access this because you have the rights to modify it."
        self._add_header(overviewpage, vSizer, header, spacer = 10)
        
        text  = "Channels can be used to spread torrents to other Tribler users. "
        text += "If a channel provides other Tribler users with original or popular content, then they might mark your channel as one of their favorites. "
        text += "This will help to promote your channel, because the number of users which have marked a channel as one of their favorites is used to calculate popularity. "
        text += "Additionally, when another Tribler user marks your channel as a favorite they help you distribute all the .torrent files.\n\n"
        text += "Currently three options exist to spread torrents. "
        text += "Two of them, periodically importing .torrents from an rss feed and manually adding .torrent files, are available from the 'Manage' tab.\n"
        text += "The third option is available from the torrentview after completely downloading a torrent and allows you to add a torrent to your channel with a single click."
        
        overviewtext = wx.StaticText(overviewpage, -1, text)
        vSizer.Add(overviewtext, 0, wx.EXPAND|wx.ALL, 10)
        
        text = "Currently your channel is not created. Please fill in  a name and description and click the create button to start spreading your torrents."
        self.createText = wx.StaticText(overviewpage, -1, text)
        self.createText.Hide()
        vSizer.Add(self.createText, 0, wx.EXPAND|wx.ALL, 10)
        
        gridSizer = wx.FlexGridSizer(0, 2, 3, 3)
        gridSizer.AddGrowableCol(1)
        gridSizer.AddGrowableRow(1)
        
        self.name = wx.TextCtrl(overviewpage)
        self.name.SetMaxLength(40)
        
        self.description = wx.TextCtrl(overviewpage, style = wx.TE_MULTILINE)
        self.description.SetMaxLength(2000)
        
        self._add_row(overviewpage, gridSizer, "Name", self.name)
        self._add_row(overviewpage, gridSizer, 'Description', self.description)
        vSizer.Add(gridSizer, 0, wx.EXPAND|wx.RIGHT, 10)
        
        self.saveButton = wx.Button(overviewpage, -1, 'Save Changes')
        self.saveButton.Bind(wx.EVT_BUTTON, self.Save)
        vSizer.Add(self.saveButton, 0, wx.ALIGN_RIGHT|wx.ALL, 10)
        
        overviewpage.SetSizer(vSizer)
        self.notebook.AddPage(overviewpage, "Overview")
        
        #shared files page
        self.fileslist = ManageChannelFilesList(self.notebook)
        self.fileslist.SetNrResults = self.header.SetNrTorrents
        
        #playlist page
        self.playlistlist = ManageChannelPlaylistList(self.notebook)
        
        #manage page
        self.managepage = wx.Panel(self.notebook)
        self.managepage.SetBackgroundColour(LIST_DESELECTED)
        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.AddSpacer((-1, 10))
        
        #rss intro
        header =  "Rss import"
        self._add_header(self.managepage, vSizer, header, spacer = 10)
        
        text =  "Rss feeds are periodically checked for new .torrent files. \nFor each item in the rss feed a .torrent file should be present in either:\n\n"
        text += "\tThe link element\n"
        text += "\tA src attribute\n"
        text += "\tA url attribute"
        manageText = wx.StaticText(self.managepage, -1, text)
        vSizer.Add(manageText, 0, wx.EXPAND|wx.ALL, 10)
        
        #rss
        self.gridSizer = wx.FlexGridSizer(0, 2, 3)
        self.gridSizer.AddGrowableCol(1)
        self.gridSizer.AddGrowableRow(0)
        
        vSizer.Add(self.gridSizer, 1, wx.EXPAND|wx.ALL, 10)
        self.managepage.SetSizer(vSizer)
        
        boxSizer.Add(self.notebook, 1, wx.EXPAND|wx.ALL, 5)
        self.SetSizer(boxSizer)
        self.Layout()
    
    def BuildRssPanel(self, parent, sizer):
        self._add_subheader(parent, sizer, "Current rss-feeds:","(which are periodically checked)")
        
        rssSizer = wx.BoxSizer(wx.VERTICAL)
        urls = self.torrentfeed.getUrls("active")
        if len(urls) > 0:
            rssPanel = wx.lib.scrolledpanel.ScrolledPanel(parent)
            rssPanel.SetBackgroundColour(LIST_DESELECTED)
            
            urlSizer = wx.FlexGridSizer(0, 2, 0, 5)
            urlSizer.AddGrowableCol(0)
            for url in urls:
                rsstext = wx.StaticText(rssPanel, -1, url.replace('&', '&&'))
                rsstext.SetMinSize((1,-1))
                
                deleteButton = wx.Button(rssPanel, -1, "Delete")
                deleteButton.url = url
                deleteButton.text = rsstext
                deleteButton.Bind(wx.EVT_BUTTON, self.OnDeleteRss)
                
                urlSizer.Add(rsstext, 1, wx.EXPAND|wx.ALIGN_CENTER_VERTICAL)
                urlSizer.Add(deleteButton, 0, wx.ALIGN_RIGHT)
            
            rssPanel.SetMinSize((-1, 50))
            rssPanel.SetSizer(urlSizer)
            rssPanel.SetupScrolling(rate_y = 5)
            rssSizer.Add(rssPanel, 1, wx.EXPAND)
            
            refresh = wx.Button(parent, -1, "Refresh all rss-feeds")
            refresh.Bind(wx.EVT_BUTTON, self.OnRefreshRss)
            rssSizer.Add(refresh, 0, wx.ALIGN_RIGHT | wx.TOP, 3)
        else:
            rssSizer.Add(wx.StaticText(parent, -1, "No rss feeds are being monitored."))
            
        #add-rss
        rssSizer.Add(wx.StaticText(parent, -1, "Add an rss-feed:"), 0, wx.TOP, 3)
        addSizer = wx.BoxSizer(wx.HORIZONTAL)
        url = wx.TextCtrl(parent)
        addButton = wx.Button(parent, -1, "Add")
        addButton.url = url
        addButton.Bind(wx.EVT_BUTTON, self.OnAddRss)
        addSizer.Add(url, 1 , wx.ALIGN_CENTER_VERTICAL)
        addSizer.Add(addButton, 0, wx.LEFT|wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_RIGHT, 5)
        rssSizer.Add(addSizer, 0, wx.EXPAND, 10)
        sizer.Add(rssSizer, 1, wx.EXPAND|wx.LEFT|wx.TOP|wx.BOTTOM, 10)
        
        #manual
        self._add_subheader(parent, sizer, "Manually import a .torrent file:","(downloaded from another source)")
        browseButton = wx.Button(parent, -1, "Browse for .torrent files")
        browseButton.Bind(wx.EVT_BUTTON, self.OnManualAdd)
        browseButton2 = wx.Button(parent, -1, "Browse for a directory")
        browseButton2.Bind(wx.EVT_BUTTON, self.OnManualDirAdd)
        
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(browseButton)
        hSizer.Add(browseButton2, 0, wx.LEFT, 5)
        sizer.Add(hSizer, 0, wx.ALIGN_RIGHT|wx.LEFT|wx.TOP, 10)
    
    def RebuildRssPanel(self):
        self.gridSizer.ShowItems(False)
        self.gridSizer.Clear()
        
        self.BuildRssPanel(self.managepage, self.gridSizer)
        self.managepage.Layout()
    
    def SetChannelId(self, channel_id):
        self.channel_id = channel_id
        self.fileslist.GetManager().SetChannelId(channel_id)
        self.playlistlist.GetManager().SetChannelId(channel_id)
        
        if channel_id:
            def update_panel(delayedResult):
                data = delayedResult.get() 
                
                name = data.name
                self.name.SetValue(name)
                self.name.originalValue = name

                description = data.description
                self.description.SetValue(description)
                self.description.originalValue = description
                
                self.header.SetName('Management interface for %s\'s Channel'%name)
                self.header.SetNrTorrents(data.nr_torrents, data.nr_favorites)
                
                if self.notebook.GetPageCount() == 1:
                    self.notebook.AddPage(self.fileslist, "Manage torrents")
                    self.notebook.AddPage(self.playlistlist, "Manage playlists")
                    self.notebook.AddPage(self.managepage, "Manage")
                    
                    self.createText.Hide()
                    self.saveButton.SetLabel('Save Changes')
                    
            startWorker(update_panel, self.channelsearch_manager.getChannel, wargs = (channel_id, ))
        else:
            self.name.SetValue('')
            self.name.originalValue = ''
            
            self.description.SetValue('')
            self.description.originalValue = ''
            
            self.header.SetName('Create your own channel')
            self.header.SetNrTorrents(0, 0)
            
            #disable all other tabs
            for i in range(1, self.notebook.GetPageCount()):
                self.notebook.RemovePage(i)
                
            self.createText.Show()
            self.saveButton.SetLabel('Create Channel')
        self.RebuildRssPanel()
        
    def SetMyChannelId(self, channel_id):
        if not self.channel_id:
            self.SetChannelId(channel_id)
    
    def IsChanged(self):
        return self.name.GetValue() != self.name.originalValue or self.description.GetValue() != self.description.originalValue
    
    def OnChange(self, event):
        page = event.GetSelection()
        if page == 1:
            self.fileslist.Show()
            self.fileslist.SetFocus()
        
        elif page == 2:
            self.playlistlist.Show()
            self.playlistlist.SetFocus() 
        event.Skip()
    
    def OnBack(self, event):
        self.guiutility.GoBack()
    
    def OnAddRss(self, event):
        item = event.GetEventObject()
        url = item.url.GetValue().strip()
        if len(url) > 0:
            self.torrentfeed.addURL(url)
            self.RebuildRssPanel()
            
            self.uelog.addEvent(message="MyChannel: rssfeed added", type = 2)
        
    def OnDeleteRss(self, event):
        item = event.GetEventObject()
        
        self.torrentfeed.deleteURL(item.url)
        self.RebuildRssPanel()
        
        self.uelog.addEvent(message="MyChannel: rssfeed removed", type = 2)
    
    def OnRefreshRss(self, event):
        self.torrentfeed.refresh()
        
        button = event.GetEventObject()
        button.Enable(False)
        wx.CallLater(5000, button.Enable, True)
        
        self.uelog.addEvent(message="MyChannel: rssfeed refreshed", type = 2)
        
    def OnManualAdd(self, event):
        dlg = wx.FileDialog(self,"Choose .torrent file", wildcard = "BitTorrent file (*.torrent) |*.torrent", style = wx.DEFAULT_DIALOG_STYLE|wx.FD_MULTIPLE)
        
        path = DefaultDownloadStartupConfig.getInstance().get_dest_dir() + os.sep
        dlg.SetPath(path)
        if dlg.ShowModal() == wx.ID_OK:
            files = dlg.GetPaths()
            self._import_torrents(files)
            
            self.uelog.addEvent(message="MyChannel: manual import files", type = 2)
            
    def OnManualDirAdd(self, event):
        dlg = wx.DirDialog(self,"Choose a directory containing the .torrent files", style = wx.wx.DD_DIR_MUST_EXIST)
        
        path = DefaultDownloadStartupConfig.getInstance().get_dest_dir() + os.sep
        dlg.SetPath(path)
        
        if dlg.ShowModal() == wx.ID_OK and os.path.isdir(dlg.GetPath()):
            full_files = []
            files = os.listdir(dlg.GetPath())
            for file in files:
                full_files.append(os.path.join(dlg.GetPath(), file))
            self._import_torrents(full_files)
            
            self.uelog.addEvent(message="MyChannel: manual import directory", type = 2)
    
    def _import_torrents(self, files):
        nr_imported = 0
        for file in files:
            if file.endswith(".torrent"):
                self.torrentfeed.addFile(file)
                nr_imported += 1
        
        if nr_imported > 0:
            if nr_imported == 1:
                self.guiutility.frame.top_bg.Notify('New torrent added to My Channel', wx.ART_INFORMATION)
            else:
                self.guiutility.frame.top_bg.Notify('Added %d torrents to your Channel'%nr_imported, wx.ART_INFORMATION)
    
    def OnRssItem(self, rss_url, infohash, torrent_data):
        manager = self.fileslist.GetManager()
        manager.refresh_list()
    
    def Show(self, show=True):
        if not show:
            if self.IsChanged():
                dlg = wx.MessageDialog(self, 'Do you want to save your changes made to this channel?', 'Save changes?', wx.YES_NO | wx.YES_DEFAULT | wx.ICON_QUESTION)
                if dlg.ShowModal() == wx.ID_YES:
                    self.Save()
            
        XRCPanel.Show(self, show)
    
    def Save(self, event = None):
        name = self.name.GetValue()
        description = self.description.GetValue()
        
        if self.channel_id:
            self.channelsearch_manager.modifyChannel(self.channel_id, name, description)
        else:
            self.channelsearch_manager.createChannel(name, description)
        
        self.name.originalValue = name
        self.description.originalValue = description
    
    def playlistCreated(self, channel_id):
        if channel_id == self.channel_id:
            manager = self.playlistlist.GetManager()
            manager.refresh_list()
        
    def playlistUpdated(self, playlist_id):
        manager = self.playlistlist.GetManager()
        manager.playlistUpdated(playlist_id)
        
    def channelUpdated(self, channel_id):
        if channel_id == self.channel_id:
            manager = self.fileslist.GetManager()
            manager.refresh_list()
            
class ManageChannelFilesList(List):
    def __init__(self, parent):
        columns = [{'name':'Name', 'width': wx.LIST_AUTOSIZE, 'icon': 'checkbox', 'sortAsc': True}, \
                   {'name':'Date Added', 'width': 85, 'fmt': self.format_time, 'defaultSorted': True}]
   
        List.__init__(self, columns, LIST_BLUE, [0,0], parent = parent, borders = False)
    
    def CreateHeader(self, parent):
        return ListHeader(parent, self, self.columns, 0)
    
    def CreateFooter(self, parent):
        return ManageChannelFilesFooter(parent, self.OnRemoveAll, self.OnRemoveSelected)
    
    def GetManager(self):
        if getattr(self, 'manager', None) == None:
            self.manager = ManageChannelFilesManager(self) 
        return self.manager
    
    def SetData(self, data):
        List.SetData(self, data)
        
        data = [(torrent.infohash,[torrent.name,torrent.time_stamp], torrent) for torrent in data]
        nr_results = 0
        if len(data) > 0:
            nr_results = self.list.SetData(data)
        else:
            self.list.ShowMessage('You are currently not sharing any torrents in your channel.')
        self.SetNrResults(nr_results)
        
    def OnExpand(self, item):
        return MyChannelDetails(item, item.original_data, self.id)
    
    def OnRemoveAll(self, event):
        dlg = wx.MessageDialog(self, 'Are you sure you want to remove all torrents from your channel?', 'Remove torrents', wx.ICON_QUESTION | wx.YES_NO | wx.NO_DEFAULT)
        if dlg.ShowModal() == wx.ID_YES:
            self.manager.RemoveAllItems()
        dlg.Destroy()
    
    def OnRemoveSelected(self, event):
        dlg = wx.MessageDialog(self, 'Are you sure you want to remove all selected torrents from your channel?', 'Remove torrents', wx.ICON_QUESTION | wx.YES_NO | wx.NO_DEFAULT)
        if dlg.ShowModal() == wx.ID_YES:
            infohashes = [key for key,item in self.list.GetExpandedItems()]
            self.manager.RemoveItems(infohashes)
        dlg.Destroy()
        
class ManageChannelPlaylistList(ManageChannelFilesList):
    def __init__(self, parent):
        columns = [{'name':'Name', 'width': wx.LIST_AUTOSIZE, 'icon': 'checkbox', 'sortAsc': True}]
        
        List.__init__(self, columns, LIST_BLUE, [0,0], parent = parent, borders = False)
    
    def CreateFooter(self, parent):
        return ManageChannelPlaylistFooter(parent, self.OnNew)
    
    def GetManager(self):
        if getattr(self, 'manager', None) == None:
            self.manager = ManageChannelPlaylistsManager(self) 
        return self.manager
    
    def RefreshData(self, key, data):
        data = (data['id'], [data['name']], data)
        self.list.RefreshData(key, data)
    
    def SetData(self, data):
        List.SetData(self, data)
        
        data = [(playlist['id'],[playlist['name']], playlist) for playlist in data]
        
        nr_results = 0
        if len(data) > 0:
            nr_results = self.list.SetData(data)
        else:
            self.list.ShowMessage('You currently do not have any playlists in your channel.')
        self.SetNrResults(nr_results)
    
    def OnExpand(self, item):
        return MyChannelPlaylist(item, self.OnEdit, item.original_data)

    def OnCollapse(self, item, panel):
        playlist_id = item.original_data.get('id', False)
        if playlist_id:
            if panel.IsChanged():
                dlg = wx.MessageDialog(self, 'Do you want to save your changes made to this playlist?', 'Save changes?', wx.YES_NO | wx.YES_DEFAULT | wx.ICON_QUESTION)
                if dlg.ShowModal() == wx.ID_YES:
                    name, description, _ = panel.GetInfo()
                    
                    manager = self.GetManager()
                    manager.savePlaylist(playlist_id, name, description)
        ManageChannelFilesList.OnCollapse(self, item, panel)
    
    def OnNew(self, event):
        vSizer = wx.BoxSizer(wx.VERTICAL)
        
        dlg = wx.Dialog(self, -1, 'Create a new playlist', size = (500, 300), style = wx.RESIZE_BORDER|wx.DEFAULT_DIALOG_STYLE)
        playlistdetails = MyChannelPlaylist(dlg, self.OnManage)
        
        vSizer.Add(playlistdetails, 1, wx.EXPAND|wx.ALL, 3)
        vSizer.Add(dlg.CreateSeparatedButtonSizer(wx.OK|wx.CANCEL), 0, wx.EXPAND|wx.ALL, 3)
        
        dlg.SetSizer(vSizer)
        if dlg.ShowModal() == wx.ID_OK:
            name, description, infohashes = playlistdetails.GetInfo()
            
            manager = self.GetManager()
            manager.createPlaylist(name, description, infohashes)
        dlg.Destroy()
    
    def OnEdit(self, playlist):
        torrent_ids = self.OnManage(playlist)
        if torrent_ids:
            manager = self.GetManager()
            manager.savePlaylistTorrents(playlist['id'], torrent_ids)
    
    def OnManage(self, playlist):
        dlg = wx.Dialog(self, -1, 'Manage the torrents for this playlist', size = (900, 500), style = wx.RESIZE_BORDER|wx.DEFAULT_DIALOG_STYLE)
        
        manager = self.GetManager()
        
        available = manager.GetTorrentsFromChannel()
        if playlist.get('id', False):
            dlg.selected = manager.GetTorrentsFromPlaylist(playlist['id'])
        else:
            dlg.selected = []
            
        selected_infohashes = [data['infohash'] for data in dlg.selected]
        selected_names = [data['name'] for data in dlg.selected]
        
        dlg.available = [data for data in available if data['infohash'] not in selected_infohashes]
        available_names = [data['name'] for data in dlg.available]
        
        dlg.selectedList = wx.ListBox(dlg, choices = selected_names, style = wx.LB_MULTIPLE)
        dlg.selectedList.SetMinSize((1,-1))
        
        dlg.availableList = wx.ListBox(dlg, choices = available_names, style = wx.LB_MULTIPLE)
        dlg.availableList.SetMinSize((1,-1))
        
        sizer = wx.FlexGridSizer(2,3,3,3)
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
        dlg.filter.SetMinSize((175,-1))
        hSizer.Add(dlg.filter)
        sizer.Add(hSizer, 1, wx.EXPAND)
        
        sizer.Add(dlg.selectedList, 1, wx.EXPAND)
        
        remove = wx.Button(dlg, -1, ">>", style = wx.BU_EXACTFIT)
        remove.SetToolTipString("Remove selected torrents from playlist")
        remove.Bind(wx.EVT_BUTTON, self.OnRemove)
        
        add = wx.Button(dlg, -1, "<<", style = wx.BU_EXACTFIT)
        add.SetToolTipString("Add selected torrents to playlist")
        add.Bind(wx.EVT_BUTTON, self.OnAdd)
        
        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.Add(remove)
        vSizer.Add(add)
        sizer.Add(vSizer, 0, wx.ALIGN_CENTER_VERTICAL)
        
        sizer.Add(dlg.availableList, 1, wx.EXPAND)
        
        sizer.AddSpacer(1)
        sizer.AddSpacer(1)
        sizer.Add(dlg.CreateSeparatedButtonSizer(wx.OK|wx.CANCEL), 0, wx.EXPAND|wx.ALL, 3)
        dlg.SetSizer(sizer)
        
        if dlg.ShowModal() == wx.ID_OK:
            return_val = [data['infohash'] for data in dlg.selected]
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
        for item in to_be_removed:
            dlg.selected.remove(item)
        
        self._rebuildLists(dlg)
    
    def OnAdd(self, event):
        dlg = event.GetEventObject().GetParent()
        selected = dlg.availableList.GetSelections()

        to_be_removed = []
        for i in selected:
            to_be_removed.append(dlg.available[i])
            
        dlg.selected.extend(to_be_removed)
        for item in to_be_removed:
            dlg.available.remove(item)
        
        self._rebuildLists(dlg)
    
    def _filterAvailable(self, dlg):
        keyword = dlg.filter.GetValue().strip().lower()
        try:
            re.compile(keyword)
        except: #regex incorrect
            keyword = ''
        
        if len(keyword) > 0:
            def match(item):
                return re.search(keyword, item['name'].lower())
            filtered_contents = filter(match, dlg.available)
        else:
            filtered_contents = dlg.available
             
        names = [data['name'] for data in filtered_contents]
        dlg.availableList.SetItems(names)
    
    def _rebuildLists(self, dlg):
        selected_names = [data['name'] for data in dlg.selected]
        dlg.selectedList.SetItems(selected_names)
        
        self._filterAvailable(dlg)

class CommentManager:
    def __init__(self, list):
        self.list = list
        self.list.id = 0
        
        self.channel_id = None
        self.playlist_id = None
        self.channeltorrent_id = None
        self.channelsearch_manager = GUIUtility.getInstance().channelsearch_manager
    
    def SetIds(self, channel_id = None, playlist_id = None, channeltorrent_id = None):
        if channel_id != self.channel_id:
            self.channel_id = channel_id
            self.list.dirty = True
            
            self.list.header.SetTitle('Comments for this channel')
        
        if playlist_id != self.playlist_id:
            self.playlist_id = playlist_id
            self.list.dirty = True
            
            self.list.header.SetTitle('Comments for this playlist')
            
        elif channeltorrent_id != self.channeltorrent_id:
            self.channeltorrent_id = channeltorrent_id
            self.list.dirty = True
            
            self.list.header.SetTitle('Comments for this torrent')
    
    def refreshDirty(self):
        self.refresh()
    
    def refresh(self):
        def db_callback():
            self.list.dirty = False
            
            if self.playlist_id:
                return self.channelsearch_manager.getCommentsFromPlayListId(self.playlist_id, COMMENT_REQ_COLUMNS)
            elif self.channeltorrent_id:
                return self.channelsearch_manager.getCommentsFromChannelTorrentId(self.channeltorrent_id, COMMENT_REQ_COLUMNS)
            else:
                return self.channelsearch_manager.getCommentsFromChannelId(self.channel_id, COMMENT_REQ_COLUMNS)
        
        startWorker(self.list.SetDelayedData, db_callback)    
       
    def getNrComments(self):
        def db_callback():
            if self.playlist_id:
                return len(self.channelsearch_manager.getCommentsFromPlayListId(self.playlist_id, COMMENT_REQ_COLUMNS))
            elif self.channeltorrent_id:
                return len(self.channelsearch_manager.getCommentsFromChannelTorrentId(self.channeltorrent_id, COMMENT_REQ_COLUMNS))
            else:
                return len(self.channelsearch_manager.getCommentsFromChannelId(self.channel_id, COMMENT_REQ_COLUMNS))
        
        total_items = startWorker(None, db_callback, jobID = "getNrComments")
        total_items = total_items.get()
        return total_items
        
    def addComment(self, comment):
        reply_after = None
        
        items = self.list.GetItems().values()
        if len(items) > 0:
            reply_after = items[-1].original_data['dispersy_id']
        
        def db_callback():
            if self.playlist_id:
                self.channelsearch_manager.createComment(comment, self.channel_id, reply_after, playlist_id = self.playlist_id)
            elif self.channeltorrent_id:
                self.channelsearch_manager.createComment(comment, self.channel_id, reply_after, channeltorrent_id = self.channeltorrent_id)
            else:
                self.channelsearch_manager.createComment(comment, self.channel_id, reply_after)
        startWorker(None, db_callback)

class CommentList(List):
    def __init__(self, parent, canReply = False, quickPost = False):
        if quickPost:
            self.quickPost = self.OnThankYou
        else:
            self.quickPost = None
            
        List.__init__(self, [], LIST_GREY, [7,7], parent = parent, singleSelect = True, borders = False)
        self.canReply = canReply
    
    def CreateHeader(self, parent):
        return TitleHeader(self, parent, [], 0, radius = 0)
    
    def CreateFooter(self, parent):
        return CommentFooter(parent, self.OnNew, self.quickPost)

    def GetManager(self):
        if getattr(self, 'manager', None) == None:
            self.manager = CommentManager(self) 
        return self.manager
    
    def SetData(self, data):
        List.SetData(self, data)
        
        data = [(comment.id,[comment.name, comment.comment, self.format_time(comment.time_stamp)], comment, CommentItem) for comment in data]
        nr_results = 0
        if len(data) > 0:
            nr_results = self.list.SetData(data)
        else:
            self.list.ShowMessage('No comments are found.')
        self.SetNrResults(nr_results)
    
    def OnExpand(self, item):
        if self.canReply:
            self.footer.SetReply(True)
        return True
    
    def OnCollapse(self, item, panel):
        List.OnCollapse(self, item, panel)
        self.footer.SetReply(False)

    def OnNew(self, event):
        comment = self.footer.GetComment()
        self.GetManager().addComment(comment)
        
        self.footer.SetComment('')
        
    def OnThankYou(self, event):
        self.GetManager().addComment(u'Thanks for uploading')
        self.footer.SetComment('')

class CommentItem(ListItem):
    def __init__(self, parent, parent_list, columns, data, original_data, leftSpacer = 0, rightSpacer = 0, showChange = False, list_selected = LIST_SELECTED):
        ListItem.__init__(self, parent, parent_list, columns, data, original_data, leftSpacer, rightSpacer, showChange, list_selected)
        
    def AddComponents(self, leftSpacer, rightSpacer):
        titleRow = wx.BoxSizer(wx.HORIZONTAL)
        if leftSpacer > 0:
            titleRow.AddSpacer((leftSpacer, -1))
        
        title = "Posted %s by %s"%(self.data[2].lower(), self.original_data.name)
        if self.original_data.get('torrent_name'):
            title += ' in %s'%self.original_data.torrent_name
        elif self.original_data.get('playlist_name'):
            title += ' in %s'%self.original_data.playlist_name
        
        title = wx.StaticText(self, -1, title)
        titleRow.Add(title)

        if rightSpacer > 0:
            titleRow.AddSpacer((rightSpacer, -1))
        self.vSizer.Add(titleRow, 0, wx.EXPAND)
        self.desc = wx.StaticText(self, -1, self.data[1], style = wx.ST_NO_AUTORESIZE|wx.ST_DOTS_END)
        self.desc.SetMinSize((1, -1))
        self.hSizer.AddSpacer((40, -1))
        self.hSizer.Add(self.desc, 1, wx.ALL, 3)
        self.AddEvents(self)

class ActivityManager:
    def __init__(self, list):
        self.list = list
        self.list.id = 0
        
        self.channel_id = None
        self.playlist_id = None
        self.channelsearch_manager = GUIUtility.getInstance().channelsearch_manager
        
    def SetIds(self, channel_id = None, playlist_id = None):
        if channel_id != self.channel_id:
            self.channel_id = channel_id
            self.list.dirty = True
            
            self.list.header.SetTitle('Recent activity in this Channel')
        
        if playlist_id != self.playlist_id:
            self.playlist_id = playlist_id
            self.list.dirty = True
            
            self.list.header.SetTitle('Recent activity in this Playlist')
    
    def refreshDirty(self):
        self.refresh()
    
    def refresh(self):
        def db_callback():
            self.list.dirty = False
            
            if self.playlist_id:
                commentList = self.channelsearch_manager.getCommentsFromPlayListId(self.playlist_id, COMMENT_REQ_COLUMNS, limit = 10)
                nrTorrents, _, torrentList = self.channelsearch_manager.getTorrentsFromPlaylist(self.playlist_id, CHANNEL_REQ_COLUMNS, limit = 10)
                nrRecentTorrents, _, recentTorrentList = self.channelsearch_manager.getRecentTorrentsFromPlaylist(self.playlist_id, CHANNEL_REQ_COLUMNS, limit = 10)
                recentModifications = self.channelsearch_manager.getRecentTorrentsFromPlaylist(self.playlist_id, MODIFICATION_REQ_COLUMNS  + ['inserted'], limit = 10)
            else:
                commentList = self.channelsearch_manager.getCommentsFromChannelId(self.channel_id, COMMENT_REQ_COLUMNS, limit = 10)
                nrTorrents, _, torrentList = self.channelsearch_manager.getTorrentsFromChannelId(self.channel_id, CHANNEL_REQ_COLUMNS, limit = 10)
                nrRecentTorrents, _, recentTorrentList = self.channelsearch_manager.getRecentTorrentsFromChannelId(self.channel_id, CHANNEL_REQ_COLUMNS, limit = 10)
                recentModifications = self.channelsearch_manager.getRecentModificationsFromChannelId(self.channel_id, MODIFICATION_REQ_COLUMNS + ['inserted'], limit = 10)
                
            return commentList, torrentList, recentTorrentList, recentModifications
        startWorker(self._on_data, db_callback)
        
    def _on_data(self, delayedResult):
        commentList, torrentList, recentTorrentList, recentModifications = delayedResult.get()
        self.list.SetData(commentList, torrentList, recentTorrentList, recentModifications)

class ActivityList(List):
    def __init__(self, parent, parent_list):
        List.__init__(self, [], LIST_GREY, [7,7], parent = parent, singleSelect = True, borders = False)
        self.parent_list = parent_list
        self.channelsearch_manager = GUIUtility.getInstance().channelsearch_manager
    
    def CreateHeader(self, parent):
        return TitleHeader(self, parent, [], 0, radius = 0)
    
    def CreateFooter(self, parent):
        return None

    def GetManager(self):
        if getattr(self, 'manager', None) == None:
            self.manager = ActivityManager(self) 
        return self.manager
    
    def SetData(self, comments, torrents, recent_torrents, recent_modifications):
        List.SetData(self, torrents)
        def genCommentActivity(comment):
            return "new comment received", self.format_time(comment.time_stamp), comment.name + "  " + comment.comment
        
        def genNewTorrentActivity(torrent):
            return "new torrent received", self.format_time(torrent.time_stamp), torrent.name
    
        def genTorrentActivity(torrent):
            return "discovered a torrent", self.format_time(torrent.inserted), torrent.name
    
        def genModificationActivity(modification):
            return "discovered a modification", self.format_time(modification.inserted), "modified %s in '%s'"%(modification.name, modification.value)
        
        #first element must be timestamp, allows for easy sorting 
        data =  [(comment.time_stamp, (comment.id, genCommentActivity(comment), comment, ActivityItem)) for comment in comments]
        data += [(file.time_stamp, (file.infohash, genNewTorrentActivity(file), file, ActivityItem)) for file in torrents]
        data += [(file.inserted, (file.infohash, genTorrentActivity(file), file, ActivityItem)) for file in recent_torrents]
        data += [(modification.inserted, (modification.id, genModificationActivity(modification), modification, ActivityItem)) for modification in recent_modifications]
        data.sort(reverse = True)
        
        #removing timestamp
        data = [item for _, item in data]
        if len(data) > 0:
            return self.list.SetData(data)
        self.list.ShowMessage('No recent activity is found.')
        return 0
    
    def OnExpand(self, item):
        if 'infohash' in item.original_data: #is this a torrent?
            self.parent_list.Select(item.original_data.infohash)
    
class ActivityItem(ListItem):
    def __init__(self, parent, parent_list, columns, data, original_data, leftSpacer = 0, rightSpacer = 0, showChange = False, list_selected = LIST_SELECTED):
        ListItem.__init__(self, parent, parent_list, columns, data, original_data, leftSpacer, rightSpacer, showChange, list_selected)
        
    def AddComponents(self, leftSpacer, rightSpacer):
        titleRow = wx.BoxSizer(wx.HORIZONTAL)
        if leftSpacer > 0:
            titleRow.AddSpacer((leftSpacer, -1))
        
        titleRow.Add(wx.StaticText(self, -1, self.data[1] + " : " +self.data[0].capitalize()))

        if rightSpacer > 0:
            titleRow.AddSpacer((rightSpacer, -1))
        self.vSizer.Add(titleRow, 0, wx.EXPAND|wx.TOP, 3)
        self.hSizer.AddSpacer((40, -1))
        self.hSizer.Add(wx.StaticText(self, -1, self.data[2]), 0, wx.BOTTOM, 3)
        self.AddEvents(self)

class ModificationManager:
    def __init__(self, list):
        self.list = list
        self.list.id = 0
        
        self.channeltorrent_id = None
        self.channelsearch_manager = GUIUtility.getInstance().channelsearch_manager
        
    def SetId(self, channeltorrent_id):
        if channeltorrent_id != self.channeltorrent_id:
            self.channeltorrent_id = channeltorrent_id
            self.list.dirty = True
    
    def refreshDirty(self):
        self.refresh()
    
    def refresh(self):
        def db_callback():
            self.list.dirty = False
            return self.channelsearch_manager.getTorrentModifications(self.channeltorrent_id)
        
        startWorker(self.list.SetDelayedData, db_callback)
        
    def getNrModifications(self):
        data = startWorker(None, self.channelsearch_manager.getTorrentModifications, wargs= (self.channeltorrent_id, ))
        return len(data.get())  

class ModificationList(List):
    def __init__(self, parent):
        List.__init__(self, [], LIST_GREY, [7,7], parent = parent, singleSelect = True, borders = False)
        self.header.SetTitle('Modifications of this torrent')
    
    def CreateHeader(self, parent):
        return TitleHeader(self, parent, [], 0, radius = 0)
    
    def CreateFooter(self, parent):
        return None

    def GetManager(self):
        if getattr(self, 'manager', None) == None:
            self.manager = ModificationManager(self) 
        return self.manager
    
    def SetData(self, data):
        List.SetData(self, data)
        data = [(modification.id, [modification.name, modification.value, self.format_time(modification.inserted)], modification, ModificationItem) for modification in data]
        
        nr_results = 0
        if len(data) > 0:
            nr_results = self.list.SetData(data)
        else:
            self.list.ShowMessage('No modifications are found.')
        self.SetNrResults(nr_results)
    
class ModificationItem(ListItem):
    def __init__(self, parent, parent_list, columns, data, original_data, leftSpacer = 0, rightSpacer = 0, showChange = False, list_selected = LIST_SELECTED):
        ListItem.__init__(self, parent, parent_list, columns, data, original_data, leftSpacer, rightSpacer, showChange, list_selected)
        
    def AddComponents(self, leftSpacer, rightSpacer):
        titleRow = wx.BoxSizer(wx.HORIZONTAL)
        if leftSpacer > 0:
            titleRow.AddSpacer((leftSpacer, -1))
        
        titleRow.Add(wx.StaticText(self, -1, "Modified %s in '%s'"%(self.data[0], self.data[1])))

        if rightSpacer > 0:
            titleRow.AddSpacer((rightSpacer, -1))
        self.vSizer.Add(titleRow, 0, wx.EXPAND|wx.TOP, 3)
        self.hSizer.AddSpacer((40, -1))
        self.hSizer.Add(wx.StaticText(self, -1, self.data[2]), 0, wx.BOTTOM, 3)
        self.AddEvents(self)