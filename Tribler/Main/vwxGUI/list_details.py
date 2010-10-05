import wx
from wx.lib.mixins.listctrl import CheckListCtrlMixin, ColumnSorterMixin, ListCtrlAutoWidthMixin

import sys
import os
import time
import re
from datetime import date, datetime

from Tribler.Core.API import *
from Tribler.TrackerChecking.TorrentChecking import *
from Tribler.Video.Progress import ProgressBar
from Tribler.Main.vwxGUI.SearchGridManager import TorrentManager
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue
from Tribler.Subscriptions.rss_client import TorrentFeedThread
from Tribler.Main.globals import DefaultDownloadStartupConfig
from Tribler.Main.vwxGUI.TopSearchPanel import TopSearchPanel
from Tribler.Core.CacheDB.sqlitecachedb import bin2str
from Tribler.Core.BuddyCast.buddycast import BuddyCastFactory
from Tribler.Core.Subtitles.SubtitlesSupport import SubtitlesSupport

from list_header import ListHeader
from list_body import ListBody

class SortedListCtrl(wx.ListCtrl, ColumnSorterMixin, ListCtrlAutoWidthMixin):
    def __init__(self, parent, numColumns):
        wx.ListCtrl.__init__(self, parent, -1, style=wx.LC_REPORT|wx.LC_NO_HEADER)
        
        ColumnSorterMixin.__init__(self, numColumns)
        ListCtrlAutoWidthMixin.__init__(self)

        self.itemDataMap = {}

    
    def GetListCtrl(self):
        return self

