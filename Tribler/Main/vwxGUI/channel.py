# Written by Niels Zeilemaker
import wx

from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.tribler_topButton import _set_font, MaxBetterText, NotebookPanel
from Tribler.Core.API import *

from list import *
from list_footer import *
from list_header import *
from list_body import *
from list_details import *
from __init__ import *
from Tribler.Main.Utility.GuiDBHandler import startWorker, cancelWorker
from Tribler.Main.vwxGUI.IconsManager import IconsManager, SMALL_ICON_MAX_DIM
from Tribler.community.channel.community import ChannelCommunity,\
    forceAndReturnDispersyThread
from Tribler.Main.Utility.GuiDBTuples import Torrent
from Tribler.Main.Utility.Feeds.rssparser import RssParser
from wx.lib.agw.flatnotebook import FlatNotebook, PageContainer
import wx.lib.agw.flatnotebook as fnb
from wx._controls import StaticLine
from Tribler.Main.vwxGUI.list_header import ChannelOnlyHeader
from Tribler.Main.Dialogs.CreateTorrent import CreateTorrent
from shutil import copyfile

DEBUG = False

class ChannelManager():
    def __init__(self, list):
        self.list = list
        self.dirtyset = set()
        
        self.guiutility = GUIUtility.getInstance()
        self.channelsearch_manager = self.guiutility.channelsearch_manager
        self.library_manager = self.guiutility.library_manager
        
        self.Reset()
    
    def Reset(self):
        if self.list.channel:
            cancelWorker("ChannelManager_refresh_list_%d"%self.list.channel.id)

        self.list.SetChannel(None)
        self.dirtyset.clear()
        
    def refreshDirty(self):
        if 'COMPLETE_REFRESH_STATE' in self.dirtyset:
            self._refresh_list(stateChanged = True)
        elif 'COMPLETE_REFRESH' in self.dirtyset:
            self._refresh_list()
        else:
            self._refresh_partial(list(self.dirtyset))
        self.dirtyset.clear()
    
    @forceDBThread
    def reload(self, channel_id):
        channel = self.channelsearch_manager.getChannel(channel_id)
        self.refresh(channel)

    @forceWxThread
    def refresh(self, channel = None):
        if channel:
            #copy torrents if channel stays the same 
            if channel == self.list.channel:
                if self.list.channel.torrents:
                    if channel.torrents:
                        channel.torrents.update(self.list.channel.torrents)
                    else:
                        channel.torrents = self.list.channel.torrents
            
            self.list.Reset()
            self.list.SetChannel(channel)

        self._refresh_list()
    
    def _refresh_list(self, stateChanged = False):
        if DEBUG:
            print >> sys.stderr, "SelChannelManager complete refresh"
        
        self.list.dirty = False
        def db_callback():
            if stateChanged:
                state, iamModerator = self.list.channel.refreshState()
            else:
                state = iamModerator = None
            
            if self.list.channel.isDispersy():
                nr_playlists, playlists = self.channelsearch_manager.getPlaylistsFromChannel(self.list.channel)
                total_items, nrfiltered, torrentList = self.channelsearch_manager.getTorrentsNotInPlaylist(self.list.channel)
            else:
                playlists = []
                total_items, nrfiltered, torrentList = self.channelsearch_manager.getTorrentsFromChannel(self.list.channel)
                
            return total_items, nrfiltered, torrentList, playlists, state, iamModerator
        
        def do_gui(delayedResult):
            total_items, nrfiltered, torrentList, playlists, state, iamModerator = delayedResult.get()
            if state:
                self.list.SetChannelState(state, iamModerator)
                
            self._on_data(total_items, nrfiltered, torrentList, playlists)
        
        startWorker(do_gui, db_callback, uId = "ChannelManager_refresh_list_%d"%self.list.channel.id, retryOnBusy=True)
    
    @forceWxThread
    def _on_data(self, total_items, nrfiltered, torrents, playlists):
        #sometimes a channel has some torrents in the torrents variable, merge them here
        if self.list.channel.torrents:
            remoteTorrents = set(torrent.infohash for torrent in self.list.channel.torrents)
            for torrent in torrents:
                if torrent.infohash in remoteTorrents:
                    remoteTorrents.discard(torrent.infohash)
            
            self.list.channel.torrents = set([torrent for torrent in self.list.channel.torrents if torrent.infohash in remoteTorrents])
            torrents = torrents + list(self.list.channel.torrents)
        
        torrents = self.library_manager.addDownloadStates(torrents)
        
        #only show a small random selection of available content for non-favorite channels
        if not self.list.channel.isFavorite() and not self.list.channel.isMyChannel():
            if len(playlists) > 3:
                playlists = sample(playlists, 3)
                
            if len(torrents) > CHANNEL_MAX_NON_FAVORITE:
                def cmp_torrent(a, b):
                    return cmp(a.time_stamp, b.time_stamp)
                
                torrents = sample(torrents, CHANNEL_MAX_NON_FAVORITE)
                torrents.sort(cmp=cmp_torrent, reverse = True)
        
        self.list.SetData(playlists, torrents)
        self.list.SetFF(self.guiutility.getFamilyFilter(), nrfiltered)
        if DEBUG:    
            print >> sys.stderr, "SelChannelManager complete refresh done"
        
    @forceDBThread
    def _refresh_partial(self, ids):
        id_data = {}
        for id in ids:
            if isinstance(id, str) and len(id) == 20:
                id_data[id] = self.channelsearch_manager.getTorrentFromChannel(self.list.channel, id)
            else:
                id_data[id] = self.channelsearch_manager.getPlaylist(self.list.channel, id)
        
        def do_gui(): 
            for id, data in id_data.iteritems():
                self.list.RefreshData(id, data)
        wx.CallAfter(do_gui)
    
    @forceWxThread  
    def downloadStarted(self, infohash):
        if self.list.InList(infohash):
            item = self.list.GetItem(infohash)
            
            torrent_details = item.GetExpandedPanel()
            torrent_details.ShowPanel(TorrentDetails.INCOMPLETE)

    def torrentUpdated(self, infohash):
        if self.list.InList(infohash):
            if self.list.ShouldGuiUpdate():
                self._refresh_partial((infohash,))
            else:
                self.dirtyset.add(infohash)
                self.list.dirty = True
             
    def channelUpdated(self, channel_id, stateChanged = False, modified = False):
        if self.list.channel == channel_id:
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
            if self.list.ShouldGuiUpdate():
                self._refresh_list()
            else:
                self.dirtyset.add('COMPLETE_REFRESH')
                self.list.dirty = True
    
    def playlistUpdated(self, playlist_id, infohash = False):
        if self.list.InList(playlist_id):
            if self.list.InList(infohash): #if infohash is shown, complete refresh is necessary
                if self.list.ShouldGuiUpdate():
                    self._refresh_list()
                else:
                    self.dirtyset.add('COMPLETE_REFRESH')
                    self.list.dirty = True
                    
            else: #else, only update this single playlist
                if self.list.ShouldGuiUpdate():
                    self._refresh_partial((playlist_id,))
                else:
                    self.dirtyset.add(playlist_id)
                    self.list.dirty = True
          
