# Written by Niels Zeilemaker
import os
import sys
from threading import currentThread
from traceback import print_stack
from math import log

import wx
from wx import html
from time import time
from datetime import date, datetime

from Tribler.Main.vwxGUI.tribler_topButton import ProgressStaticText
from Tribler.Core.API import *
from Tribler.Core.CacheDB.sqlitecachedb import bin2str
from Tribler.Core.Utilities.utilities import get_collected_torrent_filename
from Tribler.Main.Dialogs.AddTorrent import AddTorrent
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility, forceWxThread
from Tribler.Main.vwxGUI.UserDownloadChoice import UserDownloadChoice

from Tribler.__init__ import LIBRARYNAME

from __init__ import *
from list_body import *
from list_details import *
from list_footer import *
from list_header import *
from list_sidebar import *

from Tribler.Main.Utility.GuiDBHandler import startWorker
from collections import namedtuple

DEBUG = False

class RemoteSearchManager:
    def __init__(self, list):
        self.list = list
        self.oldkeywords = ''
        self.data_channels = []
        
        self.dirtyset = set()
        
        self.guiutility = GUIUtility.getInstance()
        self.guiserver = self.guiutility.frame.guiserver
        self.torrentsearch_manager = self.guiutility.torrentsearch_manager
        self.channelsearch_manager = self.guiutility.channelsearch_manager
   
    def Reset(self):
        self.dirtyset.clear()
        
    def SetKeywords(self, keywords):
        if self.oldkeywords != keywords:
            self.list.Reset()
            self.oldkeywords = keywords
   
    def refreshDirty(self):
        self.refresh_partial(self.dirtyset)
        self.dirtyset.clear()   
   
    @forceWxThread
    def refresh(self):
        def db_callback():
            keywords = self.oldkeywords
            
            total_items, nrfiltered, new_items, selected_bundle_mode, data_files = self.torrentsearch_manager.getHitsInCategory()
            total_channels, new_channels, self.data_channels = self.channelsearch_manager.getChannelHits()
            return keywords, data_files, total_items, nrfiltered, new_items, total_channels, new_channels, selected_bundle_mode
        
        startWorker(self._on_refresh, db_callback, uId = "RemoteSearchManager_refresh_%s"%self.oldkeywords)

    def _on_refresh(self, delayedResult):
        keywords, data_files, total_items, nrfiltered, new_items, total_channels, new_channels, selected_bundle_mode = delayedResult.get()
        
        if keywords == self.oldkeywords:
            if new_items or new_channels:
                self.list.SetNrResults(total_items, total_channels)
                
            self.list.SetFF(self.guiutility.getFamilyFilter(), nrfiltered)
            self.list.SetSelectedBundleMode(selected_bundle_mode)
            
            if new_items:
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
        
        startWorker(self._on_refresh_channel, db_callback, uId = "RemoteSearchManager_refresh_channel")
    
    def _on_refresh_channel(self, delayedResult):
        self.list.SetNrChannels(delayedResult.get())
        
    def refresh_partial(self, ids):
        for infohash in ids:
            startWorker(self.list.RefreshDelayedData, self.torrentsearch_manager.getTorrentByInfohash, cargs=(infohash,), wargs=(infohash,))
    
    def downloadStarted(self, infohash):
        if self.list.InList(infohash):
            item = self.list.GetItem(infohash)
            
            torrent_details = item.GetExpandedPanel()
            if torrent_details:
                torrent_details.DownloadStarted()
            
    def torrentUpdated(self, infohash):
        if self.list.InList(infohash):
            if self.list.IsShownOnScreen():
                self.refresh_partial((infohash, ))
            else:
                self.dirtyset.add(infohash)
                self.list.dirty = True

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
            return self.library_manager.getHitsInCategory()
        startWorker(self._on_data, db_callback, uId = "LocalSearchManager_refresh")

    @forceWxThread
    def _on_data(self, delayedReslt):
        total_items, nrfiltered, data = delayedReslt.get()
        
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
    
    def Reset(self):
        self.dirtyset.clear()
    
    def do_or_schedule_refresh(self, force_refresh = False):
        if self.list.isReady and (self.list.ShouldGuiUpdate() or force_refresh):
            self.refresh()
        else:
            self.dirtyset.add('COMPLETE_REFRESH')
            self.list.dirty = True
            
    def refreshDirty(self):
        if 'COMPLETE_REFRESH' in self.dirtyset or len(self.dirtyset) > 5:
            self.refresh()
        else:
            self.refresh_partial(self.dirtyset)
            self.list.dirty = False
        self.dirtyset.clear()
    
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
            self.list.SetTitle(title)
            
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
                return data, category
            
            startWorker(self._on_data_delayed, db_callback, uId = "ChannelSearchManager_refresh")

        else:
            if search_results:
                total_items = len(search_results)
                keywords = ' '.join(self.channelsearch_manager.searchkeywords)
                self.list.SetTitle('Search results for "%s"'%keywords)
                self._on_data(search_results, self.category)
    
    def _on_data_delayed(self, delayedResult):
        data, category = delayedResult.get()
        self._on_data(data, category)
    
    def _on_data(self, data, category):
        if category == self.category:
            data = [channel for channel in data if not channel.isEmpty()]
            self.list.SetData(data)
            if DEBUG:
                print >> sys.stderr, "ChannelManager complete refresh done"
            
    def refresh_partial(self, ids):
        for id in ids:
            startWorker(self.list.RefreshDelayedData, self.channelsearch_manager.getChannel, wargs=(id,),cargs=(id,))
      
    def SetCategory(self, category, force_refresh = False):
        if category != self.category:
            self.category = category
            self.list.Reset()
            self.list.ShowLoading()
            
            if category != 'searchresults':
                self.do_or_schedule_refresh(force_refresh)
        else:
            self.list.DeselectAll()
           
    def channelUpdated(self, id, votecast = False):
        if self.list.isReady:
            #only update when shown
            if self.list.IsShownOnScreen():
                if self.list.InList(id):
                    self.refresh_partial((id,))
                    
                elif self.category in ['All', 'New']:
                    #Show new channel, but only if we are not showing search results
                    self.refresh()
                    
            elif self.list.InList(id):
                self.dirtyset.add(id)
                self.list.dirty = True
                
            elif not votecast:
                if self.category == 'All':
                    update = True
                elif self.category == 'Popular':
                    update = len(self.list.GetItems()) < 20
                else:
                    update = False
                
                if update: 
                    self.do_or_schedule_refresh()

