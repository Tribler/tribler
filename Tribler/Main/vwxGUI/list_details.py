# Written by Niels Zeilemaker, Egbert Bouman
import os
import sys
import re
from time import time
import logging
import copy
import wx
from StringIO import StringIO

from Tribler.Core.osutils import startfile
from Tribler.Core.simpledefs import (DLSTATUS_ALLOCATING_DISKSPACE, DLSTATUS_WAITING4HASHCHECK, DLSTATUS_HASHCHECKING,
                                     DLSTATUS_DOWNLOADING, DLSTATUS_SEEDING, DLSTATUS_STOPPED,
                                     DLSTATUS_STOPPED_ON_ERROR, DLSTATUS_METADATA, UPLOAD, DOWNLOAD, NTFY_TORRENTS,
                                     NTFY_VIDEO_ENDED, DLMODE_VOD)
from Tribler.Core.CacheDB.sqlitecachedb import forceDBThread
from Tribler.Core.Video.utils import videoextdefaults
from Tribler.Core.Video.VideoUtility import limit_resolution

from Tribler.community.channel.community import ChannelCommunity

from Tribler.Main.Utility.GuiDBTuples import Torrent, ChannelTorrent, CollectedTorrent, Channel, Playlist
from Tribler.Main.Utility.GuiDBHandler import GUI_PRI_DISPERSY, startWorker
from Tribler.Main.vwxGUI import (warnWxThread, forceWxThread, GRADIENT_LGREY, GRADIENT_DGREY,
                                 DEFAULT_BACKGROUND, FILTER_GREY, SEPARATOR_GREY,
                                 DOWNLOADING_COLOUR, SEEDING_COLOUR, TRIBLER_RED, LIST_LIGHTBLUE, format_time)
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.GuiImageManager import GuiImageManager
from Tribler.Main.vwxGUI.widgets import (LinkStaticText, EditText, SelectableListCtrl, _set_font,
                                         BetterText as StaticText, MaxBetterText, NotebookPanel, SimpleNotebook,
                                         ProgressButton, FancyPanel, TransparentText, LinkText, StaticBitmaps,
                                         TransparentStaticBitmap, Graph, ProgressBar)

from Tribler.Main.Utility.utility import eta_value, size_format, speed_format
from Tribler.community.tunnel import CIRCUIT_ID_PORT, CIRCUIT_TYPE_RENDEZVOUS, CIRCUIT_TYPE_RP


