# Written by Niels Zeilemaker
import os
import sys
from threading import currentThread
from traceback import print_stack
from math import log

import wx
from wx import html
from wx.lib.wordwrap import wordwrap
from time import time
from datetime import date, datetime
from colorsys import hsv_to_rgb, rgb_to_hsv

from Tribler.Main.vwxGUI.widgets import ProgressStaticText, HorizontalGauge, TorrentStatus, FancyPanel
from Tribler.Core.API import *
from Tribler.Core.CacheDB.sqlitecachedb import bin2str
from Tribler.Core.Utilities.utilities import get_collected_torrent_filename
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility, forceWxThread
from Tribler.Main.vwxGUI.UserDownloadChoice import UserDownloadChoice

from Tribler.__init__ import LIBRARYNAME

from __init__ import *
from list_body import *
from list_item import *
from list_details import *
from list_footer import *
from list_header import *

from widgets import _set_font, ChannelPopularity, SwarmHealth
        
from Tribler.Main.Utility.GuiDBHandler import startWorker, cancelWorker, GUI_PRI_DISPERSY
from Tribler.Main.Utility.GuiDBTuples import ChannelTorrent, Channel
from Tribler.Main.vwxGUI.list_footer import ChannelListFooter
from Tribler.Main.Dialogs.RemoveTorrent import RemoveTorrent
from Tribler.Category.Category import Category

DEBUG = False
DEBUG_RELEVANCE = False
MAX_REFRESH_PARTIAL = 5

class BaseManager:
    def __init__(self, list):
        self.list = list
        self.dirtyset = set()
        self.guiutility = GUIUtility.getInstance()
    
    def Reset(self):
        self.dirtyset.clear()
    
    def refreshDirty(self):
        if 'COMPLETE_REFRESH' in self.dirtyset or len(self.dirtyset) > MAX_REFRESH_PARTIAL or len(self.dirtyset) == 0:
            if len(self.dirtyset) > 0:
                self.list.MarkForRemoval(self.dirtyset)
                
            self.refresh()
        else:
            if 'COMPLETE_REFRESH' in self.dirtyset:
                self.dirtyset.remove('COMPLETE_REFRESH')
            self.refresh_partial(self.dirtyset)
            self.list.dirty = False
        self.dirtyset.clear()
    
    def refresh(self):
        raise NotImplementedError('refresh is not implemented')

    def refresh_partial(self, ids):
        raise NotImplementedError('refresh_partial is not implemented')
    
    def do_or_schedule_refresh(self, force_refresh = False):
        if self.list.isReady and (self.list.ShouldGuiUpdate() or force_refresh):
            self.refresh()
        else:
            self.dirtyset.add('COMPLETE_REFRESH')
            self.list.dirty = True
        
    def do_or_schedule_partial(self, ids, force_refresh = False):
        if self.list.isReady and (self.list.ShouldGuiUpdate() or force_refresh):
            if len(ids) > MAX_REFRESH_PARTIAL:
                self.list.RemoveItems(ids)
                self.refresh()
            else:
                self.refresh_partial(ids)
        else:
            self.dirtyset.update(ids)
            self.list.dirty = True

class RemoteSearchManager(BaseManager):
    def __init__(self, list):
        BaseManager.__init__(self, list)
        self.oldkeywords = ''
        
        self.guiserver = self.guiutility.frame.guiserver
        self.torrentsearch_manager = self.guiutility.torrentsearch_manager
        self.channelsearch_manager = self.guiutility.channelsearch_manager
        
        self.Reset()
   
    def Reset(self):
        BaseManager.Reset(self)
        
        if self.oldkeywords:
            cancelWorker("RemoteSearchManager_refresh_%s"%self.oldkeywords)
            cancelWorker("RemoteSearchManager_refresh_channel_%s"%self.oldkeywords)
        
        self.oldkeywords = ''
        self.torrentsearch_manager.oldsearchkeywords = None
        self.data_channels = []
        
    def SetKeywords(self, keywords):
        if self.oldkeywords != keywords:
            self.list.Reset()
            self.oldkeywords = keywords
    
    def NewResult(self, keywords):
        if self.oldkeywords == keywords:
            self.list.NewResult()

    def refresh(self,remote=False):
        def db_callback():
            if DEBUG:
                begintime = time()
                
            keywords = self.oldkeywords
            
            total_items, nrfiltered, new_items, selected_bundle_mode, data_files, modified_hits = self.torrentsearch_manager.getHitsInCategory()
            total_channels, new_channels, self.data_channels = self.channelsearch_manager.getChannelHits()
            if DEBUG:
                print >> sys.stderr, 'RemoteSearchManager: refresh returning results took', time() - begintime, time()
            
            return keywords, data_files, total_items, nrfiltered, new_items, total_channels, new_channels, selected_bundle_mode, modified_hits
        delay = 0.5 if remote else 0.0
        workerType = "guiTaskQueue" if remote else "dbThread"
        startWorker(self._on_refresh, db_callback, delay=delay, uId = "RemoteSearchManager_refresh_%s"%self.oldkeywords, retryOnBusy=True, workerType = workerType, priority=GUI_PRI_DISPERSY)

    def _on_refresh(self, delayedResult):
        keywords, data_files, total_items, nrfiltered, new_items, total_channels, new_channels, selected_bundle_mode, modified_hits = delayedResult.get()
        
        if keywords == self.oldkeywords:
            self.list.SetSelectedBundleMode(selected_bundle_mode)
            
            if modified_hits:
                self.list.RemoveItems(modified_hits)
            
            if new_items or modified_hits:
                self.list.SetData(data_files)
            else:
                if DEBUG:
                    print >> sys.stderr, "RemoteSearchManager: not refreshing list, no new items"
        elif DEBUG:
            print >> sys.stderr, "RemoteSearchManager: ignoring old keywords"
        
    def refresh_channel(self):
        def db_callback():
            [total_channels, new_hits, self.data_channels] = self.channelsearch_manager.getChannelHits()
            return total_channels
        
        startWorker(self._on_refresh_channel, db_callback, uId = "RemoteSearchManager_refresh_channel_%s"%self.oldkeywords, retryOnBusy=True,priority=GUI_PRI_DISPERSY)
    
    def _on_refresh_channel(self, delayedResult):
        self.list.SetNrChannels(delayedResult.get())
        
    def refresh_partial(self, ids):
        for infohash in ids:
            curTorrent = self.list.GetItem(infohash).original_data
            if isinstance(curTorrent, ChannelTorrent):
                startWorker(self.list.RefreshDelayedData, self.channelsearch_manager.getTorrentFromChannelTorrentId, cargs=(infohash,), wargs=(curTorrent.channel,curTorrent.channeltorrent_id), retryOnBusy=True,priority=GUI_PRI_DISPERSY)
            else:
                startWorker(self.list.RefreshDelayedData, self.torrentsearch_manager.getTorrentByInfohash, cargs=(infohash,), wargs=(infohash,), retryOnBusy=True,priority=GUI_PRI_DISPERSY)
    
    def showSearchSuggestions(self, keywords):
        startWorker(self.list._ShowSuggestions, self.torrentsearch_manager.getSearchSuggestion, cargs = (keywords, ), wargs=(keywords, 3), retryOnBusy=True, priority=GUI_PRI_DISPERSY)
    
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

class LocalSearchManager(BaseManager):
    def __init__(self, list):
        BaseManager.__init__(self, list)
        
        self.library_manager = self.guiutility.library_manager
        self.prev_refresh_if = 0
    
    def refresh(self):
        startWorker(self._on_data, self.library_manager.getHitsInCategory, uId = "LocalSearchManager_refresh", retryOnBusy=True, priority=GUI_PRI_DISPERSY)
    
    def refresh_partial(self, ids):
        for infohash in ids:
            startWorker(self.list.RefreshDelayedData, self.library_manager.getTorrentFromInfohash, cargs=(infohash,), wargs=(infohash,), retryOnBusy=True,priority=GUI_PRI_DISPERSY)
        
    def refresh_if_exists(self, infohashes, force = False):
        def db_call():
            if self.library_manager.exists(infohashes):
                print >> sys.stderr, long(time()), "Scheduling a refresh, missing some infohashes in the Library"
                
                self.refresh()
            else:
                print >> sys.stderr, long(time()), "Not scheduling a refresh"
        
        diff = time() - self.prev_refresh_if        
        if force or diff > 30:
            self.prev_refresh_if = time()

            startWorker(None, db_call, uId="LocalSearchManager_refresh_if_exists", retryOnBusy=True,priority=GUI_PRI_DISPERSY)
        else:
            print >> sys.stderr, long(time()), "Not scheduling a refresh, update limit", long(time()), long(self.prev_refresh_if)
            
    def refresh_or_expand(self, infohash):
        if not self.list.InList(infohash):
            def select(delayedResult):
                delayedResult.get()
                self.refresh_or_expand(infohash)
                
            startWorker(select, self.refresh_partial, wargs = ([infohash], ), priority=GUI_PRI_DISPERSY)
        else:
            self.list.Select(infohash)

    @forceWxThread
    def _on_data(self, delayedResult):
        total_items, data = delayedResult.get()

        self.list.SetData(data)
        self.list.Layout()
        
    def torrentUpdated(self, infohash):
        if self.list.InList(infohash):
            self.do_or_schedule_partial([infohash])
            
    def torrentsUpdated(self, infohashes):
        infohashes = [infohash for infohash in infohashes if self.list.InList(infohash)]
        self.do_or_schedule_partial(infohashes)            
            
    def downloadStarted(self, infohash):
        self.prev_refresh_if = 0
        self.refresh()
        
