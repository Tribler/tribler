from Tribler.Core.API import *
from Tribler.Core.CacheDB.sqlitecachedb import bin2str
from Tribler.Core.Utilities.utilities import get_collected_torrent_filename
from Tribler.Main.Dialogs.AddTorrent import AddTorrent
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.UserDownloadChoice import UserDownloadChoice

from Tribler.Subscriptions.rss_client import TorrentFeedThread
from Tribler.__init__ import LIBRARYNAME
from __init__ import *
from datetime import date, datetime
from list_body import *
from list_details import *
from list_footer import *
from list_header import *
from list_sidebar import *
from threading import currentThread
from time import time
from traceback import print_stack
from wx import html
import os
import sys
import wx

DEBUG = False

class RemoteSearchManager:
    def __init__(self, list):
        self.list = list
        self.oldkeywords = ''
        self.data_channels = []
        
        self.guiutility = GUIUtility.getInstance()
        self.guiserver = self.guiutility.frame.guiserver
        self.torrentsearch_manager = self.guiutility.torrentsearch_manager
        self.channelsearch_manager = self.guiutility.channelsearch_manager
        
    def refresh(self):
        keywords = ' '.join(self.torrentsearch_manager.searchkeywords)
        if self.oldkeywords != keywords:
            self.list.Reset()
            self.oldkeywords = keywords
            self.list.SetKeywords(keywords, None)
        
        def db_callback():
            [total_items, nrfiltered, selected_bundle_mode, data_files] = self.torrentsearch_manager.getHitsInCategory()
            [total_channels, self.data_channels] = self.channelsearch_manager.getChannelHits()
            wx.CallAfter(self._on_refresh, data_files, total_items, nrfiltered, total_channels, selected_bundle_mode)

        self.guiserver.add_task(db_callback, id = "RemoteSearchManager_refresh")
        
    def _on_refresh(self, data_files, total_items, nrfiltered, total_channels, selected_bundle_mode):
        self.list.SetNrResults(total_items, nrfiltered, total_channels, self.oldkeywords)
        self.list.SetFF(self.guiutility.getFamilyFilter())
        self.list.SetSelectedBundleMode(selected_bundle_mode)
        self.list.SetData(data_files)
        
    def refresh_channel(self):
        def db_callback():
            [total_channels, self.data_channels] = self.channelsearch_manager.getChannelHits()
            wx.CallAfter(self._on_refresh_channel, total_channels)
        
        self.guiserver.add_task(db_callback, id = "RemoteSearchManager_refresh_channel")
        
    def _on_refresh_channel(self, total_channels):
        keywords = ' '.join(self.torrentsearch_manager.searchkeywords)
        self.list.SetNrResults(None, None, total_channels, keywords)
    
    def downloadStarted(self, infohash):
        if self.list.InList(infohash):
            item = self.list.GetItem(infohash)
            
            torrent_details = item.GetExpandedPanel()
            if torrent_details:
                torrent_details.ShowPanel(1)
            
    def torrentUpdated(self, infohash):
        def db_callback():
            data = self.torrentsearch_manager.torrent_db.getTorrent(infohash)
            wx.CallAfter(self._on_torrent_updated, infohash, data)
        
        if self.list.InList(infohash):
            self.guiserver.add_task(db_callback)
            
    def _on_torrent_updated(self, infohash, data):
        self.list.RefreshData(infohash, data)

class LocalSearchManager:
    def __init__(self, list):
        self.list = list
        
        guiutility = GUIUtility.getInstance()
        self.guiserver = guiutility.frame.guiserver
        self.library_manager = guiutility.library_manager 
    
    def expand(self, infohash):
        self.list.Select(infohash)
    
    def refresh(self):
        def db_callback():
            total_items, nrfiltered, data = self.library_manager.getHitsInCategory(sort="name")
            wx.CallAfter(self._on_data, data, total_items, nrfiltered)

        self.guiserver.add_task(db_callback, id = "LocalSearchManager_refresh")
        
    def _on_data(self, data, total_items, nrfiltered):
        self.list.SetData(data)
        self.list.Layout()
        
class ChannelSearchManager:
    def __init__(self, list):
        self.list = list
        self.category = ''
        self.dirtyset = set()
        
        guiutility = GUIUtility.getInstance()
        self.channelsearch_manager = guiutility.channelsearch_manager
        self.guiserver = guiutility.frame.guiserver
    
    def refreshDirty(self):
        if 'COMPLETE_REFRESH' in self.dirtyset:
            self.refresh()
        else:
            permids = list(self.dirtyset)
            channels = self.channelsearch_manager.getChannels(permids)
            for channel in channels:
                self.list.RefreshData(channel[0], channel)
        self.dirtyset.clear()
    
    def do_or_schedule_refresh(self, force_refresh = False):
        if self.list.ready and (self.list.ShouldGuiUpdate() or force_refresh):
            self.refresh()
        else:
            self.dirtyset.add('COMPLETE_REFRESH')
            self.list.dirty = True
    
    def refresh(self, search_results = None):
        if DEBUG:
            print >> sys.stderr, "ChannelManager complete refresh"
        
        if self.category != 'searchresults':
            category = self.category
            
            title = ''
            if category == 'New':
                title = 'New Channels'
            elif category == 'Popular':
                title = 'Popular Channels'
            elif category == 'Updated':
                title = 'Updated Channels'
            elif category == 'All':
                title  = 'All Channels'
            elif category == 'Favorites':
                title = 'Your Favorites'
            self.list.SetTitle(title, None)
            
            def db_callback():
                data = []
                total_items = 0
                if self.category == 'New':
                    [total_items,data] = self.channelsearch_manager.getNewChannels()
                elif self.category == 'Popular':
                    [total_items,data] = self.channelsearch_manager.getPopularChannels()
                elif self.category == 'Updated':
                    [total_items,data] = self.channelsearch_manager.getUpdatedChannels()
                elif self.category == 'All':
                    [total_items,data] = self.channelsearch_manager.getAllChannels()
                elif self.category == 'Favorites':
                    [total_items,data] = self.channelsearch_manager.getSubscriptions()
                wx.CallAfter(self._on_data, data, category, title, total_items)
            
            self.guiserver.add_task(db_callback, id = "ChannelSearchManager_refresh")
        else:
            if search_results:
                total_items = len(search_results)
                keywords = ' '.join(self.channelsearch_manager.searchkeywords) 
                self._on_data(search_results, self.category, 'Search results for "%s"'%keywords, total_items)
    
    def _on_data(self, data, category, title, total_items):
        if category == self.category:
            data = [channel for channel in data if channel[4] > 0]
            
            self.list.SetData(data)
            self.list.SetTitle(title, len(data))
            if DEBUG:
                print >> sys.stderr, "ChannelManager complete refresh done"
      
    def SetCategory(self, category, force_refresh = False):
        if category != self.category:
            self.category = category
            self.list.Reset()
            self.list.ShowLoading()
            
            if category != 'searchresults':
                self.do_or_schedule_refresh(force_refresh)
        else:
            self.list.DeselectAll()
        
    def channelUpdated(self, permid, votecast = False):
        if self.list.ready: 
            if self.list.InList(permid): #one item updated
                
                if self.list.ShouldGuiUpdate(): #only update if shown
                    data = self.channelsearch_manager.getChannel(permid)
                    if data:
                        self.list.RefreshData(permid, data)
                else:    
                    self.dirtyset.add(permid)
                    self.list.dirty = True
                    
            elif not votecast: #should we update complete list
                if self.category == 'All':
                    update = True
                elif self.category == 'Popular':
                    update = len(self.list.GetItems()) < 20
                else:
                    update = False
                
                if update: 
                    self.do_or_schedule_refresh()

