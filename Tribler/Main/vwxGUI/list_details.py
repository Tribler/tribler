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

from list_header import ListHeader
from list_body import ListBody

from font import *

class SortedListCtrl(wx.ListCtrl, ColumnSorterMixin, ListCtrlAutoWidthMixin):
    def __init__(self, parent, numColumns):
        wx.ListCtrl.__init__(self, parent, -1, style=wx.LC_REPORT)
        
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
        
        self.torrentChecker = TorrentChecking(self.torrent['infohash'])
        
    def loadTorrent(self):
        self.guiutility.torrentsearch_manager.isTorrentPlayable(self.torrent, callback = self.showTorrent)
    
    def showTorrent(self, torrent, information):
        self.torrent = torrent
        self.information = information
        
        self.Freeze()
        self.messagePanel.Show(False)
        
        self.notebook = wx.Notebook(self, style = wx.NB_NOPAGETHEME)
        
        #Create torrent overview
        self.overview = wx.Panel(self.notebook)
        self.overview.SetBackgroundColour(self.notebook.GetThemeBackgroundColour())
        vSizer = wx.BoxSizer(wx.VERTICAL)
        header = wx.StaticText(self.overview, -1, "Torrent Details")
        font = header.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        header.SetFont(font)
        vSizer.Add(header,0, wx.BOTTOM, 5)
        
        torrentSizer = wx.FlexGridSizer(0, 2, 3, 3)
        torrentSizer.AddGrowableCol(1)
        
        def add_row(name, value):
            header = wx.StaticText(self.overview, -1, name)
            font = header.GetFont()
            font.SetWeight(wx.FONTWEIGHT_BOLD)
            header.SetFont(font)
            torrentSizer.Add(header, 0, wx.RIGHT, 10)
            
            if not isinstance(value, wx.Object):
                value = wx.StaticText(self.overview, -1, value)
                value.SetMinSize((1,-1))
            torrentSizer.Add(value, 1, wx.EXPAND)
        
        def __format_time(val):
            discovered = date.fromtimestamp(val)
            return discovered.strftime('%d-%m-%y')
        
        add_row("Name", torrent['name'])
        category = torrent['category']
        if isinstance(category,list):
            category = ', '.join(category)
        add_row("Type", category.capitalize())
        add_row("Uploaded", __format_time(torrent['creation_date']))
        add_row("Filesize", self.guiutility.utility.size_format(torrent['length']) + " in " + str(len(information[2])) + " files")
        
        self.statusSizer = wx.BoxSizer(wx.HORIZONTAL)
        seeders = torrent['num_seeders']
        leechers = torrent['num_leechers']
        if seeders <= 0 and leechers <= 0:
            self.statusSizer.Add(wx.StaticText(self.overview, -1, "Unknown"))
        else:
            self.statusSizer.Add(wx.StaticText(self.overview, -1, "%s seeders, %s leechers"%(seeders,leechers)))
        add_row("Status", self.statusSizer)
        self.torrentChecker.start()
        
        vSizer.Add(torrentSizer, 0, wx.EXPAND|wx.ALL, 3)
        self.overview.SetSizer(vSizer)
        self.notebook.AddPage(self.overview, "Overview")
        
        #Create description
        if torrent['comment'] and torrent['comment'] != 'None':
            descriptionPanel = wx.Panel(self.notebook)
            descriptionPanel.SetBackgroundColour(self.notebook.GetThemeBackgroundColour())
            vSizer = wx.BoxSizer(wx.VERTICAL)
            header = wx.StaticText(descriptionPanel, -1, "Comment")
            font = header.GetFont()
            font.SetWeight(wx.FONTWEIGHT_BOLD)
            header.SetFont(font)
            vSizer.Add(header,0, wx.BOTTOM, 5)
            comment_text = wx.StaticText(descriptionPanel, -1, torrent['comment'])
            comment_text.SetMinSize((1, -1))
            vSizer.Add(comment_text, 0, wx.ALL|wx.EXPAND, 3)
            descriptionPanel.SetSizer(vSizer)
            self.notebook.AddPage(descriptionPanel, "Description")
        
        #Create filelist
        self.listCtrl = SortedListCtrl(self.notebook, 2)
        self.listCtrl.InsertColumn(0, 'Name')
        self.listCtrl.InsertColumn(1, 'Size', wx.LIST_FORMAT_RIGHT)
        self.listCtrl.SetColumnWidth(1, 70)
        self.listCtrl.setResizeColumn(1) #resize column starts at 1 instead of 0
        self.listCtrl.SetMinSize((1,-1))
        
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
                filename = unicode(filename)
                pos = self.listCtrl.InsertStringItem(sys.maxint, filename)
            self.listCtrl.SetItemData(pos, pos)
            self.listCtrl.itemDataMap.setdefault(pos, [filename, size])
            
            size = self.guiutility.utility.size_format(size)
            self.listCtrl.SetStringItem(pos, 1, size)
            
            if filename in information[1]:
                self.listCtrl.SetItemColumnImage(pos, 0, play_img)
            else:
                self.listCtrl.SetItemColumnImage(pos, 0, file_img)
        
        self.notebook.AddPage(self.listCtrl, "Files")
        
        #Create trackerlist
        trackerPanel = wx.Panel(self.notebook)
        trackerPanel.SetBackgroundColour(self.notebook.GetThemeBackgroundColour())
        vSizer = wx.BoxSizer(wx.VERTICAL)
        header = wx.StaticText(trackerPanel, -1, "Trackers")
        font = header.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        header.SetFont(font)
        vSizer.Add(header,0, wx.BOTTOM, 5)
        trackerlist = wx.lib.scrolledpanel.ScrolledPanel(trackerPanel)
        trackerSizer = wx.BoxSizer(wx.VERTICAL)
        for trackers in torrent['trackers']:
            for tracker in trackers:
                trackerSizer.Add(wx.StaticText(trackerlist, -1, tracker), 0, wx.EXPAND|wx.ALL, 3)
        trackerlist.SetSizer(trackerSizer)
        trackerlist.SetupScrolling()
        vSizer.Add(trackerlist, 1, wx.EXPAND)
        trackerPanel.SetSizer(vSizer)
        self.notebook.AddPage(trackerPanel, "Trackers")
        
        #Set height depending on number of files present
        minHeight = min(130, self.notebook.GetBestSize()[1])
        maxHeight = 180
        self.notebook.SetMinSize((-1, min(minHeight + len(information[2]) * 16, maxHeight)))
        self.details.Add(self.notebook, 6, wx.EXPAND|wx.ALL, 3)
        
        self.buttonPanel = wx.Panel(self)
        self.buttonPanel.SetBackgroundColour(wx.WHITE)
        self.buttonSizer = wx.BoxSizer(wx.VERTICAL)
        
        if self.torrent.get('ds', False):
            self.ShowDownloadProgress()
        else:
            self.ShowTorrentDetails()
        
        self.buttonPanel.SetSizer(self.buttonSizer)
        self.details.Add(self.buttonPanel, 4, wx.EXPAND)
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
            channel = self.guiutility.channelsearch_manager.getChannelForTorrent(self.torrent['infohash'])
            if channel is not None:
                if channel[0] == bin2str(self.guiutility.utility.session.get_permid()):
                    label = "This torrent is part of My Channel."
                    tooltip = "Click to got to your Channel."
                else:
                    label = "This torrent is part of %s's Channel." % channel[1]
                    tooltip = "Click to go to %s's Channel."%channel[1]
                
                self.channeltext = wx.StaticText(self.buttonPanel, -1, label, size=(280,-1))
                self.channeltext.SetToolTipString(tooltip)
                self.channeltext.SetMinSize((1,-1))
                self.channeltext.channel = channel
                
                font = self.channeltext.GetFont()
                font.SetUnderlined(True)
                self.channeltext.SetFont(font)
                self.channeltext.Bind(wx.EVT_LEFT_DOWN, self.OnClick)
                self.channeltext.target = 'channel'
                
                if sys.platform != 'linux2':
                    self.channeltext.SetCursor(wx.StockCursor(wx.CURSOR_HAND))
                self.buttonSizer.Add(self.channeltext, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.ALL|wx.EXPAND, 3)
        
        self.buttonPanel.Layout()
    
    def ShowDownloadProgress(self):
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
        self.buttonSizer.Add(self.progressPanel, 0, wx.ALL, 3)
        
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
            self.play = wx.Button(self.buttonPanel, -1, "Play")
            self.play.SetToolTipString('Start playing this torrent.')
            self.play.Bind(wx.EVT_BUTTON, self.OnPlay)
            self.buttonSizer.Add(self.play, 0, wx.BOTTOM, 5)
            
        self.buttonPanel.Layout()
        self.guiutility.torrentsearch_manager.add_download_state_callback(self.OnRefresh)
                
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
                self.guiutility.showChannel(channel[1], channel[0])    
    
    def UpdateStatus(self):
        if 'torrent_id' not in self.torrent:
            self.torrent['torrent_id'] = self.guiutility.torrentsearch_manager.torrent_db.getTorrentID(self.torrent['infohash'])
        swarmInfo = self.guiutility.torrentsearch_manager.torrent_db.getSwarmInfo(self.torrent['torrent_id'])[0]
        self.torrent['num_seeders'] = swarmInfo[1]
        self.torrent['num_leechers'] = swarmInfo[2]
        
        wx.CallAfter(self.ShowStatus)
    
    def ShowStatus(self):
        self.statusSizer.ShowItems(False)
        self.statusSizer.Clear()
        self.statusSizer.Add(wx.StaticText(self.overview, -1, "%s seeders, %s leechers"%(self.torrent['num_seeders'], self.torrent['num_leechers'])))
        self.statusSizer.Layout()
           
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
    
    def ShowDownloadProgress(self):
        header = wx.StaticText(self.buttonPanel, -1, "Did you enjoy this torrent?\nThen let other know by adding it to your channel.")
        header.SetMinSize((1,-1))
        font = header.GetFont()
        font.SetPointSize(font.GetPointSize()+1)
        header.SetFont(font)
        self.buttonSizer.Add(header, 0, wx.ALL|wx.EXPAND, 3)
        
        self.buttonSizer.AddStretchSpacer()
        
        button = wx.Button(self.buttonPanel, -1, "Add to My Channel")
        button.Bind(wx.EVT_BUTTON, self.mychannel_callback)
        button.SetToolTipString('Add this torrent to your channel.')
        
        self.buttonSizer.Add(button, 0, wx.ALIGN_CENTER_HORIZONTAL)
    