class ChannelSearchManager(BaseManager):
    def __init__(self, list):
        BaseManager.__init__(self, list)
        self.category = ''
        
        self.channelsearch_manager = self.guiutility.channelsearch_manager
        self.Reset()
    
    def Reset(self):
        BaseManager.Reset(self)
        if self.category:
            cancelWorker("ChannelSearchManager_refresh_%s"%self.category)

        self.category = ''
        self.dirtyset.clear()
        self.prev_refresh_if = 0
    
    def do_or_schedule_refresh(self, force_refresh = False):
        if self.list.isReady and (self.list.ShouldGuiUpdate() or force_refresh):
            diff = time() - self.prev_refresh_if        
            if diff > 5 or force_refresh:
                self.prev_refresh_if = time()
                self.refresh()
        else:
            self.dirtyset.add('COMPLETE_REFRESH')
            self.list.dirty = True
            
    def refreshDirty(self):
        if self.category != 'searchresults' and 'COMPLETE_REFRESH' in self.dirtyset or len(self.dirtyset) > 5:
            self.refresh()
        else:
            if 'COMPLETE_REFRESH' in self.dirtyset:
                self.dirtyset.remove('COMPLETE_REFRESH')
            
            self.refresh_partial()
            self.list.dirty = False
        self.dirtyset.clear()
    
    def refresh(self, search_results = None):
        if DEBUG:
            print >> sys.stderr, "ChannelManager complete refresh"
        
        if self.category != 'searchresults':
            category = self.category
            
            def db_callback():
                self.list.dirty = False
                
                data = []
                total_items = 0
                
                if category == 'New':
                    total_items, data = self.channelsearch_manager.getNewChannels()
                elif category == 'Popular':
                    total_items, data = self.channelsearch_manager.getPopularChannels()
                elif category == 'Updated':
                    total_items, data = self.channelsearch_manager.getUpdatedChannels()
                elif category == 'All':
                    total_items, data = self.channelsearch_manager.getAllChannels()
                elif category == 'Favorites':
                    total_items, data = self.channelsearch_manager.getMySubscriptions()
                elif category == 'Mine':
                    total_items, data = self.channelsearch_manager.getMyChannels()                   
                return data, category
            
            startWorker(self._on_data_delayed, db_callback, uId = "ChannelSearchManager_refresh_%s"%category, retryOnBusy=True, priority=GUI_PRI_DISPERSY)

        else:
            if search_results:
                total_items = len(search_results)
                self._on_data(search_results, self.category)
    
    def _on_data_delayed(self, delayedResult):
        data, category = delayedResult.get()
        self._on_data(data, category)
    
    def _on_data(self, data, category):
        if category == self.category:
            if category != 'searchresults': #if we filter empty channels from search we will never see them
                data = [channel for channel in data if not channel.isEmpty()]
            
            self.list.SetCategory(category)
            self.list.SetData(data)
            if DEBUG:
                print >> sys.stderr, "ChannelManager complete refresh done"
            
    def refresh_partial(self, ids = None):
        if ids:
            self.dirtyset.update(ids)
        
        def do_db():
            ids = list(self.dirtyset)
            self.dirtyset.clear()
            
            return self.channelsearch_manager.getChannels(ids)
        
        def do_gui(delayedResult):
            _,newChannels = delayedResult.get()
            
            for channel in newChannels:
                id = channel.id
                if self.list.InList(id):
                    item = self.list.GetItem(id)
                    oldChannel = item.original_data
                    if oldChannel.torrents:
                        channel.torrents = oldChannel.torrents
            
                self.list.RefreshData(id, channel)
        startWorker(do_gui, do_db, uId = "ChannelSearchManager_refresh_partial", retryOnBusy=True, priority=GUI_PRI_DISPERSY)
      
    def SetCategory(self, category, force_refresh = False):
        if category != self.category:
            self.list.Reset()

            self.category = category
            if category != 'searchresults':
                self.do_or_schedule_refresh(force_refresh)
        else:
            self.list.DeselectAll()
           
    def channelUpdated(self, id, votecast = False, myvote = False):
        if self.list.isReady:
            #only update when shown
            if self.list.InList(id):
                self.do_or_schedule_partial([id])
                
            elif self.category in ['All', 'New']:
                #Show new channel, but only if we are not showing search results
                self.do_or_schedule_refresh()
            
            elif self.category == 'Popular':
                if len(self.list.GetItems()) < 20:
                    self.do_or_schedule_refresh()
                    
            elif self.category == 'Favorites' and myvote:
                self.do_or_schedule_refresh()
                
            else:
                if not votecast:
                    if self.category == 'All':
                        update = True
                    elif self.category == 'Popular':
                        update = len(self.list.GetItems()) < 20
                    else:
                        update = False
                
                if myvote and self.category == "Favorites":
                    update = True
                
                if update: 
                    self.do_or_schedule_refresh()
                    
    def joinChannel(self, cid):
        self.channelsearch_manager.do_vote_cid(cid, 2)

class XRCPanel(wx.Panel):
    def __init__(self, parent = None):
        self.parent = parent
        self.isReady = False
        
        if parent:
            wx.Panel.__init__(self, parent)
            self.SetForegroundColour(parent.GetForegroundColour())
            self._PostInit()
            self.isReady = True
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
        
        def doPost():
            self._PostInit()
            self.isReady = True
        
        wx.CallAfter(doPost)
        event.Skip()
            
    def _PostInit(self):
        pass

class List(wx.BoxSizer):
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
        self.hasData = False
        self.rawfilter = ''
        self.filter = ''
        
        self.footer = self.header = self.list = None
        self.nr_results = 0
        self.nr_filtered = 0
        self.cur_nr_filtered = 0

        self.guiutility = GUIUtility.getInstance()
        self.uelog = UserEventLogDBHandler.getInstance()
        self.category = Category.getInstance()
        
        self.leftLine = self.rightLine = None
        self.parent = parent
        
        wx.BoxSizer.__init__(self, wx.VERTICAL)
        
        self.isReady = False
        self._PostInit()
        self.isReady = True
        
        self.guiutility.addList(self)
        self.GotFilter(None)
    
    def _PostInit(self):
        self.header = self.CreateHeader(self.parent)
        if self.header:
            self.Add(self.header, 0, wx.EXPAND)
        
        self.list = self.CreateList(self.parent)

        #left and right borders
        if self.borders:
            listSizer = wx.BoxSizer(wx.HORIZONTAL)
            self.leftLine = wx.Panel(self.parent, size=(1,-1))
            self.rightLine = wx.Panel(self.parent, size=(1,-1))
        
            listSizer.Add(self.leftLine, 0, wx.EXPAND)
            listSizer.Add(self.list, 1, wx.EXPAND)
            listSizer.Add(self.rightLine, 0, wx.EXPAND)
            self.Add(listSizer, 1, wx.EXPAND)
        else:
            self.Add(self.list, 1, wx.EXPAND)
        
        self.footer = self.CreateFooter(self.parent)
        if self.footer:
            self.Add(self.footer, 0, wx.EXPAND)
        
        self.SetBackgroundColour(self.background)
        self.Layout()
        
        self.list.Bind(wx.EVT_SIZE, self.OnSize)
    
    def CreateHeader(self, parent):
        return ListHeader(parent, self, self.columns)

    def CreateList(self, parent = None, listRateLimit = 1):
        if not parent:
            parent = self
        return ListBody(parent, self, self.columns, self.spacers[0], self.spacers[1], self.singleSelect, self.showChange, listRateLimit=listRateLimit)

    def CreateFooter(self, parent):
        return ListFooter(parent)
    
    def OnSize(self, event):
        assert self.isReady, "List not ready"
        event.Skip()
        
    def OnSort(self, column, reverse):
        assert self.isReady, "List not ready"
        if self.isReady:
            self.list.OnSort(column, reverse)
    
    @warnWxThread
    def Reset(self):
        assert self.isReady, "List not ready"

        self.nr_filtered = self.nr_results = 0
        if self.isReady and self.hasData:
            self.rawfilter = ''
            self.filter = ''
            self.hasData = False
            
            manager = self.GetManager()
            if manager and getattr(manager, 'Reset', False):
                manager.Reset()
            
            self.list.Reset()
            
            if self.header:
                self.header.Reset()

            if self.footer:
                self.footer.Reset()

            self.dirty = False
            self.Layout()
            
            return True
        return False
    
    @warnWxThread
    def OnExpand(self, item):
        assert self.isReady, "List not ready"
        
        wx.CallAfter(self.guiutility.frame.top_bg.TorrentsChanged)
    
    @warnWxThread
    def OnCollapse(self, item, panel):
        assert self.isReady, "List not ready"
        
        self.OnCollapseInternal(item)
        if panel:
            panel.Destroy()
            
        wx.CallAfter(self.guiutility.frame.top_bg.TorrentsChanged)
            
    def OnCollapseInternal(self, item):
        pass
    
    def GetManager(self):
        pass
    
    def do_or_schedule_refresh(self, force_refresh = False):
        self.GetManager().do_or_schedule_refresh(force_refresh = force_refresh)
    
    @warnWxThread
    def SetDelayedData(self, delayedResult):
        assert self.isReady, "List not ready"
        self.SetData(delayedResult.get())
    
    @warnWxThread
    def SetData(self, data):
        assert self.isReady, "List not ready"
        self.hasData = True
        
    @warnWxThread
    def RefreshDelayedData(self, delayedResult, key):
        assert self.isReady, "List not ready"
        data = delayedResult.get()
        if data:
            self.RefreshData(key, data)
    
    @warnWxThread
    def RefreshData(self, key, data):
        assert self.isReady, "List not ready"
    
    def RemoveItem(self, key):
        assert self.isReady, "List not ready"
        self.list.RemoveKey(key)

    def RemoveItems(self, keys):
        assert self.isReady, "List not ready"
        self.list.RemoveKeys(keys)
        
    def MarkForRemoval(self, keys):
        assert self.isReady, "List not ready"
        self.list.MarkForRemoval(keys)

    @warnWxThread
    def SetNrResults(self, nr):
        assert self.isReady, "List not ready"
        self.nr_results = nr
        
        #ff uses two variables, cur_nr_filtered is used to count the total number in the loop
        #nr_filtered is the total number filtered from the previous run
        self.nr_filtered = self.cur_nr_filtered
        self.cur_nr_filtered = 0
        
    def GetNrResults(self):
        return self.nr_results
            
    def InList(self, key, onlyCreated = True):
        assert self.isReady, "List not ready"
        if self.isReady:
            return self.list.InList(key, onlyCreated)
    
    def GetItem(self, key):
        assert self.isReady, "List not ready"
        if self.isReady:
            return self.list.GetItem(key)
        
    def GetItems(self):
        assert self.isReady, "List not ready"
        if self.isReady:
            return self.list.items
    
    def GetItemPos(self, key):
        assert self.isReady, "List not ready"
        if self.isReady:
            return self.list.GetItemPos(key)
    
    def GetExpandedItem(self):
        assert self.isReady, "List not ready"
        if self.isReady:
            return self.list.GetExpandedItem()
        
    def GetExpandedItems(self):
        assert self.isReady, "List not ready"
        if self.isReady:
            return self.list.GetExpandedItems()
    
    @warnWxThread
    def Focus(self):
        assert self.isReady, "List not ready"
        if self.isReady:
            self.list.SetFocusIgnoringChildren()
    
    @warnWxThread    
    def HasFocus(self):
        assert self.isReady, "List not ready"
        focussed = wx.Window.FindFocus()
        return focussed == self.list
    
    @warnWxThread
    def SetBackgroundColour(self, colour):
        if self.header:
            self.header.SetBackgroundColour(colour)
        
        if self.leftLine:
            self.leftLine.SetBackgroundColour(colour)
            
        self.list.SetBackgroundColour(colour)
        
        if self.rightLine:
            self.rightLine.SetBackgroundColour(colour)
        
        if self.footer:
            self.footer.SetBackgroundColour(colour)
    
    @warnWxThread
    def ScrollToEnd(self, scroll_to_end):
        assert self.isReady, "List not ready"
        if self.isReady:
            self.list.ScrollToEnd(scroll_to_end)
    
    @warnWxThread
    def ScrollToId(self, id):
        assert self.isReady, "List not ready"
        self.list.ScrollToId(id)
    
    @warnWxThread
    def DeselectAll(self):
        assert self.isReady, "List not ready"
        if self.isReady:
            self.list.DeselectAll()
        
    @warnWxThread
    def Select(self, key, raise_event = True):
        assert getattr(self, 'list', False), "List not ready"
        if self.isReady:
            self.list.Select(key, raise_event)
            
    def ShouldGuiUpdate(self):
        if not self.IsShownOnScreen():
            return False
        return self.guiutility.ShouldGuiUpdate()

    def ShowLoading(self):
        if self.isReady:
            self.list.ShowLoading()
            
    def ShowMessage(self, message, header = None, altControl = None):
        if self.isReady:
            self.list.ShowMessage(message, header, altControl)
            
    def OnLoadAll(self):
        if self.isReady:
            self.list.OnLoadAll()
            
    def IsShownOnScreen(self):
        return self.IsShown(0)
    
    def Freeze(self):
        self.parent.Freeze()
    def Thaw(self):
        self.parent.Thaw()
        
    def Show(self, show = True, isShown = False):
        self.ShowItems(show)
        
        if show and (isShown or self.IsShownOnScreen()):
            if self.dirty:
                self.dirty = False
    
                manager = self.GetManager()
                if manager:
                    manager.refreshDirty()
            
            self.list.Layout()
        self.list.Show(show)
            
    def ShowFooter(self, show = True):
        self.footer.Show(show)

    def GotFilter(self, keyword = None):
        oldrawfilter = self.rawfilter
        if keyword != None:
            self.rawfilter = keyword.lower().strip()
        else:
            self.LoadEnabledCategoryIDs()
        
        if self.rawfilter == '' and not self.guiutility.getFamilyFilter():
            wx.CallAfter(self.list.SetFilter, None, None, keyword == None)
            
        else:
            highlight = True
            if oldrawfilter[:-1] == self.rawfilter: #did the user simple remove 1 character?
                highlight = False
            
            wx.CallAfter(self.list.SetFilter, self.MatchFilter, self.GetFilterMessage, highlight)
            
        self.OnFilter(self.rawfilter)

    def OnFilter(self, keyword):
        self.filter = keyword
        if keyword:
            self.filter = keyword.strip()
            try:
                re.compile(self.filter)
                self.header.FilterCorrect(True)
                
            except: #regex incorrect
                self.filter = ''
                self.header.FilterCorrect(False)
                
    def LoadEnabledCategoryIDs(self):
        torrent_db = self.guiutility.utility.session.open_dbhandler(NTFY_TORRENTS)
        enabled_category_keys = [key.lower() for key, _ in self.category.getCategoryNames()]
        self.enabled_category_ids = set([0, 8])
        for key, id in torrent_db.category_table.iteritems():
            if key.lower() in enabled_category_keys:
                self.enabled_category_ids.add(id)
        self.deadstatus_id = torrent_db.status_table['dead']
    
    def MatchFFilter(self, item):
        result = True
        if self.guiutility.getFamilyFilter():
            if isinstance(item[2], (Torrent, CollectedTorrent)):
                torrent = item[2]
                category = torrent.category_id if torrent.category_id else 0
                result = category in self.enabled_category_ids
                    
            elif isinstance(item[2], Channel):
                result = not self.category.xxx_filter.isXXX(item[2].name, False)
                
        if not result:
            self.cur_nr_filtered += 1
            
        return result
    
    def GetFFilterMessage(self):
        if self.guiutility.getFamilyFilter() and self.nr_filtered:
            return None, '%d items were blocked by the Familiy filter'%self.nr_filtered
        return None, ''
    
    def MatchFilter(self, item):
        ff = self.MatchFFilter(item)
        if self.filter == '':
            return ff
        return re.search(self.filter, item[1][0].lower()) and ff
    
    def GetFilterMessage(self, empty = False):
        if self.rawfilter:
            if empty:
                message = '0 items'
            else:
                message = 'Only showing items'
            
            if self.filter:
                return None, message + ' matching "%s"'%self.filter
            return None, message
        else:
            return self.GetFFilterMessage()
        
    @warnWxThread
    def Layout(self):
        return wx.BoxSizer.Layout(self)
    
    def SetupScrolling(self, *args, **kwargs):
        return self.list.SetupScrolling(*args, **kwargs)
    