class XRCPanel(wx.Panel):
    def __init__(self, parent = None):
        self.parent = parent
        self.isReady = False
        
        if parent:
            wx.Panel.__init__(self, parent)
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
        self.rawfilter = ''
        self.filter = ''

        self.id = 0

        self.guiutility = GUIUtility.getInstance()
        self.uelog = UserEventLogDBHandler.getInstance()
        self.leftLine = self.rightLine = None
        XRCPanel.__init__(self, parent)
    
    def _PostInit(self):
        vSizer = wx.BoxSizer(wx.VERTICAL)
        
        self.header = self.CreateHeader(self)
        if self.header:
            vSizer.Add(self.header, 0, wx.EXPAND)
        
        self.list = self.CreateList(self)

        #left and right borders
        if self.borders:
            listSizer = wx.BoxSizer(wx.HORIZONTAL)
            self.leftLine = wx.Panel(self, size=(1,-1))
            self.rightLine = wx.Panel(self, size=(1,-1))
        
            listSizer.Add(self.leftLine, 0, wx.EXPAND)
            listSizer.Add(self.list, 1, wx.EXPAND)
            listSizer.Add(self.rightLine, 0, wx.EXPAND)
            vSizer.Add(listSizer, 1, wx.EXPAND)
        else:
            vSizer.Add(self.list, 1, wx.EXPAND)
        
        self.footer = self.CreateFooter(self)
        if self.footer:
            vSizer.Add(self.footer, 0, wx.EXPAND)
        
        self.SetBackgroundColour(self.background)
        self.SetSizer(vSizer)
        self.Layout()
        
        self.list.Bind(wx.EVT_SIZE, self.OnSize)
    
    def CreateHeader(self, parent):
        return ListHeader(parent, self, self.columns)

    def CreateList(self, parent = None):
        if not parent:
            parent = self
        return ListBody(parent, self, self.columns, self.spacers[0], self.spacers[1], self.singleSelect, self.showChange)

    def CreateFooter(self, parent):
        return ListFooter(parent)
    
    def OnSize(self, event):
        assert self.isReady, "List not ready"

        if self.header and self.footer:
            diff = self.header.GetClientSize()[0] - self.list.GetClientSize()[0]
            self.header.SetSpacerRight(diff)
            if self.footer:
                self.footer.SetSpacerRight(diff)

        event.Skip()
        
    def OnSort(self, column, reverse):
        assert self.isReady, "List not ready"
        if self.isReady:
            self.list.OnSort(column, reverse)
    
    def Reset(self):
        assert self.isReady, "List not ready"
        self.__check_thread()

        if self.isReady:
            self.rawfilter = ''
            self.filter = ''
            
            manager = self.GetManager()
            if manager and getattr(manager, 'Reset', False):
                manager.Reset()
            
            if self.header:
                self.header.Reset()
            self.list.Reset()

            if self.footer:
                self.footer.Reset()

            self.dirty = False
            self.Layout()
            
    def OnExpand(self, item):
        assert self.isReady, "List not ready"
        self.__check_thread()
    
    def OnCollapse(self, item, panel):
        assert self.isReady, "List not ready"
        self.__check_thread()
        
        self.OnCollapseInternal(item)
        if panel:
            panel.Destroy()
            
    def OnCollapseInternal(self, item):
        pass
    
    def GetManager(self):
        pass
    
    def SetDelayedData(self, delayedResult):
        assert self.isReady, "List not ready"
        self.__check_thread()
        self.SetData(delayedResult.get())
    
    def SetData(self, data):
        assert self.isReady, "List not ready"
        self.__check_thread()
        
    def RefreshDelayedData(self, delayedResult, key):
        assert self.isReady, "List not ready"
        self.__check_thread()
        self.RefreshData(key, delayedResult.get())
    
    def RefreshData(self, key, data):
        assert self.isReady, "List not ready"
        self.__check_thread()
        
    def SetNrResults(self, nr):
        assert self.isReady, "List not ready"
        self.__check_thread()
        
    def InList(self, key):
        assert self.isReady, "List not ready"
        if self.isReady:
            return self.list.InList(key)
    
    def GetItem(self, key):
        assert self.isReady, "List not ready"
        if self.isReady:
            return self.list.GetItem(key)
        
    def GetItems(self):
        assert self.isReady, "List not ready"
        if self.isReady:
            return self.list.items
        
    def GetExpandedItem(self):
        assert self.isReady, "List not ready"
        if self.isReady:
            return self.list.GetExpandedItem()
    
    def Focus(self):
        assert self.isReady, "List not ready"
        if self.isReady:
            self.list.SetFocus()
        
    def HasFocus(self):
        assert self.isReady, "List not ready"
        focussed = wx.Window.FindFocus()
        return focussed == self.list
        
    def SetBackgroundColour(self, colour):
        self.__check_thread()
        
        wx.Panel.SetBackgroundColour(self, colour)
        
        if self.header:
            self.header.SetBackgroundColour(colour)
        
        if self.leftLine:
            self.leftLine.SetBackgroundColour(colour)
            
        self.list.SetBackgroundColour(colour)
        
        if self.rightLine:
            self.rightLine.SetBackgroundColour(colour)
        
        if self.footer:
            self.footer.SetBackgroundColour(colour)
        
    def ScrollToEnd(self, scroll_to_end):
        assert self.isReady, "List not ready"
        if self.isReady:
            self.list.ScrollToEnd(scroll_to_end)
    
    def ScrollToId(self, id):
        assert self.isReady, "List not ready"
        self.list.ScrollToId(id)
    
    def DeselectAll(self):
        assert self.isReady, "List not ready"
        if self.isReady:
            self.list.DeselectAll()
        
    def Select(self, key, raise_event = True):
        assert getattr(self, 'list', False), "List not ready"
        if self.isReady:
            self.list.Select(key, raise_event)
    
    def SetFilteredResults(self, nr):
        pass

    def ShouldGuiUpdate(self):
        if not self.IsShownOnScreen():
            return False
        return self.guiutility.ShouldGuiUpdate()

    def ShowLoading(self):
        if self.isReady:
            self.list.ShowLoading()
            
    def OnLoadAll(self):
        if self.isReady:
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
            
    def ShowFooter(self, show = True):
        self.footer.Show(show)
        
    def __check_thread(self):
        if __debug__ and currentThread().getName() != "MainThread":
            print  >> sys.stderr,"List: __check_thread thread",currentThread().getName(),"is NOT MainThread"
            print_stack()
    
    def GotFilter(self, keyword):
        oldrawfilter = self.rawfilter
        self.rawfilter = keyword.lower().strip()
        
        if self.rawfilter == '':
            wx.CallAfter(self.list.SetFilter, None, None, False)
            
        else:
            self.OnFilter(self.rawfilter)
            
            highlight = True
            if oldrawfilter[:-1] == self.rawfilter: #did the user simple remove 1 character?
                highlight = False
            
            wx.CallAfter(self.list.SetFilter, self.MatchFilter, self.GetFilterMessage, highlight)
        
    def OnFilter(self, keyword):
        self.filter = keyword
        try:
            re.compile(self.filter)
            self.header.FilterCorrect(True)
            
        except: #regex incorrect
            self.filter = ''
            self.header.FilterCorrect(False)
    
    def MatchFilter(self, item):
        if self.filter == '':
            return True
        return re.search(self.filter, item[1][0].lower())
    
    def GetFilterMessage(self, empty = False):
        if empty:
            message = '0 items'
        else:
            message = 'Only showing items'
        
        if self.filter:
            return message + ' matching "%s"'%self.filter
        return message
        
    def Layout(self):
        self.__check_thread()
        return wx.Panel.Layout(self)
    
