# Written by Niels Zeilemaker
import wx

from Tribler.Main.vwxGUI.GuiUtility import GUIUtility, forceDBThread
from Tribler.Main.vwxGUI.tribler_topButton import _set_font, MaxBetterText, NotebookPanel
from Tribler.Core.API import *

from list import *
from list_footer import *
from list_header import *
from list_body import *
from list_details import *
from __init__ import *
from Tribler.Main.Utility.GuiDBHandler import startWorker
from Tribler.Main.vwxGUI.IconsManager import IconsManager, SMALL_ICON_MAX_DIM
from Tribler.community.channel.community import ChannelCommunity
from Tribler.Main.Utility.GuiDBTuples import Torrent
from Tribler.Main.Utility.Rss.rssparser import RssParser
from wx.lib.agw.flatnotebook import FlatNotebook
import wx.lib.agw.flatnotebook as fnb
from wx._controls import StaticLine

DEBUG = False

class ChannelManager():
    def __init__(self, list):
        self.list = list
        self.list.SetId(0)
        self.dirtyset = set()
        
        self.guiutility = GUIUtility.getInstance()
        self.channelsearch_manager = self.guiutility.channelsearch_manager
        self.library_manager = self.guiutility.library_manager
    
    def Reset(self):
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
        
        startWorker(do_gui, db_callback, uId = "ChannelManager_refresh_list")
    
    @forceWxThread
    def _on_data(self, total_items, nrfiltered, torrents, playlists):
        torrents = self.library_manager.addDownloadStates(torrents)
        total_items += len(playlists)
        
        #only show a small random selection of available content for non-favorite channels
        if not self.list.channel.isFavorite() and not self.list.channel.isMyChannel():
            if len(playlists) > 3:
                playlists = sample(playlists, 3)
                
            if len(torrents) > CHANNEL_MAX_NON_FAVORITE:
                torrents = sample(torrents, CHANNEL_MAX_NON_FAVORITE)
            
            total_items = len(playlists) + len(torrents)
        
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
             
    def channelUpdated(self, id, stateChanged = False, modified = False):
        if self.list.id == id:
            if modified:
                self.reload(id)
            else:
                if self.list.ShouldGuiUpdate():
                    self._refresh_list(stateChanged)
                else:
                    key = 'COMPLETE_REFRESH'
                    if stateChanged:
                        key += '_STATE'
                    self.dirtyset.add(key)
                    self.list.dirty = True
    
    def playlistUpdated(self, playlist_id):
        if self.list.InList(playlist_id):
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
        
        columns = [{'name':'Name', 'width': wx.LIST_AUTOSIZE, 'sortAsc': True, 'icon': 'tree'}, \
                   {'name':'Date Added', 'width': 85, 'fmt': format_time, 'defaultSorted': True}, \
                   {'name':'Size', 'width':  '9em', 'style': wx.ALIGN_RIGHT, 'fmt': format_size}, \
                   {'type':'method', 'width': wx.LIST_AUTOSIZE_USEHEADER, 'method': self.CreateRatio, 'name':'Popularity'}, \
                   {'type':'method', 'width': LIST_AUTOSIZEHEADER, 'method': self.CreateDownloadButton}]
        
        GenericSearchList.__init__(self, columns, LIST_GREY, [6,6], True, borders = False, showChange = True, parent = parent)
    
    @warnWxThread
    def _PostInit(self):
        self.header = ChannelHeader(self.parent, self, [])
        self.header.SetEvents(self.OnBack)
        self.Add(self.header, 0, wx.EXPAND)
        
        self.leftLine = wx.Panel(self.parent)

        self.notebook = FlatNotebook(self.leftLine)
        if getattr(self.notebook, 'SetAGWWindowStyleFlag', False):
            self.notebook.SetAGWWindowStyleFlag(fnb.FNB_HIDE_ON_SINGLE_TAB|fnb.FNB_NO_X_BUTTON|fnb.FNB_NO_NAV_BUTTONS)
        else:
            self.notebook.SetWindowStyleFlag(fnb.FNB_HIDE_ON_SINGLE_TAB|fnb.FNB_NO_X_BUTTON|fnb.FNB_NO_NAV_BUTTONS)
        self.notebook.SetTabAreaColour(self.background)
        self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.OnChange)
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.notebook, 1, wx.EXPAND|wx.TOP|wx.LEFT|wx.RIGHT,1)
        sizer.Add(StaticLine(self.leftLine, -1), 0, wx.EXPAND)
        self.leftLine.SetSizer(sizer)
        
        list = wx.Panel(self.notebook)
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
        self.commentList.SetList(CommentList(self.commentList, self))
        
        self.activityList = NotebookPanel(self.notebook)
        self.activityList.SetList(ActivityList(self.activityList, self))
        
        self.moderationList = NotebookPanel(self.notebook)
        self.moderationList.SetList(ModerationList(self.moderationList, self))
        
        self.Add(self.leftLine, 1, wx.EXPAND)
        
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
    def SetChannel(self, channel):
        self.channel = channel
        
        self.Freeze()
        self.SetId(channel.id)
        self.SetTitle(channel.name, channel.description)
        
        nr_torrents = channel.nr_torrents
        if not channel.isFavorite() and not channel.isMyChannel():
            nr_torrents = min(nr_torrents, 50)
        self.SetNrResults(nr_torrents)
        
        if channel.isDispersy():
            startWorker(self.SetState, self.channel.getState)
        else:
            self.SetChannelState(ChannelCommunity.CHANNEL_CLOSED, self.my_channel)
        self.Thaw()
    
    def SetId(self, id):
        self.id = id
        if id > 0:
            self.my_channel = self.channel.isMyChannel()
        
            manager = self.commentList.GetManager()
            manager.SetIds(channel = self.channel)
            
            manager = self.activityList.GetManager()
            manager.SetIds(channel = self.channel)
            
            manager = self.moderationList.GetManager()
            manager.SetIds(channel = self.channel)
    
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
        if state >= ChannelCommunity.CHANNEL_SEMI_OPEN:
            if self.notebook.GetPageCount() == 1:
                self.commentList.Show(True)
                self.activityList.Show(True)
                self.moderationList.Show(True)
                
                self.notebook.AddPage(self.commentList, "Comments")
                self.notebook.AddPage(self.activityList, "Activity")
                self.notebook.AddPage(self.moderationList, "Moderations")
        else:
            self.commentList.Show(False)
            self.activityList.Show(False)
            self.moderationList.Show(False)
            
            for i in range(self.notebook.GetPageCount(), 1, -1):
                self.notebook.RemovePage(i-1)

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
            
            shouldDrag = len(playlists) > 0 and (self.iamModerator or self.channel.getState == ChannelCommunity.CHANNEL_OPEN)
            if shouldDrag:
                data += [(torrent.infohash,[torrent.name, torrent.time_stamp, torrent.length, 0, 0], torrent, DragItem) for torrent in torrents]
            else:
                data += [(torrent.infohash,[torrent.name, torrent.time_stamp, torrent.length, 0, 0], torrent) for torrent in torrents]
            self.list.SetData(data)
            
            self.SetNrResults(len(data))
        else:
            header =  'No torrents or playlists found.'
            message = 'As this is an "open" channel, you can add your own torrents to share them with others in this channel'
            self.list.ShowMessage(message, header = header)
            
            self.SetNrResults(0)
    
    @warnWxThread
    def SetNrResults(self, nr):
        if self.channel.isFavorite() or self.channel.isMyChannel():
            header = 'Discovered'
        else:
            header = 'Previewing'
            
        if nr == 1:
            self.header.SetSubTitle(header+ ' %d torrent'%nr)
        else:
            if self.channel.isFavorite():
                self.header.SetSubTitle(header+' %d torrents'%nr)
            else:
                self.header.SetSubTitle(header+' %d torrents'%nr)
    
    @forceWxThread
    def RefreshData(self, key, data):
        List.RefreshData(self, key, data)
        
        if data:
            if isinstance(data, Torrent):
                if self.channel.getState == ChannelCommunity.CHANNEL_OPEN or self.iamModerator:
                    data = (data.infohash,[data.name, data.time_stamp, data.length, 0, 0], data, DragItem)
                else:
                    data = (data.infohash,[data.name, data.time_stamp, data.length, 0, 0], data)
            else:
                data = (data.id,[data.name, data.extended_description, data.nr_torrents], data, PlaylistItem)
            self.list.RefreshData(key, data)
        
        item = self.list.GetItem(key)
        panel = item.GetExpandedPanel()
        if panel:
            panel.UpdateStatus()
        
        manager = self.activityList.GetManager()
        manager.do_or_schedule_refresh()
    
    @warnWxThread
    def Reset(self):
        GenericSearchList.Reset(self)
        self.SetId(0)
        self.notebook.SetSelection(0)
    
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
                        self.OnSaveTorrent(panel)
                    dlg.Destroy()
            GenericSearchList.OnCollapse(self, item, panel)
    
    @warnWxThread
    def OnSaveTorrent(self, panel):
        changes = panel.GetChanged()
        if len(changes)>0:
            self.channelsearch_manager.modifyTorrent(self.id, panel.torrent.channeltorrent_id, changes)
            panel.Saved()
    
    @forceDBThread  
    def AddTorrent(self, playlist, torrent):
        def gui_call():
            manager = self.GetManager()
            manager._refresh_list()
            
        self.channelsearch_manager.addPlaylistTorrent(playlist, torrent)
        wx.CallAfter(gui_call)
    
    @forceDBThread
    def OnRemoveVote(self, event):
        #Set self.id to None to prevent updating twice
        id = self.id
        self.id = None
        
        self.channelsearch_manager.remove_vote(id)
        
        manager = self.GetManager()
        wx.CallAfter(manager.reload,id)
    
    @forceDBThread
    def OnFavorite(self, event = None):
        #Set self.id to None to prevent updating twice
        id = self.id
        self.id = None
        
        self.channelsearch_manager.favorite(id)
        
        #Request all items from connected peers
        if not self.channel.isDispersy():
            permid = self.channelsearch_manager.getPermidFromChannel(id)
            channelcast = BuddyCastFactory.getInstance().channelcast_core
            channelcast.updateAChannel(self.id, permid)

        self.uelog.addEvent(message="ChannelList: user marked a channel as favorite", type = 2)
        
        manager = self.GetManager()
        wx.CallAfter(manager.reload, id)
    
    @warnWxThread
    def OnSpam(self, event):
        dialog = wx.MessageDialog(None, "Are you sure you want to report %s's channel as spam?" % self.title, "Report spam", wx.ICON_QUESTION | wx.YES_NO | wx.NO_DEFAULT)
        if dialog.ShowModal() == wx.ID_YES:
            #Set self.id to None to prevent updating twice
            id = self.id
            self.id = None
            
            def db_call():
                self.channelsearch_manager.spam(id)
                self.uelog.addEvent(message="ChannelList: user marked a channel as spam", type = 2)
                 
            def gui_call(delayedResult):
                delayedResult.get()
                self.GetManager().reload(id)
                
            startWorker(gui_call, db_call)
        dialog.Destroy()
    
    @warnWxThread
    def OnManage(self, event):
        self.guiutility.showManageChannel(self.channel)
    
    @warnWxThread
    def OnBack(self, event):
        self.guiutility.GoBack(self.id)
    
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
        if channel_id == self.id:
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
        if channel_id == self.id:
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
        if channel_id == self.id:
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
    def OnMarkTorrent(self, infohash, type):
        self.channelsearch_manager.markTorrent(self.id, infohash, type)
    
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
        
        self.notebook.SetSelection(0)
        self.ScrollToId(key)
    
    @forceDBThread
    def StartDownload(self, torrent, files = None):
        if not self.channel.isFavorite():
            nrdownloaded = self.channelsearch_manager.getNrTorrentsDownloaded(self.id) + 1
            if  nrdownloaded > 1:
                wx.CallAfter(self._ShowFavoriteDialog, nrdownloaded)
        
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
        #event.LeftDown does not work
        mouse = wx.GetMouseState()
        if mouse.LeftDown():
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
        self.list.id = 0
        
        self.guiutility = GUIUtility.getInstance()
        self.library_manager = self.guiutility.library_manager
        self.channelsearch_manager = self.guiutility.channelsearch_manager
    
    def SetPlaylist(self, playlist):
        if playlist.id != self.list.id:
            self.list.Reset()
            self.list.id = playlist.id
            self.list.playlist = playlist
            
            self.list.SetChannel(playlist.channel)
        
        self._refresh_list()
    
    def refreshDirty(self):
        self._refresh_list()
    
    def _refresh_list(self):
        def db_call():
            self.list.dirty = False
            return self.channelsearch_manager.getTorrentsFromPlaylist(self.list.playlist)
            
        startWorker(self._on_data, db_call, uId = "PlaylistManager_refresh_list")
        
    def _on_data(self, delayedResult):
        total_items, nrfiltered, torrents = delayedResult.get()
        torrents = self.library_manager.addDownloadStates(torrents)
        
        self.list.SetData([], torrents)
        self.list.SetFF(self.guiutility.getFamilyFilter(), nrfiltered)

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
        self.notebook.SetSelection(0)
    
    def SetTitle(self, title, description):
        header = u"%s's channel \u2192 %s"%(self.channel.name, self.playlist.name) 
        
        self.header.SetTitle(header)
        self.header.SetStyle(self.playlist.description)
        self.Layout()
    
    def SetId(self, id):
        if id != 0:
            manager = self.commentList.GetManager()
            manager.SetIds(channel = self.playlist.channel, playlist = self.playlist)
            
            manager = self.activityList.GetManager()
            manager.SetIds(channel = self.playlist.channel, playlist = self.playlist)
            
            manager = self.moderationList.GetManager()
            manager.SetIds(channel = self.playlist.channel, playlist = self.playlist)
            
    def OnCommentCreated(self, key):
        SelectedChannelList.OnCommentCreated(self, key)
        
        if self.InList(key):
            manager = self.commentList.GetManager()
            manager.new_comment()
            
    def CreateFooter(self, parent):
        return PlaylistFooter(parent)
        