class SizeList(List):
    
    def __init__(self, columns, background, spacers = [0,0], singleSelect = False, showChange = False, borders = True, parent = None):
        List.__init__(self, columns, background, spacers, singleSelect, showChange, borders, parent)
        self.prevStates = {}
        self.library_manager = self.guiutility.library_manager
        
        self.curMax = -1
        self.filteredMax = -1
        self.sizefilter = None
    
    @warnWxThread
    def OnCollapse(self, item, panel):
        List.OnCollapse(self, item, panel)
        if panel:
            self.guiutility.SetBottomSplitterWindow(None)
    
    def OnFilter(self, keyword):
        new_filter = keyword.lower().strip()
        
        self.sizefilter = None
        if new_filter.find("size=") > -1:
            try:
                minSize = 0
                maxSize = sys.maxint
                
                start = new_filter.find("size=") + 5
                end = new_filter.find(" ", start)
                if end == -1:
                    end = len(new_filter)
                    
                sizeStr = new_filter[start:end]
                if sizeStr.find(":") > -1:
                    sizes = sizeStr.split(":")
                    if sizes[0] != '':
                        minSize = int(sizes[0])
                    if sizes[1] != '':
                        maxSize = int(sizes[1])
                else:
                    minSize = maxSize = int(sizeStr)
                    
                self.sizefilter = [minSize, maxSize]
                new_filter = new_filter[:start - 5] + new_filter[end:]
                new_filter = new_filter.rstrip()

            except:
                pass
        List.OnFilter(self, new_filter)
    
    def MatchFilter(self, item):
        listmf = List.MatchFilter(self, item)
        
        if listmf:
            length = item[2].get('length', 0)
            self.filteredMax = max(self.filteredMax, length)
            
            if self.sizefilter:
                size = int(length/1048576.0)
                if size < self.sizefilter[0] or size > self.sizefilter[1]:
                    return False
        return listmf
    
    def GetFilterMessage(self, empty = False):
        header, message = List.GetFilterMessage(self, empty)
        
        if self.sizefilter:
            if self.sizefilter[0] == self.sizefilter[1]:
                message += " equal to %d MB in size"%self.sizefilter[0]
            elif self.sizefilter[0] == 0:
                message += " smaller than %d MB in size"%self.sizefilter[1]
            elif self.sizefilter[1] == sys.maxint:
                message += " larger than %d MB in size"%self.sizefilter[0]
            else:
                message += " between %d and %d MB in size"%(self.sizefilter[0], self.sizefilter[1])
        return header, message
    
    def SetData(self, data):
        List.SetData(self, data)
        
        if getattr(self.header, 'SetSliderMinMax', None):
            #detect min/max size for this data
            minSize = 0
            self.curMax = -1
            for item in data:
                if isinstance(item, tuple) and item and isinstance(item[0], Channel):
                    pass
                else:
                    if 'bundle' in item:
                        item = item['bundle'][0]
                    self.curMax = max(self.curMax, item.length)
            
    @warnWxThread        
    def SetNrResults(self, nr):
        List.SetNrResults(self, nr)
        
        if getattr(self.header, 'SetSliderMinMax', None):
            if nr != 0:
                self.header.SetSliderMinMax(0, max(0, self.filteredMax) if self.sizefilter or self.guiutility.getFamilyFilter() else max(0, self.curMax))
            self.filteredMax = -1
        
    @warnWxThread
    def RefreshItems(self, dslist, magnetlist, rawdata = False):
        dsdict = {}
        old_dsdict = {}
        for ds in dslist:
            id = ds.get_download().get_def().get_id()
            dsdict[id] = ds
        
        curStates = {}
        didStateChange = False
        
        if rawdata:
            list_data = [(self.list.items.get(getattr(values[2],'infohash', None), None), values[2]) for values in self.list.raw_data or []]
        else:
            list_data = [(item, item.original_data) for item in self.list.items.itervalues() if item]
            
        for item, original_data in list_data:
            if isinstance(original_data, Torrent):
                infohash = original_data.infohash
                old_dsdict[infohash] = original_data.ds
                prevState = self.prevStates.get(infohash, (original_data.state, original_data.magnetState))
                
                original_data.clearDs()
                
                removekeys = [key for key, ds in dsdict.iteritems() if original_data.addDs(ds)]
                for key in removekeys:
                    del dsdict[key]
                    
                if infohash in magnetlist:
                    original_data.magnetstatus = magnetlist[infohash]
                else:
                    original_data.magnetstatus = None
                
                if item: #torrents in raw_data and items are not equal
                    item.original_data.dslist = original_data.dslist
                    item.original_data.magnetstatus = original_data.magnetstatus
    
                curState = curStates[infohash] = original_data.state, original_data.magnetState
                if curState != prevState:
                    didStateChange = True
    
                    if item:
                        item.RefreshData([infohash, item.data ,item.original_data])
    
        if didStateChange:
            self.guiutility.frame.top_bg.TorrentsChanged()
        self.prevStates = curStates
        
        return didStateChange, old_dsdict, dsdict
    
    def Show(self, show = True, isShown = False):
        List.Show(self, show, isShown)
        if show:
            self.library_manager.add_download_state_callback(self.RefreshItems)
        else:
            self.library_manager.remove_download_state_callback(self.RefreshItems)