class TorrentDetails(wx.Panel):
    def __init__(self, parent, torrent):
        wx.Panel.__init__(self, parent)
        self.guiutility = GUIUtility.getInstance()
        self.parent = parent
        self.torrent = torrent
        
        self.SetBackgroundColour(wx.WHITE)
        vSizer = wx.BoxSizer(wx.VERTICAL)
        
        #Add messagePanel text
        self.messagePanel = wx.StaticText(self, -1, "Loading details, please wait.")
        vSizer.Add(self.messagePanel, 0, wx.ALIGN_CENTRE_HORIZONTAL|wx.ALL, 3)
        
        #Add details view
        self.details = wx.BoxSizer(wx.HORIZONTAL)
        vSizer.Add(self.details, 0, wx.EXPAND, 0)
        self.SetSizer(vSizer)
        self.Layout()
        
        self.isReady = False
        self.noChannel = False
        
        self.guiserver = GUITaskQueue.getInstance()
        self.guiserver.add_task(self.loadTorrent)
        
    def loadTorrent(self):
        requesttype = self.guiutility.torrentsearch_manager.isTorrentPlayable(self.torrent, callback = self.showTorrent)
        if requesttype:
            self.messagePanel.SetLabel("Loading details, please wait.\nThe torrentfile is requested %s."%requesttype)

            self.Layout()
            self.parent.parent_list.OnChange()
    
    def showTorrent(self, torrent, information):
        self.torrent = torrent
        self.information = information
        
        self.Freeze()
        self.messagePanel.Show(False)
        
        def create_tab(tabname, header = None):
            panel = wx.lib.scrolledpanel.ScrolledPanel(self.notebook)
            panel.SetBackgroundColour(self.notebook.GetThemeBackgroundColour())
            self.notebook.AddPage(panel, tabname)
            
            vSizer = wx.BoxSizer(wx.VERTICAL)
            panel.SetSizer(vSizer)
            
            if header:
                header = wx.StaticText(panel, -1, header)
                font = header.GetFont()
                font.SetWeight(wx.FONTWEIGHT_BOLD)
                header.SetFont(font)
                vSizer.Add(header, 0, wx.BOTTOM, 3)
            
            return panel, vSizer
        
        def add_row(parent, sizer, name, value):
            if name:
                name = wx.StaticText(parent, -1, name)
                font = name.GetFont()
                font.SetWeight(wx.FONTWEIGHT_BOLD)
                name.SetFont(font)
                sizer.Add(name, 0, wx.LEFT, 10)
            
            try:
                value = wx.StaticText(parent, -1, unicode(value))
            except:
                value = wx.StaticText(parent, -1, value.decode('utf-8','ignore'))
                
            value.SetMinSize((1,-1))
            sizer.Add(value, 0, wx.EXPAND|wx.LEFT, 10)
            
            return name, value
    
        self.notebook = wx.Notebook(self, style = wx.NB_NOPAGETHEME)
        
        #Create torrent overview
        overview, vSizer = create_tab('Overview', 'Torrent Details')
        category = torrent['category']
        if isinstance(category,list):
            category = ', '.join(category)
        
        torrentSizer = wx.FlexGridSizer(0, 2, 3, 3)
        torrentSizer.AddGrowableCol(1)
        add_row(overview, torrentSizer, "Name", torrent['name'])
        add_row(overview, torrentSizer, "Type", category.capitalize())
        add_row(overview, torrentSizer, "Uploaded", date.fromtimestamp(torrent['creation_date']).strftime('%d-%m-%y'))
        add_row(overview, torrentSizer, "Filesize", self.guiutility.utility.size_format(torrent['length']) + " in " + str(len(information[2])) + " files")
        
        _, seeders, leechers, last_check, _, _ = self.guiutility.torrentsearch_manager.getSwarmInfo(torrent['torrent_id'])[0]
        diff = time() - last_check
        if seeders <= 0 and leechers <= 0:
            _, self.status = add_row(overview, torrentSizer, "Status", "Unknown")
        else:
            _, self.status = add_row(overview, torrentSizer, "Status", "%s seeders, %s leechers (updated %s ago)"%(seeders,leechers,self.guiutility.utility.eta_value(diff, 2)))
        vSizer.Add(torrentSizer, 0, wx.EXPAND)
        overview.SetupScrolling(rate_y = 5)
        
        if diff > 1800: #force update if last update more than 30 minutes ago
            #Refresh seeders/leechers
            TorrentChecking(self.torrent['infohash']).start()
        
        #Create filelist
        if len(information[2]) > 0:
            self.listCtrl = SortedListCtrl(self.notebook, 2)
            self.listCtrl.InsertColumn(0, 'Name')
            self.listCtrl.InsertColumn(1, 'Size', wx.LIST_FORMAT_RIGHT)
            self.listCtrl.Bind(wx.EVT_LEFT_DCLICK, self.OnPlaySelected)
            
            self.il = wx.ImageList(16,16)
            play_img = self.il.Add(wx.Bitmap(os.path.join(self.guiutility.vwxGUI_path, 'images', 'library_play.png'), wx.BITMAP_TYPE_ANY))
            file_img = self.il.Add(wx.ArtProvider.GetBitmap(wx.ART_NORMAL_FILE, size = (16,16)))
            self.listCtrl.SetImageList(self.il, wx.IMAGE_LIST_SMALL)
            
            #Add files
            keywords = ' | '.join(self.guiutility.current_search_query)
            def sort_by_keywords(a, b):
                a_match = re.search(keywords, a[0].lower())
                b_match = re.search(keywords, b[0].lower())
                if a_match and not b_match:
                    return -1
                if b_match and not a_match:
                    return 1
                return cmp(a[0],b[0])
            
            information[2].sort(sort_by_keywords)
            for filename, size in information[2]:
                try:
                    pos = self.listCtrl.InsertStringItem(sys.maxint, filename)
                except:
                    try:
                        pos = self.listCtrl.InsertStringItem(sys.maxint, filename.decode('utf-8','ignore'))
                    except:
                        print >> sys.stderr, "Could not format filename", torrent['name']
                self.listCtrl.SetItemData(pos, pos)
                self.listCtrl.itemDataMap.setdefault(pos, [filename, size])
                
                size = self.guiutility.utility.size_format(size)
                self.listCtrl.SetStringItem(pos, 1, size)
                
                if filename in information[1]:
                    self.listCtrl.SetItemColumnImage(pos, 0, play_img)
                else:
                    self.listCtrl.SetItemColumnImage(pos, 0, file_img)
            
            self.listCtrl.setResizeColumn(1) #resize column starts at 1 instead of 0
            self.listCtrl.SetMinSize((1,-1))
            self.listCtrl.SetColumnWidth(1, wx.LIST_AUTOSIZE) #autosize only works after adding rows
            self.notebook.AddPage(self.listCtrl, "Files")
        
        #Create description
        if torrent.get('comment', 'None') != 'None' and torrent['comment'] != '':
            descriptionPanel, vSizer = create_tab("Description", "Comment")
            add_row(descriptionPanel, vSizer, None, torrent['comment'])
            descriptionPanel.SetupScrolling(rate_y = 5)
        
        #Create subtitlelist
        subsupport = SubtitlesSupport.getInstance()
        if subsupport._registered:
            subs = subsupport.getSubtileInfosForInfohash(self.torrent['infohash'])
            if len(subs) > 0:
                supportedLang = subsupport.langUtility.getLangSupported()
    
                curlang = set()
                for channelid, dict in subs.iteritems():
                    for lang in dict.keys():
                        curlang.add(lang)
                curlang = [supportedLang[langkey] for langkey in curlang]
                curlang.sort()
                
                subtitlePanel, vSizer = create_tab("Subtitles", "Discovered Subtitles")
                for lang in curlang:
                    add_row(subtitlePanel, vSizer, None, lang)
        
        #Create trackerlist
        if torrent.get('trackers', 'None') != 'None':
            tracker_list = []
            for trackers in torrent['trackers']:
                for tracker in trackers:
                    if tracker:
                        tracker_list.append(tracker)
                
            if len(tracker_list) > 0:
                trackerPanel, vSizer = create_tab("Trackers", "Trackers")
                for tracker in tracker_list:
                    add_row(trackerPanel, vSizer, None, tracker)
                trackerPanel.SetupScrolling(rate_y = 5)
        
        #Set height depending on number of files present
        self.notebook.SetMinSize((-1, 130))
        self.details.Add(self.notebook, 6, wx.EXPAND)
        
        self.buttonPanel = wx.Panel(self)
        self.buttonPanel.SetBackgroundColour(wx.WHITE)
        self.buttonSizer = wx.BoxSizer(wx.VERTICAL)
        
        if self.torrent.get('ds', False):
            self.ShowDownloadProgress()
        else:
            self.ShowTorrentDetails()
        
        self.buttonPanel.SetSizer(self.buttonSizer)
        self.details.Add(self.buttonPanel, 4, wx.EXPAND|wx.LEFT|wx.RIGHT, 3)
        self.details.Layout()
        
        self.parent.parent_list.OnChange()
        self.Thaw()
        
        self.isReady = True
        
    def ShowChannelAd(self, show):
        if self.isReady:
            self.channeltext.Show(show)
        else:
            self.noChannel = True

    def ShowTorrentDetails(self):
        self.parent.button.Enable(True)
        
        self.buttonSizer.ShowItems(False)
        self.buttonSizer.DeleteWindows()
        self.buttonSizer.Clear()
        
        header = wx.StaticText(self.buttonPanel, -1, "Liking what you see?\nClick download or play to enjoy this torrent.")
        header.SetMinSize((1,-1))
        font = header.GetFont()
        font.SetPointSize(font.GetPointSize()+1)
        header.SetFont(font)
        self.buttonSizer.Add(header, 0, wx.ALL|wx.EXPAND, 3)
        
        self.buttonSizer.AddStretchSpacer()
        
        download_play_sizer = wx.BoxSizer(wx.HORIZONTAL)
        download = wx.Button(self.buttonPanel, -1, "Download")
        download.SetToolTipString('Start downloading this torrent.')
        download.Bind(wx.EVT_BUTTON, self.OnDownload)
        
        play = wx.Button(self.buttonPanel, -1, "Play")
        play.SetToolTipString('Start playing this torrent.')
        play.Bind(wx.EVT_BUTTON, self.OnPlay)
        
        if not self.information[0]:
            play.Disable()
        
        download_play_sizer.Add(download)
        download_play_sizer.Add(wx.StaticText(self.buttonPanel, -1, "or"), 0, wx.ALIGN_CENTRE_VERTICAL|wx.LEFT|wx.RIGHT, 3)
        download_play_sizer.Add(play)
        self.buttonSizer.Add(download_play_sizer, 0, wx.ALIGN_CENTER_HORIZONTAL)
        
        self.buttonSizer.AddStretchSpacer()
        
        if not self.noChannel:
            #prefer local channel result
            channel = self.guiutility.channelsearch_manager.getChannelForTorrent(self.torrent['infohash'])
            if channel is None:
                if 'channel_permid' in self.torrent and self.torrent['channel_permid'] != '':
                    channel = (self.torrent['channel_permid'], self.torrent['channel_name'], self.torrent['subscriptions'], {})
            
            if channel is not None:
                if channel[0] == bin2str(self.guiutility.utility.session.get_permid()):
                    label = "This torrent is part of your Channel."
                    tooltip = "Click to got to your Channel."
                else:
                    label = "This torrent is included in %s's Channel.\nSee all Channel content here." % channel[1]
                    tooltip = "Click to go to %s's Channel."%channel[1]
                
                self.channeltext = wx.StaticText(self.buttonPanel, -1, label, size=(280,-1))
                self.channeltext.SetToolTipString(tooltip)
                self.channeltext.SetMinSize((1,-1))
                self.channeltext.channel = channel
                
                font = self.channeltext.GetFont()
                font.SetUnderlined(True)
                font.SetPointSize(font.GetPointSize()+1)
                self.channeltext.SetFont(font)
                self.channeltext.Bind(wx.EVT_LEFT_DOWN, self.OnClick)
                self.channeltext.target = 'channel'
                
                if sys.platform != 'linux2':
                    self.channeltext.SetCursor(wx.StockCursor(wx.CURSOR_HAND))
                self.buttonSizer.Add(self.channeltext, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.ALL|wx.EXPAND, 3)
        self.buttonPanel.Layout()
    
    def ShowDownloadProgress(self):
        if getattr(self, 'buttonSizer', False):
            #Disable parent download button
            self.parent.button.Enable(False)
            
            self.buttonSizer.ShowItems(False)
            self.buttonSizer.DeleteWindows()
            self.buttonSizer.Clear()
            
            self.downloadText = wx.StaticText(self.buttonPanel, -1, "This torrent is in your library.")
            self.downloadText.SetToolTipString("Click to go to your library.")
            font = self.downloadText.GetFont()
            font.SetPointSize(font.GetPointSize()+1)
            font.SetUnderlined(True)
            self.downloadText.SetFont(font)
            self.downloadText.Bind(wx.EVT_LEFT_DOWN, self.OnClick)
            self.downloadText.target = 'my_files'
            
            if sys.platform != 'linux2':
                self.downloadText.SetCursor(wx.StockCursor(wx.CURSOR_HAND))
            self.buttonSizer.Add(self.downloadText, 0, wx.ALL, 3)
            
            class tmp_object():
                def __init__(self, data, original_data):
                    self.data = data
                    self.original_data = original_data
            self.item = tmp_object(['',[0,0],[0,0],0,0],self.torrent)
            self.progressPanel = ProgressPanel(self.buttonPanel, self.item)
            self.buttonSizer.Add(self.progressPanel, 0, wx.ALL|wx.EXPAND, 3)
            
            self.downText = wx.StaticText(self.buttonPanel)
            self.upText = wx.StaticText(self.buttonPanel)
            self.downSizer = wx.BoxSizer(wx.HORIZONTAL)
            self.downSizer.Add(wx.StaticText(self.buttonPanel, -1, 'Download:'), 1)
            self.downSizer.Add(self.downText)
            
            self.upSizer = wx.BoxSizer(wx.HORIZONTAL)
            self.upSizer.Add(wx.StaticText(self.buttonPanel, -1, "Upload:"), 1)
            self.upSizer.Add(self.upText)
    
            self.buttonSizer.Add(self.downSizer, 0, wx.ALL|wx.EXPAND, 3)
            self.buttonSizer.Add(self.upSizer, 0, wx.ALL|wx.EXPAND, 3)
            
            if self.information[0]:
                self.buttonSizer.AddStretchSpacer()
                self.play = wx.Button(self.buttonPanel, -1, "Start playing this torrent")
                self.play.SetToolTipString('Start playing this torrent.')
                self.play.Bind(wx.EVT_BUTTON, self.OnPlay)
                self.buttonSizer.Add(self.play, 0, wx.BOTTOM, 5)
                
            self.buttonPanel.Layout()
            self.guiutility.torrentsearch_manager.add_download_state_callback(self.OnRefresh)
        else:
            #Additionally called by database event, thus we need to check if sizer exists(torrent is downloaded).
            wx.CallAfter(self.ShowDownloadProgress)
                
    def OnDownload(self, event):
        self.guiutility.torrentsearch_manager.downloadTorrent(self.torrent)
        
    def OnPlay(self, event):
        play = event.GetEventObject()
        playable_files = self.information[1]
        
        if len(playable_files) > 1: #Create a popup
            playable_files.sort()
            dialog = wx.SingleChoiceDialog(self, 'Tribler currently only supports playing one file at a time.\nSelect the file you want to play?', 'Which file do you want to play?',playable_files)
            
            if self.notebook.GetSelection() == 1: #If currentpage is files
                selected = self.listCtrl.GetFirstSelected()
                if selected != -1:
                    selected_file = self.listCtrl.GetItemText(selected)
                    if selected_file in playable_files:
                        dialog.SetSelection(playable_files.index(selected_file))
                
            if dialog.ShowModal() == wx.ID_OK:
                response = dialog.GetStringSelection()
                
                self.guiutility.torrentsearch_manager.playTorrent(self.torrent, response)            
            dialog.Destroy()
        elif len(playable_files) == 1:
            self.guiutility.torrentsearch_manager.playTorrent(self.torrent)
    
    def OnPlaySelected(self, event):
        selected = self.listCtrl.GetFirstSelected()
        playable_files = self.information[1]
            
        if selected != -1:
            selected_file = self.listCtrl.GetItemText(selected)
            if selected_file in playable_files:
                self.guiutility.torrentsearch_manager.playTorrent(self.torrent, selected_file)
            elif self.torrent.get('progress',0) == 100: #not playable
                file = os.path.join(self.torrent.get('destdir',''), self.torrent.get('name',''),selected_file)
                if os.path.isfile(file):
                    os.startfile(file)
    
    def OnClick(self, event):
        label = event.GetEventObject()
        if label.target == 'my_files':
            self.guiutility.frame.top_bg.selectTab('my_files')
            self.guiutility.ShowPage('my_files')
        else:
            self.guiutility.frame.top_bg.selectTab('channels')
            
            channel = event.GetEventObject().channel
            if channel[0] == bin2str(self.guiutility.utility.session.get_permid()):
                self.guiutility.ShowPage('mychannel')
            else:
                if self.torrent.get('channel_permid', '') == channel[0] and 'query_permids' in self.torrent:
                    channelcast = BuddyCastFactory.getInstance().channelcast_core
                    channelcast.updateAChannel(channel[0], self.torrent['query_permids'])
                    
                self.guiutility.showChannel(channel[1], channel[0])    
    
    def UpdateStatus(self):
        if 'torrent_id' not in self.torrent:
            self.torrent['torrent_id'] = self.guiutility.torrentsearch_manager.torrent_db.getTorrentID(self.torrent['infohash'])
        
        swarmInfo = self.guiutility.torrentsearch_manager.getSwarmInfo(self.torrent['torrent_id'])[0]
        self.torrent['num_seeders'] = swarmInfo[1]
        self.torrent['num_leechers'] = swarmInfo[2]
        self.torrent['last_check'] = swarmInfo[3]
        wx.CallAfter(self.ShowStatus)
    
    def ShowStatus(self):
        diff = time() - self.torrent['last_check']
        if self.torrent['num_seeders'] < 0 and self.torrent['num_leechers'] < 0:
            self.status.SetLabel("Unknown")
        else:
            self.status.SetLabel("%s seeders, %s leechers (current)"%(self.torrent['num_seeders'], self.torrent['num_leechers']))
           
    def OnRefresh(self, dslist):
        found = False
        
        for ds in dslist:
            infohash = ds.get_download().get_def().get_infohash()
            if infohash == self.torrent['infohash']:
                found = True
                
                self.item.original_data['ds'] = ds
                self.progressPanel.Update()
                
                down = self.guiutility.utility.speed_format_new(self.item.data[3])
                if self.downText.GetLabel() != down:
                    self.downText.SetLabel(down)
                    self.downSizer.Layout()
                
                up = self.guiutility.utility.speed_format_new(self.item.data[4])
                if self.upText.GetLabel() != up:
                    self.upText.SetLabel(up)
                    self.upSizer.Layout()
                
                if ds.is_vod():
                    label = 'This torrent is being played.'
                    if getattr(self, 'play', False):
                        self.play.Hide()
                else:
                    label = 'This torrent is in your library.'
                    
                if self.downloadText.GetLabel() != label:
                    self.downloadText.SetLabel(label)
                    self.downloadText.Refresh()
                break
        
        if not found:
            self.guiutility.torrentsearch_manager.remove_download_state_callback(self.OnRefresh)

            self.buttonPanel.Freeze()
            self.ShowTorrentDetails()
            self.buttonPanel.Thaw()
            
    def __del__(self):
        if getattr(self, 'progressPanel', None) != None:
            self.guiutility.torrentsearch_manager.remove_download_state_callback(self.OnRefresh)