class AbstractDetails(FancyPanel):

    @warnWxThread
    def _create_tab(self, notebook, tabname, header=None, spacer=0, border=0):
        panel = wx.lib.scrolledpanel.ScrolledPanel(notebook)

        def OnChange():
            panel.Layout()
            panel.SetupScrolling(rate_y=5, scroll_x=False)
        panel.OnChange = OnChange

        themeColour = notebook.GetThemeBackgroundColour()
        if themeColour.IsOk():
            panel.SetBackgroundColour(themeColour)

        notebook.AddPage(panel, tabname)

        vSizer = wx.BoxSizer(wx.VERTICAL)
        panel.SetSizer(vSizer)

        if border:
            vSizer2 = wx.BoxSizer(wx.VERTICAL)
            vSizer.Add(vSizer2, 1, wx.EXPAND | wx.ALL, border)
            vSizer = vSizer2

        if header:
            header = self._add_header(panel, vSizer, header, spacer)
            panel.SetLabel = header.SetLabel

        return panel, vSizer

    @warnWxThread
    def _add_header(self, panel, sizer, header, spacer=0):
        header = wx.StaticText(panel, -1, header)
        _set_font(header, fontweight=wx.FONTWEIGHT_BOLD)

        sizer.Add(header, 0, wx.LEFT | wx.BOTTOM, spacer)
        return header

    @warnWxThread
    def _add_row(self, parent, sizer, name, value, spacer=0, flags=wx.EXPAND):
        nametext = name
        if name is not None:
            nametext = wx.StaticText(parent, -1, name)
            _set_font(nametext, fontweight=wx.FONTWEIGHT_BOLD)

            sizer.Add(nametext, 0, wx.LEFT, spacer)

        if value is not None:
            if isinstance(value, basestring):
                try:
                    value = MaxBetterText(parent, unicode(value), maxLines=3, name=name)
                except:
                    value = MaxBetterText(parent, value.decode('utf-8', 'ignore'), maxLines=3, name=name)
                value.SetMinSize((1, -1))
            sizer.Add(value, 0, flags | wx.LEFT, spacer)

        return nametext, value

    @warnWxThread
    def _add_subheader(self, parent, sizer, title, subtitle):
        title = wx.StaticText(parent, -1, title)
        _set_font(title, fontweight=wx.FONTWEIGHT_BOLD)

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

    @warnWxThread
    def __init__(self, parent):
        self._logger = logging.getLogger(self.__class__.__name__)

        FancyPanel.__init__(self, parent)
        self.Hide()

        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility

        self.parent = parent
        self.torrent = Torrent('0', '0', '', 0, 0, 0, 0, 0, None, False)
        self.torrent.torrent_db = self.guiutility.channelsearch_manager.torrent_db
        self.torrent.channelcast_db = self.guiutility.channelsearch_manager.channelcast_db

        self.state = -1
        self.timeouttimer = None

        self.SetBackgroundColour(GRADIENT_LGREY, GRADIENT_DGREY)
        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        self.notebook = SimpleNotebook(self, style=wx.NB_NOPAGETHEME, name="TorrentDetailsNotebook")
        self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.OnChange)
        self.vSizer.Add(self.notebook, 1, wx.EXPAND)
        self.SetSizer(self.vSizer)
        self.Layout()

        self.createMessagePanel()
        self.notebook.SetMessagePanel(self.messagePanel)

        self.doMark = self.guiutility.frame.selectedchannellist.OnMarkTorrent
        self.doSave = self.guiutility.frame.selectedchannellist.OnSaveTorrent
        self.canEdit = False
        self.canComment = False
        self.canMark = False
        self.showInfohash = False
        self.markWindow = None
        self.markings = None
        self.myMark = None
        self.isEditable = {}
        self.tracker_checks = {}

        self.guiutility.library_manager.add_download_state_callback(self.OnRefresh)

        self.createAllTabs()

        self.Show()
        self.DownloadStarted = lambda: None

    @forceWxThread
    def setTorrent(self, torrent):
        if torrent:
            if self.timeouttimer:
                self.timeouttimer.Stop()
                self.timeouttimer = None

            # Intermediate update
            self.messageText.SetLabel(
                'Loading details, please wait.\nTribler first needs to fetch the torrent file before this information can be accessed.')
            self.messageGauge.Show(False)
            self.messageButton.Show(False)
            self.messagePanel.Layout()
            self.torrent = torrent
            self.showTorrent(self.torrent)

            if self.guiutility.utility.session.has_collected_torrent(self.torrent.infohash):
                self.guiutility.torrentsearch_manager.loadTorrent(self.torrent, callback=self.showTorrent)
            else:
                def doGui(delayedResult):
                    requesttype = delayedResult.get()
                    if requesttype:
                        self.messageText.SetLabel(
                            'Loading details, please wait. The torrent file is requested %s.\nTribler first needs to fetch the torrent file before this information can be accessed.' % requesttype)
                        self.messageGauge.Show(True)
                        self.messageGauge.Pulse()
                        self.messagePanel.Layout()
                    self.timeouttimer = wx.CallLater(
                        10000, timeout) if not self.guiutility.frame.librarylist.IsShownOnScreen() else None

                def timeout():
                    # Avoid WxPyDeadObject exception
                    if not self:
                        return
                    self.messageText.SetLabel(
                        "Failed loading torrent.\nPlease click retry or wait to allow other peers to respond.")
                    self.messageGauge.Show(False)
                    self.messageButton.Show(True)
                    self.messagePanel.Layout()
                startWorker(doGui, self.guiutility.torrentsearch_manager.loadTorrent,
                            wargs=(self.torrent,), wkwargs={'callback': self.showTorrent})

    @forceWxThread
    def showTorrent(self, torrent, showTab=None):
        if self.torrent.infohash != torrent.infohash:
            return

        if isinstance(torrent, CollectedTorrent):
            self.guiutility.frame.top_bg.AddCollectedTorrent(torrent)

            def update():
                if not self:
                    return
                page = self.guiutility.GetSelectedPage()
                if page and hasattr(page, 'GetExpandedItems'):
                    for infohash, item in page.GetExpandedItems():
                        if infohash == torrent.infohash:
                            item.SetCollectedTorrent(torrent)
            wx.CallLater(1, update)

        self.state = -1
        self.torrent = torrent

        self.canEdit = False
        self.canComment = False
        self.canMark = False

        isChannelTorrent = isinstance(self.torrent, ChannelTorrent) or (
            isinstance(self.torrent, CollectedTorrent) and isinstance(self.torrent.torrent, ChannelTorrent))
        if isChannelTorrent and self.torrent.hasChannel():
            # This is a db call
            channel_state = self.torrent.channel.getState()

            if channel_state:
                state, _ = channel_state

                if isinstance(self, LibraryDetails):
                    self.canMark = state >= ChannelCommunity.CHANNEL_SEMI_OPEN
                else:
                    self.canEdit = state >= ChannelCommunity.CHANNEL_OPEN
                    self.canComment = state >= ChannelCommunity.CHANNEL_SEMI_OPEN

        self.updateAllTabs()

        self._Refresh(self.torrent.ds)

    def createMessagePanel(self):
        # Create messagePanel
        self.messagePanel = FancyPanel(self.notebook)
        self.messagePanel.SetBackgroundColour(GRADIENT_LGREY, GRADIENT_DGREY)
        self.messageIcon = TransparentStaticBitmap(self.messagePanel, -1, wx.ArtProvider.GetBitmap(wx.ART_INFORMATION))
        self.messageText = TransparentText(
            self.messagePanel, -1, "Loading details, please wait.\nTribler first needs to fetch the torrent file before this information can be accessed.")
        self.messageGauge = wx.Gauge(self.messagePanel, -1, size=(100, 15))
        self.messageButton = wx.Button(self.messagePanel, -1, "Retry")
        self.messageButton.Bind(wx.EVT_BUTTON, lambda evt: self.setTorrent(self.torrent))
        _set_font(self.messageText, size_increment=2, fontweight=wx.FONTWEIGHT_NORMAL)
        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.AddStretchSpacer()
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(self.messageIcon, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 15)
        hSizer.Add(self.messageText, 0, wx.ALL, 3)
        vSizer.Add(hSizer, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_CENTER_HORIZONTAL)
        vSizer.Add(self.messageGauge, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.TOP, 10)
        vSizer.Add(self.messageButton, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.TOP, 10)
        vSizer.AddStretchSpacer()
        self.messageGauge.Show(False)
        self.messageButton.Show(False)
        self.messagePanel.SetSizer(vSizer)

    def createAllTabs(self):
        self.Freeze()
        self.createDetailsTab()
        self.createFilesTab()
        self.createEditTab()
        self.createCommentsTab()
        self.createModificationsTab()
        self.createTrackersTab()
        self.Thaw()
        self.Layout()

        showTab = getattr(self.parent, self.__class__.__name__ + '_tab', None) if self.parent else None
        if showTab:
            for i in range(self.notebook.GetPageCount()):
                if self.notebook.GetPageText(i) == showTab:
                    self.notebook.SetSelection(i)
                    break
        else:
            self.notebook.SetSelection(0)

    def createDetailsTab(self):
        def OnToggleInfohash(event):
            self.showInfohash = not self.showInfohash
            self.updateDetailsTab()

        self.detailsTab, self.detailsSizer = self._create_tab(self.notebook, 'Torrent details', border=10)
        self.detailsTab.SetBackgroundColour(wx.WHITE)
        self.detailsTab.Bind(wx.EVT_LEFT_DCLICK, OnToggleInfohash)
        self.Freeze()

        fgSizer = wx.FlexGridSizer(0, 2, 3, 10)
        fgSizer.AddGrowableCol(1)
        titles = ['Name', 'Description', 'Status', 'Type', 'Uploaded', 'Filesize', 'Health']
        for title in titles:
            control1, control2 = self._add_row(self.detailsTab, fgSizer, title, '')
            setattr(self, title.lower() + '_title', control1)
            setattr(self, title.lower(), control2)

        # Add piece progress
        class tmp_object():

            def __init__(self, data, original_data):
                self.data = data
                self.original_data = original_data
        self.item = tmp_object(['', [0, 0], [0, 0], 0, 0], self.torrent)
        self.downloaded = ProgressPanel(self.detailsTab, self.item, show_bar=True, show_status=False)
        self.downloaded.SetMinSize((-1, 25))
        self.detailsSizer.Add(self.downloaded, 0, wx.EXPAND | wx.BOTTOM, 10)

        # Add infohash
        textCtrl = wx.TextCtrl(self.detailsTab, -1, '')
        textCtrl.SetEditable(False)
        self.infohash_title, self.infohash = self._add_row(self.detailsTab, fgSizer, "Infohash", textCtrl)

        # Add associated channel
        ulfont = self.GetFont()
        ulfont.SetUnderlined(True)
        link = LinkText(self.detailsTab, '', fonts=[
                        self.GetFont(), ulfont], colours=[self.GetForegroundColour(), wx.RED])
        link.SetBackgroundColour(self.detailsTab.GetBackgroundColour())
        link.Bind(wx.EVT_LEFT_UP, lambda evt: self.torrent.get('channel')
                  and self.guiutility.showChannel(self.torrent.channel))
        self.channel_title, self.channel = self._add_row(self.detailsTab, fgSizer, 'Channel', link, flags=0)

        # Add thumbnails
        self.thumbnails = StaticBitmaps(self.detailsTab, -1)
        self.thumbnails.SetBackgroundColour(self.detailsTab.GetBackgroundColour())
        self.thumbnails.SetBitmaps([])
        tSizer = wx.BoxSizer(wx.HORIZONTAL)
        tSizer.Add(fgSizer, 1, wx.ALIGN_LEFT | wx.ALIGN_TOP | wx.EXPAND)
        tSizer.Add(self.thumbnails, 0, wx.ALIGN_RIGHT | wx.ALIGN_TOP | wx.EXPAND)
        self.detailsSizer.Add(tSizer, 1, wx.EXPAND)
        self.thumbnails.Show(False)

        self.no_thumb_bitmap = wx.StaticBitmap(self.detailsTab, -1)
        bitmap = GuiImageManager.getInstance().drawBitmap("no-thumbnail",
                                                          (125, 100), self.no_thumb_bitmap.GetFont())
        self.no_thumb_bitmap.SetBitmap(bitmap)
        vsizer = wx.BoxSizer(wx.VERTICAL)
        vsizer.Add(self.no_thumb_bitmap, 1, wx.EXPAND)
        tSizer.Add(vsizer, 0, wx.EXPAND)

        # Add 'Mark this torrent' option
        self.marking_hSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.marking_vSizer = wx.BoxSizer(wx.VERTICAL)
        self.marking_vSizer.Add(
            wx.StaticLine(self.detailsTab, -1, style=wx.LI_HORIZONTAL), 0, wx.TOP | wx.BOTTOM | wx.EXPAND, 5)
        self.marking_vSizer.Add(self.marking_hSizer, 1, wx.EXPAND)
        self.markicon = GuiImageManager.getInstance().getBitmap(
            self, u"arrow", self.GetBackgroundColour(), state=0).ConvertToImage().Rotate90(False).ConvertToBitmap()
        self.markicon = wx.StaticBitmap(self.detailsTab, -1, self.markicon)
        ulfont = self.GetFont()
        ulfont.SetUnderlined(True)
        self.marktoggle = LinkText(self.detailsTab, 'Mark this torrent', fonts=[
                                   self.GetFont(), ulfont], colours=[self.GetForegroundColour(), wx.RED])
        self.marktoggle.SetBackgroundColour(self.detailsTab.GetBackgroundColour())
        self.marktoggle.Bind(wx.EVT_LEFT_UP, self.OnMark)
        self.marking_hSizer.AddStretchSpacer()
        self.marking_hSizer.Add(self.markicon, 0, wx.CENTER | wx.RIGHT, 3)
        self.marking_hSizer.Add(self.marktoggle)
        self.detailsSizer.Add(self.marking_vSizer, 0, wx.EXPAND)
        self.marking_vSizer.ShowItems(False)

        self.detailsTab.OnChange()
        self.detailsTab.Layout()

        self.Thaw()

    def createFilesTab(self):
        self.filesTab = wx.Panel(self.notebook)
        self.filesTab.SetBackgroundColour(wx.WHITE)

        self.filesList = SelectableListCtrl(self.filesTab)
        self.filesList.InsertColumn(0, 'Name')
        self.filesList.InsertColumn(1, 'Size', wx.LIST_FORMAT_RIGHT, 100)

        if isinstance(self, LibraryDetails):
            self.filesList.InsertColumn(2, 'Priority', wx.LIST_FORMAT_RIGHT)
            self.filesList.InsertColumn(3, 'Status', wx.LIST_FORMAT_RIGHT)

        self.filesList.Bind(wx.EVT_LEFT_DCLICK, self.OnDoubleClick)
        self.filesList.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnFilesSelected)
        self.filesList.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.OnFilesSelected)

        self.il = wx.ImageList(16, 16)
        self.play_img = self.il.Add(GuiImageManager.getInstance().getImage(u"file_video.png"))
        self.file_img = self.il.Add(GuiImageManager.getInstance().getImage(u"file_default.png"))
        self.filesList.SetImageList(self.il, wx.IMAGE_LIST_SMALL)

        self.filesList.setResizeColumn(0)
        # Calling SetColumnWidth seems to cause Refresh issues in list_body
        # self.filesList.SetColumnWidth(1, wx.LIST_AUTOSIZE)  # autosize only works after adding rows
        self.filesList.SetMinSize((1, -1))

        self.filesSizer = wx.BoxSizer(wx.VERTICAL)
        self.filesList.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.OnRightUp)
        self.filesSizer.Add(self.filesList, 1, wx.EXPAND | wx.LEFT | wx.TOP | wx.BOTTOM, 10)
        self.filesTab.SetSizer(self.filesSizer)
        self.notebook.AddPage(self.filesTab, "Files")

    def createEditTab(self):
        self.editTab, self.editSizer = self._create_tab(self.notebook, 'Edit', border=10)
        self.editTab.SetBackgroundColour(wx.WHITE)

        vSizer = wx.FlexGridSizer(0, 2, 3, 10)
        vSizer.AddGrowableCol(1)
        vSizer.AddGrowableRow(1)

        self.isEditable['name'] = EditText(self.editTab, '')
        self.isEditable['description'] = EditText(self.editTab, '', True)
        self.isEditable['description'].SetMinSize((1, 1))

        self._add_row(self.editTab, vSizer, "Name", self.isEditable['name'])
        self._add_row(self.editTab, vSizer, "Description", self.isEditable['description'])

        def save(event):
            self.doSave(self.torrent.channel, self)

            button = event.GetEventObject()
            button.Enable(False)
            wx.CallLater(5000, button.Enable, True)

        self.editButton = wx.Button(self.editTab, -1, "Save")
        self.editButton.Bind(wx.EVT_BUTTON, save)
        vSizer.Add((-1, -1), 0, wx.ALIGN_RIGHT)
        vSizer.Add(self.editButton, 0, wx.ALIGN_RIGHT)
        self.editSizer.Add(vSizer, 1, wx.EXPAND)

    def createCommentsTab(self):
        from Tribler.Main.vwxGUI.channel import CommentList
        self.commentList = NotebookPanel(self.notebook)
        self.commentList.SetList(
            CommentList(self.commentList, self.parent, canReply=True, quickPost=True, horizontal=True, noheader=True))

        def updateTitle(nrcomments):
            for i in range(self.notebook.GetPageCount()):
                if self.notebook.GetPageText(i).startswith('Comments'):
                    self.notebook.SetPageText(i, "Comments(%d)" % nrcomments)
        self.commentList.SetNrResults = updateTitle
        self.notebook.AddPage(self.commentList, 'Comments')

    def createModificationsTab(self):
        from channel import ModificationList
        self.modificationList = NotebookPanel(self.notebook)
        self.modificationList.SetList(ModificationList(self.modificationList, self.canEdit))

        def updateTitle(nrmodifications):
            for i in range(self.notebook.GetPageCount()):
                if self.notebook.GetPageText(i).startswith('Modifications'):
                    self.notebook.SetPageText(i, "Modifications(%d)" % nrmodifications)
        self.modificationList.SetNrResults = updateTitle
        self.notebook.AddPage(self.modificationList, 'Modifications', tab_colour=wx.WHITE)

    def createTrackersTab(self):
        self.trackerTab, self.trackerSizer = self._create_tab(self.notebook, "Trackers", border=10)
        self.trackerTab.SetBackgroundColour(wx.WHITE)

    def updateAllTabs(self):
        self.updateDetailsTab()
        self.updateFilesTab()
        self.updateEditTab()
        self.updateCommentsTab()
        self.updateModificationsTab()
        self.updateTrackersTab()

    def updateDetailsTab(self):
        self.Freeze()

        todo = []
        todo.append((self.name, self.torrent.name))
        todo.append((self.description, ''))
        todo.append((self.type, self.torrent.category.capitalize()
                    if isinstance(self.torrent.category, basestring) else 'Unknown'))
        todo.append((self.uploaded, self.torrent.formatCreationDate()
                    if hasattr(self.torrent, 'formatCreationDate') else ''))
        todo.append((self.filesize, '%s in %d file(s)' % (size_format(self.torrent.length), len(self.torrent.files))
                    if hasattr(self.torrent, 'files') else '%s' % size_format(self.torrent.length)))

        for control, new_value in todo:
            if control.GetLabel() != new_value:
                control.SetLabel(new_value)

        # Toggle piece progress
        self.downloaded.Update(torrent=self.torrent)
        self.downloaded.Show(bool(self.torrent.state))

        # Hide description
        self.description_title.Show(False)
        self.description.Show(False)
        self._updateDescription()

        # Toggle status
        show_status = bool(self.torrent.state) or bool(self.torrent.magnetstatus)
        self.status_title.Show(show_status)
        self.status.Show(show_status)

        # Toggle infohash
        if self.showInfohash:
            self.infohash.SetValue(self.torrent.infohash_as_hex)
        self.infohash_title.Show(self.showInfohash)
        self.infohash.Show(self.showInfohash)

        # Toggle associated channel
        show_channel = bool(self.torrent.get('channel', False))
        if show_channel:
            self.channel.SetLabel(self.torrent.channel.name)
        self.channel_title.Show(show_channel)
        self.channel.Show(show_channel)

        # Toggle thumbnails
        if self.torrent.metadata and 'thumb_hash' in self.torrent.metadata:
            show_thumbnails = True
            thumbnail_data = self.guiutility.utility.session.get_thumbnail_data(self.torrent.metadata['thumb_hash'])

            image = wx.EmptyImage()
            image.LoadStream(StringIO(thumbnail_data))
            bitmap = wx.BitmapFromImage(image)

            resolution = limit_resolution(bitmap.GetSize(), (175, 175))
            bitmaps = [bitmap.ConvertToImage().Scale(*resolution, quality=wx.IMAGE_QUALITY_HIGH).ConvertToBitmap()]
            self.thumbnails.SetBitmaps(bitmaps)

        else:
            show_thumbnails = False

        self.thumbnails.Show(show_thumbnails)
        self.no_thumb_bitmap.Show(not show_thumbnails)

        # Toggle 'Mark this torrent' option
        self.marking_vSizer.ShowItems(self.canComment)

        self.UpdateHealth()
        self.detailsTab.OnChange()
        self.detailsTab.Layout()

        self.Thaw()

    def _updateDescription(self):
        def set_description(widget_id, description):
            if not wx.FindWindowById(widget_id):
                return

            if not description:
                if self.canEdit:
                    description = 'No description yet, be the first to add a description.'
                else:
                    description = ''

            # Toggle description
            self.description.SetLabel(description)

            show_description = self.canEdit or bool(description)
            self.description_title.Show(show_description)
            self.description.Show(show_description)

        the_description = self.torrent.get('description', '')
        wid = self.GetId()
        if not the_description:
            metadata = self.torrent.get('metadata', None)
            if metadata:
                the_description = metadata.get('description', '')

        set_description(wid, the_description)

    def updateFilesTab(self):
        self.filesList.DeleteAllItems()

        if hasattr(self.torrent, 'files') and len(self.torrent.files) > 0:
            self.notebook.ShowMessageOnPage(self.notebook.GetIndexFromText('Files'), False)
            files = copy.copy(self.torrent.files)
            keywords = ' | '.join(self.guiutility.current_search_query)

            def sort_by_keywords(a, b):
                a_match = re.search(keywords, a[0].lower())
                b_match = re.search(keywords, b[0].lower())
                if a_match and not b_match:
                    return -1
                if b_match and not a_match:
                    return 1
                return cmp(a[0], b[0])

            files.sort(sort_by_keywords)

            for filename, size in files:
                try:
                    pos = self.filesList.InsertStringItem(sys.maxint, filename)
                except:
                    try:
                        pos = self.filesList.InsertStringItem(sys.maxint, filename.decode('utf-8', 'ignore'))
                    except:
                        self._logger.error("Could not format filename %s", self.torrent.name)
                self.filesList.SetItemData(pos, pos)

                size = "%.1f MB" % (size / 1048576.0)
                self.filesList.SetStringItem(pos, 1, size)

                if filename in self.torrent.videofiles:
                    self.filesList.SetItemColumnImage(pos, 0, self.play_img)
                else:
                    self.filesList.SetItemColumnImage(pos, 0, self.file_img)
        else:
            self.notebook.ShowMessageOnPage(self.notebook.GetIndexFromText('Files'), True)

    def updateEditTab(self):
        if self.canEdit:
            self.isEditable['name'].SetValue(self.torrent.name)
            self.isEditable['description'].SetValue(self.torrent.description or '')
        self.editButton.Enable(self.canEdit)
        self.notebook.ShowPage(self.notebook.GetIndexFromText('Edit'), self.canEdit)

    def updateCommentsTab(self):
        if self.canComment:
            commentManager = self.commentList.GetManager()
            commentManager.SetIds(self.torrent.channel, channeltorrent=self.torrent)
            commentManager.refresh()
        self.notebook.ShowPage(self.notebook.GetIndexFromText('Comments'), self.canComment)

    def updateModificationsTab(self):
        show_modifications = self.canEdit or bool(self.torrent.get('description', ''))
        if show_modifications:
            modificationManager = self.modificationList.GetManager()
            modificationManager.SetIds(self.torrent)
            modificationManager.refresh()
        self.notebook.ShowPage(self.notebook.GetIndexFromText('Modifications'), show_modifications)

    def updateTrackersTab(self):
        self.trackerSizer.Clear(deleteWindows=True)
        collected_trackers = hasattr(self.torrent, 'trackers')
        notcollected_trackers = hasattr(self.torrent, 'torrent') and hasattr(self.torrent.torrent, 'trackers')
        if collected_trackers or notcollected_trackers:
            self.notebook.ShowMessageOnPage(self.notebook.GetIndexFromText('Trackers'), False)
            if self.torrent.trackers and len(self.torrent.trackers) > 0:
                for tracker in (self.torrent.trackers if collected_trackers else self.torrent.torrent.trackers):
                    if isinstance(tracker, basestring):
                        self._add_row(self.trackerTab, self.trackerSizer, None, tracker)
                self.trackerSizer.Layout()
        else:
            self.notebook.ShowMessageOnPage(self.notebook.GetIndexFromText('Trackers'), True)

    @warnWxThread
    def ShowPanel(self, newState=None):
        if getattr(self, 'notebook', False):
            if newState is None:
                newState = self._GetState()

            if self.state != newState:
                self.state = newState

        else:
            # Additionally called by database event, thus we need to check if sizer exists(torrent is downloaded).
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

        setattr(self.parent, self.__class__.__name__ + '_tab', title)

        event.Skip()

    def OnCommentCreated(self, infohash):
        if self.torrent.infohash == infohash and self.canComment:
            manager = self.commentList.GetManager()
            manager.new_comment()

    def OnModificationCreated(self, channeltorrent_id):
        if self.canEdit:
            manager = self.modificationList.GetManager()
            manager.new_modification()

    def OnMarkingCreated(self, channeltorrent_id):
        if self.torrent.get('channeltorrent_id', False) == channeltorrent_id:
            self.UpdateMarkings()

    def UpdateMarkings(self):
        if self.torrent.get('channeltorrent_id', False):
            startWorker(self.ShowMarkings, self.guiutility.channelsearch_manager.getTorrentMarkings,
                        wargs=(self.torrent.channeltorrent_id,), priority=GUI_PRI_DISPERSY)

    @warnWxThread
    def ShowMarkings(self, delayedResult):
        markings = delayedResult.get()
        if len(markings) > 0:
            msg = 'This torrent is marked as:'
            for marktype, nr, myMark in markings:
                msg += ' %s (%d)' % (marktype, nr)
                if myMark:
                    self.myMark = marktype

            # see if we are updating
            if not self.markings:
                self.markings = MaxBetterText(self.detailsTab, unicode(msg), maxLines=3)
                self.markingSizer.Insert(0, self.markings)
            else:
                self.markings.SetLabel(msg)

            self.detailsSizer.Layout()

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
    def OnDoubleClick(self, event):
        selected = self.filesList.GetFirstSelected()
        playable_files = self.torrent.videofiles

        if selected != -1:
            selected_file = self.filesList.GetItemText(selected)
            if selected_file in playable_files:
                self.guiutility.library_manager.playTorrent(self.torrent.infohash, selected_file)

            elif self.torrent.progress == 1:  # not playable, but are we complete?
                file = self._GetPath(selected_file)
                if os.path.isfile(file):
                    startfile(file)

    @warnWxThread
    def OnRightUp(self, event):
        if not self.torrent or not self.torrent.ds or not self.torrent.ds.download:
            return
        download = self.torrent.ds.download

        selection = []
        index = self.filesList.GetFirstSelected()
        selection.append(index)
        while len(selection) != self.filesList.GetSelectedItemCount():
            index = self.filesList.GetNextSelected(index)
            selection.append(index)

        selection = set([self.filesList.GetItem(index, 0).GetText() for index in selection])
        selected_files = set(download.get_selected_files()) or set(download.get_def().get_files_as_unicode())

        selected_files_includable = selection - selected_files
        selected_files_excludable = selection & selected_files

        if not selected_files_includable and not selected_files_excludable:
            return

        menu = wx.Menu()

        menuitems = [("Include", [], False), ("Exclude", [], False)]

        if selected_files_includable:
            files = list(selected_files | selected_files_includable)
            menuitems[0] = ("Include", files, True)

        if selected_files_excludable:
            files = list(selected_files - selected_files_excludable)
            # Don't allow excluding everything
            if files:
                menuitems[1] = ("Exclude", files, True)

        for label, files, enabled in menuitems:
            itemid = wx.NewId()
            menu.Append(itemid, label)
            menu.Enable(itemid, enabled)
            if enabled:
                menu.Bind(wx.EVT_MENU, lambda evt, d=download, f=files: d.set_selected_files(f), id=itemid)

        self.PopupMenu(menu, self.ScreenToClient(wx.GetMousePosition()))
        menu.Destroy()

        self.old_progress = None

    @warnWxThread
    def _GetPath(self, file=None):
        ds = self.torrent.ds
        if ds:
            destdirs = ds.get_download().get_dest_files()
            if file:
                for filenameintorrent, path in destdirs:
                    if filenameintorrent == file:
                        return path

            return os.path.commonprefix([os.path.split(path)[0] for _, path in destdirs])

    @warnWxThread
    def OnFilesSelected(self, event):
        pass

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
            menu.Bind(wx.EVT_MENU, lambda x, selected=mark: self.doMark(
                self.torrent.channel, self.torrent.infohash, unicode(selected)), id=itemid)

        pos = wx.Point(self.markicon.GetPosition().x, self.marktoggle.GetPosition().y + self.marktoggle.GetSize().y)
        self.detailsTab.PopupMenu(menu, pos)
        menu.Destroy()

    @warnWxThread
    def RefreshData(self, data):
        if isinstance(self.torrent, Torrent):
            curTorrent = self.torrent
        else:
            curTorrent = self.torrent.torrent

        newTorrent = data[2]

        if curTorrent.infohash != newTorrent.infohash:
            return

        self.torrent.updateSwarminfo(newTorrent.swarminfo)
        self.torrent.update_torrent_id(newTorrent.torrent_id)

        if not curTorrent.exactCopy(newTorrent):
            # replace current torrent
            curTorrent.name = newTorrent.name
            curTorrent.length = newTorrent.length
            curTorrent.category = newTorrent.category
            curTorrent.status = newTorrent.status

            self.updateDetailsTab()
            if self.canEdit:
                if not self.isEditable['name'].IsChanged():
                    self.isEditable['name'].SetValue(curTorrent.name)

                if not self.isEditable['description'].IsChanged():
                    self.isEditable['description'].SetValue(curTorrent.description or '')

    @forceDBThread
    def UpdateHealth(self):
        if not (self and self.torrent and self.torrent.swarminfo):
            return

        if getattr(self.torrent, 'trackers', None) and len(self.torrent.trackers) > 0:
            # touch swarminfo property
            _, _, last_successful_check = self.torrent.swarminfo
            last_check = self.tracker_checks.get(self.torrent.infohash, 0)
            now = time()

            if now - last_successful_check > 1800 and now - last_check > 300:
                self.utility.session.check_torrent_health(self.torrent.infohash)
                self.ShowHealth(True)
                self.tracker_checks[self.torrent.infohash] = now
            else:
                self.ShowHealth(False)
        else:
            self.ShowHealth(False, ', no trackers found')

    @forceWxThread
    def ShowHealth(self, updating, no_update_reason=''):
        if not self:
            return
        if isinstance(self.torrent, CollectedTorrent):
            updating = ', updating now' if updating else no_update_reason

            num_seeders, num_leechers, last_check = self.torrent.swarminfo
            diff = time() - last_check

            if num_seeders < 0 and num_leechers < 0:
                if self.torrent.status == 'good':
                    self.health.SetLabel("Unknown, but found peers in the DHT")
                else:
                    self.health.SetLabel("Unknown" + updating)
            else:
                if diff < 5:
                    self.health.SetLabel("%s seeders, %s leechers (current)" % (num_seeders, num_leechers))
                else:
                    updated = eta_value(diff, 2)
                    if updated == '<unknown>':
                        self.health.SetLabel("%s seeders, %s leechers" % (num_seeders, num_leechers) + updating)
                    else:
                        self.health.SetLabel("%s seeders, %s leechers (updated %s ago%s)" % (
                            num_seeders, num_leechers, updated, updating))

        else:
            self.health.SetLabel("Unknown")

    def OnRefresh(self, dslist, magnetlist):
        found = False

        if self and self.torrent:  # avoid pydeadobject error
            for ds in dslist:
                if self.torrent.addDs(ds):
                    found = True

            self.torrent.magnetstatus = magnetlist.get(self.torrent.infohash, None)

            if not found:
                self.torrent.clearDs()
            self._Refresh()

    @warnWxThread
    def _Refresh(self, ds=None):
        if ds:
            self.torrent.addDs(ds)

        state = self._GetState()

        if state != self.state:
            self.ShowPanel(state)

        if state in [TorrentDetails.INCOMPLETE, TorrentDetails.INCOMPLETE_INACTIVE, TorrentDetails.VOD, TorrentDetails.FINISHED]:
            self.updateDetailsTab()

        if self.status_title.IsShown() != (bool(self.torrent.state) or bool(self.torrent.magnetstatus)):
            self.updateDetailsTab()
        self.UpdateStatus()

    def UpdateStatus(self):
        ds = self.torrent.ds
        progress = ds.get_progress() if ds else 0
        statusflag = ds.get_status() if ds else DLSTATUS_STOPPED
        finished = progress == 1.0
        is_vod = ds.get_download().get_mode() == DLMODE_VOD if ds else False
        status = None

        if self.torrent.magnetstatus or statusflag == DLSTATUS_METADATA:
            status = 'Torrent file is being downloaded from the DHT'
        elif statusflag == DLSTATUS_SEEDING:
            uls = ds.get_current_speed('up')
            status = 'Seeding @ %s, ratio: %.3f' % (speed_format(uls), ds.seeding_ratio)
        elif finished:
            status = 'Completed'
        elif statusflag in [DLSTATUS_ALLOCATING_DISKSPACE, DLSTATUS_WAITING4HASHCHECK]:
            status = 'Waiting'
        elif statusflag == DLSTATUS_HASHCHECKING:
            status = 'Checking'
        elif statusflag == DLSTATUS_DOWNLOADING:
            dls = ds.get_current_speed('down')
            status = 'Streaming' if is_vod else 'Downloading'
            status += ' @ %s' % speed_format(dls)
        elif statusflag == DLSTATUS_STOPPED:
            status = 'Stopped'

        if status and not finished and self.torrent.progress and statusflag in [DLSTATUS_DOWNLOADING, DLSTATUS_STOPPED]:
            status += " (%.1f%%)" % (self.torrent.progress * 100)

        if status:
            self.status.SetLabel(status)

    def _GetState(self):
        active = vod = False

        progress = self.torrent.progress
        finished = progress == 1.0

        ds = self.torrent.ds
        if ds:
            if finished:  # finished download
                active = ds.get_status() == DLSTATUS_SEEDING

            else:  # active download
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

    @warnWxThread
    def Layout(self):
        returnValue = wx.Panel.Layout(self)

        # force setupscrolling for scrollpages, if constructed while not shown this is required.
        for i in range(self.notebook.GetPageCount()):
            page = self.notebook.GetPage(i)
            page.Layout()

            if getattr(page, 'SetupScrolling', False):
                page.SetupScrolling(scroll_x=False)

        return returnValue

    @warnWxThread
    def __del__(self):
        self._logger.debug("TorrentDetails: destroying %s", self.torrent['name'])
        self.guiutility.library_manager.remove_download_state_callback(self.OnRefresh)

        if self.markWindow:
            self.markWindow.Show(False)
            self.markWindow.Destroy()