class ChannelManager():
    _req_columns = ['infohash', 'name', 'time_stamp', 'length', 'num_seeders', 'num_leechers', 'category_id', 'status_id', 'creation_date']
    
    def __init__(self, list):
        self.list = list
        self.list.publisher_id = 0
        self.guiutility = GUIUtility.getInstance()
        self.guiserver = self.guiutility.frame.guiserver
        
        self.channelsearch_manager = self.guiutility.channelsearch_manager
        self.library_manager = self.guiutility.library_manager
        
        self.dirtyset = set()
    
    def refreshDirty(self):
        if 'COMPLETE_REFRESH' in self.dirtyset:
            self._refresh_list()
        else:
            for infohash in self.dirtyset:
                data = self.channelsearch_manager.getTorrentFromPublisherId(self.list.publisher_id, infohash)
                self.list.RefreshData(infohash, data)
                
        self.dirtyset.clear()
        
    def refresh(self, permid = None):
        if permid:
            self.list.Reset()
            self.list.ShowLoading()
            vote = self.channelsearch_manager.getMyVote(permid)
            
            self.list.footer.SetStates(vote == -1, vote == 2)
            self.list.publisher_id = permid
            self.list.SetFF(self.guiutility.getFamilyFilter())
        self._refresh_list()
        
    def _refresh_list(self):
        if DEBUG:
            print >> sys.stderr, "SelChannelManager complete refresh"
        
        def db_callback():
            total_items, nrfiltered, torrentList  = self.channelsearch_manager.getTorrentsFromPublisherId(self.list.publisher_id, ChannelManager._req_columns)
            wx.CallAfter(self._on_data, total_items, nrfiltered, torrentList)
        
        self.guiserver.add_task(db_callback, id = "ChannelManager_refresh_list")
        
    def _on_data(self, total_items, nrfiltered, torrentList):
        torrentList = self.library_manager.addDownloadStates(torrentList)
        
        if self.list.SetData(torrentList) < total_items: #some items are filtered by quickfilter (do not update total_items)
            self.list.SetNrResults(None, nrfiltered)
        else:
            self.list.SetNrResults(total_items, nrfiltered)
        
        if DEBUG:    
            print >> sys.stderr, "SelChannelManager complete refresh done"
    
    def downloadStarted(self, infohash):
        if self.list.InList(infohash):
            item = self.list.GetItem(infohash)
            
            torrent_details = item.GetExpandedPanel()
            torrent_details.ShowPanel(1)

    def torrentUpdated(self, infohash):
        if self.list.InList(infohash):
            if self.list.ShouldGuiUpdate():
                data = self.channelsearch_manager.getTorrentFromPublisherId(self.list.publisher_id, infohash)
                self.list.RefreshData(infohash, data)
            else:
                self.dirtyset.add(infohash)
                self.list.dirty = True
            
    def channelUpdated(self, permid):
        if self.list.publisher_id == permid:
            if self.list.ShouldGuiUpdate():
                self._refresh_list()
            else:
                self.dirtyset.add('COMPLETE_REFRESH')
                self.list.dirty = True

class MyChannelManager():
    def __init__(self, list):
        self.list = list
        guiutility = GUIUtility.getInstance()
        
        self.channelsearch_manager = guiutility.channelsearch_manager
        self.guiserver = guiutility.frame.guiserver
        self.my_permid = self.channelsearch_manager.channelcast_db.my_permid
    
    def refreshDirty(self):
        self.refresh()
    
    def refresh(self):
        def db_callback():
            nr_favorite = self.channelsearch_manager.channelcast_db.getSubscribersCount(self.my_permid)
            total_items, nr_filtered, torrentList = self.channelsearch_manager.getTorrentsFromMyChannel()
            wx.CallAfter(self._on_data, torrentList, nr_favorite)
            
        self.guiserver.add_task(db_callback, id = "MyChannelManager_refresh")
            
    def _on_data(self, torrentList, nr_favorite):
        self.list.SetData(torrentList, nr_favorite)
    
    def OnNewTorrent(self):
        if self.list.ShouldGuiUpdate():
            self.refresh()
        else:
            self.list.dirty = True
    
    def RemoveItems(self, infohashes):
        for infohash in infohashes:
            self.channelsearch_manager.channelcast_db.deleteOwnTorrent(infohash)
        self.list.Reset()
        self.refresh()
        
    def RemoveAllItems(self):
        self.channelsearch_manager.channelcast_db.deleteTorrentsFromPublisherId(self.channelsearch_manager.channelcast_db.my_permid)
        self.list.Reset()
        self.refresh()

class XRCPanel(wx.Panel):
    def __init__(self, parent = None):
        self.parent = parent
        self.ready = False
        
        if parent:
            wx.Panel.__init__(self, parent)
            self._PostInit()
            
        else:
            pre = wx.PrePanel()
            # the Create step is done by XRC. 
            self.PostCreate(pre)
            if sys.platform == 'linux2': 
                self.Bind(wx.EVT_SIZE, self.OnCreate)
            else:
                self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate)
    
    def OnCreate(self, event):
        if sys.platform == 'linux2': 
            self.Unbind(wx.EVT_SIZE)
        else:
            self.Unbind(wx.EVT_WINDOW_CREATE)
        
        wx.CallAfter(self._PostInit)
        event.Skip()
    
    def _PostInit(self):
        pass

