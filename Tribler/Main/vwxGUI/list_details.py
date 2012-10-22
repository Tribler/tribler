# Written by Niels Zeilemaker
import wx
import sys
import os
import re
import shutil
from datetime import date, datetime
from threading import currentThread

from Tribler.Core.API import *
from Tribler.Core.osutils import startfile
from Tribler.TrackerChecking.TorrentChecking import *
from Tribler.Video.Progress import ProgressBar
from Tribler.Main.vwxGUI.SearchGridManager import TorrentManager
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.globals import DefaultDownloadStartupConfig
from Tribler.Core.CacheDB.sqlitecachedb import bin2str
from Tribler.Core.CacheDB.SqliteCacheDBHandler import UserEventLogDBHandler
from Tribler.Main.vwxGUI.widgets import LinkStaticText, BetterListCtrl, EditText, SelectableListCtrl, _set_font, BetterText as StaticText,\
    MaxBetterText, NotebookPanel, SimpleNotebook, NativeIcon, DottedBetterText,\
    ProgressButton, GradientPanel, TransparentText, LinkText

from list_body import ListBody
from widgets import _set_font
from __init__ import *
from Tribler.Core.simpledefs import DLSTATUS_STOPPED, DLSTATUS_STOPPED_ON_ERROR
from Tribler.Main.Utility.GuiDBHandler import startWorker, GUI_PRI_DISPERSY
from Tribler.Main.Utility.GuiDBTuples import RemoteChannel, Torrent,\
    LibraryTorrent, ChannelTorrent, CollectedTorrent, Channel, Playlist
from Tribler.community.channel.community import ChannelCommunity

VLC_SUPPORTED_SUBTITLES = ['.cdg', '.idx', '.srt', '.sub', '.utf', '.ass', '.ssa', '.aqt', '.jss', '.psb', '.rt', '.smi']
DEBUG = False

class AbstractDetails(GradientPanel):
    
    @warnWxThread
    def _create_tab(self, notebook, tabname, header = None, spacer = 0, border = 0):
        panel = wx.lib.scrolledpanel.ScrolledPanel(notebook)
        def OnChange():
            panel.Layout()
            panel.SetupScrolling(rate_y = 5, scroll_x = False)
        panel.OnChange = OnChange
        
        themeColour = notebook.GetThemeBackgroundColour()
        if themeColour.IsOk():
            panel.SetBackgroundColour(themeColour)
        
        notebook.AddPage(panel, tabname)
        
        vSizer = wx.BoxSizer(wx.VERTICAL)
        panel.SetSizer(vSizer)
        
        if border:
            vSizer2 = wx.BoxSizer(wx.VERTICAL)
            vSizer.Add(vSizer2, 1, wx.EXPAND|wx.ALL, border)
            vSizer = vSizer2
        
        if header:
            header = self._add_header(panel, vSizer, header, spacer)
            panel.SetLabel = header.SetLabel
        
        return panel, vSizer

    @warnWxThread
    def _add_header(self, panel, sizer, header, spacer = 0):
        header = wx.StaticText(panel, -1, header)
        _set_font(header, fontweight = wx.FONTWEIGHT_BOLD)

        sizer.Add(header, 0, wx.LEFT|wx.BOTTOM, spacer)
        return header
    
    @warnWxThread    
    def _add_row(self, parent, sizer, name, value, spacer = 0, flags = wx.EXPAND):
        nametext = name
        if name != None:
            nametext = wx.StaticText(parent, -1, name)
            _set_font(nametext, fontweight = wx.FONTWEIGHT_BOLD)

            sizer.Add(nametext, 0, wx.LEFT, spacer)
        
        if value != None:
            if isinstance(value, basestring):
                try:
                    value = MaxBetterText(parent, unicode(value), maxLines = 3, name = name)
                except:
                    value = MaxBetterText(parent, value.decode('utf-8','ignore'), maxLines = 3, name = name)
                value.SetMinSize((1,-1))
            sizer.Add(value, 0, flags|wx.LEFT, spacer)
        
        return nametext, value

    @warnWxThread
    def _add_subheader(self, parent, sizer, title, subtitle):
        title = wx.StaticText(parent, -1, title)
        _set_font(title, fontweight = wx.FONTWEIGHT_BOLD)
        
        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.Add(title)
        vSizer.Add(wx.StaticText(parent, -1, subtitle))
        
        sizer.Add(vSizer)
        return vSizer