class SizeList(List):
    
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
            except:
                pass
        
        List.OnFilter(self, new_filter)
    
    def MatchFilter(self, item):
        if self.sizefilter:
            size = int(item[2].length/1048576.0)
            if size < self.sizefilter[0] or size > self.sizefilter[1]:
                return False
        
        return List.MatchFilter(self, item)
    
    def GetFilterMessage(self, empty = False):
        message = List.GetFilterMessage(self, empty)
        
        if self.sizefilter:
            if self.sizefilter[0] == self.sizefilter[1]:
                message += " equal to %d MB in size."%self.sizefilter[0]
            elif self.sizefilter[0] == 0:
                message += " smaller than %d MB in size."%self.sizefilter[1]
            elif self.sizefilter[1] == sys.maxint:
                message += " larger than %d MB in size"%self.sizefilter[0]
            else:
                message += " between %d and %d MB in size."%(self.sizefilter[0], self.sizefilter[1])
        return message

class GenericSearchList(SizeList):
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
        seeders = int(item.original_data.num_seeders)
        leechers = int(item.original_data.num_leechers)
        item.data[-2] = seeders + leechers
        
        control = SwarmHealth(parent)
        control.SetMinSize((self.columns[-2]['width'],7))
        control.SetBackgroundColour(wx.WHITE)
        control.SetRatio(seeders, leechers)
        return control
        
    def OnDownload(self, event):
        item = event.GetEventObject().item
        self.Select(item.original_data.infohash)
        self.StartDownload(item.original_data)
        
        button = event.GetEventObject()
        button.Enable(False)
    
    def toggleFamilyFilter(self):
        self.guiutility.toggleFamilyFilter()

        def db_callback():
            self.uelog.addEvent(message="SearchList: user toggled family filter", type = 2)
        self.guiutility.frame.guiserver.add_task(db_callback)
        
    def SetFF(self, family_filter, nr_filtered):
        self.header.SetFF(family_filter, nr_filtered)
        
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
                        self.infohash2key[hit.infohash] = key
                    
                    # if the bundle is changed, inform the ListBody
                    if 'bundle_changed' in file:
                        self.RefreshData(key, file)
                    
                # or a single hit:
                else:
                    head = file
                    create_method = ListItem
                    key = head.infohash
                    
                    if key in self.infohash2key:
                        del self.infohash2key[key]
                
                item_data = [head.name, head.length, 0, 0]
                original_data = file
                    
                list_data.append((key, item_data, original_data, create_method))
            
            self.list.SetData(list_data)
            
        else:
            header =  'No torrents matching your query are found.'
            message = 'Try leaving Tribler running for a longer time to allow it to discover new torrents, or use less specific search terms.'
            if self.guiutility.getFamilyFilter():
                message += '\n\nAdditionally, you could disable the "Family Filter" by clicking on it.'
            self.list.ShowMessage(message, header = header)

    def RefreshData(self, key, data):
        List.RefreshData(self, key, data)
        
        if data:
            original_data = data
            if 'bundle' in data: # bundle update
                head = data['bundle'][0]
            
            else: # individual hit update
                head = original_data
                
                # check whether the individual hit is in a bundle
                key = self.infohash2key.get(key, key)
        
            # Update primary columns with new data
            data = (head.infohash, [head.name, head.length, 0, 0], original_data)
            self.list.RefreshData(key, data)
            
    def SetFilteredResults(self, nr):
        self.header.SetFiltered(nr)

    def OnExpand(self, item):
        item.button.Hide()
        item.button.Refresh()
        return TorrentDetails(item, item.original_data)
    
    def OnCollapseInternal(self, item):
        item.button.Show()
    
    def StartDownload(self, torrent, files = None):
        from Tribler.Main.vwxGUI.channel import SelectedChannelList
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
        
        self.total_results = None
        self.total_channels = None
        self.keywords = None
        
        columns = [{'name':'Name', 'width': wx.LIST_AUTOSIZE, 'sortAsc': True, 'icon': 'tree', 'fontWeight': wx.FONTWEIGHT_BOLD}, \
                   {'name':'Size', 'width': '9em', 'style': wx.ALIGN_RIGHT, 'fmt': format_size}, \
                   {'type':'method', 'width': wx.LIST_AUTOSIZE_USEHEADER, 'method': self.CreateRatio, 'name':'Popularity'}, \
                   {'type':'method', 'width': LIST_AUTOSIZEHEADER, 'method': self.CreateDownloadButton}]
        
        GenericSearchList.__init__(self, columns, LIST_GREY, [7,7], True, parent=parent)
        
    def _PostInit(self):
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.header = self.CreateHeader(self)
        sizer.Add(self.header, 0, wx.EXPAND)
        
        list = wx.Panel(self)
        self.subheader = ListHeader(list, self, self.columns, radius = 0, spacers=[7,7])
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
        
        self.footer = self.CreateFooter(self)
        sizer.Add(self.footer, 0, wx.EXPAND)
        
        self.header.SetSpacerRight = self.subheader.SetSpacerRight
        self.header.ResizeColumn = self.subheader.ResizeColumn
        self.header.SetFF = self.sidebar.SetFF
        
        self.SetBackgroundColour(self.background)
        self.SetSizer(sizer)
        self.Layout()
        
        self.list.Bind(wx.EVT_SIZE, self.OnSize)
    
    def GetManager(self):
        if getattr(self, 'manager', None) == None:
            self.manager = RemoteSearchManager(self) 
        return self.manager
    
    def CreateHeader(self, parent):
        return SearchHelpHeader(self, parent, [])

    def CreateFooter(self, parent):
        footer = ChannelResultFooter(parent)
        footer.SetEvents(self.OnChannelResults)
        return footer

    def SetSelectedBundleMode(self, selected_bundle_mode):
        self.sidebar.SetSelectedBundleMode(selected_bundle_mode)
    
    def SetData(self, data):
        GenericSearchList.SetData(self, data)
        
        #indentify popular associated channels
        channel_hits = {}
        for hit in data:
            if hit.get('channel'):
                channel = hit.get('channel')
                if channel.nr_favorites > 0:
                    if channel.id not in channel_hits:
                        channel_hits[channel.id] = [0, channel]
                    channel_hits[channel.id][0] += 1
        
        def channel_occur(a, b):
            return cmp(a[0], b[0])
        
        channels = channel_hits.values()
        channels.sort(channel_occur, reverse = True)
        self.sidebar.SetAssociatedChannels(channels)
        
    def SetNrResults(self, nr, nr_channels):
        self.total_results = nr
        self.total_channels = nr_channels
        self._SetTitles()
        
    def SetNrChannels(self, nr_channels):
        self.total_channels = nr_channels
        self._SetTitles()
        
    def SetKeywords(self, keywords):
        self.GetManager().SetKeywords(keywords)
        
        self.keywords = keywords
        self._SetTitles()
        
    def _SetTitles(self):
        title = ''
        if self.total_results != None:
            if self.total_results == 0:
                title = 'No results'
            elif self.total_results == 1:
                title = 'Got 1 result'
            else:
                title = 'Got %d results'%self.total_results
        else:
            title = 'Searching'

        if self.keywords != None:
            title += ' for "%s"'%self.keywords
        self.header.SetTitle(title)
        
        if self.total_channels != None:
            if not self.total_channels:
                title = 'No matching channels'
            elif self.total_channels == 1:
                title = 'Additionally, got 1 channel'
            else:
                title = 'Additionally, got %d channels'%self.total_channels
        else:
            title = 'Searching'
        if self.keywords != None:
            title += ' for "%s"'%self.keywords
        self.footer.SetLabel(title, self.total_channels)
            
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
        
        self.total_results = None
        self.total_channels = None
        self.keywords = None
    
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