class PlaylistItem(ListItem):
    def __init__(self, parent, parent_list, columns, data, original_data, leftSpacer = 0, rightSpacer = 0, showChange = False, list_selected = LIST_SELECTED):
        ListItem.__init__(self, parent, parent_list, columns, data, original_data, leftSpacer, rightSpacer, showChange, list_selected)
        
        self.SetDropTarget(TorrentDT(original_data, parent_list.parent_list.AddTorrent))
        
    def AddComponents(self, leftSpacer, rightSpacer):
        titleRow = wx.BoxSizer(wx.HORIZONTAL)
        if leftSpacer > 0:
            titleRow.AddSpacer((leftSpacer, -1))
        
        self.icontype = 'tree'
        self.expandedState = wx.StaticBitmap(self, -1, self.GetIcon(LIST_DESELECTED, 0))
        titleRow.Add(self.expandedState, 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 3)
        
        self.title = wx.StaticText(self, -1, self.data[0], style = wx.ST_NO_AUTORESIZE|wx.ST_DOTS_END)
        self.title.SetMinSize((1, -1))
        _set_font(self.title, fontweight = wx.FONTWEIGHT_BOLD)
        
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
            return self.channelsearch_manager.getTorrentsFromChannel(self.list.channel, filterTorrents = False)
        
        startWorker(self._on_data, db_call, uId = "ManageChannelFilesManager_refresh")
        
    def _on_data(self, delayedResult):
        total_items, nrfiltered, torrentList = delayedResult.get()
        self.list.SetData(torrentList)
    
    def SetChannel(self, channel):
        if channel != self.list.channel:
            self.list.id = channel.id
            self.list.channel = channel
            self.list.dirty = True
    
    def RemoveItems(self, infohashes):
        for infohash in infohashes:
            self.channelsearch_manager.removeTorrent(self.list.channel, infohash)
                
    def RemoveAllItems(self):
        self.channelsearch_manager.removeAllTorrents(self.list.channel)
        
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
    
    def startDownload(self, filename, *args, **kwargs):
        try:
            tdef = TorrentDef.load(filename)
            return self.AddTDef(tdef)
        except:
            return False
        
    def startDownloadFromTorrent(self, torrent):
        self.channelsearch_manager.createTorrent(self.list.channel, torrent)
        return True
        
    def AddTDef(self, tdef):
        if tdef:
            self.channelsearch_manager.createTorrentFromDef(self.list.id, tdef)
            return True
        return False
        
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
            _, playlistList = self.channelsearch_manager.getPlaylistsFromChannel(self.list.channel)
            return playlistList
        
        startWorker(self.list.SetDelayedData, db_call, uId = "ManageChannelPlaylistsManager_refresh")
       
    def _refresh_partial(self, playlist_id):
        startWorker(self.list.RefreshDelayedData, self.channelsearch_manager.getPlaylist, wargs=(self.list.channel, playlist_id), cargs = (playlist_id,))
    
    def SetChannel(self, channel):
        if channel != self.list.channel:
            self.list.id = channel.id
            self.list.channel = channel
            self.list.dirty = True
    
    def GetTorrentsFromChannel(self):
        delayedResult = startWorker(None, self.channelsearch_manager.getTorrentsFromChannel, wargs = (self.list.channel,), wkwargs = {'filterTorrents' : False})
        total_items, nrfiltered, torrentList = delayedResult.get()
        return torrentList
        
    def GetTorrentsFromPlaylist(self, playlist):
        delayedResult = startWorker(None, self.channelsearch_manager.getTorrentsFromPlaylist, wargs = (playlist,), wkwargs = {'filterTorrents' : False})
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
            self._refresh_partial(playlist_id)