class TorrentDetails(AbstractDetails):
    FINISHED = 6
    FINISHED_INACTIVE = 5
    
    INCOMPLETE = 4
    INCOMPLETE_INACTIVE = 3
    
    VOD = 2
    INACTIVE = 1
    
    SAVESPACE_THRESHOLD = 800
    MINCOMMENTHEIGHT = 230

    @warnWxThread
    def __init__(self, parent, torrent, compact=False, noChannel=False):
        GradientPanel.__init__(self, parent)
        self.Hide()

        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility
        self.uelog = UserEventLogDBHandler.getInstance()
        
        self.parent = parent
        self.torrent = torrent
        self.state = -1
        self.vod_log = None

        self.isReady = False
        self.noChannel = noChannel
        
        self.SetBackgroundColour(wx.Colour(246,246,246))
        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        
        self.timeouttimer = None
        
        #Add messagePanel text
        self.messageIcon = wx.StaticBitmap(self, -1, wx.ArtProvider.GetBitmap(wx.ART_INFORMATION))
        self.messagePanel = TransparentText(self, -1, "Loading details, please wait.")
        self.messageGauge = None
        self.messageButton = None
        _set_font(self.messagePanel, size_increment = 2, fontweight = wx.FONTWEIGHT_NORMAL)
        
        for colour, height in [(SEPARATOR_GREY, 1), (FILTER_GREY, 25), (SEPARATOR_GREY, 1)]:
            panel = wx.Panel(self)
            panel.SetMinSize((-1,height))
            panel.SetBackgroundColour(colour)
            self.vSizer.Add(panel, 0, wx.EXPAND)
        
        self.vSizer.AddStretchSpacer()
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(self.messageIcon, 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 15)
        hSizer.Add(self.messagePanel, 0, wx.ALL, 3)
        self.vSizer.Add(hSizer, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_CENTER_HORIZONTAL)
        self.vSizer.AddStretchSpacer()
        
        #Add details view
        self.SetSizer(self.vSizer)
        self.Layout()
        
        self.doMark = self.guiutility.frame.selectedchannellist.OnMarkTorrent
        self.doSave = self.guiutility.frame.selectedchannellist.OnSaveTorrent
        self.canEdit = False
        self.canComment = False
        self.canMark = False
        self.showDetails = False
        self.markWindow = None
        self.markings = None
        self.myMark = None
        
        self.isEditable = {}
        
        self.guiutility.library_manager.add_download_state_callback(self.OnRefresh)
        self._doLoad()
        
        self.Show()

    def _doLoad(self):
        if DEBUG:
            print >> sys.stderr, "TorrentDetails: loading", self.torrent['name']
            
        if self.messageButton:
            self.messageButton.Show(False)
            
        #is this torrent collected?
        filename = self.guiutility.torrentsearch_manager.getCollectedFilename(self.torrent, retried = True)
        if filename:
            self.guiutility.torrentsearch_manager.loadTorrent(self.torrent, callback = self.showTorrent)
            
        else:
            def doGui(delayedResult):
                requesttype = delayedResult.get()
                if requesttype:
                    self.showRequestType('The torrentfile is requested %s.'%requesttype)
                    self.messageGauge = wx.Gauge(self, -1, size = (100, 15))
                    self.vSizer.Insert(5, self.messageGauge, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.TOP, 10)
                    self.Layout()
                
                self.timeouttimer = wx.CallLater(10000, self._timeout)
           
            startWorker(doGui, self.guiutility.torrentsearch_manager.loadTorrent, wargs = (self.torrent,), wkwargs = {'callback':self.showTorrent}, priority = GUI_PRI_DISPERSY)
    
    @forceWxThread
    def showRequestType(self, requesttype):
        try:
            if requesttype:
                self.messagePanel.SetLabel("Loading details, please wait.\n%s"%requesttype)
            else:
                self.messagePanel.SetLabel("Loading details, please wait.")
            
            self.Layout()
        except wx.PyDeadObjectError:
            pass

    @forceWxThread
    def showTorrent(self, torrent, showTab = None):
        GUIUtility.getInstance().frame.top_bg.AddCollectedTorrent(torrent)                
        
        try:
            if not self.isReady:
                self.state = -1
                
                if DEBUG:
                    print >> sys.stderr, "TorrentDetails: finished loading", self.torrent.name
                
                self.torrent = torrent
                ds = self.torrent.ds
                

                isChannelTorrent = isinstance(self.torrent, ChannelTorrent) or (isinstance(self.torrent, CollectedTorrent) and isinstance(self.torrent.torrent, ChannelTorrent))
                if isChannelTorrent and self.torrent.hasChannel():
                    #This is a db call
                    state, iamModerator = self.torrent.channel.getState()
                    
                    if isinstance(self, LibraryDetails):
                        self.canMark = state >= ChannelCommunity.CHANNEL_SEMI_OPEN
                    else:
                        self.canEdit = state >= ChannelCommunity.CHANNEL_OPEN
                        self.canComment = state >= ChannelCommunity.CHANNEL_SEMI_OPEN
            
                self.Freeze()
                self.messagePanel.Show(False)
                self.messageIcon.Show(False)
                if self.messageGauge: self.messageGauge.Show(False) 
            
                self.notebook = SimpleNotebook(self, style = wx.NB_NOPAGETHEME, name = "TorrentDetailsNotebook")
                showTab = getattr(self.parent, self.__class__.__name__+'_tab', None) if self.parent else None
                self._addTabs(ds, showTab)
                
                self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.OnChange)
                
                self.vSizer.Clear(deleteWindows = True)
                self.vSizer.Add(self.notebook, 1, wx.EXPAND)
            
                self._Refresh(ds)
                        
                self.Thaw()
    
                self.isReady = True
                self.Layout()
            
                
        except wx.PyDeadObjectError:
            pass
    
    @forceWxThread
    def _timeout(self):
        try:
            if not self.isReady:
                if DEBUG:
                    print >> sys.stderr, "TorrentDetails: timeout on loading", self.torrent.name
            
                self.messagePanel.SetLabel("Failed loading torrent.\nPlease click retry or wait to allow other peers to respond.")
                if self.messageGauge:
                    self.messageGauge.Show(False)
                if self.messageButton:
                    self.messageButton.Show(True)
                else:
                    self.messageButton = wx.Button(self, -1, "Retry")
                    self.messageButton.Bind(wx.EVT_BUTTON, lambda evt: self._doLoad())
                    self.vSizer.Insert(5, self.messageButton, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.TOP, 10)
                
                self.Layout()
        except wx.PyDeadObjectError:
            pass
    
    @warnWxThread
    def _addTabs(self, ds, showTab = None):
        finished = self.torrent.get('progress', 0) == 100 or (ds and ds.get_progress() == 1.0)
        
        self.overview, self.torrentSizer = self._create_tab(self.notebook, 'Torrent details', border = 10)
        self.overview.SetBackgroundColour(wx.WHITE)
        self.overview.Bind(wx.EVT_LEFT_DCLICK, self.OnOverviewToggle)
        self._addOverview(self.overview, self.torrentSizer)

        if self.canEdit:
            #Create edit tab
            edit, editSizer = self._create_tab(self.notebook, 'Edit', border = 10)
            edit.SetBackgroundColour(wx.WHITE)
            
            vSizer = wx.FlexGridSizer(0, 2, 3, 10)
            vSizer.AddGrowableCol(1)
            vSizer.AddGrowableRow(1)
            
            self.isEditable['name'] = EditText(edit, self.torrent.name)
            self.isEditable['description'] = EditText(edit, self.torrent.description or '', True)
            self.isEditable['description'].SetMinSize((1,1))
            
            self._add_row(edit, vSizer, "Name", self.isEditable['name'])
            self._add_row(edit, vSizer, "Description",self.isEditable['description'])
            
            def save(event):
                self.doSave(self.torrent.channel, self)
                
                button = event.GetEventObject()
                button.Enable(False)
                wx.CallLater(5000, button.Enable, True)
            
            saveButton = wx.Button(edit, -1, "Save")
            saveButton.Bind(wx.EVT_BUTTON, save)
            vSizer.Add((-1,-1), 0, wx.ALIGN_RIGHT)
            vSizer.Add(saveButton, 0, wx.ALIGN_RIGHT)
            editSizer.Add(vSizer, 1, wx.EXPAND)
                    
        #Create torrent overview
        if self.canComment:
            from channel import CommentList
            self.commentList = NotebookPanel(self.notebook)
            list = CommentList(self.commentList, self.parent, canReply = True, quickPost = True, horizontal = True, noheader = True)
            self.commentList.SetList(list)
            commentManager = self.commentList.GetManager()
            commentManager.SetIds(self.torrent.channel, channeltorrent = self.torrent)
            
            def updateTitle(nrcomments):
                for i in range(self.notebook.GetPageCount()):
                    if self.notebook.GetPageText(i).startswith('Comments'):
                        self.notebook.SetPageText(i, "Comments(%d)"%nrcomments)
            self.commentList.SetNrResults = updateTitle

            self.notebook.AddPage(self.commentList, 'Comments')
            commentManager.refresh()
        
        hasDescription = self.torrent.get('description', '')
        if self.canEdit or hasDescription:
            from channel import ModificationList
            self.modificationList = NotebookPanel(self.notebook)
            self.modificationList.SetList(ModificationList(self.modificationList, self.canEdit))
            modificationManager = self.modificationList.GetManager()
            modificationManager.SetIds(self.torrent)
            
            def updateTitle(nrmodifications):
                for i in range(self.notebook.GetPageCount()):
                    if self.notebook.GetPageText(i).startswith('Modifications'):
                        self.notebook.SetPageText(i, "Modifications(%d)"%nrmodifications)
            self.modificationList.SetNrResults = updateTitle
            
            self.notebook.AddPage(self.modificationList, 'Modifications')
            modificationManager.refresh()
        
        #Create filelist
        if len(self.torrent.files) > 0:
            parent = wx.Panel(self.notebook)
            
            self.listCtrl = SelectableListCtrl(parent)
            self.listCtrl.InsertColumn(0, 'Name')
            self.listCtrl.InsertColumn(1, 'Size', wx.LIST_FORMAT_RIGHT)
            
            if isinstance(self, LibraryDetails):
                self.listCtrl.InsertColumn(2, 'Status', wx.LIST_FORMAT_RIGHT)
                
            self.listCtrl.Bind(wx.EVT_LEFT_DCLICK, self.OnDoubleClick)
            self.listCtrl.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnFilesSelected)
            self.listCtrl.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.OnFilesSelected)
            
            self.il = wx.ImageList(16,16)
            play_img = self.il.Add(wx.Bitmap(os.path.join(self.guiutility.vwxGUI_path, 'images', 'library_play.png'), wx.BITMAP_TYPE_ANY))
            file_img = self.il.Add(wx.ArtProvider.GetBitmap(wx.ART_NORMAL_FILE, size = (16,16)))
            self.listCtrl.SetImageList(self.il, wx.IMAGE_LIST_SMALL)
            
            #Add files
            files = self.torrent.files
            if isinstance(self, LibraryDetails):
                if ds:
                    selected_files = ds.get_selected_files()
                    if selected_files:
                        def sort_by_selected_name(a, b):
                            aSelected = a[0] in selected_files
                            bSelected = b[0] in selected_files
                            
                            if aSelected != bSelected:
                                if aSelected:
                                    return -1
                                return 1
                            
                            return cmp(a[0],b[0])                      
                        files.sort(sort_by_selected_name)
            else:
                keywords = ' | '.join(self.guiutility.current_search_query)
                def sort_by_keywords(a, b):
                    a_match = re.search(keywords, a[0].lower())
                    b_match = re.search(keywords, b[0].lower())
                    if a_match and not b_match:
                        return -1
                    if b_match and not a_match:
                        return 1
                    return cmp(a[0],b[0])

                files.sort(sort_by_keywords)
                
            for filename, size in files:
                try:
                    pos = self.listCtrl.InsertStringItem(sys.maxint, filename)
                except:
                    try:
                        pos = self.listCtrl.InsertStringItem(sys.maxint, filename.decode('utf-8','ignore'))
                    except:
                        print >> sys.stderr, "Could not format filename", self.torrent.name
                self.listCtrl.SetItemData(pos, pos)
                
                size = "%.1f MB"%(size/1048576.0)
                self.listCtrl.SetStringItem(pos, 1, size)
                
                if filename in self.torrent.videofiles:
                    self.listCtrl.SetItemColumnImage(pos, 0, play_img)
                else:
                    self.listCtrl.SetItemColumnImage(pos, 0, file_img)
                    
                if isinstance(self, LibraryDetails):
                    self.listCtrl.SetStringItem(pos, 2, '')
            
            self.listCtrl.setResizeColumn(0)
            self.listCtrl.SetColumnWidth(1, wx.LIST_AUTOSIZE) #autosize only works after adding rows
            self.listCtrl.SetMinSize((1,-1))
            
            vSizer = wx.BoxSizer(wx.VERTICAL)
            if isinstance(self, LibraryDetails):
                vSizer.Add(self.listCtrl, 1, wx.EXPAND|wx.LEFT)
                vSizer.Add(wx.StaticLine(parent, -1, style = wx.LI_HORIZONTAL), 0, wx.EXPAND|wx.ALL, 3)
                ulfont = self.GetFont()
                ulfont.SetUnderlined(True)
                self.filesFooter = LinkText(parent, 'Click here to modify which files should be downloaded.', fonts = [self.GetFont(), ulfont], colours = [self.GetForegroundColour(), wx.RED])
                self.filesFooter.Bind(wx.EVT_LEFT_UP, self.OnChangeSelection)
                vSizer.Add(self.filesFooter, 0, wx.EXPAND|wx.ALL, 3)
            else:
                vSizer.Add(self.listCtrl, 1, wx.EXPAND|wx.LEFT)
            parent.SetSizer(vSizer)
            self.notebook.AddPage(parent, "Files")
        
        #Create subtitlelist
        if self.torrent.isPlayable():
            curlang = []
            strlang = []
            
            internalSubs = self.torrent.subtitlefiles
            internalSubs.sort()
            
            for filename in internalSubs:
                _, nicefilename = os.path.split(filename)
                strlang.append(nicefilename)
                curlang.append([filename])
                
            foundSubtitles = len(curlang) > 0
            
            subtitlePanel, vSizer = self._create_tab(self.notebook, "Subtitles", border = 10)
            subtitlePanel.SetBackgroundColour(wx.WHITE)
            vSizer.AddSpacer((-1, 3))
            
            if not finished:
                title = 'After you finished downloading this torrent you can select a subtitle'
            else:
                title = 'You can now select a subtitle'
            
            if foundSubtitles:
                title += ' found by Tribler or'
            title += ' specified by you to be used with our player.'
            self._add_row(subtitlePanel, vSizer, None, title)
            
            vSizer.AddStretchSpacer()
            
            curlang.insert(0, ('','',''))
            strlang.insert(0, 'No subtitle')
            
            curlang.append(('','',''))
            strlang.append('Browse for a subtitle...')

            self.subtitleChoice = wx.Choice(subtitlePanel, choices = strlang)
            self.subtitleChoice.Bind(wx.EVT_CHOICE, self.OnSubtitle)
            self.subtitleChoice.Enable(False)
            self.subtitleChoice.items = curlang
              
            self.requestingSub = StaticText(subtitlePanel)
            self.requestingSub.Show(False)
            hSizer = wx.BoxSizer(wx.HORIZONTAL)
            
            self._add_row(subtitlePanel, hSizer, "Which subtitle do you want to use?", None)
            hSizer.AddStretchSpacer()
            hSizer.Add(self.subtitleChoice)
            vSizer.Add(hSizer, 0, wx.ALIGN_RIGHT|wx.BOTTOM|wx.RIGHT|wx.EXPAND, 3)
            vSizer.Add(self.requestingSub, 0, wx.ALIGN_RIGHT|wx.BOTTOM|wx.RIGHT, 3)
     
        #Create description
        """
        if self.torrent.get('comment', 'None') != 'None' and self.torrent['comment'] != '':
            descriptionPanel, vSizer = self._create_tab(self.notebook, "Description", "Comment")
            self._add_row(descriptionPanel, vSizer, None, self.torrent['comment'])
            descriptionPanel.SetupScrolling(rate_y = 5)
        """
        
        #Create trackerlist
        if self.torrent.trackers and len(self.torrent.trackers) > 0:
            trackerPanel, vSizer = self._create_tab(self.notebook, "Trackers", border = 10)
            trackerPanel.SetBackgroundColour(wx.WHITE)
            for tracker in self.torrent.trackers:
                if isinstance(tracker, basestring):
                    self._add_row(trackerPanel, vSizer, None, tracker)
                
        if showTab:
            for i in range(self.notebook.GetPageCount()):
                if self.notebook.GetPageText(i) == showTab:
                    self.notebook.SetSelection(i)
                    break
        else:
            self.notebook.SetSelection(0)
            
    @warnWxThread
    def _addOverview(self, panel, sizer):
        self.Freeze()

        status_label = self.status.label.GetLabel() if getattr(self, 'status', None) else ""
        sizer.Clear(deleteWindows = True)
        
        categories = self.torrent.categories
        if isinstance(categories, list):
            category = ', '.join(categories)
        else:
            print >> sys.stderr, 'categories is',type(categories)
            category = 'Unknown'

        if not self.torrent.get('description', ''):
            description = 'No description yet, be the first to add a description.'
        else:
            description = self.torrent.description
        
        filesize = "%s in %d file"%(self.guiutility.utility.size_format(self.torrent.length), len(self.torrent.files))
        if len(self.torrent.files) > 1:
            filesize += "s"

        overviewColumns = {
            "Name": self.torrent.name,
            "Description": description,
            "Downloaded": "",
            "Status": status_label,
            "Type": category.capitalize(),
            "Uploaded": self.torrent.formatCreationDate(),
            "Filesize": filesize,
            "Health": "Unknown"
        }
        
        vSizer = wx.FlexGridSizer(0, 2, 3, 10)
        vSizer.AddGrowableCol(1)
        
        if self.canEdit or self.torrent.get('description', ''):
            overviewColumnsOrder = ["Name", "Description", "Status", "Type", "Uploaded", "Filesize", "Health"]
        else:
            del overviewColumns['Description']
            overviewColumnsOrder = ["Name", "Status", "Type", "Uploaded", "Filesize", "Health"]
            
        if self.torrent.state:
            class tmp_object():
                def __init__(self, data, original_data):
                    self.data = data
                    self.original_data = original_data
            self.item = tmp_object(['',[0,0],[0,0],0,0],self.torrent)
            self.downloaded = ProgressPanel(panel, self.item, show_bar = True, show_status = False)
            self.downloaded.SetMinSize((-1, 25))
            sizer.Add(self.downloaded, 0, wx.EXPAND|wx.BOTTOM, 10)
        
        #hide Status element if we do not have a state for this torrent
        if not self.torrent.state:
            overviewColumnsOrder.remove("Status")
            
        self.status = None
        self.health = None
        for column in overviewColumnsOrder:
            if column == "Downloaded":
                _, value = self._add_row(panel, vSizer, column, overviewColumns[column], flags = 0)
            else:
                _, value = self._add_row(panel, vSizer, column, overviewColumns[column])
                    
            if column == "Status":
                self.status = value
            if column == "Health":
                self.health = value
                
        if self.showDetails:
            textCtrl = wx.TextCtrl(panel, -1, self.torrent.infohash_as_hex)
            textCtrl.SetEditable(False)
            self._add_row(panel, vSizer, "Infohash", textCtrl)
                
        if self.torrent.get('channel', False):
            channel = self.torrent.get('channel')
            ulfont = self.GetFont()
            ulfont.SetUnderlined(True)
            link = LinkText(panel, channel.name, fonts = [self.GetFont(), ulfont], colours = [self.GetForegroundColour(), wx.RED])
            link.SetBackgroundColour(panel.GetBackgroundColour())
            link.Bind(wx.EVT_LEFT_UP, lambda evt:  self.guiutility.showChannel(channel))
            self._add_row(panel, vSizer, 'Channel', link, flags = 0)                

        sizer.Add(vSizer, 1, wx.EXPAND)
            
        if self.canEdit:
            modifications = self.guiutility.channelsearch_manager.getTorrentModifications(self.torrent)
            for modification in modifications:
                if modification.name == 'swift-url':
                    value = wx.TextCtrl(panel, -1, modification.value, style = wx.TE_READONLY)
                    self._add_row(panel, vSizer, 'Swift URL', value)
        
        if self.canComment:
            sizer.Add(wx.StaticLine(panel, -1, style = wx.LI_HORIZONTAL), 0, wx.TOP|wx.BOTTOM|wx.EXPAND, 5)
            self.markingSizer = wx.BoxSizer(wx.HORIZONTAL)
            self.markicon = NativeIcon.getInstance().getBitmap(self, 'arrow', self.GetBackgroundColour(), state=0).ConvertToImage().Rotate90(False).ConvertToBitmap()
            self.markicon = wx.StaticBitmap(panel, -1, self.markicon)
            ulfont = self.GetFont()
            ulfont.SetUnderlined(True)
            self.marktoggle = LinkText(panel, 'Mark this torrent', fonts = [self.GetFont(), ulfont], colours = [self.GetForegroundColour(), wx.RED])
            self.marktoggle.SetBackgroundColour(panel.GetBackgroundColour())
            self.marktoggle.Bind(wx.EVT_LEFT_UP, self.OnMark)
            self.markingSizer.AddStretchSpacer()
            self.markingSizer.Add(self.markicon, 0, wx.CENTER|wx.RIGHT, 3)
            self.markingSizer.Add(self.marktoggle)
            sizer.Add(self.markingSizer, 0, wx.EXPAND)
            self.UpdateMarkings()
        
        self.UpdateHealth()
        panel.OnChange()
        
        self.Thaw()
    
    @warnWxThread
    def DownloadStarted(self):
        pass
    
    @warnWxThread
    def ShowPanel(self, newState = None):
        if getattr(self, 'notebook', False):
            if newState is None:
                newState  = self._GetState()
                
            if self.state != newState:
                self.state = newState
                
                if newState in [TorrentDetails.FINISHED, TorrentDetails.FINISHED_INACTIVE]:
                    self.torrent._progress = 1
                    if getattr(self, 'subtitleChoice', None):
                        self.subtitleChoice.Enable(True)
        else:
            #Additionally called by database event, thus we need to check if sizer exists(torrent is downloaded).
            wx.CallAfter(self.ShowPanel, newState)

    @warnWxThread
    def OnChange(self, event):
        page = event.GetSelection()
        
        title = self.notebook.GetPageText(page)
        if title.startswith('Comments'):
            self.commentList.Show()
            self.commentList.SetupScrolling()
            self.commentList.SetFocus()
            
        elif title.startswith('Modifications'):
            self.modificationList.Show()
            self.modificationList.SetupScrolling()
            self.modificationList.SetFocus()
            
        setattr(self.parent, self.__class__.__name__+'_tab', title)

        event.Skip()
    
    def OnCommentCreated(self, infohash):
        if self.torrent.infohash == infohash and self.isReady and self.canComment:
            manager = self.commentList.GetManager()
            manager.new_comment()
            
    def OnModificationCreated(self, channeltorrent_id):
        if self.isReady and self.canEdit:
            manager = self.modificationList.GetManager()
            manager.new_modification()
                        
    def GetChanged(self):
        newValues = {}
        for key, editable in self.isEditable.iteritems():
            newValue = editable.GetChanged()
            if newValue:
                newValues[key] = newValue
        return newValues

    def Saved(self):
        for editable in self.isEditable.values():
            editable.Saved()
    
    @warnWxThread 
    def OnDrag(self, event):
        if event.LeftIsDown():
            filename = self.guiutility.torrentsearch_manager.getCollectedFilename(self.torrent)
            if filename:
                tdo = wx.FileDataObject()
                tdo.AddFile(filename)
                
                tds = wx.DropSource(self)
                tds.SetData(tdo)
                tds.DoDragDrop(True)
    
    @warnWxThread
    def OnDoubleClick(self, event):
        selected = self.listCtrl.GetFirstSelected()
        playable_files = self.torrent.videofiles
            
        if selected != -1:
            selected_file = self.listCtrl.GetItemText(selected)
            if selected_file in playable_files:
                self.guiutility.library_manager.playTorrent(self.torrent, selected_file)

            elif self.torrent.progress == 1: #not playable, but are we complete?
                file = self._GetPath(selected_file)
                if os.path.isfile(file):
                    startfile(file)

    @warnWxThread                       
    def _GetPath(self, file = None):
        ds = self.torrent.ds
        if ds:
            destdirs = ds.get_download().get_dest_files()
            if file:
                for filenameintorrent, path in destdirs:
                    if filenameintorrent == file:
                        return path
                    
            return os.path.commonprefix([os.path.split(path)[0] for _,path in destdirs])
    
    @warnWxThread   
    def OnFilesSelected(self, event):
        pass
                    
    @warnWxThread
    def _ToggleSubtitleChoice(self, showChoice = None):
        if not showChoice:
            showChoice = not self.subtitleChoice.IsShown()
        
        self.subtitleChoice.Show(showChoice)
        self.requestingSub.Show(not showChoice)
        self.requestingSub.sizer.Layout()
    
    @warnWxThread
    def OnSubtitle(self, event):
        selected = self.subtitleChoice.GetSelection()
        nrItems =self.subtitleChoice.GetCount()
        
        if selected == 0 or selected == wx.NOT_FOUND:
            self.RemoveSubtitle()
            
        elif selected == nrItems - 1:
            self.OnSubtitleBrowse(event)
            
        else:
            if False and len(self.subtitleChoice.items[selected]) > 1:
                (lang, channelid, subtitleinfo) = self.subtitleChoice.items[selected]
                
                self.requestingSub.SetLabel('Requesting subtitle from peers...')
                self._ToggleSubtitleChoice(False)
                                
                def subTimeout():
                    if self.requestingSub.IsShown():
                        self.requestingSub.SetLabel('Request failed, no peer responded with subtitle')
                        wx.CallLater(3000, self._ToggleSubtitleChoice, True)
                wx.CallLater(10000, subTimeout)
            else:
                file = self._GetPath(self.subtitleChoice.items[selected][0])
                self.uelog.addEvent(message="Subtitles: user choose a internal subtitle", type = 2)
                self.SetSubtitle(file)
                
    @warnWxThread
    def OnRetrieveSubtitle(self, subtitleinfo):
        self.SetSubtitle(subtitleinfo.getPath())
        self.uelog.addEvent(message="Subtitles: user retrieved a subtitle", type = 2)
        self.requestingSub.SetLabel('Got subtitle from peers')
        wx.CallLater(3000, self._ToggleSubtitleChoice, True)
    
    @warnWxThread
    def OnSubtitleBrowse(self, event):
        wildcard = "*" + ";*".join(VLC_SUPPORTED_SUBTITLES)
        wildcard = "Subtitles (%s) | %s"%(wildcard, wildcard)
        
        dlg = wx.FileDialog(self, 'Please select your subtitle.', wildcard = wildcard, style = wx.FD_OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            self.uelog.addEvent(message="Subtitles: user choose his own subtitle", type = 2)
            
            file = dlg.GetPath()
            self.SetSubtitle(file)
        else:
            self.subtitleChoice.SetSelection(0)
            
        dlg.Destroy()
       
    def SetSubtitle(self, file):
        _, ext = os.path.splitext(file)
        if ext.lower() in VLC_SUPPORTED_SUBTITLES:
            #get largest playable file
            filename = self.torrent.largestvideofile
            filename = os.path.join(self._GetPath(), filename[0:filename.rfind(".")] + ext)
            shutil.copy(file, filename)
        
    def RemoveSubtitle(self, event = None):
        filename = self.torrent.largestvideofile
        if filename[0:filename.rfind(".")] + ".srt" not in self.torrent.files: #only actually remove this subtitle if it not in the .torrent
            filename = os.path.join(self._GetPath(), filename[0:filename.rfind(".")] + ".srt")
            if os.path.isfile(filename):
                os.remove(filename)
    
    @warnWxThread
    def OnClick(self, event):
        label = event.GetEventObject()
        if label.target == 'my_files':
            self.guiutility.frame.actlist.selectTab('my_files')
            self.guiutility.ShowPage('my_files', self.torrent.infohash)
            
        else:
            self.guiutility.showChannel(self.torrent.channel)
    
    @warnWxThread   
    def OnMark(self, event):
        menu = wx.Menu()
        itemid = wx.NewId()
        for mark in ['Good', 'High-Quality', 'Mid-Quality', 'Low-Quality', 'Corrupt', 'Fake', 'Spam']:
            itemid = wx.NewId()
            if self.myMark:
                menu.AppendRadioItem(itemid, mark)
                menu.Check(itemid, self.myMark == mark)
            else:
                menu.Append(itemid, mark)
            menu.Bind(wx.EVT_MENU, lambda x, selected = mark: self.doMark(self.torrent.channel, self.torrent.infohash, unicode(selected)), id = itemid)
                
        pos = wx.Point(self.markicon.GetPosition().x, self.marktoggle.GetPosition().y+self.marktoggle.GetSize().y)
        self.overview.PopupMenu(menu, pos)
        menu.Destroy()

    @warnWxThread
    def RefreshData(self, data):
        if self.isReady:
            rebuild = False
            
            if isinstance(self.torrent, Torrent):
                curTorrent = self.torrent
            else:
                curTorrent = self.torrent.torrent
            
            if hasattr(data[2], "bundle"):
                newTorrent = data[2]['bundle'][0]
            else:
                newTorrent = data[2]
            
            #remove cached swarminfo
            del self.torrent.swarminfo
            del self.torrent.status
            
            if not curTorrent.exactCopy(newTorrent):
                #replace current torrent
                curTorrent.swift_hash = newTorrent.swift_hash
                curTorrent.swift_torrent_hash = newTorrent.swift_torrent_hash
                curTorrent.torrent_file_name = newTorrent.torrent_file_name
                
                curTorrent.name = newTorrent.name
                curTorrent.length = newTorrent.length
                curTorrent.category_id = newTorrent.category_id
                curTorrent.status_id = newTorrent.status_id
                curTorrent.num_seeders = newTorrent.num_seeders
                curTorrent.num_leechers = newTorrent.num_leechers
            
                self._addOverview(self.overview, self.torrentSizer)
                if self.canEdit:
                    if not self.isEditable['name'].IsChanged():
                        self.isEditable['name'].SetValue(curTorrent.name)
                        
                    if not self.isEditable['description'].IsChanged():
                        self.isEditable['description'].SetValue(curTorrent.description or '')
            
            elif curTorrent.num_seeders != newTorrent.num_seeders or curTorrent.num_leechers != newTorrent.num_leechers:
                curTorrent.num_seeders = newTorrent.num_seeders
                curTorrent.num_leechers = newTorrent.num_leechers
                self.ShowHealth(False)
    
    @forceDBThread
    def UpdateHealth(self):
        try:
            if self.torrent.trackers and len(self.torrent.trackers) > 0:
                #touch swarminfo property        
                swarmInfo = self.torrent.swarminfo
        
                if swarmInfo:
                    diff = time() - self.torrent.last_check
                else:
                    diff = 1801
                
                if diff > 1800:
                    TorrentChecking.getInstance().addToQueue(self.torrent.infohash)
                    self.ShowHealth(True)
                else:
                    self.ShowHealth(False)
            else:
                self.ShowHealth(False)
        except wx.PyDeadObjectError:
            pass

    @forceWxThread
    def ShowHealth(self, updating):
        if getattr(self, 'health', False):
            updating = ', updating now' if updating else ''
            
            diff = time() - self.torrent.last_check
            if self.torrent.num_seeders < 0 and self.torrent.num_leechers < 0:
                if self.torrent.status == 'good':
                    self.health.SetLabel("Unknown, but found peers in the DHT")
                else:
                    self.health.SetLabel("Unknown"+updating)
            else:
                if diff < 5:
                    self.health.SetLabel("%s seeders, %s leechers (current)"%(self.torrent.num_seeders, self.torrent.num_leechers))
                else:
                    updated = self.guiutility.utility.eta_value(diff, 2)
                    if updated == '<unknown>':
                        self.health.SetLabel("%s seeders, %s leechers"%(self.torrent.num_seeders, self.torrent.num_leechers)+updating)
                    else:
                        self.health.SetLabel("%s seeders, %s leechers (updated %s ago%s)"%(self.torrent.num_seeders, self.torrent.num_leechers ,updated, updating))
        else:
            print >> sys.stderr, "No status element to show torrent_status"
    
    def OnMarkingCreated(self, channeltorrent_id):
        if self.torrent.get('channeltorrent_id', False) == channeltorrent_id:
            self.UpdateMarkings()
    
    def UpdateMarkings(self):
        if self.torrent.get('channeltorrent_id', False):
            startWorker(self.ShowMarkings, self.guiutility.channelsearch_manager.getTorrentMarkings, wargs= (self.torrent.channeltorrent_id, ),priority=GUI_PRI_DISPERSY)
     
    @warnWxThread
    def ShowMarkings(self, delayedResult):
        markings = delayedResult.get()
        if len(markings) > 0:
            msg = 'This torrent is marked as:'
            for marktype, nr, myMark in markings:
                msg += ' %s (%d)'%(marktype, nr)
                if myMark:
                    self.myMark = marktype
            
            #see if we are updating
            if not self.markings:
                self.markings = MaxBetterText(self.overview, unicode(msg), maxLines = 3)
                self.markingSizer.Insert(0, self.markings)
            else:
                self.markings.SetLabel(msg)
                
            self.torrentSizer.Layout()
           
    def OnRefresh(self, dslist, magnetlist):
        found = False
        
        for ds in dslist:
            if self.torrent.addDs(ds):
                found = True
   
        self.torrent.magnetstatus = magnetlist.get(self.torrent.infohash, None)
        
        if not found:
            self.torrent.clearDs()
            self._Refresh()
        else:
            self._Refresh()

    @warnWxThread
    def _Refresh(self, ds = None):
        if ds:
            self.torrent.addDs(ds)

        if self.torrent.magnetstatus:
            if self.timeouttimer:
                self.timeouttimer.Stop()
                self.timeouttimer = 0
            if self.messageGauge:
                if self.torrent.magnetState == 2:
                    self.messageGauge.Pulse()
                if self.torrent.magnetState == 3:
                    self.messageGauge.SetValue(self.torrent.magnetstatus[2])
        elif self.timeouttimer == 0 and not self.isReady:
            wx.CallLater(1000, self._timeout)
        

        if self.isReady:
            state = self._GetState()
            
            if state != self.state:
                self.ShowPanel(state)
    
            if state in [TorrentDetails.INCOMPLETE, TorrentDetails.INCOMPLETE_INACTIVE, TorrentDetails.VOD, TorrentDetails.FINISHED]:
                if getattr(self, 'downloaded', False):
                    self.downloaded.Update(torrent = self.torrent)
                else:                 
                    self._addOverview(self.overview, self.torrentSizer)
            
            if getattr(self, 'status', False):        
                self.UpdateStatus()
            
    def UpdateStatus(self):
        ds         = self.torrent.ds
        progress   = ds.get_progress() if ds else 0
        statusflag = ds.get_status() if ds else DLSTATUS_STOPPED
        finished   = progress == 1.0
        status     = None

        if self.torrent.magnetstatus:
            status = 'Torrent file is being downloaded from the DHT'
        elif statusflag == DLSTATUS_SEEDING:
            uls = ds.get_current_speed('up')*1024
            status = 'Seeding @ %s' % self.utility.speed_format_new(uls)
        elif finished:
            status = 'Completed'
        elif statusflag in [DLSTATUS_ALLOCATING_DISKSPACE, DLSTATUS_WAITING4HASHCHECK]:
            status = 'Waiting'
        elif statusflag == DLSTATUS_HASHCHECKING:
            status = 'Checking'
        elif statusflag == DLSTATUS_DOWNLOADING:
            dls = ds.get_current_speed('down')*1024
            status = 'Downloading @ %s' % self.utility.speed_format_new(dls)
        elif statusflag in [DLSTATUS_STOPPED, DLSTATUS_REPEXING]:
            status = 'Stopped'
            
        if status and not finished and self.torrent.progress and statusflag in [DLSTATUS_DOWNLOADING, DLSTATUS_STOPPED, DLSTATUS_REPEXING]:           
            status += " (%.1f%%)" % (self.torrent.progress*100)

        if status:
            self.status.SetLabel(status)
    
    def _GetState(self):
        active = vod = False
        
        progress = self.torrent.progress
        finished = progress == 1.0
        
        ds = self.torrent.ds        
        if ds:
            if finished: #finished download
                active = ds.get_status() == DLSTATUS_SEEDING

            else: #active download
                active = ds.get_status() not in [DLSTATUS_STOPPED, DLSTATUS_STOPPED_ON_ERROR]
                if ds.is_vod():
                    vod = True
        
        if finished:
            if active:
                state = TorrentDetails.FINISHED
            else:
                state = TorrentDetails.FINISHED_INACTIVE
                
        elif vod:
            state = TorrentDetails.VOD
            
        elif progress > 0 or active:
            if active:
                state = TorrentDetails.INCOMPLETE
            else:
                state = TorrentDetails.INCOMPLETE_INACTIVE
        else:
            state = TorrentDetails.INACTIVE
        return state
    
    def OnOverviewToggle(self, event):
        self.showDetails = not self.showDetails
        self._addOverview(self.overview, self.torrentSizer)
    
    @warnWxThread
    def Layout(self):
        returnValue = wx.Panel.Layout(self)
        
        if self.isReady:
            #force setupscrolling for scrollpages, if constructed while not shown this is required.
            for i in range(self.notebook.GetPageCount()):
                page = self.notebook.GetPage(i)
                page.Layout()
                
                if getattr(page, 'SetupScrolling', False):
                    page.SetupScrolling(scroll_x = False)
                    
        return returnValue

    @warnWxThread               
    def __del__(self):
        if DEBUG:
            print >> sys.stderr, "TorrentDetails: destroying", self.torrent['name']
        self.guiutility.library_manager.remove_download_state_callback(self.OnRefresh)
        
        if self.markWindow:
            self.markWindow.Show(False)
            self.markWindow.Destroy()

class LibraryDetails(TorrentDetails):
    @warnWxThread
    def __init__(self, parent, torrent):
        self.old_progress = -1
        TorrentDetails.__init__(self, parent, torrent)
        
        # Arno, 2012-07-17: Retrieving peerlist for the DownloadStates takes CPU
        # so only do it when needed for display.
        self.guiutility.library_manager.set_want_peers(True)
        
    def __del__(self):
        TorrentDetails.__del__(self)
        self.guiutility.library_manager.set_want_peers(False)
         
    @forceWxThread
    def _timeout(self):
        try:
            if not self.isReady:
                if DEBUG:
                    print >> sys.stderr, "TorrentDetails: timeout on loading", self.torrent.name
            
                self.Freeze()
                
                self.messagePanel.SetLabel("Failed loading torrent. Please click retry or wait to allow other peers to respond.\nAlternatively you could remove this torrent from your Downloads.")
                if self.messageGauge:
                    self.messageGauge.Show(False)
                if self.messageButton:
                    self.messageButton.Show(True)
                else:
                    self.messageButton = wx.Button(self, -1, "Retry")
                    self.messageButton.Bind(wx.EVT_BUTTON, lambda evt: self._doLoad())
                    self.vSizer.Insert(5, self.messageButton, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.TOP, 10)

                self.Layout()

                self.guiutility.frame.top_bg.SetButtonHandler(self.guiutility.frame.top_bg.delete_btn, self.guiutility.frame.top_bg.OnDelete, 'Delete this torrent.')
                        
                self.Thaw()
        except wx.PyDeadObjectError:
            pass
    
    @warnWxThread
    def _addTabs(self, ds, showTab = None):
        #add normal tabs
        TorrentDetails._addTabs(self, ds, None)
        
        #insert peers tab
        peersPanel = wx.Panel(self.notebook)
        peersPanel.SetBackgroundColour(DEFAULT_BACKGROUND)
        vSizer = wx.BoxSizer(wx.VERTICAL)
         
        self.peerList = SelectableListCtrl(peersPanel, tooltip = False)
        self.peerList.InsertColumn(0, 'IP-address')
        self.peerList.InsertColumn(1, 'Traffic', wx.LIST_FORMAT_RIGHT)
        self.peerList.InsertColumn(2, 'State', wx.LIST_FORMAT_RIGHT)
        self.peerList.InsertColumn(3, 'ID', wx.LIST_FORMAT_RIGHT)
        self.peerList.setResizeColumn(0)
        self.peerList.SetToolTipString("States:\nO\t\toptimistic unchoked\nUI\t\tgot interested\nUC\t\tupload chocked\nUQ\t\tgot request\nUBL\tsending data\nUE\t\tupload eligable\nDI\t\tsend interested\nDC\t\tdownload chocked\nS\t\tis snubbed\nL\t\tOutgoing connection\nR\t\tIncoming connection")
        vSizer.Add(self.peerList, 1, wx.EXPAND|wx.LEFT|wx.TOP|wx.BOTTOM, 10)
        
        finished = self.torrent.get('progress', 0) == 100 or (ds and ds.get_progress() == 1.0)
        if not finished:
            hSizer = wx.BoxSizer(wx.HORIZONTAL)
            self.availability = StaticText(peersPanel)
            self.pieces = StaticText(peersPanel)
            self.availability.sizer = hSizer
            
            self._add_row(peersPanel, hSizer, 'Availability', self.availability, spacer = 3)
            hSizer.AddSpacer((4,-1))
            self._add_row(peersPanel, hSizer, 'Pieces', self.pieces, spacer = 3)
            
            vSizer.Add(wx.StaticLine(peersPanel, -1, style = wx.LI_HORIZONTAL), 0, wx.EXPAND|wx.ALL, 3)
            vSizer.Add(hSizer, 0, wx.EXPAND)
        else:
            self.availability = None
            self.pieces = None

        peersPanel.SetSizer(vSizer)
        self.notebook.InsertPage(2, peersPanel, "Peers")
    
        if showTab:
            for i in range(self.notebook.GetPageCount()):
                if self.notebook.GetPageText(i) == showTab:
                    self.notebook.SetSelection(i)
                    break
        else:
            self.notebook.SetSelection(0)
                
    def OnChangeSelection(self, event):
        files = []
        for i in range(self.listCtrl.GetItemCount()):
            files.append(self.listCtrl.GetItem(i, 0).GetText())
        
        dlg = wx.MultiChoiceDialog(self, "Select which files you would like to download", "File selection", files)
        
        selected = []
        for i in range(self.listCtrl.GetItemCount()):
            if self.listCtrl.GetItem(i, 2).GetText() != "Excluded":
                selected.append(i)
        dlg.SetSelections(selected)
        
        if (dlg.ShowModal() == wx.ID_OK):
            newselections = dlg.GetSelections()
            selectedFiles = []
            for index in newselections:
                selectedFiles.append(files[index])
                
            self.guiutility.frame.modifySelection(self.torrent.ds.download, selectedFiles)
            def reset_selection():
                self.old_progress = -1
            wx.CallLater(1000, reset_selection())
            
        dlg.Destroy()    

    @warnWxThread
    def ShowPanel(self, newState = None):
        if newState and newState != self.state:
            self.state = newState
    
    @warnWxThread
    def _Refresh(self, ds = None):
        TorrentDetails._Refresh(self, ds)
        
        if self.isReady:
            #register callback for peerlist update
            self.peerList.Freeze()
            
            ds = self.torrent.ds
            index = 0
            if ds:
                peers = ds.get_peerlist()
                
                def downsort(a, b):
                    if a.get('downrate', 0) != b.get('downrate',0):
                        return a.get('downrate', 0) - b.get('downrate', 0)
                    return a.get('uprate', 0) - b.get('uprate', 0)
                peers.sort(downsort, reverse = True)
                
                for peer_dict in peers:
                    peer_name = peer_dict['ip'] + ':%d @ %d%%'%(peer_dict['port'], peer_dict.get('completed', 0)*100.0)
                    if index < self.peerList.GetItemCount():
                        self.peerList.SetStringItem(index, 0, peer_name)
                    else:
                        self.peerList.InsertStringItem(index, peer_name)
                    
                    traffic = ""
                    traffic += self.guiutility.utility.speed_format_new(peer_dict.get('downrate', 0)) + u"\u2193 "
                    traffic += self.guiutility.utility.speed_format_new(peer_dict.get('uprate', 0)) + u"\u2191"
                    self.peerList.SetStringItem(index, 1, traffic.strip())
                    
                    state = ""
                    if peer_dict.get('optimistic'):
                        state += "O,"
                    if peer_dict.get('uinterested'):
                        state += "UI,"
                    if peer_dict.get('uchoked'):
                        state += "UC,"
                    if peer_dict.get('uhasqueries'):
                        state += "UQ,"
                    if not peer_dict.get('uflushed'):
                        state += "UBL,"
                    if peer_dict.get('ueligable'):
                        state += "UE,"
                    if peer_dict.get('dinterested'):
                        state += "DI,"
                    if peer_dict.get('dchoked'):
                        state += "DC,"
                    if peer_dict.get('snubbed'):
                        state += "S,"
                    state += peer_dict.get('direction', '')
                    self.peerList.SetStringItem(index, 2, state)
                    
                    if 'extended_version' in peer_dict:
                        try:
                            self.peerList.SetStringItem(index, 3, peer_dict['extended_version'])
                        except:
                            try:
                                self.peerList.SetStringItem(index, 3, peer_dict['extended_version'].decode('utf-8','ignore'))
                            except:
                                print >> sys.stderr, "Could not format peer client version"
                    else:
                        self.peerList.SetStringItem(index, 3, '')
                    
                    index += 1
    
                if self.availability:
                    self.availability.SetLabel("%.2f"%ds.get_availability())
                    self.pieces.SetLabel("total %d, have %d"%ds.get_pieces_total_complete())
                    
                    self.availability.sizer.Layout()
    
                dsprogress = ds.get_progress()
                #Niels: 28-08-2012 rounding to prevent updating too many times
                dsprogress = long(dsprogress * 1000) / 1000.0
                if self.old_progress != dsprogress:
                    completion = {}
                    
                    useSimple = ds.get_download().get_def().get_def_type() == 'swift' or self.listCtrl.GetItemCount() > 100
                    if useSimple:
                        selected_files = ds.get_download().get_selected_files()
                        if selected_files:
                            for i in range(self.listCtrl.GetItemCount()):
                                file = self.listCtrl.GetItem(i, 0).GetText()
                                if file in selected_files:
                                    completion[file] = dsprogress
                        else:
                            for i in range(self.listCtrl.GetItemCount()):
                                completion[self.listCtrl.GetItem(i, 0).GetText()] =  dsprogress
                    else:
                        for file, progress in ds.get_files_completion():
                            completion[file] = progress
    
                    for i in range(self.listCtrl.GetItemCount()):
                        listfile = self.listCtrl.GetItem(i, 0).GetText()
                        
                        progress = completion.get(listfile, None)
                        if isinstance(progress, float) or isinstance(progress, int):
                            self.listCtrl.SetStringItem(i, 2, "%.2f%%"%(progress*100))
                        else:
                            self.listCtrl.SetStringItem(i, 2, 'Excluded')
                    
                    self.old_progress = dsprogress
                
            if index == 0:
                self.peerList.DeleteAllItems()
                self.peerList.InsertStringItem(index, "Not connected to any peers")
            else:
                while index < self.peerList.GetItemCount():
                    self.peerList.DeleteItem(index)
                    index += 1
            
            self.peerList.SetColumnWidth(1, wx.LIST_AUTOSIZE)
            self.peerList.SetColumnWidth(2, wx.LIST_AUTOSIZE)
            self.peerList.SetColumnWidth(3, wx.LIST_AUTOSIZE)
            self.peerList._doResize()
            self.peerList.Thaw()

class ChannelDetails(AbstractDetails):

    def __init__(self, parent, channel):
        GradientPanel.__init__(self, parent)
        self.Hide()

        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility
        self.uelog = UserEventLogDBHandler.getInstance()
        
        self.parent = parent
        self.isReady = False
        self.SetBackgroundColour(wx.Colour(246,246,246))

        self.vSizer = wx.BoxSizer(wx.VERTICAL)

        self.messageIcon = wx.StaticBitmap(self, -1, wx.ArtProvider.GetBitmap(wx.ART_INFORMATION))        
        self.messagePanel = TransparentText(self, -1, "Loading details, please wait.")
        self.messageGauge = None
        _set_font(self.messagePanel, size_increment = 2, fontweight = wx.FONTWEIGHT_NORMAL)
        
        for colour, height in [(SEPARATOR_GREY, 1), (FILTER_GREY, 25), (SEPARATOR_GREY, 1)]:
            panel = wx.Panel(self)
            panel.SetMinSize((-1,height))
            panel.SetBackgroundColour(colour)
            self.vSizer.Add(panel, 0, wx.EXPAND)
        
        self.vSizer.AddStretchSpacer()
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(self.messageIcon, 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 15)
        hSizer.Add(self.messagePanel, 0, wx.ALL, 3)
        self.vSizer.Add(hSizer, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_CENTER_HORIZONTAL)
        self.vSizer.AddStretchSpacer()

        self.SetSizer(self.vSizer)
        self.Layout()
        
        self.showChannel(channel)
        
        self.Show()

    @forceWxThread
    def showChannel(self, channel):
        try:
            if not self.isReady:
                self.state = -1
                self.channel = channel
                
                self.Freeze()
                self.messagePanel.Show(False)
                self.messageIcon.Show(False)
                if self.messageGauge: self.messageGauge.Show(False)
            
                self.notebook = SimpleNotebook(self, style = wx.NB_NOPAGETHEME, name = "ChannelDetailsNotebook")
                
                self.overview, self.overviewSizer = self._create_tab(self.notebook, 'Channel details', border = 10)
                self.overview.SetBackgroundColour(wx.WHITE)
                
                self._addOverview(self.overview, self.overviewSizer)

                self.vSizer.Clear(deleteWindows = True)
                self.vSizer.Add(self.notebook, 1, wx.EXPAND)
                self.notebook.SetSelection(0)
                        
                self.Thaw()
                self.isReady = True
                self.Layout()
            
        except wx.PyDeadObjectError:
            pass            
                
    @forceWxThread                
    def _addOverview(self, panel, sizer):
        sizer.Clear(deleteWindows = True)
        
        vSizer = wx.FlexGridSizer(0, 2, 3, 10)
        vSizer.AddGrowableCol(1)
        vSizer.AddGrowableRow(6)
            
        self._add_row(self.overview, vSizer, "Name", self.channel.name)
        if self.channel.description:
            self._add_row(self.overview, vSizer, "Description", self.channel.description)
        self._add_row(self.overview, vSizer, "Torrents", str(self.channel.nr_torrents))
        self._add_row(self.overview, vSizer, "Latest update", format_time(self.channel.modified))
        self._add_row(self.overview, vSizer, "Favorite votes", str(self.channel.nr_favorites))

        sizer.Add(vSizer, 1, wx.EXPAND)
        sizer.Layout()
        
    @warnWxThread
    def RefreshData(self, data):
        if self.isReady:
            if isinstance(self.channel, Channel):
                self.channel.name = data[2].name
                self.channel.description = data[2].description
                self.channel.nr_torrents = data[2].nr_torrents
                self.channel.modified = data[2].modified
                self.channel.nr_favorites = data[2].nr_favorites

            self._addOverview(self.overview, self.overviewSizer)
                

class PlaylistDetails(AbstractDetails):

    def __init__(self, parent, playlist):
        GradientPanel.__init__(self, parent)
        self.Hide()

        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility
        self.uelog = UserEventLogDBHandler.getInstance()

        self.parent = parent
        self.isReady = False
        self.SetBackgroundColour(wx.Colour(246,246,246))

        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        self.messageIcon = wx.StaticBitmap(self, -1, wx.ArtProvider.GetBitmap(wx.ART_INFORMATION))
        self.messagePanel = TransparentText(self, -1, "Loading details, please wait.")
        self.messageGauge = None
        _set_font(self.messagePanel, size_increment = 2, fontweight = wx.FONTWEIGHT_NORMAL)

        for colour, height in [(SEPARATOR_GREY, 1), (FILTER_GREY, 25), (SEPARATOR_GREY, 1)]:
            panel = wx.Panel(self)
            panel.SetMinSize((-1,height))
            panel.SetBackgroundColour(colour)
            self.vSizer.Add(panel, 0, wx.EXPAND)
        
        self.vSizer.AddStretchSpacer()
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(self.messageIcon, 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 15)
        hSizer.Add(self.messagePanel, 0, wx.ALL, 3)
        self.vSizer.Add(hSizer, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_CENTER_HORIZONTAL)
        self.vSizer.AddStretchSpacer()
        
        self.SetSizer(self.vSizer)
        self.Layout()
        
        self.showPlaylist(playlist)
        
        self.Show()

    @forceWxThread
    def showPlaylist(self, playlist):
        try:
            if not self.isReady:
                self.state = -1
                self.playlist = playlist
                
                self.Freeze()
                self.messagePanel.Show(False)
                self.messageIcon.Show(False)
                if self.messageGauge: self.messageGauge.Show(False)
            
                self.notebook = SimpleNotebook(self, style = wx.NB_NOPAGETHEME, name = "ChannelDetailsNotebook")
                    
                self.overview, self.overviewSizer = self._create_tab(self.notebook, 'Playlist details', border = 10)
                self.overview.SetBackgroundColour(wx.WHITE)
                
                self._addOverview(self.overview, self.overviewSizer)

                self.vSizer.Clear(deleteWindows = True)
                self.vSizer.Add(self.notebook, 1, wx.EXPAND)
                self.notebook.SetSelection(0)
                        
                self.Thaw()
                self.isReady = True
                self.Layout()
            
        except wx.PyDeadObjectError:
            pass
        
    @forceWxThread                
    def _addOverview(self, panel, sizer):
        sizer.Clear(deleteWindows = True)
        
        vSizer = wx.FlexGridSizer(0, 2, 3, 10)
        vSizer.AddGrowableCol(1)
        vSizer.AddGrowableRow(6)
            
        self._add_row(self.overview, vSizer, "Name", self.playlist.name)
        if self.playlist.description:
            self._add_row(self.overview, vSizer, "Description", self.playlist.description)
        self._add_row(self.overview, vSizer, "Torrents", str(self.playlist.nr_torrents))

        sizer.Add(vSizer, 1, wx.EXPAND)
        sizer.Layout()
        
    @warnWxThread
    def RefreshData(self, data):
        if self.isReady:
            if isinstance(self.playlist, Playlist):
                self.playlist.name = data[2].name
                self.playlist.description = data[2].description
                self.playlist.nr_torrents = data[2].nr_torrents

            self._addOverview(self.overview, self.overviewSizer)
        

class AbstractInfoPanel(GradientPanel):

    def __init__(self, parent):
        GradientPanel.__init__(self, parent)
        self.Hide()
        
        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility
        self.uelog = UserEventLogDBHandler.getInstance()
        
        self.parent = parent
        self.isReady = False
        self.SetBackgroundColour(wx.Colour(246,246,246))
        
        self.topSizer = wx.BoxSizer(wx.VERTICAL)
        self.mainSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.dialogSizer = wx.BoxSizer(wx.VERTICAL)
        self.messageSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.textSizer = wx.BoxSizer(wx.VERTICAL)
        self.buttonSizer = wx.BoxSizer(wx.HORIZONTAL)

        self.mainSizer.AddStretchSpacer()
        self.mainSizer.Add(self.dialogSizer, 0, wx.EXPAND)
        self.mainSizer.AddStretchSpacer()
        
        self.dialogSizer.AddStretchSpacer()
        self.dialogSizer.Add(self.messageSizer, 0, wx.EXPAND)
        self.dialogSizer.Add(self.buttonSizer, 0, wx.EXPAND|wx.TOP, 15)  
        self.dialogSizer.AddStretchSpacer()
        
        self.messageSizer.Add(self.textSizer, 0, 0)

        self.buttonSizer.AddStretchSpacer()
        
        for colour, height in [(SEPARATOR_GREY, 1), (FILTER_GREY, 25), (SEPARATOR_GREY, 1)]:
            panel = wx.Panel(self)
            panel.SetMinSize((-1,height))
            panel.SetBackgroundColour(colour)
            self.topSizer.Add(panel, 0, wx.EXPAND)
        self.topSizer.Add(self.mainSizer, 1, wx.EXPAND)    
        self.SetSizer(self.topSizer)
        self.Layout()
        
    def AddMessage(self, message, colour = wx.Colour(50,50,50), bold = False):
        if not self.textSizer.GetChildren():
            self.messageSizer.Insert(0, wx.StaticBitmap(self, -1, wx.ArtProvider.GetBitmap(wx.ART_INFORMATION)), 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 15)
        
        message = TransparentText(self, -1, message)
        _set_font(message, size_increment = 2, fontcolour = colour, fontweight = wx.FONTWEIGHT_NORMAL if not bold else wx.FONTWEIGHT_BOLD)
        self.textSizer.Add(message, 0, wx.ALIGN_CENTER_VERTICAL)

        self.Layout()

    def AddButton(self, label, handler, icon = None):
        if handler == None or label == None:
            return

        button = ProgressButton(self, -1, label)
        button.Bind(wx.EVT_LEFT_UP, handler)
        if icon:
            button.SetIcon(icon)
        self.buttonSizer.Add(button, 0, wx.LEFT, 15)
        self.Layout()

class SearchInfoPanel(AbstractInfoPanel):

    def Set(self, num_items):
        self.AddMessage('Channels may contain torrents associated with your search.')
        if num_items > 0:
            self.AddMessage('Please click on a channel or a torrent for more details.')
        self.Show(True)

class ChannelInfoPanel(AbstractInfoPanel):

    def Set(self, num_items, is_favourite):
        if is_favourite:
            self.AddMessage('This is a list of your favorite channels.')
            if num_items > 0:
                self.AddMessage('Please select a channel for more details, or visit it to access its content.')
        else:
            self.AddMessage('A channel is a collection of torrents made by users to share their favorite torrents.')
            if num_items > 0:
                self.AddMessage('Please click on a channel for more details.')
        self.Show(True)


class LibraryInfoPanel(AbstractInfoPanel):

    def Set(self, num_items):
        if num_items > 0:
            self.AddMessage('Please select a torrent for more details.')
        self.Show(True)
        

class PlaylistInfoPanel(AbstractInfoPanel):

    def Set(self, num_items, is_favourite):
        if is_favourite == True:
            self.AddMessage('You are looking at the full content of this playlist.')
        elif is_favourite == False:
            self.AddMessage('You are looking at a preview of this playlist. To see more of it, mark the channel as favorite.')
        if num_items > 0:
            self.AddMessage('Please click on a torrent for more details.')
        self.Show(True)
        

class SelectedchannelInfoPanel(AbstractInfoPanel):
        
    def Set(self, num_items, vote, channelstate, iamModerator):
        explicit_vote = vote != 0
        preview = not explicit_vote and not iamModerator
        open2edit = channelstate == ChannelCommunity.CHANNEL_CLOSED and iamModerator
        allow2edit = vote == 2 and channelstate == ChannelCommunity.CHANNEL_OPEN
        
        if preview:
            self.AddMessage("You are looking at a preview of this channel. If you want to see more of it, \"Mark it as Favorite\".")

        else:
            msg1 = ""
            msg2 = ""
            
            if iamModerator:
                msg1 = "You are looking at the contents of your channel."         
            elif vote == -1:
                msg1 = "You have marked this Channel as Spam."
            elif vote == 2:
                msg1 = 'You are looking at the full content of one of your favorite channels.'
            
            if open2edit:
                msg1 = "You can now enable community-features for this Channel."
                msg2 = "Allowing other users to comment, modify and improve meta-data will increase the overall community feel. Try it now.\nEdit the channel settings to get started."

            elif allow2edit:
                msg1 = "This is an open community channel. You can modify it, comment on it and add new content."
                msg2 = "You can edit this channel" if not msg2 else msg2

            if msg1:
                self.AddMessage(msg1)
            if msg2:
                self.AddMessage(msg2)

        if num_items > 0:
            self.AddMessage('Please click on a torrent or a playlist for more details.')
        self.Show(True)
        

class ProgressPanel(wx.BoxSizer):
    #eta style
    ETA_DEFAULT = 1
    ETA_EXTENDED = 2
    
    def __init__(self, parent, item, style = ETA_DEFAULT, show_bar = True, show_status = True):
        wx.BoxSizer.__init__(self, wx.VERTICAL)
        self.item = item
        self.style = style
        self.show_bar = show_bar
        self.show_status = show_status
        guiutility = GUIUtility.getInstance()
        self.utility = guiutility.utility
        
        #self.AddStretchSpacer()        
        if show_bar:
            self.pb = ProgressBar(parent, colours =  ["#ffffff", DOWNLOADING_COLOUR, SEEDING_COLOUR])
            self.pb.SetMaxSize((-1, -1))
            self.Add(self.pb, 1, wx.EXPAND)
        if show_status:
            self.status = StaticText(parent)
            self.Add(self.status, 0, wx.EXPAND)
        
        #self.AddStretchSpacer()
        self.Update()
        
    def Update(self, ds = None, torrent = None):
        #return_val, 0 == inactive, 1 == incomplete, 2 == complete/seeding
        return_val = 0
        
        if ds == None:
            if torrent:
                ds = torrent.ds
            else:
                ds = self.item.original_data.get('ds', None)
        
        if ds != None:
            progress = ds.get_progress()
            size = ds.get_length()
            
            seeds, peers = ds.get_num_seeds_peers()
            
            dls = ds.get_current_speed('down')*1024
            uls = ds.get_current_speed('up')*1024
            
            eta = ds.get_eta()
            status = ds.get_status()
            
        else:
            progress = self.item.original_data.get('progress')
            if progress == None:
                progress = 0
            size = self.item.original_data.get('length', False)
            
            seeds = peers = None
            dls = uls = 0
            
            eta = ''
            status = DLSTATUS_STOPPED
        
        if seeds == None:
            seeds = 0
        if peers == None:
            peers = 0
            
        progress = max(0, min(1, progress)) #progress has to be between 0 and 1
        
        self.item.data[1] = status
        self.item.data[2] = [seeds, peers]
        self.item.data[3] = dls
        self.item.data[4] = uls
            
        finished = progress == 1.0
        if finished:
            eta = "Completed"
            if status == DLSTATUS_SEEDING:
                eta += ", seeding"
                return_val = 2
            elif status == DLSTATUS_REPEXING:
                eta += ", repexing"
            elif status == DLSTATUS_WAITING4HASHCHECK:
                eta += ', waiting for hashcheck'
            elif status == DLSTATUS_HASHCHECKING:
                eta += ', checking'
            else:
                eta += ", inactive"
        else:
            if status == DLSTATUS_ALLOCATING_DISKSPACE:
                eta = 'Allocating diskspace'
                
            elif status == DLSTATUS_WAITING4HASHCHECK:
                eta = 'Waiting for hashcheck'
                
            elif status == DLSTATUS_HASHCHECKING:
                eta = 'Checking'
                if progress > 0:
                    eta += "(%0.1f%%)"%(progress*100)
            
            elif status == DLSTATUS_DOWNLOADING:
                sizestr = ''
                if size:
                    size_progress = size*progress
                    
                    def format_size(bytes):
                        if bytes > 1073741824:
                            return self.utility.size_format(bytes, 1)
                        return self.utility.size_format(bytes, 0)
                    sizestr = '%s/%s (%0.1f%%)'%(format_size(size_progress), format_size(size), progress*100) 
                    
                eta = self.utility.eta_value(eta, truncate=2)
                if eta == '' or eta.find('unknown') != -1:
                    eta = sizestr
                    
                    
                    if self.show_status and self.style == ProgressPanel.ETA_DEFAULT and dls == 0 and uls == 0 and ds:
                        if ds.get_num_con_initiated() > 0:
                            eta += ' - connecting'
                            
                            nrdots = (self.status.GetLabel()[-3:].count('.')+1) % 4
                            eta += '.'*nrdots
                        
                else:
                    eta = sizestr + ' - ' + eta
                
                return_val = 1
            else:
                eta = 'Incomplete, inactive (%0.1f%%)'%(progress*100)
            
        if self.style == ProgressPanel.ETA_EXTENDED:
            if status == DLSTATUS_SEEDING:
                upSpeed = " @ " +self.utility.speed_format_new(uls)
                eta += upSpeed
            elif status == DLSTATUS_DOWNLOADING:
                dlSpeed = " @ " +self.utility.speed_format_new(dls)
                eta += dlSpeed
        
        #Update eta
        if self.show_status and self.status.GetLabel() != eta:
            self.status.SetLabel(eta)
            self.status.Refresh()
            
        if self.show_bar:
            if not status in [DLSTATUS_WAITING4HASHCHECK, DLSTATUS_ALLOCATING_DISKSPACE, DLSTATUS_HASHCHECKING, DLSTATUS_STOPPED]:
                havedigest = ds.get_pieces_complete()
            else:
                havedigest = None
            
            #Update graph
            if finished:
                self.pb.reset(colour=2) # Show as complete
            elif havedigest:
                self.pb.set_pieces(havedigest)
            elif progress > 0:
                self.pb.setNormalPercentage(progress) # Show as having some
            else:
                self.pb.reset(colour=0) # Show as having none
            self.pb.Refresh()
        
        return return_val
    
class StringProgressPanel(wx.BoxSizer):
    def __init__(self, parent, torrent):
        wx.BoxSizer.__init__(self, wx.HORIZONTAL)
        self.parent = parent
        self.torrent = torrent
        
        guiutility = GUIUtility.getInstance()
        self.utility = guiutility.utility
        
        self.text = StaticText(parent)
        self.Add(self.text, 1, wx.EXPAND)
    
    def Update(self, ds = None):
        if ds == None:
            ds = self.torrent.ds
        
        if ds != None:
            progress = ds.get_progress()
            size = ds.get_length()
            
            seeds, peers = ds.get_num_seeds_peers()
            
            dls = ds.get_current_speed('down')*1024
            uls = ds.get_current_speed('up')*1024
            
            eta = ds.get_eta()
            
            if progress == 1.0:
                self.text.SetLabel("Currently uploading to %d peers @ %s."%(peers, self.utility.speed_format_new(uls)))
            else:
                remaining = size - (size * progress)
                eta = self.utility.eta_value(eta, truncate=2)
                if eta == '' or eta.find('unknown') != -1:
                    self.text.SetLabel("Currently downloading @ %s, %s still remaining."%(self.utility.speed_format_new(dls), format_size(remaining)))
                else:
                    self.text.SetLabel("Currently downloading @ %s, %s still remaining. Expected to finish in %s."%(self.utility.speed_format_new(dls), format_size(remaining), eta))

class MyChannelDetails(wx.Panel):
    def __init__(self, parent, torrent, channel_id):
        self.parent = parent
        self.torrent = torrent
        self.channel_id = channel_id
        
        self.uelog = UserEventLogDBHandler.getInstance()
        self.guiutility = GUIUtility.getInstance()

        wx.Panel.__init__(self, parent)
        
        self.borderSizer = wx.BoxSizer()
        self.SetSizer(self.borderSizer)
        
        self.SetBackgroundColour(LIST_DESELECTED)
        self.guiutility.torrentsearch_manager.loadTorrent(self.torrent, callback = self.showTorrent)
    
    @forceWxThread
    def showTorrent(self, torrent):
        notebook = SimpleNotebook(self, style = wx.NB_NOPAGETHEME)
        listCtrl = BetterListCtrl(notebook)
        listCtrl.InsertColumn(0, 'Name')
        listCtrl.InsertColumn(1, 'Size', wx.LIST_FORMAT_RIGHT)
            
        self.il = wx.ImageList(16,16)
        play_img = self.il.Add(wx.Bitmap(os.path.join(self.guiutility.vwxGUI_path, 'images', 'library_play.png'), wx.BITMAP_TYPE_ANY))
        file_img = self.il.Add(wx.ArtProvider.GetBitmap(wx.ART_NORMAL_FILE, size = (16,16)))
        listCtrl.SetImageList(self.il, wx.IMAGE_LIST_SMALL)
            
        for filename, size in torrent.files:
            try:
                pos = listCtrl.InsertStringItem(sys.maxint, filename)
            except:
                try:
                    pos = listCtrl.InsertStringItem(sys.maxint, filename.decode('utf-8','ignore'))
                except:
                    print >> sys.stderr, "Could not format filename", torrent.name
            listCtrl.SetItemData(pos, pos)
            size = self.guiutility.utility.size_format(size)
            listCtrl.SetStringItem(pos, 1, size)
            
            if filename in torrent.videofiles:
                listCtrl.SetItemColumnImage(pos, 0, play_img)
            else:
                listCtrl.SetItemColumnImage(pos, 0, file_img)
            
        listCtrl.setResizeColumn(0)
        listCtrl.SetMinSize((1,-1))
        listCtrl.SetColumnWidth(1, wx.LIST_AUTOSIZE) #autosize only works after adding rows
        notebook.AddPage(listCtrl, "Files")
        
        if self.subsupport._registered and torrent.isPlayable():
            self.subtitles = wx.Panel(notebook)
            self.vSizer = wx.BoxSizer(wx.VERTICAL)
            self.subtitles.SetSizer(self.vSizer)
            notebook.AddPage(self.subtitles, "Subtitles")
            self.AddSubs()
        
        self.borderSizer.Add(notebook, 1, wx.EXPAND)
        self.Layout()
    
    def AddSubs(self):
        self.vSizer.ShowItems(False)
        self.vSizer.DeleteWindows()
        self.vSizer.Clear()
        
        currentsubs = self.subsupport.getSubtitleInfos(self.my_permid, self.torrent['infohash'])
        if len(currentsubs) > 0:
            header = StaticText(self.subtitles, -1, "Current Subtitles")
            font = header.GetFont()
            font.SetWeight(wx.FONTWEIGHT_BOLD)
            header.SetFont(font)
            self.vSizer.Add(header, 0, wx.BOTTOM, 3)
            
            curlang = [self.supportedLang[langkey] for langkey in currentsubs.keys()]
            curlang.sort()
            for lang in curlang:
                self.vSizer.Add(StaticText(self.subtitles, -1, lang), 0, wx.LEFT, 6)
        else:
            header = StaticText(self.subtitles, -1, "No subtitles added to this .torrent.")
            font = header.GetFont()
            font.SetWeight(wx.FONTWEIGHT_BOLD)
            header.SetFont(font)
            self.vSizer.Add(header)
        
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(StaticText(self.subtitles, -1, "Add a subtitle to this .torrent"), 0, wx.ALIGN_CENTER_VERTICAL)
        hSizer.AddStretchSpacer()
        button = wx.Button(self.subtitles, -1, "Browse")
        button.Bind(wx.EVT_BUTTON, self.OnClick)
        hSizer.Add(button)
        self.vSizer.Add(hSizer, 0, wx.EXPAND)
        self.vSizer.Layout()
    
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
                        self.uelog.addEvent(message="MyChannel: new subtitle added", type = 2)
                        self.AddSubs()
                        
                        break
        dlg.Destroy()
        
class MyChannelPlaylist(AbstractDetails):
    def __init__(self, parent, on_manage, can_edit = False, on_save = None, on_remove = None, playlist = {}):
        self.can_edit = can_edit
        self.on_manage = on_manage
        self.on_save = on_save
        self.on_remove = on_remove
        self.playlist = playlist
        self.torrent_ids = []
        
        wx.Panel.__init__(self, parent)
        self.SetBackgroundColour(wx.WHITE)
        vSizer = wx.BoxSizer(wx.VERTICAL)
        
        gridSizer = wx.FlexGridSizer(0, 2, 3, 10)
        gridSizer.AddGrowableCol(1)
        gridSizer.AddGrowableRow(1)
        
        
        if can_edit:
            self.name = wx.TextCtrl(self, value = playlist.get('name', ''))
            self.name.SetMaxLength(40)
            
            self.description = wx.TextCtrl(self, value = playlist.get('description',''), style = wx.TE_MULTILINE)
            self.description.SetMaxLength(2000)
        else:
            self.name = StaticText(self, -1, playlist.get('name', ''))
            self.description = StaticText(self, -1, playlist.get('description',''))
            
            self.name.SetMinSize((1, -1))
            self.description.SetMinSize((1, -1))
        
        self._add_row(self, gridSizer, 'Name', self.name)
        self._add_row(self, gridSizer, 'Description', self.description)
        vSizer.Add(gridSizer, 1, wx.EXPAND|wx.ALL, 3)
        
        manage = wx.Button(self, -1, 'Manage Torrents')
        manage.Bind(wx.EVT_BUTTON, self.OnManage)
        
        if can_edit and playlist.get('id', False):
            hSizer = wx.BoxSizer(wx.HORIZONTAL)
            save = wx.Button(self, -1, 'Save Playlist')
            save.Bind(wx.EVT_BUTTON, self.OnSave)
            
            delete = wx.Button(self, -1, 'Remove Playlist')
            delete.Bind(wx.EVT_BUTTON, self.OnRemove)
            
            hSizer.Add(save, wx.RIGHT, 3)
            hSizer.Add(delete, wx.RIGHT, 3)
            hSizer.Add(manage)
            
            vSizer.Add(hSizer, 0, wx.ALIGN_RIGHT|wx.ALL, 3)
        else:
            vSizer.Add(manage, 0, wx.ALIGN_RIGHT|wx.ALL, 3)
        
        self.SetSizer(vSizer)
    
    def OnManage(self, event):
        self.torrent_ids = self.on_manage(self.playlist)
        
    def OnSave(self, event):
        self.on_save(self.playlist.get('id'), self)
    
    def OnRemove(self, event):
        self.on_remove(self.playlist.get('id'), self)
        
    def GetInfo(self):
        name = self.name.GetValue()
        description = self.description.GetValue()
        return name, description, self.torrent_ids 

    def IsChanged(self):
        if self.can_edit:
            name = self.name.GetValue()
            description = self.description.GetValue()
            
            return name != self.playlist.get('name', '') or description != self.playlist.get('description','')
        return False


class ChannelsExpandedPanel(wx.Panel):
    def __init__(self, parent, size = wx.DefaultSize):
        wx.Panel.__init__(self, parent, size = size, style = wx.NO_BORDER)
        self.guiutility = GUIUtility.getInstance()
        self.fg_colour  = self.GetForegroundColour()
        self.manager    = self.guiutility.frame.channellist.GetManager()
        self.channel_category = None
        self.channel_or_playlist = None
        self.AddComponents()
        self.SetBackgroundColour(parent.GetBackgroundColour())
        self.Bind(wx.EVT_SHOW, self.OnShow)
        wx.CallAfter(self.AddCurrentChannelLink)
                
    def AddComponents(self):        
        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)                        
        self.hSizer.Add(self.vSizer, 1, wx.EXPAND|wx.LEFT, 20)
        
        self.links = {}        
        for name in ['All','Favorites','My Channel']:
            link = LinkStaticText(self, name, icon = None, font_colour = TRIBLER_RED if name == 'All' else self.fg_colour)
            link.Bind(wx.EVT_LEFT_UP, self.OnCategory)
            self.links[name] = link
            self.vSizer.Add(link, 0, wx.EXPAND|wx.ALIGN_CENTER_VERTICAL)
            
        self.SetSizer(self.hSizer)
        self.Layout()
        
    def OnShow(self, event):
        if self.IsShownOnScreen():
            if self.channel_or_playlist:
                if isinstance(self.channel_or_playlist, Channel):
                    self.guiutility.showChannel(self.channel_or_playlist)
                elif isinstance(self.channel_or_playlist, Playlist):
                    self.guiutility.showPlaylist(self.channel_or_playlist)
            elif self.GetCategory() == 'My Channel':
                self.guiutility.ShowPage('mychannel')

    def SetBackgroundColour(self, colour):
        if self.GetBackgroundColour() != colour:
            wx.Panel.SetBackgroundColour(self, colour)
            for link in self.links.values():
                link.SetBackgroundColour(colour)
                                
    def SetTextColour(self, colour):
        for link in self.links.values():
            link.SetForegroundColour(colour)
            
    def SetTextHighlight(self):
        self.SetTextColour(self.fg_colour)
        if not self.channel_or_playlist:
            link = self.links[self.GetCategory()]
            link.SetForegroundColour(TRIBLER_RED)
        elif isinstance(self.channel_or_playlist, Playlist) and self.links.has_key('playlist'):
            self.links['playlist'].SetForegroundColour(TRIBLER_RED)          
        elif isinstance(self.channel_or_playlist, Channel) and self.links.has_key('channel'):
            self.links['channel'].SetForegroundColour(TRIBLER_RED)

    def AddCurrentPlaylistLink(self):
        playlist = self.guiutility.frame.playlist.playlist
        self.AddLink(playlist)

    def AddCurrentChannelLink(self):
        channel = self.guiutility.frame.selectedchannellist.channel
        self.AddLink(channel)

    def AddLink(self, channel_or_playlist):
        if channel_or_playlist:
    
            def DetermineText(text, maxWidth):
                for i in xrange(len(text), 0, -1):
                    newText = text[0:i]
                    if i != len(text):
                        newText += ".."
                    width, _ = self.GetTextExtent(newText)
                    if width <= maxWidth:
                        return newText
                    
            def CreateLinkStaticText():
                link = LinkStaticText(self, '', icon = None, font_colour = self.fg_colour)
                link_icon = NativeIcon.getInstance().getBitmap(self, 'arrow', self.GetBackgroundColour(), state=0)
                link_icon = link_icon.ConvertToImage().Rotate90(False).ConvertToBitmap()
                link_icon = wx.StaticBitmap(self, -1, link_icon)
                link.Insert(0, link_icon, 0, wx.CENTER|wx.RIGHT, 3)
                return link

            if not self.links.get('channel', None):
                self.links['channel'] = CreateLinkStaticText()
            else:
                self.vSizer.Detach(self.links['channel'])
            if not self.links.get('playlist', None):
                self.links['playlist'] = CreateLinkStaticText()
            else:
                self.vSizer.Detach(self.links['playlist'])
                
            channel = channel_or_playlist if isinstance(channel_or_playlist, Channel) else channel_or_playlist.channel
            self.links['channel'].Bind(wx.EVT_LEFT_UP, lambda evt: self.OnHistory(evt, channel))
            self.links['channel'].SetLabel(DetermineText(channel.name, self.GetSize()[0]-self.links['channel'].text.GetPosition()[0]))
            self.vSizer.Insert(2 if channel.isFavorite() else 1, self.links['channel'], 0, wx.EXPAND|wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 2)
            
            if isinstance(channel_or_playlist, Playlist):
                self.links['playlist'].ShowItems(True)
                self.links['playlist'].Bind(wx.EVT_LEFT_UP, lambda evt: self.OnHistory(evt, channel_or_playlist))
                self.links['playlist'].SetLabel(DetermineText(channel_or_playlist.name, self.GetSize()[0]-self.links['playlist'].text.GetPosition()[0]))
                self.vSizer.Insert(3 if channel_or_playlist.channel.isFavorite() else 2, self.links['playlist'], 0, wx.EXPAND|wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 10)
            else:
                self.links['playlist'].ShowItems(False)

            self.vSizer.Layout()
            self.channel_or_playlist = channel_or_playlist
            self.SetTextHighlight()
            self.guiutility.frame.actlist.Layout()

    def GetCategory(self):
        cat = self.channel_category
        if not cat and self.manager.category:
            if self.manager.category in ["Popular","New","Updated"]:
                cat = "All"
            else:
                cat = self.manager.category
        if not cat:
            cat = "All"
        return cat

    def OnCategory(self, event):
        control = event.GetEventObject()
        label = control.GetLabel()
        if label == 'My Channel':
            self.guiutility.ShowPage('mychannel')
        else:
            self.guiutility.showChannelCategory(label)
            self.guiutility.frame.channellist.header.ShowChannelTypeFilter(label != 'Favorites')    
            self.guiutility.frame.channellist.ResetBottomWindow()
        self.channel_category = label    
        self.channel_or_playlist = None
        self.SetTextHighlight()
        
    def OnHistory(self, event, channel_or_playlist):
        if isinstance(channel_or_playlist, Channel):
            self.guiutility.showChannel(channel_or_playlist)
        elif isinstance(channel_or_playlist, Playlist):
            self.guiutility.showPlaylist(channel_or_playlist)
        self.channel_or_playlist = channel_or_playlist
        self.SetTextHighlight()