class LibraryList(SizeList):
    def __init__(self, parent):
        self.user_download_choice = UserDownloadChoice.get_singleton()
        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility
        self.library_manager = self.guiutility.library_manager

        columns = [{'name':'Name', 'width': wx.LIST_AUTOSIZE, 'sortAsc': True, 'icon': 'tree'}, \
                   {'type':'method', 'name':'Completion', 'width': 250, 'method': self.CreateProgress}, \
                   {'type':'method', 'name':'Connections', 'width': wx.LIST_AUTOSIZE_USEHEADER, 'method': self.CreateConnections, 'footer_style': wx.ALIGN_RIGHT}, \
                   {'type':'method', 'name':'Down', 'width': 70, 'method': self.CreateDown, 'fmt': self.utility.speed_format_new, 'footer_style': wx.ALIGN_RIGHT}, \
                   {'type':'method', 'name':'Up', 'width': 70, 'method': self.CreateUp, 'fmt': self.utility.speed_format_new, 'footer_style': wx.ALIGN_RIGHT}]
     
        List.__init__(self, columns, LIST_GREY, [7,7], True, parent = parent)
    
    def GetManager(self):
        if getattr(self, 'manager', None) == None:
            self.manager = LocalSearchManager(self) 
        return self.manager
    
    def CreateHeader(self, parent):
        header = LibraryHeader(parent, self, self.columns)
        header.SetTitle('Library')
        header.SetEvents(self.OnAdd)
        return header
    
    def CreateFooter(self, parent):
        footer = TotalFooter(parent, self.columns)
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
        return LibraryDetails(item, item.original_data, self.OnStop, self.OnResume, self.OnDelete)

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
        ds = item.original_data.ds
        if ds:
            ds.get_download().restart()
        else:
            #TODO: start inactive item?
            pass
        self.user_download_choice.set_download_state(item.original_data.infohash, "restart")
    
    def OnStop(self, event):
        item = self.list.GetExpandedItem()
        ds = item.original_data.ds
        if ds:
            ds.get_download().stop()
            
        self.user_download_choice.set_download_state(item.original_data.infohash, "stop")

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
            self.list.RemoveItem(item)
            
        elif buttonId == wx.ID_DELETE:
            self.library_manager.deleteTorrent(item.original_data, True)
            self.list.RemoveItem(item)
        
        if self.list.IsEmpty():
            self.SetData([])
        
        dlg.Destroy()
            
    def RefreshItems(self, dslist):
        if self.isReady and self.ShouldGuiUpdate():
            totals = {2:0, 3:0, 4:0}
            
            nr_seeding = 0
            nr_downloading = 0
            for item in self.list.items.values():
                item.original_data.ds = None #remote all downloadstates
            
            for ds in dslist:
                infohash = ds.get_download().get_def().get_infohash()
                if infohash in self.list.items:
                    item = self.list.items[infohash]
                    item.original_data.ds = ds
                else:
                    self.GetManager().refresh() #new torrent
                    break
            
            for infohash, item in self.list.items.iteritems():
                ds = item.original_data.ds
                status = item.progressPanel.Update(ds)
                
                if status == 1:
                    nr_downloading += 1
                elif status == 2:
                    nr_seeding += 1
                
                totals[2] = totals[2] + item.data[2][0] + item.data[2][1]
                totals[3] = totals[3] + item.data[3]
                totals[4] = totals[4] + item.data[4]
                
                nr_connections = str(item.data[2][0] + item.data[2][1])
                item.connections.SetLabel(nr_connections)
                
                down = self.utility.speed_format_new(item.data[3])
                item.down.SetLabel(down)
                
                up = self.utility.speed_format_new(item.data[4])
                item.up.SetLabel(up)
                
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
            data = [(file.infohash, [file.name, [0,0], None, None, None], file) for file in data]
            self.list.SetData(data)
        else:
            header = "Currently not downloading any torrents."
            message = "Torrents can be found using our integrated search or using channels.\n"
            message += "Additionally you could add any torrent file downloaded from an external source by using the '+ Add' button or dropping it here."
            self.list.ShowMessage(message, header = header)

    def Show(self, show = True):
        List.Show(self, show)
        if show:
            self.library_manager.add_download_state_callback(self.RefreshItems)
        else:
            self.library_manager.remove_download_state_callback(self.RefreshItems)
       
    def Hide(self):
        self.Show(False)
        
    def OnFilter(self, keyword):
        new_filter = keyword.lower().strip()
        
        self.statefilter = None
        if new_filter.find("state=") > -1:
            try:
                start = new_filter.find("state=") + 6
                end = new_filter.find(" ", start)
                if end == -1:
                    end = len(new_filter)
                
                state = new_filter[start:end]
                if state in ['completed','active','stopped']: 
                    self.statefilter = state
                
                new_filter = new_filter[:start - 6] + new_filter[end:]
            except:
                pass
        
        SizeList.OnFilter(self, new_filter)
    
    def MatchFilter(self, item):
        if self.statefilter:
            if self.statefilter != item[2].state:
                return False
        
        return SizeList.MatchFilter(self, item)
    
    def GetFilterMessage(self, empty = False):
        message = SizeList.GetFilterMessage(self, empty)
        
        if self.statefilter:
            message += " with state %s"%self.statefilter
        return message