class GenericSearchList(SizeList):
    def __init__(self, columns, background, spacers = [0,0], singleSelect = False, showChange = False, borders = True, parent = None):
        SizeList.__init__(self, columns, background, spacers, singleSelect, showChange, borders, parent)

        self.infohash2key = {} # bundled infohashes
        
        self.statusDHT = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","status_dht.png"), wx.BITMAP_TYPE_ANY)
        self.statusInactive = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","status_inact.png"), wx.BITMAP_TYPE_ANY)
        self.statusDownloading = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","status_dl.png"), wx.BITMAP_TYPE_ANY)
        self.statusFinished = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","status_fin.png"), wx.BITMAP_TYPE_ANY)
        self.statusSeeding = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","status_sd.png"), wx.BITMAP_TYPE_ANY)
        self.statusStopped = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","status_stop.png"), wx.BITMAP_TYPE_ANY)     

        self.favorite = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","starEnabled.png"), wx.BITMAP_TYPE_ANY)
        self.normal = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","star.png"), wx.BITMAP_TYPE_ANY)
        
        self.ministar = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","ministarEnabled.png"), wx.BITMAP_TYPE_ANY)
        self.normalministar = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","ministar.png"), wx.BITMAP_TYPE_ANY)
        
        self.mychannel = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","mychannel.png"), wx.BITMAP_TYPE_ANY)
        self.spam = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","bug.png"), wx.BITMAP_TYPE_ANY)
        self.max_votes = 5
    
    def _favorite_icon(self, item):
        channel = item.original_data
        if channel.isMyChannel():
            return self.mychannel
        if channel.isFavorite():
            return self.favorite
        if channel.isSpam():
            return self.spam
        return self.normal
    
    def _status_icon(self, item):
        torrent = item.original_data
        if torrent.magnetstatus:
            return self.statusDHT, "This torrent being fetched from the DHT"
        elif "downloading" in torrent.state:
            return self.statusDownloading, "This torrent is downloading"
        elif "seeding" in torrent.state:
            return self.statusSeeding, "This torrent is seeding"
        elif "completed" in torrent.state:
            return self.statusFinished, "This torrent is finished downloading"
        elif "stopped" in torrent.state:
            return self.statusStopped, "This torrent is paused"
        else:
            return self.statusInactive, "This torrent is inactive"   
    
    @warnWxThread
    def CreateDownloadButton(self, parent, item):
        button = wx.Button(parent, -1, 'Download', style = wx.BU_EXACTFIT)
        button.item = item
        item.button = button
        
        if not item.original_data.get('ds',False):
            button.Bind(wx.EVT_BUTTON, self.OnDownload)
        else:
            button.Enable(False)
        return button

    @warnWxThread
    def CreateRatio(self, parent, item):
        seeders = int(item.original_data.num_seeders)
        leechers = int(item.original_data.num_leechers)
        item.data[-2] = seeders + leechers
        
        control = SwarmHealth(parent)
        width = item.columns[-2]['width'] if isinstance(item.columns[-2]['width'], int) else -1
        control.SetMinSize((width,7))
        control.SetBackgroundColour(DEFAULT_BACKGROUND)
        control.SetRatio(seeders, leechers)
        return control, 3

    @warnWxThread
    def OnDownload(self, event):
        item = event.GetEventObject().item
        key = self.infohash2key.get(item.original_data.infohash, item.original_data.infohash)
        self.Select(key)
        self.StartDownload(item.original_data)
        
        button = event.GetEventObject()
        button.Enable(False)
        
    @warnWxThread
    def SetData(self, data):
        from Tribler.Main.vwxGUI.list_bundle import BundleListItem # solving circular dependency for now
        
        resetbottomwindow = not bool(self.list.raw_data)
        
        SizeList.SetData(self, data)
        if len(data) > 0:
            list_data = []
            for item in data:
                if isinstance(item, tuple) and item and isinstance(item[0], Channel):
                    channel, position, isAssociated = item[:3]                    
                    self.max_votes = max(channel.nr_favorites, self.max_votes)
                    if isAssociated:
                        list_data.append((channel.id, [channel.name, channel.modified, channel.nr_torrents, channel.nr_favorites, item[3]], channel, ChannelListItemAssociatedTorrents, position))
                    else:
                        list_data.append((channel.id, [channel.name, channel.modified, channel.nr_torrents, channel.nr_favorites], channel, ChannelListItem, position))
                else:

                    # either we have a bundle of hits:
                    if 'bundle' in item:
                        head = item['bundle'][0]
                        create_method = BundleListItem
                        key = item['key']
                    
                        for hit in item['bundle']:
                            self.infohash2key[hit.infohash] = key
                    
                        # if the bundle is changed, inform the ListBody
                        if 'bundle_changed' in item:
                            self.RefreshData(key, item)
                    
                    # or a single hit:
                    else:
                        head = item
                        create_method = TorrentListItem
                        key = head.infohash
                    
                        if key in self.infohash2key:
                            del self.infohash2key[key]

                    if DEBUG_RELEVANCE:
                        item_data = ["%s %s"%(head.name,head.relevance_score), head.length, self.category_names[head.category_id], head.num_seeders, head.num_leechers, 0, 0]
                    else:
                        item_data = [head.name, head.length, self.category_names[head.category_id], head.num_seeders, head.num_leechers, 0, 0]
                    original_data = item
                    
                    list_data.append((key, item_data, original_data, create_method))
            
            self.list.SetData(list_data)
            
        else:
            header =  'No torrents matching your query are found.'
            message = 'Try leaving Tribler running for a longer time to allow it to discover new torrents, or use less specific search terms.'
            
            if self.guiutility.getFamilyFilter():
                message += '\n\nAdditionally, you could disable the "Family filter".'
                
                suggestionSizer = wx.BoxSizer(wx.VERTICAL)
                ffbutton = LinkStaticText(self.list.messagePanel, 'Turn off Family filter', None)
                ffbutton.Bind(wx.EVT_LEFT_UP, lambda evt: self.guiutility.toggleFamilyFilter(setCheck = True))
                suggestionSizer.Add(ffbutton)
                
                self.list.ShowMessage(message, header, suggestionSizer)
            else:
                self.list.ShowMessage(message, header)
            self.SetNrResults(0)
                
        if resetbottomwindow:
            self.ResetBottomWindow()
        
    @warnWxThread
    def RefreshData(self, key, data):
        List.RefreshData(self, key, data)
        
        if data:
            if isinstance(data, Channel):
                self.max_votes = max(data.nr_favorites, self.max_votes)
                self.list.RefreshData(key, (data.id, [data.name, data.modified, data.nr_torrents, data.nr_favorites], data, ChannelListItem))
                return
            
            original_data = data
            if 'bundle' in data: # bundle update
                head = data['bundle'][0]
            else: # individual hit update
                head = original_data
                
                # check whether the individual hit is in a bundle
                key = self.infohash2key.get(key, key)
                
            #we need to merge the dslist from the current item
            prevItem = self.list.GetItem(head.infohash)
            if prevItem.original_data.ds:
                original_data.dslist = prevItem.original_data.dslist
                
            # Update primary columns with new data
            if DEBUG_RELEVANCE:
                data = (head.infohash, ["%s %s"%(head.name, head.relevance_score), head.length, self.category_names[head.category_id], head.num_seeders, head.num_leechers, 0, 0], original_data)
            else:
                data = (head.infohash, [head.name, head.length, self.category_names[head.category_id], head.num_seeders, head.num_leechers, 0, 0], original_data)
            
            self.list.RefreshData(key, data)
            
    def Reset(self):
        self.infohash2key = {}
        return List.Reset(self)

    @warnWxThread
    def OnExpand(self, item):
        List.OnExpand(self, item)
        if isinstance(item.original_data, Torrent):
            td = TorrentDetails(self.guiutility.frame.splitter_bottom_window, item.original_data)
            item.expandedPanel = td
            self.guiutility.SetBottomSplitterWindow(td)
        elif isinstance(item.original_data, Channel):
            cd = ChannelDetails(self.guiutility.frame.splitter_bottom_window, item.original_data)
            item.expandedPanel = cd
            self.guiutility.SetBottomSplitterWindow(cd)
        return True

    @warnWxThread
    def OnCollapseInternal(self, item):
        self.ResetActionButtons()
        self.ResetBottomWindow()
            
    def ResetActionButtons(self):
        self.guiutility.frame.top_bg.ClearButtonHandlers()
                
    def ResetBottomWindow(self):
        panel = SearchInfoPanel(self.guiutility.frame.splitter_bottom_window)
        num_items = len(self.list.raw_data) if self.list.raw_data else 0
        panel.Set(num_items)
        self.guiutility.SetBottomSplitterWindow(panel)

    @forceWxThread
    def StartDownload(self, torrent, files = None):
        from Tribler.Main.vwxGUI.channel import SelectedChannelList
        from list_bundle import BundleListView
        
        # vliegendhart: Logging relevance ranking stats
        def relevance_ranking_msg():
            infohash = torrent.infohash
            
            main_searchlist = self.guiutility.frame.searchlist
            header = main_searchlist.header
            
            bundlestate = main_searchlist.header.bundlestate
            selected_bundle_mode = header.selected_bundle_mode
            bundlestate_str = header.bundlestates_str[bundlestate]
            selected_bundle_mode_str = header.bundlestates_str.get(selected_bundle_mode, None)
            
            pos_visual = None
            subpos_visual = None
            subpos_hits = None
            
            if isinstance(self, BundleListView):
                bundlelistitem = main_searchlist.GetItem(infohash)
                
                pos_visual = main_searchlist.GetItemPos(infohash)
                subpos_visual = self.GetItemPos(infohash)
                try:
                    subpos_hits = bundlelistitem.bundle[1:].index(torrent)
                except:
                    pass
            else:
                pos_visual = self.GetItemPos(infohash)
            
            hits = self.guiutility.torrentsearch_manager.hits
            try:
                hits_pos = hits.index(torrent)
                hits_old_pos = sorted(hits, key=lambda hit: hit.relevance_score[-1], reverse=True).index(torrent)
            except:
                hits_pos = None
                hits_old_pos = None
            
            keywords = self.guiutility.torrentsearch_manager.getSearchKeywords()[0]
            query = ' '.join(keywords)
            
            return \
            'RelevanceRanking: pos/subpos_v/subpos_h: %s/%s/%s; hits_pos: %s; hits_old_pos: %s; bundle: %s/%s [%s/%s]; family: %s; relevance: %s; q=%s' \
            % (pos_visual, subpos_visual, subpos_hits,
               hits_pos, hits_old_pos, 
               bundlestate, selected_bundle_mode, bundlestate_str, selected_bundle_mode_str,
               self.guiutility.getFamilyFilter(), torrent.relevance_score, query)
        
        relevance_msg = relevance_ranking_msg()
        def db_callback():
            if isinstance(self, SelectedChannelList):
                self.uelog.addEvent(message="Torrent: torrent download from channel", type = 2)
            elif isinstance(self, BundleListView):
                self.uelog.addEvent(message="Torrent: torrent download from bundle", type = 2)
            else:
                self.uelog.addEvent(message="Torrent: torrent download from other", type = 2)
            
            self.uelog.addEvent(message=relevance_msg, type = 4)

        startWorker(None, db_callback, retryOnBusy=True)
        response = self.guiutility.torrentsearch_manager.downloadTorrent(torrent, selectedFiles = files)
        if response:
            self.guiutility.Notify('Downloading .Torrent file (%s)'%response, icon = wx.ART_INFORMATION)
        
    def InList(self, key):
        key = self.infohash2key.get(key, key)
        return List.InList(self, key)
    
    def GetItem(self, key):
        key = self.infohash2key.get(key, key)
        return List.GetItem(self, key)
    
    def GetItemPos(self, key):
        key = self.infohash2key.get(key, key)
        return List.GetItemPos(self, key)
        
    def format(self, val):
        val = int(val)
        if val < 0:
            return "?"
        return str(val)
        
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
                new_filter = new_filter[:start - 10] + new_filter[end+1:]
            except:
                pass
    
        SizeList.OnFilter(self, new_filter)
    
    def MatchFilter(self, item):
        if isinstance(item[2], Torrent) and (self.categoryfilter and self.categoryfilter not in self.category_names[item[2].category_id].lower()):
            return False
        
        return SizeList.MatchFilter(self, item)
    
    def GetFilterMessage(self, empty = False):
        header, message = SizeList.GetFilterMessage(self, empty)
        
        if self.categoryfilter:
            message = message.rstrip('.')
            message += " matching category '%s'"%self.categoryfilter
        return header, message
        