class SelectedChannelList(GenericSearchList):
    def __init__(self, parent):
        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility
        self.channelsearch_manager = self.guiutility.channelsearch_manager 
        
        self.title = None
        self.channel = None
        self.iamModerator = False
        self.my_channel = False
        self.state = ChannelCommunity.CHANNEL_CLOSED
        
        columns = [{'name':'Name', 'width': wx.LIST_AUTOSIZE, 'sortAsc': True, 'icon': 'tree'}, \
                   {'name':'Date Added', 'width': 85, 'fmt': format_time, 'defaultSorted': True}, \
                   {'name':'Size', 'width':  '9em', 'style': wx.ALIGN_RIGHT, 'fmt': format_size}, \
                   {'type':'method', 'width': wx.LIST_AUTOSIZE_USEHEADER, 'method': self.CreateRatio, 'name':'Popularity'}, \
                   {'type':'method', 'width': LIST_AUTOSIZEHEADER, 'method': self.CreateDownloadButton}]
        
        GenericSearchList.__init__(self, columns, LIST_GREY, [6,6], True, borders = False, showChange = True, parent = parent)
    
    @warnWxThread
    def _PostInit(self):
        if self.parent.top_bg:
            self.header = ChannelHeader(self.parent, self, [])
            self.header.SetEvents(self.OnBack)
            
        else:
            self.header = ChannelOnlyHeader(self.parent, self, [])
            
            def showSettings(event):
                self.guiutility.ShowPage('settings')
                
            def showLibrary(event):
                self.guiutility.ShowPage('my_files')
                
            self.header.SetEvents(showSettings, showLibrary)
        
        self.Add(self.header, 0, wx.EXPAND)
        
        #Hack to prevent focus on tabs
        PageContainer.SetFocus = lambda a: None

        style = fnb.FNB_HIDE_ON_SINGLE_TAB|fnb.FNB_NO_X_BUTTON|fnb.FNB_NO_NAV_BUTTONS|fnb.FNB_NODRAG
        self.notebook = FlatNotebook(self.parent, style = style)
        if getattr(self.notebook, 'SetAGWWindowStyleFlag', False):
            self.notebook.SetAGWWindowStyleFlag(style)
        else:
            self.notebook.SetWindowStyleFlag(style)
        self.notebook.SetTabAreaColour(self.background)
        self.notebook.SetForegroundColour(self.parent.GetForegroundColour())
        self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.OnChange)
        
        list = wx.Panel(self.notebook)
        list.SetForegroundColour(self.notebook.GetForegroundColour())
        list.SetFocus = list.SetFocusIgnoringChildren

        vSizer = wx.BoxSizer(wx.VERTICAL)
        
        self.subheader = self.CreateHeader(list)
        self.subheader.SetBackgroundColour(self.background)
        self.header.SetSpacerRight = self.subheader.SetSpacerRight
        self.header.ResizeColumn = self.subheader.ResizeColumn
        
        vSizer.Add(self.subheader, 0, wx.EXPAND)
        self.list = self.CreateList(list)
        vSizer.Add(self.list, 1, wx.EXPAND)
        
        list.SetSizer(vSizer)
        self.notebook.AddPage(list, "Contents")
        
        self.commentList = NotebookPanel(self.notebook)
        self.commentList.SetList(CommentList(self.commentList, self, canReply=True))
        self.commentList.Show(False)
                
        self.activityList = NotebookPanel(self.notebook)
        self.activityList.SetList(ActivityList(self.activityList, self))
        self.activityList.Show(False)
        
        self.moderationList = NotebookPanel(self.notebook)
        self.moderationList.SetList(ModerationList(self.moderationList, self))
        self.moderationList.Show(False)
        
        self.leftLine = wx.Panel(self.parent, size=(1,-1))
        self.rightLine = wx.Panel(self.parent, size=(1,-1))

        listSizer = wx.BoxSizer(wx.HORIZONTAL)
        listSizer.Add(self.leftLine, 0, wx.EXPAND)
        listSizer.Add(self.notebook, 1, wx.EXPAND)
        listSizer.Add(self.rightLine, 0, wx.EXPAND)
        self.Add(listSizer, 1, wx.EXPAND)
        
        self.footer = self.CreateFooter(self.parent)
        self.Add(self.footer, 0, wx.EXPAND)
        
        self.SetBackgroundColour(self.background)
        
        self.Layout()
        self.list.Bind(wx.EVT_SIZE, self.OnSize)
    
    @warnWxThread
    def CreateHeader(self, parent):
        return ListHeader(parent, self, self.columns, radius = 0, spacers=[6,6])
   
    @warnWxThread
    def CreateFooter(self, parent):
        footer = ChannelFooter(parent)
        footer.SetEvents(self.OnSpam, self.OnFavorite, self.OnRemoveVote, self.OnManage)
        return footer
    
    @warnWxThread
    def Reset(self):
        GenericSearchList.Reset(self)
        
        self.commentList.Reset()
        self.activityList.Reset()
        self.moderationList.Reset()

    @warnWxThread
    def SetChannel(self, channel):
        self.channel = channel
        
        self.Freeze()
        self.SetIds(channel)
        
        if channel:
            self.SetTitle(channel.name, channel.description)
        
            if __debug__:
                self.header.SetToolTip(str(channel))
        
            nr_torrents = channel.nr_torrents
            if not channel.isFavorite() and not channel.isMyChannel():
                nr_torrents = min(nr_torrents, 50)
            self.SetNrResults(nr_torrents)
            
            if channel.isDispersy():
                startWorker(self.SetState, self.channel.getState, retryOnBusy=True)
            else:
                self.SetChannelState(ChannelCommunity.CHANNEL_CLOSED, self.my_channel)
        else:
            self.SetChannelState(ChannelCommunity.CHANNEL_CLOSED, False)
            
        self.Thaw()
    
    def SetIds(self, channel):
        if channel:
            self.my_channel = channel.isMyChannel()
        
            manager = self.commentList.GetManager()
            manager.SetIds(channel = channel)
            
            manager = self.activityList.GetManager()
            manager.SetIds(channel = channel)
            
            manager = self.moderationList.GetManager()
            manager.SetIds(channel = channel)
        else:
            self.my_channel = False
            
        #Always switch to page 1 after new id
        if self.notebook.GetPageCount() > 0:
            self.notebook.SetSelection(0)
    
    @warnWxThread
    def SetFooter(self, vote, channelstate, iamModerator):
        self.footer.SetStates(vote, channelstate, iamModerator)
        self.Layout()
    
    @warnWxThread
    def SetState(self, delayedResult):
        state, iamModerator = delayedResult.get()
        self.SetChannelState(state, iamModerator)
    
    @warnWxThread
    def SetChannelState(self, state, iamModerator):
        self.iamModerator = iamModerator
        self.state = state
        if state >= ChannelCommunity.CHANNEL_SEMI_OPEN:
            if self.notebook.GetPageCount() == 1:
                self.commentList.Show(True)
                self.activityList.Show(True)
                
                self.notebook.AddPage(self.commentList, "Comments")
                self.notebook.AddPage(self.activityList, "Activity")
                
            if state >= ChannelCommunity.CHANNEL_OPEN and self.notebook.GetPageCount() == 3:
                self.moderationList.Show(True)
                self.notebook.AddPage(self.moderationList, "Moderations")
        else:
            for i in range(self.notebook.GetPageCount(), 1, -1):
                page = self.notebook.GetPage(i-1)
                page.Show(False)
                self.notebook.RemovePage(i-1)

        if self.channel:
            self.SetFooter(self.channel.my_vote, state, iamModerator)
    
    @warnWxThread    
    def SetTitle(self, title, description):
        if title != self.title:
            self.title = title
            self.header.SetTitle("%s's channel"%title)
        
        self.header.SetStyle(description)
        self.Layout()
   
    @warnWxThread
    def toggleFamilyFilter(self):
        GenericSearchList.toggleFamilyFilter(self)
        manager = self.GetManager()
        manager.refresh(self.channel)
   
    def GetManager(self):
        if getattr(self, 'manager', None) == None:
            self.manager = ChannelManager(self) 
        return self.manager
    
    @forceWxThread
    def SetData(self, playlists, torrents):
        List.SetData(self, torrents)
        
        if len(playlists) > 0 or len(torrents) > 0:
            data = [(playlist.id,[playlist.name, playlist.extended_description, playlist.nr_torrents], playlist, PlaylistItem) for playlist in playlists]
            
            shouldDrag = len(playlists) > 0 and (self.iamModerator or self.state == ChannelCommunity.CHANNEL_OPEN)
            if shouldDrag:
                data += [(torrent.infohash,[torrent.name, torrent.time_stamp, torrent.length, 0, 0], torrent, DragItem) for torrent in torrents]
            else:
                data += [(torrent.infohash,[torrent.name, torrent.time_stamp, torrent.length, 0, 0], torrent) for torrent in torrents]
            self.list.SetData(data)
            
            self.SetNrResults(len(data))
        else:
            header =  'No torrents or playlists found.'
            
            if self.state == ChannelCommunity.CHANNEL_OPEN:
                message = 'As this is an "open" channel, you can add your own torrents to share them with others in this channel'
                self.list.ShowMessage(message, header = header)
            else:
                self.list.ShowMessage(header)
            
            self.SetNrResults(0)
    
    @warnWxThread
    def SetNrResults(self, nr):
        if self.channel and (self.channel.isFavorite() or self.channel.isMyChannel()):
            header = 'Discovered'
        else:
            header = 'Previewing'
            
        if nr == 1:
            self.header.SetSubTitle(header+ ' %d torrent'%nr)
        else:
            if self.channel and self.channel.isFavorite():
                self.header.SetSubTitle(header+' %d torrents'%nr)
            else:
                self.header.SetSubTitle(header+' %d torrents'%nr)
    
    @forceWxThread
    def RefreshData(self, key, data):
        List.RefreshData(self, key, data)
        
        if data:
            if isinstance(data, Torrent):
                if self.state == ChannelCommunity.CHANNEL_OPEN or self.iamModerator:
                    data = (data.infohash,[data.name, data.time_stamp, data.length, 0, 0], data, DragItem)
                else:
                    data = (data.infohash,[data.name, data.time_stamp, data.length, 0, 0], data)
            else:
                data = (data.id,[data.name, data.extended_description, data.nr_torrents], data, PlaylistItem)
            self.list.RefreshData(key, data)
         
        manager = self.activityList.GetManager()
        manager.do_or_schedule_refresh()
    
    @warnWxThread
    def OnExpand(self, item):
        if isinstance(item, PlaylistItem):
            self.guiutility.showPlaylist(item.original_data)
            return False
        
        item.button.Hide()
        item.button.Refresh()
        return TorrentDetails(item, item.original_data, noChannel = True)

    @warnWxThread
    def OnCollapse(self, item, panel):
        if not isinstance(item, PlaylistItem):
            if panel:
                #detect changes
                changes = panel.GetChanged()
                if len(changes)>0:
                    dlg = wx.MessageDialog(None, 'Do you want to save your changes made to this torrent?', 'Save changes?', wx.YES_NO | wx.YES_DEFAULT | wx.ICON_QUESTION)
                    if dlg.ShowModal() == wx.ID_YES:
                        self.OnSaveTorrent(self.channel, panel)
                    dlg.Destroy()
            GenericSearchList.OnCollapse(self, item, panel)
    
    @warnWxThread
    def OnSaveTorrent(self, channel, panel):
        changes = panel.GetChanged()
        if len(changes)>0:
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
    def OnRemoveVote(self, event):
        if event:
            button = event.GetEventObject()
            button.Enable(False)
            wx.CallLater(5000, button.Enable, True)
            
        self._DoRemoveVote()
    
    @forceDBThread    
    def _DoRemoveVote(self):
        #Set self.channel to None to prevent updating twice
        id = self.channel.id
        self.channel = None
        self.channelsearch_manager.remove_vote(id)
        
        manager = self.GetManager()
        wx.CallAfter(manager.reload, id)
    
    @warnWxThread
    def OnFavorite(self, event = None):
        if event:
            button = event.GetEventObject()
            button.Enable(False)
            wx.CallLater(5000, button.Enable, True)

        self._DoFavorite()
        
    @forceDBThread    
    def _DoFavorite(self):
        #Request all items from connected peers
        if not self.channel.isDispersy():
            permid = self.channelsearch_manager.getPermidFromChannel(id)
            channelcast = BuddyCastFactory.getInstance().channelcast_core
            channelcast.updateAChannel(id, permid)
        
        #Set self.channel to None to prevent updating twice
        id = self.channel.id
        self.channel = None
        self.channelsearch_manager.favorite(id)

        self.uelog.addEvent(message="ChannelList: user marked a channel as favorite", type = 2)
        
        manager = self.GetManager()
        wx.CallAfter(manager.reload, id)
    
    @warnWxThread
    def OnSpam(self, event):
        dialog = wx.MessageDialog(None, "Are you sure you want to report %s's channel as spam?" % self.title, "Report spam", wx.ICON_QUESTION | wx.YES_NO | wx.NO_DEFAULT)
        if dialog.ShowModal() == wx.ID_YES:
            self._DoSpam()
        
        if event:
            button = event.GetEventObject()
            button.Enable(False)
            wx.CallLater(5000, button.Enable, True)
        
        dialog.Destroy()
        
    @forceDBThread
    def _DoSpam(self):
        #Set self.channel to None to prevent updating twice
        id = self.channel.id
        self.channel = None
        self.channelsearch_manager.spam(id)
        
        self.uelog.addEvent(message="ChannelList: user marked a channel as spam", type = 2)
            
        manager = self.GetManager()
        wx.CallAfter(manager.reload, id)     
    
    @warnWxThread
    def OnManage(self, event):
        self.guiutility.showManageChannel(self.channel)
    
    @warnWxThread
    def OnBack(self, event):
        self.guiutility.GoBack(self.channel.id)
    
    @warnWxThread
    def OnSize(self, event):
        diff = self.subheader.GetClientSize()[0] - self.list.GetClientSize()[0]
        self.subheader.SetSpacerRight(diff)
        self.footer.SetSpacerRight(diff)
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
            
        else: #maybe channel_id is a infohash
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
            
        else: #maybe channel_id is a channeltorrent_id
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
    
    @warnWxThread
    def Select(self, key, raise_event = True):
        if isinstance(key, Torrent):
            torrent = key
            key = torrent.infohash
            
            if torrent.playlist:
                self.guiutility.showPlaylist(torrent.playlist)
                wx.CallLater(1000, self.guiutility.frame.playlist.Select, key)
                return

        GenericSearchList.Select(self, key, raise_event)
        
        if self.notebook.GetPageCount() > 0:
            self.notebook.SetSelection(0)
        self.ScrollToId(key)
    
    def StartDownload(self, torrent, files = None):
        def do_gui(delayedResult):
            nrdownloaded = delayedResult.get()
            self._ShowFavoriteDialog(nrdownloaded)
            GenericSearchList.StartDownload(self, torrent, files)
        
        def do_db():
            return self.channelsearch_manager.getNrTorrentsDownloaded(self.channel.id) + 1
        
        if not self.channel.isFavorite():
            startWorker(do_gui, do_db, retryOnBusy=True)
        else:
            GenericSearchList.StartDownload(self, torrent, files)
        
    def _ShowFavoriteDialog(self, nrdownloaded):
        dial = wx.MessageDialog(None, "You downloaded %d torrents from this Channel. 'Mark as favorite' will ensure that you will always have access to newest channel content.\n\nDo you want to mark this channel as one of your favorites now?"%nrdownloaded, 'Mark as Favorite?', wx.YES_NO | wx.YES_DEFAULT | wx.ICON_QUESTION)
        if dial.ShowModal() == wx.ID_YES:
            self.OnFavorite()
            self.uelog.addEvent(message="ChannelList: user clicked yes to mark as favorite", type = 2)
        else:
            self.uelog.addEvent(message="ChannelList: user clicked no to mark as favorite", type = 2)  
        dial.Destroy()
        