class ChannelList(List):
    def __init__(self, parent):
        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility
        
        columns = [{'name':'Name', 'width': wx.LIST_AUTOSIZE, 'icon': self.__favorite_icon, 'sortAsc': True}, \
                   {'name':'Latest Update', 'width': wx.LIST_AUTOSIZE_USEHEADER, 'fmt': format_time}, \
                   {'type':'method', 'width': 75, 'method': self.CreatePopularity, 'name':'Popularity', 'defaultSorted': True}, \
                   {'type':'method', 'width': wx.LIST_AUTOSIZE_USEHEADER, 'method': self.CreateTorrents, 'name':'Torrents'}]
        
        self.favorite = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","starEnabled.png"), wx.BITMAP_TYPE_ANY)
        self.normal = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","star.png"), wx.BITMAP_TYPE_ANY)
        self.mychannel = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","mychannel.png"), wx.BITMAP_TYPE_ANY)
        self.spam = wx.Bitmap(os.path.join(self.utility.getPath(),LIBRARYNAME,"Main","vwxGUI","images","bug.png"), wx.BITMAP_TYPE_ANY)
        
        self.total_results = None
        self.title = None
        
        self.select_popular = True
        self.max_votes = 5
        List.__init__(self, columns, LIST_BLUE, [7,7], showChange = True, parent = parent)
    
    def __favorite_icon(self, item):
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
    
    def CreateHeader(self, parent):
        return SubTitleSeachHeader(parent, self, self.columns)
    
    def CreatePopularity(self, parent, item):
        pop = int(item.data[2])
        if pop <= 0:
            ratio = wx.StaticText(parent, -1, "New", )
            ratio.SetMinSize((self.columns[2]['width'],-1))
            return ratio
        
        max = log(self.max_votes)
        cur = log(pop+1)
        ratio = min(1, cur/max)
        
        control = ChannelPopularity(parent, self.normal, self.favorite)
        control.SetMinSize((self.columns[2]['width'],15))
        control.SetBackgroundColour(wx.WHITE)
        control.SetVotes(ratio)
        control.SetToolTipString('%s users marked this channel as one of their favorites.'%pop)
        return control
    
    def CreateTorrents(self, parent, item):
        torrents = str(item.data[3])
        torrents = wx.StaticText(parent, -1, torrents)
        torrents.SetMinSize((self.columns[3]['width'], -1))
        return torrents
    
    def OnExpand(self, item):
        self.guiutility.showChannel(item.original_data)
        return False
    
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
            
            data = [(channel.id,[channel.name, channel.modified, channel.nr_favorites, channel.nr_torrents], channel) for channel in data]
            self.list.SetData(data)
        else:
            self.list.ShowMessage('No channels are discovered for this category.')
        self.SetNrResults(len(data))
        
    def RefreshData(self, key, data):
        List.RefreshData(self, key, data)
        
        data = (data.id,[data.name, data.modified, data.nr_favorites, data.nr_torrents], data)
        self.list.RefreshData(key, data)
    
    def SetNrResults(self, nr):
        self.total_results = nr
        self._SetTitles()

    def SetTitle(self, title):
        self.title = title
        self._SetTitles()
    
    def _SetTitles(self):
        self.header.SetTitle(self.title)
        
        if self.total_results:
            if self.title == 'Popular Channels':
                self.header.SetSubTitle("Showing the %d most popular channels" % self.total_results)
                
            elif self.title == 'Your Favorites':
                self.header.SetSubTitle("You marked %d channels as a favorite" % self.total_results)
                
            elif self.title == 'Updated Channels':
                self.header.SetSubTitle("Showing the %d latest updated channels" % self.total_results)
                
            elif self.title == 'New Channels':
                self.header.SetSubTitle("Discovered %d new channels (not marked yet and updated within the last 2 months)"% self.total_results)
                
            else:
                if self.total_results == 1:
                    self.header.SetSubTitle("Discovered %d channel" % self.total_results)
                else:
                    self.header.SetSubTitle("Discovered %d channels" % self.total_results)
        else:
            if self.title == 'New Channels':
                self.header.SetSubTitle('No new channels discovered (not marked as a favorite by anyone and updated within the last 2 months)')
            else:
                self.header.SetSubTitle('')
        
        if self.title == 'Updated Channels':
            self.header.ShowSortedBy(1)
            
        elif self.title == 'New Channels':
            self.header.ShowSortedBy(1)
            
        elif self.title.startswith('Search results'):
            self.header.ShowSortedBy(3)

        else:
            self.header.ShowSortedBy(2)

        self.header.Refresh()

    def SetMyChannelId(self, channel_id):
        self.GetManager().refresh_partial((channel_id,))

    def Reset(self):
        List.Reset(self)
        
        self.total_results = None
        self.title = None

