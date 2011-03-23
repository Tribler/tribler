# Written by Niels Zeilemaker
import wx
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Core.API import *

from list import *
from list_footer import *
from list_header import *
from list_body import *
from list_details import *
from __init__ import *

class ChannelManager():
    def __init__(self, list):
        self.list = list
        self.list.SetId(0)
        
        self.guiutility = GUIUtility.getInstance()
        self.channelsearch_manager = self.guiutility.channelsearch_manager
        self.torrentsearch_manager = self.guiutility.torrentsearch_manager
        
        self.channel_id = self.channelsearch_manager.channelcast_db._channel_id
        
    def refresh(self, id = None):
        if id:
            self.list.Reset()
            self.list.SetId(id)
            
            data = self.channelsearch_manager.getChannel(id)
            
            self.list.footer.SetStates(data[CHANNEL_MY_VOTE] == -1, data[CHANNEL_MY_VOTE] == 2, id == self._channel_id)
            self.list.SetFF(self.guiutility.getFamilyFilter())
            self.list.SetTitle(data[CHANNEL_NAME], data[CHANNEL_DESCRIPTION])
            self.list.SetDispersy(data[CHANNEL_IS_DISPERSY])
            
        self._refresh_list()
        
    def _refresh_list(self):
        #TODO: should we filter out children?
        nr_playlists, playlists = self.channelsearch_manager.getPlaylistsFromChannelId(self.list.id, PLAYLIST_REQ_COLUMNS)
        total_items, nrfiltered, torrents  = self.channelsearch_manager.getTorrentsNotInPlaylist(self.list.id, CHANNEL_REQ_COLUMNS)
        torrents = self.torrentsearch_manager.addDownloadStates(torrents)
        
        if self.list.SetData(playlists, torrents) < total_items: #some items are filtered by quickfilter (do not update total_items)
            self.list.SetNrResults(None, nrfiltered, None, None)
        else:
            self.list.SetNrResults(total_items, nrfiltered, None, None)
    
    def downloadStarted(self, infohash):
        if self.list.InList(infohash):
            item = self.list.GetItem(infohash)
            
            torrent_details = item.GetExpandedPanel()
            torrent_details.ShowPanel(TorrentDetails.INCOMPLETE)

    def torrentUpdated(self, infohash):
        if self.list.InList(infohash):
            data = self.channelsearch_manager.getTorrentFromChannelId(self.list.id, infohash, CHANNEL_REQ_COLUMNS)
            self.list.RefreshData(infohash, data)
            
    def channelUpdated(self, permid):
        if self.list.id == permid:
            self._refresh_list()