class List(XRCPanel):
    def __init__(self, columns, background, spacers = [0,0], singleSelect = False, showChange = False, borders = True, parent = None):
        """
        Column alignment:
        
        Text should usually be left-aligned, though if there are only a small number of possible values and 
        they are all short, then centre alignment can work well.
        
        Numbers should usually be right-aligned with each other.
        
        Numbers with decimal points should have the same number of digits to the right of the point. They 
        should be right-aligned (so the decimal points are all aligned).
        
        Numbers are right-aligned to make it easy to visually compare magnitudes. So in cases where the 
        magnitude is irrelevant (for example, listing the team numbers of football players) you could consider left- or centre-alignment.
        For the same reason, numbers representing magnitudes should use the same units. For example, Mac OS "helpfully" displays file sizes 
        in differing units (kB, MB). This makes it very easy to miss a 3MB file in a listing of 3kB files. If it were listed as 3000kB then it would stand out appropriately.
        
        Headings often look good if they are aligned the same as their data. You could consider alternatives such as centre-alignment, but 
        avoid situations where a column heading is not actually above the data in the column (e.g. a wide column with left-aligned header and right-aligned data).
        
        taken from: http://uxexchange.com/questions/2249/text-alignment-in-tables-legibility
        """
        
        self.columns = columns
        self.background = background
        self.spacers = spacers
        self.singleSelect = singleSelect
        self.borders = borders
        self.showChange = showChange
        self.dirty = False
        
        self.guiutility = GUIUtility.getInstance()
        self.uelog = UserEventLogDBHandler.getInstance()
        
        self.id = 0
        
        self.leftLine = self.rightLine = None
        XRCPanel.__init__(self, parent)
    
    def _PostInit(self):
        vSizer = wx.BoxSizer(wx.VERTICAL)
        
        self.header = self.CreateHeader()
        if self.header:
            vSizer.Add(self.header, 0, wx.EXPAND)
        
        self.list = self.CreateList()
        listSizer = wx.BoxSizer(wx.HORIZONTAL)
        
        #left and right borders
        self.leftLine = wx.Panel(self, size=(1,-1))
        self.rightLine = wx.Panel(self, size=(1,-1))
        
        listSizer.Add(self.leftLine, 0, wx.EXPAND)
        listSizer.Add(self.list, 1, wx.EXPAND)
        listSizer.Add(self.rightLine, 0, wx.EXPAND)
        vSizer.Add(listSizer, 1, wx.EXPAND)
        
        self.footer = self.CreateFooter()
        if self.footer:
            vSizer.Add(self.footer, 0, wx.EXPAND)
        
        self.SetBackgroundColour(self.background)
        self.SetSizer(vSizer)
        self.Layout()
        
        self.list.Bind(wx.EVT_SIZE, self.OnSize)
        self.ready = True
    
    def format_time(self, val):
        today = datetime.today()
        discovered = datetime.fromtimestamp(val)
        
        diff = today - discovered
        if diff.days > 0 or today.day != discovered.day:
            return discovered.strftime('%d-%m-%Y')
        return discovered.strftime('Today %H:%M')

    def format_size(self, val):
        size = (val/1048576.0)
        return "%.0f MB"%size
    
    def CreateHeader(self):
        return ListHeader(self, self.columns)
    
    def CreateList(self, parent = None):
        if not parent:
            parent = self
        return ListBody(parent, self, self.columns, self.spacers[0], self.spacers[1], self.singleSelect, self.showChange)
    
    def CreateFooter(self):
        return ListFooter(self)
    
    def OnSize(self, event):
        assert self.ready, "List not ready"
        if self.header:
            diff = self.header.GetClientSize()[0] - self.list.GetClientSize()[0]
            self.header.SetSpacerRight(diff)
            self.footer.SetSpacerRight(diff)
        event.Skip()
        
    def OnSort(self, column, reverse):
        assert self.ready, "List not ready"
        if self.ready:
            self.list.OnSort(column, reverse)
    
    def Reset(self):
        assert self.ready, "List not ready"
        self.__check_thread()

        if self.ready:
            if self.header:
                self.header.Reset()
                
            self.list.Reset()
            
            if self.footer:
                self.footer.Reset()
            
            self.dirty = False
            self.Layout()
    
    def OnExpand(self, item):
        assert self.ready, "List not ready"
        self.__check_thread()
    
    def OnCollapse(self, item, panel):
        assert self.ready, "List not ready"
        self.__check_thread()
        
        self.OnCollapseInternal(item)
        if panel:
            panel.Destroy()
            
    def OnCollapseInternal(self, item):
        pass
    
    def GetManager(self):
        pass
    
    def SetData(self, data):
        assert self.ready, "List not ready"
        self.__check_thread()
    
    def RefreshData(self, key, data):
        assert self.ready, "List not ready"
        self.__check_thread()
        
    def InList(self, key):
        assert self.ready, "List not ready"
        if self.ready:
            return self.list.InList(key)
    
    def GetItem(self, key):
        assert self.ready, "List not ready"
        if self.ready:
            return self.list.GetItem(key)
        
    def GetItems(self):
        assert self.ready, "List not ready"
        if self.ready:
            return self.list.items
        
    def GetExpandedItem(self):
        assert self.ready, "List not ready"
        if self.ready:
            return self.list.GetExpandedItem()
    
    def Focus(self):
        assert self.ready, "List not ready"
        if self.ready:
            self.list.SetFocus()
        
    def HasFocus(self):
        assert self.ready, "List not ready"
        focussed = wx.Window.FindFocus()
        return focussed == self.list
        
    def SetBackgroundColour(self, colour):
        self.__check_thread()
        
        wx.Panel.SetBackgroundColour(self, colour)
        
        if self.header:
            self.header.SetBackgroundColour(colour)
            
        self.leftLine.SetBackgroundColour(colour)
        self.list.SetBackgroundColour(colour)
        self.rightLine.SetBackgroundColour(colour)
        
        if self.footer:
            self.footer.SetBackgroundColour(colour)
        
    def ScrollToEnd(self, scroll_to_end):
        assert self.ready, "List not ready"
        if self.ready:
            self.list.ScrollToEnd(scroll_to_end)
    
    def DeselectAll(self):
        assert self.ready, "List not ready"
        if self.ready:
            self.list.DeselectAll()
        
    def Select(self, key, raise_event = True):
        assert self.ready, "List not ready"
        if self.ready:
            self.list.Select(key, raise_event)
            
    def ShouldGuiUpdate(self):
        if not self.IsShownOnScreen():
            return False
        return self.guiutility.ShouldGuiUpdate()

    def ShowLoading(self):
        if self.ready:
            self.list.ShowLoading()
            
    def OnLoadAll(self):
        if self.ready:
            self.list.OnLoadAll()
        
    def Show(self, show = True):
        wx.Panel.Show(self, show)
        
        if show:
            if self.dirty:
                self.dirty = False
    
                manager = self.GetManager()
                if manager:
                    manager.refreshDirty()
                    
            self.list.Layout()
        
    def __check_thread(self):
        if __debug__ and currentThread().getName() != "MainThread":
            print  >> sys.stderr,"List: __check_thread thread",currentThread().getName(),"is NOT MainThread"
            print_stack()
    
    def Layout(self):
        self.__check_thread()
        return wx.Panel.Layout(self)

