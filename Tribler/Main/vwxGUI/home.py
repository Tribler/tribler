# Written by Niels Zeilemaker
import wx
import sys
import os
import logging
import binascii
from time import strftime
from traceback import print_exc

from Tribler.Category.Category import Category
from Tribler.Core.simpledefs import NTFY_TORRENTS, NTFY_INSERT
from Tribler.Core.Session import Session
from Tribler.Core.CacheDB.SqliteCacheDBHandler import MiscDBHandler, \
    TorrentDBHandler, ChannelCastDBHandler
from Tribler.Core.RemoteTorrentHandler import RemoteTorrentHandler

from Tribler.Main.vwxGUI import SEPARATOR_GREY, DEFAULT_BACKGROUND
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility, forceWxThread
from Tribler.Main.Utility.GuiDBHandler import startWorker, GUI_PRI_DISPERSY
from Tribler.Main.vwxGUI.list_header import DetailHeader
from Tribler.Main.vwxGUI.list_body import ListBody
from Tribler.Main.vwxGUI.list_item import ThumbnailListItemNoTorrent
from Tribler.Main.vwxGUI.list_footer import ListFooter
from Tribler.Main.vwxGUI.widgets import SelectableListCtrl, \
    TextCtrlAutoComplete, BetterText as StaticText, LinkStaticText


class Home(wx.Panel):

    def __init__(self, parent):
        wx.Panel.__init__(self, parent)
        self.guiutility = GUIUtility.getInstance()

        self.SetBackgroundColour(DEFAULT_BACKGROUND)

        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.AddStretchSpacer()

        text = StaticText(self, -1, "Tribler")
        font = text.GetFont()
        font.SetPointSize(font.GetPointSize() * 3)
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        text.SetForegroundColour((255, 51, 0))
        text.SetFont(font)

        textSizer = wx.FlexGridSizer(2, 2, 3, 7)
        if sys.platform == 'darwin':  # mac
            self.searchBox = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        else:
            self.searchBox = TextCtrlAutoComplete(self, entrycallback=parent.top_bg.complete, selectcallback=parent.top_bg.OnAutoComplete)

        font = self.searchBox.GetFont()
        font.SetPointSize(font.GetPointSize() * 2)
        self.searchBox.SetFont(font)
        self.searchBox.Bind(wx.EVT_TEXT_ENTER, self.OnSearchKeyDown)

        if sys.platform == 'darwin':  # mac
            self.searchBox.SetMinSize((450, self.searchBox.GetTextExtent('T')[1] + 5))
        else:
            self.searchBox.SetMinSize((450, -1))
        self.searchBox.SetFocus()

        textSizer.Add(text, 0, wx.EXPAND | wx.RIGHT, 7)
        scalingSizer = wx.BoxSizer(wx.HORIZONTAL)
        scalingSizer.Add(self.searchBox)

        if sys.platform == 'darwin':  # mac
            searchButton = wx.Button(self, -1, '\n')
            searchButton.SetLabel('Search')
        else:
            searchButton = wx.Button(self, -1, 'Search')
        searchButton.Bind(wx.EVT_BUTTON, self.OnClick)

        scalingSizer.Add(searchButton, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 3)

        textSizer.Add(scalingSizer, 0, wx.ALIGN_CENTER_VERTICAL)
        textSizer.AddSpacer((1, 1))

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(StaticText(self, -1, "Take me to "))
        channelLink = LinkStaticText(self, "channels", icon=None)

        channelLink.Bind(wx.EVT_LEFT_UP, self.OnChannels)
        hSizer.Add(channelLink)
        hSizer.Add(StaticText(self, -1, " to see what others are sharing"))
        textSizer.Add(hSizer)

        vSizer.Add(textSizer, 0, wx.ALIGN_CENTER)
        vSizer.AddStretchSpacer()

        self.aw_panel = ArtworkPanel(self)
        self.aw_panel.SetMinSize((-1, 275))
        self.aw_panel.Show(self.guiutility.ReadGuiSetting('show_artwork', True))
        vSizer.Add(self.aw_panel, 0, wx.EXPAND)

        self.SetSizer(vSizer)
        self.Layout()

        self.Bind(wx.EVT_RIGHT_UP, self.OnRightClick)
        self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy, self)

        self.SearchFocus()

    def OnDestroy(self, event):
        print >> sys.stderr, "+++ Home OnDestroy()"

    def OnRightClick(self, event):
        menu = wx.Menu()
        itemid = wx.NewId()
        menu.AppendCheckItem(itemid, 'Show recent videos')
        menu.Check(itemid, self.aw_panel.IsShown())

        def toggleArtwork(event):
            show = not self.aw_panel.IsShown()
            self.aw_panel.Show(show)
            self.guiutility.WriteGuiSetting("show_artwork", show)
            self.Layout()

        menu.Bind(wx.EVT_MENU, toggleArtwork, id=itemid)

        if menu:
            self.PopupMenu(menu, self.ScreenToClient(wx.GetMousePosition()))
            menu.Destroy()

    def OnClick(self, event):
        term = self.searchBox.GetValue()
        self.guiutility.dosearch(term)

    def OnSearchKeyDown(self, event):
        self.OnClick(event)

    def OnChannels(self, event):
        self.guiutility.showChannels()

    def ResetSearchBox(self):
        self.searchBox.Clear()

    def SearchFocus(self):
        self.searchBox.SetFocus()
        self.searchBox.SelectAll()