class DragItem(ListItem):
    def __init__(self, parent, parent_list, columns, data, original_data, leftSpacer = 0, rightSpacer = 0, showChange = False, list_selected = LIST_SELECTED):
        ListItem.__init__(self, parent, parent_list, columns, data, original_data, leftSpacer, rightSpacer, showChange, list_selected)

    def AddEvents(self, control):
        if getattr(control, 'GetWindow', False): #convert sizeritems
            control = control.GetWindow() or control.GetSizer()
        
        if getattr(control, 'Bind', False):
            control.Bind(wx.EVT_MOTION, self.OnDrag)
            
        ListItem.AddEvents(self, control)
        
    def OnDrag(self, event):
        if event.LeftIsDown():
            self.parent_list.parent_list.OnDrag(self)
        
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

class PlaylistManager():
    def __init__(self, list):
        self.list = list
        self.dirtyset = set()   
        
        self.guiutility = GUIUtility.getInstance()
        self.library_manager = self.guiutility.library_manager
        self.channelsearch_manager = self.guiutility.channelsearch_manager
    
    def SetPlaylist(self, playlist):
        if self.list.playlist != playlist:
            self.list.Reset()
            
            self.list.playlist = playlist
            self.list.SetChannel(playlist.channel)
        
        self._refresh_list()
    
    def Reset(self):
        self.dirtyset.clear()
        
        if self.list.playlist:
            cancelWorker("PlaylistManager_refresh_list_%d"%self.list.playlist.id)
    
    def refreshDirty(self):
        if 'COMPLETE_REFRESH' in self.dirtyset:
            self._refresh_list()
        else:
            self._refresh_partial(list(self.dirtyset))
        self.dirtyset.clear()
    
    def _refresh_list(self):
        def db_call():
            self.list.dirty = False
            return self.channelsearch_manager.getTorrentsFromPlaylist(self.list.playlist)
            
        startWorker(self._on_data, db_call, uId = "PlaylistManager_refresh_list_%d"%self.list.playlist.id, retryOnBusy=True)
        
    @forceDBThread
    def _refresh_partial(self, ids):
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
        self.list.SetFF(self.guiutility.getFamilyFilter(), nrfiltered)
        
    def torrentUpdated(self, infohash):
        if self.list.InList(infohash):
            if self.list.ShouldGuiUpdate():
                self._refresh_partial((infohash,))
            else:
                self.dirtyset.add(infohash)
                self.list.dirty = True
        
    def playlistUpdated(self, playlist_id):
        if self.list.playlist == playlist_id:
            if self.list.ShouldGuiUpdate():
                self._refresh_list()
            else:
                self.list.dirty = True

class Playlist(SelectedChannelList):
    def __init__(self, *args, **kwargs):
        self.playlist = None
        SelectedChannelList.__init__(self, *args, **kwargs)
    
    def GetManager(self):
        if getattr(self, 'manager', None) == None:
            self.manager = PlaylistManager(self) 
        return self.manager
    
    def Set(self, playlist):
        manager = self.GetManager()
        manager.SetPlaylist(playlist)
        if self.notebook.GetPageCount() > 0:
            self.notebook.SetSelection(0)
    
    def SetTitle(self, title, description):
        header = u"%s's channel \u2192 %s"%(self.channel.name, self.playlist.name) 
        
        self.header.SetTitle(header)
        self.header.SetStyle(self.playlist.description)
        self.Layout()
    
    def SetIds(self, channel):
        if channel:
            manager = self.commentList.GetManager()
            manager.SetIds(channel = channel, playlist = self.playlist)
            
            manager = self.activityList.GetManager()
            manager.SetIds(channel = channel, playlist = self.playlist)
            
            manager = self.moderationList.GetManager()
            manager.SetIds(channel = channel, playlist = self.playlist)
            
    @warnWxThread
    def toggleFamilyFilter(self):
        GenericSearchList.toggleFamilyFilter(self)
        self.Set(self.playlist)
            
    def OnCommentCreated(self, key):
        SelectedChannelList.OnCommentCreated(self, key)
        
        if self.InList(key):
            manager = self.commentList.GetManager()
            manager.new_comment()
            
    def CreateFooter(self, parent):
        return PlaylistFooter(parent)
    
    @warnWxThread
    def OnBack(self, event):
        self.guiutility.GoBack(self.playlist.id)
        
class PlaylistItem(ListItem):
    def __init__(self, parent, parent_list, columns, data, original_data, leftSpacer = 0, rightSpacer = 0, showChange = False, list_selected = LIST_SELECTED):
        ListItem.__init__(self, parent, parent_list, columns, data, original_data, leftSpacer, rightSpacer, showChange, list_selected)
        
        self.SetDropTarget(TorrentDT(original_data, parent_list.parent_list.AddTorrent))
        self.should_update = True
        
    def AddComponents(self, leftSpacer, rightSpacer):
        titleRow = wx.BoxSizer(wx.HORIZONTAL)
        if leftSpacer > 0:
            titleRow.AddSpacer((leftSpacer, -1))
        
        icon = wx.StaticBitmap(self, -1, self.GetIcon('tree', LIST_DESELECTED, 0))
        titleRow.Add(icon, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 3)
        
        self.title = wx.StaticText(self, -1, self.data[0], style = wx.ST_NO_AUTORESIZE|wx.ST_DOTS_END)
        self.title.SetMinSize((1, -1))
        _set_font(self.title, fontweight = wx.FONTWEIGHT_BOLD)
        
        titleRow.Add(self.title, 1, wx.RESERVE_SPACE_EVEN_IF_HIDDEN|wx.ALIGN_CENTER_VERTICAL|wx.TOP|wx.LEFT|wx.BOTTOM, 3)
        self.nrTorrents = wx.StaticText(self, -1, "%d Torrents"%self.data[2], style = wx.ST_NO_AUTORESIZE|wx.ST_DOTS_END)
        titleRow.Add(self.nrTorrents, 0, wx.RESERVE_SPACE_EVEN_IF_HIDDEN|wx.ALIGN_CENTER_VERTICAL|wx.TOP|wx.LEFT|wx.BOTTOM, 3)

        if rightSpacer > 0:
            titleRow.AddSpacer((rightSpacer, -1))
        self.vSizer.Add(titleRow, 0, wx.EXPAND)
        
        #set icon as title.icon and add to controls to allow listitem to change backgrouncolour of icon
        self.title.icon = icon
        self.title.icon.type = 'tree'
        self.controls.append(self.title)
        
        self.desc = wx.StaticText(self, -1, self.data[1], style = wx.ST_NO_AUTORESIZE|wx.ST_DOTS_END)
        self.desc.SetMinSize((1, -1))
        self.hSizer.AddSpacer((40, -1))
        self.hSizer.Add(self.desc, 1, wx.LEFT|wx.BOTTOM, 3)
        self.AddEvents(self)
        
    def RefreshData(self, data):
        has_changed = False
        for i in range(3):
            if data[1][i] != self.data[i]:
                has_changed = True
                break
        
        if has_changed:
            self.Freeze()
            
            self.data = data[1]
            self.title.SetLabel(self.data[0])
            self.nrTorrents.SetLabel("%d Torrents"%self.data[2])
            self.desc.SetLabel(self.data[1])
            
            self.Highlight()
        
            self.Layout()
            self.Thaw()
    