class GenericSearchList(List):
    def __init__(self, columns, background, spacers = [0,0], singleSelect = False, showChange = False, borders = True, parent = None):
        List.__init__(self, columns, background, spacers, singleSelect, showChange, borders, parent)
        
        self.infohash2key = {} # bundled infohashes
    
    def CreateDownloadButton(self, parent, item):
        button = wx.Button(parent, -1, 'Download', style = wx.BU_EXACTFIT)
        button.item = item
        item.button = button
        
        if not item.original_data.get('ds',False):
            button.Bind(wx.EVT_BUTTON, self.OnDownload)
        else:
            button.Enable(False)
        return button

    def CreateRatio(self, parent, item):
        seeders = int(item.original_data['num_seeders'])
        leechers = int(item.original_data['num_leechers'])
        item.data[-2] = seeders + leechers
        
        control = SwarmHealth(parent)
        control.SetMinSize((self.columns[-2]['width'],7))
        control.SetBackgroundColour(wx.WHITE)
        control.SetRatio(seeders, leechers)
        return control
        
    def OnDownload(self, event):
        item = event.GetEventObject().item
        self.Select(item.original_data['infohash'])
        self.StartDownload(item.original_data)
    
    def toggleFamilyFilter(self):
        self.guiutility.toggleFamilyFilter()

        def db_callback():
            self.uelog.addEvent(message="SearchList: user toggled family filter", type = 2)
        self.guiutility.frame.guiserver.add_task(db_callback)
        
    def SetFF(self, family_filter):
        self.header.SetFF(family_filter)
        
    def SetData(self, data):
        from Tribler.Main.vwxGUI.list_bundle import BundleListItem # solving circular dependency for now
        
        List.SetData(self, data)
        
        if len(data) > 0:
            list_data = []
            for file in data:
                # either we have a bundle of hits:
                if 'bundle' in file:
                    head = file['bundle'][0]
                    create_method = BundleListItem
                    key = file['key']
                    
                    for hit in file['bundle']:
                        self.infohash2key[hit['infohash']] = key
                    
                    # if the bundle is changed, inform the ListBody
                    if 'bundle_changed' in file:
                        self.RefreshData(key, file)
                    
                # or a single hit:
                else:
                    head = file
                    create_method = ListItem
                    key = head['infohash']
                    
                    if key in self.infohash2key:
                        del self.infohash2key[key]
                
                item_data = [head['name'], head['length'], 0, 0]
                original_data = file
                    
                list_data.append((key, item_data, original_data, create_method))
            
            return self.list.SetData(list_data)
        
        message =  'No torrents matching your query are found. \n'
        message += 'Try leaving Tribler running for a longer time to allow it to discover new torrents, or use less specific search terms.'
        if self.guiutility.getFamilyFilter():
            message += '\n\nAdditionally, you could disable the "Family Filter" by clicking on it.'
        self.list.ShowMessage(message)
        return 0

    def RefreshData(self, key, data):
        List.RefreshData(self, key, data)
        
        original_data = data
        if 'bundle' in data: # bundle update
            head = data['bundle'][0]
        
        else: # individual hit update
            head = original_data
            
            # check whether the individual hit is in a bundle
            key = self.infohash2key.get(key, key)
        
        # Update primary columns with new data
        data = (head['infohash'], [head['name'], head['length'], 0, 0], original_data)
        self.list.RefreshData(key, data)
    
    def SetFilteredResults(self, nr):
        if nr != self.total_results: 
            self.header.SetNrResults(nr)
        else:
            self.header.SetNrResults()
            
    def SetNrResults(self, nr, nr_filtered, nr_channels, keywords):
        if keywords and isinstance(nr, int):
            self.SetKeywords(keywords, nr)
        
        if isinstance(nr_filtered, int):
            self.header.SetFiltered(nr_filtered)
            
        if isinstance(nr_channels, int):
            self.footer.SetNrResults(nr_channels, keywords)
    
    def OnFilter(self, keyword):
        def doFilter():
            self.header.FilterCorrect(self.list.FilterItems(keyword))
        #Niels: use callafter due to the filteritems method being slow and halting the events
        wx.CallAfter(doFilter)
        
    def OnExpand(self, item):
        item.button.Hide()
        item.button.Refresh()
        return TorrentDetails(item, item.original_data)
    
    def OnCollapseInternal(self, item):
        item.button.Show()
    
    def StartDownload(self, torrent, files = None):
        from list_bundle import BundleListView
        
        def db_callback():
            if isinstance(self, SelectedChannelList):
                self.uelog.addEvent(message="Torrent: torrent download from channel", type = 2)
            elif isinstance(self, BundleListView):
                self.uelog.addEvent(message="Torrent: torrent download from bundle", type = 2)
            else:
                self.uelog.addEvent(message="Torrent: torrent download from other", type = 2)
        
        self.guiutility.frame.guiserver.add_task(db_callback)
        self.guiutility.torrentsearch_manager.downloadTorrent(torrent, selectedFiles = files)
        
    def InList(self, key):
        key = self.infohash2key.get(key, key)
        return List.InList(self, key)
    
    def GetItem(self, key):
        key = self.infohash2key.get(key, key)
        return List.GetItem(self, key)
        
    def format(self, val):
        val = int(val)
        if val < 0:
            return "?"
        return str(val)
        
