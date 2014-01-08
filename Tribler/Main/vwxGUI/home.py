# Written by Niels Zeilemaker
import wx
import sys
import os
import random
from time import strftime, time

from Tribler.__init__ import LIBRARYNAME
from Tribler.Main.vwxGUI.list_header import *
from Tribler.Main.vwxGUI.list_footer import *
from Tribler.Main.vwxGUI.list import XRCPanel

from Tribler.Main.vwxGUI.GuiUtility import GUIUtility, forceWxThread
from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue
from Tribler.Main.vwxGUI.widgets import BetterListCtrl, SelectableListCtrl, \
    TextCtrlAutoComplete, BetterText as StaticText, _set_font, SimpleNotebook, FancyPanel
from Tribler.Category.Category import Category
from Tribler.Core.RemoteTorrentHandler import RemoteTorrentHandler

from __init__ import LIST_GREY, LIST_LIGHTBLUE

from Tribler.Core.CacheDB.SqliteCacheDBHandler import MiscDBHandler, \
    NetworkBuzzDBHandler, TorrentDBHandler, ChannelCastDBHandler
from Tribler.Core.Session import Session
from Tribler.Core.simpledefs import NTFY_TORRENTS, NTFY_INSERT
from Tribler.Core.Utilities.utilities import show_permid_short
from Tribler.Main.Utility.GuiDBHandler import startWorker, GUI_PRI_DISPERSY
from traceback import print_exc, print_stack
from Tribler.Main.vwxGUI import DEFAULT_BACKGROUND
from Tribler.Core.Tag.Extraction import TermExtraction

import wx.lib.agw.customtreectrl as CT


class Home(XRCPanel):

    @warnWxThread
    def _PostInit(self):
        self.guiutility = GUIUtility.getInstance()

        self.SetBackgroundColour(DEFAULT_BACKGROUND)

        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.AddStretchSpacer()

        text = StaticText(self, -1, self.guiutility.utility.lang.get('title'))
        font = text.GetFont()
        font.SetPointSize(font.GetPointSize() * 3)
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        text.SetForegroundColour((255, 51, 0))
        text.SetFont(font)

        textSizer = wx.FlexGridSizer(2, 2, 3, 7)
        if sys.platform == 'darwin':  # mac
            self.searchBox = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        else:
            self.searchBox = TextCtrlAutoComplete(self, entrycallback=self.parent.top_bg.complete, selectcallback=self.parent.top_bg.OnAutoComplete)

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

        self.buzzpanel = BuzzPanel(self)
        self.buzzpanel.SetMinSize((-1, 180))
        self.buzzpanel.Show(self.guiutility.ReadGuiSetting('show_buzz', True))
        vSizer.Add(self.buzzpanel, 0, wx.EXPAND)

        self.SetSizer(vSizer)
        self.Layout()

        self.Bind(wx.EVT_RIGHT_UP, self.OnRightClick)

        self.SearchFocus()

    def OnRightClick(self, event):
        menu = wx.Menu()
        itemid = wx.NewId()
        menu.AppendCheckItem(itemid, 'Show "what\'s hot"')
        menu.Check(itemid, self.buzzpanel.IsShown())

        def toggleBuzz(event):
            show = not self.buzzpanel.IsShown()
            self.buzzpanel.Show(show)
            self.guiutility.WriteGuiSetting("show_buzz", show)
            self.Layout()

        menu.Bind(wx.EVT_MENU, toggleBuzz, id=itemid)

        if menu:
            self.PopupMenu(menu, self.ScreenToClient(wx.GetMousePosition()))
            menu.Destroy()

    def OnClick(self, event):
        term = self.searchBox.GetValue()
        self.guiutility.dosearch(term)

    @warnWxThread
    def OnSearchKeyDown(self, event):
        self.OnClick(event)

    @warnWxThread
    def OnChannels(self, event):
        self.guiutility.showChannels()

    @warnWxThread
    def ResetSearchBox(self):
        self.searchBox.Clear()

    @warnWxThread
    def SearchFocus(self):
        if self.isReady:
            self.searchBox.SetFocus()
            self.searchBox.SelectAll()