class ManageChannelFilesManager():
    def __init__(self, list):
        self.list = list
        self.channel = None
        self.guiutility = GUIUtility.getInstance()
        self.channelsearch_manager = self.guiutility.channelsearch_manager
        
        self.Reset()
        
    def Reset(self):
        if self.channel:
            cancelWorker("ManageChannelFilesManager_refresh_%d"%self.channel.id)
            
        self.channel = None
    
    def refreshDirty(self):
        if self.channel:
            self._refresh()
    
    def refresh_list(self):
        if self.list.IsShownOnScreen():
            self._refresh()
        else:
            self.list.dirty = True
        
    def _refresh(self):
        def db_call():
            self.list.dirty = False
            return self.channelsearch_manager.getTorrentsFromChannel(self.channel, filterTorrents = False)
        
        startWorker(self._on_data, db_call, uId = "ManageChannelFilesManager_refresh_%d"%self.channel.id, retryOnBusy=True)
        
    def _on_data(self, delayedResult):
        total_items, nrfiltered, torrentList = delayedResult.get()
        self.list.SetData(torrentList)
    
    def SetChannel(self, channel):
        if self.channel != channel:
            self.channel = channel

            self.list.dirty = True
            
    def RemoveItems(self, infohashes):
        for infohash in infohashes:
            self.channelsearch_manager.removeTorrent(self.channel, infohash)
                
    def RemoveAllItems(self):
        self.channelsearch_manager.removeAllTorrents(self.channel)
        
    def startDownloadFromUrl(self, url, *args, **kwargs):
        try:
            tdef = TorrentDef.load_from_url(url)
            return self.AddTDef(tdef)
        except:
            return False
        
    def startDownloadFromMagnet(self, url, *args, **kwargs):
        try:
            return TorrentDef.retrieve_from_magnet(url, self.AddTDef)
        except:
            return False
    
    def startDownload(self, torrentfilename, *args, **kwargs):
        try:
            tdef = TorrentDef.load(torrentfilename)
            if 'fixtorrent' not in kwargs:
                self.guiutility.frame.startDownload(torrentfilename = torrentfilename, destdir = kwargs.get('destdir', None), correctedFilename = kwargs.get('correctedFilename',None))

            return self.AddTDef(tdef)
        except:
            return False
        
    def startDownloads(self, filenames, *args, **kwargs):
        torrentdefs = []
        
        while len(filenames) > 0:
            for torrentfilename in filenames[:500]:
                try:
                    tdef = TorrentDef.load(torrentfilename)
                    if 'fixtorrent' not in kwargs:
                        self.guiutility.frame.startDownload(torrentfilename = torrentfilename, destdir = kwargs.get('destdir', None), correctedFilename = kwargs.get('correctedFilename',None))
    
                    torrentdefs.append(tdef)
                except:
                    pass
            
            if not self.AddTDefs(torrentdefs):
                return False
            
            filenames = filenames[500:]
        return True 
        
    def startDownloadFromTorrent(self, torrent):
        self.channelsearch_manager.createTorrent(self.channel, torrent)
        return True
        
    def AddTDef(self, tdef):
        if tdef:
            self.channelsearch_manager.createTorrentFromDef(self.channel.id, tdef)
            if not self.channel.isMyChannel():
                notification = "New torrent added to %s's channel"%self.channel.name
            else:
                notification = 'New torrent added to My Channel'
            self.guiutility.frame.top_bg.Notify(notification, wx.ART_INFORMATION)
            
            return True
        return False

    def AddTDefs(self, tdefs):
        if tdefs:
            self.channelsearch_manager.createTorrentsFromDefs(self.channel.id, tdefs)
            if not self.channel.isMyChannel():
                notification = "%d new torrents added to %s's channel"%(len(tdefs),self.channel.name)
            else:
                notification = '%d new torrents added to My Channel'%len(tdefs)
            self.guiutility.frame.top_bg.Notify(notification, wx.ART_INFORMATION)
            
            return True
        return False
    
    def DoExport(self, target_dir):
        if os.path.isdir(target_dir):
            torrent_dir = self.channelsearch_manager.session.get_torrent_collecting_dir()
            _,_,torrents = self.channelsearch_manager.getTorrentsFromChannel(self.channel, filterTorrents = False)
            
            nr_torrents_exported = 0
            for torrent in torrents:
                collected_torrent_filename = get_collected_torrent_filename(torrent.infohash)
                
                torrent_filename = os.path.join(torrent_dir, collected_torrent_filename)
                if os.path.isfile(torrent_filename):
                    new_torrent_filename = os.path.join(target_dir, collected_torrent_filename)
                    copyfile(torrent_filename, new_torrent_filename)
                    
                    nr_torrents_exported += 1
            
            self.guiutility.frame.top_bg.Notify('%d torrents exported'%nr_torrents_exported, wx.ART_INFORMATION)
        
class ManageChannelPlaylistsManager():
    
    def __init__(self, list):
        self.list = list
        self.channel = None
        self.channelsearch_manager = GUIUtility.getInstance().channelsearch_manager
        
        self.Reset()
        
    def Reset(self):
        if self.channel:
            cancelWorker("ManageChannelPlaylistsManager_refresh_%d"%self.channel.id)
            
        self.channel = None
    
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
            _, playlistList = self.channelsearch_manager.getPlaylistsFromChannel(self.channel)
            return playlistList
        
        startWorker(self.list.SetDelayedData, db_call, uId = "ManageChannelPlaylistsManager_refresh_%d"%self.channel.id, retryOnBusy=True)
       
    def _refresh_partial(self, playlist_id):
        startWorker(self.list.RefreshDelayedData, self.channelsearch_manager.getPlaylist, wargs=(self.channel, playlist_id), cargs = (playlist_id,), retryOnBusy=True)
    
    def SetChannel(self, channel):
        if channel != self.channel:
            self.channel = channel
            self.list.dirty = True
    
    def GetTorrentsFromChannel(self):
        delayedResult = startWorker(None, self.channelsearch_manager.getTorrentsFromChannel, wargs = (self.channel,), wkwargs = {'filterTorrents' : False}, retryOnBusy=True)
        total_items, nrfiltered, torrentList = delayedResult.get()
        return torrentList
    
    def GetTorrentsNotInPlaylist(self):
        delayedResult = startWorker(None, self.channelsearch_manager.getTorrentsNotInPlaylist, wargs = (self.channel,), wkwargs = {'filterTorrents' : False}, retryOnBusy=True)
        total_items, nrfiltered, torrentList = delayedResult.get()
        return torrentList
        
    def GetTorrentsFromPlaylist(self, playlist):
        delayedResult = startWorker(None, self.channelsearch_manager.getTorrentsFromPlaylist, wargs = (playlist,), wkwargs = {'filterTorrents' : False}, retryOnBusy=True)
        total_items, nrfiltered, torrentList = delayedResult.get()
        return torrentList
    
    def createPlaylist(self, name, description, infohashes):
        startWorker(None, self.channelsearch_manager.createPlaylist, wargs = (self.channel.id, name, description, infohashes), retryOnBusy=True)
    
    def savePlaylist(self, playlist_id, name, description):
        startWorker(None, self.channelsearch_manager.modifyPlaylist, wargs = (self.channel.id, playlist_id, name, description), retryOnBusy=True)
    
    def savePlaylistTorrents(self, playlist_id, infohashes):
        startWorker(None, self.channelsearch_manager.savePlaylistTorrents, wargs = (self.channel.id, playlist_id, infohashes), retryOnBusy=True)
    
    def playlistUpdated(self, playlist_id):
        if self.list.InList(playlist_id):
            self._refresh_partial(playlist_id)