class SearchList(GenericSearchList):
    def __init__(self, parent=None):
        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility
        
        columns = [{'name':'Name', 'width': wx.LIST_AUTOSIZE, 'sortAsc': True, 'icon': 'tree', 'fontWeight': wx.FONTWEIGHT_BOLD}, \
                   {'name':'Size', 'width': '9em', 'style': wx.ALIGN_RIGHT, 'fmt': self.format_size, 'sizeCol': True}, \
                   #{'name':'Seeders', 'width': wx.LIST_AUTOSIZE_USEHEADER, 'style': wx.ALIGN_RIGHT, 'fmt': self.format}, \
                   #{'name':'Leechers', 'width': wx.LIST_AUTOSIZE_USEHEADER, 'style': wx.ALIGN_RIGHT, 'fmt': self.format}, \
                   {'type':'method', 'width': wx.LIST_AUTOSIZE_USEHEADER, 'method': self.CreateRatio, 'name':'Popularity'}, \
                   {'type':'method', 'width': LIST_AUTOSIZEHEADER, 'method': self.CreateDownloadButton}]
        
        GenericSearchList.__init__(self, columns, LIST_GREY, [0,0], True, parent=parent)
        
    def _PostInit(self):
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.header = self.CreateHeader()
        sizer.Add(self.header, 0, wx.EXPAND)
        
        list = wx.Panel(self)
        self.subheader = ListHeader(list, self.columns, radius = 0)
        self.sidebar = SearchSideBar(self, size=(200,-1))
        self.leftLine = self.sidebar
        self.rightLine = wx.Panel(self, size=(1,-1))
        
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(self.leftLine, 0, wx.EXPAND)
        
        self.list = self.CreateList(list)
        list.OnSort = self.list.OnSort
        
        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.Add(self.subheader, 0, wx.EXPAND)
        vSizer.Add(self.list, 1, wx.EXPAND)
        list.SetSizer(vSizer)

        hSizer.Add(list, 1, wx.EXPAND)
        hSizer.Add(self.rightLine, 0, wx.EXPAND)

        sizer.Add(hSizer, 1, wx.EXPAND)
        
        self.footer = self.CreateFooter()
        sizer.Add(self.footer, 0, wx.EXPAND)
        
        self.header.SetSpacerRight = self.subheader.SetSpacerRight
        self.header.ResizeColumn = self.subheader.ResizeColumn
        self.header.SetFiltered = self.sidebar.SetFiltered
        self.header.SetFF = self.sidebar.SetFF
        
        self.SetBackgroundColour(self.background)
        self.SetSizer(sizer)
        self.Layout()
        
        self.list.Bind(wx.EVT_SIZE, self.OnSize)
        self.ready = True
    
    def GetManager(self):
        if getattr(self, 'manager', None) == None:
            self.manager = RemoteSearchManager(self) 
        return self.manager
    
    def CreateHeader(self):
        return SearchHelpHeader(self, [])

    def CreateFooter(self):
        footer = ChannelResultFooter(self)
        footer.SetEvents(self.OnChannelResults)
        return footer
    
    def SetKeywords(self, keywords, nr = None):
        self.keywords = keywords
        
        if isinstance(nr, int):
            if nr == 0:
                self.header.SetTitle('No results for "%s"'%keywords)
            elif nr == 1:
                self.header.SetTitle('Got 1 result for "%s"'%keywords)
            else:
                self.header.SetTitle('Got %d results for "%s"'%(nr, keywords))
            self.total_results = nr
        else:
            self.header.SetTitle('Searching for "%s"'%keywords)
    
    def SetSelectedBundleMode(self, selected_bundle_mode):
        self.sidebar.SetSelectedBundleMode(selected_bundle_mode)
    
    def SetData(self, data):
        GenericSearchList.SetData(self, data)
        
        #indentify popular associated channels
        channel_hits = {}
        for hit in data:
            if 'channel_permid' in hit:
                if hit['subscriptions'] > 0:
                    if hit['channel_permid'] not in channel_hits:
                        channel_hits[hit['channel_permid']] = [0, hit['channel_name'], hit['channel_permid']]
                    channel_hits[hit['channel_permid']][0] += 1
        
        def channel_occur(a, b):
            return cmp(a[0], b[0])            
        
        channels = channel_hits.values()
        channels.sort(channel_occur, reverse = True)
        self.sidebar.SetAssociatedChannels(channels)
            
    def SetMaxResults(self, max):
        self.sidebar.SetMaxResults(max)
    def NewResult(self):
        self.sidebar.NewResult()
    
    def toggleFamilyFilter(self):
        GenericSearchList.toggleFamilyFilter(self)
        self.guiutility.dosearch()
    
    def Reset(self):
        GenericSearchList.Reset(self)
        self.sidebar.Reset()
        self.subheader.Reset()
    
    def SetBackgroundColour(self, colour):
        GenericSearchList.SetBackgroundColour(self, colour)
        self.subheader.SetBackgroundColour(colour)
        
    def OnChannelResults(self, event):
        manager = self.GetManager()
        self.guiutility.showChannelResults(manager.data_channels)
        
        def db_callback():
            self.uelog.addEvent(message="SearchList: user clicked to view channel results", type = 2)
        self.guiutility.frame.guiserver.add_task(db_callback)  
        
    def OnSize(self, event):
        diff = self.subheader.GetClientSize()[0] - self.list.GetClientSize()[0]
        self.subheader.SetSpacerRight(diff)
        self.footer.SetSpacerRight(diff)
        event.Skip()