class SearchList(GenericSearchList):
    def __init__(self, parent=None):
        self.guiutility = GUIUtility.getInstance()
        self.utility    = self.guiutility.utility
        self.session    = self.guiutility.utility.session
        self.category   = Category.getInstance()
        
        self.total_channels = None
        self.keywords = None
        self.categoryfilter = None
        self.keywords = None
        self.xxx_keywords = False
        
        columns = [{'name':'Name', 'sortAsc': True, 'fontSize': 2, 'showColumname': False, 'dlbutton': not self.guiutility.ReadGuiSetting('hide_buttons', True)}, \
                   {'name':'Size', 'width': '16em', 'fmt': self.guiutility.utility.size_format}, \
                   {'name':'File type', 'width': '24em', 'sortAsc': True}, \
                   {'name':'Seeders', 'width': '14em', 'fmt': lambda x: '?' if x < 0 else str(x)}, \
                   {'name':'Leechers', 'width': '15em', 'fmt': lambda x: '?' if x < 0 else str(x)}, \
                   {'name':'Health', 'type':'method', 'width': 100, 'method': self.CreateRatio}]
        
        columns = self.guiutility.SetColumnInfo(TorrentListItem, columns, hide_defaults = [3,4])
        ColumnsManager.getInstance().setColumns(TorrentListItem, columns)
        ColumnsManager.getInstance().setColumns(DragItem, columns)        
        
        torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)
        self.category_names = {}
        for key, name in self.category.getCategoryNames(filter = False):
            if torrent_db.category_table.has_key(key):
                self.category_names[torrent_db.category_table[key]] = name
        self.category_names[8] = 'Other'
        self.category_names[None] = self.category_names[0] = 'Unknown'

        self.inFavoriteChannel = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","starEnabled.png"), wx.BITMAP_TYPE_ANY)
        self.outFavoriteChannel = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","star.png"), wx.BITMAP_TYPE_ANY)
        self.hasSwift = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","swift.png"), wx.BITMAP_TYPE_ANY)
        self.noSwift = wx.EmptyBitmapRGBA(self.hasSwift.GetWidth(), self.hasSwift.GetHeight(), alpha=1)
        GenericSearchList.__init__(self, None, LIST_GREY, [0,0], True, parent=parent)
       
    def _PostInit(self):
        self.header = self.CreateHeader(self.parent)
        self.Add(self.header, 0, wx.EXPAND)
        
        self.leftLine = wx.Panel(self.parent, size=(1,-1))
        self.rightLine = wx.Panel(self.parent, size=(1,-1))
        
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(self.leftLine, 0, wx.EXPAND)
        
        list = wx.Panel(self.parent)
        list.SetForegroundColour(self.parent.GetForegroundColour())
        
        self.list = self.CreateList(list, listRateLimit=0.5)
        list.OnSort = self.list.OnSort
        
        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.Add(self.list, 1, wx.EXPAND)
        list.SetSizer(vSizer)

        hSizer.Add(list, 1, wx.EXPAND)
        hSizer.Add(self.rightLine, 0, wx.EXPAND)

        self.Add(hSizer, 1, wx.EXPAND)
        
        self.footer = self.CreateFooter(self.parent)
        self.Add(self.footer, 0, wx.EXPAND)
        
        self.SetBackgroundColour(self.background)
        self.Layout()
        
        self.list.Bind(wx.EVT_SIZE, self.OnSize)
    
    def _special_icon(self, item):
#        torrent = item.original_data
#        if torrent.swift_hash:
#            return self.hasSwift, "This torrent is Swift-enabled"
#        return self.noSwift
        
        torrent = item.original_data
        if torrent.hasChannel() and torrent.channel.isFavorite():
            return self.inFavoriteChannel, "This torrent is part of one of your favorite channels, %s"%torrent.channel.name
        else:
            return self.outFavoriteChannel, "This torrent is not part of one of your favorite channels"

    def GetManager(self):
        if getattr(self, 'manager', None) == None:
            self.manager = RemoteSearchManager(self) 
        return self.manager
    
    @warnWxThread
    def CreateHeader(self, parent):
        return TorrentFilter(parent, self)

    @warnWxThread
    def CreateFooter(self, parent):
        footer = ListFooter(parent, radius = 0)
        footer.SetMinSize((-1, 0))
        return footer

    def SetSelectedBundleMode(self, selected_bundle_mode):
        self.header.SetSelectedBundleMode(selected_bundle_mode)

    @warnWxThread
    def SetData(self, torrents):
        #Determine the associated channels
        associated = {}
        for torrent in torrents:
            if torrent.get('channel', False):
                channel = torrent.get('channel')
                if channel.id not in associated:
                    associated[channel.id] = [0, [], channel]
                if channel.nr_favorites > 0 or channel.isFavorite():
                    associated[channel.id][0] += 1
                associated[channel.id][1].append(torrent)
                    
        #Determine the channels results
        results = self.GetManager().data_channels
        results = results if results else {}
        results = dict( [(key, result) for key, result in results.iteritems() if result.nr_torrents > 0] )
        results_ids = results.keys()
        if results:
            for chid in associated.keys():
                if chid in results_ids:
                    associated.pop(chid)
                
        #Sorting + filtering..
        associated_torrents = dict([(ch, tr) for _, tr, ch in associated.values()])
        associated = associated.values()
        associated.sort(reverse = True)
        associated = [a[-1] for a in associated]
        results = results.values()
        results.sort(reverse = True, key = lambda x: x.nr_torrents)
        
        #We need to filter here, as otherwise our top-3 associated channels could only consist of
        #xxx channels, which will be filtered afterwards. Resulting in no channels being shown.
        def channelFilter(channel):
            isXXX = self.category.xxx_filter.isXXX(channel.name, False)
            return not isXXX
        
        if self.guiutility.getFamilyFilter():
            associated = filter(channelFilter, associated)        
            results = filter(channelFilter, results)
            
        associated = associated[:3]
        results = results[:3]
        channels = results+associated
        for index, channel in enumerate(channels):
            if channel in associated:
                channels[index] = (channel, (index+1)*5, True, associated_torrents[channel])
            else:
                channels[index] = (channel, (index+1)*5, False)
        
        self.SetNrChannels(len(channels))
        GenericSearchList.SetData(self, channels+torrents)
        
    def SetNrResults(self, nr):
        SizeList.SetNrResults(self, nr)
        
        actitem = self.guiutility.frame.actlist.GetItem(2)
        num_items = getattr(actitem, 'num_items', None)
        if num_items:
            num_items.SetValue(str(nr))
            actitem.hSizer.Layout()
        
    def SetNrChannels(self, nr_channels):
        self.total_channels = nr_channels
    
    def GetNrChannels(self):
        return self.total_channels
        
    def SetKeywords(self, keywords):
        self.GetManager().SetKeywords(keywords)
        self.keywords = keywords
        
        self.CalcXXXKeywords()
        
    def CalcXXXKeywords(self):
        if self.keywords and self.guiutility.getFamilyFilter():
            self.xxx_keywords = any(self.category.xxx_filter.isXXX(keyword, False) for keyword in self.keywords)
        else:
            self.xxx_keywords = False
    
    @warnWxThread
    def ShowSuggestions(self, suggestions):
        if len(suggestions) > 0:
            header, message = self.list.GetMessage()
            message += '\n\nAlternatively your could search for %s'%suggestions[0][0]
            self.list.ShowMessage(message, header = header)

    @forceWxThread        
    def SetMaxResults(self, max, keywords):
        self.Freeze()
        self.guiutility.frame.top_bg.go.SetRange(max+16)
        self.guiutility.frame.top_bg.go.SetValue(0)
        self.guiutility.frame.top_bg.ag.Play()
        self.guiutility.frame.top_bg.ag.Show()        
        self.Thaw()
        wx.CallLater(10000, self.SetFinished, keywords)
        wx.CallLater(250, self.FakeResult)
    
    @forceWxThread
    def FakeResult(self, times = 1):
        maxValue = self.guiutility.frame.top_bg.go.GetRange()
        newValue = min(self.guiutility.frame.top_bg.go.GetValue() + 1, maxValue)
        if times < 16:
            self.guiutility.frame.top_bg.go.SetValue(newValue)
            wx.CallLater(250, self.FakeResult, times+1)
    
    @forceWxThread
    def NewResult(self):
        maxValue = self.guiutility.frame.top_bg.go.GetRange()
        newValue = min(self.guiutility.frame.top_bg.go.GetValue() + 1, maxValue)
        if newValue == maxValue:
            self.SetFinished(None)
        else:
            self.guiutility.frame.top_bg.go.SetValue(newValue)

    def SetFinished(self, keywords):
        curkeywords, hits, filtered = self.guiutility.torrentsearch_manager.getSearchKeywords()
        if not keywords or curkeywords == keywords:
            self.Freeze()
            self.guiutility.frame.top_bg.ag.Stop()
            self.guiutility.frame.top_bg.ag.Hide()
            self.guiutility.frame.top_bg.go.SetValue(self.guiutility.frame.top_bg.go.GetRange())
            self.Layout()
            self.Thaw()

            def db_callback(keywords):
                self.uelog.addEvent(message="Search: nothing found for query: "+" ".join(keywords), type = 2)
                self.GetManager().showSearchSuggestions(keywords)
        
            if self.nr_results == 0 and self.nr_filtered == 0:
                startWorker(None, db_callback, wargs = (self.keywords,), retryOnBusy=True,priority=GUI_PRI_DISPERSY)
    
    @warnWxThread
    def _ShowSuggestions(self, delayedResult, keywords):
        if keywords == self.keywords and self.nr_results == 0 and self.nr_filtered == 0 and not self.xxx_keywords:
            suggestions = delayedResult.get()
            
            if len(suggestions) > 0:
                suggestionSizer = wx.BoxSizer(wx.VERTICAL)
                suggestionSizer.Add(StaticText(self.list.messagePanel, -1, "Alternatively, try one of the following suggestions:"))
                for suggestion, hits in suggestions:
                    label = LinkStaticText(self.list.messagePanel, suggestion)
                    label.Bind(wx.EVT_LEFT_UP, self.OnSearchSuggestion)
                    suggestionSizer.Add(label)
                    
                header, message = self.list.GetMessage()
                self.list.ShowMessage(message, header, suggestionSizer)
                
        
    def OnSearchSuggestion(self, event):
        label = event.GetEventObject()
        self.guiutility.dosearch(label.GetLabel())
    
    def Reset(self):
        if GenericSearchList.Reset(self):
            self.total_channels = None
            self.keywords = None
            self.xxx_keywords = False
            return True
        return False

    def OnSize(self, event):
        event.Skip()
    
    def GotFilter(self, keyword = None):
        self.CalcXXXKeywords()
        
        GenericSearchList.GotFilter(self, keyword)
    
    def GetFFilterMessage(self):
        if self.xxx_keywords and self.guiutility.getFamilyFilter():
            return 'At least one of the keywords that you used has been blocked by the family filter.', 'If you would still like to see the results, please disable the "Family filter" in the bottom left of your screen.' 
        return GenericSearchList.GetFFilterMessage(self)
    
    def MatchFFilter(self, item):
        if self.xxx_keywords:
            return False

        return GenericSearchList.MatchFFilter(self, item)