class SelectedChannelList(SearchList):
    def __init__(self):
        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility
        self.channelsearch_manager = self.guiutility.channelsearch_manager 
        self.isDispersy = False
        
        columns = [{'name':'Name', 'width': wx.LIST_AUTOSIZE, 'sortAsc': True, 'icon': 'tree'}, \
                   {'name':'Date Added', 'width': 85, 'fmt': self.format_time, 'defaultSorted': True}, \
                   {'name':'Size', 'width':  '8em', 'style': wx.ALIGN_RIGHT, 'fmt': self.format_size, 'sizeCol': True}, \
                   {'type':'method', 'width': wx.LIST_AUTOSIZE_USEHEADER, 'method': self.CreateRatio, 'name':'Popularity'}, \
                   {'type':'method', 'width': -1, 'method': self.CreateDownloadButton}]
        
        List.__init__(self, columns, LIST_GREY, [0,0], True, borders = False)
        
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
        list = SearchList.CreateList(self, parent)
        return list
   
    def CreateFooter(self, parent):
        footer = ChannelFooter(parent)
        footer.SetEvents(self.OnSpam, self.OnFavorite, self.OnRemoveVote, self.OnManage)
        return footer

    def SetId(self, id):
        self.id = id
        
        manager = self.commentList.GetManager()
        manager.SetIds(channel_id = id)
        
        manager = self.activityList.GetManager()
        manager.SetIds(channel_id = id)
        
    def SetDispersy(self, isDispersy):
        if isDispersy:
            if self.notebook.GetPageCount() == 1:
                self.notebook.AddPage(self.commentList, "Comments")
                self.notebook.AddPage(self.activityList, "Activity")
        else:
            for i in range(1, self.notebook.GetPageCount()):
                self.notebook.RemovePage(i)
        self.isDispersy = isDispersy
        
    def SetTitle(self, title, description):
        self.title = title
        self.header.SetTitle("%s's channel"%title)
        self.header.SetStyle(description)
        self.Layout()
   
    def toggleFamilyFilter(self):
        self.guiutility.toggleFamilyFilter()
        self.guiutility.showChannel(self.title, self.id)
   
    def GetManager(self):
        if getattr(self, 'manager', None) == None:
            self.manager = ChannelManager(self) 
        return self.manager
    
    def SetData(self, playlists, torrents):
        List.SetData(self, torrents)
        
        if len(playlists) > 0 or len(torrents) > 0:
            data = [(playlist['id'],[playlist['name'], playlist['description'], playlist['nr_torrents']], playlist, PlaylistItem) for playlist in playlists]
            data += [(file['infohash'],[file['name'], file['time_stamp'], file['length'], 0, 0], file) for file in torrents]
            return self.list.SetData(data)
        
        message =  'No torrents or playlists found.\n'
        message += 'As this is an "open" channel, you can add your own torrents to share them with others in this channel'
        self.list.ShowMessage(message)
        return 0
    
    def SetNrResults(self, nr, nr_filtered, nr_channels, keywords):
        if isinstance(nr, int):
            self.total_results = nr
            if self.total_results == 1:
                self.header.SetSubTitle('Discovered %d torrent'%self.total_results)
            else:
                self.header.SetSubTitle('Discovered %d torrents'%self.total_results)
        
        SearchList.SetNrResults(self, None, nr_filtered, nr_channels, keywords)
    
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
        SearchList.Reset(self)
        self.SetId(0)
        self.notebook.ChangeSelection(0)
    
    def OnExpand(self, item):
        if isinstance(item, PlaylistItem):
            self.guiutility.showPlaylist(item.original_data)
            return False
        
        panel = SearchList.OnExpand(self, item)
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
                        self.channelsearch_manager.modifyTorrent(self.id, item.original_data['ChannelTorrents.id'], changes)
            SearchList.OnCollapse(self, item, panel)
        
    def OnRemoveVote(self, event):
        self.channelsearch_manager.remove_vote(self.id)
        self.footer.SetStates(False, False)
    
    def OnFavorite(self, event = None):
        self.channelsearch_manager.favorite(self.id)
        self.footer.SetStates(False, True)
        
        #Request all items from connected peers
        if not self.isDispersy:
            channelcast = BuddyCastFactory.getInstance().channelcast_core
            channelcast.updateAChannel(self.id)
        self.uelog.addEvent(message="ChannelList: user marked a channel as favorite", type = 2)
        
    def OnSpam(self, event):
        dialog = wx.MessageDialog(None, "Are you sure you want to report %s's channel as spam?" % self.title, "Report spam", wx.ICON_QUESTION | wx.YES_NO | wx.NO_DEFAULT)
        if dialog.ShowModal() == wx.ID_YES:
            self.channelsearch_manager.spam(self.id)
            self.footer.SetStates(True, False)
            self.uelog.addEvent(message="ChannelList: user marked a channel as spam", type = 2)
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
        
    def Select(self, key, raise_event = True):
        SearchList.Select(self, key, raise_event)
        
        self.notebook.ChangeSelection(0)
        self.ScrollToId(key)
            
    def StartDownload(self, torrent):
        states = self.footer.GetStates()
        if not states[1]:
            nrdownloaded = self.channelsearch_manager.getNrTorrentsDownloaded(self.id) + 1
            if  nrdownloaded > 1:
                dial = wx.MessageDialog(self, "You downloaded %d torrents from this Channel. 'Mark as favorite' will ensure that you will always have access to newest channel content.\n\nDo you want to mark this channel as one of your favorites now?"%nrdownloaded, 'Mark as Favorite?', wx.YES_NO | wx.YES_DEFAULT | wx.ICON_QUESTION)
                if dial.ShowModal() == wx.ID_YES:
                    self.OnFavorite()
                    self.uelog.addEvent(message="ChannelList: user clicked yes to mark as favorite", type = 2)
                else:
                    self.uelog.addEvent(message="ChannelList: user clicked no to mark as favorite", type = 2)  
                dial.Destroy()
        
        self.uelog.addEvent(message="Torrent: torrent download from channel", type = 2)
        self.guiutility.torrentsearch_manager.downloadTorrent(torrent)