class LibaryList(List):
    def __init__(self):
        self.user_download_choice = UserDownloadChoice.get_singleton()
        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility
        self.library_manager = self.guiutility.library_manager

        columns = [{'name':'Name', 'width': wx.LIST_AUTOSIZE, 'sortAsc': True, 'icon': 'tree'}, \
                   {'type':'method', 'name':'Completion', 'width': 250, 'method': self.CreateProgress}, \
                   {'type':'method', 'name':'Connections', 'width': wx.LIST_AUTOSIZE_USEHEADER, 'method': self.CreateConnections, 'footer_style': wx.ALIGN_RIGHT}, \
                   {'type':'method', 'name':'Down', 'width': 70, 'method': self.CreateDown, 'fmt': self.utility.speed_format_new, 'footer_style': wx.ALIGN_RIGHT}, \
                   {'type':'method', 'name':'Up', 'width': 70, 'method': self.CreateUp, 'fmt': self.utility.speed_format_new, 'footer_style': wx.ALIGN_RIGHT}]
     
        List.__init__(self, columns, LIST_GREY, [7,7], True)
    
    def GetManager(self):
        if getattr(self, 'manager', None) == None:
            self.manager = LocalSearchManager(self) 
        return self.manager
    
    def CreateHeader(self):
        header = ButtonHeader(self, self.columns)
        header.SetTitle('Library')
        header.SetEvents(self.OnAdd, self.OnResume, self.OnStop, self.OnDelete)
        return header
    
    def CreateFooter(self):
        footer = TotalFooter(self, self.columns)
        footer.SetTotal(0, 'Totals:')
        return footer
    
    def CreateUp(self, parent, item):
        up = wx.StaticText(parent, style = wx.ALIGN_RIGHT|wx.ST_NO_AUTORESIZE, size=(70,-1))
        item.up = up
        
        if item.data[4]:
            up.SetLabel(self.utility.speed_format_new(item.data[4]))
        else:
            up.SetLabel(self.utility.speed_format_new(0))
        return up
        
    def CreateDown(self, parent, item):
        down = wx.StaticText(parent, style = wx.ALIGN_RIGHT|wx.ST_NO_AUTORESIZE, size=(70,-1))
        item.down = down
        
        if item.data[3]:
            down.SetLabel(self.utility.speed_format_new(item.data[3]))
        else:
            down.SetLabel(self.utility.speed_format_new(0))
        return down
    
    def CreateProgress(self, parent, item):
        progressPanel = ProgressPanel(parent, item)
        progressPanel.SetMinSize((self.columns[1]['width'],-1))
        progressPanel.Layout()
        
        item.progressPanel = progressPanel
        return progressPanel
    
    def CreateConnections(self, parent, item):
        connections = wx.StaticText(parent, style = wx.ALIGN_RIGHT|wx.ST_NO_AUTORESIZE, size=(self.columns[2]['width'],-1))
        item.connections = connections
        
        if item.data[2]:
            connections.SetLabel(str(item.data[2][0] + item.data[2][1]))
        return connections

    def OnExpand(self, item):
        playable = False
        delete = True
        
        if item.original_data.get('ds'):
            ds = item.original_data['ds']
            
            finished = ds.get_progress() == 1.0
            if finished: #finished download
                if ds.get_status() == DLSTATUS_SEEDING:
                    resume = False
                    stop = True
                else:
                    resume = True
                    stop = False
            elif ds.get_status() in (DLSTATUS_STOPPED, DLSTATUS_REPEXING): #stopped download
                resume = True
                stop = False
            else: #active download
                resume = False
                stop = True
        else: #inactive download
            progress = item.original_data.get('progress')
            finished = progress == 100
            
            resume = True
            stop = False
        
        self.header.SetStates(resume, stop, delete)
        return LibraryDetails(item, item.original_data)

    def OnCollapseInternal(self, item):
        self.header.SetStates(False, False, False)

    def OnAdd(self, event):
        dlg = AddTorrent(self, self.guiutility.frame)
        dlg.CenterOnParent()
        dlg.ShowModal()
        dlg.Destroy()

    def OnPlay(self, event):
        item = self.list.GetExpandedItem()
        self.library_manager.playTorrent(item.original_data)
    
    def OnResume(self, event):
        item = self.list.GetExpandedItem()
        if item.original_data.get('ds'):
            ds = item.original_data['ds']
            ds.get_download().restart()
            
            self.header.SetStates(False, True, True)
        else:
            #TODO: start inactive item?
            pass
        self.user_download_choice.set_download_state(item.original_data["infohash"], "restart")
    
    def OnStop(self, event):
        item = self.list.GetExpandedItem()
        if item.original_data.get('ds'):
            ds = item.original_data['ds']
            ds.get_download().stop()
            
            self.header.SetStates(True, False, True)
        self.user_download_choice.set_download_state(item.original_data["infohash"], "stop")
            
    def OnDelete(self, event):
        item = self.list.GetExpandedItem()
        
        dlg = wx.Dialog(None, -1, 'Are you sure you want to remove this torrent?', style=wx.DEFAULT_DIALOG_STYLE, size = (600, 125))
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(wx.StaticBitmap(dlg, -1, wx.ArtProvider.GetBitmap(wx.ART_QUESTION, wx.ART_MESSAGE_BOX)), 0, wx.RIGHT, 10)
        
        vSizer = wx.BoxSizer(wx.VERTICAL)
        firstLine = wx.StaticText(dlg, -1, "Delete '%s' from disk, or just remove them from your library?"%item.data[0])
        font = firstLine.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        firstLine.SetFont(font)
        firstLine.SetMinSize((1, -1))
        
        vSizer.Add(firstLine, 0, wx.EXPAND|wx.BOTTOM, 7)
        vSizer.AddStretchSpacer()
        vSizer.Add(wx.StaticText(dlg, -1, "Removing from disk will move the selected item to your trash."), 0, wx.EXPAND)
        
        bSizer = wx.BoxSizer(wx.HORIZONTAL)
        bSizer.AddStretchSpacer()
        bSizer.Add(wx.Button(dlg, wx.ID_CANCEL), 0, wx.RIGHT, 3)
        bSizer.Add(wx.Button(dlg, wx.ID_DEFAULT, 'Only delete from library'), 0, wx.RIGHT, 3)
        bSizer.Add(wx.Button(dlg, wx.ID_DELETE, 'Also delete from disk'))
        
        vSizer.Add(bSizer, 0, wx.ALIGN_RIGHT|wx.TOP, 7)
        hSizer.Add(vSizer, 1, wx.EXPAND)
        
        border = wx.BoxSizer()
        border.Add(hSizer, 1, wx.ALL|wx.EXPAND, 10)
        
        dlg.Bind(wx.EVT_BUTTON, lambda event: dlg.EndModal(event.GetId()))
        dlg.SetSizer(border)
        dlg.CenterOnParent()
        
        buttonId = dlg.ShowModal()
        if buttonId == wx.ID_DEFAULT:
            self.library_manager.deleteTorrent(item.original_data)
            self.header.SetStates(False, False, False) #nothing selected
            self.list.RemoveItem(item)
            
        elif buttonId == wx.ID_DELETE:
            self.library_manager.deleteTorrent(item.original_data, True)
            self.header.SetStates(False, False, False) #nothing selected
            self.list.RemoveItem(item)
        
        if self.list.IsEmpty():
            self.SetData([])
        
        dlg.Destroy()
    
    def RefreshItems(self, dslist):
        if self.ready and self.ShouldGuiUpdate():
            totals = {2:0, 3:0, 4:0}
            
            nr_seeding = 0
            nr_downloading = 0
            for item in self.list.items.values():
                item.original_data['ds'] = None #remote all downloadstates
            
            for ds in dslist:
                infohash = ds.get_download().get_def().get_infohash()
                if infohash in self.list.items:
                    item = self.list.items[infohash]
                    item.original_data['ds'] = ds
                else:
                    self.GetManager().refresh() #new torrent
                    break
            
            for infohash, item in self.list.items.iteritems():
                ds = item.original_data['ds']
                status = item.progressPanel.Update(ds)
                if status == 1:
                    nr_downloading += 1
                elif status == 2:
                    nr_seeding += 1
                
                totals[2] = totals[2] + item.data[2][0] + item.data[2][1]
                totals[3] = totals[3] + item.data[3]
                totals[4] = totals[4] + item.data[4]
                
                nr_connections = str(item.data[2][0] + item.data[2][1])
                if item.connections.GetLabel() != nr_connections:
                    item.connections.SetLabel(nr_connections)
                    item.connections.Refresh()
                
                down = self.utility.speed_format_new(item.data[3])
                if item.down.GetLabel() != down:
                    item.down.SetLabel(down)
                    item.down.Refresh()
                
                up = self.utility.speed_format_new(item.data[4])
                if item.up.GetLabel() != up:
                    item.up.SetLabel(up)
                    item.up.Refresh()
                
                if ds:
                    item.connections.SetToolTipString("Connected to %d Seeders and %d Leechers.\nInitiated %d, %d candidates remaining."%(item.data[2][0], item.data[2][1], ds.get_num_con_initiated(), ds.get_num_con_candidates()))
                    if ds.get_seeding_statistics():
                        stats = ds.get_seeding_statistics()
                        dl = stats['total_down']
                        ul = stats['total_up']
                        
                        if dl == 0L:
                            ratio = 0
                        else:
                            ratio = 1.0*ul/dl
                            
                        tooltip = "Total transferred: %s down, %s up.\nRatio: %.2f\nTime seeding: %s"%(self.utility.size_format(dl), self.utility.size_format(ul), ratio, self.utility.eta_value(stats['time_seeding']))
                        item.down.SetToolTipString(tooltip)
                        item.up.SetToolTipString(tooltip)
                    else:
                        dl = ds.get_total_transferred(DOWNLOAD)
                        ul = ds.get_total_transferred(UPLOAD)
                        
                        if dl == 0L:
                            ratio = 0
                        else:
                            ratio = 1.0*ul/dl
                        
                        tooltip = "Total transferred: %s down, %s up.\nRatio: %.2f"%(self.utility.size_format(dl), self.utility.size_format(ul), ratio)
                        item.down.SetToolTipString(tooltip)
                        item.up.SetToolTipString(tooltip)
                else:
                    item.connections.SetToolTipString('')
                    item.down.SetToolTipString('')
                    item.down.SetToolTipString('')
                        
            if len(self.list.items) > 0:
                totalStr = "Totals: %d items ("%len(self.list.items)
                
                if nr_downloading > 0:
                    totalStr += "%d downloading, "%nr_downloading
                if nr_seeding > 0:
                    totalStr += "%d seeding, "%nr_seeding
                nr_inactive = len(self.list.items) - nr_seeding - nr_downloading
                if nr_inactive > 0:
                    totalStr += "%d inactive, "%nr_inactive
                
                totalStr = totalStr[:-2] + ")"
                self.footer.SetTotal(0, totalStr)
            else:
                self.footer.SetTotal(0, "Totals: 0 items")
            
            for key in totals.keys():
                self.footer.SetTotal(key, totals[key])
        
    def SetData(self, data):
        List.SetData(self, data)
        
        if len(data) > 0:
            data = [(file['infohash'], [file['name'], [0,0], None, None, None], file) for file in data]
            return self.list.SetData(data)
        message = "Currently not downloading any torrents.\n"
        message += "Torrents can be found using our integrated search, inside a channel.\n\n"
        message += "Additionally you could drag and drop any torrent file downloaded from an external source."
        self.list.ShowMessage(message)
        return 0

    def Show(self):
        List.Show(self)
        self.library_manager.add_download_state_callback(self.RefreshItems)
        
    def Hide(self):
        wx.Panel.Hide(self)
        self.library_manager.remove_download_state_callback(self.RefreshItems)
    
    def ScrollToEnd(self, scroll_to_end):
        self.list.ScrollToEnd(scroll_to_end)
        