class LibraryList(SizeList):
    def __init__(self, parent):
        self.user_download_choice = UserDownloadChoice.get_singleton()
        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility
        
        self.channelsearch_manager = self.guiutility.channelsearch_manager
        
        self.statefilter = None
        self.newfilter = False
        self.prevStates = {}
        
        self.initnumitems = False

        columns = [{'name':'Name', 'width': wx.LIST_AUTOSIZE, 'sortAsc': True, 'fontSize': 2, 'showColumname': False}, \
                   {'name':'Progress', 'type':'method', 'width': '20em', 'method': self.CreateProgress, 'showColumname': False, 'autoRefresh': False}, \
                   {'name':'Size', 'width': '16em', 'fmt': self.guiutility.utility.size_format}, \
                   {'name':'ETA', 'width': '13em', 'fmt': self._format_eta, 'sortAsc': True, 'autoRefresh': False}, \
                   {'name':'Down speed', 'width': '20em', 'fmt': self.utility.speed_format_new, 'autoRefresh': False}, \
                   {'name':'Up speed', 'width': '20em', 'fmt': self.utility.speed_format_new, 'autoRefresh': False}, \
                   {'name':'Connections', 'width': '15em', 'autoRefresh': False},
                   {'name':'Ratio', 'width':'15em', 'fmt': self._format_ratio, 'autoRefresh': False},
                   {'name':'Time seeding', 'width': '25em', 'fmt': self.utility.eta_value, 'autoRefresh': False}]
        
        columns = self.guiutility.SetColumnInfo(LibraryListItem, columns, hide_defaults = [2, 7, 8])
        ColumnsManager.getInstance().setColumns(LibraryListItem, columns)
        
        self.hasSwift = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","swift.png"), wx.BITMAP_TYPE_ANY)
        self.noSwift = wx.EmptyBitmapRGBA(self.hasSwift.GetWidth(), self.hasSwift.GetHeight(), alpha=1)
        SizeList.__init__(self, None, LIST_GREY, [0,0], False, parent = parent)
        
    def OnDeleteKey(self, event):
        if self.list.GetExpandedItems():
            self.guiutility.frame.top_bg.OnDelete()
    
    def GetManager(self):
        if getattr(self, 'manager', None) == None:
            self.manager = LocalSearchManager(self) 
        return self.manager
    
    def _format_eta(self, value):
        eta = self.utility.eta_value(value, truncate=2)
        return eta or '-'

    def _format_ratio(self, value):
        return "%.2f"%value
    
    def _swift_icon(self, item):
        torrent = item.original_data
        if torrent.swift_hash:
            return self.hasSwift, "This torrent is Swift-enabled"
        return self.noSwift, ""

    @warnWxThread
    def CreateHeader(self, parent):
        if self.guiutility.frame.top_bg:
            header = DownloadFilter(parent, self)
        else:
            raise NotYetImplementedException('')