class LibraryDetails(TorrentDetails):

    @warnWxThread
    def __init__(self, parent):
        self._logger = logging.getLogger(self.__class__.__name__)

        self.old_progress = -1
        self.old_tracker_status = {}
        self.refresh_counter = 0
        self.bw_history = []

        self.gui_image_manager = GuiImageManager.getInstance()

        TorrentDetails.__init__(self, parent)

    def getHashes(self):
        hashes = []
        if self.torrent:
            if self.torrent.infohash:
                hashes.append(self.torrent.infohash)
        return hashes

    def setTorrent(self, torrent, bw_history=[]):
        # Arno, 2012-07-17: Retrieving peerlist for the DownloadStates takes CPU
        # so only do it when needed for display.
        self.guiutility.library_manager.set_want_peers(self.getHashes(), enable=False)

        self.old_progress = -1
        self.bw_history = bw_history
        TorrentDetails.setTorrent(self, torrent)

        self.guiutility.library_manager.set_want_peers(self.getHashes(), enable=True)

    def createAllTabs(self):
        self.Freeze()
        self.createDetailsTab()
        self.createFilesTab()
        self.createEditTab()
        self.createCommentsTab()
        self.createModificationsTab()
        self.createTrackersTab()
        self.createPeersTab()
        self.createSpeedTab()
        self.createNetworkGraphTab()
        self.Thaw()
        self.Layout()

        showTab = getattr(self.parent, self.__class__.__name__ + '_tab', None) if self.parent else None
        if showTab:
            for i in range(self.notebook.GetPageCount()):
                if self.notebook.GetPageText(i) == showTab:
                    self.notebook.SetSelection(i)
                    break
        else:
            self.notebook.SetSelection(0)

    def createFilesTab(self):
        TorrentDetails.createFilesTab(self)

        self.filesFooter = wx.BoxSizer(wx.VERTICAL)
        self.filesFooter.Add(wx.StaticLine(self.filesTab, -1, style=wx.LI_HORIZONTAL), 0, wx.EXPAND | wx.ALL, 3)
        self.filesFooter.Add(
            wx.StaticText(self.filesTab, -1, 'Right click to include/exclude selected file(s). Use ctrl+a to select all/deselect all.'), 1, wx.EXPAND)
        self.filesSizer.Add(self.filesFooter, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 6)
        self.filesSizer.AddSpacer((-1, 3))

    def createPeersTab(self):
        self.peersTab = wx.Panel(self.notebook)
        self.peersTab.SetBackgroundColour(DEFAULT_BACKGROUND)
        self.peersSizer = wx.BoxSizer(wx.VERTICAL)

        self.peerList = SelectableListCtrl(self.peersTab, tooltip=False)
        self.peerList.InsertColumn(0, 'IP-address')
        self.peerList.InsertColumn(1, 'Progress', wx.LIST_FORMAT_RIGHT)
        self.peerList.InsertColumn(2, 'Traffic', wx.LIST_FORMAT_RIGHT)
        self.peerList.InsertColumn(3, 'State', wx.LIST_FORMAT_RIGHT)
        self.peerList.InsertColumn(4, 'ID', wx.LIST_FORMAT_RIGHT)
        self.peerList.setResizeColumn(0)
        tt_string = "States:" + (" " * 75 if sys.platform == 'win32' else "")
        tt_string += "\nO\t\toptimistic unchoked\nUI\t\tgot interested\nUC\t\tupload chocked\nUQ\t\tgot request\nUBL\t\tsending data\nUE\t\tupload eligable\nDI\t\tsend interested\nDC\t\tdownload chocked\nS\t\tis snubbed\nL\t\toutgoing connection\nR\t\tincoming connection"
        self.peerList.SetToolTipString(tt_string)
        self.peersTab.il = wx.ImageList(16, 11)
        self.peerList.SetImageList(self.peersTab.il, wx.IMAGE_LIST_SMALL)
        self.peersSizer.Add(self.peerList, 1, wx.EXPAND | wx.LEFT | wx.TOP | wx.BOTTOM, 10)

        self.country_to_index = {}
        for code, flag in self.gui_image_manager.getCountryFlagDict().iteritems():
            self.country_to_index[code] = self.peersTab.il.Add(flag)

        self.country_to_index['hidden_services'] = self.peersTab.il.Add(self.gui_image_manager.getImage(u"lock.png"))

        self.availability_hSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.availability = StaticText(self.peersTab)
        self.pieces = StaticText(self.peersTab)

        self._add_row(self.peersTab, self.availability_hSizer, 'Availability', self.availability, spacer=3)
        self.availability_hSizer.AddSpacer((4, -1))
        self._add_row(self.peersTab, self.availability_hSizer, 'Pieces', self.pieces, spacer=3)

        self.availability_vSizer = wx.BoxSizer(wx.VERTICAL)
        self.availability_vSizer.Add(wx.StaticLine(self.peersTab, -1, style=wx.LI_HORIZONTAL), 0, wx.EXPAND | wx.ALL, 3)
        self.availability_vSizer.Add(self.availability_hSizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 3)

        self.peersSizer.Add(self.availability_vSizer, 0, wx.EXPAND)

        self.peersTab.SetSizer(self.peersSizer)
        self.notebook.InsertPage(2, self.peersTab, "Peers")

    def createTrackersTab(self):
        self.trackersTab = wx.Panel(self.notebook)
        self.trackersTab.SetBackgroundColour(DEFAULT_BACKGROUND)
        self.trackersSizer = wx.BoxSizer(wx.VERTICAL)

        self.trackersList = SelectableListCtrl(self.trackersTab, tooltip=False)
        self.trackersList.InsertColumn(0, 'Name')
        self.trackersList.InsertColumn(1, 'Status', wx.LIST_FORMAT_LEFT, 300)
        self.trackersList.InsertColumn(2, 'Peers', wx.LIST_FORMAT_RIGHT, 100)
        self.trackersList.setResizeColumn(0)

        self.trackersSizer.Add(self.trackersList, 1, wx.EXPAND)

        self.trackersTab.SetSizer(self.trackersSizer)
        self.notebook.AddPage(self.trackersTab, "Trackers")

    def createSpeedTab(self):
        self.speedPanel = Graph(self.notebook)
        self.speedPanel.SetAxisLabels('Time (5 second update interval)', 'kB/s')
        self.speedPanel.SetMaxPoints(120)
        self.speedPanel.AddGraph(wx.Colour(0, 162, 232), [bw[1] for bw in self.bw_history], "Download speed")
        self.speedPanel.AddGraph(wx.Colour(163, 73, 164), [bw[0] for bw in self.bw_history], "Upload speed")
        self.notebook.AddPage(self.speedPanel, "Speed")

    def createNetworkGraphTab(self):
        from Tribler.Main.vwxGUI.home import NetworkGraphPanel
        self.networkgraphPanel = NetworkGraphPanel(self.notebook, fullscreen=False)
        self.notebook.AddPage(self.networkgraphPanel, "Network graph")

    def updateAllTabs(self):
        self.updateDetailsTab()
        self.updateFilesTab()
        self.updateEditTab()
        self.updateCommentsTab()
        self.updateModificationsTab()
        self.updateTrackersTab()
        self.updatePeersTab()
        self.updateSpeedTab()
        self.updateNetworkGraphTab()

    def updateFilesTab(self):
        self.filesList.DeleteAllItems()

        if hasattr(self.torrent, 'files') and len(self.torrent.files) > 0:
            self.notebook.ShowMessageOnPage(self.notebook.GetIndexFromText('Files'), False)
            files = copy.copy(self.torrent.files)
            if self.torrent.ds:
                selected_files = self.torrent.ds.get_selected_files()
                if selected_files:
                    def sort_by_selected_name(a, b):
                        aSelected = a[0] in selected_files
                        bSelected = b[0] in selected_files

                        if aSelected != bSelected:
                            if aSelected:
                                return -1
                            return 1

                        return cmp(a[0], b[0])
                    files.sort(sort_by_selected_name)

            for filename, size in files:
                try:
                    pos = self.filesList.InsertStringItem(sys.maxint, filename)
                except:
                    try:
                        pos = self.filesList.InsertStringItem(sys.maxint, filename.decode('utf-8', 'ignore'))
                    except:
                        self._logger.error("Could not format filename %s", self.torrent.name)
                self.filesList.SetItemData(pos, pos)

                size = "%.1f MB" % (size / 1048576.0)
                self.filesList.SetStringItem(pos, 1, size)

                if filename in self.torrent.videofiles:
                    self.filesList.SetItemColumnImage(pos, 0, self.play_img)
                else:
                    self.filesList.SetItemColumnImage(pos, 0, self.file_img)

                self.filesList.SetStringItem(pos, 2, '')
        else:
            self.notebook.ShowMessageOnPage(self.notebook.GetIndexFromText('Files'), True)

    def updatePeersTab(self):
        ds = self.torrent.ds if self.torrent else None
        finished = self.torrent.get('progress', 0) == 100 or (ds and ds.get_progress() == 1.0)
        self.availability_vSizer.ShowItems(not finished)

    def updateTrackersTab(self):
        ds = self.torrent.ds if self.torrent else None
        self.trackersList.DeleteAllItems()
        if not ds:
            collected_trackers = hasattr(self.torrent, 'trackers')
            notcollected_trackers = hasattr(self.torrent, 'torrent') and hasattr(self.torrent.torrent, 'trackers')

            if collected_trackers or notcollected_trackers:
                for tracker in (self.torrent.trackers if collected_trackers else self.torrent.torrent.trackers):
                    if isinstance(tracker, basestring):
                        self.trackersList.Append([tracker, 'Not contacted yet', 0])

    def updateSpeedTab(self):
        if self.bw_history:
            self.speedPanel.SetData(0, [bw[1] for bw in self.bw_history])
            self.speedPanel.SetData(1, [bw[0] for bw in self.bw_history])

    def updateNetworkGraphTab(self):
        self.networkgraphPanel.ShowTunnels(self.torrent.ds.get_download().get_hops() if self.torrent.ds else False)

    @warnWxThread
    def ShowPanel(self, newState=None):
        if newState and newState != self.state:
            self.state = newState

    @warnWxThread
    def _Refresh(self, ds=None):
        TorrentDetails._Refresh(self, ds)

        self.refresh_counter += 1
        if self.refresh_counter % 5 == 0:
            self.speedPanel.AppendData(0, self.torrent.ds.get_current_speed(DOWNLOAD) / 1024 if self.torrent.ds else 0)
            self.speedPanel.AppendData(1, self.torrent.ds.get_current_speed(UPLOAD) / 1024 if self.torrent.ds else 0)

        # register callback for peerlist update
        self.peerList.Freeze()

        ds = self.torrent.ds
        index = 0
        if ds:
            peers = ds.get_peerlist()

            def downsort(a, b):
                if a.get('downrate', 0) != b.get('downrate', 0):
                    return a.get('downrate', 0) - b.get('downrate', 0)
                return a.get('uprate', 0) - b.get('uprate', 0)
            peers.sort(downsort, reverse=True)

            for peer_dict in peers:
                peer_name = peer_dict['ip'] + ':%d' % peer_dict['port']
                image_index = self.country_to_index.get(peer_dict.get('country', '00').lower(), -1)
                # If this is a hidden services circuit, show a different icon
                tc = self.utility.session.lm.tunnel_community
                if tc and peer_dict['port'] == CIRCUIT_ID_PORT:
                    cid = tc.ip_to_circuit_id(peer_dict['ip'])
                    if cid in tc.circuits and tc.circuits[cid].ctype in [CIRCUIT_TYPE_RENDEZVOUS, CIRCUIT_TYPE_RP]:
                        image_index = self.country_to_index['hidden_services']
                        peer_name = 'Darknet circuit ID %d' % cid

                connection_type = peer_dict.get('connection_type', 0)
                if connection_type == 1:
                    peer_name += ' [WebSeed]'
                elif connection_type == 2:
                    peer_name += ' [HTTP Seed]'
                elif connection_type == 3:
                    peer_name += ' [uTP]'

                if index < self.peerList.GetItemCount():
                    self.peerList.SetStringItem(index, 0, peer_name)
                else:
                    self.peerList.InsertStringItem(index, peer_name)

                if image_index != -1:
                    self.peerList.SetItemColumnImage(index, 0, image_index)

                self.peerList.SetStringItem(index, 1, '%d%%' % (peer_dict.get('completed', 0) * 100.0))

                traffic = ""
                traffic += speed_format(peer_dict.get('downrate', 0)) + u"\u2193 "
                traffic += speed_format(peer_dict.get('uprate', 0)) + u"\u2191"
                self.peerList.SetStringItem(index, 2, traffic.strip())

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
                self.peerList.SetStringItem(index, 3, state)

                if 'extended_version' in peer_dict:
                    try:
                        self.peerList.SetStringItem(index, 4, peer_dict['extended_version'].decode('ascii'))
                    except:
                        try:
                            self.peerList.SetStringItem(
                                index, 4, peer_dict['extended_version'].decode('utf-8', 'ignore'))
                        except:
                            self._logger.error("Could not format peer client version")
                else:
                    self.peerList.SetStringItem(index, 4, '')

                index += 1

            if self.availability:
                self.availability.SetLabel("%.2f" % ds.get_availability())
                self.pieces.SetLabel("total %d, have %d" % ds.get_pieces_total_complete())

                self.availability_vSizer.Layout()

            dsprogress = ds.get_progress()
            # Niels: 28-08-2012 rounding to prevent updating too many times
            dsprogress = long(dsprogress * 1000) / 1000.0
            if self.old_progress != dsprogress and self.filesList.GetItemCount() > 0:
                completion = {}

                useSimple = self.filesList.GetItemCount() > 100
                selected_files = ds.get_download().get_selected_files()
                if useSimple:
                    if selected_files:
                        for i in range(self.filesList.GetItemCount()):
                            file = self.filesList.GetItem(i, 0).GetText()
                            if file in selected_files:
                                completion[file] = dsprogress
                    else:
                        for i in range(self.filesList.GetItemCount()):
                            completion[self.filesList.GetItem(i, 0).GetText()] = dsprogress
                else:
                    for file, progress in ds.get_files_completion():
                        completion[file] = progress

                for i in range(self.filesList.GetItemCount()):
                    listfile = self.filesList.GetItem(i, 0).GetText()

                    if listfile in selected_files or not selected_files:
                        self.filesList.SetStringItem(i, 2, 'Included')
                    else:
                        self.filesList.SetStringItem(i, 2, 'Excluded')

                    progress = completion.get(listfile, None)
                    if isinstance(progress, float) or isinstance(progress, int):
                        self.filesList.SetStringItem(i, 3, "%.2f%%" % (progress * 100))

                self.old_progress = dsprogress

        if index == 0:
            self.peerList.DeleteAllItems()
        else:
            while index < self.peerList.GetItemCount():
                self.peerList.DeleteItem(index)
                index += 1

        self.peerList.SetColumnWidth(1, wx.LIST_AUTOSIZE)
        self.peerList.SetColumnWidth(2, wx.LIST_AUTOSIZE)
        self.peerList.SetColumnWidth(3, wx.LIST_AUTOSIZE)
        self.peerList.SetColumnWidth(4, wx.LIST_AUTOSIZE)
        self.peerList._doResize()
        self.peerList.Thaw()

        # Tracker status
        ds = self.torrent.ds if self.torrent else None
        if ds:
            new_tracker_status = ds.get_tracker_status()
            if self.old_tracker_status != new_tracker_status:
                self.trackersList.Freeze()

                # Remove items that aren't in the tracker_status dict
                for i in range(self.trackersList.GetItemCount() - 1, -1, -1):
                    if self.trackersList.GetItem(i, 0).GetText() not in new_tracker_status:
                        self.trackersList.DeleteItem(i)

                # Update list
                items = [self.trackersList.GetItem(i, 0).GetText() for i in range(self.trackersList.GetItemCount())]
                tracker_status_items = [(url.decode('utf-8', 'replace').encode('ascii', "ignore"), info)
                                        for url, info in ds.get_tracker_status().items()]

                for url, info in sorted(tracker_status_items):
                    num_peers, status = info
                    if url in items:
                        self.trackersList.SetStringItem(items.index(url), 1, status)
                        self.trackersList.SetStringItem(items.index(url), 2, str(num_peers))
                    else:
                        self.trackersList.Append([url, status, num_peers])

                self.trackersList.Thaw()
                self.old_tracker_status = new_tracker_status

    def __del__(self):
        TorrentDetails.__del__(self)
        self.guiutility.library_manager.set_want_peers(self.getHashes(), enable=False)