class Stats(XRCPanel):

    def __init__(self, parent=None):
        XRCPanel.__init__(self, parent)
        self.createTimer = None
        self.isReady = False

    @warnWxThread
    def _DoInit(self):

        try:
            ldisp = LeftDispersyPanel(self)
            rdisp = RightDispersyPanel(self)
        except:
            if self.createTimer is None:
                self.createTimer = wx.CallLater(5000, self._DoInit)
            else:
                self.createTimer.Restart(5000)
            print_exc()
            return

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
        hSizer.Add(ldisp, 1, wx.EXPAND | wx.RIGHT, 3)
        hSizer.Add(rdisp, 2, wx.EXPAND)
        vSizer.Add(hSizer, 1, wx.EXPAND | wx.BOTTOM, 3)

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(NetworkPanel(self), 1, wx.EXPAND | wx.RIGHT, 7)
        self.activity = ActivityPanel(self)
        hSizer.Add(self.activity, 1, wx.EXPAND)
        vSizer.Add(hSizer, 0, wx.EXPAND)

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(NewTorrentPanel(self), 1, wx.EXPAND | wx.RIGHT, 7)
        hSizer.Add(PopularTorrentPanel(self), 1, wx.EXPAND, 7)
        vSizer.Add(hSizer, 0, wx.EXPAND)

        self.SetSizer(vSizer)
        self.Layout()

        self.Bind(wx.EVT_KEY_UP, self.onKey)
        if sys.platform.startswith('win'):
            # on Windows, the panel doesn't respond to keypresses
            self.Bind(wx.EVT_MOUSE_EVENTS, self.onMouse)

        self.isReady = True

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
            print >> sys.stderr, table, torrentdb._db.fetchone("SELECT COUNT(*) FROM %s" % table)

    @warnWxThread
    def Show(self, show=True):
        if show:
            if not self.isReady:
                self._DoInit()

        XRCPanel.Show(self, show)


class HomePanel(wx.Panel):

    @warnWxThread
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

    @warnWxThread
    def CreateHeader(self):
        return DetailHeader(self)

    def CreatePanel(self):
        pass

    @warnWxThread
    def CreateFooter(self):
        return ListFooter(self)

    @warnWxThread
    def DoLayout(self):
        self.Freeze()
        self.Layout()
        self.GetParent().Layout()
        self.Thaw()


class NetworkPanel(HomePanel):

    @warnWxThread
    def __init__(self, parent):
        HomePanel.__init__(self, parent, 'Network info', SEPARATOR_GREY, (0, 1))

        self.torrentdb = TorrentDBHandler.getInstance()
        self.channelcastdb = ChannelCastDBHandler.getInstance()
        self.remotetorrenthandler = RemoteTorrentHandler.getInstance()

        self.timer = None

        session = Session.get_instance()
        session.add_observer(self.OnNotify, NTFY_TORRENTS, [NTFY_INSERT])
        self.UpdateStats()

    @warnWxThread
    def CreatePanel(self):
        panel = wx.Panel(self)
        panel.SetBackgroundColour(DEFAULT_BACKGROUND)
        vSizer = wx.BoxSizer(wx.VERTICAL)

        self.nrTorrents = StaticText(panel)
        self.nrFiles = StaticText(panel)
        self.totalSize = StaticText(panel)
        self.queueSize = StaticText(panel)
        self.queueSuccess = StaticText(panel)
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