class LibraryDetails(TorrentDetails):
    def __init__(self, parent, torrent, mychannel_callback):
        TorrentDetails.__init__(self, parent, torrent)
        self.mychannel_callback = mychannel_callback
    
    def ShowTorrentDetails(self):
        self.ShowDownloadProgress()
        
    def ShowDownloadProgress(self):
        channel = self.guiutility.channelsearch_manager.getChannelForTorrent(self.torrent['infohash'])
        
        if channel is None or channel[0] != bin2str(self.guiutility.utility.session.get_permid()):
            header = wx.StaticText(self.buttonPanel, -1, "Did you enjoy this torrent?\nThen let others know by adding it to your channel.")
            header.SetMinSize((1,-1))
            font = header.GetFont()
            font.SetPointSize(font.GetPointSize()+1)
            header.SetFont(font)
            self.buttonSizer.Add(header, 0, wx.ALL|wx.EXPAND, 3)
            
            button = wx.Button(self.buttonPanel, -1, "Add to My Channel")
            button.Bind(wx.EVT_BUTTON, self.mychannel_callback)
            button.SetToolTipString('Add this torrent to your channel.')
            self.buttonSizer.Add(button, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.TOP, 5)
            self.buttonSizer.AddStretchSpacer()
        
        if channel and channel[0] != bin2str(self.guiutility.utility.session.get_permid()):
            label = "This torrent is included in %s's Channel.\nSee all Channel content here." % channel[1]
            tooltip = "Click to go to %s's Channel."%channel[1]
        
            channeltext = wx.StaticText(self.buttonPanel, -1, label, size=(280,-1))
            channeltext.SetToolTipString(tooltip)
            channeltext.SetMinSize((1,-1))
            channeltext.channel = channel
            
            font = channeltext.GetFont()
            font.SetUnderlined(True)
            font.SetPointSize(font.GetPointSize()+1)
            channeltext.SetFont(font)
            channeltext.Bind(wx.EVT_LEFT_DOWN, self.OnClick)
            channeltext.target = 'channel'
            if sys.platform != 'linux2':
                channeltext.SetCursor(wx.StockCursor(wx.CURSOR_HAND))
            
            self.buttonSizer.Add(channeltext, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.ALL|wx.EXPAND, 3)
    
