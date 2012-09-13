# Written by Niels Zeilemaker
import wx
import sys
import os
import random
from time import strftime

from Tribler.__init__ import LIBRARYNAME
from Tribler.Main.vwxGUI.list_header import *
from Tribler.Main.vwxGUI.list_footer import *
from Tribler.Main.vwxGUI.list import XRCPanel

from Tribler.Main.vwxGUI.GuiUtility import GUIUtility, forceWxThread
from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue
from Tribler.Main.vwxGUI.widgets import BetterListCtrl, SelectableListCtrl,\
    TextCtrlAutoComplete, BetterText as StaticText, _set_font
from Tribler.Category.Category import Category
from Tribler.Core.RemoteTorrentHandler import RemoteTorrentHandler
from Tribler.Core.SocialNetwork.RemoteQueryMsgHandler import RemoteQueryMsgHandler

from __init__ import LIST_GREY, LIST_LIGHTBLUE

from Tribler.Core.CacheDB.SqliteCacheDBHandler import NetworkBuzzDBHandler, UserEventLogDBHandler, TorrentDBHandler, BarterCastDBHandler, PeerDBHandler, ChannelCastDBHandler
from Tribler.Core.Session import Session
from Tribler.Core.simpledefs import NTFY_TORRENTS, NTFY_INSERT, NTFY_PROXYDISCOVERY
from Tribler.Core.Utilities.utilities import show_permid_short
from Tribler.Main.Utility.GuiDBHandler import startWorker, GUI_PRI_DISPERSY
from Tribler.dispersy.dispersy import Dispersy
from traceback import print_exc
from Tribler.Main.vwxGUI import DEFAULT_BACKGROUND, forceDBThread
from Tribler.Core.BitTornado.BT1.Encrypter import IncompleteCounter
from Tribler.Core.Tag.Extraction import TermExtraction

# ProxyService 90s Test_
#from Tribler.Core.simpledefs import *
# _ProxyService 90s Test

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
        if sys.platform == 'darwin': # mac
            self.searchBox = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        else:
            self.searchBox = TextCtrlAutoComplete(self, entrycallback = self.parent.top_bg.complete, selectcallback = self.parent.top_bg.OnAutoComplete)

        font = self.searchBox.GetFont()
        font.SetPointSize(font.GetPointSize() * 2)
        self.searchBox.SetFont(font)
        self.searchBox.Bind(wx.EVT_TEXT_ENTER, self.OnSearchKeyDown)

        if sys.platform == 'darwin': # mac
            self.searchBox.SetMinSize((450, self.searchBox.GetTextExtent('T')[1] + 5))
        else:
            self.searchBox.SetMinSize((450, -1))
        self.searchBox.SetFocus()

        textSizer.Add(text, 0, wx.EXPAND|wx.RIGHT, 7)
        scalingSizer = wx.BoxSizer(wx.HORIZONTAL)
        scalingSizer.Add(self.searchBox)

        if sys.platform == 'darwin': # mac
            searchButton = wx.Button(self, -1, '\n')
            searchButton.SetLabel('Search')
        else:
            searchButton = wx.Button(self, -1, 'Search')
        searchButton.Bind(wx.EVT_BUTTON, self.OnClick)

        scalingSizer.Add(searchButton, 0, wx.EXPAND|wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 3)

        textSizer.Add(scalingSizer, 0, wx.ALIGN_CENTER_VERTICAL)
        textSizer.AddSpacer((1,1))

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(StaticText(self, -1, "Take me to "))
        channelLink = LinkStaticText(self, "channels", icon = None)

        channelLink.Bind(wx.EVT_LEFT_UP, self.OnChannels)
        hSizer.Add(channelLink)
        hSizer.Add(StaticText(self, -1, " to see what others are sharing"))
        textSizer.Add(hSizer)

        vSizer.Add(textSizer, 0, wx.ALIGN_CENTER)
        vSizer.AddStretchSpacer()
        
        buzzpanel = BuzzPanel(self)
        buzzpanel.SetMinSize((-1,180))
        vSizer.Add(buzzpanel, 0, wx.EXPAND)

        self.SetSizer(vSizer)
        self.Layout()

        self.SearchFocus()

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
    def __init__(self, parent = None):
        XRCPanel.__init__(self, parent)
        self.createTimer = None
        self.isReady = False

    def _DoInit(self):
        
        try:
            disp = DispersyPanel(self)
        except:
            #Dispersy not ready, try again in 5s
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
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(self.dowserStatus, 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 3)
        hSizer.Add(self.dowserButton)
        vSizer.Add(hSizer,0, wx.ALIGN_RIGHT|wx.BOTTOM, 10)
        
        vSizer.Add(disp, 1, wx.EXPAND|wx.BOTTOM, 10)

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(NetworkPanel(self), 1, wx.EXPAND|wx.BOTTOM|wx.RIGHT, 10)
        self.activity = ActivityPanel(self)
        hSizer.Add(self.activity, 1, wx.EXPAND|wx.BOTTOM, 10)
        vSizer.Add(hSizer, 0, wx.EXPAND)

        # ProxyService 90s Test_
        #
