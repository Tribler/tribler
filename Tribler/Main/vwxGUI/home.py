# Written by Niels Zeilemaker
import datetime
import logging
import os
import random
import sys
import binascii

from time import strftime, time
from traceback import print_exc

# pylint complaining if wx imported before those three
import wx

from Tribler.Category.Category import Category
from Tribler.Core.CacheDB.sqlitecachedb import bin2str
from Tribler.Core.Session import Session
from Tribler.Core.Video.VideoUtility import considered_xxx
from Tribler.Core.simpledefs import (NTFY_TORRENTS, NTFY_CHANNELCAST, NTFY_INSERT, NTFY_TUNNEL, NTFY_CREATED,
                                     NTFY_EXTENDED, NTFY_BROKEN, NTFY_SELECT, NTFY_JOINED, NTFY_EXTENDED_FOR,
                                     NTFY_IP_REMOVED, NTFY_RP_REMOVED, NTFY_IP_RECREATE, NTFY_DHT_LOOKUP,
                                     NTFY_KEY_REQUEST, NTFY_KEY_RESPOND, NTFY_KEY_RESPONSE, NTFY_CREATE_E2E,
                                     NTFY_ONCREATED_E2E, NTFY_IP_CREATED, NTFY_RP_CREATED, NTFY_REMOVE)
from Tribler.Main.Utility.GuiDBHandler import startWorker, GUI_PRI_DISPERSY
from Tribler.Main.Utility.utility import size_format
from Tribler.Main.vwxGUI import SEPARATOR_GREY, DEFAULT_BACKGROUND, LIST_BLUE, THUMBNAIL_FILETYPES
from Tribler.Main.vwxGUI.GuiImageManager import GuiImageManager
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility, forceWxThread
from Tribler.Main.vwxGUI.list_body import ListBody
from Tribler.Main.vwxGUI.list_footer import ListFooter
from Tribler.Main.vwxGUI.list_header import DetailHeader
from Tribler.Main.vwxGUI.list_item import ThumbnailListItemNoTorrent
from Tribler.Main.vwxGUI.widgets import (SelectableListCtrl, TextCtrlAutoComplete, BetterText as StaticText,
                                         LinkStaticText, ActionButton, HorizontalGauge, TagText)
from Tribler.Policies.credit_mining_util import string_to_source
from Tribler.community.multichain.community import MultiChainCommunity
from Tribler.community.tunnel.hidden_community import HiddenTunnelCommunity
from Tribler.community.tunnel.routing import Hop

# width size of channel grid
COLUMN_SIZE = 3
# how long the string before it cut
CHANNEL_STRING_LENGTH = 35
# number of popular torrent fetched to know the 'content' of channels
TORRENT_FETCHED = 5
# max number of channel shown in the panel
MAX_CHANNEL_SHOW = 9