class ProgressPanel(wx.Panel):
    def __init__(self, parent, item):
        wx.Panel.__init__(self, parent)
        self.SetBackgroundColour(wx.WHITE)
        self.item = item
        self.utility = GUIUtility.getInstance().utility

        self.pb = ProgressBar(self)
        self.status = wx.StaticText(self)
        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.AddStretchSpacer()
        vSizer.Add(self.pb, 0, wx.EXPAND)
        vSizer.Add(self.status, 0, wx.EXPAND)
        vSizer.AddStretchSpacer()
        
        self.SetSizer(vSizer)
        self.Update()
        
    def Update(self, ds = None):
        #return_val, 0 == inactive, 1 == incomplete, 2 == complete/seeding
        return_val = 0
        
        if ds == None:
            ds = self.item.original_data.get('ds', None)
        
        if ds != None:
            # Allow STOPPED_ON_ERROR, sometimes transient
            startable = not ds.get_status() in [DLSTATUS_WAITING4HASHCHECK, DLSTATUS_ALLOCATING_DISKSPACE, DLSTATUS_HASHCHECKING]
            if startable:
                #isVideo = bool(ds.get_download().get_def().get_files(exts=videoextdefaults))
                #showPlayButton = isVideo
                havedigest = ds.get_pieces_complete()
            else:
                havedigest = None
            
            #Update eta
            progress = ds.get_progress()
            finished = progress == 1.0
            if finished:
                eta = "Completed"
                if ds.get_status() == DLSTATUS_SEEDING:
                    eta += ", seeding"
                    return_val = 2
                else:
                    eta += ", inactive"
            else:
                if ds.get_status() in [DLSTATUS_WAITING4HASHCHECK, DLSTATUS_HASHCHECKING]:
                    eta = 'Checking'
                else:
                    sizestr = ''
                    size = self.item.original_data.get('length', False)
                    if size:
                        sizestr = '%s/%s (%0.1f%%)'%(self.utility.size_format(size*ds.get_progress(), 0), self.utility.size_format(size, 0), ds.get_progress()*100) 
                        
                    eta = self.utility.eta_value(ds.get_eta(), truncate=2)
                    if eta == '' or eta.find('unknown') != -1:
                        eta = sizestr
                    else:
                        eta = sizestr + ' - ' + eta
                    return_val = 1
            
            #Update eta
            if self.status.GetLabel() != eta:
                self.status.SetLabel(eta)
                self.status.Refresh()
                
                #Update graph
                if finished:
                    self.pb.reset(colour=2) # Show as complete
                elif havedigest:
                    self.pb.set_pieces(havedigest)
                elif progress > 0:
                    self.pb.reset(colour=1) # Show as having some
                else:
                    self.pb.reset(colour=0) # Show as having none
                self.pb.Refresh()
            
            seeds, peers = ds.get_num_seeds_peers()
            if seeds == None:
                seeds = 0
            if peers == None:
                peers = 0
            self.item.data[2] = [seeds, peers]
    
            dls = ds.get_current_speed('down')*1024
            self.item.data[3] = dls
            
            uls = ds.get_current_speed('up')*1024
            self.item.data[4] = uls
        else:
            eta = ''
            progress = self.item.original_data.get('progress')
            
            if progress != None:
                str_progress = '%0.1f%%' % progress
                self.pb.setNormalPercentage(progress)
                
                if progress == 100:
                    eta = 'Completed, '
                else:
                    eta = 'Incomplete, '
                self.item.data[1] = [progress,1]
            else:
                str_progress = '?'
                self.pb.reset()
                self.item.data[1] = [-1,0]
            
            eta += 'inactive'
            if self.status.GetLabel() != eta:
                self.status.SetLabel(eta)
            
            self.item.data[2] = [0,0]
            self.item.data[3] = 0
            self.item.data[4] = 0
            
        return return_val
    
