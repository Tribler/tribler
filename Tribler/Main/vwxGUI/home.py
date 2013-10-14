# Written by Niels Zeilemaker
import wx
import sys
import os
import copy
import igraph
import random
import threading
from time import strftime, time

from Tribler.__init__ import LIBRARYNAME
from Tribler.Main.vwxGUI.list_header import *
from Tribler.Main.vwxGUI.list_footer import *
from Tribler.Main.vwxGUI.list import XRCPanel

from Tribler.Main.vwxGUI.GuiUtility import GUIUtility, forceWxThread
from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue
from Tribler.Main.vwxGUI.widgets import BetterListCtrl, SelectableListCtrl, \
    TextCtrlAutoComplete, BetterText as StaticText, _set_font, FancyPanel
from Tribler.Category.Category import Category
from Tribler.Core.RemoteTorrentHandler import RemoteTorrentHandler

from __init__ import LIST_GREY, LIST_LIGHTBLUE

from Tribler.Core.CacheDB.SqliteCacheDBHandler import NetworkBuzzDBHandler, TorrentDBHandler, ChannelCastDBHandler
from Tribler.Core.Session import Session
from Tribler.Core.simpledefs import NTFY_TORRENTS, NTFY_INSERT, NTFY_ANONTUNNEL, NTFY_CREATED, NTFY_EXTENDED
from Tribler.Core.Utilities.utilities import show_permid_short
from Tribler.Main.Utility.GuiDBHandler import startWorker, GUI_PRI_DISPERSY
from traceback import print_exc, print_stack
from Tribler.Main.vwxGUI import DEFAULT_BACKGROUND
from Tribler.Core.Tag.Extraction import TermExtraction
from Tribler.Utilities.TimedTaskQueue import TimedTaskQueue

try:
    # C(ython) module
    import arflayout
except ImportError, e:
    # Python fallback module
    import arflayout_fb as arflayout


class Home(XRCPanel):

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

    def OnSearchKeyDown(self, event):
        self.OnClick(event)

    def OnChannels(self, event):
        self.guiutility.showChannels()

    def ResetSearchBox(self):
        self.searchBox.Clear()

    def SearchFocus(self):
        if self.isReady:
            self.searchBox.SetFocus()
            self.searchBox.SelectAll()


class Stats(XRCPanel):

    def __init__(self, parent=None):
        XRCPanel.__init__(self, parent)
        self.createTimer = None
        self.isReady = False

    def _DoInit(self):

        try:
            disp = DispersyPanel(self)
        except:
            # Dispersy not ready, try again in 5s
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

        vSizer.Add(disp, 1, wx.EXPAND | wx.BOTTOM, 3)

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

    def Show(self, show=True):
        if show:
            if not self.isReady:
                self._DoInit()

        XRCPanel.Show(self, show)


class HomePanel(wx.Panel):

    def __init__(self, parent, title, background, hspacer=(0, 0)):
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