class ChannelDetails(AbstractDetails):

    def __init__(self, parent):
        FancyPanel.__init__(self, parent)
        self.Hide()

        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility

        self.parent = parent
        self.channel = None

        self.SetBackgroundColour(GRADIENT_LGREY, GRADIENT_DGREY)
        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        self.notebook = SimpleNotebook(self, style=wx.NB_NOPAGETHEME, name="ChannelDetailsNotebook")
        self.vSizer.Add(self.notebook, 1, wx.EXPAND)
        self.SetSizer(self.vSizer)
        self.Layout()

        self.createAllTabs()

        self.Show()

    @forceWxThread
    def showChannel(self, channel):
        self.channel = channel
        self.updateAllTabs()
        self.Layout()

    def createAllTabs(self):
        self.Freeze()

        self.detailsTab, self.detailsSizer = self._create_tab(self.notebook, 'Channel details', border=10)
        self.detailsTab.SetBackgroundColour(wx.WHITE)

        fgSizer = wx.FlexGridSizer(0, 2, 3, 10)

        titles = ['Name', 'Description', 'Torrents', 'Latest update', 'Favorite votes']
        for title in titles:
            control1, control2 = self._add_row(self.detailsTab, fgSizer, title, '')
            control1_name = title.lower().replace(' ', '') + '_title'
            control2_name = title.lower().replace(' ', '')
            setattr(self, control1_name, control1)
            setattr(self, control2_name, control2)
        
        fgSizer.AddGrowableCol(1)

        self.detailsSizer.Add(fgSizer, 1, wx.EXPAND)
        self.detailsTab.Layout()

        self.Thaw()
        self.Layout()

        self.notebook.SetSelection(0)

    def updateAllTabs(self):
        self.Freeze()

        todo = []
        todo.append((self.name, self.channel.name))
        if self.channel.description:
            todo.append((self.description, self.channel.description))
        todo.append((self.torrents, str(self.channel.nr_torrents)))
        todo.append((self.latestupdate, format_time(self.channel.modified)))
        todo.append((self.favoritevotes, str(self.channel.nr_favorites)))

        for control, new_value in todo:
            if control.GetLabel() != new_value:
                control.SetLabel(new_value)

        self.description.Show(bool(self.channel.description))
        self.description_title.Show(bool(self.channel.description))

        self.detailsTab.Layout()

        self.Thaw()

    @warnWxThread
    def RefreshData(self, data):
        if isinstance(self.channel, Channel):
            self.channel.name = data[2].name
            self.channel.description = data[2].description
            self.channel.nr_torrents = data[2].nr_torrents
            self.channel.modified = data[2].modified
            self.channel.nr_favorites = data[2].nr_favorites

        self.updateAllTabs()