class MyChannelTabs(wx.Panel):
    def __init__(self, parent, background, columns, spacers, singleSelect):
        self.parent = parent
        self.torrentfeed = TorrentFeedThread.getInstance()
        self.torrentfeed.addCallback(self.OnRssItem)
        self.guiutility = GUIUtility.getInstance()
        
        wx.Panel.__init__(self, parent)
        self.SetBackgroundColour(background)
        
        notebook = wx.Notebook(self, style = wx.NB_NOPAGETHEME)
        notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.OnChange)
        #overview page
        text =  """
        <p>
            This is your channel.
        </p>
        <p>
            You can use this channel to share files with other Tribler users.<br />
            Currently <em>three</em> options exist to share torrents. Two of them, periodically importing .torrents from an rss feed and manually adding .torrent files, are available from the 'Manage' tab. <br />
            The third option allows you to add torrents from your library (by clicking on the 'Add to My Channel' button).
        </p>
        <p>
            If your channel provides other Tribler users with original or popular content, then they might mark your channel as one of their favorites.<br />
            This will help to promote your channel, because the number of users which have marked a channel as one of their favorites is used to calculate popularity.
            Additionally, when another Tribler user marks your channel as a favorite they help you distribute all the .torrent files.
        </p>
                """
        overviewpage = wx.Panel(notebook)
        overviewpage.SetBackgroundColour(wx.WHITE)
        overviewtext = self.createHtml(overviewpage, text)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(overviewtext, 1, wx.EXPAND)
        overviewpage.SetSizer(hSizer)
        notebook.AddPage(overviewpage, "Overview")
        
        #shared files page
        filespage = wx.Panel(notebook)
        filespage.SetBackgroundColour(wx.WHITE)
        self.header = ListHeader(filespage, 7, 7, background, columns)
        self.list = ListBody(filespage, background, columns, spacers[0], spacers[1], singleSelect)
        
        #small onexpand hack
        filespage.OnExpand = self.parent.OnExpand
        filespage.OnCollapse = self.parent.OnCollapse
        filespage.OnSort = self.parent.OnSort
        
        listbuttons = wx.Panel(filespage)
        listbuttons.SetBackgroundColour(wx.WHITE)
        removesel = wx.Button(listbuttons, -1, "Remove Selected")
        removesel.Bind(wx.EVT_BUTTON, self.parent.OnRemoveSelected)
        removeall = wx.Button(listbuttons, -1, "Remove All")
        removeall.Bind(wx.EVT_BUTTON, self.parent.OnRemoveAll)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.AddStretchSpacer()
        hSizer.Add(removesel, 0, wx.ALL, 3)
        hSizer.Add(removeall, 0, wx.ALL, 3)
        listbuttons.SetSizer(hSizer)
        
        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.Add(self.header, 0, wx.EXPAND|wx.TOP, 3)
        vSizer.Add(self.list, 1, wx.EXPAND)
        vSizer.Add(listbuttons, 0, wx.EXPAND)
        filespage.SetSizer(vSizer)
        notebook.AddPage(filespage, "Shared torrents")
        
        #manage page
        self.managepage = wx.Panel(notebook)
        self.managepage.SetBackgroundColour(wx.WHITE)
        vSizer = wx.BoxSizer(wx.VERTICAL)
        
        #intro
        text =  """
        <p>
            Here you can manage your channel.
        </p>
        <p>
            Rss feeds are periodically checked for new .torrent files. For each item in the rss feed a .torrent file should be present in either:
            <ul>
            <li>The link element</li>
            <li>A src attribute</li>
            <li>A url attribute</li>
            </ul>
        </p>
                """
        self.manageText = self.createHtml(self.managepage, text)
        vSizer.Add(self.manageText, 0, wx.EXPAND)
        
        #rss
        self.gridSizer = wx.FlexGridSizer(0,2,3)
        self.gridSizer.AddGrowableCol(1)
        self.BuildRssPanel(self.managepage, self.gridSizer)
        vSizer.Add(self.gridSizer, 0, wx.EXPAND|wx.ALL, 10)
        
        self.managepage.SetSizer(vSizer)
        
        notebook.AddPage(self.managepage, "Manage")
        boxSizer = wx.BoxSizer(wx.HORIZONTAL)
        boxSizer.Add(notebook, 1, wx.EXPAND|wx.ALL, 5)
        self.SetSizer(boxSizer)
        
        self.Layout()
    
    def BuildRssPanel(self, parent, sizer):
        sizer.Add(self.createHeader(parent, "Current rss-feeds:","(which are periodically checked)"))
        
        rssSizer = wx.BoxSizer(wx.VERTICAL)
        urls = self.torrentfeed.getUrls("active")
        if len(urls) > 0:
            for url in urls:
                rowSizer = wx.BoxSizer(wx.HORIZONTAL)
                
                rsstext = wx.StaticText(parent, -1, url.replace('&', '&&'))
                rsstext.SetMinSize((1,-1))
                
                deleteButton = wx.Button(parent, -1, "Delete")
                deleteButton.url = url
                deleteButton.text = rsstext
                deleteButton.Bind(wx.EVT_BUTTON, self.OnDeleteRss)
                
                rowSizer.Add(rsstext, 1, wx.EXPAND|wx.ALIGN_CENTER_VERTICAL)
                rowSizer.Add(deleteButton, 0, wx.LEFT|wx.ALIGN_RIGHT, 5)
                rssSizer.Add(rowSizer, 0, wx.EXPAND)

            refresh = wx.Button(parent, -1, "Refresh all rss-feeds")
            refresh.Bind(wx.EVT_BUTTON, self.OnRefreshRss)
            rssSizer.Add(refresh, 0, wx.ALIGN_RIGHT | wx.TOP, 3)
        else:
            rssSizer.Add(wx.StaticText(parent, -1, "No rss feeds are being monitored."))
            
        #add-rss
        rssSizer.Add(wx.StaticText(parent, -1, "Add an rss-feed:"), 0, wx.TOP, 3)
        addSizer = wx.BoxSizer(wx.HORIZONTAL)
        url = wx.TextCtrl(parent)
        addButton = wx.Button(parent, -1, "Browse")
        addButton.url = url
        addButton.Bind(wx.EVT_BUTTON, self.OnAddRss)
        addSizer.Add(url, 1 , wx.ALIGN_CENTER_VERTICAL)
        addSizer.Add(addButton, 0, wx.LEFT|wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_RIGHT, 5)
        rssSizer.Add(addSizer, 0, wx.EXPAND, 10)
        sizer.Add(rssSizer, 1, wx.EXPAND|wx.LEFT|wx.TOP|wx.BOTTOM, 10)
        
        #manual
        sizer.Add(self.createHeader(parent, "Manually import a .torrent file:","(downloaded from another source)"), 0, wx.EXPAND)
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
    
    def createHtml(self, parent, text):
        html = wx.html.HtmlWindow(parent)
        html.SetPage(text)
        return html
    
    def createHeader(self, parent, title, subtitle):
        title = wx.StaticText(parent, -1, title)
        font = title.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        title.SetFont(font)
        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.Add(title)
        vSizer.Add(wx.StaticText(parent, -1, subtitle))
        return vSizer
    
    def OnChange(self, event):
        page = event.GetSelection()
        if page == 1:
            self.parent.ShowList()
        elif page == 2:
            self.manageText.SetMinSize((-1,self.manageText.GetVirtualSize()[1]))
            self.managepage.Layout()
        event.Skip()
    
    def OnAddRss(self, event):
        item = event.GetEventObject()
        url = item.url.GetValue().strip()
        if len(url) > 0:
            self.torrentfeed.addURL(url)
            self.RebuildRssPanel()
        
    def OnDeleteRss(self, event):
        item = event.GetEventObject()
        
        self.torrentfeed.deleteURL(item.url)
        self.RebuildRssPanel()
    
    def OnRefreshRss(self, event):
        self.torrentfeed.refresh()
        
    def OnManualAdd(self, event):
        dlg = wx.FileDialog(self,"Choose .torrent file", wildcard = "BitTorrent file (*.torrent) |*.torrent", style = wx.DEFAULT_DIALOG_STYLE|wx.FD_MULTIPLE)
        
        path = DefaultDownloadStartupConfig.getInstance().get_dest_dir() + os.sep
        dlg.SetPath(path)
        if dlg.ShowModal() == wx.ID_OK:
            files = dlg.GetPaths()
            self._import_torrents(files)
            
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
    
    def _import_torrents(self, files):
        nr_imported = 0
        for file in files:
            if file.endswith(".torrent"):
                self.torrentfeed.addFile(file)
                nr_imported += 1
        
        if nr_imported > 0:
            self.parent.manager.refresh()
            if nr_imported == 1:
                self.guiutility.frame.top_bg.Notify('New .torrent added to My Channel', wx.ART_INFORMATION)
            else:
                self.guiutility.frame.top_bg.Notify('Added %d .torrents to your Channel'%nr_imported, wx.ART_INFORMATION)
    
    def OnRssItem(self, rss_url, infohash, torrent_data):
        #this is called from another non-gui thread, thus we wrap it using wx.callafter
        self.parent.GetManager()
        wx.CallAfter(self.parent.manager.refresh)