#        hSizer = wx.BoxSizer(wx.HORIZONTAL)
#        hSizer.Add(NetworkTestPanel(self), 1, wx.EXPAND|wx.BOTTOM|wx.RIGHT, 10)
#        hSizer.Add(ProxyDiscoveryPanel(self), 1, wx.EXPAND|wx.BOTTOM, 10)
#        vSizer.Add(hSizer, 0, wx.EXPAND)
        #
        # _ProxyService 90s Test

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(NewTorrentPanel(self), 1, wx.EXPAND|wx.RIGHT, 10)
        hSizer.Add(PopularTorrentPanel(self), 1, wx.EXPAND, 10)
        # boudewijn: disabled TopContributorsPanel, getTopNPeers is a very expensive call
        # hSizer.Add(TopContributorsPanel(self), 1, wx.EXPAND)
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
        if event.ControlDown() and (event.GetKeyCode() == 73 or event.GetKeyCode() == 105): #ctrl + i
            self._showInspectionTool()
            
        elif event.ControlDown() and (event.GetKeyCode() == 68 or event.GetKeyCode() == 100): #ctrl + d 
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
                dlg = wx.DirDialog(None, "Please select your dowser installation directory", style = wx.wx.DD_DIR_MUST_EXIST)
                if dlg.ShowModal() == wx.ID_OK and os.path.isdir(dlg.GetPath()):
                    sys.path.append(dlg.GetPath())
                    self._startDowser()
                     
                dlg.Destroy()
    
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
            frame.locals['dispersy'] = Dispersy.get_instance()

        except Exception:
            import traceback
            traceback.print_exc()
            
    def _printDBStats(self):
        torrentdb = TorrentDBHandler.getInstance()
        tables = torrentdb._db.fetchall("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name");
        for table, in tables:
            print >> sys.stderr, table, torrentdb._db.fetchone("SELECT COUNT(*) FROM %s"%table)

    def Show(self, show = True):
        if show:
            if not self.isReady:
                self._DoInit()

        XRCPanel.Show(self, show)

class HomePanel(wx.Panel):
    def __init__(self, parent, title, background):
        wx.Panel.__init__(self, parent)

        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility
        self.SetBackgroundColour(background)
        self.SetForegroundColour(parent.GetForegroundColour())

        vSizer = wx.BoxSizer(wx.VERTICAL)

        self.header = self.CreateHeader()
        self.header.SetTitle(title)
        self.header.SetBackgroundColour(background)
        vSizer.Add(self.header, 0, wx.EXPAND)

        self.panel = self.CreatePanel()
        if self.panel:
            vSizer.Add(self.panel, 1, wx.EXPAND|wx.LEFT|wx.RIGHT, 1)

        self.footer = self.CreateFooter()
        self.footer.SetBackgroundColour(background)
        vSizer.Add(self.footer, 0, wx.EXPAND)

        self.SetSizer(vSizer)
        self.Layout()

    def CreateHeader(self):
        return TitleHeader(self, self, [], radius=LIST_RADIUS)
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
        HomePanel.__init__(self, parent, 'Network info' , LIST_LIGHTBLUE)

        self.torrentdb = TorrentDBHandler.getInstance()
        self.channelcastdb = ChannelCastDBHandler.getInstance()
        self.remotetorrenthandler = RemoteTorrentHandler.getInstance()
        self.remotequerymsghandler = RemoteQueryMsgHandler.getInstance()
        self.incompleteCounter = IncompleteCounter.getInstance()

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
        self.nrChannels = StaticText(panel)
        self.incomplete = StaticText(panel)

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
        gridSizer.Add(StaticText(panel, -1, 'Channels found'))
        gridSizer.Add(self.nrChannels, 0, wx.EXPAND)
        gridSizer.Add(StaticText(panel, -1, 'Incomplete limit (cur, max, history, maxhistory)'))
        gridSizer.Add(self.incomplete, 0, wx.EXPAND)
        if self.freeMem:
            gridSizer.Add(StaticText(panel, -1, 'WX:Free memory'))
            gridSizer.Add(self.freeMem, 0, wx.EXPAND)

        vSizer.Add(gridSizer, 0, wx.EXPAND|wx.LEFT, 10)
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

        startWorker(None, db_callback, uId ="NetworkPanel_UpdateStats",priority=GUI_PRI_DISPERSY)

    @forceWxThread
    def _UpdateStats(self, stats, nr_channels):
        self.nrTorrents.SetLabel(str(stats[0]))
        if stats[1] is None:
            self.totalSize.SetLabel(str(stats[1]))
        else:
            self.totalSize.SetLabel(self.guiutility.utility.size_format(stats[1]))
        self.nrFiles.SetLabel(str(stats[2]))
        self.queueSize.SetLabel('%d (%d sources)'%self.remotetorrenthandler.getQueueSize())
        self.nrChannels.SetLabel(str(nr_channels))
        self.incomplete.SetLabel(", ".join(map(str, self.incompleteCounter.getstats())))
        
        if self.freeMem:
            self.freeMem.SetLabel(self.guiutility.utility.size_format(wx.GetFreeMemory()))

        if self.timer:
            self.timer.Restart(10000)
        else:
            self.timer = wx.CallLater(10000, self.UpdateStats)