class LeftDispersyPanel(HomePanel):

    @warnWxThread
    def __init__(self, parent):
        self.buildColumns = False

        guiutility = GUIUtility.getInstance()
        self.dispersy = guiutility.utility.session.lm.dispersy
        if not self.dispersy:
            raise RuntimeError("Dispersy has not started yet")

        HomePanel.__init__(self, parent, 'Dispersy info', SEPARATOR_GREY, hspacer=(0, 1), vspacer=(0, 1))

        self.SetMinSize((-1, 200))

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._onTimer, self.timer)
        self.timer.Start(5000, False)
        self.UpdateStats()

        def ratio(i, j):
            return "%d / %d ~%.1f%%" % (i, j, (100.0 * i / j) if j else 0.0)

        self.mapping = [
            ("WAN Address", '', lambda stats: "%s:%d" % stats.wan_address),
            ("LAN Address", '', lambda stats: "%s:%d" % stats.lan_address),
            ("Connection", '', lambda stats: str(stats.connection_type)),
            ("Runtime", '', lambda stats: self.utility.eta_value(stats.timestamp - stats.start)),
            ("Download", '', lambda stats: self.utility.size_format(stats.total_down) + " or " + self.utility.size_format(int(stats.total_down / (stats.timestamp - stats.start))) + "/s"),
            ("Upload", '', lambda stats: self.utility.size_format(stats.total_up) + " or " + self.utility.size_format(int(stats.total_up / (stats.timestamp - stats.start))) + "/s"),

            ("Packets send", 'Packets send vs Packets handled', lambda stats: ratio(stats.total_send, stats.received_count + stats.total_send)),
            ("Packets received", 'Packets received vs Packets handled', lambda stats: ratio(stats.received_count, stats.received_count + stats.total_send)),
            ("Packets dropped", 'Packets dropped vs Packets received', lambda stats: ratio(stats.drop_count, stats.received_count)),
            ("Packets success", 'Messages successfully handled vs Packets received', lambda stats: ratio(stats.success_count, stats.received_count)),
            ("Packets delayed", 'Packets being delayed vs Packets reveived', lambda stats: ratio(stats.delay_count, stats.received_count)),
            ("Sync-Messages created", 'Total number of messages created by us in this session which should be synced', lambda stats: str(stats.created_count)),

            ("Packets delayed send", 'Total number of delaymessages or delaypacket messages being sent', lambda stats: ratio(stats.delay_send, stats.delay_count)),
            ("Packets delayed success", 'Total number of packets which were delayed, and did not timeout', lambda stats: ratio(stats.delay_success, stats.delay_count)),
            ("Packets delayed timeout", 'Total number of packets which were delayed, but got a timeout', lambda stats: ratio(stats.delay_timeout, stats.delay_count)),

            ("Walker success", '', lambda stats: ratio(stats.walk_success, stats.walk_attempt)),
            ("Walker success (from trackers)", 'Comparing the successes to tracker to overall successes.', lambda stats: ratio(stats.walk_bootstrap_success, stats.walk_bootstrap_attempt)),
            ("Walker resets", '', lambda stats: str(stats.walk_reset)),

            ("Bloom new", 'Total number of bloomfilters created vs IntroductionRequest sent in this session', lambda stats: ratio(sum(c.sync_bloom_new for c in stats.communities), sum(c.sync_bloom_send + c.sync_bloom_skip for c in stats.communities))),
            ("Bloom reuse", 'Total number of bloomfilters reused vs IntroductionRequest sent in this session', lambda stats: ratio(sum(c.sync_bloom_reuse for c in stats.communities), sum(c.sync_bloom_send + c.sync_bloom_skip for c in stats.communities))),
            ("Bloom skip", 'Total number of bloomfilters skipped vs IntroductionRequest sent in this session', lambda stats: ratio(sum(c.sync_bloom_skip for c in stats.communities), sum(c.sync_bloom_send + c.sync_bloom_skip for c in stats.communities))),

            ("Debug mode", '', lambda stats: "yes" if __debug__ else "no"),
        ]

    @warnWxThread
    def CreatePanel(self):
        panel = wx.Panel(self)
        panel.SetBackgroundColour(DEFAULT_BACKGROUND)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)

        self.gridpanel = wx.lib.scrolledpanel.ScrolledPanel(panel)
        self.gridpanel.SetBackgroundColour(DEFAULT_BACKGROUND)
        self.gridSizer = wx.FlexGridSizer(0, 2, 3, 10)
        self.gridSizer.AddGrowableCol(1)
        self.gridpanel.SetSizer(self.gridSizer)
        hSizer.Add(self.gridpanel, 1, wx.EXPAND | wx.LEFT, 7)

        panel.SetSizer(hSizer)
        return panel

    @warnWxThread
    def CreateColumns(self):
        self.textdict = {}

        def addColumn(strkey, strtooltip):
            # strkey = key.replace("_", " ").capitalize()
            header = StaticText(self.gridpanel, -1, strkey)
            _set_font(header, fontweight=wx.FONTWEIGHT_BOLD)
            self.gridSizer.Add(header)
            self.textdict[strkey] = StaticText(self.gridpanel, -1, '')
            self.textdict[strkey].SetMinSize((200, -1))
            self.gridSizer.Add(self.textdict[strkey])

            if strtooltip:
                header.SetToolTipString(strtooltip)
                self.textdict[strkey].SetToolTipString(strtooltip)

        for title, tooltip, _ in self.mapping:
            addColumn(title, tooltip)

        self.gridpanel.Layout()
        self.gridpanel.SetupScrolling()
        self.buildColumns = True

    def _onTimer(self, event):
        if self.IsShownOnScreen():
            self.UpdateStats()

    def UpdateStats(self):
        def db_callback():
            self.dispersy.statistics.update(database=False)
            self._UpdateStats(self.dispersy.statistics)

        startWorker(None, db_callback, uId=u"LeftDispersyPanel_UpdateStats", priority=GUI_PRI_DISPERSY)

    @forceWxThread
    def _UpdateStats(self, stats):
        if not self.buildColumns:
            self.CreateColumns()

        for title, _, func in self.mapping:
            self.textdict[title].SetLabel(str(func(stats)))

        self.panel.Layout()