class ProgressPanel(wx.Panel):
    def __init__(self, parent, item):
        wx.Panel.__init__(self, parent)
        self.SetBackgroundColour(wx.WHITE)
        self.item = item
        self.utility = GUIUtility.getInstance().utility
        
        self.SetMinSize((150,-1))
        self.pb = ProgressBar(self)

        self.eta = wx.StaticText(self)
        self.percentage = wx.StaticText(self, -1, "100.0%", style = wx.ST_NO_AUTORESIZE | wx.ALIGN_RIGHT)
        self.percentage.SetLabel('')
        
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(self.pb, 1, wx.ALIGN_CENTER_VERTICAL)
        hSizer.Add(self.percentage, 0, wx.LEFT|wx.FIXED_MINSIZE|wx.ALIGN_CENTER_VERTICAL, 3)
        
        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.AddStretchSpacer()
        vSizer.Add(hSizer, 0, wx.EXPAND)
        vSizer.Add(self.eta)
        vSizer.AddStretchSpacer()
        
        self.SetSizer(vSizer)
        self.Update()
        
    def Update(self, ds = None):
        #return_val, 0 == inactive, 1 == incomplete, 2 == complete/seeding
        return_val = 0
        
        if ds == None:
            ds = self.item.original_data.get('ds', None)
        
        if ds != None:
            #Update eta
            finished = ds.get_progress() == 1.0
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
                    eta = self.utility.eta_value(ds.get_eta(), truncate=2)
                    if eta == '' or eta.find('unknown') != -1:
                        eta = ''
                    return_val = 1
            
            #Update progress
            progress = (ds.get_progress() or 0.0) * 100.0
            if progress != self.item.data[1][0]:
                self.percentage.SetLabel('%.1f%%' % progress)
                self.percentage.Refresh()
                self.item.data[1] = [progress,2]
            
            #Update eta
            if self.eta.GetLabel() != eta:
                self.eta.SetLabel(eta)
                self.eta.Refresh()
            
            seeds, peers = ds.get_num_seeds_peers()
            if seeds == None:
                seeds = 0
            if peers == None:
                peers = 0
            self.item.data[2] = [seeds, peers]
                
            # Allow STOPPED_ON_ERROR, sometimes transient
            startable = not ds.get_status() in [DLSTATUS_WAITING4HASHCHECK, DLSTATUS_ALLOCATING_DISKSPACE, DLSTATUS_HASHCHECKING]
            if startable:
                #isVideo = bool(ds.get_download().get_def().get_files(exts=videoextdefaults))
                #showPlayButton = isVideo
                havedigest = ds.get_pieces_complete()
            else:
                havedigest = None
                
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
                
            if self.percentage.GetLabel() != str_progress:
                self.percentage.SetLabel(str_progress)
            
            eta += 'inactive'
            if self.eta.GetLabel() != eta:
                self.eta.SetLabel(eta)
            
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
            Currently <em>three</em> options exist to share torrents, periodically importing .torrents from an rss feed and manually adding .torrent files are available in the 'Manage' tab. <br />
            The third option allows you to add torrents from your library (by clicking on the '+ My Channel' button).
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
                
                rsstext = wx.StaticText(parent, -1, url)
                rsstext.SetMinSize((1,-1))
                
                deleteButton = wx.Button(parent, -1, "Delete")
                deleteButton.url = url
                deleteButton.text = rsstext
                deleteButton.Bind(wx.EVT_BUTTON, self.OnDeleteRss)
                
                rowSizer.Add(rsstext, 1, wx.EXPAND|wx.ALIGN_CENTER_VERTICAL)
                rowSizer.Add(deleteButton, 0, wx.LEFT|wx.ALIGN_RIGHT, 5)
                rssSizer.Add(rowSizer, 0, wx.EXPAND)
        else:
            rssSizer.Add(wx.StaticText(parent, -1, "No rss feeds are being monitored."))
            
        #add-rss
        rssSizer.Add(wx.StaticText(parent, -1, "Add a rss-feed:"), 0, wx.TOP, 3)
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
        sizer.Add(self.createHeader(parent, "Manually import a .torrent file:","(downloaded from another source)"), 0, wx.EXPAND)
        browseButton = wx.Button(parent, -1, "Browse")
        browseButton.Bind(wx.EVT_BUTTON, self.OnManualAdd)
        sizer.Add(browseButton, 0, wx.ALIGN_RIGHT|wx.LEFT|wx.TOP, 10)
    
    def RebuildRssPanel(self):
        self.gridSizer.ShowItems(False)
        self.gridSizer.Clear()
        
        rssPanel = self.BuildRssPanel(self.managepage, self.gridSizer)
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
        
    def OnManualAdd(self, event):
        dlg = wx.FileDialog(self,"Choose .torrent file", wildcard = "BitTorrent file (*.torrent) |*.torrent", style = wx.DEFAULT_DIALOG_STYLE)
        
        path = DefaultDownloadStartupConfig.getInstance().get_dest_dir() + os.sep
        dlg.SetPath(path)
        if dlg.ShowModal() == wx.ID_OK and os.path.isfile(dlg.GetPath()):
            self.torrentfeed.addFile(dlg.GetPath())
            self.parent.manager.refresh()
            
            self.guiutility.frame.top_bg.Notify('New .torrent added to My Channel', wx.ART_INFORMATION)
    
    def OnRssItem(self, rss_url, infohash, torrent_data):
        #this is called from another non-gui thread, thus we wrap it using wx.callafter
        self.parent.GetManager()
        wx.CallAfter(self.parent.manager.refresh)