class MyChannelDetails(wx.Panel):
    def __init__(self, parent, torrent, my_permid):
        self.parent = parent
        self.torrent = torrent
        self.my_permid = my_permid
        
        self.subsupport = SubtitlesSupport.getInstance()
        self.supportedLang = self.subsupport.langUtility.getLangSupported()
        self.supportedLangFull = self.supportedLang.values()
        self.supportedLangFull.sort()
        
        wx.Panel.__init__(self, parent)
        self.SetBackgroundColour(wx.WHITE)
        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        borderSizer = wx.BoxSizer()
        borderSizer.Add(self.vSizer, 1, wx.ALL|wx.EXPAND, 5)
        self.SetSizer(borderSizer)
        self.AddSubs()
    
    def AddSubs(self):
        self.vSizer.ShowItems(False)
        self.vSizer.DeleteWindows()
        self.vSizer.Clear()
        
        currentsubs = self.subsupport.getSubtitleInfos(self.my_permid, self.torrent['infohash'])
        if len(currentsubs) > 0:
            header = wx.StaticText(self, -1, "Current Subtitles")
            font = header.GetFont()
            font.SetWeight(wx.FONTWEIGHT_BOLD)
            header.SetFont(font)
            self.vSizer.Add(header, 0, wx.BOTTOM, 3)
            
            curlang = [self.supportedLang[langkey] for langkey in currentsubs.keys()]
            curlang.sort()
            for lang in curlang:
                self.vSizer.Add(wx.StaticText(self, -1, lang), 0, wx.LEFT, 6)
        else:
            header = wx.StaticText(self, -1, "No subtitles added to this .torrent.")
            font = header.GetFont()
            font.SetWeight(wx.FONTWEIGHT_BOLD)
            header.SetFont(font)
            self.vSizer.Add(header)
        
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(wx.StaticText(self, -1, "Add a subtitle to this .torrent"), 0, wx.ALIGN_CENTER_VERTICAL)
        hSizer.AddStretchSpacer()
        button = wx.Button(self, -1, "Browse")
        button.Bind(wx.EVT_BUTTON, self.OnClick)
        hSizer.Add(button)
        self.vSizer.Add(hSizer, 0, wx.EXPAND)
        self.vSizer.Layout()
        
        self.parent.parent_list.OnChange()
    
    def OnClick(self, event):
        dlg = wx.FileDialog(self,"Choose .srt file", wildcard = "SubRip file (*.srt) |*.srt", style = wx.DEFAULT_DIALOG_STYLE)
        
        path = DefaultDownloadStartupConfig.getInstance().get_dest_dir() + os.sep
        dlg.SetPath(path)
        if dlg.ShowModal() == wx.ID_OK:
            file = dlg.GetPath()
            dlg.Destroy()
            
            dlg = wx.SingleChoiceDialog(self, 'Choose a language for this subtitle?', 'Language?',self.supportedLangFull)
            if dlg.ShowModal() == wx.ID_OK:
                lang = dlg.GetStringSelection()
                for key, value in self.supportedLang.iteritems():
                    if value == lang:
                        self.subsupport.publishSubtitle(self.torrent['infohash'], key, file)
                        self.AddSubs()
                        break
        dlg.Destroy()
    