class RightDispersyPanel(FancyPanel):

    @warnWxThread
    def __init__(self, parent):
        FancyPanel.__init__(self, parent, border=wx.LEFT | wx.BOTTOM)
        self.SetBorderColour(SEPARATOR_GREY)
        self.SetBackgroundColour(wx.WHITE)

        guiutility = GUIUtility.getInstance()
        self.dispersy = guiutility.utility.session.lm.dispersy
        if not self.dispersy:
            raise RuntimeError("Dispersy has not started yet")

        # Create notebook
        self.notebook = SimpleNotebook(self, show_single_tab=True, style=wx.NB_NOPAGETHEME)
        checkboxSizer = wx.BoxSizer(wx.HORIZONTAL)
        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.Add(self.notebook, 1, wx.EXPAND | wx.LEFT, 1)
        vSizer.Add(checkboxSizer, 0, wx.EXPAND | wx.LEFT, 5)
        vSizer.AddSpacer((-1, 2))
        self.SetSizer(vSizer)

        # Create and populate community panel
        self.community_panel = wx.Panel(self.notebook)
        self.community_panel.SetBackgroundColour(wx.WHITE)
        self.notebook.AddPage(self.community_panel, "Community info")

        community_sizer = wx.BoxSizer(wx.VERTICAL)
        self.community_tree = CT.CustomTreeCtrl(self.community_panel, agwStyle=wx.TR_DEFAULT_STYLE | wx.TR_HIDE_ROOT | wx.TR_NO_LINES | wx.TR_HAS_VARIABLE_ROW_HEIGHT)
        self.community_tree.blockUpdate = False
        self.community_tree.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouseEvent)
        self.community_tree.Bind(wx.EVT_MOTION, self.OnMouseEvent)

        font = self.community_tree.GetFont()
        font = wx.Font(font.GetPointSize(), wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.community_tree.SetFont(font)

        community_sizer.Add(self.community_tree, 1, wx.EXPAND)

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(community_sizer, 1, wx.EXPAND)
        self.community_panel.SetSizer(hSizer)

        # Create and populate raw info panel
        self.rawinfo_panel = wx.Panel(self.notebook)
        self.rawinfo_panel.SetBackgroundColour(wx.WHITE)
        self.notebook.AddPage(self.rawinfo_panel, "Raw info")

        self.rawinfo_sizer = wx.BoxSizer(wx.VERTICAL)
        self.rawinfo_tree = CT.CustomTreeCtrl(self.rawinfo_panel, agwStyle=wx.TR_DEFAULT_STYLE | wx.TR_HIDE_ROOT | wx.TR_NO_LINES | wx.TR_HAS_VARIABLE_ROW_HEIGHT)
        self.rawinfo_tree.blockUpdate = False
        self.rawinfo_tree.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouseEvent)
        self.rawinfo_tree.Bind(wx.EVT_MOTION, self.OnMouseEvent)

        font = self.rawinfo_tree.GetFont()
        font = wx.Font(font.GetPointSize(), wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.rawinfo_tree.SetFont(font)

        self.rawinfo_sizer.Add(self.rawinfo_tree, 1, wx.EXPAND)

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(self.rawinfo_sizer, 1, wx.EXPAND)
        self.rawinfo_panel.SetSizer(hSizer)

        # Create and populate runtime statistics panel
        self.runtime_panel = wx.Panel(self.notebook)
        self.runtime_panel.SetBackgroundColour(wx.WHITE)
        self.notebook.AddPage(self.runtime_panel, "Runtime stats")

        self.runtime_sizer = wx.BoxSizer(wx.VERTICAL)
        self.runtime_tree = CT.CustomTreeCtrl(self.runtime_panel, agwStyle=wx.TR_DEFAULT_STYLE | wx.TR_HIDE_ROOT | wx.TR_NO_LINES | wx.TR_HAS_VARIABLE_ROW_HEIGHT)
        self.runtime_tree.blockUpdate = False
        self.runtime_tree.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouseEvent)
        self.runtime_tree.Bind(wx.EVT_MOTION, self.OnMouseEvent)

        font = self.runtime_tree.GetFont()
        font = wx.Font(font.GetPointSize(), wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.runtime_tree.SetFont(font)

        self.runtime_sizer.Add(self.runtime_tree, 1, wx.EXPAND)

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(self.runtime_sizer, 1, wx.EXPAND)
        self.runtime_panel.SetSizer(hSizer)

        # Add checkboxes
        self.includeStuffs = wx.CheckBox(self, -1, "Include stuffs")
        checkboxSizer.Add(self.includeStuffs, 0, wx.TOP | wx.BOTTOM, 3)

        self.includeDebug = wx.CheckBox(self, -1, "Collect debug")
        self.includeDebug.SetValue(self.dispersy.statistics.are_debug_statistics_enabled())
        checkboxSizer.Add(self.includeDebug, 0, wx.TOP | wx.BOTTOM, 3)

        # Add timer for stats updates
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._onTimer, self.timer)
        self.timer.Start(5000, False)
        self.UpdateStats()

    def OnMouseEvent(self, event):
        tree = event.GetEventObject()

        if event.Moving():
            tree.blockUpdate = True

        elif event.Leaving():
            tree.blockUpdate = False

        event.Skip()

    def _onTimer(self, event):
        if self.IsShownOnScreen():
            self.UpdateStats()

    @warnWxThread
    def AddDataToTree(self, data, parent, tree, prepend=True, sort_dict=False):

        def addValue(parentNode, value):
            if isinstance(value, dict):
                addDict(parentNode, value)
            elif isinstance(value, list):
                addList(parentNode, value)
            elif isinstance(value, tuple):
                addTuple(parentNode, value)
            elif value != None:
                tree.AppendItem(parentNode, str(value))

        def addList(parentNode, nodelist):
            for key, value in enumerate(nodelist):
                keyNode = tree.AppendItem(parentNode, str(key))
                addValue(keyNode, value)

        def addTuple(parentNode, nodetuple):
            for value in nodetuple:
                addValue(parentNode, value)

        def addDict(parentNode, nodedict):
            kv_pairs = sorted(nodedict.items(), reverse=True) if sort_dict else nodedict.items()
            if prepend and kv_pairs:
                kv_pairs.sort(key=lambda kv: kv[1], reverse=True)
            for key, value in kv_pairs:
                prepend_str = ''
                if prepend and not isinstance(value, (list, dict)):
                    prepend_str = str(value) + "x "
                    value = None

                if not isinstance(key, basestring):
                    key = str(key)
                try:
                    key = key.decode("utf-8")
                except UnicodeDecodeError:
                    key = key.encode("hex")

                keyNode = tree.AppendItem(parentNode, prepend_str + key)
                addValue(keyNode, value)

        addValue(parent, data)

    def UpdateStats(self):
        includeStuffs = self.includeStuffs.GetValue()
        includeDebug = self.includeDebug.GetValue()

        def db_callback():
            self.dispersy.statistics.enable_debug_statistics(includeDebug)
            self.dispersy.statistics.update(database=includeStuffs)
            self._UpdateStats(self.dispersy.statistics)

        startWorker(None, db_callback, uId=u"DispersyPanel_UpdateStats", priority=GUI_PRI_DISPERSY)

    @forceWxThread
    def _UpdateStats(self, stats):

        if not self.community_tree.blockUpdate:
            self.community_tree.DeleteAllItems()
            root = self.community_tree.AddRoot("fake")
            for community in sorted(stats.communities, key=lambda community: (not community.dispersy_enable_candidate_walker, community.classification, community.cid)):
                if community.dispersy_enable_candidate_walker or community.dispersy_enable_candidate_walker_responses:
                    candidates = "%d " % len(community.candidates)
                elif community.candidates:
                    candidates = "%d*" % len(community.candidates)
                else:
                    candidates = "- "
                total_packets = sum(community.database.itervalues())
                parent = self.community_tree.AppendItem(root, u"%s %6d %3s %s @%d ~%d" % (community.hex_cid, total_packets, candidates, community.classification, community.global_time, community.acceptable_global_time - community.global_time - community.dispersy_acceptable_global_time_range))
                self.community_tree.AppendItem(parent, u"member:             %s" % community.hex_mid)
                self.community_tree.AppendItem(parent, u"classification:     %s" % community.classification)
                self.community_tree.AppendItem(parent, u"database id:        %d" % community.database_id)
                self.community_tree.AppendItem(parent, u"global time:        %d" % community.global_time)
                self.community_tree.AppendItem(parent, u"median global time: %d (%d difference)" % (community.acceptable_global_time - community.dispersy_acceptable_global_time_range, community.acceptable_global_time - community.global_time - community.dispersy_acceptable_global_time_range))
                self.community_tree.AppendItem(parent, u"acceptable range:   %d" % community.dispersy_acceptable_global_time_range)
                self.community_tree.AppendItem(parent, u"sync bloom created: %d" % community.sync_bloom_new)
                self.community_tree.AppendItem(parent, u"sync bloom reused:  %d" % community.sync_bloom_reuse)
                self.community_tree.AppendItem(parent, u"sync bloom skip: %d" % community.sync_bloom_skip)
                if community.dispersy_enable_candidate_walker or community.dispersy_enable_candidate_walker_responses:
                    sub_parent = self.community_tree.AppendItem(parent, u"candidates: %s" % candidates)
                    for candidate in sorted(("@%d %s:%d" % (global_time, wan_address[0], wan_address[1]) if lan_address == wan_address else "@%d %s:%d, %s:%d" % (global_time, wan_address[0], wan_address[1], lan_address[0], lan_address[1]))
                                            for lan_address, wan_address, global_time
                                            in community.candidates):
                        self.community_tree.AppendItem(sub_parent, candidate)
                if community.database:
                    sub_parent = self.community_tree.AppendItem(parent, u"database: %d packets" % sum(count for count in community.database.itervalues()))
                    for name, count in sorted(community.database.iteritems(), key=lambda tup: tup[1]):
                        self.community_tree.AppendItem(sub_parent, "%s: %d" % (name, count))

        if not self.rawinfo_tree.blockUpdate:
            self.rawinfo_tree.DeleteAllItems()
            parentNode = self.rawinfo_tree.AddRoot('raw info')

            raw_info = {}
            if stats.drop:
                raw_info['drop'] = stats.drop
            if stats.delay:
                raw_info['delay'] = stats.delay
            if stats.success:
                raw_info['success'] = stats.success
            if stats.outgoing:
                raw_info['outgoing'] = stats.outgoing
            if stats.created:
                raw_info['created'] = stats.created
            if stats.walk_fail:
                raw_info['walk_fail'] = stats.walk_fail
            if stats.attachment:
                raw_info['attachment'] = stats.attachment
            if stats.database:
                raw_info['database'] = stats.database
            if stats.endpoint_recv:
                raw_info['endpoint_recv'] = stats.endpoint_recv
            if stats.endpoint_send:
                raw_info['endpoint_send'] = stats.endpoint_send
            if stats.bootstrap_candidates:
                raw_info['bootstrap_candidates'] = stats.bootstrap_candidates
            self.AddDataToTree(raw_info, parentNode, self.rawinfo_tree)

        if not self.runtime_tree.blockUpdate:
            self.runtime_tree.DeleteAllItems()
            parentNode = self.runtime_tree.AddRoot('runtime stats')

            runtime = []
            if getattr(stats, 'runtime', None):
                for stat_dict in stats.runtime:
                    stat_list = []
                    for k, v in stat_dict.iteritems():
                        if isinstance(v, basestring):
                            v = v.replace('\n', '\n          ')
                        stat_list.append('%-10s%s' % (k, v))
                    runtime.append(("duration = %7.2f ; entry = %s" % (stat_dict['duration'], stat_dict['entry'].split('\n')[0]), tuple(stat_list)))
                runtime.sort(reverse=True)
            self.AddDataToTree(dict(runtime), parentNode, self.rawinfo_tree, prepend=False, sort_dict=True)

        self.Layout()