class PlaylistDetails(AbstractDetails):

    def __init__(self, parent):
        FancyPanel.__init__(self, parent)
        self.Hide()

        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility

        self.parent = parent
        self.playlist = None
        self.playlist_torrents = None

        self.SetBackgroundColour(GRADIENT_LGREY, GRADIENT_DGREY)
        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        self.notebook = SimpleNotebook(self, style=wx.NB_NOPAGETHEME, name="PlaylistDetailsNotebook")
        self.vSizer.Add(self.notebook, 1, wx.EXPAND)
        self.SetSizer(self.vSizer)
        self.Layout()

        self.createAllTabs()

        self.Show()

    @forceWxThread
    def showPlaylist(self, playlist):
        self.playlist = playlist
        self.playlist_torrents = None
        self.updateAllTabs()
        self.Layout()

    def createAllTabs(self):
        self.Freeze()

        self.detailsTab, self.detailsSizer = self._create_tab(self.notebook, 'Playlist details', border=10)
        self.detailsTab.SetBackgroundColour(wx.WHITE)

        fgSizer = wx.FlexGridSizer(0, 2, 3, 10)

        titles = ['Name', 'Description', 'Torrents']
        for title in titles:
            control1, control2 = self._add_row(self.detailsTab, fgSizer, title, '')
            setattr(self, title.lower() + '_title', control1)
            setattr(self, title.lower(), control2)

        # Add thumbnails
        self.thumbnails = wx.Panel(self.detailsTab, -1)
        self.thumbnails.SetBackgroundColour(self.detailsTab.GetBackgroundColour())
        fgThumbSizer = wx.FlexGridSizer(2, 2, 5, 5)
        hThumbSizer = wx.BoxSizer(wx.HORIZONTAL)
        hThumbSizer.Add(fgThumbSizer, 1, 0)
        self.smallthumbs = []
        for _ in range(4):
            sbmp = wx.StaticBitmap(self.thumbnails, -1)
            self.smallthumbs.append(sbmp)
            fgThumbSizer.Add(sbmp, 0, 0)
        self.bigthumb = StaticBitmaps(self.thumbnails, -1)
        hThumbSizer.AddSpacer((5, -1))
        hThumbSizer.Add(self.bigthumb, 1, 0)
        self.thumbnails.SetSizer(hThumbSizer)

        tSizer = wx.BoxSizer(wx.HORIZONTAL)
        tSizer.Add(fgSizer, 1, wx.ALIGN_LEFT | wx.ALIGN_TOP | wx.EXPAND)
        tSizer.Add(self.thumbnails, 0, wx.ALIGN_RIGHT | wx.ALIGN_TOP | wx.EXPAND)
        self.detailsSizer.Add(tSizer, 1, wx.EXPAND)
        self.thumbnails.Show(False)
        
        fgSizer.AddGrowableCol(1)

        self.detailsTab.Layout()

        self.Thaw()
        self.Layout()

        self.notebook.SetSelection(0)

    def updateAllTabs(self):
        self.Freeze()

        todo = []
        todo.append((self.name, self.playlist.name))
        if self.playlist.description:
            todo.append((self.description, self.playlist.description))
        todo.append((self.torrents, str(self.playlist.nr_torrents)))

        for control, new_value in todo:
            if control.GetLabel() != new_value:
                control.SetLabel(new_value)

        self.description.Show(bool(self.playlist.description))
        self.description_title.Show(bool(self.playlist.description))

        # Reset old thumbnails
        self.bigthumb.SetBitmaps([])
        for sbmp in self.smallthumbs:
            sbmp.SetBitmap(wx.NullBitmap)

        # Set new thumbnails
        if self.playlist and self.playlist.nr_torrents > 0:
            if self.playlist_torrents is None:
                def do_db():
                    from Tribler.Main.vwxGUI.SearchGridManager import ChannelManager
                    return ChannelManager.getInstance().getTorrentsFromPlaylist(self.playlist)[2]

                def do_gui(delayedResult):
                    self.playlist_torrents = delayedResult.get()
                    bmps = []
                    for torrent in self.playlist_torrents:
                        if torrent.metadata:
                            thumbnail_data = self.guiutility.utility.session.get_thumbnail_data(torrent.metadata['thumb_hash'])

                            img = wx.EmptyImage()
                            img.LoadStream(StringIO(thumbnail_data))
                            bitmap = wx.BitmapFromImage(img)

                            bmps.append(bitmap)

                        if len(bmps) > 3:
                            break

                    if bmps:
                        self.thumbnails.Show(True)
                        self.Freeze()
                        res_large = limit_resolution(bmps[0].GetSize(), (175, 175))
                        res_small = limit_resolution(bmps[0].GetSize(), (85, 85))

                        bmps_large = [bmp.ConvertToImage().Scale(*res_large, quality=wx.IMAGE_QUALITY_HIGH).ConvertToBitmap()
                                      for bmp in bmps if bmp.IsOk()]
                        bmps_small = [bmp.ConvertToImage().Scale(*res_small, quality=wx.IMAGE_QUALITY_HIGH).ConvertToBitmap()
                                      for bmp in bmps if bmp.IsOk()]

                        self.bigthumb.SetBitmaps(bmps_large)
                        for i, sbmp in enumerate(self.smallthumbs):
                            if i < len(bmps_small):
                                sbmp.SetBitmap(bmps_small[i])
                        self.thumbnails.Layout()
                        self.detailsTab.Layout()
                        self.Thaw()

                startWorker(do_gui, do_db, retryOnBusy=True, priority=GUI_PRI_DISPERSY)

        self.detailsTab.Layout()

        self.Thaw()

    @warnWxThread
    def RefreshData(self, data):
        if isinstance(self.playlist, Playlist):
            self.playlist.name = data[2].name
            self.playlist.description = data[2].description
            self.playlist.nr_torrents = data[2].nr_torrents

        self.updateAllTabs()