class SwarmHealth(wx.Panel):
    def __init__(self, parent, bordersize = 0, size = wx.DefaultSize):
        wx.Panel.__init__(self, parent, size = size, style = wx.NO_BORDER)
        self.bordersize = bordersize
        
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
    
    def SetRatio(self, seeders, leechers):
        self.blue = 0
        if leechers < 0 and seeders < 0:
            self.barwidth = 0
            
            self.green = 0
            self.red = 0
        else:
            if leechers <= 0:
                ratio = sys.maxint
            elif seeders <= 0:
                ratio = 0
            else:  
                ratio = seeders/(leechers*1.0)
            
            if ratio == 0:
                self.barwidth = 1
                self.green = 0
                self.red = 0
            else:
                pop = seeders + leechers
                if pop > 0:
                    self.barwidth = max(math.log(pop,10) * 2, 1) / 10.0
                else:
                    self.barwidth = 1
                
                self.green = max(0, min(255, 125 + (ratio * 130)))
                self.red = max(0, min(255, 125 + ((1 - ratio) * 130)))
        self.Refresh()
        
    def OnPaint(self, event):
        dc = wx.BufferedPaintDC(self)
        
        dc.SetBackground(wx.Brush(self.GetBackgroundColour()))
        dc.Clear()
        
        width, height = self.GetClientSize()
        width -= self.bordersize * 2
        width -= 1
        width -= width % 10
        width += 1
        
        xpos = (self.GetClientSize()[0] - width) / 2
            
        dc.SetPen(wx.BLACK_PEN)
        dc.SetBrush(wx.WHITE_BRUSH)
        dc.DrawRectangle(xpos, 0, width, height)
                
        dc.SetPen(wx.TRANSPARENT_PEN)
        
        dc.SetBrush(wx.Brush((self.red, self.green, self.blue), wx.SOLID))
        
        if self.barwidth > 0:
            dc.DrawRectangle(xpos + 1, 1,  self.barwidth * (width - 2), height-2)
        
        if self.green > 0 or self.red > 0:
            dc.SetPen(wx.WHITE_PEN)
            for i in range(1,10):
                x = xpos + (width/10) * i
                dc.DrawLine(x, 1, x, height - 1)

    def OnEraseBackground(self, event):
        pass
    