class ChannelCategoriesList(List):
    def __init__(self, parent):
        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility
        self.searchSelected = False
        columns = [{'width': wx.LIST_AUTOSIZE}]
    
        List.__init__(self, columns, LIST_GREY, [7,7], True, parent = parent)
    
    def CreateHeader(self, parent):
        title = TitleHeader(parent, self, self.columns, 1, wx.FONTWEIGHT_NORMAL)
        title.SetTitle('Categories')
        return title
    
    def CreateList(self, parent):
        return FixedListBody(parent, self, self.columns, self.spacers[0], self.spacers[1], self.singleSelect)    
    
    def _PostInit(self):
        List._PostInit(self)
        self.list.SetData([(1,['Popular'],None), (2,['New'],None), (6, ['Updated'], None), (3,['Favorites'],None), (4,['All'],None), (5,['My Channel'],None)])
        self.SetMinSize((-1, self.GetBestSize()[1]))
        
    def OnExpand(self, item):
        if item.data[0] in ['Popular','New','Favorites','All','Updated']:
            self.guiutility.showChannelCategory(item.data[0])
            self.searchSelected = False
            
        elif item.data[0] == 'My Channel':
            self.guiutility.ShowPage('mychannel')
        
        #Show highlight
        return True
    
    def GetSelectedCategory(self):
        category = self.list.GetExpandedItem()
        if category:
            self.searchSelected = False
            return category.data[0]
        
        if self.searchSelected:
            return 'Search'
        
        return ''

    def SetQuicktip(self, quicktip):
        self.quicktip = quicktip
        self.Quicktip('All Channels are ordered by popularity. Popularity is measured by the number of Tribler users which have marked this channel as a favrotie.')
        
    def Quicktip(self, html):
        html = '<font size=\'2\'><b>Quick Tip:</b> ' + html + '</font>' 
        self.quicktip.SetPage(html)