class AbstractInfoPanel(FancyPanel):

    def __init__(self, parent):
        FancyPanel.__init__(self, parent)
        self.Hide()

        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility

        self.parent = parent
        self.SetBackgroundColour(GRADIENT_LGREY, GRADIENT_DGREY)

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
        self.dialogSizer.Add(self.buttonSizer, 0, wx.EXPAND | wx.TOP, 15)
        self.dialogSizer.AddStretchSpacer()

        self.messageSizer.Add(self.textSizer, 0, 0)

        self.buttonSizer.AddStretchSpacer()

        for colour, height in [(SEPARATOR_GREY, 1), (FILTER_GREY, 23), (SEPARATOR_GREY, 1)]:
            panel = wx.Panel(self)
            panel.SetMinSize((-1, height))
            panel.SetBackgroundColour(colour)
            self.topSizer.Add(panel, 0, wx.EXPAND)
        self.topSizer.Add(self.mainSizer, 1, wx.EXPAND)
        self.SetSizer(self.topSizer)
        self.Layout()

    def AddMessage(self, message, colour=wx.Colour(50, 50, 50), bold=False):
        if not self.textSizer.GetChildren():
            self.messageSizer.Insert(0, TransparentStaticBitmap(
                self, -1, wx.ArtProvider.GetBitmap(wx.ART_INFORMATION)), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 15)

        message = TransparentText(self, -1, message)
        _set_font(message, size_increment=2, fontcolour=colour,
                  fontweight=wx.FONTWEIGHT_NORMAL if not bold else wx.FONTWEIGHT_BOLD)
        self.textSizer.Add(message, 0, wx.ALIGN_CENTER_VERTICAL)

        self.Layout()

    def AddButton(self, label, handler, icon=None):
        if handler is None or label is None:
            return

        button = ProgressButton(self, -1, label)
        button.Bind(wx.EVT_LEFT_UP, handler)
        if icon:
            button.SetIcon(icon)
        self.buttonSizer.Add(button, 0, wx.LEFT, 15)
        self.Layout()

    def Clear(self):
        self.messageSizer.Clear(deleteWindows=True)
        self.textSizer = wx.BoxSizer(wx.VERTICAL)
        self.messageSizer.Add(self.textSizer, 0, 0)
        self.buttonSizer.Clear(deleteWindows=True)