class PlaylistManager():
    def __init__(self, list):
        self.list = list
        self.list.id = 0
        
        self.guiutility = GUIUtility.getInstance()
        self.torrentsearch_manager = self.guiutility.torrentsearch_manager
        self.channelsearch_manager = self.guiutility.channelsearch_manager
    
    def SetPlaylistId(self, playlist_id):
        if playlist_id != self.list.id:
            self.list.Reset()
            self.list.id = playlist_id
            self.list.SetFF(self.guiutility.getFamilyFilter())
            
            self._refresh_list()
    
    def _refresh_list(self):
        #TODO: Should look for children of this playlist
        total_items, nrfiltered, torrents = self.channelsearch_manager.getTorrentsFromPlaylist(self.list.id, CHANNEL_REQ_COLUMNS)
        torrents = self.torrentsearch_manager.addDownloadStates(torrents)
        
        if self.list.SetData([], torrents) < total_items: #some items are filtered by quickfilter (do not update total_items)
            self.list.SetNrResults(None, nrfiltered, None, None)
        else:
            self.list.SetNrResults(total_items, nrfiltered, None, None)        

class Playlist(SelectedChannelList):
    def __init__(self):
        SelectedChannelList.__init__(self)
    
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
        
    def refresh(self):
        total_items, nrfiltered, torrentList = self.channelsearch_manager.getTorrentsFromChannelId(self.list.id, CHANNEL_REQ_COLUMNS, filterTorrents = False)
        self.list.SetData(torrentList)
        return total_items
    
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
        
    def refresh(self):
        total_items, playlistList = self.channelsearch_manager.getPlaylistsFromChannelId(self.list.id, PLAYLIST_REQ_COLUMNS)
        self.list.SetData(playlistList)
    
    def SetChannelId(self, channel_id):
        if channel_id != self.list.id:
            self.list.id = channel_id
            self.list.dirty = True
    
    def GetTorrentsFromChannel(self):
        total_items, nrfiltered, torrentList = self.channelsearch_manager.getTorrentsFromChannelId(self.list.id, CHANNEL_REQ_COLUMNS, filterTorrents = False)
        return torrentList
        
    def GetTorrentsFromPlaylist(self, playlist_id):
        total_items, nrfiltered, torrentList = self.channelsearch_manager.getTorrentsFromPlaylist(playlist_id, CHANNEL_REQ_COLUMNS, filterTorrents = False)
        return torrentList
    
    def createPlaylist(self, name, description, infohashes):
        self.channelsearch_manager.createPlaylist(self.list.id, name, description, infohashes)
    
    def savePlaylist(self, playlist_id, name, description):
        self.channelsearch_manager.modifyPlaylist(self.list.id, playlist_id, name, description)
    
    def savePlaylistTorrents(self, playlist_id, infohashes):
        self.channelsearch_manager.savePlaylistTorrents(self.list.id, playlist_id, infohashes)
    
    def playlistUpdated(self, playlist_id):
        if self.list.InList(playlist_id):
            data = self.channelsearch_manager.getPlaylist(playlist_id, PLAYLIST_REQ_COLUMNS)
            self.list.RefreshData(playlist_id, data)

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
            data = self.channelsearch_manager.getChannel(channel_id)
            
            name = data[CHANNEL_NAME]
            header = 'Management interface for %s\'s Channel'%name
            nr_favorites = data[CHANNEL_NR_FAVORITES]
            nr_torrents = data[CHANNEL_NR_TORRENTS_COLLECTED]
            description = data[CHANNEL_DESCRIPTION] 
            
            if self.notebook.GetPageCount() == 1:
                self.notebook.AddPage(self.fileslist, "Manage torrents")
                self.notebook.AddPage(self.playlistlist, "Manage playlists")
                self.notebook.AddPage(self.managepage, "Manage")
                
                self.createText.Hide()
                self.saveButton.SetLabel('Save Changes')
        else:
            name = ''
            header = 'Create your own channel'
            nr_favorites = 0
            nr_torrents = 0
            description = ''
            
            #disable all other tabs
            for i in range(1, self.notebook.GetPageCount()):
                self.notebook.RemovePage(i)
                
            self.createText.Show()
            self.saveButton.SetLabel('Create Channel')
            
        self.header.SetName(header)
        self.header.SetNrTorrents(nr_torrents, nr_favorites)
        self.name.SetValue(name)
        self.name.originalValue = name
        self.description.SetValue(description)
        self.description.originalValue = description
        
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
        #this is called from another non-gui thread, thus we wrap it using wx.callafter
        manager = self.fileslist.GetManager()
        wx.CallAfter(manager.refresh)
    
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
            manager.refresh()
        
    def playlistUpdated(self, playlist_id):
        manager = self.playlistlist.GetManager()
        manager.playlistUpdated(playlist_id)
        
    def channelUpdated(self, channel_id):
        if channel_id == self.channel_id:
            manager = self.fileslist.GetManager()
            
            nr_torrents = manager.refresh()
            self.header.SetNrTorrents(nr_torrents)

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
        
        data = [(file['infohash'],[file['name'],file['time_stamp']], file) for file in data]
        
        if len(data) > 0:
            return self.list.SetData(data)
        self.list.ShowMessage('You are currently not sharing any torrents in your channel.')
        return 0
    
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
        
        if len(data) > 0:
            return self.list.SetData(data)
        self.list.ShowMessage('You are currently do not have any playlists in your channel.')
        return 0
    
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
        manager = self.GetManager()
        
        dlg = wx.Dialog(self, -1, 'Manage the torrents for this playlist', size = (500, 600), style = wx.RESIZE_BORDER|wx.DEFAULT_DIALOG_STYLE)
        dlg.contents = manager.GetTorrentsFromChannel()
        dlg.torrent_infohashes = [data['infohash'] for data in dlg.contents]
        
        names = [data['name'] for data in dlg.contents]
        
        if playlist.get('id', False):
            selected = [dlg.torrent_infohashes.index(data['infohash']) for data in manager.GetTorrentsFromPlaylist(playlist['id'])]
        else:
            selected = None
        
        vSizer = wx.BoxSizer(wx.VERTICAL)
        dlg.list = wx.CheckListBox(dlg, choices = names)
        if selected:
            dlg.list.SetChecked(selected)
        
        self.filter = wx.SearchCtrl(dlg)
        self.filter.SetDescriptiveText('Search within torrents')
        self.filter.Bind(wx.EVT_TEXT, self.OnKey)
        self.filter.SetMinSize((175,-1))
        
        vSizer.Add(self.filter, 0, wx.ALIGN_RIGHT|wx.ALL, 3)
        vSizer.Add(dlg.list, 1, wx.EXPAND|wx.ALL, 3)
        vSizer.Add(dlg.CreateSeparatedButtonSizer(wx.OK|wx.CANCEL), 0, wx.EXPAND|wx.ALL, 3)
        
        dlg.SetSizer(vSizer)
        
        if dlg.ShowModal() == wx.ID_OK:
            return_val = [dlg.torrent_infohashes[index] for index in dlg.list.GetChecked()]
        else:
            return_val = None
            
        dlg.Destroy()
        return return_val
        
    def OnKey(self, event):
        dlg = self.filter.GetParent()
        sel_torrents = [dlg.torrent_infohashes[index] for index in dlg.list.GetChecked()]
        
        keyword = self.filter.GetValue().strip()
        try:
            re.compile(keyword)
        except: #regex incorrect
            keyword = ''
        
        if len(keyword) > 0:
            def match(item):
                if item['infohash'] in sel_torrents:
                    return True
                return re.search(keyword, item['name'].lower())
            filtered_contents = filter(match, dlg.contents)
        else:
            filtered_contents = dlg.contents
             
        dlg.torrent_infohashes = [data['infohash'] for data in filtered_contents]
        names = [data['name'] for data in filtered_contents]
        
        dlg.list.SetItems(names)
        selected = [dlg.torrent_infohashes.index(torrent_id) for torrent_id in sel_torrents]
        if selected:
            dlg.list.SetChecked(selected)

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
            
            self.list.header.SetTitle('Comments for this Channel')
        
        if playlist_id != self.playlist_id:
            self.playlist_id = playlist_id
            self.list.dirty = True
            
            self.list.header.SetTitle('Comments for this Playlist')
            
        elif channeltorrent_id != self.channeltorrent_id:
            self.channeltorrent_id = channeltorrent_id
            self.list.dirty = True
            
            self.list.header.SetTitle('Comments for this Torrent')
    
    def refresh(self):
        if self.playlist_id:
            total_items, commentList = self.channelsearch_manager.getCommentsFromPlayListId(self.playlist_id, COMMENT_REQ_COLUMNS)
        elif self.channeltorrent_id:
            total_items, commentList = self.channelsearch_manager.getCommentsFromChannelTorrentId(self.channeltorrent_id, COMMENT_REQ_COLUMNS)
        else:
            total_items, commentList = self.channelsearch_manager.getCommentsFromChannelId(self.channel_id, COMMENT_REQ_COLUMNS)
        self.list.SetData(commentList)
        return total_items
        
    def getNrComments(self):
        if self.playlist_id:
            total_items, commentList = self.channelsearch_manager.getCommentsFromPlayListId(self.playlist_id, COMMENT_REQ_COLUMNS)
        elif self.channeltorrent_id:
            total_items, commentList = self.channelsearch_manager.getCommentsFromChannelTorrentId(self.channeltorrent_id, COMMENT_REQ_COLUMNS)
        else:
            total_items, commentList = self.channelsearch_manager.getCommentsFromChannelId(self.channel_id, COMMENT_REQ_COLUMNS)
        return total_items
        
    def addComment(self, comment):
        reply_after = None
        
        items = self.list.GetItems().values()
        if len(items) > 0:
            reply_after = items[-1].original_data['dispersy_id']
        
        if self.playlist_id:
            self.channelsearch_manager.createComment(comment, self.channel_id, reply_after, playlist_id = self.playlist_id)
        elif self.channeltorrent_id:
            self.channelsearch_manager.createComment(comment, self.channel_id, reply_after, channeltorrent_id = self.channeltorrent_id)
        else:
            self.channelsearch_manager.createComment(comment, self.channel_id, reply_after)