class ManageChannel(XRCPanel, AbstractDetails):

    def _PostInit(self):
        self.channel = None
        self.channel_id = 0
        
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
    
    @forceWxThread
    def SetChannel(self, channel):
        self.fileslist.GetManager().SetChannel(channel)
        self.playlistlist.GetManager().SetChannel(channel)
        
        if channel:
            self.channel = channel
            self.channel_id = channel.id
            
            def db_call():
                channel_state, iamModerator = self.channelsearch_manager.getChannelState(channel.id)
                return channel_state, iamModerator
            
            def update_panel(delayedResult):
                channel_state, iamModerator = delayedResult.get() 
                
                name = channel.name
                self.name.SetValue(name)
                self.name.originalValue = name

                description = channel.description
                self.description.SetValue(description)
                self.description.originalValue = description
                
                self.header.SetName('Management interface for %s\'s Channel'%name)
                self.header.SetNrTorrents(channel.nr_torrents, channel.nr_favorites)
                
                self.createText.Hide()
                self.saveButton.SetLabel('Save Changes')
                
                if iamModerator:
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
                else:
                    self.RemovePage(self.notebook, "Manage torrents")
                
                if iamModerator:
                    self.AddPage(self.notebook, self.playlistlist, "Manage playlists", 3)
                    
                    self.RebuildRssPanel()
                    self.AddPage(self.notebook, self.managepage, "Manage", 4)
                else:
                    self.RemovePage(self.notebook, "Manage playlists")
                    self.RemovePage(self.notebook, "Manage")
                    
            startWorker(update_panel, db_call)
            
        else:
            self.channel = None
            self.channel_id = 0
            
            self.name.SetValue('')
            self.name.originalValue = ''
            
            self.description.SetValue('')
            self.description.originalValue = ''
            
            self.header.SetName('Create your own channel')
            self.header.SetNrTorrents(0, 0)
                
            self.createText.Show()
            self.saveButton.SetLabel('Create Channel')
            
            self.AddPage(self.notebook, self.overviewpage, "Overview", 0)
            #disable all other tabs
            for i in range(1, self.notebook.GetPageCount()):
                self.notebook.RemovePage(i)
    
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
            index = min(notebook.GetPageCount(), index)
            notebook.InsertPage(index, page, title)
            page.Show(True)
    
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
            self.fileslist.Show()
            self.fileslist.SetFocus()
        
        elif page == self.GetPage(self.notebook, "Manage playlists"):
            self.playlistlist.Show()
            self.playlistlist.SetFocus() 
        event.Skip()
    
    def OnBack(self, event):
        self.guiutility.GoBack()
    
    def OnAddRss(self, event):
        item = event.GetEventObject()
        url = item.url.GetValue().strip()
        if len(url) > 0:
            self.torrentfeed.addURL(url, self.channel_id)
            self.RebuildRssPanel()
            
            self.uelog.addEvent(message="MyChannel: rssfeed added", type = 2)
        
    def OnDeleteRss(self, event):
        item = event.GetEventObject()
        
        self.torrentfeed.deleteURL(item.url, self.channel_id)
        self.RebuildRssPanel()
        
        self.uelog.addEvent(message="MyChannel: rssfeed removed", type = 2)
    
    def OnRefreshRss(self, event):
        self.torrentfeed.doRefresh()
        
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
            
    def CreateJoinChannelFile(self):
        f = open('joinchannel', 'wb')
        f.write(self.channel.dispersy_cid)
        f.close()
    
    def _import_torrents(self, files):
        tdefs = [TorrentDef.load(file) for file in files if file.endswith(".torrent")]
        self.channelsearch_manager.createTorrentsFromDefs(self.channel_id, tdefs)
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
        if self.channel_id:
            changes = {}
            if self.name.IsChanged():
                changes['name'] = self.name.GetValue()
            if self.description.IsChanged():
                changes['description'] = self.description.GetValue()
            
            self.channelsearch_manager.modifyChannel(self.channel_id, changes)
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
        startWorker(None, self.channelsearch_manager.setChannelState, wargs = (self.channel_id, state))
        
        button = event.GetEventObject()
        button.Enable(False)
        wx.CallLater(5000, button.Enable, True)
    
    def playlistCreated(self, channel_id):
        if channel_id == self.channel_id:
            manager = self.playlistlist.GetManager()
            manager.refresh_list()
        
    def playlistUpdated(self, playlist_id):
        manager = self.playlistlist.GetManager()
        manager.playlistUpdated(playlist_id)
        
    def channelUpdated(self, channel_id, created = False, modified = False):
        if channel_id == self.channel_id:
            manager = self.fileslist.GetManager()
            manager.refresh_list()
            
            if modified:
                self.SetChannelId(channel_id)
                
        elif not self.channel_id and created:
            self.SetChannelId(channel_id)
            