class Stats(wx.Panel):

    def __init__(self, parent):
        wx.Panel.__init__(self, parent)

        self._logger = logging.getLogger(self.__class__.__name__)

        self.guiutility = GUIUtility.getInstance()
        self.createTimer = None
        self.isReady = False

    def _DoInit(self):
        self.SetBackgroundColour(DEFAULT_BACKGROUND)
        vSizer = wx.BoxSizer(wx.VERTICAL)

        self.dowserStatus = StaticText(self, -1, 'Dowser is not running')
        self.dowserButton = wx.Button(self, -1, 'Start dowser')
        self.dowserButton.Bind(wx.EVT_BUTTON, self.OnDowser)
        self.memdumpButton = wx.Button(self, -1, 'Dump memory')
        self.memdumpButton.Bind(wx.EVT_BUTTON, self.OnMemdump)

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(self.dowserStatus, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 3)
        hSizer.Add(self.dowserButton)
        hSizer.Add(self.memdumpButton, 0, wx.RIGHT, 3)
        vSizer.Add(hSizer, 0, wx.ALIGN_RIGHT | wx.TOP | wx.BOTTOM, 3)

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.__dispersy_frame_btn = wx.Button(self, -1, "Open Dispersy Debug Frame")
        self.__dispersy_frame_btn.Bind(wx.EVT_BUTTON, self.OnOpenDispersyDebugButtonClicked)
        hSizer.Add(self.__dispersy_frame_btn, 0, wx.EXPAND, 3)
        vSizer.Add(hSizer, 0, wx.EXPAND | wx.BOTTOM, 3)

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(NetworkPanel(self), 1, wx.EXPAND | wx.RIGHT, 7)
        self.activity = ActivityPanel(self)
        hSizer.Add(self.activity, 1, wx.EXPAND)
        vSizer.Add(hSizer, 1, wx.EXPAND)

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(NewTorrentPanel(self), 1, wx.EXPAND | wx.RIGHT, 7)
        hSizer.Add(PopularTorrentPanel(self), 1, wx.EXPAND, 7)
        vSizer.Add(hSizer, 1, wx.EXPAND)

        self.SetSizer(vSizer)
        self.Layout()

        self.Bind(wx.EVT_KEY_UP, self.onKey)
        if sys.platform.startswith('win'):
            # on Windows, the panel doesn't respond to keypresses
            self.Bind(wx.EVT_MOUSE_EVENTS, self.onMouse)

        self.isReady = True

    def OnOpenDispersyDebugButtonClicked(self, event):
        self.guiutility.frame.OnOpenDebugFrame(None)

    def onActivity(self, msg):
        if self.isReady:
            self.activity.onActivity(msg)

    def onKey(self, event):
        if event.ControlDown() and (event.GetKeyCode() == 73 or event.GetKeyCode() == 105):  # ctrl + i
            self._showInspectionTool()

        elif event.ControlDown() and (event.GetKeyCode() == 68 or event.GetKeyCode() == 100):  # ctrl + d
            self._printDBStats()
        else:
            event.Skip()

    def onMouse(self, event):
        if all([event.RightUp(), event.ControlDown(), event.AltDown(), event.ShiftDown()]):
            self._showInspectionTool()

        elif all([event.LeftUp(), event.ControlDown(), event.AltDown(), event.ShiftDown()]):
            self._printDBStats()

        else:
            event.Skip()

    def OnDowser(self, event):
        if self.dowserStatus.GetLabel() == 'Dowser is running':
            self._stopDowser()
        else:
            if not self._startDowser():
                dlg = wx.DirDialog(None, "Please select your dowser installation directory", style=wx.wx.DD_DIR_MUST_EXIST)
                if dlg.ShowModal() == wx.ID_OK and os.path.isdir(dlg.GetPath()):
                    sys.path.append(dlg.GetPath())
                    self._startDowser()

                dlg.Destroy()

    def OnMemdump(self, event):
        from meliae import scanner
        scanner.dump_all_objects("memory-dump.out")

    def _startDowser(self):
        try:
            import cherrypy
            import dowser
            cherrypy.config.update({'server.socket_port': 8080})
            cherrypy.tree.mount(dowser.Root())
            cherrypy.engine.start()

            self.dowserButton.SetLabel('Stop dowser')
            self.dowserStatus.SetLabel('Dowser is running')
            return True

        except:
            print_exc()
            return False

    def _stopDowser(self):
        try:
            import cherrypy
            cherrypy.engine.stop()

            self.dowserButton.SetLabel('Start dowser')
            self.dowserStatus.SetLabel('Dowser is not running')
            return True

        except:
            print_exc()
            return False

    def _showInspectionTool(self):
        import wx.lib.inspection
        itool = wx.lib.inspection.InspectionTool()
        itool.Show()
        try:
            frame = itool._frame

            import Tribler
            frame.locals['Tribler'] = Tribler

            session = Session.get_instance()
            frame.locals['session'] = session
            frame.locals['dispersy'] = session.lm.dispersy

        except Exception:
            import traceback
            traceback.print_exc()

    def _printDBStats(self):
        torrentdb = TorrentDBHandler.getInstance()
        tables = torrentdb._db.fetchall("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        for table, in tables:
            self._logger.info("%s %s", table, torrentdb._db.fetchone("SELECT COUNT(*) FROM %s" % table))

    def Show(self, show=True):
        if show:
            if not self.isReady:
                self._DoInit()

        wx.Panel.Show(self, show)


class HomePanel(wx.Panel):

    def __init__(self, parent, title, background, hspacer=(0, 0), vspacer=(0, 0)):
        wx.Panel.__init__(self, parent)

        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility
        self.SetBackgroundColour(background)
        self.SetForegroundColour(parent.GetForegroundColour())

        spacerFlags = 0
        if hspacer[0]:
            spacerFlags |= wx.LEFT
        if hspacer[1]:
            spacerFlags |= wx.RIGHT
        spacer = max(hspacer)

        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.AddSpacer((-1, vspacer[0]))

        self.header = self.CreateHeader()
        self.header.SetTitle(title)
        self.header.SetBackgroundColour(background)
        vSizer.Add(self.header, 0, wx.EXPAND | spacerFlags, spacer)

        self.panel = self.CreatePanel()
        if self.panel:
            vSizer.Add(self.panel, 1, wx.EXPAND | spacerFlags, spacer)

        self.footer = self.CreateFooter()
        self.footer.SetBackgroundColour(background)
        vSizer.Add(self.footer, 0, wx.EXPAND | spacerFlags, spacer)
        vSizer.AddSpacer((-1, vspacer[1]))

        self.SetSizer(vSizer)
        self.Layout()

    def CreateHeader(self):
        return DetailHeader(self)

    def CreatePanel(self):
        pass

    def CreateFooter(self):
        return ListFooter(self)

    def DoLayout(self):
        self.Freeze()
        self.Layout()
        self.GetParent().Layout()
        self.Thaw()


class NetworkPanel(HomePanel):

    def __init__(self, parent):
        HomePanel.__init__(self, parent, 'Network info', SEPARATOR_GREY, (0, 1))

        self.torrentdb = TorrentDBHandler.getInstance()
        self.channelcastdb = ChannelCastDBHandler.getInstance()
        self.remotetorrenthandler = RemoteTorrentHandler.getInstance()

        self.timer = None

        session = Session.get_instance()
        session.add_observer(self.OnNotify, NTFY_TORRENTS, [NTFY_INSERT])
        self.UpdateStats()

    def CreatePanel(self):
        panel = wx.Panel(self)
        panel.SetBackgroundColour(DEFAULT_BACKGROUND)
        vSizer = wx.BoxSizer(wx.VERTICAL)

        self.nrTorrents = StaticText(panel)
        self.nrFiles = StaticText(panel)
        self.totalSize = StaticText(panel)
        self.queueSize = StaticText(panel)
        self.queueSize.SetToolTipString('Number of torrents queued per prio')
        self.queueSuccess = StaticText(panel)
        self.queueBW = StaticText(panel)
        self.queueBW.SetToolTipString('Bandwidth spent on collecting .torrents')
        self.nrChannels = StaticText(panel)

        self.freeMem = None
        try:
            if wx.GetFreeMemory() != -1:
                self.freeMem = StaticText(panel)
        except:
            pass

        gridSizer = wx.FlexGridSizer(0, 2, 3, 10)
        gridSizer.AddGrowableCol(1)

        gridSizer.Add(StaticText(panel, -1, 'Number files'))
        gridSizer.Add(self.nrFiles, 0, wx.EXPAND)
        gridSizer.Add(StaticText(panel, -1, 'Total size'))
        gridSizer.Add(self.totalSize, 0, wx.EXPAND)
        gridSizer.Add(StaticText(panel, -1, 'Torrents collected'))
        gridSizer.Add(self.nrTorrents, 0, wx.EXPAND)
        gridSizer.Add(StaticText(panel, -1, 'Torrents in queue'))
        gridSizer.Add(self.queueSize, 0, wx.EXPAND)
        gridSizer.Add(StaticText(panel, -1, 'Torrent queue success'))
        gridSizer.Add(self.queueSuccess, 0, wx.EXPAND)
        gridSizer.Add(StaticText(panel, -1, 'Torrent queue bw'))
        gridSizer.Add(self.queueBW, 0, wx.EXPAND)
        gridSizer.Add(StaticText(panel, -1, 'Channels found'))
        gridSizer.Add(self.nrChannels, 0, wx.EXPAND)
        if self.freeMem:
            gridSizer.Add(StaticText(panel, -1, 'WX:Free memory'))
            gridSizer.Add(self.freeMem, 0, wx.EXPAND)

        vSizer.Add(gridSizer, 0, wx.EXPAND | wx.LEFT, 7)
        panel.SetSizer(vSizer)
        return panel

    def OnNotify(self, subject, type, infohash):
        try:
            if self.IsShownOnScreen():
                self.UpdateStats()
        except wx.PyDeadObjectError:
            pass

    def UpdateStats(self):
        def db_callback():
            stats = self.torrentdb.getTorrentsStats()
            nr_channels = self.channelcastdb.getNrChannels()
            self._UpdateStats(stats, nr_channels)

        startWorker(None, db_callback, uId=u"NetworkPanel_UpdateStats", priority=GUI_PRI_DISPERSY)

    @forceWxThread
    def _UpdateStats(self, stats, nr_channels):
        self.nrTorrents.SetLabel(str(stats[0]))
        if stats[1] is None:
            self.totalSize.SetLabel(str(stats[1]))
        else:
            self.totalSize.SetLabel(self.guiutility.utility.size_format(stats[1]))
        self.nrFiles.SetLabel(str(stats[2]))
        self.queueSize.SetLabel(self.remotetorrenthandler.getQueueSize())
        self.queueBW.SetLabel(self.remotetorrenthandler.getBandwidthSpent())

        qsuccess = self.remotetorrenthandler.getQueueSuccess()
        qlabel = ", ".join(label for label, tooltip in qsuccess)
        qtooltip = ", ".join(tooltip for label, tooltip in qsuccess)
        self.queueSuccess.SetLabel(qlabel)
        self.queueSuccess.SetToolTipString(qtooltip)
        self.nrChannels.SetLabel(str(nr_channels))

        if self.freeMem:
            self.freeMem.SetLabel(self.guiutility.utility.size_format(wx.GetFreeMemory()))

        if self.timer:
            self.timer.Restart(10000)
        else:
            self.timer = wx.CallLater(10000, self.UpdateStats)


class NewTorrentPanel(HomePanel):

    def __init__(self, parent):
        HomePanel.__init__(self, parent, 'Newest Torrents', SEPARATOR_GREY, (0, 1))
        self.Layout()

        self.torrentdb = TorrentDBHandler.getInstance()
        session = Session.get_instance()
        session.add_observer(self.OnNotify, NTFY_TORRENTS, [NTFY_INSERT])

    def CreatePanel(self):
        self.list = SelectableListCtrl(self)
        self.list.InsertColumn(0, 'Torrent')
        self.list.setResizeColumn(0)
        self.list.Bind(wx.EVT_LEFT_DCLICK, self.OnDoubleClick)
        self.list.SetMinSize((1, 80))
        return self.list

    def OnNotify(self, subject, type, infohash):
        try:
            if self.IsShownOnScreen():
                self.UpdateStats(infohash)
        except wx.PyDeadObjectError:
            pass

    def UpdateStats(self, infohash):
        def db_callback():
            torrent = self.torrentdb.getTorrent(infohash, include_mypref=False)
            if torrent:
                self._UpdateStats(torrent)

        startWorker(None, db_callback, uId=u"NewTorrentPanel_UpdateStats", priority=GUI_PRI_DISPERSY)

    @forceWxThread
    def _UpdateStats(self, torrent):
        self.list.InsertStringItem(0, torrent['name'])
        size = self.list.GetItemCount()
        if size > 10:
            self.list.DeleteItem(size - 1)

    def OnDoubleClick(self, event):
        selected = self.list.GetFirstSelected()
        if selected != -1:
            selected_file = self.list.GetItemText(selected)
            self.guiutility.dosearch(selected_file)


class PopularTorrentPanel(NewTorrentPanel):

    def __init__(self, parent):
        HomePanel.__init__(self, parent, 'Popular Torrents', SEPARATOR_GREY, (1, 0))
        self.Layout()

        self.misc_db = MiscDBHandler.getInstance()
        self.torrentdb = TorrentDBHandler.getInstance()

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._onTimer, self.timer)
        self.timer.Start(10000, False)
        self.RefreshList()

    def _onTimer(self, event):
        if self.IsShownOnScreen():
            self.RefreshList()

    def RefreshList(self):
        def db_callback():
            familyfilter_sql = Category.getInstance().get_family_filter_sql(self.misc_db.categoryName2Id)
            if familyfilter_sql:
                familyfilter_sql = familyfilter_sql[4:]

            topTen = self.torrentdb._db.getAll("CollectedTorrent", ("infohash", "name", "(num_seeders+num_leechers) as popularity"), where=familyfilter_sql, order_by="(num_seeders+num_leechers) DESC", limit=10)
            self._RefreshList(topTen)

        startWorker(None, db_callback, uId=u"PopularTorrentPanel_RefreshList", priority=GUI_PRI_DISPERSY)

    @forceWxThread
    def _RefreshList(self, topTen):
        self.list.Freeze()
        self.list.DeleteAllItems()
        for item in topTen:
            if item[2] > 0:
                self.list.InsertStringItem(sys.maxsize, item[1])
        self.list.Thaw()