class CommentList(List):
    def __init__(self, parent, canReply = False):
        List.__init__(self, [], LIST_GREY, [7,7], parent = parent, singleSelect = True, borders = False)
        
        self.canReply = canReply
    
    def CreateHeader(self, parent):
        return TitleHeader(self, parent, [], 0, radius = 0)
    
    def CreateFooter(self, parent):
        return CommentFooter(parent, self.OnNew)

    def GetManager(self):
        if getattr(self, 'manager', None) == None:
            self.manager = CommentManager(self) 
        return self.manager
    
    def SetData(self, data):
        List.SetData(self, data)
        
        data = [(comment['id'],[comment['name'], comment['comment'], self.format_time(comment['time_stamp'])], comment, CommentItem) for comment in data]
        
        if len(data) > 0:
            return self.list.SetData(data)
        self.list.ShowMessage('No comments are found.')
        return 0
    
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

class CommentItem(ListItem):
    def __init__(self, parent, parent_list, columns, data, original_data, leftSpacer = 0, rightSpacer = 0, showChange = False, list_selected = LIST_SELECTED):
        ListItem.__init__(self, parent, parent_list, columns, data, original_data, leftSpacer, rightSpacer, showChange, list_selected)
        
    def AddComponents(self, leftSpacer, rightSpacer):
        titleRow = wx.BoxSizer(wx.HORIZONTAL)
        if leftSpacer > 0:
            titleRow.AddSpacer((leftSpacer, -1))
        
        title = "Posted %s by %s"%(self.data[2].lower(), self.data[0])
        if self.original_data.get('channeltorrent_id'):
            title += ' in %s'%self.original_data['torrent_name']
        elif self.original_data.get('playlist_id'):
            title += ' in %s'%self.original_data['playlist_name']
            
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
    
    def refresh(self):
        if self.playlist_id:
            _, commentList = self.channelsearch_manager.getCommentsFromPlayListId(self.playlist_id, COMMENT_REQ_COLUMNS, limit = 10)
            _, _, torrentList = self.channelsearch_manager.getTorrentsFromPlaylist(self.playlist_id, CHANNEL_REQ_COLUMNS, limit = 10)
            _, _, recentTorrentList = self.channelsearch_manager.getRecentTorrentsFromPlaylist(self.playlist_id, CHANNEL_REQ_COLUMNS  + ['inserted'], limit = 10)
        else:
            _, commentList = self.channelsearch_manager.getCommentsFromChannelId(self.channel_id, COMMENT_REQ_COLUMNS, limit = 10)
            _, _, torrentList = self.channelsearch_manager.getTorrentsFromChannelId(self.channel_id, CHANNEL_REQ_COLUMNS, limit = 10)
            _, _, recentTorrentList = self.channelsearch_manager.getRecentTorrentsFromChannelId(self.channel_id, CHANNEL_REQ_COLUMNS + ['inserted'], limit = 10)
        
        self.list.SetData(commentList, torrentList, recentTorrentList)        

