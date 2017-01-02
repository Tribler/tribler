"""
This module contains credit mining panel and list in wx

Written by Ardhi Putra Pratama H
"""

import logging
from binascii import hexlify

# pylint complaining if wx imported before binascii
from twisted.internet import reactor
import wx

from wx.lib.agw import ultimatelistctrl as ULC
from wx.lib.agw.ultimatelistctrl import EVT_LIST_ITEM_CHECKED

from Tribler.Core.exceptions import NotYetImplementedException
from Tribler.Core.simpledefs import NTFY_TORRENTS
from Tribler.Main.Dialogs.BoostingDialogs import RemoveBoostingSource, AddBoostingSource
from Tribler.Main.Utility.GuiDBHandler import startWorker, GUI_PRI_DISPERSY
from Tribler.Main.Utility.GuiDBTuples import Channel
from Tribler.Main.vwxGUI import SEPARATOR_GREY, GRADIENT_LGREY, GRADIENT_DGREY, format_time, forceWxThread
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.list import CreditMiningList
from Tribler.Main.vwxGUI.widgets import FancyPanel, LinkStaticText, _set_font
from Tribler.Core.CreditMining.BoostingSource import RSSFeedSource, DirectorySource, ChannelSource, BoostingSource
from Tribler.dispersy.taskmanager import TaskManager

RETURNED_CHANNELS = 30