class ChannelPopularity(wx.Panel):
    def __init__(self, parent, background, bitmap, bordersize = 0, size = wx.DefaultSize):
        wx.Panel.__init__(self, parent, size = size, style = wx.NO_BORDER)
        self.background = background
        self.bitmap = bitmap
        self.bordersize = bordersize
        
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
    
    def SetVotes(self, votes):
        self.votes = votes
        self.Refresh()
    
    def OnPaint(self, event):
        dc = wx.BufferedPaintDC(self)
        
        dc.SetBackground(wx.Brush(self.GetBackgroundColour()))
        dc.Clear()
        
        bitmapWidth, bitmapHeight = self.bitmap.GetSize()
        
        width, height = self.GetClientSize()
        width -= self.bordersize * 2
        width = min(width, 5 * bitmapWidth)
        
        xpos = self.bordersize
        ypos = (height - bitmapHeight) / 2

        for i in range(5):
            dc.DrawBitmap(self.background, xpos + (i * bitmapWidth), ypos, True)

        dc.SetClippingRegion(xpos, ypos, width * self.votes, bitmapHeight)
        for i in range(5):
            dc.DrawBitmap(self.bitmap, xpos + (i * bitmapWidth), ypos, True)
    
    def OnEraseBackground(self, event):
        pass