class DispersyPanel(HomePanel):
    def __init__(self, parent):
        self.buildColumns = False
        self.dispersy = Dispersy.has_instance()
        if not self.dispersy:
            raise RuntimeError("Dispersy has not started yet")

        HomePanel.__init__(self, parent, 'Dispersy info' , LIST_LIGHTBLUE)

        self.SetMinSize((-1, 200))

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._onTimer, self.timer)
        self.timer.Start(5000, False)
        self.UpdateStats()

        self.mapping = {"total_down":[("Down", lambda info: self.utility.size_format(info["total_down"])),
                                      ("Down avg", lambda info: self.utility.size_format(int(info["total_down"] / info["runtime"])) + "/s")],
                        "total_up":[("Up", lambda info: self.utility.size_format(info["total_up"])),
                                    ("Up avg", lambda info: self.utility.size_format(int(info["total_up"] / info["runtime"])) + "/s")],
                        "drop":[("Dropped", lambda info: "%s ~%.1f%%" % (self.utility.size_format(int(sum(byte_count for _, byte_count in info["drop"].itervalues()))), (100.0 * sum(byte_count for _, byte_count in info["drop"].itervalues()) / info["total_down"]) if info["total_down"] else 0.0))],
                        "walk_success":[("Walker success", lambda info: "%d / %d ~%.1f%%" % (info["walk_success"], info["walk_attempt"], (100.0 * info["walk_success"] / info["walk_attempt"]) if info["walk_attempt"] else 0.0))],
                        "walk_reset":[("Walker resets", lambda info: str(info["walk_reset"]))],
                        "wan_address":[("Address WAN", lambda info: "%s:%d" % info["wan_address"])],
                        "lan_address":[("Address LAN", lambda info: "%s:%d" % info["lan_address"])],
                        "runtime":[("Runtime", lambda info: self.utility.eta_value(info["runtime"]))],
                        "walk_attempt":[],
                        "outgoing":[],
                        "timestamp":[],
                        "class":[],
                        "success":[],
                        "delay":[],
                        "version":[],
                        "communities":[],
                        "sequence_number":[],
                        "start":[],
                        "walk_fail":[],
                        "attachment":[],
                        "revision":[("Version", lambda info: str(max(info["revision"].itervalues())))],
                        "drop_count":[],
                        "success_count":[("Packet success", lambda info: "%d / %d ~%.1f%%" % (info["success_count"] - info["drop_count"], info["success_count"], 100.0 * (info["success_count"] - info["drop_count"]) / info["success_count"] if info["success_count"] else 0.0))]}

    def CreatePanel(self):
        panel = wx.Panel(self)
        panel.SetBackgroundColour(DEFAULT_BACKGROUND)
        vSizer = wx.BoxSizer(wx.HORIZONTAL)

        self.gridSizer = wx.FlexGridSizer(0, 2, 3, 10)
        self.gridSizer.AddGrowableCol(1)

        vSizer.Add(self.gridSizer, 0, wx.EXPAND|wx.LEFT, 10)

        vSumSizer = wx.BoxSizer(wx.VERTICAL)
        self.summary_tree = wx.TreeCtrl(panel, style = wx.TR_DEFAULT_STYLE|wx.TR_HIDE_ROOT|wx.NO_BORDER)
        self.summary_tree.blockUpdate = False
        self.summary_tree.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouseEvent)
        self.summary_tree.Bind(wx.EVT_MOTION, self.OnMouseEvent)

        font = self.summary_tree.GetFont()
        font = wx.Font(font.GetPointSize(), wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.summary_tree.SetFont(font)
        
        vSumSizer.Add(self.summary_tree, 1, wx.EXPAND)
        self.includeStuffs = wx.CheckBox(panel, -1, "Include stuffs")
        vSumSizer.Add(self.includeStuffs, 0, wx.TOP|wx.BOTTOM, 3)
        
        vSizer.Add(vSumSizer, 2, wx.EXPAND|wx.LEFT, 10)

        self.tree = wx.TreeCtrl(panel, style = wx.TR_DEFAULT_STYLE|wx.TR_HIDE_ROOT|wx.NO_BORDER)
        self.tree.blockUpdate = False
        self.tree.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouseEvent)
        self.tree.Bind(wx.EVT_MOTION, self.OnMouseEvent)
        vSizer.Add(self.tree, 1, wx.EXPAND|wx.LEFT, 10)

        panel.SetSizer(vSizer)
        return panel

    def CreateColumns(self, info):
        self.textdict = {}
        def addColumn(key):
            strkey = key.replace("_", " ").capitalize()
            header = StaticText(self.panel, -1, strkey)
            _set_font(header, fontweight=wx.FONTWEIGHT_BOLD)
            self.gridSizer.Add(header)
            self.textdict[key] = StaticText(self.panel, -1, '')
            self.textdict[key].SetMinSize((200,-1))
            self.gridSizer.Add(self.textdict[key])

        columns = ["in_debugmode"]
        for key in info.iterkeys():
            for title, _ in self.mapping.get(key, [(key, None)]):
                columns.append(title)

        for title in sorted(columns):
            addColumn(title)

        self.buildColumns = True

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

    def UpdateStats(self):
        includeStuffs = self.includeStuffs.GetValue()

        def db_callback():
            info = self.dispersy.info(database_sync=includeStuffs)
            self._UpdateStats(info)

        startWorker(None, db_callback, uId ="DispersyPanel_UpdateStats",priority=GUI_PRI_DISPERSY)

    @forceWxThread
    def _UpdateStats(self, info):
        if not self.buildColumns:
            self.CreateColumns(info)

        def addValue(parentNode, value):
            if isinstance(value, dict):
                addDict(parentNode, value)
            elif isinstance(value, list):
                addList(parentNode, value)
            else:
                self.tree.AppendItem(parentNode, str(value))

        def addList(parentNode, nodelist):
            for key, value in enumerate(nodelist):
                keyNode = self.tree.AppendItem(parentNode, str(key))
                addValue(keyNode, value)

        def addDict(parentNode, nodedict):
            for key, value in nodedict.items():
                try:
                    keyNode = self.tree.AppendItem(parentNode, str(key))
                except UnicodeDecodeError:
                    keyNode = self.tree.AppendItem(parentNode, key.encode("HEX"))
                addValue(keyNode, value)

        def updateColumn(key, value):
            # if key.find('address') != -1:
            #     value = "%s:%d"%value
            self.textdict[key].SetLabel(str(value))

        # center tree
        if not self.summary_tree.blockUpdate:
            self.summary_tree.DeleteAllItems()
            if "communities" in info:
                root = self.summary_tree.AddRoot("fake")
                def communitykey(community):
                    hasCandidates = 1
                    if community["attributes"]["dispersy_enable_candidate_walker"] or community["attributes"]["dispersy_enable_candidate_walker_responses"]:
                        hasCandidates = 0
                    elif community["candidates"]:
                        hasCandidates = 0
                    return (hasCandidates, community["classification"], community["hex_cid"])
                
                for community in sorted(info["communities"], key=communitykey):
                    if community["attributes"]["dispersy_enable_candidate_walker"] or community["attributes"]["dispersy_enable_candidate_walker_responses"]:
                        candidates = "%d " % len(community["candidates"])
                    elif community["candidates"]:
                        candidates = "%d*" % len(community["candidates"])
                    else:
                        candidates = "- "
                    total_packets = sum(community["database_sync"].itervalues()) if "database_sync" in community else -1
                    parent = self.summary_tree.AppendItem(root, u"%s %6d %3s %s @%d ~%d" % (community["hex_cid"], total_packets, candidates, community["classification"], community["global_time"], community["acceptable_global_time"] - community["global_time"] - community["dispersy_acceptable_global_time_range"]))
                    self.summary_tree.AppendItem(parent, u"member:             %s" % community["hex_mid"])
                    self.summary_tree.AppendItem(parent, u"classification:     %s" % community["classification"])
                    self.summary_tree.AppendItem(parent, u"database id:        %d" % community["database_id"])
                    self.summary_tree.AppendItem(parent, u"global time:        %d" % community["global_time"])
                    self.summary_tree.AppendItem(parent, u"median global time: %d (%d difference)" % (community["acceptable_global_time"] - community["dispersy_acceptable_global_time_range"], community["acceptable_global_time"] - community["global_time"] - community["dispersy_acceptable_global_time_range"]))
                    self.summary_tree.AppendItem(parent, u"acceptable range:   %d" % community["dispersy_acceptable_global_time_range"])
                    if community["attributes"]["dispersy_enable_candidate_walker"] or community["attributes"]["dispersy_enable_candidate_walker_responses"]:
                        sub_parent = self.summary_tree.AppendItem(parent, u"candidates: %s" % candidates)
                        for candidate in sorted(("@%d %s:%d" % (global_time, wan_address[0], wan_address[1]) if lan_address == wan_address else "@%d %s:%d, %s:%d" % (global_time, wan_address[0], wan_address[1], lan_address[0], lan_address[1]))
                                                for lan_address, wan_address, global_time
                                                in community["candidates"]):
                            self.summary_tree.AppendItem(sub_parent, candidate)
                    if "database_sync" in community:
                        sub_parent = self.summary_tree.AppendItem(parent, u"database: %d packets" % sum(count for count in community["database_sync"].itervalues()))
                        for name, count in sorted(community["database_sync"].iteritems(), key=lambda tup: tup[1]):
                            self.summary_tree.AppendItem(sub_parent, "%s: %d" % (name, count))
                    # self.summary_tree.Expand(parent)
                # self.summary_tree.ExpandAll()


        # left tree
        if not self.tree.blockUpdate:
            self.tree.DeleteAllItems()
            fakeRoot = self.tree.AddRoot('fake')
            for key, value in info.iteritems():
                for title, func in self.mapping.get(key, [(key, lambda info: str(info[key]))]):
                    updateColumn(title, func(info))
            updateColumn("in_debugmode", str(__debug__))

            parentNode = self.tree.AppendItem(fakeRoot, "raw info")
            addValue(parentNode, info)

        self.panel.Layout()