class CpanelCheckListCtrl(wx.ScrolledWindow, ULC.UltimateListCtrl, TaskManager):
    """
    The checklist of credit mining sources. Check to enable, uncheck to disable.
    It is grouped by type : RSS, directory, and Channels
    """
    def __init__(self, parent, wxid=wx.ID_ANY, style=0, agwStyle=0):
        ULC.UltimateListCtrl.__init__(self, parent, wxid, wx.DefaultPosition, wx.DefaultSize, style, agwStyle)
        TaskManager.__init__(self)

        self.guiutility = GUIUtility.getInstance()
        self.boosting_manager = self.guiutility.utility.session.lm.boosting_manager

        self.channel_list = {}

        self._logger = logging.getLogger(self.__class__.__name__)

        self.InsertColumn(0, 'col')
        self.SetColumnWidth(0, -3)

        # index holder for labels. 0 for RSS, 1 for directory, 2 for channel
        self.labels = [0, 1, 2]

        self.InsertStringItem(self.labels[0], "RSS")
        item = self.GetItem(self.labels[0])
        item.Enable(False)
        item.SetData("RSS")
        self.SetItem(item)

        self.InsertStringItem(self.labels[1], "Directory")
        item = self.GetItem(self.labels[1])
        item.Enable(False)
        item.SetData("Directory")
        self.SetItem(item)

        self.InsertStringItem(self.labels[2], "Channel")
        item = self.GetItem(self.labels[2])
        item.Enable(False)
        item.SetData("Channel")
        self.SetItem(item)

        self.Bind(EVT_LIST_ITEM_CHECKED, self.OnGetItemCheck)

        self.getting_channels = False
        self._mainWin.Bind(wx.EVT_SCROLLWIN, self.on_scroll)

    def on_scroll(self, evt):
        """
        scroller watcher. Might be useful for unlimited load channels
        """
        vpos = self._mainWin.GetScrollPos(wx.VERTICAL)
        list_total = self.GetItemCount()
        list_pp = self.GetCountPerPage()
        topitem_idx, _ = self._mainWin.GetVisibleLinesRange()

        total_page = list_total / list_pp

        # print "vpos %d totlist %d topidx %d pp %d" "btmidx %s"
        #  %(vpos, total_page*list_pp, topitem_idx, list_pp, bottomitem_idx)
        if (vpos >= list_total and total_page * list_pp < vpos and
                vpos > topitem_idx + list_pp) or vpos == 0:
            # not so accurate but this will do

            if self.getting_channels:
                evt.Skip()
                return

            self.load_more()

        evt.Skip()

    @forceWxThread
    def load_more(self):
        """
        load more channels to the list
        """
        self._logger.info("getting new channels..")
        self.getting_channels = True

        def do_query_channels():
            """
            querying channels in the background. Only return as much as RETURNED_CHANNELS
            """
            _, channels = self.guiutility.channelsearch_manager.getPopularChannels(20)
            dict_channels = {channel.dispersy_cid: channel for channel in channels}
            new_channels_ids = list(set(dict_channels.keys()) - set(self.channel_list.keys()))

            return_list = [dict_channels.get(new_channels_ids[i])
                           for i in xrange(0, min(len(new_channels_ids), RETURNED_CHANNELS))]

            if return_list:
                return [l for l in sorted(return_list, key=lambda x: x.nr_favorites,
                                          reverse=True)]

        def do_update_gui(delayed_result):
            """
            add fetched channels to GUI
            """
            channels = delayed_result.get()

            if channels:
                for channel in channels:
                    # s is channel object
                    self.channel_list[channel.dispersy_cid] = channel
                    self.create_source_item(channel)

            self.getting_channels = False
            self.refresh_sourcelist_data()
            self.Layout()

        startWorker(do_update_gui, do_query_channels, retryOnBusy=True, priority=GUI_PRI_DISPERSY)

    def create_source_item(self, source):
        """
        put the source object in the sourcelist available for enable/disable
        """
        item_count = self.GetItemCount()

        if isinstance(source, RSSFeedSource):

            # update label for directory as we pushed it down
            self.InsertStringItem(self.labels[1], source.get_source_text(), 1)
            item = self.GetItem(self.labels[1])
            item.Check(source.enabled)
            item.SetData(source)
            self.SetItem(item)
            self.labels[1] += 1
            self.labels[2] += 1
        elif isinstance(source, DirectorySource):
            self.InsertStringItem(self.labels[2], source.get_source_text(), 1)
            item = self.GetItem(self.labels[2])
            item.Check(source.enabled)
            item.SetData(source)
            self.SetItem(item)
            self.labels[2] += 1
        elif isinstance(source, ChannelSource):
            self.InsertStringItem(self.labels[2] + 1, source.get_source_text() or "Loading..", 1)
            item = self.GetItem(self.labels[2] + 1)
            item.Check(source.enabled)
            item.SetData(source)
            self.SetItem(item)

            self.channel_list[source.source] = source
        elif isinstance(source, Channel):
            # channel can't be 'added'. Initialization only
            self.InsertStringItem(item_count, source.name, 1)
            self.SetItemData(item_count, source)
        else:
            raise NotYetImplementedException('Source type unknown')

    def OnGetItemCheck(self, evt):
        item = evt.GetItem()
        data = item.GetData()
        flag = item.IsChecked()

        # if it was channel that not stored in cm variables
        if not isinstance(data, BoostingSource) and flag:
            source = data.dispersy_cid
            self.boosting_manager.add_source(source)
            self.boosting_manager.set_archive(source, False)

        self.boosting_manager.set_enable_mining(
            data.dispersy_cid if not isinstance(data, BoostingSource)
            else data.source, flag, True)

        if isinstance(data, Channel):
            # channel -> channel source
            channel_src = self.boosting_manager.boosting_sources.get(data.dispersy_cid)
            channel_src.channel = data
            item.SetData(channel_src)
            self.SetItem(item)

    @forceWxThread
    def refresh_sourcelist_data(self, rerun=True):
        """
        delete all the source in the list and adding a new one
        """

        # don't refresh if we are quitting
        if GUIUtility.getInstance().utility.abcquitting:
            return

        for i in xrange(0, self.GetItemCount()):
            item = self.GetItem(i)
            data = item.GetData()

            if isinstance(data, ChannelSource):
                if item.GetText() == "Loading..":
                    item.SetText(data.get_source_text() or "Loading..")
                    self.SetItem(item)

        if rerun and not self.is_pending_task_active(str(self) + "_refresh_data_ULC"):
            self.register_task(str(self) + "_refresh_data_ULC", reactor.callLater(30, self.refresh_sourcelist_data))

    def fix_channel_position(self, source):
        """
        This function called when new checked channel want to pushed above
        """
        chn_source = self.boosting_manager.boosting_sources[source]

        chn = self.channel_list[source]

        idx = self.FindItemData(-1, chn)
        self.DeleteItem(idx)

        self.InsertStringItem(self.labels[2] + 1, chn_source.get_source_text() or "Loading..", 1)
        item = self.GetItem(self.labels[2] + 1)
        item.Check(chn_source.enabled)
        item.SetData(chn_source)
        self.SetItem(item)

        self.channel_list[source] = chn_source