class NewTorrentPanel(HomePanel):

    @warnWxThread
    def __init__(self, parent):
        HomePanel.__init__(self, parent, 'Newest Torrents', SEPARATOR_GREY, (0, 1))
        self.Layout()

        self.torrentdb = TorrentDBHandler.getInstance()
        session = Session.get_instance()
        session.add_observer(self.OnNotify, NTFY_TORRENTS, [NTFY_INSERT])

    @warnWxThread
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

    @warnWxThread
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

    @warnWxThread
    def __init__(self, parent):
        HomePanel.__init__(self, parent, 'Recent Activity', SEPARATOR_GREY, (1, 0))

    @forceWxThread
    def onActivity(self, msg):
        msg = strftime("%H:%M:%S ") + msg
        self.list.InsertStringItem(0, msg)
        size = self.list.GetItemCount()
        if size > 50:
            self.list.DeleteItem(size - 1)


class BuzzPanel(wx.Panel):
    INACTIVE_COLOR = (255, 51, 0)
    ACTIVE_COLOR = (0, 105, 156)

    TERM_BORDERS = [15, 8, 8]
    DISPLAY_SIZES = [3, 5, 5]
    REFRESH_EVERY = 5

    @warnWxThread
    def __init__(self, parent):
        wx.Panel.__init__(self, parent)
        self.SetBackgroundColour(wx.WHITE)
        self.SetForegroundColour(parent.GetForegroundColour())

        # Niels 04-06-2012: termextraction needs a session variable, create instance from mainthread
        TermExtraction.getInstance()

        self.nbdb = None
        self.xxx_filter = Category.getInstance().xxx_filter
        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility

        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.Add(DetailHeader(self, "Click below to explore what's hot"), 0, wx.EXPAND)
        vSizer.AddSpacer((-1, 10))

        self.panel = wx.Panel(self)
        self.panel.SetBackgroundColour(DEFAULT_BACKGROUND)
        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        self.panel.SetSizer(self.vSizer)
        vSizer.Add(self.panel, 1, wx.EXPAND | wx.BOTTOM, 5)

        self.footer = wx.StaticText(self)
        vSizer.Add(self.footer, 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, 1)

        self.tags = []
        self.buzz_cache = [[], [], []]
        self.last_shown_buzz = None

        row1_font = self.GetFont()
        row1_font.SetPointSize(row1_font.GetPointSize() + 10)
        row1_font.SetWeight(wx.FONTWEIGHT_BOLD)

        row2_font = self.GetFont()
        row2_font.SetPointSize(row2_font.GetPointSize() + 4)
        row2_font.SetWeight(wx.FONTWEIGHT_BOLD)

        row3_font = self.GetFont()
        row3_font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.TERM_FONTS = [row1_font, row2_font, row3_font]

        self.panel.Bind(wx.EVT_ENTER_WINDOW, self.OnEnterWindow)
        self.panel.Bind(wx.EVT_LEAVE_WINDOW, self.OnLeaveWindow)

        text = wx.StaticText(self.panel, -1, '...collecting buzz information...')
        _set_font(text, fontcolour=BuzzPanel.INACTIVE_COLOR)
        self.vSizer.AddStretchSpacer()
        self.vSizer.Add(text, 0, wx.ALIGN_CENTER)
        self.vSizer.AddStretchSpacer()

        self.refresh = 5
        self.GetBuzzFromDB(doRefresh=True, samplesize=10)
        self.guiutility.addList(self)

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnRefreshTimer, self.timer)
        self.timer.Start(1000, False)

        self.SetSizer(vSizer)
        self.Layout()

    def do_or_schedule_refresh(self, force_refresh=False):
        # Only called when the FF is toggled.
        if self.guiutility.ShouldGuiUpdate():
            self.ForceUpdate()
        else:
            self.refresh = -1

    def ForceUpdate(self):
        self.GetBuzzFromDB(doRefresh=True)

    def GetBuzzFromDB(self, doRefresh=False, samplesize=NetworkBuzzDBHandler.DEFAULT_SAMPLE_SIZE):
        def do_db():
            if self.nbdb == None:
                self.nbdb = NetworkBuzzDBHandler.getInstance()

            self.buzz_cache = [[], [], []]
            buzz = self.nbdb.getBuzz(samplesize, with_freq=True, flat=True)
            for i in range(len(buzz)):
                random.shuffle(buzz[i])
                self.buzz_cache[i] = buzz[i]

            if len(self.tags) <= 1 and len(buzz) > 0 or doRefresh:
                self.OnRefreshTimer(force=True, fromDBThread=True)
        startWorker(None, do_db, uId=u"NetworkBuzz.GetBuzzFromDB", priority=GUI_PRI_DISPERSY)

    @forceWxThread
    def OnRefreshTimer(self, event=None, force=False, fromDBThread=False):
        self.refresh -= 1
        if self.refresh <= 0 or force or fromDBThread:
            if (self.IsShownOnScreen() and self.guiutility.ShouldGuiUpdate()) or force or fromDBThread:
                # simple caching
                # (Completely throws away the old cache and refills it)
                if any(len(row) < 10 for row in self.buzz_cache) and not fromDBThread:
                    self.GetBuzzFromDB(doRefresh=True)
                    return

                if self.guiutility.getFamilyFilter():
                    xxx_filter = self.xxx_filter.isXXX
                else:
                    xxx_filter = lambda *args, **kwargs: False

                # consume cache
                # Note: if a term is fetched from two different row caches, it is shown in the
                # higher-frequency row, regardless of which information is fresher.
                filtered_buzz = [[], [], []]
                empty = True
                added_terms = set()
                for i in range(len(filtered_buzz)):
                    while len(filtered_buzz[i]) < BuzzPanel.DISPLAY_SIZES[i] and len(self.buzz_cache[i]):
                        term, freq = self.buzz_cache[i].pop(0)
                        if term not in added_terms and not xxx_filter(term, isFilename=False):
                            filtered_buzz[i].append((term, freq))
                            added_terms.add(term)
                            empty = False

                if empty:
                    filtered_buzz = None
                self.DisplayTerms(filtered_buzz)
                self.last_shown_buzz = filtered_buzz
            self.refresh = BuzzPanel.REFRESH_EVERY

        self.footer.SetLabel('Update in %d...' % self.refresh)
        self.Layout()

    @warnWxThread
    def getStaticText(self, term, font=None):
        if len(self.tags) > 0:
            text = self.tags.pop()
            text.SetLabel(term)
            text.SetFonts([font, font])
            text.Reset()

        else:
            text = LinkText(self.panel, term, fonts=[font, font], colours=[BuzzPanel.INACTIVE_COLOR, BuzzPanel.ACTIVE_COLOR])
            text.SetBackgroundColour(DEFAULT_BACKGROUND)
            text.Bind(wx.EVT_LEFT_UP, self.OnClick)
        text.SetToolTipString("Click to search for '%s'" % term)
        return text

    @warnWxThread
    def DisplayTerms(self, rows):
        if rows:
            self.Freeze()
            self.vSizer.ShowItems(False)
            self.vSizer.Clear()
            self.vSizer.AddStretchSpacer()

            cur_tags = []
            for i in range(len(rows)):
                row = rows[i]
                if len(row) == 0:
                    # don't bother adding an empty hsizer
                    continue
                hSizer = wx.BoxSizer(wx.HORIZONTAL)
                hSizer.AddStretchSpacer(2)

                for term, freq in row:
                    text = self.getStaticText(term, self.TERM_FONTS[i])
                    cur_tags.append(text)

                    hSizer.Add(text, 0, wx.BOTTOM, self.TERM_BORDERS[i])
                    hSizer.AddStretchSpacer()
                hSizer.AddStretchSpacer()
                self.vSizer.Add(hSizer, 0, wx.EXPAND)

            self.vSizer.AddStretchSpacer()
            self.vSizer.ShowItems(True)
            self.vSizer.Layout()

            # destroy all unnecessary statictexts
            for text in self.tags:
                text.Destroy()
            self.tags = cur_tags

            self.Layout()
            self.GetParent().Layout()
            self.Thaw()

    @warnWxThread
    def DoPauseResume(self):
        def IsEnter(control):
            if getattr(control, 'GetWindow', False):
                control = control.GetWindow()

            if getattr(control, 'enter', False):
                return True

            if getattr(control, 'GetChildren', False):
                children = control.GetChildren()
                for child in children:
                    if IsEnter(child):
                        return True
            return False

        enter = getattr(self.panel, 'enter', False) or IsEnter(self)
        timerstop = not enter  # stop timer if one control has enter==true

        if timerstop != self.timer.IsRunning():
            if not enter:
                self.timer.Start(1000, False)
                self.footer.SetLabel('Resuming update')
                self.Layout()

        if enter:
            self.timer.Stop()
            self.footer.SetLabel('Update has paused')
            self.Layout()
        return enter

    def OnMouse(self, event):
        if event.Entering() or event.Moving():
            self.OnEnterWindow(event)

        elif event.Leaving():
            self.OnLeaveWindow(event)

        event.Skip()

    def OnEnterWindow(self, event):
        evtobj = event.GetEventObject()
        evtobj.enter = True

        self.DoPauseResume()

    def OnLeaveWindow(self, event=None):
        if event:
            evtobj = event.GetEventObject()
            evtobj.enter = False

        wx.CallAfter(self.DoPauseResume)

    def OnClick(self, event):
        evtobj = event.GetEventObject()
        term = evtobj.GetLabel()
        if term != '...collecting buzz information...':
            self.guiutility.dosearch(term)

            evtobj.enter = False
            self.DoPauseResume()

            # 29/06/11 boudewijn: do not perform database inserts on the GUI thread

# 17-10-2011: Niels disabling networkbuzz uel
#            def db_callback():
#                uelog = UserEventLogDBHandler.getInstance()
#                uelog.addEvent(message=repr((term, last_shown_buzz)))
#            last_shown_buzz = self.last_shown_buzz
#            self.guiserver.add_task(db_callback)