class NewTorrentPanel(HomePanel):
    def __init__(self, parent):
        HomePanel.__init__(self, parent, 'Newest Torrents' , LIST_LIGHTBLUE)
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

        startWorker(None, db_callback, uId ="NewTorrentPanel_UpdateStats",priority=GUI_PRI_DISPERSY)

    @forceWxThread
    def _UpdateStats(self, torrent):
        self.list.InsertStringItem(0, torrent['name'])
        size = self.list.GetItemCount()
        if size > 10:
            self.list.DeleteItem(size-1)

    def OnDoubleClick(self, event):
        selected = self.list.GetFirstSelected()
        if selected != -1:
            selected_file = self.list.GetItemText(selected)
            self.guiutility.dosearch(selected_file)

class PopularTorrentPanel(NewTorrentPanel):
    def __init__(self, parent):
        HomePanel.__init__(self, parent, 'Popular Torrents' , LIST_LIGHTBLUE)
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

            topTen = self.torrentdb._db.getAll("CollectedTorrent", ("infohash", "name", "(num_seeders+num_leechers) as popularity"), where = familyfilter_sql , order_by = "(num_seeders+num_leechers) DESC", limit= 10)
            self._RefreshList(topTen)

        startWorker(None, db_callback, uId ="PopularTorrentPanel_RefreshList",priority=GUI_PRI_DISPERSY)

    @forceWxThread
    def _RefreshList(self, topTen):
        self.list.Freeze()
        self.list.DeleteAllItems()
        for item in topTen:
            if item[2] > 0:
                self.list.InsertStringItem(sys.maxint, item[1])
        self.list.Thaw()