class Home(wx.Panel):

    def __init__(self, parent):
        wx.Panel.__init__(self, parent)
        self.guiutility = GUIUtility.getInstance()
        self.gui_image_manager = GuiImageManager.getInstance()
        self.session = self.guiutility.utility.session
        self.boosting_manager = self.session.lm.boosting_manager

        #dispersy_cid:Channel
        self.channels = {}

        #dispersy_cid:Popular Torrents
        self.chn_torrents = {}

        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.AddStretchSpacer()

        text = StaticText(self, -1, "Tribler")
        font = text.GetFont()
        font.SetPointSize(font.GetPointSize() * 3)
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        text.SetForegroundColour((255, 51, 0))
        text.SetFont(font)

        if sys.platform == 'darwin':  # mac
            self.searchBox = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        else:
            self.searchBox = TextCtrlAutoComplete(self, entrycallback=parent.top_bg.complete)

        font = self.searchBox.GetFont()
        font.SetPointSize(font.GetPointSize() * 2)
        self.searchBox.SetFont(font)
        self.searchBox.Bind(wx.EVT_TEXT_ENTER, self.OnSearchKeyDown)

        if sys.platform == 'darwin':  # mac
            self.searchBox.SetMinSize((450, self.searchBox.GetTextExtent('T')[1] + 5))
        else:
            self.searchBox.SetMinSize((450, -1))
        self.searchBox.SetFocus()

        scalingSizer = wx.BoxSizer(wx.HORIZONTAL)

        search_img = GuiImageManager.getInstance().getImage(u"search.png")
        search_button = ActionButton(self, -1, search_img)
        search_button.Bind(wx.EVT_LEFT_UP, self.OnClick)

        scalingSizer.Add(self.searchBox, 0, wx.ALIGN_CENTER_VERTICAL)
        scalingSizer.AddSpacer(3, -1)
        scalingSizer.Add(search_button, 0, wx.ALIGN_CENTER_VERTICAL, 3)

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(StaticText(self, -1, "Take me to "))
        channelLink = LinkStaticText(self, "channels", icon=None)

        channelLink.Bind(wx.EVT_LEFT_UP, self.OnChannels)
        hSizer.Add(channelLink)
        hSizer.Add(StaticText(self, -1, " to see what others are sharing."))

        vSizer.Add(text, 0, wx.ALIGN_CENTER)
        vSizer.Add(scalingSizer, 1, wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_TOP)
        vSizer.Add(hSizer, 0, wx.ALIGN_CENTER)
        vSizer.AddStretchSpacer()

        # channel panel is for popular channel
        self.channel_panel = wx.lib.scrolledpanel.ScrolledPanel(self, 1)
        self.channel_panel.SetBackgroundColour(wx.WHITE)
        self.channel_panel.SetForegroundColour(parent.GetForegroundColour())

        v_chn_sizer = wx.BoxSizer(wx.VERTICAL)
        v_chn_sizer.Add(
            DetailHeader(self.channel_panel, "Select popular channels to mine"),
            0, wx.EXPAND, 5)

        self.loading_channel_txt = wx.StaticText(self.channel_panel, 1,
                                                 'Loading, please wait.'
                                                 if self.boosting_manager else "Credit Mining inactive")

        v_chn_sizer.Add(self.loading_channel_txt, 1, wx.TOP | wx.ALIGN_CENTER_HORIZONTAL, 10)

        self.chn_sizer = wx.FlexGridSizer(0, COLUMN_SIZE, 5, 5)

        for i in xrange(0, COLUMN_SIZE):
            if wx.MAJOR_VERSION > 2:
                if self.chn_sizer.IsColGrowable(i):
                    self.chn_sizer.AddGrowableCol(i, 1)
            else:
                self.chn_sizer.AddGrowableCol(i, 1)

        v_chn_sizer.Add(self.chn_sizer, 0, wx.EXPAND, 5)

        self.channel_panel.SetSizer(v_chn_sizer)
        self.channel_panel.SetupScrolling()

        vSizer.Add(self.channel_panel, 5, wx.EXPAND)

        # video thumbnail panel
        self.aw_panel = ArtworkPanel(self)
        self.aw_panel.SetMinSize((-1, 275))
        self.aw_panel.Show(self.guiutility.ReadGuiSetting('show_artwork', False))
        vSizer.Add(self.aw_panel, 0, wx.EXPAND)

        self.SetSizer(vSizer)
        self.Layout()
        self.Bind(wx.EVT_RIGHT_UP, self.OnRightClick)
        self.SearchFocus()

        self.channel_list_ready = False

        if self.boosting_manager:
            self.session.lm.threadpool.add_task(self.refresh_channels_home, 10,
                                                task_name=str(self.__class__)+"_refreshchannel")

    def OnRightClick(self, event):
        menu = wx.Menu()
        itemid_rcvid = wx.NewId()
        itemid_popchn = wx.NewId()
        menu.AppendCheckItem(itemid_rcvid, 'Show recent videos')
        menu.AppendCheckItem(itemid_popchn, 'Show popular channels')

        menu.Check(itemid_rcvid, self.aw_panel.IsShown())
        menu.Check(itemid_popchn, self.channel_panel.IsShown())

        def toggleArtwork(event):
            show = not self.aw_panel.IsShown()
            self.aw_panel.Show(show)
            self.guiutility.WriteGuiSetting("show_artwork", show)
            self.Layout()

        def togglechannels(_):
            show = not self.channel_panel.IsShown()
            self.channel_panel.Show(show)
            self.Layout()

        menu.Bind(wx.EVT_MENU, togglechannels, id=itemid_popchn)
        menu.Bind(wx.EVT_MENU, toggleArtwork, id=itemid_rcvid)

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

    def create_channel_item(self, parent, channel, torrents, max_fav):
        """
        Function to create channel (and its torrents) checkbox on home panel
        """

        from Tribler.Main.Utility.GuiDBTuples import Channel as ChannelObj
        assert isinstance(channel, ChannelObj), "Type channel should be ChannelObj %s" % channel

        vsizer = wx.BoxSizer(wx.VERTICAL)
        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        chn_pn = wx.Panel(parent, -1, style=wx.SUNKEN_BORDER)

        cb_chn = wx.CheckBox(chn_pn, 1, '', name=binascii.hexlify(channel.dispersy_cid))
        obj = self.boosting_manager.get_source_object(channel.dispersy_cid)

        cb_chn.SetValue(False if not obj else obj.enabled)

        control = HorizontalGauge(chn_pn, self.gui_image_manager.getImage(u"ministar.png"),
                                  self.gui_image_manager.getImage(u"ministarEnabled.png"), 5)

        # count popularity
        pop = channel.nr_favorites
        if pop <= 0 or max_fav == 0:
            control.SetPercentage(0)
        else:
            control.SetPercentage(pop/float(max_fav))

        control.SetToolTipString('%s users marked this channel as one of their favorites.' % pop)
        hsizer.Add(cb_chn, 0, wx.ALIGN_LEFT)
        hsizer.Add(TagText(chn_pn, -1, label='channel', fill_colour=wx.Colour(210, 252, 120)), 0,
                   wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)
        hsizer.AddSpacer(5)
        hsizer.Add(wx.StaticText(chn_pn, -1, channel.name.encode('utf-8')), 0, wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)
        hsizer.AddSpacer(30)
        hsizer.AddStretchSpacer()
        hsizer.Add(control, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)

        vsizer.Add(hsizer, 0, wx.EXPAND)

        for trnts in torrents:
            trnts = wx.StaticText(chn_pn, 1, trnts.name[:CHANNEL_STRING_LENGTH] + (trnts.name[CHANNEL_STRING_LENGTH:]
                                                                                   and '...'))
            vsizer.Add(trnts, 0, wx.EXPAND | wx.LEFT, 25)

        chn_pn.SetSizer(vsizer)
        self.Bind(wx.EVT_CHECKBOX, self.on_check_channels_cm, cb_chn)
        return chn_pn

    def refresh_channels_home(self):
        """
        This function will be called to get popular channel list in Home
        """
        def do_query():
            """
            querying channels to show at home page. Blocking
            :return: dict_channels, dict_torrents, new_channels_ids
            """
            _, channels = self.guiutility.channelsearch_manager.getPopularChannels(2 * MAX_CHANNEL_SHOW)

            dict_channels = {channel.dispersy_cid: channel for channel in channels}
            dict_torrents = {}
            new_channels_ids = list(set(dict_channels.keys()) -
                                    set(self.channels.keys() if not self.channel_list_ready else []))

            for chan_id in new_channels_ids:
                channel = dict_channels.get(chan_id)
                torrents = self.guiutility.channelsearch_manager.getRecentReceivedTorrentsFromChannel(
                    channel, limit=TORRENT_FETCHED)[2]
                dict_torrents[chan_id] = torrents
            return dict_channels, dict_torrents, new_channels_ids

        def do_gui(delayed_result):
            """
            put those new channels in the GUI
            """
            (dict_channels, dict_torrents, new_channels_ids) = delayed_result.get()
            count = 0

            if self.channel_list_ready:
                # reset it. Not reseting torrent_dict because it dynamically added anyway
                self.channels = {}

            for chn_id in new_channels_ids:
                channel = dict_channels.get(chn_id)
                self.channels[chn_id] = channel
                self.chn_torrents.update(dict_torrents)

            self.chn_sizer.Clear(True)
            self.chn_sizer.Layout()
            self.loading_channel_txt.Show()
            for i in xrange(0, COLUMN_SIZE):
                if wx.MAJOR_VERSION > 2:
                    if self.chn_sizer.IsColGrowable(i):
                        self.chn_sizer.AddGrowableCol(i, 1)
                else:
                    self.chn_sizer.AddGrowableCol(i, 1)

            sortedchannels = sorted(self.channels.values(),
                                    key=lambda z: z.nr_favorites if z else 0, reverse=True)

            max_favourite = sortedchannels[0].nr_favorites if sortedchannels else 0

            for chn_id in [x for x in sortedchannels]:
                d = chn_id.dispersy_cid
                # if we can't find channel details, ignore it, or
                # if no torrent available for that channel
                if not dict_channels.get(d) or not len(self.chn_torrents.get(d)):
                    continue

                if self.session.get_creditmining_enable():
                    self.chn_sizer.Add(
                        self.create_channel_item(self.channel_panel, dict_channels.get(d), self.chn_torrents.get(d),
                                                 max_favourite), 0, wx.ALL | wx.EXPAND)

                self.loading_channel_txt.Hide()

                count += 1
                if count >= MAX_CHANNEL_SHOW:
                    break

            if new_channels_ids:
                self.chn_sizer.Layout()
                self.channel_panel.SetupScrolling()

        # quit refreshing if Tribler quitting
        if GUIUtility.getInstance().utility.abcquitting:
            return

        if self.guiutility.frame.ready and isinstance(self.guiutility.GetSelectedPage(), Home):
            startWorker(do_gui, do_query, retryOnBusy=True, priority=GUI_PRI_DISPERSY)

        repeat = len(self.channels) < MAX_CHANNEL_SHOW
        self.channel_list_ready = not repeat

        # try to update the popular channel once in a while
        self.session.lm.threadpool.add_task_in_thread(self.refresh_channels_home, 10,
                                                      task_name=str(self.__class__)+"_refreshchannel")

    def on_check_channels_cm(self, evt):
        """
        this callback called if a channel in home was checked/unchecked
        """
        cbox = evt.GetEventObject()
        source_str = cbox.GetName()

        # if we don't have the channel in boosting source, and its checked for the first time
        if not self.boosting_manager.get_source_object(string_to_source(source_str)) and evt.IsChecked():
            source = binascii.unhexlify(source_str)
            self.boosting_manager.add_source(source)
            self.boosting_manager.set_archive(source, False)

        self.boosting_manager.set_enable_mining(binascii.unhexlify(source_str), evt.IsChecked())

        if evt.IsChecked():
            chn_src = self.boosting_manager.boosting_sources[binascii.unhexlify(cbox.GetName())]
            sourcelist = self.guiutility.frame.creditminingpanel.sourcelist

            if binascii.unhexlify(cbox.GetName()) in sourcelist.channel_list:
                sourcelist.fix_channel_position(binascii.unhexlify(cbox.GetName()))
            else:
                sourcelist.create_source_item(chn_src)


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
        if self.guiutility.utility.session.get_enable_multichain():
            hSizer.Add(MultichainPanel(self), 1, wx.EXPAND | wx.RIGHT, 7)
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
                dlg = wx.DirDialog(None,
                                   "Please select your dowser installation directory",
                                   style=wx.wx.DD_DIR_MUST_EXIST)
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
        sqlite_db = self.guiutility.utility.session.sqlite_db
        tables = sqlite_db.fetchall("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        for table, in tables:
            self._logger.info("%s %s", table, sqlite_db.fetchone("SELECT COUNT(*) FROM %s" % table))

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

        self.torrentdb = parent.guiutility.utility.session.open_dbhandler(NTFY_TORRENTS)
        self.channelcastdb = parent.guiutility.utility.session.open_dbhandler(NTFY_CHANNELCAST)
        self.remotetorrenthandler = parent.guiutility.utility.session.lm.rtorrent_handler

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
            self.totalSize.SetLabel(size_format(stats[1]))
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
            self.freeMem.SetLabel(size_format(wx.GetFreeMemory()))

        if self.timer:
            self.timer.Restart(10000)
        else:
            self.timer = wx.CallLater(10000, self.UpdateStats)


class NewTorrentPanel(HomePanel):

    def __init__(self, parent):
        HomePanel.__init__(self, parent, 'Newest Torrents', SEPARATOR_GREY, (1, 1))
        self.Layout()

        session = parent.guiutility.utility.session
        self.torrentdb = session.open_dbhandler(NTFY_TORRENTS)
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

class MultichainPanel(HomePanel):

    def __init__(self, parent):
        HomePanel.__init__(self, parent, 'Multichain stats', SEPARATOR_GREY, (0, 1))

        self.dispersy = self.utility.session.lm.dispersy
        self.multichain_community = None
        self.find_multichain_community()

        self.timer = None
        self.UpdateStats()

    def find_multichain_community(self):
        try:
            self.multichain_community = next((c for c in self.dispersy.get_communities()
                                              if isinstance(c, MultiChainCommunity)))
        except StopIteration:
            wx.CallLater(1000, self.find_multichain_community)

    def CreatePanel(self):
        panel = wx.Panel(self)
        panel.SetBackgroundColour(DEFAULT_BACKGROUND)
        vSizer = wx.BoxSizer(wx.VERTICAL)

        self.self_id = StaticText(panel)
        self.self_total_blocks = StaticText(panel)
        self.self_total_up_mb = StaticText(panel)
        self.self_total_down_mb = StaticText(panel)
        self.latest_block_insert_time = StaticText(panel)
        self.latest_block_id = StaticText(panel)
        self.latest_block_requester_id = StaticText(panel)
        self.latest_block_responder_id = StaticText(panel)
        self.latest_block_up_mb = StaticText(panel)
        self.latest_block_down_mb = StaticText(panel)

        gridSizer = wx.FlexGridSizer(0, 2, 3, 10)
        gridSizer.AddGrowableCol(1)

        gridSizer.Add(StaticText(panel, -1, 'Multichain identity'))
        gridSizer.Add(self.self_id, 0, wx.EXPAND)
        gridSizer.Add(StaticText(panel, -1, 'Number of blocks'))
        gridSizer.Add(self.self_total_blocks, 0, wx.EXPAND)
        gridSizer.Add(StaticText(panel, -1, 'Total up (MB)'))
        gridSizer.Add(self.self_total_up_mb, 0, wx.EXPAND)
        gridSizer.Add(StaticText(panel, -1, 'Total down (MB)'))
        gridSizer.Add(self.self_total_down_mb, 0, wx.EXPAND)
        gridSizer.Add(StaticText(panel, -1, 'Latest block created'))
        gridSizer.Add(self.latest_block_insert_time, 0, wx.EXPAND)
        gridSizer.Add(StaticText(panel, -1, 'Latest block ID'))
        gridSizer.Add(self.latest_block_id, 0, wx.EXPAND)
        gridSizer.Add(StaticText(panel, -1, 'Latest block requester identity'))
        gridSizer.Add(self.latest_block_requester_id, 0, wx.EXPAND)
        gridSizer.Add(StaticText(panel, -1, 'Latest block responder identity'))
        gridSizer.Add(self.latest_block_responder_id, 0, wx.EXPAND)
        gridSizer.Add(StaticText(panel, -1, 'Latest block up (MB)'))
        gridSizer.Add(self.latest_block_up_mb, 0, wx.EXPAND)
        gridSizer.Add(StaticText(panel, -1, 'Latest block down (MB)'))
        gridSizer.Add(self.latest_block_down_mb, 0, wx.EXPAND)

        vSizer.Add(gridSizer, 0, wx.EXPAND | wx.LEFT, 7)
        panel.SetSizer(vSizer)
        return panel

    def UpdateStats(self):
        def db_callback():
            if self.multichain_community:
                multichain_statistics = self.multichain_community.get_statistics()
                self._UpdateStats(multichain_statistics)


        startWorker(None, db_callback, uId=u"MultichainPanel_UpdateStats", priority=GUI_PRI_DISPERSY)

    @forceWxThread
    def _UpdateStats(self, stats):
        self.self_id.SetLabel("..." + str(stats["self_id"])[-20:])
        self.self_total_blocks.SetLabel(str(stats["self_total_blocks"]))
        self.self_total_up_mb.SetLabel(str(stats["self_total_up_mb"]))
        self.self_total_down_mb.SetLabel(str(stats["self_total_down_mb"]))
        self.latest_block_insert_time.SetLabel(str(stats["latest_block_insert_time"]))
        self.latest_block_id.SetLabel("..." + str(stats["latest_block_id"])[-20:])
        self.latest_block_requester_id.SetLabel("..." + str(stats["latest_block_requester_id"])[-20:])
        self.latest_block_responder_id.SetLabel("..." + str(stats["latest_block_responder_id"])[-20:])
        self.latest_block_up_mb.SetLabel(str(stats["latest_block_up_mb"]))
        self.latest_block_down_mb.SetLabel(str(stats["latest_block_down_mb"]))

        if self.timer:
            self.timer.Restart(10000)
        else:
            self.timer = wx.CallLater(10000, self.UpdateStats)


class PopularTorrentPanel(NewTorrentPanel):

    def __init__(self, parent):
        HomePanel.__init__(self, parent, 'Popular Torrents', SEPARATOR_GREY, (1, 0))
        self.Layout()

        self.torrentdb = parent.guiutility.utility.session.open_dbhandler(NTFY_TORRENTS)

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._onTimer, self.timer)
        self.timer.Start(10000, False)
        self.RefreshList()

    def _onTimer(self, event):
        if self.IsShownOnScreen():
            self.RefreshList()

    def RefreshList(self):
        def db_callback():
            familyfilter_sql = Category.getInstance().get_family_filter_sql()
            if familyfilter_sql:
                familyfilter_sql = familyfilter_sql[4:]

            topTen = self.torrentdb._db.getAll(
                "CollectedTorrent", ("infohash", "name", "(num_seeders+num_leechers) as popularity"),
                where=familyfilter_sql,
                order_by="(num_seeders+num_leechers) DESC",
                limit=10)
            self._RefreshList(topTen)

        startWorker(None, db_callback, uId=u"PopularTorrentPanel_RefreshList", priority=GUI_PRI_DISPERSY)

    @forceWxThread
    def _RefreshList(self, topTen):
        if not self:
            return

        self.list.Freeze()
        self.list.DeleteAllItems()
        for item in topTen:
            if item[2] > 0:
                self.list.InsertStringItem(sys.maxint, item[1])
        self.list.Thaw()


