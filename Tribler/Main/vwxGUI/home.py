# Written by Niels Zeilemaker
import threading
import wx
import sys
import os
import copy

import wx
import igraph
from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue
from Tribler.Utilities.TimedTaskQueue import TimedTaskQueue
from Tribler.community.anontunnel.community import ProxyCommunity
import datetime
from Tribler.community.anontunnel.routing import Hop

try:
    import igraph.vendor.texttable
except:
    pass
import random
import logging
import binascii
from time import strftime, time
from collections import defaultdict
from traceback import print_exc

from Tribler.Category.Category import Category
from Tribler.Core.Tag.Extraction import TermExtraction
from Tribler.Core.simpledefs import NTFY_TORRENTS, NTFY_INSERT, NTFY_ANONTUNNEL, \
    NTFY_CREATED, NTFY_EXTENDED, NTFY_BROKEN, NTFY_SELECT, NTFY_JOINED, \
    NTFY_EXTENDED_FOR
from Tribler.Core.Session import Session
from Tribler.Core.CacheDB.SqliteCacheDBHandler import MiscDBHandler, \
    TorrentDBHandler, ChannelCastDBHandler
from Tribler.Core.RemoteTorrentHandler import RemoteTorrentHandler

from Tribler.Main.vwxGUI import SEPARATOR_GREY, DEFAULT_BACKGROUND, LIST_BLUE
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility, forceWxThread
from Tribler.Main.Utility.GuiDBHandler import startWorker, GUI_PRI_DISPERSY
from Tribler.Main.vwxGUI.list_header import DetailHeader
from Tribler.Main.vwxGUI.list_body import ListBody
from Tribler.Main.vwxGUI.list_item import ThumbnailListItemNoTorrent
from Tribler.Main.vwxGUI.list_footer import ListFooter
from Tribler.Main.vwxGUI.widgets import SelectableListCtrl, \
    TextCtrlAutoComplete, BetterText as StaticText, LinkStaticText

try:
    # C(ython) module
    import arflayout
except ImportError, e:
    # Python fallback module
    import arflayout_fb as arflayout


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

        self.SearchFocus()

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