class ManageChannelFilesList(List):
    def __init__(self, parent):
        self.channel = None
        columns = [{'name':'Name', 'width': wx.LIST_AUTOSIZE, 'icon': 'checkbox', 'sortAsc': True}, \
                   {'name':'Date Added', 'width': 85, 'fmt': format_time, 'defaultSorted': True}]
   
        List.__init__(self, columns, LIST_BLUE, [0,0], parent = parent, borders = False)
    
    def CreateHeader(self, parent):
        return ListHeader(parent, self, self.columns, 0)
    
    def CreateFooter(self, parent):
        return ManageChannelFilesFooter(parent, self.OnRemoveAll, self.OnRemoveSelected, self.OnAdd)
    
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
        canDelete = iamModerator
        canAdd = (state == ChannelCommunity.CHANNEL_OPEN) or iamModerator
        
        self.footer.SetState(canDelete, canAdd)
        
    def OnExpand(self, item):
        return True
        #return MyChannelDetails(item, item.original_data, self.id)
    
    def OnRemoveAll(self, event):
        dlg = wx.MessageDialog(None, 'Are you sure you want to remove all torrents from your channel?', 'Remove torrents', wx.ICON_QUESTION | wx.YES_NO | wx.NO_DEFAULT)
        if dlg.ShowModal() == wx.ID_YES:
            self.manager.RemoveAllItems()
        dlg.Destroy()
    
    def OnRemoveSelected(self, event):
        dlg = wx.MessageDialog(None, 'Are you sure you want to remove all selected torrents from your channel?', 'Remove torrents', wx.ICON_QUESTION | wx.YES_NO | wx.NO_DEFAULT)
        if dlg.ShowModal() == wx.ID_YES:
            infohashes = [key for key,_ in self.list.GetExpandedItems()]
            self.manager.RemoveItems(infohashes)
        dlg.Destroy()
        
    def OnAdd(self, event):
        _,_,libraryTorrents = self.guiutility.library_manager.getHitsInCategory()
        
        dlg = AddTorrent(None, self.GetManager(),libraryTorrents)
        dlg.CenterOnParent()
        dlg.ShowModal()
        dlg.Destroy()
        