class ActivityPanel(NewTorrentPanel):

    def __init__(self, parent):
        HomePanel.__init__(self, parent, 'Recent Activity', SEPARATOR_GREY, (1, 0))
        session = self.utility.session
        # TODO(emilon): This observer should be removed when shutting down.
        session.add_observer(self.on_tunnel_remove, NTFY_TUNNEL, [NTFY_REMOVE])

    @forceWxThread
    def onActivity(self, msg):
        msg = strftime("%H:%M:%S ") + msg
        self.list.InsertStringItem(0, msg)
        size = self.list.GetItemCount()
        if size > 50:
            self.list.DeleteItem(size - 1)

    @forceWxThread
    def on_tunnel_remove(self, subject, change_type, tunnel, candidate):
        if not self:
            return
        self.onActivity("Tunnel removed with: [Up = " + str(tunnel.bytes_up) +
                        " bytes | Down = " + str(tunnel.bytes_down) + " bytes]")


class NetworkGraphPanel(wx.Panel):

    def __init__(self, parent, fullscreen=True):
        wx.Panel.__init__(self, parent, -1)

        self.SetBackgroundColour(wx.WHITE)
        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility
        self.session = self.utility.session
        self.dispersy = self.utility.session.lm.dispersy

        self.swarm = GuiImageManager.getInstance().getImage(u"darknet.png")
        self.font_small = self.GetFont()
        self.font_large = self.GetFont()
        self.font_large.SetPointSize(self.font_large.GetPointSize() + 2)

        self.circuits = {}
        self.circuits_old = None
        self.hop_to_colour = {}
        self.colours = [wx.RED, wx.Colour(156, 18, 18),
                        wx.Colour(183, 83, 83),
                        wx.Colour(254, 134, 134),
                        wx.Colour(254, 190, 190)]

        self.selected_circuit = None
        self.hop_hover_evt = None
        self.hop_hover = None
        self.hop_active_evt = None
        self.hop_active = None

        self.hops = -1
        self.fullscreen = fullscreen
        self.radius = 20 if self.fullscreen else 12
        self.line_width = 2 if self.fullscreen else 1
        self.margin_x = self.margin_y = self.radius
        self.swarm_size = wx.Size(180, 60)

        self.AddComponents()

        self.tunnel_community = None
        self.try_community()

    def try_community(self):
        try:
            tunnel_community = (
                c for c in self.dispersy.get_communities(
                ) if isinstance(
                    c,
                    HiddenTunnelCommunity)).next(
            )
            self.found_community(tunnel_community)
        except:
            wx.CallLater(1000, self.try_community)

    def found_community(self, tunnel_community):
        self.tunnel_community = tunnel_community

        self.my_address = Hop(self.tunnel_community.my_member._ec.pub())
        self.my_address.address = ('127.0.0.1', "SELF")

        self.circuit_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnUpdateCircuits, self.circuit_timer)
        self.circuit_timer.Start(5000)

        if self.fullscreen:
            self.session.add_observer(self.OnExtended, NTFY_TUNNEL, [NTFY_CREATED, NTFY_EXTENDED, NTFY_BROKEN])
            self.session.add_observer(self.OnSelect, NTFY_TUNNEL, [NTFY_SELECT])
            self.session.add_observer(self.OnJoined, NTFY_TUNNEL, [NTFY_JOINED])
            self.session.add_observer(self.OnExtendedFor, NTFY_TUNNEL, [NTFY_EXTENDED_FOR])
            self.session.add_observer(self.OnIpRemoved, NTFY_TUNNEL, [NTFY_IP_REMOVED])
            self.session.add_observer(self.OnRpRemoved, NTFY_TUNNEL, [NTFY_RP_REMOVED])
            self.session.add_observer(self.OnIpRecreate, NTFY_TUNNEL, [NTFY_IP_RECREATE])
            self.session.add_observer(self.OnDhtLookup, NTFY_TUNNEL, [NTFY_DHT_LOOKUP])
            self.session.add_observer(self.OnKeyRequest, NTFY_TUNNEL, [NTFY_KEY_REQUEST])
            self.session.add_observer(self.OnKeyRespond, NTFY_TUNNEL, [NTFY_KEY_RESPOND])
            self.session.add_observer(self.OnKeyResponse, NTFY_TUNNEL, [NTFY_KEY_RESPONSE])
            self.session.add_observer(self.OnCreateE2E, NTFY_TUNNEL, [NTFY_CREATE_E2E])
            self.session.add_observer(self.OnCreatedE2E, NTFY_TUNNEL, [NTFY_ONCREATED_E2E])
            self.session.add_observer(self.OnIpCreated, NTFY_TUNNEL, [NTFY_IP_CREATED])
            self.session.add_observer(self.OnRpCreated, NTFY_TUNNEL, [NTFY_RP_CREATED])

    def AddComponents(self):
        self.graph_panel = wx.Panel(self, -1)
        self.graph_panel.Bind(wx.EVT_MOTION, self.OnMouse)
        self.graph_panel.Bind(wx.EVT_LEFT_UP, self.OnMouse)
        self.graph_panel.Bind(wx.EVT_PAINT, self.OnPaint)
        self.graph_panel.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)

        self.circuit_list = SelectableListCtrl(self, style=wx.LC_REPORT | wx.BORDER_SIMPLE)
        self.circuit_list.InsertColumn(0, 'ID', wx.LIST_FORMAT_LEFT, 25)
        self.circuit_list.InsertColumn(1, 'Online', wx.LIST_FORMAT_RIGHT, 50)
        self.circuit_list.InsertColumn(2, 'Hops', wx.LIST_FORMAT_RIGHT, 45)
        self.circuit_list.InsertColumn(3, u'Bytes \u2191', wx.LIST_FORMAT_RIGHT, 83)
        self.circuit_list.InsertColumn(4, u'Bytes \u2193', wx.LIST_FORMAT_RIGHT, 83)
        self.circuit_list.InsertColumn(5, 'Uptime', wx.LIST_FORMAT_RIGHT, 54)
        self.circuit_list.setResizeColumn(0)
        self.circuit_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnItemSelected)
        self.circuit_list.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.OnItemSelected)
        self.circuit_to_listindex = {}

        if self.fullscreen:
            self.log_text = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.BORDER_SIMPLE | wx.HSCROLL & wx.VSCROLL)
            self.log_text.SetEditable(False)
            self.log_text.Show(self.fullscreen)
            self.num_circuits_label = wx.StaticText(self, -1, "You have 0 circuit(s); 0 relay(s); \
                0 exit socket(s); 0 candidate(s)")

        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        self.vSizer.Add(self.circuit_list, 1, wx.EXPAND | wx.RESERVE_SPACE_EVEN_IF_HIDDEN, 0)
        if self.fullscreen:
            self.vSizer.Add(self.log_text, 1, wx.EXPAND | wx.TOP, 10)
            self.vSizer.Add(self.num_circuits_label, 0, wx.EXPAND | wx.TOP, 10)

        self.main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.main_sizer.Add(self.graph_panel, 3, wx.EXPAND | wx.LEFT | wx.TOP | wx.BOTTOM, 10)
        self.main_sizer.Add(self.vSizer, 2, wx.EXPAND | wx.ALL, 10)
        self.SetSizer(self.main_sizer)

    def ShowTunnels(self, hops):
        self.circuit_list.Show(hops != 0)
        self.hops = hops
        self.OnUpdateCircuits(None)

    def OnItemSelected(self, event):
        selected = []
        item = self.circuit_list.GetFirstSelected()
        while item != -1:
            selected.append(item)
            item = self.circuit_list.GetNextSelected(item)

        self.selected_circuit = None
        for item in selected:
            for circuit_id, listindex in self.circuit_to_listindex.iteritems():
                if listindex == item and circuit_id in self.circuits:
                    self.selected_circuit = self.circuits[circuit_id]
        self.graph_panel.Refresh()

    def OnUpdateCircuits(self, event):
        if not self.tunnel_community:
            return

        if self.fullscreen:
            self.num_circuits_label.SetLabel("You have %d circuit(s); %d relay(s); %d exit socket(s); %d candidate(s)" %
                                             (len(self.tunnel_community.circuits),
                                              len(self.tunnel_community.relay_from_to),
                                              len(self.tunnel_community.exit_sockets),
                                              sum(1 for _ in self.tunnel_community.dispersy_yield_verified_candidates())))

        new_circuits = dict(self.tunnel_community.circuits)
        self.circuits = {k: v for k, v in new_circuits.iteritems() if v.goal_hops == self.hops or self.hops < 0}

        # Add new circuits & update existing circuits
        for circuit_id, circuit in self.circuits.iteritems():
            if circuit_id not in self.circuit_to_listindex:
                pos = self.circuit_list.InsertStringItem(sys.maxint, str(circuit_id))
                self.circuit_to_listindex[circuit_id] = pos
            else:
                pos = self.circuit_to_listindex[circuit_id]
            self.circuit_list.SetStringItem(pos, 1, str(circuit.state))
            self.circuit_list.SetStringItem(pos, 2, str(len(circuit.hops)) + "/" + str(circuit.goal_hops))

            bytes_uploaded = circuit.bytes_up
            bytes_downloaded = circuit.bytes_down

            self.circuit_list.SetStringItem(pos, 3, size_format(bytes_uploaded))
            self.circuit_list.SetStringItem(pos, 4, size_format(bytes_downloaded))
            self.circuit_list.SetStringItem(pos, 5, "%d" % (time() - circuit.creation_time))

        # Remove old circuits
        old_circuits = [circuit_id for circuit_id in self.circuit_to_listindex if circuit_id not in self.circuits]
        for circuit_id in old_circuits:
            listindex = self.circuit_to_listindex[circuit_id]
            self.circuit_list.DeleteItem(listindex)
            self.circuit_to_listindex.pop(circuit_id)
            for k, v in self.circuit_to_listindex.items():
                if v > listindex:
                    self.circuit_to_listindex[k] = v - 1

        self.graph_panel.Refresh()

    def AppendToLog(self, msg):
        if not self:
            return
        self.log_text.AppendText('[%s]: %s' % (datetime.datetime.now().strftime("%H:%M:%S"), msg))

    @forceWxThread
    def OnExtended(self, subject, changeType, circuit):
        if not self:
            return
        if changeType == NTFY_CREATED:
            self.AppendToLog("Created circuit %s\n" % (circuit.circuit_id))
        if changeType == NTFY_EXTENDED:
            self.AppendToLog("Extended circuit %s\n" % (circuit.circuit_id))
        if changeType == NTFY_BROKEN:
            self.AppendToLog("Circuit %d has been broken\n" % circuit)

    @forceWxThread
    def OnSelect(self, subject, changeType, circuit, address):
        if not self:
            return
        self.AppendToLog("Circuit %d has been selected for destination %s\n" % (circuit, address))

    @forceWxThread
    def OnJoined(self, subject, changeType, address, circuit_id):
        if not self:
            return
        self.AppendToLog("Joined an external circuit %d with %s:%d\n" % (circuit_id, address[0], address[1]))

    @forceWxThread
    def OnExtendedFor(self, subject, changeType, extended_for, extended_with):
        if not self:
            return
        self.AppendToLog("Extended an external circuit (%s:%d, %d) with (%s:%d, %d)\n" % (
            extended_for[0].sock_addr[0], extended_for[0].sock_addr[1], extended_for[1], extended_with[0].sock_addr[0],
            extended_with[0].sock_addr[1], extended_with[1]))

    @forceWxThread
    def OnIpRemoved(self, subject, changeType, circuit_id):
        if not self:
            return
        self.AppendToLog("Removed introduction circuit %d\n" % (circuit_id))

    @forceWxThread
    def OnIpRecreate(self, subject, changeType, circuit_id, info_hash):
        if not self:
            return
        self.AppendToLog("Recreate introduction circuit to replace circuit %d for info_hash %s\n" % (circuit_id, info_hash))

    @forceWxThread
    def OnRpRemoved(self, subject, changeType, circuit_id):
        if not self:
            return
        self.AppendToLog("Removed rendezvous circuit %d\n" % (circuit_id))

    @forceWxThread
    def OnDhtLookup(self, subject, changeType, info_hash, peers):
        if not self:
            return
        self.AppendToLog("DHT lookup for info_hash %s resulted in peers: %s\n" % (info_hash, repr(peers)))

    @forceWxThread
    def OnKeyRequest(self, subject, changeType, info_hash, peer):
        if not self:
            return
        self.AppendToLog("Request key for info_hash %s from %s\n" % (info_hash, repr(peer)))

    @forceWxThread
    def OnKeyRespond(self, subject, changeType, info_hash, circuit_id):
        if not self:
            return
        self.AppendToLog("Respond with key for info_hash %s to circuit %s\n" % (info_hash, circuit_id))

    @forceWxThread
    def OnKeyResponse(self, subject, changeType, info_hash, circuit_id):
        if not self:
            return
        self.AppendToLog("Respond with key for info_hash %s to circuit %s\n" % (info_hash, circuit_id))

    @forceWxThread
    def OnCreateE2E(self, subject, changeType, info_hash):
        if not self:
            return
        self.AppendToLog("Create end-to-end for info_hash %s\n" % (info_hash))

    @forceWxThread
    def OnCreatedE2E(self, subject, changeType, info_hash, rp_addr):
        if not self:
            return
        self.AppendToLog("Connect rendezvous %s for info_hash %s\n" % (repr(rp_addr[0]), info_hash))

    @forceWxThread
    def OnIpCreated(self, subject, changeType, info_hash, circuit_id):
        if not self:
            return
        self.AppendToLog("Created introduction point %s for info_hash on circuit %d\n" % (info_hash, circuit_id))

    @forceWxThread
    def OnRpCreated(self, subject, changeType, info_hash, circuit_id):
        if not self:
            return
        self.AppendToLog("Created rendezvous point %s for info_hash on circuit %d\n" % (info_hash, circuit_id))

    def OnMouse(self, event):
        if event.Moving():
            self.hop_hover_evt = event.GetPosition()
            self.graph_panel.Refresh()
        elif event.LeftUp():
            self.hop_active_evt = event.GetPosition()
            self.graph_panel.Refresh()

    def OnSize(self, evt):
        size = min(*evt.GetEventObject().GetSize())
        x = min(size + self.margin_x * 2 + self.swarm.GetSize().x, self.GetSize().x - self.circuit_list.GetSize().x)
        y = size + self.margin_y * 2
        self.graph_panel.SetSize((x, y))

    def OnEraseBackground(self, event):
        pass

    def OnPaint(self, event):
        eo = event.GetEventObject()
        dc = wx.BufferedPaintDC(eo)
        dc.SetFont(self.font_large)
        dc.SetBackground(wx.WHITE_BRUSH)
        dc.Clear()
        gc = wx.GraphicsContext.Create(dc)

        swarm_size = self.swarm.GetSize()

        w = eo.GetSize().x - 2 * self.margin_x - 1 - swarm_size.x
        h = eo.GetSize().y - 2 * self.margin_y - 1

        swarm_pos = (eo.GetSize().x - swarm_size.x - 11, h / 2 - swarm_size.y / 2 + 11)
        swarm_center = (eo.GetSize().x - swarm_size.x / 2, h / 2 + self.margin_y)

        circuit_points = {}

        if self.hops != 0:
            num_circuits = len(self.circuits)
            for c_index, circuit in enumerate(sorted(self.circuits.values(), key=lambda c: c.circuit_id)):
                circuit_points[circuit] = [(self.margin_x, h / 2 + self.margin_y)]
                for h_index, hop in enumerate(circuit.hops):
                    circuit_points[circuit].append((w * (float(h_index + 1) / (circuit.goal_hops + 1)) + self.margin_x,
                                                    h * (float(c_index + 0.5) / num_circuits) + self.margin_y))
        else:
            circuit_points[None] = [(self.margin_x, h / 2 + self.margin_y)]
            gc.SetPen(wx.Pen(wx.Colour(229, 229, 229), self.line_width))

        # Draw edges
        for circuit, points in circuit_points.iteritems():
            for point1, point2 in zip(points[0::1], points[1::1]):
                if circuit == self.selected_circuit:
                    gc.SetPen(wx.Pen(wx.BLUE, self.line_width))
                else:
                    gc.SetPen(wx.Pen(wx.Colour(229, 229, 229), self.line_width))
                gc.DrawLines([point1, point2])

            # If exit node, draw edge to bittorrent swarm
            if not circuit or circuit.goal_hops == len(circuit.hops):
                gc.DrawLines([points[-1], swarm_center])

        # Draw vertices
        gc.SetPen(wx.Pen(wx.Colour(229, 229, 229), self.line_width))
        for circuit, points in circuit_points.iteritems():
            for index, point in enumerate(points):
                hop = (circuit, index)
                colour = self.hop_to_colour.get(hop, None)
                if not colour:
                    self.hop_to_colour[hop] = colour = random.choice(self.colours[1:]) if index > 0 else self.colours[0]

                x, y = point
                gc.SetBrush(wx.Brush(colour))
                gc.DrawEllipse(x - self.radius / 2, y - self.radius / 2, self.radius, self.radius)

        # Draw swarm and darknet
        gc.DrawBitmap(self.swarm, swarm_pos[0], swarm_pos[1], *swarm_size)
        self.DrawHoverAndInfo(gc, dc, circuit_points)

    def DrawHoverAndInfo(self, gc, dc, circuit_points):
        gc.SetBrush(wx.TRANSPARENT_BRUSH)

        if self.hop_hover_evt:
            self.hop_hover = self.PositionToCircuit(self.hop_hover_evt, circuit_points)
            self.hop_hover_evt = None

        if self.hop_hover and self.hop_hover[0] in circuit_points:
            circuit, hop_index = self.hop_hover
            x, y = circuit_points[circuit][hop_index]
            pen = wx.Pen(wx.Colour(229, 229, 229), 1, wx.USER_DASH)
            pen.SetDashes([8, 4])
            gc.SetPen(pen)
            gc.DrawEllipse(x - self.radius, y - self.radius, self.radius * 2, self.radius * 2)

        if self.hop_active_evt:
            self.hop_active = self.PositionToCircuit(self.hop_active_evt, circuit_points)
            self.hop_active_evt = None

        if self.hop_active and self.hop_active[0] in circuit_points and \
           (not self.hop_active[0] or self.hop_active[1] <= len(self.hop_active[0].hops)):
            circuit, hop_index = self.hop_active
            hop = circuit.hops[hop_index - 1] if hop_index and circuit else None
            x, y = circuit_points[circuit][hop_index]

            # Draw cicle around node
            pen = wx.Pen(self.hop_to_colour.get(self.hop_active, wx.BLACK), 1, wx.USER_DASH)
            pen.SetDashes([8, 4])
            gc.SetPen(pen)
            gc.DrawEllipse(x - self.radius, y - self.radius, self.radius * 2, self.radius * 2)

            # Determine text
            dc.SetFont(self.font_small)
            if not hop:
                text = 'You\nPERMID ' + bin2str(self.tunnel_community.my_member.public_key)[:10]
            else:
                text = 'PERMID ' + bin2str(self.dispersy.crypto.key_to_hash(hop.public_key))[:10]
                if 'UNKNOWN HOST' not in hop.host:
                    text = 'IP %s:%s\n' % (hop.host, hop.port) + text

            # Draw info box + text
            box_width, box_height = self.GetTextExtent(dc, text)
            box_width += 10
            box_height += 10
            x = x - box_width - 1.1 * self.radius if x > self.graph_panel.GetSize()[0] / 2 else x + 1.1 * self.radius
            y = y - box_height - 1.1 * self.radius if y > self.graph_panel.GetSize()[1] / 2 else y + 1.1 * self.radius
            gc.SetBrush(wx.Brush(wx.Colour(216, 237, 255, 50)))
            gc.SetPen(wx.Pen(LIST_BLUE))
            gc.DrawRectangle(x, y, box_width, box_height)
            self.DrawText(dc, text, x + 5, y + 5)

    def GetTextExtent(self, dc, text):
        w_list, h_list = zip(*[dc.GetTextExtent(line) for line in text.split('\n')])
        return max(w_list), sum(h_list)

    def DrawText(self, dc, text, x, y):
        # For wxPython 2.8, newline separated text does not always work with gc.DrawText
        y_cur = y
        for line in text.split('\n'):
            dc.DrawText(line, x, y_cur)
            _, h = dc.GetTextExtent(line)
            y_cur += h

    def PositionToCircuit(self, position, circuit_points):
        for circuit, points in circuit_points.iteritems():
            for index, point in enumerate(points):
                if (position[0] - point[0]) ** 2 + (position[1] - point[1]) ** 2 < self.radius ** 2:
                    return (circuit, index)
        return None

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
        self.is_xxx = {}

        self.list = ListBody(self, self, [{'width': wx.LIST_AUTOSIZE}], 0, 0, True, False,
                             grid_columns=self.max_torrents, horizontal_scroll=True)
        self.list.SetBackgroundColour(self.GetBackgroundColour())

        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.Add(
            DetailHeader(self, "Start streaming immediately by clicking on one of the items below"),
            0, wx.EXPAND)
        vSizer.Add(self.list, 1, wx.EXPAND)

        self.SetSizer(vSizer)
        self.Layout()

        self.refreshNow()

    def refreshNow(self):
        startWorker(self.SetData, self.GetTorrents)

    def GetTorrents(self):
        torrents = self.guiutility.torrentsearch_manager.getThumbnailTorrents(is_collected=True,
                                                                              limit=self.max_torrents)

        if len(torrents) == 0:
            non_torrents = self.guiutility.torrentsearch_manager.getThumbnailTorrents(
                is_collected=False, limit=self.max_torrents)
            for torrent in non_torrents:
                self.guiutility.torrentsearch_manager.downloadTorrentfileFromPeers(torrent,
                                                                                   lambda _: self.refreshNow(),
                                                                                   prio=2)

        return torrents

    @forceWxThread
    def SetData(self, delayedResult):
        if not self or not self.list:
            return
        data = []
        torrents = delayedResult.get()

        for torrent in torrents:
            data.append((torrent.infohash, [torrent.name], torrent, ThumbnailListItemNoTorrent))

        self.list.SetData(data)
        self.list.SetupScrolling()

        if len(data) < self.max_torrents:
            interval = self.update_interval / 4
        else:
            interval = self.update_interval

        startWorker(self.SetData, self.GetTorrents, delay=interval, uId=u"ArtworkPanel_refresh")

    def IsXXX(self, torrent, thumb_dir):
        infohash = torrent.infohash

        if infohash in self.is_xxx:
            return self.is_xxx[infohash]

        thumb_files = [os.path.join(dp, fn) for dp, _, fns in os.walk(thumb_dir)
                       for fn in fns if os.path.splitext(fn)[1] in THUMBNAIL_FILETYPES]

        if thumb_files:
            result = considered_xxx(thumb_files[0])

        self.is_xxx[infohash] = result
        return result