class ActivityList(List):
    def __init__(self, parent, parent_list):
        List.__init__(self, [], LIST_GREY, [7,7], parent = parent, singleSelect = True, borders = False)
        self.parent_list = parent_list
    
    def CreateHeader(self, parent):
        return TitleHeader(self, parent, [], 0, radius = 0)
    
    def CreateFooter(self, parent):
        return None

    def GetManager(self):
        if getattr(self, 'manager', None) == None:
            self.manager = ActivityManager(self) 
        return self.manager
    
    def SetData(self, comments, torrents, recent_torrents):
        List.SetData(self, torrents)
        def genCommentActivity(comment):
            return "new comment received", self.format_time(comment['time_stamp']), comment['name'] + "  " + comment['comment']
        
        def genNewTorrentActivity(torrent):
            return "new torrent received", self.format_time(torrent['time_stamp']), torrent['name']
    
        def genTorrentActivity(torrent):
            return "discovered a torrent", self.format_time(torrent['inserted']), torrent['name']
        
        data =  [(comment['time_stamp'], (comment['id'],genCommentActivity(comment), comment, ActivityItem)) for comment in comments]
        data += [(file['time_stamp'], (file['infohash'],genNewTorrentActivity(file), file, ActivityItem)) for file in torrents]
        data += [(file['inserted'], (file['infohash'],genTorrentActivity(file), file, ActivityItem)) for file in recent_torrents]
        
        data.sort(reverse = True)
        data = [item for _, item in data]
        
        if len(data) > 0:
            return self.list.SetData(data)
        self.list.ShowMessage('No recent activity is found.')
        return 0
    
    def OnExpand(self, item):
        if 'infohash' in item.original_data: #is this a torrent?
            self.parent_list.Select(item.original_data['infohash'])
    
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