class ManageChannelPlaylistList(ManageChannelFilesList):
    def __init__(self, parent):
        self.channel = None
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
        if torrent_ids is not None:
            manager = self.GetManager()
            manager.savePlaylistTorrents(playlist.id, torrent_ids)
    
    def OnManage(self, playlist):
        dlg = wx.Dialog(self, -1, 'Manage the torrents for this playlist', size = (900, 500), style = wx.RESIZE_BORDER|wx.DEFAULT_DIALOG_STYLE)
        
        manager = self.GetManager()
        available = manager.GetTorrentsFromChannel()
        if playlist.get('id', False):
            dlg.selected = manager.GetTorrentsFromPlaylist(playlist)
        else:
            dlg.selected = []

        selected_infohashes = [data.infohash for data in dlg.selected]
        dlg.available = [data for data in available if data.infohash not in selected_infohashes]
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
        
        sizer.AddSpacer(1)
        sizer.AddSpacer(1)
        sizer.Add(dlg.CreateSeparatedButtonSizer(wx.OK|wx.CANCEL), 0, wx.EXPAND|wx.ALL, 3)
        dlg.SetSizer(sizer)
        
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
        for item in to_be_removed:
            dlg.selected.remove(item)
        
        self._rebuildLists(dlg)
    
    def OnAdd(self, event):
        dlg = event.GetEventObject().GetParent()
        selected = dlg.availableList.GetSelections()

        to_be_removed = []
        for i in selected:
            if dlg.filtered_available:
                to_be_removed.append(dlg.filtered_available[i])
            else:
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
                return re.search(keyword, item.name.lower())
            filtered_contents = filter(match, dlg.available)
            dlg.filtered_available = filtered_contents
        else:
            filtered_contents = dlg.available
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
        self.additionalButton = None
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
        if self.additionalButton:
            self.moreButton = wx.Button(self, style = wx.BU_EXACTFIT)
            
        self.desc = MaxBetterText(self, self.body, maxLines = self.maxlines, button = self.moreButton)
        self.desc.SetMinSize((1, -1))
        vSizer.Add(self.desc, 0, wx.EXPAND)
        
        if self.additionalButton:
            hSizer = wx.BoxSizer(wx.HORIZONTAL)
            hSizer.Add(self.moreButton, 0, wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
            hSizer.Add(self.additionalButton, 0, wx.RESERVE_SPACE_EVEN_IF_HIDDEN)
            
            self.moreButton.Show(False)
            self.additionalButton.Show(False)
            vSizer.Add(hSizer, 0, wx.ALIGN_RIGHT)
        
        titleRow.Add(vSizer, 1)
        
        if rightSpacer > 0:
            titleRow.AddSpacer((rightSpacer, -1))
        self.vSizer.Add(titleRow, 0, wx.EXPAND|wx.TOP|wx.BOTTOM, 3)
        self.AddEvents(self)
        
    def BackgroundColor(self, color):
        changed = ListItem.BackgroundColor(self, color)
        
        if self.additionalButton and changed:
            if self.desc.hasMore:
                self.moreButton.Show(color == self.list_selected)
            self.additionalButton.Show(color == self.list_selected)
            
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
                self.additionalButton = wx.Button(self, -1, 'Open Torrent', style = wx.BU_EXACTFIT)
                self.additionalButton.Bind(wx.EVT_BUTTON, self.ShowTorrent)
        else:
            leftSpacer += depth * (self.avantar.GetWidth() + 7)  #avantar + spacer
            
        AvantarItem.AddComponents(self, leftSpacer, rightSpacer)       
        
    def ShowTorrent(self, event):
        if self.original_data.torrent:
            self.parent_list.parent_list.OnShowTorrent(self.original_data.torrent)
        
class CommentActivityItem(CommentItem):
        
    def AddComponents(self, leftSpacer, rightSpacer):
        comment = self.original_data
        self.header = "New comment received, posted %s by %s"%(format_time(comment.time_stamp).lower(), comment.name)
        
        if not self.inTorrent and comment.torrent:
            self.header += " in %s"%comment.torrent.name
            self.additionalButton = wx.Button(self, -1, 'Open Torrent', style = wx.BU_EXACTFIT)
            self.additionalButton.Bind(wx.EVT_BUTTON, self.ShowTorrent)
            
        self.body = comment.comment
        im = IconsManager.getInstance()
        self.avantar = im.get_default('COMMENT', SMALL_ICON_MAX_DIM)
        
        AvantarItem.AddComponents(self, leftSpacer, rightSpacer)  

class NewTorrentActivityItem(AvantarItem):
        
    def AddComponents(self, leftSpacer, rightSpacer):
        torrent = self.original_data
        
        self.header = "New torrent received at %s"%(format_time(torrent.time_stamp).lower())
        self.body = torrent.name
        
        self.additionalButton = wx.Button(self, -1, 'Open Torrent', style = wx.BU_EXACTFIT)
        self.additionalButton.Bind(wx.EVT_BUTTON, self.ShowTorrent)
        
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
        
        self.additionalButton = wx.Button(self, -1, 'Open Torrent', style = wx.BU_EXACTFIT)
        self.additionalButton.Bind(wx.EVT_BUTTON, self.ShowTorrent)
        
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
            self.header += " for torrent '%s'"%modification.torrent.name
            self.additionalButton = wx.Button(self, -1, 'Open Torrent', style = wx.BU_EXACTFIT)
            self.additionalButton.Bind(wx.EVT_BUTTON, self.ShowTorrent)
        
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
                self.additionalButton = wx.Button(self, -1, 'Revert Modification', style = wx.BU_EXACTFIT)
                self.additionalButton.Bind(wx.EVT_BUTTON, self.RevertModification)
        
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
                self.additionalButton = wx.Button(self, -1, 'Open Torrent', style = wx.BU_EXACTFIT)
                self.additionalButton.Bind(wx.EVT_BUTTON, self.ShowTorrent)
            
        else:
            self.body = moderation.message
        im = IconsManager.getInstance()
        self.avantar = im.get_default('REVERTED_MODIFICATION',SMALL_ICON_MAX_DIM)
        
        AvantarItem.AddComponents(self, leftSpacer, rightSpacer)
        
    def ShowTorrent(self, event):
        if self.original_data:
            self.parent_list.parent_list.OnShowTorrent(self.original_data.modification.torrent)

class CommentManager:
    def __init__(self, list):
        self.list = list
        self.list.id = 0
        
        self.channel = None
        self.playlist = None
        self.channeltorrent = None
        self.channelsearch_manager = GUIUtility.getInstance().channelsearch_manager
    
    def SetIds(self, channel = None, playlist = None, channeltorrent = None):
        if channel != self.channel:
            self.channel = channel
            self.list.dirty = True
            
            self.list.header.SetTitle('Comments for this channel')
        
        if playlist != self.playlist:
            self.playlist = playlist
            self.list.dirty = True
            
            self.list.header.SetTitle('Comments for this playlist')
            
        elif channeltorrent != self.channeltorrent:
            self.channeltorrent = channeltorrent
            self.list.dirty = True
            
            self.list.header.SetTitle('Comments for this torrent')
    
    def do_or_schedule_refresh(self, force_refresh = False):
        if self.list.isReady and (self.list.ShouldGuiUpdate() or force_refresh):
            self.refresh()
        else:
            self.list.dirty = True
    
    def refreshDirty(self):
        self.refresh()
    
    @forceDBThread
    def refresh(self):
        self.list.dirty = False
        
        if self.playlist:
            comments = self.channelsearch_manager.getCommentsFromPlayList(self.playlist)
        elif self.channeltorrent:
            comments = self.channelsearch_manager.getCommentsFromChannelTorrent(self.channeltorrent)
        else:
            comments = self.channelsearch_manager.getCommentsFromChannel(self.channel)
            
        self.list.SetData(comments)
        
    def new_comment(self):
        self.do_or_schedule_refresh()
    
    @forceDBThread
    def addComment(self, comment):
        item = self.list.GetExpandedItem()
        if item:
            reply_after = item.original_data.dispersy_id
        else:
            reply_after = None
        
        if self.playlist:
            self.channelsearch_manager.createComment(comment, self.channel, reply_after, infohash = self.channeltorrent.infohash, playlist = self.playlist)
        elif self.channeltorrent:
            self.channelsearch_manager.createComment(comment, self.channel, reply_after, infohash = self.channeltorrent.infohash)
        else:
            self.channelsearch_manager.createComment(comment, self.channel, reply_after)

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

class ActivityManager:
    def __init__(self, list):
        self.list = list
        self.list.id = 0
        
        self.channel = None
        self.playlist = None
        self.channeltorrent = None
        self.channelsearch_manager = GUIUtility.getInstance().channelsearch_manager
        
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
    
    @forceDBThread
    def refresh(self):
        self.list.dirty = False
        
        if self.playlist:
            commentList = self.channelsearch_manager.getCommentsFromPlayList(self.playlist, limit = 10)
            nrTorrents, _, torrentList = self.channelsearch_manager.getTorrentsFromPlaylist(self.playlist, limit = 10)
            nrRecentTorrents, _, recentTorrentList = self.channelsearch_manager.getRecentTorrentsFromPlaylist(self.playlist, limit = 10)
            recentModifications = self.channelsearch_manager.getRecentModificationsFromPlaylist(self.playlist, limit = 10)
            recentModerations = self.channelsearch_manager.getRecentModerationsFromPlaylist(self.playlist, limit = 10)
            
        else:
            commentList = self.channelsearch_manager.getCommentsFromChannel(self.channel, limit = 10)
            nrTorrents, _, torrentList = self.channelsearch_manager.getTorrentsFromChannel(self.channel, limit = 10)
            nrRecentTorrents, _, recentTorrentList = self.channelsearch_manager.getRecentReceivedTorrentsFromChannel(self.channel, limit = 10)
            recentModifications = self.channelsearch_manager.getRecentModificationsFromChannel(self.channel, limit = 10)
            recentModerations = self.channelsearch_manager.getRecentModerationsFromChannel(self.channel, limit = 10)
            
        self.channelsearch_manager.populateWithPlaylists(torrentList)
        self.channelsearch_manager.populateWithPlaylists(recentTorrentList)
        self.list.SetData(commentList, torrentList, recentTorrentList, recentModifications, recentModerations)
        
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
    def SetData(self, comments, recent_torrents, recent_received_torrents, recent_modifications, recent_moderations):
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
        self.list.id = 0
        
        self.torrent = None
        self.channelsearch_manager = GUIUtility.getInstance().channelsearch_manager
        
    def SetId(self, channeltorrent):
        if channeltorrent != self.torrent:
            self.torrent = channeltorrent
            self.list.dirty = True
    
    def refreshDirty(self):
        self.refresh()
    
    def refresh(self):
        def db_callback():
            self.list.dirty = False
            return self.channelsearch_manager.getTorrentModifications(self.torrent)
        
        startWorker(self.list.SetDelayedData, db_callback)
        
    def new_modification(self):
        if self.list.ShouldGuiUpdate():
            self.refresh()
        else:
            self.list.dirty = True
    
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
        dlg = wx.Dialog(self, -1, 'Revert this modification', size = (700, 400), style = wx.RESIZE_BORDER|wx.DEFAULT_DIALOG_STYLE)
        dlg.SetBackgroundColour(wx.WHITE)
        vSizer = wx.BoxSizer(wx.VERTICAL)
        
        vSizer.Add(ModificationItem(dlg, dlg, '', '', modification, list_selected = wx.WHITE), 0, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, 7)
        dlg.OnExpand = lambda a: False
        dlg.OnChange = vSizer.Layout 
        
        why = wx.StaticText(dlg, -1, 'Why do you want to revert this modification?')
        _set_font(why, fontweight=wx.FONTWEIGHT_BOLD)
        vSizer.Add(why, 0, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, 7)
        
        reason = wx.TextCtrl(dlg, -1, style = wx.TE_MULTILINE)
        vSizer.Add(reason, 0, wx.EXPAND|wx.LEFT|wx.RIGHT, 7)
        
        def canClose(event):
            givenReason = reason.GetValue().strip()
            if givenReason == '':
                reason.SetBackgroundColour(wx.RED)
                wx.CallLater(500, reason.SetBackgroundColour, wx.WHITE)
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
        self.list.id = 0
        
        self.channel = None
        self.playlist = None
        self.channeltorrent = None
        self.channelsearch_manager = GUIUtility.getInstance().channelsearch_manager
        
    def SetIds(self, channel = None, playlist = None):
        if channel != self.channel:
            self.channel = channel
            self.list.dirty = True
            
            self.list.header.SetTitle('Recent moderations for this Channel')
        
        if playlist != self.playlist:
            self.playlist = playlist
            self.list.dirty = True
            
            self.list.header.SetTitle('Recent moderations for this Playlist')
    
    def do_or_schedule_refresh(self, force_refresh = False):
        if self.list.isReady and (self.list.ShouldGuiUpdate() or force_refresh):
            self.refresh()
        else:
            self.list.dirty = True
    
    def refreshDirty(self):
        self.refresh()
    
    @forceDBThread
    def refresh(self):
        self.list.dirty = False
        
        if self.playlist:
            data = self.channelsearch_manager.getRecentModerationsFromPlaylist(self.playlist, 25)
        else:
            data = self.channelsearch_manager.getRecentModerationsFromChannel(self.channel, 25)
        self.list.SetData(data)
        
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