class TopContributorsPanel(HomePanel):
    def __init__(self, parent):
        HomePanel.__init__(self, parent, 'Top Contributors' , LIST_LIGHTBLUE)
        self.Layout()

        self.peerdb = PeerDBHandler.getInstance()
        self.barterdb = BarterCastDBHandler.getInstance()

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._onTimer, self.timer)
        self.timer.Start(10000, False)
        self.RefreshList()

    def CreatePanel(self):
        self.list = BetterListCtrl(self)
        self.list.InsertColumn(0, 'Name')
        self.list.InsertColumn(1, 'Up', wx.LIST_FORMAT_RIGHT)
        self.list.setResizeColumn(0)

        return self.list

    def _onTimer(self, event):
        if self.IsShownOnScreen():
            self.RefreshList()

    def RefreshList(self):
        def db_callback():
            topTen = self.barterdb.getTopNPeers(10)
            self._RefreshList(topTen)

        startWorker(None, db_callback, uId ="TopContributorsPanel_RefreshList",priority=GUI_PRI_DISPERSY)

    @forceWxThread
    def _RefreshList(self, topTen):
        self.list.Freeze()
        self.list.DeleteAllItems()
        for item in topTen['top']:
            name = self.peerdb.getPeer(item[0], 'name')
            if name:
                pos = self.list.InsertStringItem(sys.maxint, name)
                self.list.SetStringItem(pos, 1, self.guiutility.utility.size_format(item[1], 1))

        self.list.SetColumnWidth(1, wx.LIST_AUTOSIZE)
        self.list.Layout()
        self.list.Thaw()

    def OnDoubleClick(self, event):
        pass

