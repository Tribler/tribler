# Written by Niels Zeilemaker
import wx
import sys
import os
import time
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
from Tribler.Core.BuddyCast.buddycast import BuddyCastFactory
from Tribler.Core.Subtitles.SubtitlesSupport import SubtitlesSupport
from Tribler.Main.vwxGUI.tribler_topButton import LinkStaticText, BetterListCtrl, EditText, SelectableListCtrl, _set_font, BetterText as StaticText,\
    MaxBetterText, NotebookPanel

from list_header import ListHeader
from list_body import ListBody
from __init__ import *
from Tribler.Core.simpledefs import DLSTATUS_STOPPED, DLSTATUS_STOPPED_ON_ERROR
from Tribler.Main.Utility.GuiDBHandler import startWorker, GUI_PRI_DISPERSY
from Tribler.Main.Utility.GuiDBTuples import RemoteChannel, Torrent,\
    LibraryTorrent, ChannelTorrent, CollectedTorrent
from Tribler.community.channel.community import ChannelCommunity
from wx.richtext import RichTextCtrl

VLC_SUPPORTED_SUBTITLES = ['.cdg', '.idx', '.srt', '.sub', '.utf', '.ass', '.ssa', '.aqt', '.jss', '.psb', '.rt', '.smi']
DEBUG = False