class ChannelList(List):
    def __init__(self):
        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility
        
        columns = [{'name':'Name', 'width': wx.LIST_AUTOSIZE, 'icon': self.__favorite_icon, 'sortAsc': True}, \
                   {'name':'Latest Update', 'width': wx.LIST_AUTOSIZE_USEHEADER, 'fmt': self.format_time}, \
                   #{'name':'Popularity', 'width': wx.LIST_AUTOSIZE_USEHEADER, 'style': wx.ALIGN_RIGHT, 'fmt': self.__format}, \
                   {'type':'method', 'width': 75, 'method': self.CreatePopularity, 'name':'Popularity', 'defaultSorted': True}, \
                   {'name':'Torrents', 'width': wx.LIST_AUTOSIZE_USEHEADER, 'style': wx.ALIGN_RIGHT}]
        
        self.favorite = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","starEnabled.png"), wx.BITMAP_TYPE_ANY)
        self.normal = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","star.png"), wx.BITMAP_TYPE_ANY)
        self.mychannel = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","mychannel.png"), wx.BITMAP_TYPE_ANY)
        self.spam = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","bug.png"), wx.BITMAP_TYPE_ANY)
        
        self.my_permid = bin2str(self.guiutility.channelsearch_manager.channelcast_db.my_permid)
        List.__init__(self, columns, LIST_BLUE, [7,7], showChange = True)
    
    def __favorite_icon(self, item):
        if item.original_data[0] == self.my_permid:
            return self.mychannel
        if item.original_data[0] in self.favorites:
            return self.favorite
        if item.original_data[0] in self.spam_channels:
            return self.spam
        return self.normal
    
    def __format(self, val):
        val = int(val)
        if val <= 0:
            return "New"
        return str(val)
    
    def CreateHeader(self):
        return SubTitleHeader(self, self.columns)
    
    def CreatePopularity(self, parent, item):
        pop = int(item.data[2])
        if pop <= 0:
            ratio = wx.StaticText(parent, -1, "New", )
            ratio.SetMinSize((self.columns[2]['width'],-1))
            return ratio
        
        ratio = min(1, pop / 5.0)
        control = ChannelPopularity(parent, self.normal, self.favorite)
        control.SetMinSize((self.columns[2]['width'],15))
        control.SetBackgroundColour(wx.WHITE)
        control.SetVotes(ratio)
        control.SetToolTipString('%s users marked this channel as one of their favorites.'%pop)
        return control
    
    def OnExpand(self, item):
        if item.original_data[0] == self.my_permid:
            self.guiutility.frame.channelcategories.Select(5)
        else:
            self.guiutility.showChannel(item.GetColumn(0), item.original_data[0])
        return False
    
    def GetManager(self):
        if getattr(self, 'manager', None) == None:
            self.manager = ChannelSearchManager(self) 
        return self.manager

    def SetData(self, data):
        List.SetData(self, data)
        
        if len(data) > 0:
            self.favorites = [file[0] for file in data if file[6] == 2]
            self.spam_channels = [file[0] for file in data if file[6] == -1]
            
            data = [(file[0],[file[1], file[2], file[3], file[4]], file) for file in data]
            return self.list.SetData(data)
        
        self.list.ShowMessage('No channels are discovered for this category.')
        return 0
        
    def RefreshData(self, key, data):
        List.RefreshData(self, key, data)
        
        data = (data[0],[data[1], data[2], data[3], data[4]], data)
        self.list.RefreshData(key, data)
        
    def SetTitle(self, title, nr):
        self.header.SetTitle(title)
        
        if nr:
            if title == 'Popular Channels':
                self.header.SetSubTitle("Showing the %d most popular channels" % nr)
            elif title == 'Your Favorites':
                self.header.SetSubTitle("You marked %d channels as a favorite" % nr)
            elif title == 'Updated Channels':
                self.header.SetSubTitle("Showing the %d latest updated channels" % nr)
            elif title == 'New Channels':
                self.header.SetSubTitle("Discovered %d new channels (not marked yet and updated within the last 2 months)"% nr)
            else:
                if nr == 1:
                    self.header.SetSubTitle("Discovered %d channel" % nr)
                else:
                    self.header.SetSubTitle("Discovered %d channels" % nr)
        else:
            self.header.SetSubTitle('')
        
        if title == 'Updated Channels':
            self.header.ShowSortedBy(1)
        elif title == 'New Channels':
            self.header.ShowSortedBy(1)
        elif title.startswith('Search results'):
            self.header.ShowSortedBy(3)
            
        self.header.Refresh()
        