#            header = LibraryOnlyHeader(parent, self, self.columns)
#            def showSettings(event):
#                self.guiutility.ShowPage('settings')
#                
#            def showChannel(event):
#                self.guiutility.ShowPage('selectedchannel')
#                
#            header.SetEvents(self.OnAdd, showSettings, showChannel)
#            header.SetTitle('Downloads')
        
        return header
    
    @warnWxThread
    def CreateFooter(self, parent):
        footer = ListFooter(parent, radius = 0)
        footer.SetMinSize((-1, 0))
        return footer
    
    @warnWxThread
    def CreateProgress(self, parent, item):
        progressPanel = TorrentStatus(parent)
        progressPanel.SetMinSize((item.columns[1]['width'],-1))
        item.progressPanel = progressPanel
        return progressPanel

    def OnExpand(self, item):
        List.OnExpand(self, item)
        ld = LibraryDetails(self.guiutility.frame.splitter_bottom_window, item.original_data)
        item.expandedPanel = ld
        self.guiutility.SetBottomSplitterWindow(ld)
        
        return True
    
    def OnCollapseInternal(self, item):
        self.ResetActionButtons()
        self.ResetBottomWindow()
            
    def ResetActionButtons(self):
        self.guiutility.frame.top_bg.ClearButtonHandlers()
                
    def ResetBottomWindow(self):
        panel = LibraryInfoPanel(self.guiutility.frame.splitter_bottom_window)
        num_items = len(self.list.raw_data) if self.list.raw_data else 0
        panel.Set(num_items)
        self.guiutility.SetBottomSplitterWindow(panel)

    def __ds__eq__(self, ds1, ds2):
        #Exact same objects or both None
        if ds1 == ds2:
            return True
        
        #Check if one of the two is None
        if not ds1:
            return False
        if not ds2:
            return False
        
        #Compare status
        if ds1.get_status() != ds2.get_status():
            return False
        
        #Compare connections
        if ds1.get_num_con_initiated() != ds2.get_num_con_initiated():
            return False
        if ds1.get_num_con_candidates() != ds2.get_num_con_candidates():
            return False
        
        #Compare current speed
        if ds1.get_current_speed('down') != ds2.get_current_speed('down'):
            return False
        if ds1.get_current_speed('up') != ds2.get_current_speed('up'):
            return False
        
        seeds1, peers1 = ds1.get_num_seeds_peers()
        seeds2, peers2 = ds2.get_num_seeds_peers()
        if seeds1 != seeds2:
            return False
        if peers1 != peers2:
            return False
        
        ds1progress = long(ds1.get_progress() * 1000)/ 1000.0
        ds2progress = long(ds2.get_progress() * 1000)/ 1000.0 
        if ds1progress != ds2progress:
            return False
        
        #Compare size
        if ds1.get_length() != ds2.get_length():
            return False 
    
        return True
    
    @warnWxThread
    def RefreshItems(self, dslist, magnetlist):
        didStateChange, oldDS, newDS = SizeList.RefreshItems(self, dslist, magnetlist, rawdata = True)
        
        newFilter = self.newfilter
        show_seeding_colours = False
        if self.statefilter == 'active' and self.utility.config.Read('t4t_option', 'int') == 0:
            show_seeding_colours = True
            t4t_ratio = self.utility.config.Read('t4t_ratio', 'int')/100.0
            
            orange = LIST_ORANGE
            orange = rgb_to_hsv(orange.Red()/255.0, orange.Green()/255.0, orange.Blue()/255.0)
            
            green = LIST_GREEN
            green = rgb_to_hsv(green.Red()/255.0, green.Green()/255.0, green.Blue()/255.0)
            
            colourstep = (green[0] - orange[0], green[1] - orange[1], green[2] - orange[2])
        
        if len(newDS) > 0:
            ids = newDS.keys()
            self.GetManager().refresh_if_exists(ids, force = True) #new torrent?
        
        if didStateChange:
            if self.statefilter != None:
                self.list.SetData() #basically this means execute filter again
            
        for item in self.list.items.itervalues():
            ds = item.original_data.ds
            if newFilter or not self.__ds__eq__(ds, oldDS.get(id, None)):
                if hasattr(item, 'progressPanel'):
                    progress = item.progressPanel.Update(item.original_data)
                    item.data[1] = progress
                else:
                    item.data[1] = -1

                tooltip = ''
                ratio = 0
                time_seeding = 0
                if ds:
                    if ds.get_seeding_statistics():
                        stats = ds.get_seeding_statistics()
                        dl = stats['total_down']
                        ul = stats['total_up']
                        
                        #set dl at min progress*length
                        size_progress = ds.get_length()*ds.get_progress()
                        dl = max(dl, size_progress)                 
                        
                        if dl == 0L:
                            if ul != 0L:
                                ratio = sys.maxint
                            else:
                                ratio = 0
                        else:
                            ratio = 1.0*ul/dl
                            
                        tooltip = "Total transferred: %s down, %s up."%(self.utility.size_format(dl), self.utility.size_format(ul))
                        time_seeding = stats['time_seeding']
                        
                    else:
                        dl = ds.get_total_transferred(DOWNLOAD)
                        ul = ds.get_total_transferred(UPLOAD)
                        
                        #set dl at min progress*length
                        progress = item.original_data.progress or 0
                        size = item.original_data.length or 0
                        size_progress = size*progress
                        dl = max(dl, size_progress)
                        
                        if dl == 0L:
                            if ul != 0L:
                                ratio = sys.maxint
                            else:
                                ratio = 0
                        else:
                            ratio = 1.0*ul/dl
                        
                        tooltip = "Total transferred: %s down, %s up."%(self.utility.size_format(dl), self.utility.size_format(ul))
                        
                    if show_seeding_colours:
                        #t4t_ratio is goal
                        step = ratio / t4t_ratio
                        step = int(min(1, step) * 5)/5.0 #rounding to 5 different colours
                        
                        rgbTuple = (c*255.0 for c in hsv_to_rgb(orange[0]+step*colourstep[0], orange[1]+step*colourstep[1], orange[2]+step*colourstep[2]))
                        bgcolour = wx.Colour(*rgbTuple)
                        item.SetDeselectedColour(bgcolour)
                    else:
                        item.SetDeselectedColour(LIST_DESELECTED)
                    
                item.RefreshColumn(3, ds.get_eta() if ds else '-')
                
                item.RefreshColumn(4, ds.get_current_speed('down') * 1024 if ds else 0)
                item.SetToolTipColumn(4, tooltip)
                    
                item.RefreshColumn(5, ds.get_current_speed('up')*1024 if ds else 0)
                item.SetToolTipColumn(5, tooltip)
                
                seeds, peers = ds.get_num_seeds_peers() if ds else (0,0)
                item.RefreshColumn(6, seeds+peers)
                item.SetToolTipColumn(6, "Connected to %d Seeders and %d Leechers."%(seeds, peers) if ds else '')
                
                item.RefreshColumn(7, ratio)
                item.RefreshColumn(8, time_seeding)

        if newFilter:
            self.newfilter = False
    
    @warnWxThread
    def SetData(self, data):
        SizeList.SetData(self, data)
        
        if len(data) > 0:
            data = [(file.infohash, [file.name, None, file.length, None, None, None, 0, 0, 0, -1], file, LibraryListItem) for file in data]
        else:
            header = "Currently not downloading or uploading any torrents."
            message = "Torrents can be found using our integrated search or using channels.\n"
            message += "Additionally you could add any torrent file downloaded from an external source by using the '+ Add' button or dropping it here."
            self.list.ShowMessage(message, header = header)
            self.SetNrResults(0)

        self.list.SetData(data)
        
    @warnWxThread   
    def RefreshData(self, key, data):
        List.RefreshData(self, key, data)
        
        data = (data.infohash, [data.name, None, data.length, None, None, None, 0, 0, 0, -1], data)
        self.list.RefreshData(key, data)
    
    def SetNrResults(self, nr):
        highlight = nr > self.nr_results and self.initnumitems
        SizeList.SetNrResults(self, nr)
        
        actitem = self.guiutility.frame.actlist.GetItem(4)
        num_items = getattr(actitem, 'num_items', None)
        if num_items:
            num_items.SetValue(str(nr))
            actitem.hSizer.Layout()
            if highlight: actitem.Highlight()
            self.initnumitems = True

    @warnWxThread
    def OnFilter(self, keyword):
        self.statefilter = None
        if keyword:
            new_filter = keyword.lower().strip()
            
            if new_filter.find("state=") > -1:
                try:
                    start = new_filter.find("state=") + 6
                    end = new_filter.find(" ", start)
                    if end == -1:
                        end = len(new_filter)
                    
                    state = new_filter[start:end]
                    if state in ['completed','active','stopped','checking','seeding','downloading']: 
                        self.statefilter = state
                        self.newfilter = True
                        
                        new_filter = new_filter[:start - 6] + new_filter[end:]
                except:
                    pass
            
            SizeList.OnFilter(self, new_filter)
        else:
            SizeList.OnFilter(self, keyword)
    
    def MatchFilter(self, item):
        if self.statefilter:
            if self.statefilter not in item[2].state:
                return False
        
        return SizeList.MatchFilter(self, item)
    
    def MatchFFilter(self, item):
        return True
    
    def GetFilterMessage(self, empty = False):
        header, message = SizeList.GetFilterMessage(self, empty)
        
        if self.statefilter:
            message += " with state %s"%self.statefilter
            if self.statefilter == 'active'and self.utility.config.Read('t4t_option', 'int') == 0:
                t4t_ratio = self.utility.config.Read('t4t_ratio', 'int')/100.0
                message += ".\nColours represent the upload/download ratio. Starting at orange, the colour will change into green when approaching a upload/download ratio of %.1f"%t4t_ratio
        return header, message

class ChannelList(List):
    def __init__(self, parent):
        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility
        
        columns = [{'name':'Name', 'sortAsc': True, 'fontSize': 2, 'showColumname': False}, \
                   {'name':'Latest Update', 'width': '27em', 'fmt': format_time}, \
                   {'name':'Torrents', 'width': '13em'}, \
                   {'type':'method', 'width': '20em', 'method': self.CreatePopularity, 'name':'Popularity', 'defaultSorted': True}]
        
        columns = self.guiutility.SetColumnInfo(ChannelListItem, columns)
        ColumnsManager.getInstance().setColumns(ChannelListItem, columns)

        columns = [copy.copy(column) for column in columns]
        columns.append({'name':'Associated torrents', 'width': '25em', 'fmt': lambda x: str(len(x))})
        columns = self.guiutility.SetColumnInfo(ChannelListItemAssociatedTorrents, columns)
        ColumnsManager.getInstance().setColumns(ChannelListItemAssociatedTorrents, columns)
        
        self.favorite = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","starEnabled.png"), wx.BITMAP_TYPE_ANY)
        self.normal = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","star.png"), wx.BITMAP_TYPE_ANY)
        self.mychannel = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","mychannel.png"), wx.BITMAP_TYPE_ANY)
        self.spam = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","bug.png"), wx.BITMAP_TYPE_ANY)
        self.ministar = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","ministarEnabled.png"), wx.BITMAP_TYPE_ANY)
        self.normalministar = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","ministar.png"), wx.BITMAP_TYPE_ANY)
        
        self.select_popular = True
        self.max_votes = 5
        List.__init__(self, None, LIST_GREY, [0,0], True, parent = parent)

    def _special_icon(self, item):
        return (self._favorite_icon(item),'')
            
    def _favorite_icon(self, item):
        channel = item.original_data
        if channel.isMyChannel():
            return self.mychannel
        if channel.isFavorite():
            return self.favorite
        if channel.isSpam():
            return self.spam
        return self.normal
    
    def __format(self, val):
        val = int(val)
        if val <= 0:
            return "New"
        return str(val)
    
    @warnWxThread
    def CreateHeader(self, parent):
        return ChannelFilter(parent, self)
    
    @warnWxThread
    def CreateFooter(self, parent):
        footer = ListFooter(parent, radius = 0)
        footer.SetMinSize((-1, 0))
        return footer
    
    def SetCategory(self, category):
        if category == "Favorites":
            self.header.AddButton("Add Favorite channel", self.OnAdd)
        else:
            self.header.AddButton('', None)
    
    @warnWxThread
    def CreatePopularity(self, parent, item):
        pop = item.original_data.nr_favorites
        if pop <= 0:
            ratio = wx.StaticText(parent, -1, "New", )
            return ratio
        
        max = log(self.max_votes)
        cur = log(pop+1)
        ratio = min(1, cur/max)
        ratio = int(item.columns[3]['width'] * ratio) / float(item.columns[3]['width'])
        prev_ratio = getattr(item, 'prev_ratio', None)
        
        if ratio != prev_ratio: #if not enough difference don't return the control
            item.prev_ratio = ratio
            
            control = HorizontalGauge(parent, self.normalministar, self.ministar, 5)
            control.SetBackgroundColour(DEFAULT_BACKGROUND)
            #control.SetMinSize((50,10))
            control.SetPercentage(ratio)
            control.SetToolTipString('%s users marked this channel as one of their favorites.'%pop)
            return control

    @warnWxThread
    def MarkAsFavorite(self, event, channel):
        if channel:
            if event:
                button = event.GetEventObject()
                button.Enable(False)
                wx.CallLater(5000, button.Enable, True)

            self.guiutility.channelsearch_manager.favorite(channel.id)
            self.uelog.addEvent(message="ChannelList: user marked a channel as favorite", type = 2)
            wx.CallAfter(self.GetManager().refresh_partial, (channel.id,))
            
    @warnWxThread
    def RemoveFavorite(self, event, channel):
        if channel:
            if event:
                button = event.GetEventObject()
                button.Enable(False)
                wx.CallLater(5000, button.Enable, True)
                
            self.guiutility.channelsearch_manager.remove_vote(channel.id)
            wx.CallAfter(self.GetManager().refresh_partial, (channel.id,))
    
    def OnExpand(self, item):
        List.OnExpand(self, item)
        cd = ChannelDetails(self.guiutility.frame.splitter_bottom_window, item.original_data)
        item.expandedPanel = cd
        self.guiutility.SetBottomSplitterWindow(cd)
        return True
    
    def OnCollapseInternal(self, item):
        self.ResetActionButtons()
        self.ResetBottomWindow()
            
    def ResetActionButtons(self):
        self.guiutility.frame.top_bg.ClearButtonHandlers()
                
    def ResetBottomWindow(self):
        panel = ChannelInfoPanel(self.guiutility.frame.splitter_bottom_window)
        num_items = len(self.list.raw_data) if self.list.raw_data else 1
        panel.Set(num_items, self.GetManager().category == "Favorites")
        self.guiutility.SetBottomSplitterWindow(panel)   

    def OnAdd(self, event):
        dlg = wx.TextEntryDialog(None, 'Please specify the channel-identifier.\nThis should be a 40 character string which can be found in the overview tab of the channel management interface.\n\nJoining a channel can take up to 1 minute and should appear in the all channellist.', 'Enter channel-identifier')
        if dlg.ShowModal() == wx.ID_OK:
            cid = dlg.GetValue()
            cid = cid.decode("hex")
            
            self.GetManager().joinChannel(cid)
            
        dlg.Destroy()
    
    def GetManager(self):
        if getattr(self, 'manager', None) == None:
            self.manager = ChannelSearchManager(self) 
        return self.manager

    def SetData(self, data):
        List.SetData(self, data)
        
        if len(data) > 0:
            max_votes = max([channel.nr_favorites for channel in data])
            if max_votes > self.max_votes:
                self.max_votes = max_votes
            
            data = [(channel.id,[channel.name, channel.modified, channel.nr_torrents, channel.nr_favorites], channel, ChannelListItem) for channel in data]
            self.list.SetData(data)
        else:
            self.list.ShowMessage('No channels are discovered for this category.')
            self.SetNrResults(0)
        
    def RefreshData(self, key, data):
        List.RefreshData(self, key, data)
        
        data = (data.id,[data.name, data.modified, data.nr_torrents, data.nr_favorites], data)
        self.list.RefreshData(key, data)
    
    def SetNrResults(self, nr):
        List.SetNrResults(self, nr)
        
        actitem = self.guiutility.frame.actlist.GetItem(3)
        chcat = actitem.expandedPanel.channel_category if actitem.expandedPanel else None
        if chcat and chcat != 'All':
            return
        num_items = getattr(actitem, 'num_items', None)
        if num_items:
            num_items.SetValue(str(nr))
            actitem.hSizer.Layout()

    def SetMyChannelId(self, channel_id):
        self.GetManager().refresh_partial((channel_id,))