class AbstractDetails(wx.Panel):
    
    @warnWxThread
    def _create_tab(self, notebook, tabname, header = None, spacer = 3):
        panel = wx.lib.scrolledpanel.ScrolledPanel(notebook)
        def OnChange():
            panel.Layout()
            panel.SetupScrolling(rate_y = 5)
        panel.OnChange = OnChange
        
        themeColour = notebook.GetThemeBackgroundColour()
        if themeColour.IsOk():
            panel.SetBackgroundColour(themeColour)
        
        notebook.AddPage(panel, tabname)
        
        vSizer = wx.BoxSizer(wx.VERTICAL)
        panel.SetSizer(vSizer)
        
        if header:
            header = self._add_header(panel, vSizer, header, spacer)
            panel.SetLabel = header.SetLabel
        
        return panel, vSizer

    @warnWxThread
    def _add_header(self, panel, sizer, header, spacer = 3):
        header = wx.StaticText(panel, -1, header)
        _set_font(header, fontweight = wx.FONTWEIGHT_BOLD)

        sizer.Add(header, 0, wx.LEFT|wx.BOTTOM, spacer)
        return header
    
    @warnWxThread    
    def _add_row(self, parent, sizer, name, value, spacer = 10):
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
            sizer.Add(value, 0, wx.EXPAND|wx.LEFT, spacer)
        
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
        wx.Panel.__init__(self, parent)
        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility
        self.uelog = UserEventLogDBHandler.getInstance()
        
        self.parent = parent
        self.torrent = torrent
        self.state = -1
        self.vod_log = None

        self.compact = compact
        self.saveSpace = compact or parent.GetSize()[0] < self.SAVESPACE_THRESHOLD
        
        self.isReady = False
        self.noChannel = noChannel
        
        self.SetBackgroundColour(LIST_DESELECTED)
        vSizer = wx.BoxSizer(wx.VERTICAL)
        
        #Add messagePanel text
        self.messagePanel = StaticText(self, -1, "Loading details, please wait.")
        vSizer.Add(self.messagePanel, 0, wx.ALIGN_CENTRE_HORIZONTAL|wx.ALL, 3)
        
        #Add details view
        self.details = wx.BoxSizer(wx.HORIZONTAL)
        vSizer.Add(self.details, 0, wx.EXPAND, 0)
        self.SetSizer(vSizer)
        self.Layout()
        
        self.doMark = self.guiutility.frame.selectedchannellist.OnMarkTorrent
        self.doSave = self.guiutility.frame.selectedchannellist.OnSaveTorrent
        self.canEdit = False
        self.canComment = False
        self.canMark = False
        self.showDetails = False
        self.markWindow = None
        
        self.isEditable = {}
        
        self._doLoad()

    def _doLoad(self):
        if DEBUG:
            print >> sys.stderr, "TorrentDetails: loading", self.torrent['name']
            
        #is this torrent collected?
        filename = self.guiutility.torrentsearch_manager.getCollectedFilename(self.torrent, retried = True)
        if filename:
            self.guiutility.torrentsearch_manager.loadTorrent(self.torrent, callback = self.showTorrent)
            
        else:
            def doGui(delayedResult):
                requesttype = delayedResult.get()
                if requesttype:
                    self.showRequestType('The torrentfile is requested %s.'%requesttype)
                
                wx.CallLater(10000, self._timeout)
            
            startWorker(doGui, self.guiutility.torrentsearch_manager.loadTorrent, wargs = (self.torrent,), wkwargs = {'callback':self.showTorrent}, priority = 1024)
    
    @forceWxThread
    def showRequestType(self, requesttype):
        try:
            if requesttype:
                self.messagePanel.SetLabel("Loading details, please wait.\n%s"%requesttype)
            else:
                self.messagePanel.SetLabel("Loading details, please wait.")
            
            self.Layout()
            self.parent.parent_list.OnChange()
        except wx.PyDeadObjectError:
            pass

    @forceWxThread
    def showTorrent(self, torrent, showTab = None):
        try:
            if not self.isReady:
                self.state = -1
                
                if DEBUG:
                    print >> sys.stderr, "TorrentDetails: finished loading", self.torrent.name
                
                self.torrent = torrent
                ds = self.torrent.ds
                
                #start with files tab if we are saving space
                if showTab == None and self.saveSpace and not isinstance(self, LibraryDetails):
                    showTab = "Files"
                
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
                self.details.Clear(deleteWindows = True)
            
                self.notebook = wx.Notebook(self, style = wx.NB_NOPAGETHEME, name = "TorrentDetailsNotebook")
                self._addTabs(ds, showTab)
                
                self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.OnChange)
                self.details.Add(self.notebook, 65, wx.EXPAND)
            
                self._addButtonPanel(self, self.details)
                self._Refresh(ds)
                        
                self.Thaw()
    
                self.parent.parent_list.OnChange()
                self.isReady = True
            
                self.guiutility.library_manager.add_download_state_callback(self.OnRefresh)
        except wx.PyDeadObjectError:
            pass
    
    @forceWxThread
    def _timeout(self):
        try:
            if not self.isReady:
                if DEBUG:
                    print >> sys.stderr, "TorrentDetails: timeout on loading", self.torrent.name
            
                self.messagePanel.SetLabel("Failed loading torrent.\nPlease collapse and expand to retry or wait to allow other peers to respond.")
            
                self.Layout()
                self.parent.parent_list.OnChange()
        except wx.PyDeadObjectError:
            pass
    
    @warnWxThread
    def _addTabs(self, ds, showTab = None):
        finished = self.torrent.get('progress', 0) == 100 or (ds and ds.get_progress() == 1.0)
        
        self.overview = wx.Panel(self.notebook)
        self.overview.Bind(wx.EVT_LEFT_DCLICK, self.OnOverviewToggle)
        def OnChange():
            self.overview.Layout()

            def resize():
                best = self.overview.GetBestSize()[1]
                if self.canComment:
                    best = max(best, self.MINCOMMENTHEIGHT)
                
                if self.compact:
                    best = max(best, 75)
                else:
                    best = max(best, 100)
                
                notebook = self.notebook.CalcSizeFromPage((1, best))[1]
                self.notebook.SetMinSize((-1, notebook))
                self.parent.parent_list.OnChange()
            wx.CallAfter(resize)
        self.overview.OnChange = OnChange
       
        self.torrentSizer = wx.BoxSizer(wx.VERTICAL)
        self.overview.SetSizer(self.torrentSizer)
        
        self.notebook.AddPage(self.overview, "Details")
        
        self._addOverview(self.overview, self.torrentSizer)

        if self.canEdit:
            #Create edit tab
            edit, editSizer = self._create_tab(self.notebook, 'Edit', 'Modify Details')
            
            vSizer = wx.FlexGridSizer(0, 2, 3, 3)
            vSizer.AddGrowableCol(1)
            vSizer.AddGrowableRow(1)
            
            self.isEditable['name'] = EditText(edit, self.torrent.name)
            self.isEditable['description'] = EditText(edit, self.torrent.description or '', True)
            
            self._add_row(edit, vSizer, "Name", self.isEditable['name'])
            self._add_row(edit, vSizer, "Description",self.isEditable['description'])
            editSizer.Add(vSizer, 1, wx.EXPAND)
            
            def save(event):
                self.doSave(self.torrent.channel, self)
                
                button = event.GetEventObject()
                button.Enable(False)
                wx.CallLater(5000, button.Enable, True)
            
            saveButton = wx.Button(edit, -1, "Save")
            saveButton.Bind(wx.EVT_BUTTON, save)
            editSizer.Add(saveButton, 0, wx.ALIGN_RIGHT)
        
        #Create torrent overview
        if self.canComment:
            from channel import CommentList
            self.commentList = NotebookPanel(self.notebook)
            self.commentList.SetList(CommentList(self.commentList, self.parent, canReply = True, quickPost = True))
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
            if self.saveSpace or isinstance(self, LibraryDetails):
                parent = wx.Panel(self.notebook)
                parent.SetBackgroundColour(DEFAULT_BACKGROUND)
            else:
                parent = self.notebook
            
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
                if ds and ds.get_selected_files():
                    selected_files = ds.get_selected_files()
                     
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
            
            if self.saveSpace and not isinstance(self, LibraryDetails):
                hSizer = wx.BoxSizer(wx.HORIZONTAL)
                hSizer.Add(self.listCtrl, 6, wx.EXPAND)
                
                self.buttonPanel = parent
                self.buttonSizer = wx.BoxSizer(wx.VERTICAL)
                
                hSizer.Add(wx.StaticLine(parent, -1, style = wx.LI_VERTICAL), 0, wx.EXPAND|wx.ALL, 3)
                hSizer.Add(self.buttonSizer, 4, wx.EXPAND|wx.RIGHT, 3)
                parent.SetSizer(hSizer)
                self.notebook.AddPage(parent, "Files")
                
            elif isinstance(self, LibraryDetails):
                vSizer = wx.BoxSizer(wx.VERTICAL)
                vSizer.Add(self.listCtrl, 1, wx.EXPAND)
                
                vSizer.Add(wx.StaticLine(parent, -1, style = wx.LI_HORIZONTAL), 0, wx.EXPAND|wx.ALL, 3)
                
                self.filesFooter = StaticText(parent, -1, 'Double click on any file to modify which files should be downloaded.')
                vSizer.Add(self.filesFooter, 0, wx.EXPAND)
                parent.SetSizer(vSizer)
                self.notebook.AddPage(parent, "Files")
            else:
                self.notebook.AddPage(self.listCtrl, "Files")
        
        #Create subtitlelist
        if self.torrent.isPlayable():
            curlang = []
            strlang = []
            
            subsupport = SubtitlesSupport.getInstance()
            if subsupport._registered:
                subs = subsupport.getSubtileInfosForInfohash(self.torrent.infohash)
                if len(subs) > 0:
                    supportedLang = subsupport.langUtility.getLangSupported()

                    for channelid, dict in subs.iteritems():
                        for lang in dict.keys():
                            curlang.append((supportedLang[lang], channelid, dict[lang]))
                    curlang.sort()
                    strlang = [lang[0] for lang in curlang]
            
            internalSubs = self.torrent.subtitlefiles
            internalSubs.sort()
            
            for filename in internalSubs:
                _, nicefilename = os.path.split(filename)
                strlang.append(nicefilename)
                curlang.append([filename])
                
            foundSubtitles = len(curlang) > 0
            
            subtitlePanel, vSizer = self._create_tab(self.notebook, "Subtitles")
            vSizer.AddSpacer((-1, 3))
            
            if not finished:
                title = 'After you finished downloading this torrent you can select a subtitle'
            else:
                title = 'You can now select a subtitle'
            
            if foundSubtitles:
                title += ' found by Tribler or'
            title += ' specified by you to be used with our player.'
            self._add_row(subtitlePanel, vSizer, None, title, spacer = 3)
            
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
            
            self._add_row(subtitlePanel, vSizer, "Which subtitle do you want to use?", None, spacer = 3)
            
            vSizer.Add(self.subtitleChoice, 0, wx.ALIGN_RIGHT|wx.BOTTOM|wx.RIGHT, 3)
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
            trackerPanel, vSizer = self._create_tab(self.notebook, "Trackers", "Trackers")
            for tracker in self.torrent.trackers:
                if isinstance(tracker, basestring):
                    self._add_row(trackerPanel, vSizer, None, tracker)
            trackerPanel.SetupScrolling(rate_y = 5)
                
        self.overview.OnChange()
    
        if showTab:
            for i in range(self.notebook.GetPageCount()):
                if self.notebook.GetPageText(i) == showTab:
                    self.notebook.SetSelection(i)
                    break
    
    @warnWxThread
    def _addButtonPanel(self, parent, sizer):
        if not self.saveSpace:
            self.buttonPanel = wx.Panel(parent)
            self.buttonPanel.SetBackgroundColour(LIST_DESELECTED)
            self.buttonSizer = wx.BoxSizer(wx.VERTICAL)
            self.buttonPanel.SetSizer(self.buttonSizer)
            
            sizer.Add(self.buttonPanel, 35, wx.EXPAND|wx.LEFT|wx.RIGHT, 3)
            
    @warnWxThread
    def _addOverview(self, panel, sizer):
        sizer.Clear(deleteWindows = True)
        self._add_header(panel, sizer, 'Torrent Details')
        
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
            "Type": category.capitalize(),
            "Uploaded": self.torrent.formatCreationDate(),
            "Filesize": filesize,
            "Status": "Unknown"
        }

        if self.compact:
            vSizer = wx.FlexGridSizer(0, 6, 3, 3)
            vSizer.AddGrowableCol(1,4) #we give more space to name and status
            vSizer.AddGrowableCol(3,2)
            vSizer.AddGrowableCol(5,2)
            
            overviewColumnsOrder = ["Name", "Type", "Uploaded", "Status", "Filesize"]
            del overviewColumns['Description']
            
        else:
            vSizer = wx.FlexGridSizer(0, 2, 3, 3)
            vSizer.AddGrowableCol(1)
            
            if self.canEdit or self.torrent.get('description', ''):
                overviewColumnsOrder = ["Name", "Description", "Type", "Uploaded", "Filesize", "Status"]
            else:
                del overviewColumns['Description']
                overviewColumnsOrder = ["Name", "Type", "Uploaded", "Filesize", "Status"]
                
        for column in overviewColumnsOrder:
            _, value = self._add_row(panel, vSizer, column, overviewColumns[column])
            if column == "Status":
                self.status = value
        
        if self.showDetails:
            textCtrl = wx.TextCtrl(panel, -1, self.torrent.infohash_as_hex)
            textCtrl.SetEditable(False)
            self._add_row(panel, vSizer, "Infohash", textCtrl)
        sizer.Add(vSizer, 1, wx.EXPAND)
            
        if self.canEdit:
            modifications = self.guiutility.channelsearch_manager.getTorrentModifications(self.torrent)
            for modification in modifications:
                if modification.name == 'swift-url':
                    value = wx.TextCtrl(panel, -1, modification.value, style = wx.TE_READONLY)
                    self._add_row(panel, vSizer, 'Swift URL', value)
        
        if self.canComment:
            self.UpdateMarkings()
        
        self.UpdateStatus()
        panel.OnChange()
    
    @warnWxThread
    def DownloadStarted(self):
        self.ShowPanel(TorrentDetails.INCOMPLETE)
        
        #Switch to Files tab if in compact mode
        if self.compact:
            for i in range(self.notebook.GetPageCount()):
                if self.notebook.GetPageText(i) == 'Files':
                    self.notebook.ChangeSelection(i)
                    break
    
    @warnWxThread
    def ShowPanel(self, newState = None):
        if getattr(self, 'buttonSizer', False):
            if newState is None:
                newState  = self._GetState()
                
            if self.state != newState:
                self.state = newState
                
                self.buttonPanel.Freeze()
                self.buttonSizer.ShowItems(False)
                self.buttonSizer.DeleteWindows()
                self.buttonSizer.Clear()
                
                #add title
                self.title = wx.StaticText(self.buttonPanel)
                self.title.SetMinSize((1,-1))
                
                if self.saveSpace:
                    _set_font(self.title, size_increment = 0, fontweight = wx.FONTWEIGHT_BOLD)
                else:
                    _set_font(self.title, size_increment = 1, fontweight = wx.FONTWEIGHT_BOLD)
                self.buttonSizer.Add(self.title, 0, wx.ALL|wx.EXPAND, 3)
                
                self._SetTitle(newState)
                
                if newState in [TorrentDetails.FINISHED, TorrentDetails.FINISHED_INACTIVE]:
                    self.torrent.progress = 100
                    self._ShowDone(self.buttonPanel, self.buttonSizer)

                elif newState in [TorrentDetails.INCOMPLETE, TorrentDetails.INCOMPLETE_INACTIVE, TorrentDetails.VOD]:
                    self._ShowDownloadProgress(self.buttonPanel, self.buttonSizer)
                    
                else:
                    self._ShowTorrentDetails(self.buttonPanel, self.buttonSizer)

                if getattr(self.parent, 'button', False):
                    self.parent.button.Enable(newState == TorrentDetails.INACTIVE)
            
                self.buttonPanel.Thaw()
                self.buttonPanel.Layout()
                self.Layout()
        else:
            #Additionally called by database event, thus we need to check if sizer exists(torrent is downloaded).
            wx.CallAfter(self.ShowPanel, newState)

    @warnWxThread
    def _ShowTorrentDetails(self, panel, sizer):
        if not self.saveSpace:
            subtitle = StaticText(panel, -1, "Click download or play to enjoy this torrent.")
            subtitle.SetMinSize((1, -1))
            sizer.Add(subtitle, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM|wx.EXPAND, 3)
        
        sizer.AddStretchSpacer()
        
        download_play_sizer = wx.BoxSizer(wx.HORIZONTAL)
        if wx.Platform=="__WXMAC__":
            self.downloadButton = wx.Button(panel, -1, "Download")
            self.playButton = wx.Button(panel, -1, "Play")
        else:
            #Niels: multiline wx.button bug, if we ever want multiple init with multiline
            self.downloadButton = wx.Button(panel, -1, "Download\n")
            self.downloadButton.SetLabel("Download")
            
            self.playButton = wx.Button(panel, -1, "Play\n")
            self.playButton.SetLabel("Play")
        
        self.downloadButton.SetToolTipString('Start downloading this torrent.')
        self.downloadButton.Bind(wx.EVT_BUTTON, self.OnDownload)
        self.downloadButton.Bind(wx.EVT_MOTION, self.OnDrag)
        
        self.playButton.Bind(wx.EVT_BUTTON, self.OnPlay)
        
        if not self.torrent.isPlayable():
            self.playButton.Disable()
            self.playButton.SetToolTipString('Cannot stream this torrent.')
        else:
            self.playButton.SetToolTipString('Start playing this torrent.')
        
        download_play_sizer.Add(self.downloadButton)
        download_play_sizer.Add(StaticText(panel, -1, "or"), 0, wx.ALIGN_CENTRE_VERTICAL|wx.LEFT|wx.RIGHT, 3)
        download_play_sizer.Add(self.playButton, 0, wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(download_play_sizer, 0, wx.ALIGN_CENTER_HORIZONTAL)
        
        sizer.AddStretchSpacer()
        
        if not self.noChannel:
            if self.torrent.hasChannel():
                if self.torrent.channel.isMyChannel():
                    label = "This torrent is part of your Channel."
                    tooltip = "Open your Channel."
                    
                else:
                    label = "Click to see more from %s's Channel."%self.torrent.channel.name
                    tooltip = "Click to go to %s's Channel."%self.torrent.channel.name

                self.channeltext = LinkStaticText(panel, label)
                self.channeltext.SetToolTipString(tooltip)
                self.channeltext.SetMinSize((1, -1))
                self.channeltext.Bind(wx.EVT_LEFT_UP, self.OnClick)
                self.channeltext.target = 'channel'
                sizer.Add(self.channeltext, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.ALL|wx.EXPAND, 3)
                
                #this is not a 'local' known channel, update it
                if isinstance(self.torrent.channel, RemoteChannel) and self.torrent.query_permids:
                    channelcast = BuddyCastFactory.getInstance().channelcast_core
                    channelcast.updateAChannel(self.torrent.channel.id, self.torrent.channel.permid, self.torrent.query_permids)
        
        elif self.canMark:
            wrong = LinkStaticText(panel, 'Have an opinion? Signal it to other users:')
            wrong.Bind(wx.EVT_LEFT_UP, self.OnMark)
            sizer.Add(wrong, 0, wx.ALL|wx.EXPAND, 3)
    
    @warnWxThread
    def _ShowDownloadProgress(self, panel, sizer):
        if not self.saveSpace and not isinstance(self, LibraryDetails):
            library = LinkStaticText(panel, "Open downloads")
            library.SetToolTipString("Open downloads")
            library.target = 'my_files'
            library.Bind(wx.EVT_LEFT_UP, self.OnClick)
            sizer.Add(library, 0, wx.LEFT|wx.RIGHT, 3)
        
        sizer.AddStretchSpacer()
    
        if not isinstance(self, LibraryDetails):
            if not self.saveSpace:
                #Progress
                header = StaticText(panel, -1, "Current progress")
                _set_font(header, fontweight = wx.FONTWEIGHT_BOLD)
                
                sizer.Add(header, 0, wx.ALL, 3)
            
            class tmp_object():
                def __init__(self, data, original_data):
                    self.data = data
                    self.original_data = original_data
            self.item = tmp_object(['',[0,0],[0,0],0,0],self.torrent)
            self.progress = ProgressPanel(panel, self.item, ProgressPanel.ETA_EXTENDED)
            sizer.Add(self.progress, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM|wx.EXPAND, 3)
        
        #Optional stream button
        if self.torrent.isPlayable() and not self.state == TorrentDetails.VOD:
            sizer.AddStretchSpacer()
            self._AddVodAd(panel, sizer)

        if not self.saveSpace and isinstance(self, LibraryDetails):
            self.vod_log = StaticText(panel)
            self.vod_log.SetMinSize((1,-1))
            self.vod_log.Hide()
        
            sizer.Add(self.vod_log, 0, wx.EXPAND, 3)
        else:
            self.vod_log = None
            
        self.guiutility.library_manager.add_download_state_callback(self.OnRefresh)
    
    @warnWxThread
    def _ShowDone(self, panel, sizer):
        sizer.AddStretchSpacer()
        self._AddDoneAd(panel, sizer)
        
        if getattr(self, 'subtitleChoice', None):
            self.subtitleChoice.Enable(True)
    
    @warnWxThread      
    def _AddDoneAd(self, parent, sizer):
        play = wx.Button(parent, -1, "Play")
        play.SetToolTipString('Start playing this torrent.')
        play.Bind(wx.EVT_BUTTON, self.OnPlay)
        play.Enable(self.torrent.isPlayable())
        
        explore_play_sizer = wx.BoxSizer(wx.HORIZONTAL)
        explore = wx.Button(parent, -1, "Explore Files")
        explore.SetToolTipString('Explore the files of this torrent.')
        explore.Bind(wx.EVT_BUTTON, self.OnExplore)
        
        explore_play_sizer.Add(explore)
        explore_play_sizer.Add(StaticText(parent, -1, "or"), 0, wx.ALIGN_CENTRE_VERTICAL|wx.LEFT|wx.RIGHT, 3)
        explore_play_sizer.Add(play)
        sizer.Add(explore_play_sizer, 0, wx.ALIGN_CENTER_HORIZONTAL)
        
        if isinstance(self, LibraryDetails):
            sizer.AddSpacer((-1, 10))
        sizer.AddStretchSpacer()
        
        if not self.saveSpace and not self.noChannel:
            #if not attached channel, or not from my channel
            if not self.torrent.hasChannel() or not self.torrent.channel.isMyChannel():
                header = wx.StaticText(parent, -1, "Did you enjoy this torrent?")
                _set_font(header, fontweight = wx.FONTWEIGHT_BOLD)
                header.SetMinSize((1,-1))
                sizer.Add(header, 0, wx.ALL|wx.EXPAND, 3)
                
                if self.torrent.hasChannel():
                    if self.canMark:
                        wrong = LinkStaticText(parent, 'Signal your opinion to other users')
                        wrong.Bind(wx.EVT_LEFT_UP, self.OnMark)
                        wrong.SetMinSize((1, -1))
                        sizer.Add(wrong, 0, wx.ALL|wx.EXPAND, 3)
                    
                    channeltext = LinkStaticText(parent, "Click to see more from %s's Channel."%self.torrent.channel.name)
                    channeltext.SetToolTipString("Click to go to %s's Channel."%self.torrent.channel.name)
                    channeltext.SetMinSize((1, -1))
                    channeltext.target = 'channel'
                    channeltext.Bind(wx.EVT_LEFT_UP, self.OnClick)
                    sizer.Add(channeltext, 0, wx.ALL|wx.EXPAND, 3)
                
                    mychannel = LinkStaticText(parent, "Or spread it using your channel")
                else:
                    mychannel = LinkStaticText(parent, "Spread it using your channel")
                
                mychannel.SetMinSize((1, -1))
                mychannel.Bind(wx.EVT_LEFT_UP, self.OnMyChannel)
                mychannel.SetToolTipString('Add this torrent to your channel.')
                sizer.Add(mychannel, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM|wx.EXPAND, 3)
                
            else:
                header = wx.StaticText(parent, -1, "You are sharing this torrent in your channel")
                _set_font(header, fontweight = wx.FONTWEIGHT_BOLD)
                header.SetMinSize((1,-1))
                
                sizer.Add(header, 0, wx.ALL|wx.EXPAND, 3)
                
                channeltext = LinkStaticText(parent, "Open your channel")
                channeltext.SetToolTipString("Click to go to your Channel.")
                channeltext.SetMinSize((1, -1))
                channeltext.target = 'channel'
                channeltext.Bind(wx.EVT_LEFT_UP, self.OnClick)
                sizer.Add(channeltext, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM|wx.EXPAND, 3)

        parent.Layout()
    
    @warnWxThread
    def _AddVodAd(self, parent, sizer):
        vSizer = wx.BoxSizer(wx.VERTICAL)
        
        if not self.compact:
            header = wx.StaticText(parent, -1, "Impatient?")
            _set_font(header, fontweight = wx.FONTWEIGHT_BOLD)

            vSizer.Add(header, 0, wx.ALL, 3)
        
        play = LinkStaticText(parent, "Start streaming this torrent now")
        play.SetToolTipString('Start streaming this torrent.')
        play.Bind(wx.EVT_LEFT_UP, self.OnPlay)
        vSizer.Add(play, 0, wx.LEFT|wx.RIGHT|wx.BOTTOM, 3)
        sizer.Add(vSizer, 0, wx.EXPAND)

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
    def OnEdit(self, doEdit):
        if len(self.isEditable) > 0:
            for editable in self.isEditable.values():
                editable.ShowEdit(doEdit)
        
        self.notebook.SetMinSize((-1, self.notebook.GetBestSize()[1]))
        self.parent.parent_list.OnChange()
    
    @warnWxThread
    def OnChange(self, event):
        page = event.GetSelection()
        
        title = self.notebook.GetPageText(page)
        if title.startswith('Comments'):
            self.commentList.Show()
            self.commentList.SetFocus()
            
        elif title.startswith('Modifications'):
            self.modificationList.Show()
            self.modificationList.SetFocus()

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
    def OnExplore(self, event):
        path = self._GetPath()
        if path and os.path.exists(path):
            startfile(path)
        else:
            path = DefaultDownloadStartupConfig.getInstance().get_dest_dir()
            startfile(path)
            
        button = event.GetEventObject()
        button.Enable(False)
        wx.CallLater(5000, button.Enable, True)
    
    @warnWxThread
    def OnDownload(self, event):
        nrSelected = self.listCtrl.GetSelectedItemCount()
        if nrSelected > 0 and nrSelected < self.listCtrl.GetItemCount():
            files = []
            selected = self.listCtrl.GetFirstSelected()
            while selected != -1:
                files.append(self.listCtrl.GetItem(selected, 0).GetText())
                selected = self.listCtrl.GetNextSelected(selected)
        else:
            files = None
        self.parent.parent_list.parent_list.StartDownload(self.torrent, files)
        
        button = event.GetEventObject()
        button.Enable(False)
        wx.CallLater(5000, button.Enable, True)
    
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
    def OnPlay(self, event):
        @forceDBThread
        def addEvent(message, type):
            self.uelog.addEvent(message = message, type = type)
        
        print >> sys.stderr, "PLAY button clicked"
        
        
        play = event.GetEventObject()
        playable_files = self.torrent.videofiles
        
        if len(playable_files) > 1: #Create a popup
            playable_files.sort()
            
            nrSelected = self.listCtrl.GetSelectedItemCount()
            selected = self.listCtrl.GetFirstSelected()
            if selected != -1 and self.listCtrl.GetItemText(selected) in playable_files and nrSelected == 1:
                selected_file = self.listCtrl.GetItemText(selected)
                
            else:
                dialog = wx.SingleChoiceDialog(self, 'Tribler currently only supports playing one file at a time.\nSelect the file you want to play?', 'Which file do you want to play?',playable_files)
            
                (_, selected_file) = max([(size, filename) for filename, size in self.torrent.files if filename in self.torrent.videofiles])
             
                if selected_file in playable_files:
                    dialog.SetSelection(playable_files.index(selected_file))
                
                if dialog.ShowModal() == wx.ID_OK:
                    selected_file = dialog.GetStringSelection()
                else:
                    selected_file = None
                dialog.Destroy()
            
            if selected_file:
                self.guiutility.library_manager.playTorrent(self.torrent, selected_file)
                if self.noChannel:
                    addEvent("Torrent: torrent play from channel", 2)
                else:
                    addEvent("Torrent: torrent play from other", 2)       
            
        elif len(playable_files) == 1:
            self.guiutility.library_manager.playTorrent(self.torrent, playable_files[0])
            
            if self.noChannel:
                addEvent("Torrent: torrent play from channel", 2)
            else:
                addEvent("Torrent: torrent play from other", 2)
        
        if isinstance(play, wx.Button):
            play.Enable(False)
            wx.CallLater(5000, play.Enable, True)
    
    @warnWxThread
    def OnDoubleClick(self, event):
        selected = self.listCtrl.GetFirstSelected()
        playable_files = self.torrent.videofiles
            
        if selected != -1:
            selected_file = self.listCtrl.GetItemText(selected)
            if selected_file in playable_files:
                self.guiutility.library_manager.playTorrent(self.torrent, selected_file)

            elif self.torrent.progress == 100: #not playable, but are we complete?
                file = self._GetPath(selected_file)
                if os.path.isfile(file):
                    startfile(file)
    
    @warnWxThread   
    def OnFilesSelected(self, event):
        if wx.Platform !="__WXMAC__" and getattr(self, 'buttonPanel', False):
            self.buttonPanel.Freeze()
            
            if getattr(self, 'downloadButton', False):
                nrSelected = self.listCtrl.GetSelectedItemCount()
                if nrSelected > 0 and nrSelected < self.listCtrl.GetItemCount():
                    #not all files selected
                    label = "Download \nselected only"
                else:
                    label = 'Download'
                    
                if label != self.downloadButton.GetLabel():
                    self.downloadButton.SetLabel(label)
                    self.buttonPanel.Layout()
                    
            if getattr(self, 'playButton', False):
                playable_files = self.torrent.videofiles
                
                nrSelected = self.listCtrl.GetSelectedItemCount()
                selected = self.listCtrl.GetFirstSelected()
                if selected != -1 and self.listCtrl.GetItemText(selected) in playable_files and nrSelected == 1:
                    label = 'Play\nselected'
                else:
                    label = 'Play'
                    
                if label != self.playButton.GetLabel():
                    self.playButton.SetLabel(label)
                    self.buttonPanel.Layout()
                    
            self.buttonPanel.Thaw()
                    
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
            if len(self.subtitleChoice.items[selected]) > 1:
                (lang, channelid, subtitleinfo) = self.subtitleChoice.items[selected]
                
                self.requestingSub.SetLabel('Requesting subtitle from peers...')
                self._ToggleSubtitleChoice(False)
                                
                subsupport = SubtitlesSupport.getInstance()
                subsupport.retrieveSubtitleContent(channelid, self.torrent['infohash'], subtitleinfo, self.OnRetrieveSubtitle)
                
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
            self.guiutility.frame.top_bg.selectTab('my_files')
            self.guiutility.ShowPage('my_files', self.torrent.infohash)
            
        else:
            self.guiutility.showChannel(self.torrent.channel)
    
    @warnWxThread   
    def OnMark(self, event):
        if self.markWindow:
            self.markWindow.Show(False)
            self.markWindow.Destroy()
            self.markWindow = None
        
        parentPanel = self.parent.GetParent()
        
        self.markWindow = wx.Panel(parentPanel)
        vSizer = wx.BoxSizer(wx.VERTICAL)
        
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        text = wx.StaticText(self.markWindow, -1, "Mark this torrent as being: ")
        _set_font(text, size_increment = 1, fontweight = wx.FONTWEIGHT_BOLD)
        
        markChoices = wx.Choice(self.markWindow, choices = ['Good', 'High-Quality', 'Mid-Quality', 'Low-Quality', 'Corrupt', 'Fake', 'Spam'])
        hSizer.Add(text, 1, wx.RIGHT|wx.ALIGN_CENTER_VERTICAL, 3)
        hSizer.Add(markChoices)
        
        vSizer.Add(hSizer, 0, wx.EXPAND|wx.ALL, 3)
        
        addiText = wx.StaticText(self.markWindow, -1, "Corrupt, Fake and Spam torrents are reported to the Moderators \nfor deletion.")
        vSizer.Add(addiText, 0, wx.EXPAND|wx.ALL, 3)
        
        def DoMark(event):
            selected = markChoices.GetSelection()
            if selected != wx.NOT_FOUND:
                type = markChoices.GetString(selected)
                
                self.doMark(self.torrent.channel, self.torrent.infohash, type)
                self.markWindow.Show(False)
                self.markWindow.Destroy()
                self.markWindow = None
                
        button = wx.Button(self.markWindow, -1, "Mark Now")
        button.Bind(wx.EVT_BUTTON, DoMark)
        vSizer.Add(button, 0, wx.ALIGN_RIGHT|wx.ALL, 3)
        
        self.markWindow.SetSizerAndFit(vSizer)
        self.markWindow.Layout()
        
        btn = event.GetEventObject()
        
        sz =  btn.GetSize()
        pos = btn.ClientToScreen((0,0))
        parentpos = parentPanel.ClientToScreen((0,0))
        pos = pos - parentpos + (0, sz[1])
        
        self.markWindow.SetPosition(pos)
        self.markWindow.Show()
        self.markWindow.Raise()
    
    @forceDBThread
    def OnMyChannel(self, event):
        didAdd = self.guiutility.channelsearch_manager.createTorrent(None, self.torrent)
        if didAdd:
            self.uelog.addEvent(message="MyChannel: manual add from library", type = 2)
            
            #remote channel link to force reload
            del self.torrent.channel
            self.torrent.channel
            
            def gui_call():
                self.guiutility.Notify('New torrent added to My Channel', wx.ART_INFORMATION)
            wx.CallAfter(gui_call)

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
                self.ShowStatus(False)
    
    @forceDBThread
    def UpdateStatus(self):
        if self.torrent.trackers and len(self.torrent.trackers) > 0:
            #touch swarminfo property        
            swarmInfo = self.torrent.swarminfo
            
            if swarmInfo:
                diff = time() - self.torrent.last_check
            else:
                diff = 1801
                
            if diff > 1800:
                updating = TorrentChecking.getInstance().addToQueue(self.torrent.infohash)
                self.ShowStatus(updating)
            else:
                self.ShowStatus(False)
        else:
            self.ShowStatus(False)

    @forceWxThread
    def ShowStatus(self, updating):
        if getattr(self, 'status', False):
            updating = ', updating now' if updating else ''
            
            diff = time() - self.torrent.last_check
            if self.torrent.num_seeders < 0 and self.torrent.num_leechers < 0:
                if self.torrent.status == 'good':
                    self.status.SetLabel("Unknown, but found peers in the DHT")
                else:
                    self.status.SetLabel("Unknown"+updating)
            else:
                if diff < 5:
                    self.status.SetLabel("%s seeders, %s leechers (current)"%(self.torrent.num_seeders, self.torrent.num_leechers))
                else:
                    updated = self.guiutility.utility.eta_value(diff, 2)
                    if updated == '<unknown>':
                        self.status.SetLabel("%s seeders, %s leechers"%(self.torrent.num_seeders, self.torrent.num_leechers)+updating)
                    else:
                        self.status.SetLabel("%s seeders, %s leechers (updated %s ago%s)"%(self.torrent.num_seeders, self.torrent.num_leechers ,updated, updating))
        else:
            print >> sys.stderr, "No status element to show torrent_status"
    
    def OnMarkingCreated(self, channeltorrent_id):
        if self.torrent.get('channeltorrent_id', False) == channeltorrent_id:
            self.UpdateMarkings()
    
    def UpdateMarkings(self):
        if self.torrent.get('channeltorrent_id', False):
            startWorker(self.ShowMarkings, self.guiutility.channelsearch_manager.getTorrentMarkings, wargs= (self.torrent.channeltorrent_id, ))
     
    @warnWxThread
    def ShowMarkings(self, delayedResult):
        markings = delayedResult.get()
        if len(markings) > 0:
            msg = 'This torrent is marked as:'
            for marktype, nr in markings:
                msg += ' %s (%d)'%(marktype, nr)
            
            #see if we are updating
            children = list(self.torrentSizer.GetChildren())
            staticline = children[-2].GetWindow()
            
            if not isinstance(staticline, wx.StaticLine):
                self.torrentSizer.Add(wx.StaticLine(self.overview, -1, style = wx.LI_HORIZONTAL), 0, wx.ALL|wx.EXPAND, 5)
                self._add_row(self.overview, self.torrentSizer, None, msg, 10)
            else:
                statictext = children[-1].GetSizer()
                statictext.SetLabel(msg)
                
            self.torrentSizer.Layout()
           
    def OnRefresh(self, dslist):
        found = False
        
        for ds in dslist:
            if self.torrent.addDs(ds):
                found = True
        
        if not found:
            self.torrent.clearDs()
            self._Refresh()
        else:
            self._Refresh()

    @warnWxThread
    def _Refresh(self, ds = None):
        if ds:
            self.torrent.addDs(ds)

        state = self._GetState()
        if state != self.state:
            self.ShowPanel(state)
            self._SetTitle(state)
        
        elif state in [TorrentDetails.INCOMPLETE, TorrentDetails.INCOMPLETE_INACTIVE, TorrentDetails.VOD]:
            if getattr(self, 'progress', False):
                self.progress.Update(self.torrent.ds)
    
    def _GetState(self):
        active = vod = False
        
        ds = self.torrent.ds        
        if ds:
            progress = ds.get_progress()
            finished = progress == 1.0
            if finished: #finished download
                active = ds.get_status() == DLSTATUS_SEEDING

            else: #active download
                active = ds.get_status() not in [DLSTATUS_STOPPED, DLSTATUS_STOPPED_ON_ERROR]
                if ds.is_vod():
                    vod = True
        else:
            progress = self.torrent.get('progress', 0)
            finished = progress >= 100
        
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
    
    @warnWxThread
    def _SetTitle(self, state):
        if state == TorrentDetails.FINISHED or state == TorrentDetails.FINISHED_INACTIVE:
            label = 'This torrent has finished downloading.'
        
        elif state == TorrentDetails.VOD:
            label = 'You are streaming this torrent'
        
        elif state == TorrentDetails.INCOMPLETE:
            label = 'You are downloading this torrent'

        elif state == TorrentDetails.INCOMPLETE_INACTIVE:
            label = 'This torrent is inactive'
        
        else:
            label = 'Liking what you see?'
        
        if getattr(self,'title', False) and self.title.GetLabel() != label:
            self.title.SetLabel(label)
            self.title.Refresh()
    
    @warnWxThread
    def Layout(self):
        returnValue = wx.Panel.Layout(self)
        
        if self.isReady:
            #force setupscrolling for scrollpages, if constructed while not shown this is required.
            for i in range(self.notebook.GetPageCount()):
                page = self.notebook.GetPage(i)
                page.Layout()
                
                if getattr(page, 'SetupScrolling', False):
                    page.SetupScrolling()
                    
        return returnValue
    
    @warnWxThread
    def OnEventSize(self, width):
        if self.compact:
            return False
        
        if width < self.SAVESPACE_THRESHOLD:
            if not self.saveSpace:
                self.saveSpace = True
                self.state = -1
                
                self.details.Clear(deleteWindows = True)
                self.isReady = False
                self.showTorrent(self.torrent, "Files")
                return True
            
        if self.saveSpace:
            self.saveSpace = False
            self.state = -1

            self.details.Clear(deleteWindows = True)
            self.isReady = False
            self.showTorrent(self.torrent)
            return True
        
        return False
    
    def OnOverviewToggle(self, event):
        self.showDetails = not self.showDetails
        self._addOverview(self.overview, self.torrentSizer)
    
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
    def __init__(self, parent, torrent, onstop, onresume, ondelete):
        self.onstop = onstop
        self.onresume = onresume
        self.ondelete = ondelete 

        self.old_progress = -1
        self.startstop = None
        TorrentDetails.__init__(self, parent, torrent)
        
        # Arno, 2012-07-17: Retrieving peerlist for the DownloadStates takes CPU
        # so only do it when needed for display.
        self.guiutility.library_manager.set_want_peers(True)
        
    def __del__(self):
        TorrentDetails.__del__(self)
        self.guiutility.library_manager.set_want_peers(False)
        
    def _doLoad(self):
        if DEBUG:
            print >> sys.stderr, "LibraryDetails: loading", self.torrent['name']
        
        self.showRequestType('')
        startWorker(None, self.guiutility.torrentsearch_manager.loadTorrent, wargs = (self.torrent,), wkwargs = {'callback': self.showTorrent}, priority=GUI_PRI_DISPERSY)
        
        wx.CallLater(10000, self._timeout)
        
    @forceWxThread
    def _timeout(self):
        try:
            if not self.isReady:
                if DEBUG:
                    print >> sys.stderr, "TorrentDetails: timeout on loading", self.torrent.name
            
                self.Freeze()
                self.messagePanel.Show(False)
                
                vSizer = wx.BoxSizer(wx.VERTICAL)
                vSizer.AddStretchSpacer()
                
                msg = StaticText(self, -1, "Failed loading torrent. Please collapse and expand to retry or wait to allow other peers to respond.\nAlternatively you could remove this torrent from your Downloads.")
                vSizer.Add(msg)
                
                button = wx.Button(self, -1, 'Delete...')
                button.Bind(wx.EVT_BUTTON, self.OnDelete)
                vSizer.Add(button, 0, wx.TOP|wx.ALIGN_CENTER_HORIZONTAL, 10)
                vSizer.AddStretchSpacer()
                
                self.details.AddStretchSpacer()
                self.details.Add(vSizer, 0, wx.ALL, 10)
                self.details.AddStretchSpacer()
                        
                self.Thaw()
            
                self.Layout()
                self.parent.parent_list.OnChange()
        except wx.PyDeadObjectError:
            pass
    
    @warnWxThread
    def _addTabs(self, ds, showTab = None):
        if self.saveSpace and showTab == "Files":
            showTab = "Overview"
        
        self.overviewPanel = wx.Panel(self.notebook)
        def OnChange():
            self.overviewPanel.Layout()
            self.overview.Layout()

            def resize():
                best = self.overviewPanel.GetBestSize()[1]
                best2 = self.overview.GetBestSize()[1]
                if self.canComment:
                    best = max(best, best2, self.MINCOMMENTHEIGHT)
                else:
                    best = max(best, best2)
                
                #making sure it is at least 100px 
                best = max(best, 100)
                
                notebook = self.notebook.CalcSizeFromPage((1, best))[1]
                self.notebook.SetMinSize((-1, notebook))
                self.parent.parent_list.OnChange()
            wx.CallAfter(resize)
        self.overviewPanel.OnChange = OnChange
        
        vSizer = wx.BoxSizer(wx.VERTICAL)
        self.overviewPanel.SetSizer(vSizer)
        
        self._add_header(self.overviewPanel, vSizer, 'Transfer Overview')
        
        self.overviewSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.Add(self.overviewSizer, 1, wx.EXPAND)
        
        self.notebook.AddPage(self.overviewPanel, "Overview")
        
        #add normal tabs
        TorrentDetails._addTabs(self, ds, showTab)
        
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
        vSizer.Add(self.peerList, 1, wx.EXPAND)
        
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
    
    @warnWxThread
    def OnDoubleClick(self, event):
        selected = self.listCtrl.GetFirstSelected()
        
        if selected != -1:
            selected_file = self.listCtrl.GetItem(selected, 0).GetText()
            selected_state = self.listCtrl.GetItem(selected, 2).GetText()
            
            if selected_state == 'Excluded':
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
            else:
                TorrentDetails.OnDoubleClick(self, event)
    
    @warnWxThread
    def _SetTitle(self, state):
        TorrentDetails._SetTitle(self, state)

        if self.startstop:
            if state in [TorrentDetails.FINISHED, TorrentDetails.FINISHED_INACTIVE]:
                statestr = "Seeding"
                
            elif state == TorrentDetails.VOD:
                statestr = "Streaming"
                
            else:
                statestr = "Downloading"
            
            if state in [TorrentDetails.FINISHED_INACTIVE, TorrentDetails.INCOMPLETE_INACTIVE, TorrentDetails.INACTIVE]:
                button = "Start "+statestr
            else:
                button = "Stop "+statestr
                        
            if self.startstop.GetLabel() != button:
                self.startstop.SetLabel(button)
                self.startstop.Enable()
                self.buttonPanel.Layout()
    
    @warnWxThread
    def OnStartStop(self, event):
        button = event.GetEventObject()
        
        if button.GetLabel().startswith('Start'):
            self.onresume(event)
        else:
            self.onstop(event)
        
        button.Enable(False)
        wx.CallLater(5000, button.Enable, True)
    
    @warnWxThread
    def OnDelete(self, event):
        self.ondelete(event)
    
    @warnWxThread
    def ShowPanel(self, newState = None):
        if newState and newState != self.state:
            self.state = newState
            
            self.overviewPanel.Freeze()
            self.overviewSizer.ShowItems(False)
            self.overviewSizer.DeleteWindows()
            self.overviewSizer.Clear()
            
            self.overviewSizer.AddSpacer((-1, 10))
            self.overviewSizer.AddStretchSpacer()
            
            if self.saveSpace:
                self.buttonPanel = self.overviewPanel
                self._AddButtons(self.overviewPanel, self.overviewSizer)
                
                if self.state == TorrentDetails.FINISHED or self.state == TorrentDetails.FINISHED_INACTIVE:
                    nrChildren = len(self.overviewSizer.GetChildren())
                    
                    self._AddDoneAd(self.overviewPanel, self.overviewSizer)
                    
                    #merge two sizers
                    last = self.overviewSizer.GetItem(nrChildren-1).GetSizer()
                    first = self.overviewSizer.GetItem(nrChildren).GetSizer()
                    self.overviewSizer.Detach(last)
                    
                    for child in last.GetChildren():
                        if child.IsWindow():
                            control = child.GetWindow()
                            first.Add(control)
                            
                    for child in first.GetChildren():
                        if child.IsWindow():
                            control = child.GetWindow()
                            if isinstance(control, StaticText):
                                first.Remove(control)
                                control.Destroy()

                elif newState in [TorrentDetails.INCOMPLETE, TorrentDetails.INCOMPLETE_INACTIVE, TorrentDetails.VOD]:
                    self._ShowDownloadProgress(self.overviewPanel, self.overviewSizer)
                    
                elif self.state == TorrentDetails.VOD:
                    pass
               
            else:
                if self.state == TorrentDetails.FINISHED or self.state == TorrentDetails.FINISHED_INACTIVE:
                    self._AddDoneAd(self.overviewPanel, self.overviewSizer)
                    self.overviewPanel.SetLabel('Transfer Completed')
                
                elif self.state == TorrentDetails.INCOMPLETE or self.state == TorrentDetails.INCOMPLETE_INACTIVE:
                    self.progress = StringProgressPanel(self.overviewPanel, self.torrent)
                    
                    self.overviewSizer.Add(self.progress, 0, wx.EXPAND|wx.LEFT|wx.RIGHT, 3)
                    
                    #Optional stream button
                    if self.torrent.isPlayable():
                        self.overviewSizer.AddStretchSpacer()
                        self._AddVodAd(self.overviewPanel, self.overviewSizer)
                    
                elif self.state == TorrentDetails.VOD:
                    #TODO: show buffer, bitrate etc
                    pass
                
                if len(self.buttonSizer.GetChildren()) == 0:
                    #Header
                    self.title = StaticText(self.buttonPanel)
                    _set_font(self.title, fontweight = wx.FONTWEIGHT_BOLD, size_increment=1)
                    
                    self.buttonSizer.Add(self.title, 0, wx.LEFT|wx.RIGHT|wx.TOP|wx.EXPAND, 3)
    
                    self.buttonSizer.AddStretchSpacer()
                    
                    self._AddButtons(self.buttonPanel, self.buttonSizer)
            
            self.overviewPanel.Layout()
            self.overviewPanel.OnChange()
            self.overviewPanel.Thaw()
    
    @warnWxThread
    def _AddButtons(self, panel, sizer):
        #create torrent start/stop/delete buttons
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.startstop = wx.Button(panel)
        self.startstop.Bind(wx.EVT_BUTTON, self.OnStartStop)
        hSizer.Add(self.startstop)
        
        hSizer.Add(StaticText(panel, -1, "or"), 0, wx.ALIGN_CENTRE_VERTICAL|wx.LEFT|wx.RIGHT, 3)
        
        button = wx.Button(panel, -1, 'Delete...')
        button.Bind(wx.EVT_BUTTON, self.OnDelete)
        hSizer.Add(button)
        sizer.Add(hSizer, 0, wx.ALIGN_CENTER_HORIZONTAL)
        
        if not self.saveSpace:
            sizer.AddStretchSpacer()
            
            vSizer = wx.FlexGridSizer(0, 4, 3, 3)
            vSizer.AddGrowableCol(1)
            vSizer.AddGrowableCol(3)
            _, self.downloaded = self._add_row(panel, vSizer, "Downloaded", self.utility.size_format(0), spacer = 3)
            _, self.uploaded = self._add_row(panel, vSizer, "Uploaded", self.utility.size_format(0), spacer = 3)
            sizer.Add(vSizer, 0, wx.EXPAND)
            sizer.Layout()
        else:
            self.downloaded = self.uploaded = None
    
    @warnWxThread
    def _Refresh(self, ds = None):
        TorrentDetails._Refresh(self, ds)
        
        #register callback for peerlist update
        self.peerList.Freeze()
        
        ds = self.torrent.ds
        index = 0
        if ds:
            if getattr(self, 'downloaded', False):
                if ds.get_seeding_statistics():
                    stats = ds.get_seeding_statistics()
                    dl = stats['total_down']
                    ul = stats['total_up']
                    
                    progress = ds.get_progress()
                    size = ds.get_length()
                else:
                    dl = ds.get_total_transferred(DOWNLOAD)
                    ul = ds.get_total_transferred(UPLOAD)
                    
                    progress = self.torrent.progress or 0
                    size = self.torrent.length or 0
            
                size_progress = size*progress
                dl = max(dl, size_progress)
                
                self.downloaded.SetLabel(self.utility.size_format(dl))
                self.uploaded.SetLabel(self.utility.size_format(ul))
                self.buttonPanel.Layout()
            
            peers = ds.get_peerlist()
            
            def downsort(a, b):
                if a['downrate'] != b['downrate']:
                    return a['downrate'] - b['downrate']
                return a['uprate'] - b['uprate']
            peers.sort(downsort, reverse = True)
            
            for peer_dict in peers:
                peer_name = peer_dict['ip'] + ':%d @ %d%%'%(peer_dict['port'], peer_dict['completed']*100.0)
                if index < self.peerList.GetItemCount():
                    self.peerList.SetStringItem(index, 0, peer_name)
                else:
                    self.peerList.InsertStringItem(index, peer_name)
                
                traffic = ""
                traffic += self.guiutility.utility.speed_format_new(peer_dict['downrate']) + u"\u2193 "
                traffic += self.guiutility.utility.speed_format_new(peer_dict['uprate']) + u"\u2191"
                self.peerList.SetStringItem(index, 1, traffic.strip())
                
                state = ""
                if peer_dict['optimistic']:
                    state += "O,"
                if peer_dict['uinterested']:
                    state += "UI,"
                if peer_dict['uchoked']:
                    state += "UC,"
                if peer_dict['uhasqueries']:
                    state += "UQ,"
                if not peer_dict['uflushed']:
                    state += "UBL,"
                if peer_dict['ueligable']:
                    state += "UE,"
                if peer_dict['dinterested']:
                    state += "DI,"
                if peer_dict['dchoked']:
                    state += "DC,"
                if peer_dict['snubbed']:
                    state += "S,"
                state += peer_dict['direction']
                self.peerList.SetStringItem(index, 2, state)
                
                try:
                    self.peerList.SetStringItem(index, 3, peer_dict['extended_version'])
                except:
                    try:
                        self.peerList.SetStringItem(index, 3, peer_dict['extended_version'].decode('utf-8','ignore'))
                    except:
                        print >> sys.stderr, "Could not format peer client version"
                
                index += 1

            if self.availability:
                self.availability.SetLabel("%.2f"%ds.get_availability())
                self.pieces.SetLabel("total %d, have %d"%ds.get_pieces_total_complete())
                
                self.availability.sizer.Layout()

            dsprogress = ds.get_progress()
            if self.old_progress != dsprogress:
                if ds.get_download().get_def().get_def_type() == 'swift':
                    completion = []
                    
                    selected_files = ds.get_download().get_selected_files()
                    if selected_files:
                        for i in range(self.listCtrl.GetItemCount()):
                            file = self.listCtrl.GetItem(i, 0).GetText()
                            if file in selected_files:
                                completion.append([file, dsprogress])
                    else:
                        for i in range(self.listCtrl.GetItemCount()):
                            completion.append([self.listCtrl.GetItem(i, 0).GetText(), dsprogress])
                else:
                    completion = ds.get_files_completion()
                
                for i in range(self.listCtrl.GetItemCount()):
                    listfile = self.listCtrl.GetItem(i, 0).GetText()
                    
                    found = False
                    for file, progress in completion:
                        if file == listfile:
                            self.listCtrl.SetStringItem(i, 2, "%.2f%%"%(progress*100))
                            found = True
                            break
                        
                    if not found:
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

class ProgressPanel(wx.BoxSizer):
    #eta style
    ETA_DEFAULT = 1
    ETA_EXTENDED = 2
    
    def __init__(self, parent, item, style = ETA_DEFAULT):
        wx.BoxSizer.__init__(self, wx.VERTICAL)
        self.item = item
        self.style = style
        guiutility = GUIUtility.getInstance()
        self.utility = guiutility.utility

        self.pb = ProgressBar(parent)
        self.status = StaticText(parent)
        
        self.AddStretchSpacer()
        self.Add(self.pb, 0, wx.EXPAND)
        self.Add(self.status, 0, wx.EXPAND)
        
        self.AddStretchSpacer()
        self.Update()
        
    def Update(self, ds = None):
        #return_val, 0 == inactive, 1 == incomplete, 2 == complete/seeding
        return_val = 0
        
        if ds == None:
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
                    
                    
                    if self.style == ProgressPanel.ETA_DEFAULT and dls == 0 and uls == 0 and ds:
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
        if self.status.GetLabel() != eta:
            self.status.SetLabel(eta)
            self.status.Refresh()
            
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

        self.subsupport = SubtitlesSupport.getInstance()
        self.supportedLang = self.subsupport.langUtility.getLangSupported()
        self.supportedLangFull = self.supportedLang.values()
        self.supportedLangFull.sort()
        
        wx.Panel.__init__(self, parent)
        
        self.borderSizer = wx.BoxSizer()
        self.SetSizer(self.borderSizer)
        
        self.SetBackgroundColour(LIST_DESELECTED)
        self.guiutility.torrentsearch_manager.loadTorrent(self.torrent, callback = self.showTorrent)
    
    @forceWxThread
    def showTorrent(self, torrent):
        notebook = wx.Notebook(self, style = wx.NB_NOPAGETHEME)
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
        self.parent.parent_list.OnChange()
    
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
                        
                        self.parent.parent_list.OnChange()
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
        
        gridSizer = wx.FlexGridSizer(0, 2, 3, 3)
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
    
class SwarmHealth(wx.Panel):
    def __init__(self, parent, bordersize = 0, size = wx.DefaultSize, align = wx.ALIGN_LEFT):
        wx.Panel.__init__(self, parent, size = size, style = wx.NO_BORDER)
        self.bordersize = bordersize
        self.align = align
        
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
    
    def SetRatio(self, seeders, leechers):
        ratio = 0
        pop = 0
        
        self.blue = 0
        if leechers <= 0 and seeders <= 0:
            self.barwidth = 0
            
            self.green = 0
            self.red = 0
        else:
            if leechers == 0 and seeders:
                ratio = sys.maxint
            elif seeders == 0:
                if leechers:
                    ratio = 0.01
                else:
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
                    self.barwidth = min(max(math.log(pop*4,10) * 2, 1) / 10.0, 1) #let it max at 25k population
                else:
                    self.barwidth = 1
                
                self.green = max(0, min(255, 125 + (ratio * 130)))
                self.red = max(0, min(255, 125 + ((1 - ratio) * 130)))
        self.Refresh()
        
        if self.barwidth == 0:
            tooltip = 'Unknown swarmsize and seeder to leecher ratio.'
        else:
            if pop < 10:
                tooltip = 'A small swarm'
            elif pop < 500:
                tooltip = 'A medium-sized swarm'
            else:
                tooltip = 'A large swarm'
            
            if ratio == 0:
                tooltip += ', with no seeders.'
            elif ratio < 0.3:
                tooltip += ', with much more leechers than seeders.'
            elif ratio < 1:
                tooltip += ', with more leechers than seeders.'
            elif ratio == sys.maxint:
                tooltip += ', with only seeders.'
            else:
                tooltip += ', with more seeders than leechers.'
        self.SetToolTipString(tooltip)
        
    def OnPaint(self, event):
        dc = wx.BufferedPaintDC(self)
        
        dc.SetBackground(wx.Brush(self.GetBackgroundColour()))
        dc.Clear()
        
        width, height = self.GetClientSize()
        width -= self.bordersize * 2
        width -= 1
        width -= width % 10
        width += 1
        
        if self.align == wx.ALIGN_CENTER:
            xpos = (self.GetClientSize()[0] - width) / 2
        elif self.align == wx.ALIGN_RIGHT:
            xpos = self.GetClientSize()[0] - width
        else:
            xpos = 0
            
        dc.SetPen(wx.Pen(self.GetParent().GetForegroundColour()))
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
        
        dc.SetPen(wx.BLACK_PEN)
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.DrawRectangle(xpos, 0, width, height)

    def OnEraseBackground(self, event):
        pass