class DispersyPanel(HomePanel):

    def __init__(self, parent):
        self.buildColumns = False

        guiutility = GUIUtility.getInstance()
        self.dispersy = guiutility.utility.session.lm.dispersy
        if not self.dispersy:
            raise RuntimeError("Dispersy has not started yet")

        HomePanel.__init__(self, parent, 'Dispersy info', SEPARATOR_GREY)

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

        vSumSizer = wx.BoxSizer(wx.VERTICAL)
        self.summary_tree = wx.TreeCtrl(panel, style=wx.TR_DEFAULT_STYLE | wx.TR_HIDE_ROOT | wx.NO_BORDER)
        self.summary_tree.blockUpdate = False
        self.summary_tree.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouseEvent)
        self.summary_tree.Bind(wx.EVT_MOTION, self.OnMouseEvent)

        font = self.summary_tree.GetFont()
        font = wx.Font(font.GetPointSize(), wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.summary_tree.SetFont(font)

        vSumSizer.Add(self.summary_tree, 1, wx.EXPAND)
        self.includeStuffs = wx.CheckBox(panel, -1, "Include stuffs")
        vSumSizer.Add(self.includeStuffs, 0, wx.TOP | wx.BOTTOM, 3)

        self.vTreeSizer = wx.BoxSizer(wx.VERTICAL)
        self.tree = wx.TreeCtrl(panel, style=wx.TR_DEFAULT_STYLE | wx.TR_HIDE_ROOT | wx.NO_BORDER)
        self.tree.blockUpdate = False
        self.tree.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouseEvent)
        self.tree.Bind(wx.EVT_MOTION, self.OnMouseEvent)

        self.vTreeSizer.Add(self.tree, 1, wx.EXPAND)
        self.includeDebug = wx.CheckBox(panel, -1, "Collect debug")
        self.includeDebug.SetValue(self.dispersy.statistics.are_debug_statistics_enabled())
        self.vTreeSizer.Add(self.includeDebug, 0, wx.TOP | wx.BOTTOM, 3)

        hSizer.Add(vSumSizer, 2, wx.EXPAND | wx.LEFT, 10)
        hSizer.Add(self.vTreeSizer, 1, wx.EXPAND | wx.LEFT, 10)
        panel.SetSizer(hSizer)
        return panel

    def ExpandTree(self, expand=True):
        sizer = self.panel.GetSizer()
        sizerItem = sizer.GetItem(self.vTreeSizer)

        newProportion = 4 if expand else 1
        if sizerItem.GetProportion() != newProportion:
            sizerItem.SetProportion(newProportion)

            self.panel.Layout()

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

    def OnMouseEvent(self, event):
        tree = event.GetEventObject()

        if event.Moving():
            tree.blockUpdate = True

        elif event.Leaving():
            tree.blockUpdate = False

        if tree == self.tree:
            self.ExpandTree(tree.blockUpdate)

        event.Skip()

    def _onTimer(self, event):
        if self.IsShownOnScreen():
            self.UpdateStats()

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
        if not self.buildColumns:
            self.CreateColumns()

        def addValue(parentNode, value):
            if isinstance(value, dict):
                addDict(parentNode, value)
            elif isinstance(value, list):
                addList(parentNode, value)
            elif value != None:
                self.tree.AppendItem(parentNode, str(value))

        def addList(parentNode, nodelist):
            for key, value in enumerate(nodelist):
                keyNode = self.tree.AppendItem(parentNode, str(key))
                addValue(keyNode, value)

        def addDict(parentNode, nodedict):
            for key, value in nodedict.items():
                key = str(key)
                prepend = ''
                if not isinstance(value, (list, dict)):
                    prepend = str(value) + "x "
                    value = None
                try:
                    keyNode = self.tree.AppendItem(parentNode, prepend + str(key))
                except UnicodeDecodeError:
                    keyNode = self.tree.AppendItem(parentNode, prepend + key.encode("HEX"))
                addValue(keyNode, value)

        def updateColumn(key, value):
            # if key.find('address') != -1:
            #     value = "%s:%d"%value
            self.textdict[key].SetLabel(str(value))

        # center communities
        if not self.summary_tree.blockUpdate:
            self.summary_tree.DeleteAllItems()
            root = self.summary_tree.AddRoot("fake")
            for community in sorted(stats.communities, key=lambda community: (not community.dispersy_enable_candidate_walker, community.classification, community.cid)):
                if community.dispersy_enable_candidate_walker or community.dispersy_enable_candidate_walker_responses:
                    candidates = "%d " % len(community.candidates)
                elif community.candidates:
                    candidates = "%d*" % len(community.candidates)
                else:
                    candidates = "- "
                total_packets = sum(community.database.itervalues())
                parent = self.summary_tree.AppendItem(root, u"%s %6d %3s %s @%d ~%d" % (community.hex_cid, total_packets, candidates, community.classification, community.global_time, community.acceptable_global_time - community.global_time - community.dispersy_acceptable_global_time_range))
                self.summary_tree.AppendItem(parent, u"member:             %s" % community.hex_mid)
                self.summary_tree.AppendItem(parent, u"classification:     %s" % community.classification)
                self.summary_tree.AppendItem(parent, u"database id:        %d" % community.database_id)
                self.summary_tree.AppendItem(parent, u"global time:        %d" % community.global_time)
                self.summary_tree.AppendItem(parent, u"median global time: %d (%d difference)" % (community.acceptable_global_time - community.dispersy_acceptable_global_time_range, community.acceptable_global_time - community.global_time - community.dispersy_acceptable_global_time_range))
                self.summary_tree.AppendItem(parent, u"acceptable range:   %d" % community.dispersy_acceptable_global_time_range)
                self.summary_tree.AppendItem(parent, u"sync bloom created: %d" % community.sync_bloom_new)
                self.summary_tree.AppendItem(parent, u"sync bloom reused:  %d" % community.sync_bloom_reuse)
                self.summary_tree.AppendItem(parent, u"sync bloom skip: %d" % community.sync_bloom_skip)
                if community.dispersy_enable_candidate_walker or community.dispersy_enable_candidate_walker_responses:
                    sub_parent = self.summary_tree.AppendItem(parent, u"candidates: %s" % candidates)
                    for candidate in sorted(("@%d %s:%d" % (global_time, wan_address[0], wan_address[1]) if lan_address == wan_address else "@%d %s:%d, %s:%d" % (global_time, wan_address[0], wan_address[1], lan_address[0], lan_address[1]))
                                            for lan_address, wan_address, global_time
                                            in community.candidates):
                        self.summary_tree.AppendItem(sub_parent, candidate)
                if community.database:
                    sub_parent = self.summary_tree.AppendItem(parent, u"database: %d packets" % sum(count for count in community.database.itervalues()))
                    for name, count in sorted(community.database.iteritems(), key=lambda tup: tup[1]):
                        self.summary_tree.AppendItem(sub_parent, "%s: %d" % (name, count))
                # self.summary_tree.Expand(parent)
            # self.summary_tree.ExpandAll()

        # left tree
        if not self.tree.blockUpdate:
            self.tree.DeleteAllItems()
            fakeRoot = self.tree.AddRoot('fake')
            for title, _, func in self.mapping:
                updateColumn(title, func(stats))

        # right tree
        if not self.tree.blockUpdate:
            parentNode = self.tree.AppendItem(fakeRoot, "raw info")

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
            addValue(parentNode, raw_info)

        self.panel.Layout()


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
            familyfilter_sql = Category.getInstance().get_family_filter_sql(self.torrentdb._getCategoryID)
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