class ActivitiesList(List):
    def __init__(self, parent):
        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility
        self.settings = {}
        self.expandedPanel = None
        columns = [{'width': wx.LIST_AUTOSIZE}]
        List.__init__(self, columns, parent.GetBackgroundColour(), [10,10], True, parent = parent)

    def _PostInit(self):
        self.list = self.CreateList(self.parent)
        listSizer = wx.BoxSizer(wx.HORIZONTAL)
        listSizer.Add(self.list, 1, wx.EXPAND)
        self.Add(listSizer, 0, wx.EXPAND)
        
        self.notifyPanel = FancyPanel(self.parent, radius = 5, border = wx.ALL)
        self.notifyPanel.SetBorderColour(SEPARATOR_GREY)
        self.notifyPanel.SetBackgroundColour(GRADIENT_LGREY, GRADIENT_DGREY)
        self.notifyPanel.SetForegroundColour(wx.Colour(80,80,80))
        self.notifyBmp = wx.ArtProvider.GetBitmap(wx.ART_INFORMATION, wx.ART_FRAME_ICON)
        self.notifyIcon = wx.StaticBitmap(self.notifyPanel, -1, self.notifyBmp)
        self.notify = TransparentText(self.notifyPanel)
        _set_font(self.notify, fontweight = wx.FONTWEIGHT_NORMAL, size_increment = 0)
        
        notifySizer = wx.BoxSizer(wx.HORIZONTAL)
        notifySizer.Add(self.notifyIcon, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
        notifySizer.Add(self.notify, 1, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
        self.notifyPanel.SetSizer(notifySizer)
        self.notifyPanel.Hide()
        
        self.AddStretchSpacer()
        self.Add(self.notifyPanel, 0, wx.EXPAND|wx.ALIGN_BOTTOM|wx.LEFT|wx.RIGHT|wx.BOTTOM|wx.RESERVE_SPACE_EVEN_IF_HIDDEN, 5)
        
        self.SetBackgroundColour(self.background)
        self.Layout()
        self.list.Bind(wx.EVT_SIZE, self.OnSize)
        _set_font(self.list, size_increment = 2)
        wx.CallAfter(self.__SetData)
        
    def __SetData(self):
        self.list.SetData([(1,['Home'],None,ActivityListItem), (2,['Results'],None,ActivityListItem), (3,['Channels'],None,ActivityListItem), \
                           (4,['Downloads'],None,ActivityListItem), (5,['Videoplayer'],None,ActivityListItem)])
        self.ResizeListItems()
        self.DisableItem(2)
        if not self.guiutility.frame.videoparentpanel:
            self.DisableItem(5)
        self.DisableCollapse()
        self.selectTab('home')
        
    def do_or_schedule_refresh(self, force_refresh = False):
        pass
    
    def GotFilter(self, filter):
        pass

    def CreateList(self, parent):
        flb = FixedListBody(parent, self, self.columns, self.spacers[0], self.spacers[1], self.singleSelect)
        flb.listpanel.SetBackgroundColour(self.background)
        flb.SetStyle(list_expanded = None)
        return flb  

    def DisableItem(self, index):
        if self.settings.get(index, None):
            return
        item = self.list.items[index]
        num_items = getattr(item, 'num_items', None)
        if num_items:
            num_items.Show(False)
            item.hSizer.Layout()
        for child in item.GetChildren():
            if not isinstance(child, TagText):
                _set_font(child, fontweight = wx.FONTWEIGHT_NORMAL, fontcolour = wx.Colour(160,160,160))
        self.settings[index] = (item.list_deselected, item.list_selected, item.OnClick)
        item.list_deselected = wx.WHITE
        item.list_selected = wx.WHITE
        item.ShowSelected()
        item.OnClick = lambda evt: None

    def EnableItem(self, index):
        if not self.settings.get(index, None):
            return
        item = self.list.items[index]
        num_items = getattr(item, 'num_items', None)
        if num_items:
            num_items.Show(True)
            item.hSizer.Layout()
        item.list_deselected, item.list_selected, item.OnClick = self.settings[index]
        item.ShowSelected()
        self.settings.pop(index)
        
    def DisableCollapse(self):
        # Ensure that items from the menu cannot be deselected by double-clicking.
        for item in self.list.items.values():
            item.DoCollapse = lambda raise_events = True: None

    def ResizeListItems(self):
        for item in self.list.items.values():
            item.vSizer.Detach(item.hSizer)
            item.vSizer.Add(item.hSizer, 0, wx.EXPAND|wx.TOP|wx.BOTTOM, 5)

    def OnExpand(self, item):
        for child in item.GetChildren():
            if not isinstance(child, TagText):
                _set_font(child, fontweight = wx.FONTWEIGHT_NORMAL, fontcolour = TRIBLER_RED)
        wx.CallAfter(self.Layout)
        if item.data[0] == 'Home':
            self.guiutility.ShowPage('home')
        elif item.data[0] == 'Results':
            self.guiutility.ShowPage('search_results')
        elif item.data[0] == 'Channels':
            if self.guiutility.guiPage not in ['channels', 'selectedchannel', 'mychannel']:
                self.guiutility.ShowPage('channels')
            if not self.expandedPanel:
                self.expandedPanel = ChannelsExpandedPanel(item)
                item.AddEvents(self.expandedPanel)
            return self.expandedPanel
        elif item.data[0] == 'Downloads':
            self.guiutility.ShowPage('my_files')
        elif item.data[0] == 'Videoplayer':
            self.guiutility.ShowPlayer()
        return True

    def OnCollapse(self, item, panel):
        if panel == self.expandedPanel:
            panel = None
        
        List.OnCollapse(self, item, panel)

    def OnCollapseInternal(self, item):
        for child in item.GetChildren():
            if not isinstance(child, TagText):
                _set_font(child, fontweight = wx.FONTWEIGHT_NORMAL, fontcolour = item.GetForegroundColour())
        List.OnCollapseInternal(self, item)
        self.list.OnChange()
        self.list.Refresh()
        
    @forceWxThread
    def Notify(self, msg, icon = None):
        if icon:
            self.notifyIcon.Show()
            self.notifyIcon.SetBitmap(self.notifyBmp)
        else:
            self.notifyIcon.Hide()
        
        self.notifyPanel.Layout()
        cdc = wx.ClientDC(self.notify)
        cdc.SetFont(self.notify.GetFont())
        wrapped_msg = wordwrap(msg, self.notify.GetSize()[0], cdc, breakLongWords = True, margin = 0)
        self.notify.SetLabel(wrapped_msg)
        self.notify.SetSize(self.notify.GetBestSize())        
        
        self.Freeze()
        self.notifyPanel.Show()
        #NotifyLabel size changed, thus call Layout
        self.Layout()
        self.Thaw()
        
        wx.CallLater(5000, self.HideNotify)
        
    def HideNotify(self):
        if self.notifyPanel.GetScreenRect().Contains(wx.GetMousePosition()):
            wx.CallLater(1000, self.HideNotify)
        else:
            wx.CallLater(500, self.notifyPanel.Hide)

    def selectTab(self, tab):
        itemKey = 0
        if tab == 'home':
            itemKey = 1
        elif tab == 'search_results':
            itemKey = 2
            self.EnableItem(2)
        elif tab in ['channels', 'selectedchannel', 'mychannel']:
            itemKey = 3
        elif tab == 'my_files':
            itemKey = 4
        elif tab == 'videoplayer':
            itemKey = 5
        if itemKey:
            wx.CallAfter(self.Select, itemKey, True)
        return

    def NextPage(self):
        self._DoPage(1)

    def PrevPage(self):
        self._DoPage(-1)
        
    def _DoPage(self, increment):
        pages = [self.list.items[k].expanded for k in range(1, len(self.list.items)+1)]
        for i in self.settings.keys():
            pages.pop(i-1)

        curPage = pages.index(True)
        curPage = (curPage + increment) % len(pages)
        if curPage < 0:
            curPage = len(pages) - 1
            
        pageNames = ['home', 'search_results', 'channels', 'my_files', 'videoplayer']
        for i in self.settings.keys():
            pageNames.pop(i-1)
        self.guiutility.ShowPage(pageNames[curPage])