class SearchInfoPanel(AbstractInfoPanel):

    def Set(self, num_items):
        self.Show(False)
        self.Clear()
        self.AddMessage('A channel is a collection of torrents made by users to share their favorite torrents.')
        self.AddMessage('Channels may contain torrents associated with your search.')
        if num_items > 0:
            self.AddMessage('Please click on a channel or a torrent for more details.')
        self.Show(True)


class ChannelInfoPanel(AbstractInfoPanel):

    def Set(self, num_items, is_favourite):
        self.Show(False)
        self.Clear()
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
        self.Show(False)
        self.Clear()
        if num_items > 0:
            self.AddMessage('Please select a torrent for more details.')
        self.Show(True)


class PlaylistInfoPanel(AbstractInfoPanel):

    def Set(self, num_items, is_favourite):
        self.Show(False)
        self.Clear()
        if is_favourite == True:
            self.AddMessage('You are looking at the full content of this playlist.')
        elif is_favourite == False:
            self.AddMessage(
                'You are looking at a preview of this playlist. To see more of it, mark the channel as favorite.')
        if num_items > 0:
            self.AddMessage('Please click on a torrent for more details.')
        self.Show(True)


class SelectedchannelInfoPanel(AbstractInfoPanel):

    def Set(self, num_items, vote, channelstate, iamModerator):
        self.Show(False)
        self.Clear()
        explicit_vote = vote != 0
        preview = not explicit_vote and not iamModerator
        open2edit = channelstate == ChannelCommunity.CHANNEL_CLOSED and iamModerator
        allow2edit = vote == 2 and channelstate == ChannelCommunity.CHANNEL_OPEN

        if preview:
            self.AddMessage(
                "You are looking at a preview of this channel. If you want to see more of it, \"Mark it as Favorite\".")

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
    # eta style
    ETA_DEFAULT = 1
    ETA_EXTENDED = 2

    def __init__(self, parent, item, style=ETA_DEFAULT, show_bar=True, show_status=True):
        wx.BoxSizer.__init__(self, wx.VERTICAL)
        self.item = item
        self.style = style
        self.show_bar = show_bar
        self.show_status = show_status
        guiutility = GUIUtility.getInstance()
        self.utility = guiutility.utility

        # self.AddStretchSpacer()
        if show_bar:
            self.pb = ProgressBar(parent, colours=["#ffffff", DOWNLOADING_COLOUR, SEEDING_COLOUR])
            self.pb.SetMaxSize((-1, -1))
            self.Add(self.pb, 1, wx.EXPAND)
        if show_status:
            self.status = StaticText(parent)
            self.Add(self.status, 0, wx.EXPAND)

        # self.AddStretchSpacer()
        wx.CallLater(100, self.Update)

    def Show(self, show):
        self.ShowItems(show)

    def Update(self, ds=None, torrent=None):
        # return_val, 0 == inactive, 1 == incomplete, 2 == complete/seeding
        return_val = 0

        if ds is None:
            if torrent:
                ds = torrent.ds
            else:
                ds = self.item.original_data.get('ds', None)

        if ds is not None:
            progress = ds.get_progress()
            size = ds.get_length()

            seeds, peers = ds.get_num_seeds_peers()

            dls = ds.get_current_speed('down')
            uls = ds.get_current_speed('up')

            eta = ds.get_eta()
            status = ds.get_status()

        else:
            progress = self.item.original_data.get('progress')
            if progress is None:
                progress = 0
            size = self.item.original_data.get('length', False)

            seeds = peers = None
            dls = uls = 0

            eta = ''
            status = DLSTATUS_STOPPED

        if seeds is None:
            seeds = 0
        if peers is None:
            peers = 0

        progress = max(0, min(1, progress))  # progress has to be between 0 and 1

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
                    eta += "(%0.1f%%)" % (progress * 100)

            elif status == DLSTATUS_DOWNLOADING:
                sizestr = ''
                if size:
                    size_progress = size * progress

                    def format_size(bytes):
                        if bytes > 1073741824:
                            return size_format(bytes, 1)
                        return size_format(bytes, 0)
                    sizestr = '%s/%s (%0.1f%%)' % (format_size(size_progress), format_size(size), progress * 100)

                eta = eta_value(eta, truncate=2)
                if eta == '' or eta.find('unknown') != -1:
                    eta = sizestr

                    if self.show_status and self.style == ProgressPanel.ETA_DEFAULT and dls == 0 and uls == 0 and ds:
                        if ds.get_num_con_initiated() > 0:
                            eta += ' - connecting'

                            nrdots = (self.status.GetLabel()[-3:].count('.') + 1) % 4
                            eta += '.' * nrdots

                else:
                    eta = sizestr + ' - ' + eta

                return_val = 1
            else:
                eta = 'Incomplete, inactive (%0.1f%%)' % (progress * 100)

        if self.style == ProgressPanel.ETA_EXTENDED:
            if status == DLSTATUS_SEEDING:
                upSpeed = " @ " + speed_format(uls)
                eta += upSpeed
            elif status == DLSTATUS_DOWNLOADING:
                dlSpeed = " @ " + speed_format(dls)
                eta += dlSpeed

        # Update eta
        if self.show_status and self.status.GetLabel() != eta:
            self.status.SetLabel(eta)
            self.status.Refresh()

        if self.show_bar:
            if not status in [DLSTATUS_WAITING4HASHCHECK, DLSTATUS_ALLOCATING_DISKSPACE, DLSTATUS_HASHCHECKING] and ds:
                havedigest = ds.get_pieces_complete()
            else:
                havedigest = None

            # Update graph
            if finished:
                self.pb.reset(colour=2)  # Show as complete
            elif havedigest:
                self.pb.set_pieces(havedigest)
            elif progress > 0:
                self.pb.setNormalPercentage(progress)  # Show as having some
            else:
                self.pb.reset(colour=0)  # Show as having none
            self.pb.Refresh()

        return return_val


class MyChannelPlaylist(AbstractDetails):

    def __init__(self, parent, on_manage, can_edit=False, on_save=None, on_remove=None, playlist={}):
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
            self.name = EditText(self, playlist.get('name', ''))
            self.name.SetMaxLength(40)

            self.description = EditText(self, playlist.get('description', ''), multiline=True)
            self.description.SetMaxLength(2000)
        else:
            self.name = StaticText(self, -1, playlist.get('name', ''))
            self.description = StaticText(self, -1, playlist.get('description', ''))

            self.name.SetMinSize((1, -1))
            self.description.SetMinSize((1, -1))

        self._add_row(self, gridSizer, 'Name', self.name)
        self._add_row(self, gridSizer, 'Description', self.description)
        vSizer.Add(gridSizer, 1, wx.EXPAND | wx.ALL, 3)

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

            vSizer.Add(hSizer, 0, wx.ALIGN_RIGHT | wx.ALL, 3)
        else:
            vSizer.Add(manage, 0, wx.ALIGN_RIGHT | wx.ALL, 3)

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

            return name != self.playlist.get('name', '') or description != self.playlist.get('description', '')
        return False