class BuzzPanel(wx.Panel):
    INACTIVE_COLOR = (255, 51, 0)
    ACTIVE_COLOR = (0, 105, 156)

    TERM_BORDERS = [15, 8, 8]
    DISPLAY_SIZES = [3, 5, 5]
    REFRESH_EVERY = 5

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


class Anonymity(wx.Panel):
    def __init__(self, parent):
        wx.Panel.__init__(self, parent, -1)

        self.SetBackgroundColour(wx.WHITE)
        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility
        self.session = self.utility.session
        self.socks_server = self.utility.socks_server

        self.AddComponents()

        self.vertices = {}
        self.edges = []

        self.vertex_max = 100
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
        self.radius = 16

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

        self.taskqueue = TimedTaskQueue(nameprefix="GraphLayoutCalculator")

        self.lock = threading.RLock()

        self.session.add_observer(self.OnExtended, NTFY_ANONTUNNEL, [NTFY_CREATED, NTFY_EXTENDED])

    def AddComponents(self):
        self.graph_panel = wx.Panel(self, -1)
        self.graph_panel.Bind(wx.EVT_MOTION, self.OnMouse)
        self.graph_panel.Bind(wx.EVT_LEFT_UP, self.OnMouse)
        self.graph_panel.Bind(wx.EVT_PAINT, self.OnPaint)
        self.graph_panel.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
        self.graph_panel.Bind(wx.EVT_SIZE, self.OnSize)

        self.circuit_list = SelectableListCtrl(self, style=wx.LC_REPORT | wx.BORDER_SIMPLE)
        self.circuit_list.InsertColumn(0, 'Circuit ID')
        self.circuit_list.InsertColumn(1, 'Bytes up', wx.LIST_FORMAT_RIGHT, 100)
        self.circuit_list.InsertColumn(2, 'Bytes down', wx.LIST_FORMAT_RIGHT, 100)
        self.circuit_list.setResizeColumn(0)
        self.circuit_to_listindex = {}

        self.log_text = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.BORDER_SIMPLE | wx.HSCROLL & wx.VSCROLL)
        self.log_text.SetEditable(False)

        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.Add(self.circuit_list, 1, wx.EXPAND | wx.BOTTOM, 20)
        vSizer.Add(self.log_text, 1, wx.EXPAND)
        self.main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.main_sizer.Add(self.graph_panel, 3, wx.EXPAND | wx.ALL, 20)
        self.main_sizer.Add(vSizer, 2, wx.EXPAND | wx.ALL, 20)
        self.SetSizer(self.main_sizer)

    def OnUpdateCircuits(self, event):
        circuits = self.socks_server.tunnel.get_circuits()

        # Add new circuits & update existing circuits
        for circuit_id, circuit in circuits.iteritems():
            if circuit_id not in self.circuit_to_listindex:
                pos = self.circuit_list.InsertStringItem(sys.maxsize, str(circuit_id))
                self.circuit_to_listindex[circuit_id] = pos
            else:
                pos = self.circuit_to_listindex[circuit_id]
            self.circuit_list.SetStringItem(pos, 1, self.utility.size_format(circuit.bytes_uploaded))
            self.circuit_list.SetStringItem(pos, 2, self.utility.size_format(circuit.bytes_downloaded))

        # Remove old circuits
        old_circuits = [circuit_id for circuit_id in self.circuit_to_listindex if circuit_id not in circuits]
        for circuit_id in old_circuits:
            listindex = self.circuit_to_listindex[circuit_id]
            self.circuit_list.DeleteItem(listindex)
            self.circuit_to_listindex.pop(circuit_id)
            for k, v in self.circuit_to_listindex.items():
                if v > listindex:
                    self.circuit_to_listindex[k] = v - 1

    def OnExtended(self, subject, changeType, circuit):
        circuit_id = circuit.id
        extend_from = circuit.hops[-2].wan_address if hasattr(circuit.hops[-2], 'wan_address') else circuit.hops[-2]
        extend_to = circuit.hops[-1].wan_address if hasattr(circuit.hops[-1], 'wan_address') else circuit.hops[-1]

        self.log_text.AppendText("Extended circuit %s with %s:%d\n" % (circuit_id, extend_to[0], extend_to[1]))

        if not self.peers:
            with self.lock:
                self.peers.append(('127.0.0.1', 0))
                self.toInsert.add(0)
                self.vertices[0] = {}
            self.Layout()

        with self.lock:
            if extend_to not in self.peers:
                self.peers.append(extend_to)
            to_id = self.peers.index(extend_to)
            from_id = self.peers.index(extend_from)
            self.AddEdge(to_id, from_id)

    def AddEdge(self, from_id, to_id):
        with self.lock:
            if to_id not in self.peers:
                self.toInsert.add(to_id)
                self.vertices[to_id] = {}
            self.edges.append([to_id, from_id])
            self.new_data = True

    def RemoveVertex(self):
        with self.lock:

            # Build a list of the vertices, sorted by the number of neighbors.
            num_neighbors = self.CountNeighbors()
            num_neighbors = sorted([(v, k) for k, v in num_neighbors.iteritems()], reverse=True)
            toremove = num_neighbors[-1][1]

            # Remove the vertex with the fewest neighbors.
            if toremove in self.vertices:
                self.vertices.pop(toremove)
            if toremove in self.vertex_to_colour:
                self.vertex_to_colour.pop(toremove)
            if toremove < len(self.peers):
                self.peers.pop(toremove)
            self.edges = [edge for edge in self.edges if toremove not in edge]
            self.toInsert = set([id - 1 if id > toremove else id for id in self.toInsert if id != toremove])
            self.vertex_active = self.vertex_active - 1 if self.vertex_active > toremove else self.vertex_active
            self.vertex_hover = self.vertex_hover - 1 if self.vertex_hover > toremove else self.vertex_hover

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
                if edge[0] >= toremove:
                    edge[0] -= 1
                if edge[1] >= toremove:
                    edge[1] -= 1

            # The arflayout module keeps the vertex positions from the latest iteration in memory. So we need to notify arflayout.
            arflayout.arf_remove([toremove])

    def CountNeighbors(self):
        with self.lock:
            num_neighbors = dict([(k, 0) for k in self.vertices])
            for edge in self.edges:
                for vertexid in edge:
                    num_neighbors[vertexid] = num_neighbors.get(vertexid, 0) + 1
            return num_neighbors

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
        self.graph_panel.SetSize((size, size))

    def OnEraseBackground(self, event):
        pass

    def OnPaint(self, event):
        eo = event.GetEventObject()
        dc = wx.BufferedPaintDC(eo)
        dc.Clear()
        gc = wx.GraphicsContext.Create(dc)

        w, h = eo.GetSize().x - 2 * self.radius - 1, eo.GetSize().y - 2 * self.radius - 1

        schedule_layout = not self.layout_busy and self.new_data and time() - self.last_keyframe >= self.time_step
        if schedule_layout:
            task = lambda : self.CalculateLayout()
            self.taskqueue.add_task(task)
            self.new_data = False
            self.layout_busy = True

        elif len(self.vertices) > self.vertex_max:
            task = lambda: self.RemoveVertex()
            self.taskqueue.add_task(task)

        if len(self.vertices) > 0:

            int_points = {}

            with self.lock:

                # Get current vertex positions using interpolation
                for vertexid in self.vertices.iterkeys():
                    if self.GetVertexPosition(vertexid, self.step - 1) and self.GetVertexPosition(vertexid, self.step):
                        scaled_x, scaled_y = self.InterpolateVertexPosition(vertexid, self.step - 1, self.step)
                        int_points[vertexid] = (scaled_x * w + self.radius, scaled_y * h + self.radius)

                # Draw edges
                gc.SetPen(wx.Pen(wx.Colour(229, 229, 229)))
                for vertexid1, vertexid2 in self.edges:
                    if int_points.has_key(vertexid1) and int_points.has_key(vertexid2):
                        x1, y1 = int_points[vertexid1]
                        x2, y2 = int_points[vertexid2]
                        gc.DrawLines([(x1, y1), (x2, y2)])

                # Draw vertices
                gc.SetPen(wx.TRANSPARENT_PEN)
                for vertexid in self.vertices.iterkeys():
                    colour = self.vertex_to_colour.get(vertexid, None)
                    if not colour:
                        colour = self.colours[0] if vertexid == 0 else random.choice(self.colours[1:])
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
                    pen = wx.Pen(wx.Colour(119, 119, 119), 1, wx.USER_DASH)
                    pen.SetDashes([8, 4])
                    gc.SetPen(pen)
                    gc.DrawEllipse(x - self.radius, y - self.radius, self.radius * 2, self.radius * 2)

                if self.vertex_active_evt:
                    self.vertex_active = self.PositionToVertex(self.vertex_active_evt, int_points)
                    self.vertex_active_evt = None

                if self.vertex_active >= 0 and self.vertex_active != self.vertex_hover:
                    x, y = int_points[self.vertex_active]
                    pen = wx.Pen(self.vertex_to_colour.get(self.vertex_active, wx.BLACK), 1, wx.USER_DASH)
                    pen.SetDashes([8, 4])
                    gc.SetPen(pen)
                    gc.DrawEllipse(x - self.radius, y - self.radius, self.radius * 2, self.radius * 2)

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