class ManageChannel(XRCPanel, AbstractDetails):

    def _PostInit(self):
        self.channel = None
        
        self.guiutility = GUIUtility.getInstance()
        self.uelog = UserEventLogDBHandler.getInstance()
        self.torrentfeed = RssParser.getInstance()
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
        self.overviewpage = wx.Panel(self.notebook)
        self.overviewpage.SetBackgroundColour(LIST_DESELECTED)
        
        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.AddSpacer((-1, 10))
        header =  "Welcome to the management interface for this channel. You can access this because you have the rights to modify it."
        self._add_header(self.overviewpage, vSizer, header, spacer = 10)
        
        text  = "Channels can be used to spread torrents to other Tribler users. "
        text += "If a channel provides other Tribler users with original or popular content, then they might mark your channel as one of their favorites. "
        text += "This will help to promote your channel, because the number of users which have marked a channel as one of their favorites is used to calculate popularity. "
        text += "Additionally, when another Tribler user marks your channel as a favorite they help you distribute all the .torrent files.\n\n"
        text += "Currently three options exist to spread torrents. "
        text += "Two of them, periodically importing .torrents from an rss feed and manually adding .torrent files, are available from the 'Manage' tab.\n"
        text += "The third option is available from the torrentview after completely downloading a torrent and allows you to add a torrent to your channel with a single click."
        
        overviewtext = wx.StaticText(self.overviewpage, -1, text)
        vSizer.Add(overviewtext, 0, wx.EXPAND|wx.ALL, 10)
        
        text = "Currently your channel is not created. Please fill in  a name and description and click the create button to start spreading your torrents."
        self.createText = wx.StaticText(self.overviewpage, -1, text)
        self.createText.Hide()
        vSizer.Add(self.createText, 0, wx.EXPAND|wx.ALL, 10)
        
        gridSizer = wx.FlexGridSizer(0, 2, 3, 3)
        gridSizer.AddGrowableCol(1)
        gridSizer.AddGrowableRow(1)
        
        self.name = EditText(self.overviewpage, '')
        self.name.SetMaxLength(40)
        
        self.description = EditText(self.overviewpage, '', multiLine=True)
        self.description.SetMaxLength(2000)
        self.description.SetMinSize((-1, 50))
        
        self._add_row(self.overviewpage, gridSizer, "Name", self.name)
        self._add_row(self.overviewpage, gridSizer, 'Description', self.description)
        vSizer.Add(gridSizer, 0, wx.EXPAND|wx.RIGHT, 10)
        
        self.saveButton = wx.Button(self.overviewpage, -1, 'Save Changes')
        self.saveButton.Bind(wx.EVT_BUTTON, self.Save)
        vSizer.Add(self.saveButton, 0, wx.ALIGN_RIGHT|wx.ALL, 10)
        
        self.overviewpage.SetSizer(vSizer)
        self.overviewpage.Show(False)
        
        #Open2Edit settings
        self.settingspage = wx.Panel(self.notebook)
        self.settingspage.SetBackgroundColour(LIST_DESELECTED)
        
        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.AddSpacer((-1, 10))
        header =  "Community Settings"
        self._add_header(self.settingspage, vSizer, header, spacer = 10)
        
        text  = "Tribler allows you to involve your community. "
        text += "You as a channel-owner have the option to define the openness of your community. "
        text += "By choosing a more open setting, other users are allowed to do more.\n\n"
        
        text += "Currently three configurations exist:\n"
        text += "\tOpen, only you can define playlists and delete torrents. Other users can do everything else, ie add torrents, categorize torrents, comment etc.\n"
        text += "\tSemi-Open, only you can add new .torrents. Other users can download and comment on them.\n"
        text += "\tClosed, only you can add new .torrents. Other users can only download them."
        vSizer.Add(wx.StaticText(self.settingspage, -1, text), 0, wx.EXPAND|wx.ALL, 10)
        
        gridSizer = wx.FlexGridSizer(0, 2, 3, 3)
        gridSizer.AddGrowableCol(1)
        gridSizer.AddGrowableRow(1)
        
        self.statebox = wx.RadioBox(self.settingspage, choices = ('Open', 'Semi-Open', 'Closed'), style = wx.RA_VERTICAL) 
        self._add_row(self.settingspage, gridSizer, "Configuration", self.statebox)
        vSizer.Add(gridSizer, 0, wx.EXPAND|wx.RIGHT, 10)
        
        saveButton = wx.Button(self.settingspage, -1, 'Save Changes')
        saveButton.Bind(wx.EVT_BUTTON, self.SaveSettings)
        vSizer.Add(saveButton, 0, wx.ALIGN_RIGHT|wx.ALL, 10)
        self.settingspage.SetSizer(vSizer)
        self.settingspage.Show(False)
        
        #shared files page
        self.fileslist = NotebookPanel(self.notebook)
        filelist = ManageChannelFilesList(self.fileslist)
        self.fileslist.SetList(filelist)
        filelist.SetNrResults = self.header.SetNrTorrents
        self.fileslist.Show(False)
        
        #playlist page
        self.playlistlist = NotebookPanel(self.notebook)
        self.playlistlist.SetList(ManageChannelPlaylistList(self.playlistlist))
        self.playlistlist.Show(False)
        
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
        self.managepage.Show(False)
        
        boxSizer.Add(self.notebook, 1, wx.EXPAND|wx.ALL, 5)
        self.SetSizer(boxSizer)
        self.Layout()
    
    def BuildRssPanel(self, parent, sizer):
        self._add_subheader(parent, sizer, "Current rss-feeds:","(which are periodically checked)")
        
        rssSizer = wx.BoxSizer(wx.VERTICAL)
        
        if self.channel:
            urls = self.torrentfeed.getUrls(self.channel.id)
        else:
            urls = []
            
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
            
            self.header.SetName('Management interface for %s\'s Channel'%channel.name)
            self.header.SetNrTorrents(channel.nr_torrents, channel.nr_favorites)
            
            if channel.isMyChannel():
                self.torrentfeed.register(self.guiutility.utility.session, channel.id)
                
                name = channel.name
                self.name.SetValue(name)
                self.name.originalValue = name

                description = channel.description
                self.description.SetValue(description)
                self.description.originalValue = description
                
                self.createText.Hide()
                self.saveButton.SetLabel('Save Changes')
                
                self.AddPage(self.notebook, self.overviewpage, "Overview", 0)
            else:
                #Best to removepage, will be added if we're moderator
                self.RemovePage(self.notebook, "Overview")

            
            def db_call():
                channel_state, iamModerator = self.channelsearch_manager.getChannelState(channel.id)
                return channel_state, iamModerator
            
            def update_panel(delayedResult):
                channel_state, iamModerator = delayedResult.get() 
                
                if iamModerator:
                    #If this is not mychannel, but I am moderator add overview panel
                    self.AddPage(self.notebook, self.overviewpage, "Overview", 0)
                    
                    selection = channel_state
                    if selection == 0:
                        selection = 2
                    elif selection == 2:
                        selection = 0
                    
                    self.statebox.SetSelection(selection)
                    self.AddPage(self.notebook, self.settingspage, "Settings", 1)
                else:
                    self.RemovePage(self.notebook, "Overview")
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
                #self.CreateJoinChannelFile()
                    
            startWorker(update_panel, db_call, retryOnBusy=True)
            
        else:
            self.name.SetValue('')
            self.name.originalValue = ''
            
            self.description.SetValue('')
            self.description.originalValue = ''
            
            self.header.SetName('Create your own channel')
            self.header.SetNrTorrents(0, 0)
                
            self.createText.Show()
            self.saveButton.SetLabel('Create Channel')
            
            self.AddPage(self.notebook, self.overviewpage, "Overview", 0)
            
            #disable all other tabs, do it in reverse as pageindexes change
            for i in range(self.notebook.GetPageCount(), 1, -1):
                page = self.notebook.GetPage(i-1)
                page.Show(False)
                self.notebook.RemovePage(i-1)
            
            self.fileslist.Reset()
            self.playlistlist.Reset()
        
        #Always switch to page 1 after new id
        if self.notebook.GetPageCount() > 0:
            self.notebook.SetSelection(0)
                
    @warnWxThread
    def Reset(self):
        self.SetChannel(None)
    
    @forceDBThread        
    def SetChannelId(self, channel_id):
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
            self.fileslist.Show(isSelected = True)
            self.fileslist.Focus()
        
        elif page == self.GetPage(self.notebook, "Manage playlists"):
            self.playlistlist.Show(isSelected = True)
            self.playlistlist.Focus() 
        event.Skip()
    
    def OnBack(self, event):
        self.guiutility.GoBack()
    
    def OnAddRss(self, event):
        item = event.GetEventObject()
        url = item.url.GetValue().strip()
        if len(url) > 0:
            self.torrentfeed.addURL(url, self.channel.id)
            self.RebuildRssPanel()
            
            self.uelog.addEvent(message="MyChannel: rssfeed added", type = 2)
        
    def OnDeleteRss(self, event):
        item = event.GetEventObject()
        
        self.torrentfeed.deleteURL(item.url, self.channel.id)
        self.RebuildRssPanel()
        
        self.uelog.addEvent(message="MyChannel: rssfeed removed", type = 2)
    
    def OnRefreshRss(self, event):
        self.torrentfeed.doRefresh()
        
        button = event.GetEventObject()
        button.Enable(False)
        wx.CallLater(5000, button.Enable, True)
        
        self.uelog.addEvent(message="MyChannel: rssfeed refreshed", type = 2)
            
    def CreateJoinChannelFile(self):
        f = open('joinchannel', 'wb')
        f.write(self.channel.dispersy_cid)
        f.close()
    
    def _import_torrents(self, files):
        tdefs = [TorrentDef.load(file) for file in files if file.endswith(".torrent")]
        self.channelsearch_manager.createTorrentsFromDefs(self.channel.id, tdefs)
        nr_imported = len(tdefs)
        
        if nr_imported > 0:
            if nr_imported == 1:
                self.guiutility.frame.top_bg.Notify('New torrent added to My Channel', wx.ART_INFORMATION)
            else:
                self.guiutility.frame.top_bg.Notify('Added %d torrents to your Channel'%nr_imported, wx.ART_INFORMATION)
    
    def Show(self, show=True):
        if not show:
            if self.IsChanged():
                dlg = wx.MessageDialog(None, 'Do you want to save your changes made to this channel?', 'Save changes?', wx.YES_NO | wx.YES_DEFAULT | wx.ICON_QUESTION)
                if dlg.ShowModal() == wx.ID_YES:
                    self.Save()
            
        XRCPanel.Show(self, show)
    
    def Save(self, event = None):
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
        
    def SaveSettings(self, event):
        state = self.statebox.GetSelection()
        if state == 0:
            state = 2
        elif state == 2:
            state = 0
        startWorker(None, self.channelsearch_manager.setChannelState, wargs = (self.channel.id, state), retryOnBusy=True)
        
        button = event.GetEventObject()
        button.Enable(False)
        wx.CallLater(5000, button.Enable, True)
    
    def playlistCreated(self, channel_id):
        if self.channel == channel_id:
            manager = self.playlistlist.GetManager()
            manager.refresh_list()
        
    def playlistUpdated(self, playlist_id):
        manager = self.playlistlist.GetManager()
        manager.playlistUpdated(playlist_id)
        
    def channelUpdated(self, channel_id, created = False, modified = False):
        if self.channel == channel_id:
            manager = self.fileslist.GetManager()
            manager.refresh_list()
            
            if modified:
                self.SetChannelId(channel_id)
                
        elif not self.channel and created:
            self.SetChannelId(channel_id)
            