class SwarmHealth(wx.Panel):
    def __init__(self, parent, bordersize = 0, size = wx.DefaultSize):
        wx.Panel.__init__(self, parent, size = size, style = wx.NO_BORDER)
        self.bordersize = bordersize
        
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
    
    def SetRatio(self, ratio):
        self.ratio = max(0, ratio)
        
        self.green = max(0, min(255, 125 + (self.ratio * 260)))
        self.red = max(0, min(255, 125 + ((1 - self.ratio) * 260)))
        self.Refresh()
        
    def OnPaint(self, event):
        dc = wx.BufferedPaintDC(self)
        
        dc.SetBackground(wx.Brush(self.GetBackgroundColour()))
        dc.Clear()
        
        width, height = self.GetClientSize()
        width -= self.bordersize * 2
        width -= width % 10
        width += 1

        xpos = (self.GetClientSize()[0] - width) / 2
            
        dc.SetPen(wx.BLACK_PEN)
        dc.SetBrush(wx.WHITE_BRUSH)
        dc.DrawRectangle(xpos, 0, width, height)
                
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.SetBrush(wx.Brush((self.red, self.green, 0), wx.SOLID))
        
        if self.ratio == 0:
            colorwidth = width - 2
        else:
            colorwidth = (width - 2) * min(self.ratio,1)
        dc.DrawRectangle(xpos + 1, 1, colorwidth , height-2)
        
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
        
        width, height = self.GetClientSize()
        width -= self.bordersize * 2
        
        bitmapWidth, bitmapHeight = self.bitmap.GetSize()
        xpos = (self.GetClientSize()[0] - width) / 2
        ypos = (height - bitmapHeight) / 2

        for i in range(5):
            dc.DrawBitmap(self.background, xpos + (i * bitmapWidth), ypos, True)

        dc.SetClippingRegion(xpos, ypos, width * self.votes, bitmapHeight)
        for i in range(5):
            dc.DrawBitmap(self.bitmap, xpos + (i * bitmapWidth), ypos, True)
    
    def OnEraseBackground(self, event):
        pass