class ActivityPanel(NewTorrentPanel):
    def __init__(self, parent):
        HomePanel.__init__(self, parent, 'Recent Activity' , LIST_LIGHTBLUE)

    @forceWxThread
    def onActivity(self, msg):
        msg = strftime("%H:%M:%S ") + msg
        self.list.InsertStringItem(0, msg)
        size = self.list.GetItemCount()
        if size > 50:
            self.list.DeleteItem(size-1)

class BuzzPanel(wx.Panel):
    INACTIVE_COLOR = (255, 51, 0)
    ACTIVE_COLOR = (0, 105, 156)

    TERM_BORDERS = [15, 8, 8]
    DISPLAY_SIZES = [3,5,5]
    REFRESH_EVERY = 5

    def __init__(self, parent):
        wx.Panel.__init__(self, parent)
        self.SetBackgroundColour(wx.WHITE)
        self.SetForegroundColour(parent.GetForegroundColour())
                
        #Niels 04-06-2012: termextraction needs a session variable, create instance from mainthread
        TermExtraction.getInstance()

        self.nbdb       = None
        self.xxx_filter = Category.getInstance().xxx_filter
        self.guiutility = GUIUtility.getInstance()
        self.utility    = self.guiutility.utility

        vSizer = wx.BoxSizer(wx.VERTICAL)        
        for colour, height, text in [(SEPARATOR_GREY, 1, None), (FILTER_GREY, 25, "Click below to explore what's hot"), (SEPARATOR_GREY, 1, None)]:
            panel = wx.Panel(self)
            panel.SetMinSize((-1,height))
            panel.SetBackgroundColour(colour)
            panel.Bind(wx.EVT_ENTER_WINDOW, lambda event: self.OnLeaveWindow())
            if text:
                stext = wx.StaticText(panel, label = text)
                _set_font(stext, fontweight = wx.FONTWEIGHT_BOLD, fontcolour = wx.BLACK)
                sizer = wx.BoxSizer(wx.HORIZONTAL)
                sizer.Add(stext, 0, wx.CENTER|wx.LEFT, 5)
                panel.SetSizer(sizer)
            vSizer.Add(panel, 0, wx.EXPAND)
        vSizer.AddSpacer((-1,10))

        self.panel = wx.Panel(self)
        self.panel.SetBackgroundColour(DEFAULT_BACKGROUND)
        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        self.panel.SetSizer(self.vSizer)
        vSizer.Add(self.panel, 1, wx.EXPAND|wx.BOTTOM, 5)

        self.footer = wx.StaticText(self)
        vSizer.Add(self.footer, 0, wx.ALIGN_RIGHT|wx.RIGHT|wx.BOTTOM, 1)

        self.tags = []
        self.buzz_cache = [[],[],[]]
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
        _set_font(text, fontcolour = BuzzPanel.INACTIVE_COLOR)
        self.vSizer.AddStretchSpacer()
        self.vSizer.Add(text, 0, wx.ALIGN_CENTER)
        self.vSizer.AddStretchSpacer()

        self.refresh = 5
        self.GetBuzzFromDB(doRefresh=True,samplesize=10)
        self.guiutility.addList(self)

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnRefreshTimer, self.timer)
        self.timer.Start(1000, False)

        self.SetSizer(vSizer)
        self.Layout()
   
    def do_or_schedule_refresh(self, force_refresh = False):
        # Only called when the FF is toggled.
        if self.guiutility.ShouldGuiUpdate():
            self.ForceUpdate()
        else:
            self.refresh = -1

    def ForceUpdate(self):
        self.GetBuzzFromDB(doRefresh=True)
    
    def GetBuzzFromDB(self, doRefresh=False, samplesize = NetworkBuzzDBHandler.DEFAULT_SAMPLE_SIZE):
        def do_db():
            if self.nbdb == None:
                self.nbdb = NetworkBuzzDBHandler.getInstance()
            
            self.buzz_cache = [[],[],[]]
            buzz = self.nbdb.getBuzz(samplesize, with_freq=True, flat=True)
            for i in range(len(buzz)):
                random.shuffle(buzz[i])
                self.buzz_cache[i] = buzz[i]
    
            if len(self.tags) <= 1 and len(buzz) > 0 or doRefresh:
                self.OnRefreshTimer(force = True, fromDBThread = True)
        startWorker(None, do_db, uId="NetworkBuzz.GetBuzzFromDB", priority=GUI_PRI_DISPERSY)


    @forceWxThread
    def OnRefreshTimer(self, event = None, force = False, fromDBThread = False):
        if event:
            if self.DoPauseResume():
                return
        
        self.refresh -= 1
        if self.refresh <= 0 or force or fromDBThread:
            if (self.IsShownOnScreen() and self.guiutility.ShouldGuiUpdate()) or force or fromDBThread:
                # simple caching
                # (Completely throws away the old cache and refills it)
                if any(len(row) < 10 for row in self.buzz_cache) and not fromDBThread:
                    self.GetBuzzFromDB(doRefresh = True)
                    return

                if self.guiutility.getFamilyFilter():
                    xxx_filter = self.xxx_filter.isXXX
                else:
                    xxx_filter = lambda *args, **kwargs: False

                # consume cache
                # Note: if a term is fetched from two different row caches, it is shown in the
                # higher-frequency row, regardless of which information is fresher.
                filtered_buzz = [[],[],[]]
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

        self.footer.SetLabel('Update in %d...'%self.refresh)
        self.Layout()

    def getStaticText(self, term, font = None):
        if len(self.tags) > 0:
            text = self.tags.pop()
            text.SetLabel(term)
            text.SetFonts([font, font])
            text.Reset()

        else:
            text = LinkText(self.panel, term, fonts=[font, font], colours = [BuzzPanel.INACTIVE_COLOR, BuzzPanel.ACTIVE_COLOR])
            text.SetBackgroundColour(DEFAULT_BACKGROUND)
            text.Bind(wx.EVT_LEFT_UP, self.OnClick)
        text.SetToolTipString("Click to search for '%s'"%term)
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
        timerstop = not enter #stop timer if one control has enter==true

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

    def OnLeaveWindow(self, event = None):
        if event:
            evtobj = event.GetEventObject()
            evtobj.enter = False

        wx.CallAfter(self.DoPauseResume)

    def OnClick(self, event):
        evtobj = event.GetEventObject()
        term = evtobj.GetLabel()
        if term <> '...collecting buzz information...':
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