class ManageChannelFilesList(List):
    def __init__(self, parent):
        columns = [{'name':'Name', 'width': wx.LIST_AUTOSIZE, 'icon': 'checkbox', 'sortAsc': True}, \
                   {'name':'Date Added', 'width': 85, 'fmt': format_time, 'defaultSorted': True}]
   
        List.__init__(self, columns, LIST_BLUE, [0,0], parent = parent, borders = False)
    
    def CreateHeader(self, parent):
        return ListHeader(parent, self, self.columns, 0)
    
    def CreateFooter(self, parent):
        return ManageChannelFilesFooter(parent, self.OnRemoveAll, self.OnRemoveSelected, self.OnAdd, self.OnExport)
    
    def GetManager(self):
        if getattr(self, 'manager', None) == None:
            self.manager = ManageChannelFilesManager(self) 
        return self.manager
    
    def SetData(self, data):
        List.SetData(self, data)
        
        data = [(torrent.infohash,[torrent.name,torrent.time_stamp], torrent) for torrent in data]
        if len(data) > 0:
            self.list.SetData(data)
        else:
            self.list.ShowMessage('You are currently not sharing any torrents in your channel.')
        self.SetNrResults(len(data))
        
    def SetFooter(self, state, iamModerator):
        self.canDelete = iamModerator
        self.canAdd = (state == ChannelCommunity.CHANNEL_OPEN) or iamModerator
        
        self.footer.SetState(self.canDelete, self.canAdd)
        
    def OnExpand(self, item):
        return True
    
    def OnRemoveAll(self, event):
        dlg = wx.MessageDialog(None, 'Are you sure you want to remove all torrents from your channel?', 'Remove torrents', wx.ICON_QUESTION | wx.YES_NO | wx.NO_DEFAULT)
        if dlg.ShowModal() == wx.ID_YES:
            self.GetManager().RemoveAllItems()
        dlg.Destroy()
    
    def OnRemoveSelected(self, event):
        dlg = wx.MessageDialog(None, 'Are you sure you want to remove all selected torrents from your channel?', 'Remove torrents', wx.ICON_QUESTION | wx.YES_NO | wx.NO_DEFAULT)
        if dlg.ShowModal() == wx.ID_YES:
            infohashes = [key for key,_ in self.list.GetExpandedItems()]
            self.GetManager().RemoveItems(infohashes)
        dlg.Destroy()
        
    def OnAdd(self, event):
        _,_,libraryTorrents = self.guiutility.library_manager.getHitsInCategory()
        
        dlg = AddTorrent(None, self.GetManager(),libraryTorrents)
        dlg.CenterOnParent()
        dlg.ShowModal()
        dlg.Destroy()
        
    def OnExport(self, event):
        dlg = wx.DirDialog(None, "Please select a directory to which all .torrents should be exported", style = wx.wx.DD_DIR_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK and os.path.isdir(dlg.GetPath()):
            self.GetManager().DoExport(dlg.GetPath())
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
    
    @forceWxThread
    def RefreshData(self, key, playlist):
        data = (playlist.id, (playlist.name,), playlist)
        self.list.RefreshData(key, data)
    
    @forceWxThread
    def SetData(self, data):
        List.SetData(self, data)
        
        data = [(playlist.id,(playlist.name, ), playlist) for playlist in data]
        if len(data) > 0:
            self.list.SetData(data)
        else:
            self.list.ShowMessage('You currently do not have any playlists in your channel.')
        self.SetNrResults(len(data))
    
    def OnExpand(self, item):
        return MyChannelPlaylist(item, self.OnEdit, self.canDelete, self.OnSave, item.original_data)

    def OnCollapse(self, item, panel):
        playlist_id = item.original_data.get('id', False)
        if playlist_id:
            if panel.IsChanged():
                dlg = wx.MessageDialog(None, 'Do you want to save your changes made to this playlist?', 'Save changes?', wx.YES_NO | wx.YES_DEFAULT | wx.ICON_QUESTION)
                if dlg.ShowModal() == wx.ID_YES:
                    self.OnSave(playlist_id, panel)
        ManageChannelFilesList.OnCollapse(self, item, panel)
        
    def OnSave(self, playlist_id, panel):
        name, description, _ = panel.GetInfo()
        manager = self.GetManager()
        manager.savePlaylist(playlist_id, name, description)
    
    def OnNew(self, event):
        vSizer = wx.BoxSizer(wx.VERTICAL)
        
        dlg = wx.Dialog(None, -1, 'Create a new playlist', size = (500, 300), style = wx.RESIZE_BORDER|wx.DEFAULT_DIALOG_STYLE)
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
        if torrent_ids is not None:
            manager = self.GetManager()
            manager.savePlaylistTorrents(playlist.id, torrent_ids)
    
    def OnManage(self, playlist):
        dlg = wx.Dialog(None, -1, 'Manage the torrents for this playlist', size = (900, 500), style = wx.RESIZE_BORDER|wx.DEFAULT_DIALOG_STYLE)
        
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
        vSizer.Add(add)
        vSizer.Add(remove)
        sizer.Add(vSizer, 0, wx.ALIGN_CENTER_VERTICAL)
        
        sizer.Add(dlg.availableList, 1, wx.EXPAND)
        sizer.AddSpacer((1,1))
        sizer.AddSpacer((1,1))
        
        self.all = wx.RadioButton(dlg, -1, "Show all available torrents", style = wx.RB_GROUP )
        self.all.Bind(wx.EVT_RADIOBUTTON, self.OnRadio)
        self.all.dlg = dlg
        self.playlist = wx.RadioButton(dlg, -1, "Show only torrent not yet in a playlist" )
        self.playlist.Bind(wx.EVT_RADIOBUTTON, self.OnRadio)
        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.Add(self.all)
        vSizer.Add(self.playlist)
        sizer.Add(vSizer)
        
        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.Add(sizer, 1, wx.TOP|wx.LEFT|wx.RIGHT|wx.EXPAND, 10)
        vSizer.AddSpacer((1,3))
        vSizer.Add(dlg.CreateSeparatedButtonSizer(wx.OK|wx.CANCEL), 0, wx.EXPAND|wx.BOTTOM|wx.LEFT|wx.RIGHT, 10)
        
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
        except: #regex incorrect
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
            dlg.filtered_available =  None
        else:
            filtered_contents = dlg.not_in_playlist
            dlg.filtered_available =  None
            
        names = [torrent.name for torrent in filtered_contents]
        dlg.availableList.SetItems(names)
    
    def _rebuildLists(self, dlg):
        names = [torrent.name for torrent in dlg.selected]
        dlg.selectedList.SetItems(names)
        self._filterAvailable(dlg)

class AvantarItem(ListItem):
    def __init__(self, parent, parent_list, columns, data, original_data, leftSpacer = 0, rightSpacer = 0, showChange = False, list_selected = LIST_SELECTED):
        self.header = ''
        self.body = ''
        self.avantar = None
        self.additionalButtons = []
        self.maxlines = 6
        ListItem.__init__(self, parent, parent_list, columns, data, original_data, leftSpacer, rightSpacer, showChange, list_selected)
    
    def AddComponents(self, leftSpacer, rightSpacer):
        titleRow = wx.BoxSizer(wx.HORIZONTAL)
        if leftSpacer > 0:
            titleRow.AddSpacer((leftSpacer, -1))
        
        if self.avantar:
            titleRow.Add(wx.StaticBitmap(self, bitmap = self.avantar), 0, wx.RIGHT, 7)
        
        vSizer = wx.BoxSizer(wx.VERTICAL)
        
        header = wx.StaticText(self, -1, self.header)
        _set_font(header, -1, wx.FONTWEIGHT_BOLD)
        
        vSizer.Add(header, 0, wx.EXPAND)
        vSizer.Add(wx.StaticLine(self, -1, style = wx.LI_HORIZONTAL), 0, wx.EXPAND|wx.RIGHT, 5)
        
        self.moreButton = None
        if len(self.additionalButtons) > 0:
            self.moreButton = wx.Button(self, style = wx.BU_EXACTFIT)
            
        self.desc = MaxBetterText(self, self.body, maxLines = self.maxlines, button = self.moreButton)
        self.desc.SetMinSize((1, -1))
        vSizer.Add(self.desc, 0, wx.EXPAND)
        
        if len(self.additionalButtons) > 0:
            hSizer = wx.BoxSizer(wx.HORIZONTAL)
            hSizer.Add(self.moreButton, 0, wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
        
            for button in self.additionalButtons:
                hSizer.Add(button, 0, wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
                button.Show(False)
                
            self.moreButton.Show(False)
            vSizer.Add(hSizer, 0, wx.ALIGN_RIGHT)
        
        titleRow.Add(vSizer, 1)
        
        if rightSpacer > 0:
            titleRow.AddSpacer((rightSpacer, -1))
        self.vSizer.Add(titleRow, 0, wx.EXPAND|wx.TOP|wx.BOTTOM, 3)
        self.AddEvents(self)
        
    def BackgroundColor(self, color):
        changed = ListItem.BackgroundColor(self, color)
        
        if len(self.additionalButtons) > 0 and changed:
            if self.desc.hasMore:
                self.moreButton.Show(color == self.list_selected)
                
            for button in self.additionalButtons:
                button.Show(color == self.list_selected)
            
    def OnChange(self):
        self.parent_list.OnChange()
        
class CommentItem(AvantarItem):
    
    def __init__(self, parent, parent_list, columns, data, original_data, leftSpacer = 0, rightSpacer = 0, showChange = False, list_selected = LIST_SELECTED):
        #check if we are part of a torrent
        manager = parent_list.parent_list.GetManager()
        if manager.channeltorrent:
            self.inTorrent = True
        else:
            self.inTorrent = False
        
        comment = original_data
        self.canRemove = comment.isMyComment() or (comment.channel and comment.channel.isMyChannel())
        
        AvantarItem.__init__(self, parent, parent_list, columns, data, original_data, leftSpacer, rightSpacer, showChange, list_selected)
    
    def AddComponents(self, leftSpacer, rightSpacer):
        comment = self.original_data
        depth = self.data[0]
        
        self.header = "Posted %s by %s"%(format_time(comment.time_stamp).lower(), comment.name)
        self.body = comment.comment
        self.avantar = comment.avantar
        
        if depth == 0:
            if not self.inTorrent and comment.torrent:
                self.header += " in %s"%comment.torrent.name
                button = wx.Button(self, -1, 'Open Torrent', style = wx.BU_EXACTFIT)
                button.Bind(wx.EVT_BUTTON, self.ShowTorrent)
                self.additionalButtons.append(button)
        else:
            leftSpacer += depth * (self.avantar.GetWidth() + 7)  #avantar + spacer
            
        if self.canRemove:
            button = wx.Button(self, -1, 'Remove Comment', style = wx.BU_EXACTFIT)
            button.Bind(wx.EVT_BUTTON, self.RemoveComment)
            self.additionalButtons.append(button)
            
        AvantarItem.AddComponents(self, leftSpacer, rightSpacer)       
        
    def ShowTorrent(self, event):
        if self.original_data.torrent:
            self.parent_list.parent_list.OnShowTorrent(self.original_data.torrent)
    
    def RemoveComment(self, event):
        comment = self.original_data
        self.parent_list.parent_list.OnRemoveComment(comment)
        
        
class CommentActivityItem(CommentItem):
        
    def AddComponents(self, leftSpacer, rightSpacer):
        comment = self.original_data
        self.header = "New comment received, posted %s by %s"%(format_time(comment.time_stamp).lower(), comment.name)
        
        if not self.inTorrent and comment.torrent:
            self.header += " in %s"%comment.torrent.name
            button = wx.Button(self, -1, 'Open Torrent', style = wx.BU_EXACTFIT)
            button.Bind(wx.EVT_BUTTON, self.ShowTorrent)
            self.additionalButtons.append(button)
            
        self.body = comment.comment
        im = IconsManager.getInstance()
        self.avantar = im.get_default('COMMENT', SMALL_ICON_MAX_DIM)
        
        AvantarItem.AddComponents(self, leftSpacer, rightSpacer)  

class NewTorrentActivityItem(AvantarItem):
        
    def AddComponents(self, leftSpacer, rightSpacer):
        torrent = self.original_data
        
        self.header = "New torrent received at %s"%(format_time(torrent.time_stamp).lower())
        self.body = torrent.name
        
        button = wx.Button(self, -1, 'Open Torrent', style = wx.BU_EXACTFIT)
        button.Bind(wx.EVT_BUTTON, self.ShowTorrent)
        self.additionalButtons.append(button)
        
        im = IconsManager.getInstance()
        self.avantar = im.get_default('TORRENT_NEW', SMALL_ICON_MAX_DIM)
        AvantarItem.AddComponents(self, leftSpacer, rightSpacer)
        
    def ShowTorrent(self, event):
        if self.original_data:
            self.parent_list.parent_list.OnShowTorrent(self.original_data)

class TorrentActivityItem(AvantarItem):
        
    def AddComponents(self, leftSpacer, rightSpacer):
        torrent = self.original_data
        
        self.header = "Discovered a torrent at %s, injected at %s"%(format_time(torrent.inserted).lower(), format_time(torrent.time_stamp).lower())
        self.body = torrent.name
        
        button = wx.Button(self, -1, 'Open Torrent', style = wx.BU_EXACTFIT)
        button.Bind(wx.EVT_BUTTON, self.ShowTorrent)
        self.additionalButtons.append(button)
        
        im = IconsManager.getInstance()
        self.avantar = im.get_default('TORRENT', SMALL_ICON_MAX_DIM)
        AvantarItem.AddComponents(self, leftSpacer, rightSpacer)
        
    def ShowTorrent(self, event):
        if self.original_data:
            self.parent_list.parent_list.OnShowTorrent(self.original_data)
        
class ModificationActivityItem(AvantarItem):
        
    def AddComponents(self, leftSpacer, rightSpacer):
        modification = self.original_data

        self.header = "Discovered a modification by %s at %s"%(modification.peer_name, format_time(modification.inserted).lower())
        self.body = "Modified %s in '%s'"%(modification.name, modification.value)
        
        if modification.torrent:
            self.header += " for torrent '%s'"%modification.torrent.colt_name
            button = wx.Button(self, -1, 'Open Torrent', style = wx.BU_EXACTFIT)
            button.Bind(wx.EVT_BUTTON, self.ShowTorrent)
            self.additionalButtons.append(button)
        
        im = IconsManager.getInstance()
        self.avantar = im.get_default('MODIFICATION',SMALL_ICON_MAX_DIM)
        AvantarItem.AddComponents(self, leftSpacer, rightSpacer)
    
    def ShowTorrent(self, event):
        if self.original_data:
            self.parent_list.parent_list.OnShowTorrent(self.original_data.torrent)
        
class ModificationItem(AvantarItem):
    
    def __init__(self, parent, parent_list, columns, data, original_data, leftSpacer = 0, rightSpacer = 0, showChange = False, list_selected = LIST_SELECTED):
        if isinstance(parent, wx.Dialog):
            self.noButton = True
        else:
            self.noButton = False
        AvantarItem.__init__(self, parent, parent_list, columns, data, original_data, leftSpacer, rightSpacer, showChange, list_selected)
    
    def AddComponents(self, leftSpacer, rightSpacer):
        modification = self.original_data

        self.body = modification.value
        
        im = IconsManager.getInstance()
        if modification.moderation:
            moderation = modification.moderation
            self.header = "%s modified by %s,\nbut reverted by %s due to: '%s'"%(modification.name.capitalize(), modification.peer_name, moderation.peer_name, moderation.message)
            self.avantar = im.get_default('REVERTED_MODIFICATION',SMALL_ICON_MAX_DIM)
            self.maxlines = 2
        else:
            self.header = "%s modified by %s at %s"%(modification.name.capitalize(), modification.peer_name, format_time(modification.time_stamp).lower())
            self.avantar = im.get_default('MODIFICATION',SMALL_ICON_MAX_DIM)
        
            if not self.noButton:
                button = wx.Button(self, -1, 'Revert Modification', style = wx.BU_EXACTFIT)
                button.Bind(wx.EVT_BUTTON, self.RevertModification)
                self.additionalButtons.append(button)
        
        AvantarItem.AddComponents(self, leftSpacer, rightSpacer)
        
    def RevertModification(self, event):
        self.parent_list.parent_list.OnRevertModification(self.original_data)
        
class ModerationActivityItem(AvantarItem):
    
    def AddComponents(self, leftSpacer, rightSpacer):
        moderation = self.original_data

        self.header = "Discovered a moderation %s"%(format_time(moderation.inserted).lower())
        self.body = "%s reverted a modification made by %s, reason '%s'"%(moderation.peer_name, moderation.by_peer_name, moderation.message)
        
        im = IconsManager.getInstance()
        self.avantar = im.get_default('REVERTED_MODIFICATION',SMALL_ICON_MAX_DIM)
        AvantarItem.AddComponents(self, leftSpacer, rightSpacer)
        
class ModerationItem(AvantarItem):
    
    def AddComponents(self, leftSpacer, rightSpacer):
        moderation = self.original_data

        self.header = "%s reverted a modification by %s at %s"%(moderation.peer_name.capitalize(), moderation.by_peer_name, format_time(moderation.time_stamp).lower())
        
        if moderation.modification:
            modification = moderation.modification
            self.body = "%s reverted due to '%s'.\n"%(modification.name.capitalize(),moderation.message)
            if moderation.severity > 0:
                self.body += "%s additionally issued a warning!\n"%moderation.peer_name.capitalize()
            self.body += "Modification was:\n%s"%modification.value
            
            if modification.torrent:
                self.header += " for torrent '%s'"%modification.torrent.name
                button = wx.Button(self, -1, 'Open Torrent', style = wx.BU_EXACTFIT)
                button.Bind(wx.EVT_BUTTON, self.ShowTorrent)
                self.additionalButtons.append(button)
            
        else:
            self.body = moderation.message
        im = IconsManager.getInstance()
        self.avantar = im.get_default('REVERTED_MODIFICATION',SMALL_ICON_MAX_DIM)
        
        AvantarItem.AddComponents(self, leftSpacer, rightSpacer)
        
    def ShowTorrent(self, event):
        if self.original_data:
            self.parent_list.parent_list.OnShowTorrent(self.original_data.modification.torrent)
            
class MarkingActivityItem(AvantarItem):
    
    def AddComponents(self, leftSpacer, rightSpacer):
        marking = self.original_data

        self.header = "Discovered an opinion %s"%(format_time(marking.time_stamp).lower())
        self.body = "%s was marked as '%s'"%(marking.torrent.name, marking.type)
        
        button = wx.Button(self, -1, 'Open Torrent', style = wx.BU_EXACTFIT)
        button.Bind(wx.EVT_BUTTON, self.ShowTorrent)
        self.additionalButtons.append(button)
        
        im = IconsManager.getInstance()
        self.avantar = im.get_default('MARKING',SMALL_ICON_MAX_DIM)
        AvantarItem.AddComponents(self, leftSpacer, rightSpacer)       
        
    def ShowTorrent(self, event):
        if self.original_data:
            self.parent_list.parent_list.OnShowTorrent(self.original_data.torrent)     

class CommentManager:
    def __init__(self, list):
        self.list = list
        self.channelsearch_manager = GUIUtility.getInstance().channelsearch_manager
        
        self.Reset()
        
    def Reset(self):
        self.channel = None
        self.playlist = None
        self.channeltorrent = None
    
    def SetIds(self, channel = None, playlist = None, channeltorrent = None):
        changed = False
        
        if channel != self.channel:
            self.channel = channel
            self.list.header.SetTitle('Comments for this channel')
            
            changed = True
        
        if playlist != self.playlist:
            self.playlist = playlist
            self.list.header.SetTitle('Comments for this playlist')
            
            changed = True
            
        elif channeltorrent != self.channeltorrent:
            self.channeltorrent = channeltorrent
            self.list.header.SetTitle('Comments for this torrent')
            
            changed = True
        
        if changed: 
            self.do_or_schedule_refresh()
    
    def do_or_schedule_refresh(self, force_refresh = False):
        if self.list.isReady and (self.list.ShouldGuiUpdate() or force_refresh):
            self.refresh()
        else:
            self.list.dirty = True
    
    def refreshDirty(self):
        self.refresh()
    
    def refresh(self):
        def db_callback():
            self.list.dirty = False
            
            if self.playlist:
                return self.channelsearch_manager.getCommentsFromPlayList(self.playlist)
            if self.channeltorrent:
                return self.channelsearch_manager.getCommentsFromChannelTorrent(self.channeltorrent)
            return self.channelsearch_manager.getCommentsFromChannel(self.channel)

        startWorker(self.list.SetDelayedData, db_callback, retryOnBusy=True)
            
    def new_comment(self):
        self.do_or_schedule_refresh()
    
    def addComment(self, comment):
        item = self.list.GetExpandedItem()
        if item:
            reply_to = item.original_data.dispersy_id
        else:
            reply_to = None
        
        reply_after = None
        items = self.list.GetItems().values()
        if len(items) > 0:
            reply_after = items[-1].original_data.dispersy_id
            
        def db_callback():
            if self.playlist:
                self.channelsearch_manager.createComment(comment, self.channel, reply_to, reply_after, playlist = self.playlist)
            elif self.channeltorrent:
                self.channelsearch_manager.createComment(comment, self.channel, reply_to, reply_after, infohash = self.channeltorrent.infohash)
            else:
                self.channelsearch_manager.createComment(comment, self.channel, reply_to, reply_after)
        startWorker(workerFn=db_callback, retryOnBusy=True)
            
    def removeComment(self, comment):
        self.channelsearch_manager.removeComment(comment, self.channel)

class CommentList(List):
    def __init__(self, parent, parent_list, canReply = False, quickPost = False):
        if quickPost:
            self.quickPost = self.OnThankYou
        else:
            self.quickPost = None
            
        List.__init__(self, [], LIST_GREY, [7,7], parent = parent, singleSelect = True, borders = False)
        self.parent_list = parent_list
        self.canReply = canReply
    
    def CreateHeader(self, parent):
        return TitleHeader(parent, self, [], 0, radius = 0,spacers = [4,7])
    
    def CreateFooter(self, parent):
        return CommentFooter(parent, self.OnNew, self.quickPost)

    def GetManager(self):
        if getattr(self, 'manager', None) == None:
            self.manager = CommentManager(self) 
        return self.manager
    
    @forceWxThread
    def SetData(self, data):
        List.SetData(self, data)
        
        listData = []
        def addComments(comment, depth):
            listData.append((comment.id, [depth], comment, CommentItem))
            for reply in comment.replies:
                addComments(reply, depth+1)
        
        for comment in data:
            addComments(comment, 0)
        
        if len(listData) > 0:
            self.list.SetData(listData)
        else:
            self.list.ShowMessage('No comments are found.')
        self.SetNrResults(len(listData))
    
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
        
    def OnShowTorrent(self, torrent):
        self.parent_list.Select(torrent)
        
    def OnRemoveComment(self, comment):
        self.GetManager().removeComment(comment)

class ActivityManager:
    def __init__(self, list):
        self.list = list
        self.channelsearch_manager = GUIUtility.getInstance().channelsearch_manager
        
        self.Reset()
        
    def Reset(self):
        self.channel = None
        self.playlist = None
        self.channeltorrent = None
        
    def SetIds(self, channel = None, playlist = None):
        if channel != self.channel:
            self.channel = channel
            self.list.dirty = True
            
            self.list.header.SetTitle('Recent activity in this Channel')
        
        if playlist != self.playlist:
            self.playlist = playlist
            self.list.dirty = True
            
            self.list.header.SetTitle('Recent activity in this Playlist')
    
    def do_or_schedule_refresh(self, force_refresh = False):
        if self.list.isReady and (self.list.ShouldGuiUpdate() or force_refresh):
            self.refresh()
        else:
            self.list.dirty = True
    
    def refreshDirty(self):
        self.refresh()
    
    def refresh(self):
        def db_callback():
            self.list.dirty = False
            
            if self.playlist:
                commentList = self.channelsearch_manager.getCommentsFromPlayList(self.playlist, limit = 10)
                nrTorrents, _, torrentList = self.channelsearch_manager.getTorrentsFromPlaylist(self.playlist, limit = 10)
                nrRecentTorrents, _, recentTorrentList = self.channelsearch_manager.getRecentTorrentsFromPlaylist(self.playlist, limit = 10)
                recentModifications = self.channelsearch_manager.getRecentModificationsFromPlaylist(self.playlist, limit = 10)
                recentModerations = self.channelsearch_manager.getRecentModerationsFromPlaylist(self.playlist, limit = 10)
                recent_markings = self.channelsearch_manager.getRecentMarkingsFromPlaylist(self.playlist, limit = 10)
            else:
                commentList = self.channelsearch_manager.getCommentsFromChannel(self.channel, limit = 10)
                nrTorrents, _, torrentList = self.channelsearch_manager.getTorrentsFromChannel(self.channel, limit = 10)
                nrRecentTorrents, _, recentTorrentList = self.channelsearch_manager.getRecentReceivedTorrentsFromChannel(self.channel, limit = 10)
                recentModifications = self.channelsearch_manager.getRecentModificationsFromChannel(self.channel, limit = 10)
                recentModerations = self.channelsearch_manager.getRecentModerationsFromChannel(self.channel, limit = 10)
                recent_markings = self.channelsearch_manager.getRecentMarkingsFromChannel(self.channel, limit = 10)
            
            return torrentList, recentTorrentList, commentList, recentModifications, recentModerations, recent_markings
        
        def do_gui(delayedResult):
            torrentList, recentTorrentList, commentList, recentModifications, recentModerations, recent_markings = delayedResult.get()
            
            self.channelsearch_manager.populateWithPlaylists(torrentList)
            self.channelsearch_manager.populateWithPlaylists(recentTorrentList)
            self.list.SetData(commentList, torrentList, recentTorrentList, recentModifications, recentModerations, recent_markings)
        
        startWorker(do_gui, db_callback, retryOnBusy=True)
        
    def new_activity(self):
        self.do_or_schedule_refresh()

class ActivityList(List):
    def __init__(self, parent, parent_list):
        List.__init__(self, [], LIST_GREY, [7,7], parent = parent, singleSelect = True, borders = False)
        self.parent_list = parent_list
        self.channelsearch_manager = GUIUtility.getInstance().channelsearch_manager
    
    def CreateHeader(self, parent):
        return TitleHeader(parent, self, [], 0, radius = 0, spacers = [4,7])
    
    def CreateFooter(self, parent):
        return None

    def GetManager(self):
        if getattr(self, 'manager', None) == None:
            self.manager = ActivityManager(self) 
        return self.manager
    
    @forceWxThread
    def SetData(self, comments, recent_torrents, recent_received_torrents, recent_modifications, recent_moderations, recent_markings):
        List.SetData(self, recent_torrents)
        
        #remove duplicates
        recent_torrent_infohashes = set([torrent.infohash for torrent in recent_torrents])
        recent_received_torrents = [torrent for torrent in recent_received_torrents if torrent.infohash not in recent_torrent_infohashes]
        
        #first element must be timestamp, allows for easy sorting
        data =  [(comment.inserted, ("COMMENT_%d"%comment.id, (), comment, CommentActivityItem)) for comment in comments]
        data += [(torrent.inserted, (torrent.infohash, (), torrent, NewTorrentActivityItem)) for torrent in recent_torrents]
        data += [(torrent.inserted, (torrent.infohash, (), torrent, TorrentActivityItem)) for torrent in recent_received_torrents]
        data += [(modification.inserted, ("MODIFICATION_%d"%modification.id, (), modification, ModificationActivityItem)) for modification in recent_modifications]
        data += [(modification.inserted, ("MODERATION_%d"%moderation.id, (), moderation, ModerationActivityItem)) for moderation in recent_moderations]
        data += [(marking.time_stamp, (marking.dispersy_id, (), marking, MarkingActivityItem)) for marking in recent_markings]
        data.sort(reverse = True)
        
        #removing timestamp
        data = [item for _, item in data]
        if len(data) > 0:
            self.list.SetData(data)
        else:
            self.list.ShowMessage('No recent activity is found.')
            
    def OnShowTorrent(self, torrent):
        self.parent_list.Select(torrent)

class ModificationManager:
    def __init__(self, list):
        self.list = list
        self.channelsearch_manager = GUIUtility.getInstance().channelsearch_manager
        
        self.Reset()
        
    def Reset(self):
        self.torrent = None
        
    def SetIds(self, channeltorrent):
        if channeltorrent != self.torrent:
            self.torrent = channeltorrent
            
            self.do_or_schedule_refresh()
    
    def do_or_schedule_refresh(self, force_refresh = False):
        if self.list.isReady and (self.list.ShouldGuiUpdate() or force_refresh):
            self.refresh()
        else:
            self.list.dirty = True
    
    def refreshDirty(self):
        self.refresh()
    
    def refresh(self):
        def db_callback():
            self.list.dirty = False
            return self.channelsearch_manager.getTorrentModifications(self.torrent)
        
        startWorker(self.list.SetDelayedData, db_callback, retryOnBusy=True)
        
    def new_modification(self):
        self.do_or_schedule_refresh()
    
    def OnRevertModification(self, modification, reason, warning = False):
        severity = 1 if warning else 0
        self.channelsearch_manager.revertModification(self.torrent.channel, modification, reason, severity, None)

class ModificationList(List):
    def __init__(self, parent):
        List.__init__(self, [], LIST_GREY, [7,7], parent = parent, singleSelect = True, borders = False)
        self.header.SetTitle('Modifications of this torrent')
    
    def CreateHeader(self, parent):
        return TitleHeader(parent, self, [], 0, radius = 0, spacers = [4,7])
    
    def CreateFooter(self, parent):
        return None

    def GetManager(self):
        if getattr(self, 'manager', None) == None:
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
        self.SetNrResults(len(data))
        
    def OnRevertModification(self, modification):
        dlg = wx.Dialog(None, -1, 'Revert this modification', size = (700, 400), style = wx.RESIZE_BORDER|wx.DEFAULT_DIALOG_STYLE)
        dlg.SetBackgroundColour(DEFAULT_BACKGROUND)
        vSizer = wx.BoxSizer(wx.VERTICAL)
        
        vSizer.Add(ModificationItem(dlg, dlg, '', '', modification, list_selected = DEFAULT_BACKGROUND), 0, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, 7)
        dlg.OnExpand = lambda a: False
        dlg.OnChange = vSizer.Layout 
        
        why = StaticText(dlg, -1, 'Why do you want to revert this modification?')
        _set_font(why, fontweight=wx.FONTWEIGHT_BOLD)
        ori_why_colour = why.GetForegroundColour()
        vSizer.Add(why, 0, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, 7)
        
        reason = wx.TextCtrl(dlg, -1, style = wx.TE_MULTILINE)
        reason.SetMinSize((-1, 50))
        vSizer.Add(reason, 1, wx.EXPAND|wx.LEFT|wx.RIGHT, 7)
        
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
        vSizer.Add(buttonSizer, 0, wx.ALIGN_RIGHT|wx.LEFT|wx.RIGHT|wx.BOTTOM|wx.TOP, 7)
        
        dlg.SetSizer(vSizer)
        id = dlg.ShowModal()
        if id == revertAndWarn.GetId():
            self.GetManager().OnRevertModification(modification, reason.GetValue(), warning = True)
        elif id == revert.GetId():
            self.GetManager().OnRevertModification(modification, reason.GetValue())    
            
        dlg.Destroy()        
        
class ModerationManager:
    def __init__(self, list):
        self.list = list
        self.channelsearch_manager = GUIUtility.getInstance().channelsearch_manager
        
        self.Reset()
        
    def Reset(self):
        self.channel = None
        self.playlist = None
        self.channeltorrent = None
        
    def SetIds(self, channel = None, playlist = None):
        changed = False
        if channel != self.channel:
            self.channel = channel
            self.list.header.SetTitle('Recent moderations for this Channel')
            
            changed = True
        
        if playlist != self.playlist:
            self.playlist = playlist
            self.list.header.SetTitle('Recent moderations for this Playlist')
            
            changed = True
        
        if changed:    
            self.do_or_schedule_refresh()
    
    def do_or_schedule_refresh(self, force_refresh = False):
        if self.list.isReady and (self.list.ShouldGuiUpdate() or force_refresh):
            self.refresh()
        else:
            self.list.dirty = True
    
    def refreshDirty(self):
        self.refresh()
    
    def refresh(self):
        def db_callback():
            self.list.dirty = False
            if self.playlist:
                return self.channelsearch_manager.getRecentModerationsFromPlaylist(self.playlist, 25)
            return self.channelsearch_manager.getRecentModerationsFromChannel(self.channel, 25)
        
        startWorker(self.list.SetDelayedData, db_callback, retryOnBusy=True)
        
    def new_moderation(self):
        self.do_or_schedule_refresh()

class ModerationList(List):
    def __init__(self, parent, parent_list):
        List.__init__(self, [], LIST_GREY, [7,7], parent = parent, singleSelect = True, borders = False)
        self.parent_list = parent_list
    
    def CreateHeader(self, parent):
        return TitleHeader(parent, self, [], 0, radius = 0)
    
    def CreateFooter(self, parent):
        return None

    def GetManager(self):
        if getattr(self, 'manager', None) == None:
            self.manager = ModerationManager(self) 
        return self.manager
    
    @forceWxThread
    def SetData(self, data):
        List.SetData(self, data)
        data = [(moderation.id, (), moderation, ModerationItem) for moderation in data]
        
        if len(data) > 0:
            self.list.SetData(data)
        else:
            self.list.ShowMessage('No moderations are found.')
        self.SetNrResults(len(data))
        
    def OnShowTorrent(self, torrent):
        self.parent_list.Select(torrent)