class SelectedChannelList(GenericSearchList):
    def __init__(self):
        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility
        self.channelsearch_manager = self.guiutility.channelsearch_manager 
        
        columns = [{'name':'Name', 'width': wx.LIST_AUTOSIZE, 'sortAsc': True, 'icon': 'tree'}, \
                   {'name':'Date Added', 'width': 85, 'fmt': self.format_time, 'defaultSorted': True}, \
                   {'name':'Size', 'width':  '9em', 'style': wx.ALIGN_RIGHT, 'fmt': self.format_size, 'sizeCol': True}, \
                   {'type':'method', 'width': wx.LIST_AUTOSIZE_USEHEADER, 'method': self.CreateRatio, 'name':'Popularity'}, \
                   {'type':'method', 'width': LIST_AUTOSIZEHEADER, 'method': self.CreateDownloadButton}]
        
        GenericSearchList.__init__(self, columns, LIST_GREY, [7,7], True)
        
    def CreateHeader(self):
        header = ChannelHeader(self, self.columns)
        header.SetEvents(self.OnBack)
        return header
    
    def CreateList(self):
        list = GenericSearchList.CreateList(self)
        return list
   
    def CreateFooter(self):
        footer = ChannelFooter(self)
        footer.SetEvents(self.OnSpam, self.OnFavorite, self.OnRemoveVote)
        return footer
        
    def SetTitle(self, title):
        self.title = title
        self.header.SetTitle("%s's channel"%title)
    
    def SetDescription(self, description):
        self.header.SetDescription(description)
   
    def toggleFamilyFilter(self):
        GenericSearchList.toggleFamilyFilter(self)
        self.guiutility.showChannel(self.title, self.publisher_id)
   
    def GetManager(self):
        if getattr(self, 'manager', None) == None:
            self.manager = ChannelManager(self) 
        return self.manager
    
    def SetData(self, data):
        List.SetData(self, data)
        
        data = [(file['infohash'],[file['name'], file['time_stamp'], file['length'], 0, 0], file) for file in data]
        return self.list.SetData(data)
    
    def SetNrResults(self, nr, nr_filtered):
        if isinstance(nr, int):
            self.total_results = nr
            if self.total_results == 1:
                self.header.SetSubTitle('Discovered %d torrent'%self.total_results)
            else:
                self.header.SetSubTitle('Discovered %d torrents'%self.total_results)
        
        GenericSearchList.SetNrResults(self, None, nr_filtered, None, None)
    
    def RefreshData(self, key, data):
        List.RefreshData(self, key, data)
        
        data = (data['infohash'],[data['name'], data['time_stamp'], data['length'], 0, 0], data)
        self.list.RefreshData(key, data)
        
        item = self.list.GetItem(key)
        panel = item.GetExpandedPanel()
        if panel:
            panel.UpdateStatus()
    
    def Reset(self):
        GenericSearchList.Reset(self)
        self.publisher_id = 0
    
    def OnExpand(self, item):
        item.button.Hide()
        item.button.Refresh()
        return TorrentDetails(item, item.original_data, noChannel = True)
        
    def OnRemoveVote(self, event):
        self.channelsearch_manager.remove_vote(self.publisher_id)
        self.footer.SetStates(False, False)
    
    def OnFavorite(self, event = None):
        self.channelsearch_manager.favorite(self.publisher_id)
        self.footer.SetStates(False, True)
        
        #Request all items from connected peers
        channelcast = BuddyCastFactory.getInstance().channelcast_core
        channelcast.updateAChannel(self.publisher_id)
        
        def db_callback():
            self.uelog.addEvent(message="ChannelList: user marked a channel as favorite", type = 2)
        self.guiutility.frame.guiserver.add_task(db_callback)
        
    def OnSpam(self, event):
        dialog = wx.MessageDialog(None, "Are you sure you want to report %s's channel as spam?" % self.title, "Report spam", wx.ICON_QUESTION | wx.YES_NO | wx.NO_DEFAULT)
        if dialog.ShowModal() == wx.ID_YES:
            self.channelsearch_manager.spam(self.publisher_id)
            self.footer.SetStates(True, False)
            
            def db_callback():
                self.uelog.addEvent(message="ChannelList: user marked a channel as spam", type = 2)
            self.guiutility.frame.guiserver.add_task(db_callback)
        dialog.Destroy()
    
    def OnBack(self, event):
        self.guiutility.GoBack()
        
    def StartDownload(self, torrent):
        states = self.footer.GetStates()
        if not states[1]:
            nrdownloaded = self.channelsearch_manager.getNrTorrentsDownloaded(self.publisher_id) + 1
            if  nrdownloaded > 1:
                dial = wx.MessageDialog(self, "You downloaded %d torrents from this Channel. 'Mark as favorite' will ensure that you will always have access to newest channel content.\n\nDo you want to mark this channel as one of your favorites now?"%nrdownloaded, 'Mark as Favorite?', wx.YES_NO | wx.YES_DEFAULT | wx.ICON_QUESTION)
                if dial.ShowModal() == wx.ID_YES:
                    self.OnFavorite()
                    clickedYes = True
                else:
                    clickedYes = False
                    
                dial.Destroy()
                
                def db_callback():
                    if clickedYes:
                        self.uelog.addEvent(message="ChannelList: user clicked yes to mark as favorite", type = 2)
                    else:
                        self.uelog.addEvent(message="ChannelList: user clicked no to mark as favorite", type = 2)
                self.guiutility.frame.guiserver.add_task(db_callback)
                
        GenericSearchList.StartDownload(self, torrent)
        
class MyChannelList(List):
    def __init__(self):
        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility
        
        columns = [{'name':'Name', 'width': wx.LIST_AUTOSIZE, 'sortAsc': True}, \
                   {'name':'Date Added', 'width': 85, 'fmt': self.format_time, 'defaultSorted': True}]
   
        List.__init__(self, columns, LIST_BLUE, [7,7])
      
    def CreateHeader(self):
        self.myheader = MyChannelHeader(self, self.columns)
        self.myheader.SetBackgroundColour(self.background)
        self.myheader.SetName(self.utility.session.get_nickname())
        return self.myheader
    
    def CreateList(self):
        return MyChannelTabs(self, self.background, self.columns, self.spacers, self.singleSelect)
    
    def CreateFooter(self):
        #small ugly hack to correct references
        self.header = self.list.header
        self.list = self.list.list
        
        #Return default footer
        return List.CreateFooter(self)
    
    def GetManager(self):
        if getattr(self, 'manager', None) == None:
            self.manager = MyChannelManager(self) 
        return self.manager
    
    def SetData(self, data, nr_favorites):
        List.SetData(self, data)
        
        data = [(file['infohash'],[file['name'],file['time_stamp']], file) for file in data]
        self.myheader.SetNrTorrents(len(data), nr_favorites)
        
        if len(data) > 0:
            return self.list.SetData(data)
        self.list.ShowMessage('You are currently not sharing any torrents in your channel.')
        return 0
    
    def ShowList(self):
        self.list.SetFocus()
    
    def OnExpand(self, item):
        return MyChannelDetails(item, item.original_data, self.GetManager().my_permid)
    
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
        
class ChannelCategoriesList(List):
    def __init__(self):
        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility
        columns = [{'width': wx.LIST_AUTOSIZE}]
    
        List.__init__(self, columns, LIST_GREY, [7,7], True)
    
    def CreateHeader(self):
        title = TitleHeader(self, self.columns, 1, wx.FONTWEIGHT_NORMAL)
        title.SetTitle('Categories')
        return title
    
    def CreateList(self):
        return FixedListBody(self, self, self.columns, self.spacers[0], self.spacers[1], self.singleSelect)    
    
    def _PostInit(self):
        List._PostInit(self)
        self.list.SetData([(1,['Popular'],None), (2,['New'],None), (6, ['Updated'], None), (3,['Favorites'],None), (4,['All'],None), (5,['My Channel'],None)])
        self.SetMinSize((-1, self.GetBestSize()[1]))
        
        self.Select(1, False)
        wx.CallAfter(self.guiutility.showChannelCategory, 'Popular', False)
        
    def OnExpand(self, item):
        if item.data[0] in ['Popular','New','Favorites','All','Updated']:
            wx.CallAfter(self.guiutility.showChannelCategory, item.data[0])
            
        elif item.data[0] == 'My Channel':
            self.guiutility.ShowPage('mychannel')
        
        #Show highlight
        return True
    
    def GetSelectedCategory(self):
        category = self.list.GetExpandedItem()
        if category:
            return category.data[0]
        return ''

    def SetQuicktip(self, quicktip):
        self.quicktip = quicktip
    def Quicktip(self, html):
        html = '<font size=\'2\'><b>Quick Tip:</b> ' + html + '</font>' 
        self.quicktip.SetPage(html)