class ChannelsExpandedPanel(wx.Panel):

    def __init__(self, parent, size=wx.DefaultSize):
        wx.Panel.__init__(self, parent, size=size, style=wx.NO_BORDER)
        self.guiutility = GUIUtility.getInstance()
        self.fg_colour = self.GetForegroundColour()
        self.manager = self.guiutility.frame.channellist.GetManager()
        self.channel_category = None
        self.channel_or_playlist = None
        self.AddComponents()
        self.SetBackgroundColour(parent.GetBackgroundColour())
        self.Bind(wx.EVT_SHOW, self.OnShow)
        wx.CallAfter(self.AddCurrentChannelLink)

    def AddComponents(self):
        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.hSizer.Add(self.vSizer, 1, wx.EXPAND | wx.LEFT, 20)

        self.links = {}
        for name in ['All', 'Favorites', 'My Channel']:
            link = LinkStaticText(self, name, icon=None, font_colour=TRIBLER_RED if name == 'All' else self.fg_colour)
            link.Bind(wx.EVT_LEFT_UP, self.OnCategory)
            self.links[name] = link
            self.vSizer.Add(link, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)

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
        elif isinstance(self.channel_or_playlist, Playlist) and 'playlist' in self.links:
            self.links['playlist'].SetForegroundColour(TRIBLER_RED)
        elif isinstance(self.channel_or_playlist, Channel) and 'channel' in self.links:
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
                return ""

            def CreateLinkStaticText():
                link = LinkStaticText(self, '', icon=None, font_colour=self.fg_colour)
                link_icon = GuiImageManager.getInstance().getBitmap(self, u"arrow", self.GetBackgroundColour(), state=0)
                link_icon = link_icon.ConvertToImage().Rotate90(False).ConvertToBitmap()
                link_icon = wx.StaticBitmap(self, -1, link_icon)
                link.Insert(0, link_icon, 0, wx.CENTER | wx.RIGHT, 3)
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
            self.links['channel'].SetLabel(
                DetermineText(channel.name, self.GetSize()[0] - self.links['channel'].text.GetPosition()[0]))
            self.vSizer.Insert(2 if channel.isFavorite() else 1, self.links[
                               'channel'], 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 2)

            if isinstance(channel_or_playlist, Playlist):
                self.links['playlist'].ShowItems(True)
                self.links['playlist'].Bind(wx.EVT_LEFT_UP, lambda evt: self.OnHistory(evt, channel_or_playlist))
                self.links['playlist'].SetLabel(
                    DetermineText(channel_or_playlist.name, self.GetSize()[0] - self.links['playlist'].text.GetPosition()[0]))
                self.vSizer.Insert(3 if channel_or_playlist.channel.isFavorite() else 2, self.links[
                                   'playlist'], 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 10)
            else:
                self.links['playlist'].ShowItems(False)

            self.vSizer.Layout()
            self.channel_or_playlist = channel_or_playlist
            self.SetTextHighlight()
            self.guiutility.frame.actlist.Layout()

    def GetCategory(self):
        cat = self.channel_category
        if not cat and self.manager.category:
            if self.manager.category in ["Popular", "New", "Updated"]:
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


class VideoplayerExpandedPanel(wx.lib.scrolledpanel.ScrolledPanel):

    def __init__(self, parent):
        wx.lib.scrolledpanel.ScrolledPanel.__init__(self, parent, style=wx.NO_BORDER)

        self.guiutility = GUIUtility.getInstance()
        self.library_manager = self.guiutility.library_manager
        self.torrentsearch_manager = self.guiutility.torrentsearch_manager

        self.tdef = None
        self.fileindex = -1
        self.message = None

        self.close_icon = GuiImageManager.getInstance().getImage(u"close.png")
        self.fg_colour = self.GetForegroundColour()
        self.bg_colour = LIST_LIGHTBLUE
        self.SetBackgroundColour(self.bg_colour)
        self.AddComponents()

        self.guiutility.utility.session.add_observer(self.OnVideoEnded, NTFY_TORRENTS, [NTFY_VIDEO_ENDED])

    def AddComponents(self):
        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.hSizer.Add(self.vSizer, 1, wx.EXPAND | wx.LEFT, 20)
        self.links = []
        self.SetSizer(self.hSizer)
        self.Layout()

    def AddLinks(self):
        def DetermineText(linktext, text):
            for i in xrange(len(text), 0, -1):
                newText = text[0:i]
                if i != len(text):
                    newText += ".."
                width, _ = linktext.GetTextExtent(newText)
                if width <= 140:
                    return newText
            return ""

        self.links = []
        files = self.tdef.get_files_as_unicode()
        videofiles = self.tdef.get_files_as_unicode(exts=videoextdefaults)
        for filename in sorted(files):
            if filename in videofiles:
                fileindex = files.index(filename)
                link = LinkStaticText(
                    self, filename, icon=None, font_colour=TRIBLER_RED if fileindex == self.fileindex else self.fg_colour)
                link.SetBackgroundColour(self.bg_colour)
                link.SetLabel(DetermineText(link.text, filename))
                link.Bind(wx.EVT_MOUSE_EVENTS, self.OnLinkStaticTextMouseEvent)
                link.SetToolTipString(filename)
                link_close = wx.StaticBitmap(self, -1, self.close_icon)
                link_close.Show(False)
                link_close.Bind(wx.EVT_LEFT_UP, lambda evt, i=fileindex: self.RemoveFileindex(i))
                link.Add(link_close, 0, wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.RIGHT, 2)
                link.fileindex = fileindex
                self.links.append(link)
                self.vSizer.Add(link, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)

        self.OnChange()
        self.GetParent().parent_list.parent_list.Layout()

    def UpdateComponents(self):
        self.Freeze()
        self.vSizer.Clear(deleteWindows=True)
        self.links = []
        if not self.message:
            self.AddLinks()
        else:
            label, show_animation = self.message
            text = wx.StaticText(self, -1, label)
            sizer = wx.BoxSizer(wx.HORIZONTAL)
            sizer.Add(text, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
            if show_animation:
                ag = wx.animate.GIFAnimationCtrl(self, -1,
                                                 os.path.join(self.guiutility.vwxGUI_path, 'images', 'search_new.gif'))
                ag.Play()
                sizer.Add(ag, 0, wx.ALIGN_CENTER_VERTICAL)
            sizer.AddStretchSpacer()
            self.vSizer.Add(sizer, 1, wx.EXPAND)
        self.Layout()
        self.OnChange()
        self.Thaw()

    @forceWxThread
    def SetTorrentDef(self, tdef, fileindex=-1):
        if self.tdef != tdef and self.fileindex != fileindex:
            self.tdef = tdef
            self.fileindex = fileindex
            self.message = None
            self.UpdateComponents()

    @forceWxThread
    def SetMessage(self, message, show_animation=False):
        if self.message != (message, show_animation):
            self.tdef = None
            self.fileindex = -1
            self.message = (message, show_animation)
            self.UpdateComponents()

    @forceWxThread
    def Reset(self):
        self.tdef = None
        self.fileindex = -1
        self.message = None
        self.links = []
        self.vSizer.Clear(deleteWindows=True)
        self.Layout()
        self.OnChange()

    def RemoveFileindex(self, fileindex):
        for index, link in reversed(list(enumerate(self.links))):
            if link.fileindex == fileindex:
                self.links.pop(index)
                link.ShowItems(False)
                link.Clear(deleteWindows=True)
                self.vSizer.Remove(link)
                self.OnChange()

        vod_dl = self.guiutility.videoplayer.get_vod_download()
        if vod_dl and vod_dl.get_vod_fileindex() == fileindex:
            self.library_manager.stopTorrent(self.tdef.get_infohash())
            self.library_manager.last_vod_torrent = None

    def SetNrFiles(self, nr):
        videoplayer_item = self.guiutility.frame.actlist.GetItem(5)
        num_items = getattr(videoplayer_item, 'num_items', None)
        if num_items and self.guiutility.frame.videoparentpanel:
            num_items.SetValue(str(nr))
            num_items.Show(bool(nr))
            videoplayer_item.hSizer.Layout()

    def DoHighlight(self):
        for control in self.links:
            if control.fileindex == self.fileindex:
                control.SetForegroundColour(TRIBLER_RED)
            else:
                control.SetForegroundColour(self.fg_colour)

    def OnChange(self):
        self.Freeze()

        max_height = self.guiutility.frame.actlist.GetSize().y - self.GetParent().GetPosition()[1] * 1.25 - 4
        virtual_height = sum([link.text.GetSize()[1]
                             for link in self.links]) if self.links else (30 if self.message else 0)
        best_height = min(max_height, virtual_height)
        self.SetMinSize((-1, best_height))
        self.GetParent().parent_list.Layout()
        self.SetupScrolling(scroll_x=False, scroll_y=True)
        self.SetNrFiles(len(self.links))

        self.Thaw()

    def OnLinkStaticTextMouseEvent(self, event):
        link = event.GetEventObject()
        if event.LeftDown():
            self.dragging = link
        elif event.LeftUp():
            destination = None
            source = self.dragging
            self.dragging = None
            for l in self.links:
                if l.text.GetScreenRect().Contains(wx.GetMousePosition()):
                    destination = l

            if source and destination and source != destination:
                source_index = self.links.index(source)
                destination_index = self.links.index(destination)
                self.links.pop(source_index)
                self.links.insert(destination_index, source)
                self.vSizer.Detach(source)
                self.vSizer.Insert(destination_index, source, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
                self.Layout()
                return
            else:
                self.fileindex = link.fileindex
                self.DoHighlight()
                # This needs to be in a CallAfter, or VLC may crash.
                wx.CallAfter(lambda: self.library_manager.playTorrent(
                    self.tdef.get_infohash(), self.tdef.get_files_as_unicode()[self.fileindex]))

        for link in self.links:
            mousepos = wx.GetMousePosition()
            show = link.GetItem(0).GetWindow().GetScreenRect().Contains(mousepos) or \
                link.GetItem(1).GetWindow().GetScreenRect().Contains(mousepos)
            wx.BoxSizer.Show(link, 1, show)
        event.Skip()

    @forceWxThread
    def OnVideoEnded(self, subject, changeType, torrent_tuple):
        infohash, fileindex = torrent_tuple

        if not self.tdef or self.tdef.get_infohash() != infohash:
            return

        for index, control in enumerate(self.links):
            if control and control.fileindex == fileindex:
                control.SetForegroundColour(self.fg_colour)
                if index + 1 < len(self.links):
                    control_next = self.links[index + 1]
                    control_next.SetForegroundColour(TRIBLER_RED)
                    self.fileindex = control_next.fileindex
                    self.DoHighlight()
                    self.library_manager.playTorrent(
                        self.tdef.get_infohash(), self.tdef.get_files_as_unicode()[control_next.fileindex])