# ProxyService 90s Test_
#
#class NetworkTestPanel(HomePanel):
#    def __init__(self, parent):
#        HomePanel.__init__(self, parent, 'Network Test' , LIST_LIGHTBLUE)
#
#        self.timer = None
#
#        self.UpdateStats()
#
#    def CreatePanel(self):
#        panel = wx.Panel(self)
#        panel.SetBackgroundColour(DEFAULT_BACKGROUND)
#        vSizer = wx.BoxSizer(wx.VERTICAL)
#
#        self.eligibleCandidate = wx.StaticText(panel)
#        self.activeCandidate = wx.StaticText(panel)
#        self.testProgress = wx.StaticText(panel)
#        self.testDuration = wx.StaticText(panel)
#        self.nrPeers = wx.StaticText(panel)
##        self.smallestChunk = wx.StaticText(panel)
#
#        gridSizer = wx.FlexGridSizer(0, 2, 3, 3)
#        gridSizer.AddGrowableCol(1)
#
#        gridSizer.Add(wx.StaticText(panel, -1, 'Eligible Candidate'), 0, wx.LEFT, 10)
#        gridSizer.Add(self.eligibleCandidate, 0, wx.EXPAND|wx.LEFT, 10)
#        gridSizer.Add(wx.StaticText(panel, -1, 'Active Candidate'), 0, wx.LEFT, 10)
#        gridSizer.Add(self.activeCandidate, 0, wx.EXPAND|wx.LEFT, 10)
#        gridSizer.Add(wx.StaticText(panel, -1, 'Test status'), 0, wx.LEFT, 10)
#        gridSizer.Add(self.testProgress, 0, wx.EXPAND|wx.LEFT, 10)
#        gridSizer.Add(wx.StaticText(panel, -1, 'Test duration'), 0, wx.LEFT, 10)
#        gridSizer.Add(self.testDuration, 0, wx.EXPAND|wx.LEFT, 10)
#        gridSizer.Add(wx.StaticText(panel, -1, '# of peers used'), 0, wx.LEFT, 10)
#        gridSizer.Add(self.nrPeers, 0, wx.EXPAND|wx.LEFT, 10)
##        gridSizer.Add(wx.StaticText(panel, -1, 'Smallest chunk (MB)'), 0, wx.LEFT, 10)
##        gridSizer.Add(self.smallestChunk, 0, wx.EXPAND|wx.LEFT, 10)
#
#        vSizer.Add(gridSizer, 0, wx.EXPAND)
#        panel.SetSizer(vSizer)
#        return panel
#
#    def OnNotify(self, subject, type, infohash):
#        if self.IsShownOnScreen():
#            self.UpdateStats()
#
#    def UpdateStats(self):
#        def stats_callback():
#            #candidate
#            from Tribler.Core.Session import Session
#            session = Session.get_instance()
#            if session.lm.overlay_apps.proxy_peer_manager.am_i_connectable():
#                eligibleCandidate = "Y"
#            else:
#                eligibleCandidate = "N"
#
#            #active candidate
#            if session.get_proxyservice_status() == PROXYSERVICE_ON:
#                activeCandidate = "Y"
#            else:
#                activeCandidate = "N"
#            if eligibleCandidate == "N":
#                activeCandidate = "N"
#
#            #testProgress
#            if session.get_90stest_state():
#                progress = "in progress..."
#            else:
#                progress = "done"
#
#            # testDuration
#            if session.get_90stest_state():
#                duration = long(round(time() - session.start_time))
#            else:
#                duration = 0
#
#            # nrPeers
#            nrPeers = 0
#            guiUtility = GUIUtility.getInstance()
#            dlist = guiUtility.utility.session.get_downloads()
#            for d in dlist:
#                safename = `d.get_def().get_name()`
#                if safename == "'Data.90s-test.8M.bin'":
#                    nrPeers = d.sd.dow.proxydownloader.doe.get_nr_used_proxies()
#
#            stats = []
#            stats.append(eligibleCandidate)
#            stats.append(activeCandidate)
#            stats.append(progress)
#            stats.append(duration)
#            stats.append(nrPeers)
#
#            wx.CallAfter(self._UpdateStats, stats)
#
#        self.guiserver.add_task(stats_callback, id = "NetworkTest_UpdateStats")
#
#    def _UpdateStats(self, stats):
#        self.eligibleCandidate.SetLabel(str(stats[0]))
#        self.activeCandidate.SetLabel(str(stats[1]))
#        self.testProgress.SetLabel(str(stats[2]))
#        self.testDuration.SetLabel(str(stats[3])+" sec")
#        self.nrPeers.SetLabel(str(stats[4]))
##        self.largestChunk.SetLabel(str("0"+" MB"))
##        self.smallestChunk.SetLabel(str("0"+" MB"))
#
#        if self.timer:
#            self.timer.Restart(1000)
#        else:
#            self.timer = wx.CallLater(1000, self.UpdateStats)
#
# _ProxyService 90s Test