class Anonymity(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent, -1)

        self.SetBackgroundColour(wx.WHITE)
        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility
        self.session = self.utility.session

        dispersy = self.utility.session.lm.dispersy
        self.proxy_community = (c for c in dispersy.get_communities() if isinstance(c, ProxyCommunity)).next()

        self.AddComponents()

        self.my_address = Hop(self.proxy_community.my_member._ec.pub())
        self.my_address.address = ('127.0.0.1', "SELF")

        self.vertices = {}
        self.edges = []

        self.selected_edges = []

        self.vertex_active = -1
        self.vertex_hover = -1
        self.vertex_hover_evt = None
        self.vertex_active_evt = None

        self.vertex_to_colour = {}
        self.colours = [wx.RED, wx.Colour(156, 18, 18), wx.Colour(183, 83, 83), wx.Colour(254, 134, 134), wx.Colour(254, 190, 190)]

        self.step = 0
        self.fps = 20

        self.last_keyframe = 0
        self.time_step = 5.0
        self.radius = 32
        self.line_width = 4
        self.margin_x = self.margin_y = 0

        self.layout_busy = False
        self.new_data = False

        self.peers = []
        self.toInsert = set()

        self.refresh_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, lambda evt: self.graph_panel.Refresh(), self.refresh_timer)
        self.refresh_timer.Start(1000.0 / self.fps)

        self.circuit_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnUpdateCircuits, self.circuit_timer)
        self.circuit_timer.Start(5000)

        self.taskqueue = GUITaskQueue.getInstance()

        self.lock = threading.RLock()

        self.session.add_observer(self.OnExtended, NTFY_ANONTUNNEL, [NTFY_CREATED, NTFY_EXTENDED, NTFY_BROKEN])
        self.session.add_observer(self.OnSelect, NTFY_ANONTUNNEL, [NTFY_SELECT])
        self.session.add_observer(self.OnJoined, NTFY_ANONTUNNEL, [NTFY_JOINED])
        self.session.add_observer(self.OnExtendedFor, NTFY_ANONTUNNEL, [NTFY_EXTENDED_FOR])

    def SetFullScreenMode(self, enable):
        self.fullscreen = enable
        self.log_text.Show(enable)
        self.radius = 20 if enable else 12
        self.line_width = 2 if enable else 1
        self.vSizer.GetChildren()[0].SetBorder(20 if enable else 0)
        self.main_sizer.GetChildren()[0].SetBorder(20 if enable else 0)
        self.main_sizer.GetChildren()[1].SetBorder(20 if enable else 0)
        self.margin_x = 0 if enable else 50
        self.Layout()

    def AddComponents(self):
        self.graph_panel = wx.Panel(self, -1)
        self.graph_panel.Bind(wx.EVT_MOTION, self.OnMouse)
        self.graph_panel.Bind(wx.EVT_LEFT_UP, self.OnMouse)
        self.graph_panel.Bind(wx.EVT_PAINT, self.OnPaint)
        self.graph_panel.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
        self.graph_panel.Bind(wx.EVT_SIZE, self.OnSize)

        self.circuit_list = SelectableListCtrl(self, style=wx.LC_REPORT | wx.BORDER_SIMPLE)
        self.circuit_list.InsertColumn(0, 'Circuit', wx.LIST_FORMAT_LEFT, 30)
        self.circuit_list.InsertColumn(1, 'Online', wx.LIST_FORMAT_RIGHT, 50)
        self.circuit_list.InsertColumn(2, 'Hops', wx.LIST_FORMAT_RIGHT, 45)
        self.circuit_list.InsertColumn(3, 'Bytes up', wx.LIST_FORMAT_RIGHT, 65)
        self.circuit_list.InsertColumn(4, 'Bytes down', wx.LIST_FORMAT_RIGHT, 65)
        self.circuit_list.setResizeColumn(0)
        self.circuit_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnItemSelected)
        self.circuit_list.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.OnItemSelected)
        self.circuit_to_listindex = {}

        self.log_text = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.BORDER_SIMPLE | wx.HSCROLL & wx.VSCROLL)
        self.log_text.SetEditable(False)

        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        self.vSizer.Add(self.circuit_list, 1, wx.EXPAND | wx.BOTTOM, 20)
        self.vSizer.Add(self.log_text, 1, wx.EXPAND)
        self.main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.main_sizer.Add(self.graph_panel, 3, wx.EXPAND | wx.ALL, 20)
        self.main_sizer.Add(self.vSizer, 2, wx.EXPAND | wx.ALL, 20)
        self.SetSizer(self.main_sizer)

    def OnItemSelected(self, event):
        selected = []
        item = self.circuit_list.GetFirstSelected()
        while item != -1:
            selected.append(item)
            item = self.circuit_list.GetNextSelected(item)

        selected_edges = []
        for item in selected:
            for circuit_id, listindex in self.circuit_to_listindex.iteritems():
                if listindex == item:
                    circuit = self.circuits.get(circuit_id, None)

                    if circuit:
                        hops = [self.my_address] + list(copy.copy(circuit.hops))
                        for index in range(len(hops) - 1):
                            vertexid1 = self.peers.index(hops[index]) if hops[index] in self.peers else None
                            vertexid2 = self.peers.index(hops[index + 1]) if hops[index + 1] in self.peers else None
                            edge = set([vertexid1, vertexid2])
                            selected_edges.append(edge)

        self.selected_edges = selected_edges

    def OnUpdateCircuits(self, event):
        self.circuits = dict(self.proxy_community.circuits)
        stats = self.proxy_community.global_stats.circuit_stats

        # Add new circuits & update existing circuits
        for circuit_id, circuit in self.circuits.iteritems():
            if circuit_id not in self.circuit_to_listindex:
                pos = self.circuit_list.InsertStringItem(sys.maxsize, str(circuit_id))
                self.circuit_to_listindex[circuit_id] = pos
            else:
                pos = self.circuit_to_listindex[circuit_id]
            self.circuit_list.SetStringItem(pos, 1, str(circuit.state))
            self.circuit_list.SetStringItem(pos, 2, str(len(circuit.hops)) + "/" + str(circuit.goal_hops))

            bytes_uploaded = stats[circuit_id].bytes_uploaded
            bytes_downloaded = stats[circuit_id].bytes_downloaded

            self.circuit_list.SetStringItem(pos, 3, self.utility.size_format(bytes_uploaded))
            self.circuit_list.SetStringItem(pos, 4, self.utility.size_format(bytes_downloaded))

        # Remove old circuits
        old_circuits = [circuit_id for circuit_id in self.circuit_to_listindex if circuit_id not in self.circuits]
        for circuit_id in old_circuits:
            listindex = self.circuit_to_listindex[circuit_id]
            self.circuit_list.DeleteItem(listindex)
            self.circuit_to_listindex.pop(circuit_id)
            for k, v in self.circuit_to_listindex.items():
                if v > listindex:
                    self.circuit_to_listindex[k] = v - 1

        # Update graph
        old_edges = getattr(self, 'old_edges', [])
        new_edges = []

        for circuit in self.circuits.values():
            hops = [self.my_address] + list(circuit.hops)
            for index in range(len(hops) - 1):
                edge = set([hops[index], hops[index + 1]])
                if edge not in new_edges:
                    new_edges.append(edge)

        for edge in new_edges:
            if edge not in old_edges:
                self.AddEdge(*edge)

        for edge in old_edges:
            if edge not in new_edges:
                self.RemoveEdge(*edge)

        self.old_edges = new_edges

    def AppendToLog(self, msg):
        self.log_text.AppendText('[%s]: %s' % (datetime.datetime.now().strftime("%H:%M:%S"), msg))

    @forceWxThread
    def OnExtended(self, subject, changeType, circuit):
        if changeType == NTFY_CREATED:
            self.AppendToLog("Created circuit %s\n" % (circuit.circuit_id))
        if changeType == NTFY_EXTENDED:
            self.AppendToLog("Extended circuit %s\n" % (circuit.circuit_id))
        if changeType == NTFY_BROKEN:
            self.AppendToLog("Circuit %d has been broken\n" % circuit)

    @forceWxThread
    def OnSelect(self, subject, changeType, circuit, address):
        self.AppendToLog("Circuit %d has been selected for destination %s\n" % (circuit, address))

    @forceWxThread
    def OnJoined(self, subject, changeType, address, circuit_id):
        self.AppendToLog("Joined an external circuit %d with %s:%d\n" % (circuit_id, address[0], address[1]))

    @forceWxThread
    def OnExtendedFor(self, subject, changeType, extended_for, extended_with):
        self.AppendToLog("Extended an external circuit (%s:%d, %d) with (%s:%d, %d)\n" % (
            extended_for[0].sock_addr[0], extended_for[0].sock_addr[1], extended_for[1], extended_with[0].sock_addr[0],
            extended_with[0].sock_addr[1], extended_with[1]))

    def AddEdge(self, from_addr, to_addr):
        with self.lock:
            # Convert from_addr/to_addr to from_id/to_id
            if from_addr not in self.peers:
                self.peers.append(from_addr)
            from_id = self.peers.index(from_addr)
            if to_addr not in self.peers:
                self.peers.append(to_addr)
            to_id = self.peers.index(to_addr)

            # Add id's to graph
            for peer_id in (from_id, to_id):
                if peer_id not in self.vertices:
                    self.toInsert.add(peer_id)
                    self.vertices[peer_id] = {}
            self.edges.append([to_id, from_id])
            self.new_data = True

    def RemoveEdge(self, from_addr, to_addr):
        with self.lock:
            if from_addr in self.peers and to_addr in self.peers:
                from_id = self.peers.index(from_addr)
                to_id = self.peers.index(to_addr)
                if [to_id, from_id] in self.edges:
                    self.edges.remove([to_id, from_id])
                if [from_id, to_id] in self.edges:
                    self.edges.remove([from_id, to_id])
                self.RemoveUnconnectedVertices()
                self.new_data = True

    def RemoveUnconnectedVertices(self):
        # Build a list of vertices and their number of neighbors, and delete the unconnected ones.
        for vertex_id, num_neighbors in self.CountNeighbors().iteritems():
            if num_neighbors == 0:
                self.RemoveVertex(vertex_id)

    def CountNeighbors(self):
        with self.lock:
            num_neighbors = dict([(k, 0) for k in self.vertices])
            for edge in self.edges:
                for vertexid in edge:
                    num_neighbors[vertexid] = num_neighbors.get(vertexid, 0) + 1
            return num_neighbors

    def RemoveVertex(self, toremove_id):
        with self.lock:
            if toremove_id in self.vertices:
                self.vertices.pop(toremove_id)
            if toremove_id in self.vertex_to_colour:
                self.vertex_to_colour.pop(toremove_id)
            if toremove_id < len(self.peers):
                self.peers.pop(toremove_id)
            self.edges = [edge for edge in self.edges if toremove_id not in edge]
            self.toInsert = set([id - 1 if id > toremove_id else id for id in self.toInsert if id != toremove_id])
            self.vertex_active = self.vertex_active - 1 if self.vertex_active > toremove_id else self.vertex_active
            self.vertex_hover = self.vertex_hover - 1 if self.vertex_hover > toremove_id else self.vertex_hover

            # We want the vertex id's to be 0, 1, 2 etc., so we need to correct for the vertex that we just removed.
            vertices = {}
            for index, vertexid in enumerate(sorted(self.vertices)):
                vertices[index] = self.vertices[vertexid]
            self.vertices = vertices
            vertex_to_colour = {}
            for index, vertexid in enumerate(sorted(self.vertex_to_colour)):
                vertex_to_colour[index] = self.vertex_to_colour[vertexid]
            self.vertex_to_colour = vertex_to_colour
            for edge in self.edges:
                if edge[0] >= toremove_id:
                    edge[0] -= 1
                if edge[1] >= toremove_id:
                    edge[1] -= 1

            # The arflayout module keeps the vertex positions from the latest iteration in memory. So we need to notify arflayout.
            arflayout.arf_remove([toremove_id])

    def CalculateLayout(self):
        with self.lock:
            edges = copy.copy(self.edges)
            toInsert = self.toInsert
            self.toInsert = set()

        graph = igraph.Graph(edges, directed=False)
        positions = arflayout.arf_layout(toInsert, graph)

        with self.lock:
            self.step += 1
            for vertexid, pos in positions.iteritems():
                self.SetVertexPosition(vertexid, self.step, *pos)
            self.time_step = 5 + max(0, len(self.vertices) - 75) / 9
            self.last_keyframe = time()
            self.layout_busy = False

    def OnMouse(self, event):
        if event.Moving():
            self.vertex_hover_evt = event.GetPosition()
        elif event.LeftUp():
            self.vertex_active_evt = event.GetPosition()

    def OnSize(self, evt):
        size = min(*evt.GetEventObject().GetSize())
        self.graph_panel.SetSize((size + self.margin_x * 2, size + self.margin_y * 2))

    def OnEraseBackground(self, event):
        pass

    def OnPaint(self, event):
        eo = event.GetEventObject()
        dc = wx.BufferedPaintDC(eo)
        dc.Clear()
        gc = wx.GraphicsContext.Create(dc)

        w, h = eo.GetSize().x - 2 * self.radius - 2 * self.margin_x - 1, eo.GetSize().y - 2 * self.radius - 2 * self.margin_y - 1

        schedule_layout = not self.layout_busy and self.new_data and time() - self.last_keyframe >= self.time_step
        if schedule_layout:
            task = lambda : self.CalculateLayout()
            self.taskqueue.add_task(task)
            self.new_data = False
            self.layout_busy = True

        if len(self.vertices) > 0:

            int_points = {}

            with self.lock:

                # Get current vertex positions using interpolation
                for vertexid in self.vertices.iterkeys():
                    if self.GetVertexPosition(vertexid, self.step):
                        if self.GetVertexPosition(vertexid, self.step - 1):
                            scaled_x, scaled_y = self.InterpolateVertexPosition(vertexid, self.step - 1, self.step)
                        else:
                            scaled_x, scaled_y = self.GetVertexPosition(vertexid, self.step)
                        int_points[vertexid] = (scaled_x * w + self.radius + self.margin_x, scaled_y * h + self.radius + self.margin_y)

                # Draw edges
                for vertexid1, vertexid2 in self.edges:
                    if int_points.has_key(vertexid1) and int_points.has_key(vertexid2):
                        if set([vertexid1, vertexid2]) in self.selected_edges:
                            gc.SetPen(wx.Pen(wx.BLUE, self.line_width))
                        else:
                            gc.SetPen(wx.Pen(wx.Colour(229, 229, 229), self.line_width))
                        x1, y1 = int_points[vertexid1]
                        x2, y2 = int_points[vertexid2]
                        gc.DrawLines([(x1, y1), (x2, y2)])

                # Draw vertices
                gc.SetPen(wx.TRANSPARENT_PEN)
                for vertexid in self.vertices.iterkeys():
                    colour = self.vertex_to_colour.get(vertexid, None)
                    if not colour:
                        colour = self.colours[0] if self.peers[vertexid] == self.my_address else random.choice(self.colours[1:])
                        self.vertex_to_colour[vertexid] = colour
                    gc.SetBrush(wx.Brush(colour))

                    if int_points.has_key(vertexid):
                        x, y = int_points[vertexid]
                        gc.DrawEllipse(x - self.radius / 2, y - self.radius / 2, self.radius, self.radius)

                        if len(self.vertices.get(vertexid, {})) <= 2:
                            gc.SetBrush(wx.WHITE_BRUSH)
                            gc.DrawEllipse(x - self.radius / 4, y - self.radius / 4, self.radius / 2, self.radius / 2)

                # Draw circle around active vertex
                gc.SetBrush(wx.TRANSPARENT_BRUSH)

                if self.vertex_hover_evt:
                    self.vertex_hover = self.PositionToVertex(self.vertex_hover_evt, int_points)
                    self.vertex_hover_evt = None

                if self.vertex_hover >= 0:
                    x, y = int_points[self.vertex_hover]
                    pen = wx.Pen(wx.Colour(229, 229, 229), 1, wx.USER_DASH)
                    pen.SetDashes([8, 4])
                    gc.SetPen(pen)
                    gc.DrawEllipse(x - self.radius, y - self.radius, self.radius * 2, self.radius * 2)

                if self.vertex_active_evt:
                    self.vertex_active = self.PositionToVertex(self.vertex_active_evt, int_points)
                    self.vertex_active_evt = None

                if self.vertex_active in int_points:
                    x, y = int_points[self.vertex_active]
                    pen = wx.Pen(self.vertex_to_colour.get(self.vertex_active, wx.BLACK), 1, wx.USER_DASH)
                    pen.SetDashes([8, 4])
                    gc.SetPen(pen)
                    gc.DrawEllipse(x - self.radius, y - self.radius, self.radius * 2, self.radius * 2)

                    if 'UNKNOWN HOST' not in self.peers[self.vertex_active].host:
                        text_height = dc.GetTextExtent('gG')[1]
                        box_height = text_height + 3

                        # Draw status box
                        x = x - 150 - 1.1 * self.radius if x > self.graph_panel.GetSize()[0] / 2 else x + 1.1 * self.radius
                        y = y - box_height - 1.1 * self.radius if y > self.graph_panel.GetSize()[1] / 2 else y + 1.1 * self.radius
                        gc.SetBrush(wx.Brush(wx.Colour(216, 237, 255, 50)))
                        gc.SetPen(wx.Pen(LIST_BLUE))
                        gc.DrawRectangle(x, y, 150, box_height)

                        # Draw status text
                        dc.SetFont(self.GetFont())
                        for index, text in enumerate(['IP %s:%s' % (self.peers[self.vertex_active].host, self.peers[self.vertex_active].port)]):
                            dc.DrawText(text, x + 5, y + index * text_height + 5)

            if self.fullscreen:
                # Draw vertex count
                gc.SetFont(self.GetFont())
                gc.DrawText("|V| = %d" % len(int_points), w - 50, h - 20)

    def PositionToVertex(self, position, key_to_position):
        for vertexid, vposition in key_to_position.iteritems():
            if (position[0] - vposition[0]) ** 2 + (position[1] - vposition[1]) ** 2 < self.radius ** 2:
                return vertexid
        return -1

    def InterpolateVertexPosition(self, vertexid, s1, s2):
        x0, y0 = self.GetVertexPosition(vertexid, s1)
        x1, y1 = self.GetVertexPosition(vertexid, s2)

        t = min(time() - self.last_keyframe, self.time_step)
        t1 = 1.0 / 5 * self.time_step
        t2 = 3.0 / 5 * self.time_step
        t3 = 1.0 / 5 * self.time_step
        x = arflayout.CubicHermiteInterpolate(t1, t2, t3, x0, x1, t)
        y = arflayout.CubicHermiteInterpolate(t1, t2, t3, y0, y1, t)
        return (x, y)

    def GetVertexPosition(self, vertexid, t):
        if self.vertices.has_key(vertexid):
            return self.vertices[vertexid].get(t, None)
        return None

    def SetVertexPosition(self, vertexid, t, x, y):
        if self.vertices.has_key(vertexid):
            self.vertices[vertexid][t] = (x, y)
        else:
            self.vertices[vertexid] = {t: (x, y)}

    def ResetSearchBox(self):
        pass


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