class CreditMiningPanel(FancyPanel, TaskManager):
    """
    A class representing panel control for credit mining
    """
    def __init__(self, parent):
        self._logger = logging.getLogger(self.__class__.__name__)

        self._logger.debug("CreditMiningPanel: __init__")

        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility
        self.installdir = self.utility.getPath()

        FancyPanel.__init__(self, parent, border=wx.BOTTOM)
        TaskManager.__init__(self)

        self.SetBorderColour(SEPARATOR_GREY)
        self.SetBackgroundColour(GRADIENT_LGREY, GRADIENT_DGREY)

        if not self.utility.session.get_creditmining_enable():
            wx.StaticText(self, -1, 'Credit mining inactive')
            return

        self.tdb = self.utility.session.open_dbhandler(NTFY_TORRENTS)
        self.boosting_manager = self.utility.session.lm.boosting_manager

        self.main_sizer = wx.BoxSizer(wx.VERTICAL)

        self.header = self.create_header_info(self)
        if self.header:
            self.main_sizer.Add(self.header, 0, wx.EXPAND)

        self.main_splitter = wx.SplitterWindow(self, style=wx.SP_BORDER)
        self.main_splitter.SetMinimumPaneSize(300)

        self.sourcelist = CpanelCheckListCtrl(self.main_splitter, -1,
                                              agwStyle=wx.LC_REPORT | wx.LC_NO_HEADER | wx.LC_VRULES | wx.LC_HRULES
                                              | wx.LC_SINGLE_SEL | ULC.ULC_HAS_VARIABLE_ROW_HEIGHT)

        self.add_components(self.main_splitter)
        self.SetSizer(self.main_sizer)

        self.register_task(str(self) + "_post_init", reactor.callLater(2, self._post_init))

    def add_components(self, parent):
        """
        adding GUI components to the control panel
        """
        self.info_panel = FancyPanel(parent, style=wx.BORDER_SUNKEN)

        if_sizer = wx.BoxSizer(wx.VERTICAL)
        self.top_info_p = FancyPanel(self.info_panel, border=wx.ALL, style=wx.BORDER_SUNKEN, name="top_info_p")
        tinfo_sizer = wx.BoxSizer(wx.VERTICAL)

        self.tnfo_subpanel_top = FancyPanel(self.top_info_p, border=wx.ALL)
        tinfo_spanel_sizer = wx.BoxSizer(wx.HORIZONTAL)

        stat_sizer = wx.BoxSizer(wx.VERTICAL)

        self.source_label = wx.StaticText(self.tnfo_subpanel_top, -1, 'Source : -')
        stat_sizer.Add(self.source_label, 1)
        self.source_name = wx.StaticText(self.tnfo_subpanel_top, -1, 'Name : -')
        stat_sizer.Add(self.source_name, 1)
        self.torrent_num = wx.StaticText(self.tnfo_subpanel_top, -1, '# Torrents : -')
        stat_sizer.Add(self.torrent_num, 1)

        # channels only
        self.last_updt = wx.StaticText(self.tnfo_subpanel_top, -1, 'Latest update : -')
        stat_sizer.Add(self.last_updt, 1)
        self.votes_num = wx.StaticText(self.tnfo_subpanel_top, -1, 'Favorite votes : -')
        stat_sizer.Add(self.votes_num, 1)

        # rss only
        self.rss_title = wx.StaticText(self.tnfo_subpanel_top, -1, 'Title : -')
        stat_sizer.Add(self.rss_title, 1)
        self.rss_desc = wx.StaticText(self.tnfo_subpanel_top, -1, 'Description : -')
        stat_sizer.Add(self.rss_desc, 1)

        self.debug_info = wx.StaticText(self.tnfo_subpanel_top, -1, 'Debug Info : -')
        stat_sizer.Add(self.debug_info)

        tinfo_spanel_sizer.Add(stat_sizer, -1)
        tinfo_spanel_sizer.Add(wx.StaticText(self.tnfo_subpanel_top, -1, 'Credit Mining Status: '))
        self.status_cm = wx.StaticText(self.tnfo_subpanel_top, -1, '-')
        tinfo_spanel_sizer.Add(self.status_cm)
        self.tnfo_subpanel_top.SetSizer(tinfo_spanel_sizer)

        tinfo_sizer.Add(self.tnfo_subpanel_top, 1, wx.EXPAND)
        tinfo_sizer.Add(wx.StaticLine(self.top_info_p), 0, wx.ALL | wx.EXPAND, 5)

        self.up_rate = wx.StaticText(self.top_info_p, -1, 'Upload rate : -', name="up_rate")
        tinfo_sizer.Add(self.up_rate)
        self.dwn_rate = wx.StaticText(self.top_info_p, -1, 'Download rate : -', name="dwn_rate")
        tinfo_sizer.Add(self.dwn_rate)
        self.storage_used = wx.StaticText(self.top_info_p, -1, 'Storage Used : -', name="storage_used")
        tinfo_sizer.Add(self.storage_used)

        self.top_info_p.SetSizer(tinfo_sizer)

        if_sizer.Add(self.top_info_p, 1, wx.EXPAND)

        self.cmlist = CreditMiningList(self.info_panel)
        self.cmlist.do_or_schedule_refresh(True)
        self.cmlist.library_manager.add_download_state_callback(self.cmlist.RefreshItems)

        if_sizer.Add(self.cmlist, 1, wx.EXPAND)
        self.info_panel.SetSizer(if_sizer)

        self.sourcelist.Hide()
        self.loading_holder = wx.StaticText(self.main_splitter, -1, 'Loading..')

        parent.SplitVertically(self.loading_holder, self.info_panel, 1)
        parent.SetSashGravity(0.3)
        self.main_sizer.Add(parent, 1, wx.EXPAND)

    def on_sourceitem_selected(self, event):
        """
        This function is called when a user select 'source' in the list.
        The credit mining list will only show this particular source
        """
        idx = event.m_itemIndex
        data = self.sourcelist.GetItem(idx).GetData()

        if isinstance(data, ChannelSource):
            self.cmlist.GotFilter(data.source)
        else:
            self.cmlist.GotFilter(data.get_source_text() if isinstance(data, BoostingSource) else '')

        self.show_source_info(data)

    def show_source_info(self, data):
        """
        shows information about selected source (not necessarily activated/enabled) in the panel
        """

        if isinstance(data, ChannelSource):
            self.last_updt.Show()
            self.votes_num.Show()
            self.rss_title.Hide()
            self.rss_desc.Hide()

            self.source_label.SetLabel("Source : Channel (stored)")
            self.source_name.SetLabel("Name : " + data.get_source_text())
            self.torrent_num.SetLabel("# Torrents : " + str(data.channel.nr_torrents))
            self.last_updt.SetLabel("Latest update : " + format_time(data.channel.modified))
            self.votes_num.SetLabel('Favorite votes : ' + str(data.channel.nr_favorites))
            self.status_cm.SetLabel("Active" if data.enabled else "Inactive")

            debug_str = hexlify(data.source)
            self.debug_info.SetLabel("Debug Info : \n" + debug_str)

        elif isinstance(data, Channel):
            self.last_updt.Show()
            self.votes_num.Show()
            self.rss_title.Hide()
            self.rss_desc.Hide()

            self.source_label.SetLabel("Source : Channel")
            self.source_name.SetLabel("Name : " + data.name)
            self.torrent_num.SetLabel("# Torrents : " + str(data.nr_torrents))
            self.last_updt.SetLabel("Latest update : " + format_time(data.modified))
            self.votes_num.SetLabel('Favorite votes : ' + str(data.nr_favorites))
            self.status_cm.SetLabel("Inactive")

            debug_str = hexlify(data.dispersy_cid)
            self.debug_info.SetLabel("Debug Info : \n" + debug_str)

        elif isinstance(data, RSSFeedSource):
            self.last_updt.Hide()
            self.votes_num.Hide()
            self.rss_title.Show()
            self.rss_desc.Show()

            self.source_label.SetLabel("Source : RSS Web Feed")
            self.source_name.SetLabel("Source URL : " + data.get_source_text())
            self.torrent_num.SetLabel("# Torrents : %s" % len(data.torrents))
            self.rss_title.SetLabel("Title : " + data.title)
            self.rss_desc.SetLabel("Description : " + data.description)
            self.status_cm.SetLabel("Active" if data.enabled else "Inactive")

            debug_str = "-"
            self.debug_info.SetLabel("Debug Info : \n" + debug_str)

        elif isinstance(data, DirectorySource):
            self.last_updt.Hide()
            self.votes_num.Hide()
            self.rss_title.Hide()
            self.rss_desc.Hide()

            self.source_label.SetLabel("Source : Directory")
            self.source_name.SetLabel("Name : " + data.get_source_text())
            self.torrent_num.SetLabel("# Torrents : %d" % len(data.torrents))
            self.status_cm.SetLabel("Active" if data.enabled else "Inactive")

            debug_str = "-"
            self.debug_info.SetLabel("Debug Info : \n" + debug_str)

        else:
            self._logger.debug("Not implemented yet")

        # show/hide items
        self.tnfo_subpanel_top.Layout()

    def create_header_info(self, parent):
        """
        function to create wx header/info panel above the credit mining list
        """
        if self.guiutility.frame.top_bg:
            header = FancyPanel(parent, border=wx.BOTTOM, name="cm_header")
            text = wx.StaticText(header, -1, 'Investment overview')

            def on_add_source(_):
                """
                callback when a user wants to add new source
                """
                dlg = AddBoostingSource(None)
                if dlg.ShowModal() == wx.ID_OK:
                    source, archive = dlg.get_value()
                    if source:
                        self.boosting_manager.add_source(source)
                        self.boosting_manager.set_archive(source, archive)

                        self.sourcelist.create_source_item(self.boosting_manager.boosting_sources[source])

                dlg.Destroy()

            def on_remove_source(_):
                """
                callback when a user wants to remove source
                """
                dlg = RemoveBoostingSource(None)
                if dlg.ShowModal() == wx.ID_OK and dlg.get_value():
                    self.boosting_manager.remove_source(dlg.get_value())
                    self.sourcelist.refresh_sourcelist_data()
                dlg.Destroy()

            addsource = LinkStaticText(header, 'Add', icon=None)
            addsource.Bind(wx.EVT_LEFT_UP, on_add_source)
            removesource = LinkStaticText(header, 'Remove', icon=None)
            removesource.Bind(wx.EVT_LEFT_UP, on_remove_source)

            self.b_up = wx.StaticText(header, -1, 'Total bytes up: -', name="b_up")
            self.b_down = wx.StaticText(header, -1, 'Total bytes down: -', name="b_down")
            self.s_up = wx.StaticText(header, -1, 'Total speed up: -', name="s_up")
            self.s_down = wx.StaticText(header, -1, 'Total speed down: -', name="s_down")
            self.iv_sum = wx.StaticText(header, -1, 'Investment summary: -', name="iv_sum")
            _set_font(text, size_increment=2, fontweight=wx.FONTWEIGHT_BOLD)
            sizer = wx.BoxSizer(wx.VERTICAL)
            sizer.AddStretchSpacer()
            titlesizer = wx.BoxSizer(wx.HORIZONTAL)
            titlesizer.Add(text, 0, wx.ALIGN_BOTTOM | wx.RIGHT, 5)
            titlesizer.Add(wx.StaticText(header, -1, '('), 0, wx.ALIGN_BOTTOM)
            titlesizer.Add(addsource, 0, wx.ALIGN_BOTTOM)
            titlesizer.Add(wx.StaticText(header, -1, '/'), 0, wx.ALIGN_BOTTOM)
            titlesizer.Add(removesource, 0, wx.ALIGN_BOTTOM)
            titlesizer.Add(wx.StaticText(header, -1, ' boosting source)'), 0, wx.ALIGN_BOTTOM)
            sizer.Add(titlesizer, 0, wx.LEFT | wx.BOTTOM, 5)
            sizer.Add(self.b_up, 0, wx.LEFT, 5)
            sizer.Add(self.b_down, 0, wx.LEFT, 5)
            sizer.Add(self.s_up, 0, wx.LEFT, 5)
            sizer.Add(self.s_down, 0, wx.LEFT, 5)
            sizer.Add(self.iv_sum, 0, wx.LEFT, 5)
            sizer.AddStretchSpacer()
            header.SetSizer(sizer)
            header.SetMinSize((-1, 100))
        else:
            raise NotYetImplementedException('')

        return header

    @forceWxThread
    def _post_init(self):
        if GUIUtility.getInstance().utility.abcquitting:
            return

        some_ready = any([i.ready for i in self.boosting_manager.boosting_sources.values()])

        # if none are ready, keep waiting or If no source available
        if not some_ready and len(self.boosting_manager.boosting_sources.values()):
            self.register_task(str(self) + "_post_init", reactor.callLater(2, self._post_init))
            return

        for _, source_obj in self.boosting_manager.boosting_sources.items():
            self.sourcelist.create_source_item(source_obj)

        self.sourcelist.Show()
        self.main_splitter.ReplaceWindow(self.loading_holder, self.sourcelist)
        self.loading_holder.Close()

        self.Bind(ULC.EVT_LIST_ITEM_SELECTED, self.on_sourceitem_selected, self.sourcelist)

        self.register_task(str(self) + "_load_more", reactor.callLater(2, self.sourcelist.load_more))
        self.Layout()