class ActivityPanel(NewTorrentPanel):

    def __init__(self, parent):
        HomePanel.__init__(self, parent, 'Recent Activity', SEPARATOR_GREY, (1, 0))

    @forceWxThread
    def onActivity(self, msg):
        msg = strftime("%H:%M:%S ") + msg
        self.list.InsertStringItem(0, msg)
        size = self.list.GetItemCount()
        if size > 50:
            self.list.DeleteItem(size - 1)


class ArtworkPanel(wx.Panel):

    def __init__(self, parent):
        wx.Panel.__init__(self, parent)
        self.SetBackgroundColour(wx.WHITE)
        self.SetForegroundColour(parent.GetForegroundColour())

        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility
        self.OnExpand = lambda *args: None
        self.OnCollapse = lambda *args: None
        self.update_interval = 120
        self.max_torrents = 20

        self.list = ListBody(self, self, [{'width': wx.LIST_AUTOSIZE}], 0, 0, True, False, grid_columns=self.max_torrents, horizontal_scroll=True)
        self.list.SetBackgroundColour(self.GetBackgroundColour())

        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.Add(DetailHeader(self, "Start streaming immediately by clicking on one of items below"), 0, wx.EXPAND)
        vSizer.Add(self.list, 1, wx.EXPAND)

        self.SetSizer(vSizer)
        self.Layout()

        startWorker(None, self.GetData, delay=3, workerType="guiTaskQueue")

    def GetData(self):
        data = []

        torrents = self.guiutility.torrentsearch_manager.getThumbnailTorrents(limit=self.max_torrents)

        for torrent in torrents:
            thumb_path = os.path.join(self.utility.session.get_torrent_collecting_dir(), 'thumbs-%s' % binascii.hexlify(torrent.infohash))
            if os.path.isdir(thumb_path):
                data.append((torrent.infohash, [torrent.name], torrent, ThumbnailListItemNoTorrent))

        self.SetData(data)

        if len(torrents) < self.max_torrents:
            interval = self.update_interval / 2
        else:
            interval = self.update_interval
        startWorker(None, self.GetData, delay=interval, workerType="guiTaskQueue")

    @forceWxThread
    def SetData(self, data):
        self.list.SetData(data)
        self.list.SetupScrolling()