# ProxyService 90s Test_
#
#class ProxyDiscoveryPanel(NewTorrentPanel):
#    def __init__(self, parent):
#        HomePanel.__init__(self, parent, 'Peer Discovery' , LIST_LIGHTBLUE)
#
#        session = Session.get_instance()
#        session.add_observer(self.OnNotify, NTFY_PROXYDISCOVERY, [NTFY_INSERT])
#
#        self.proxies=[]
#        self.OnNotify(None, None, None, session.lm.overlay_apps.proxy_peer_manager.available_proxies.keys())
#
#    def OnNotify(self, subject, changeType, objectID, *args):
#        """  Handler registered with the session observer
#
#        @param subject The subject to observe, one of NTFY_* subjects (see simpledefs).
#        @param changeTypes The list of events to be notified of one of NTFY_* events.
#        @param objectID The specific object in the subject to monitor (e.g. a specific primary key in a database to monitor for updates.)
#        @param args: A list of optional arguments.
#        """
#        proxy_permid_list=args[0]
#        wx.CallAfter(self._OnNotify, proxy_permid_list)
#
#    def _OnNotify(self, proxy_permid_list):
#        for proxy_permid in proxy_permid_list:
#            if proxy_permid not in self.proxies:
#                self.proxies.append(proxy_permid)
#
#                msg = strftime("%H:%M:%S ") + show_permid_short(proxy_permid)
#                self.list.InsertStringItem(0, msg)
#                size = self.list.GetItemCount()
#                if size > 50:
#                    self.list.DeleteItem(size-1)
#
# _ProxyService 90s Test
