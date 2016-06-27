# Written by Ardhi Putra Pratama Hartono


import os
import sys
import logging
import wx
from binascii import hexlify, unhexlify
from wx.lib.agw.ultimatelistctrl import ULC_VIRTUAL, EVT_LIST_ITEM_CHECKED

from Tribler import LIBRARYNAME
from Tribler.Core.exceptions import NotYetImplementedException
from Tribler.Core.simpledefs import NTFY_TORRENTS
from Tribler.Main.Dialogs.BoostingDialogs import RemoveBoostingSource, AddBoostingSource

from Tribler.Main.Utility.GuiDBTuples import CollectedTorrent, Torrent, Channel
from Tribler.Main.Utility.GuiDBHandler import startWorker, cancelWorker, GUI_PRI_DISPERSY
from Tribler.Main.vwxGUI import forceWxThread, TRIBLER_RED, SEPARATOR_GREY, GRADIENT_LGREY, GRADIENT_DGREY, format_time
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.GuiImageManager import GuiImageManager
from Tribler.Main.vwxGUI.list import CreditMiningList
from Tribler.Main.vwxGUI.widgets import ActionButton, FancyPanel, TextCtrlAutoComplete, ProgressButton, LinkStaticText, \
    _set_font
from Tribler.Main.Dialogs.AddTorrent import AddTorrent
from Tribler.Main.Dialogs.RemoveTorrent import RemoveTorrent
from Tribler.Policies.BoostingManager import BoostingManager, RSSFeedSource, DirectorySource, ChannelSource, \
    BoostingSource

try:
    from agw import ultimatelistctrl as ULC
except ImportError:
    from wx.lib.agw import ultimatelistctrl as ULC



class CpanelCheckListCtrl(wx.ScrolledWindow, ULC.UltimateListCtrl):
    def __init__(self, parent, id=wx.ID_ANY, pos=wx.DefaultPosition, size=wx.DefaultSize, style=0, \
                 agwStyle=0):
        ULC.UltimateListCtrl.__init__(self, parent, id, pos, size, style, agwStyle)
        self.boosting_manager = BoostingManager.get_instance()
        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility
        self.channel_list = {}

        self._logger = logging.getLogger(self.__class__.__name__)

        self.InsertColumn(0,'col')
        self.SetColumnWidth(0, -3)

        self.label_rss_idx = 0
        self.InsertStringItem(self.label_rss_idx,"RSS")
        it = self.GetItem(self.label_rss_idx)
        it.Enable(False)
        it.SetData("RSS")
        self.SetItem(it)

        self.label_dir_idx = 1
        self.InsertStringItem(self.label_dir_idx,"Directory")
        it = self.GetItem(self.label_dir_idx)
        it.Enable(False)
        it.SetData("Directory")
        self.SetItem(it)

        self.label_channel_idx = 2
        self.InsertStringItem(self.label_channel_idx,"Channel")
        it = self.GetItem(self.label_channel_idx)
        it.Enable(False)
        it.SetData("Channel")
        self.SetItem(it)

        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnItemActivated)
        self.Bind(EVT_LIST_ITEM_CHECKED, self.OnGetItemCheck)

        self.getting_channels = False
        self._mainWin.Bind(wx.EVT_SCROLLWIN, self.OnScroll)

    def OnItemActivated(self, evt):
        # double click
        pass

    def OnScroll(self, evt):
        vpos = self._mainWin.GetScrollPos(wx.VERTICAL)
        list_total = self.GetItemCount()
        list_pp = self.GetCountPerPage()
        topitem_idx, bottomitem_idx = self._mainWin.GetVisibleLinesRange()

        total_page = list_total/list_pp

        # print "vpos %d totlist %d topidx %d pp %d" "btmidx %s" %(vpos, total_page*list_pp, topitem_idx, list_pp, bottomitem_idx)
        if (vpos >= list_total and total_page*list_pp < vpos and vpos > topitem_idx+list_pp)\
                or vpos == 0:
            #not so accurate but this will do

            if self.getting_channels:
                evt.Skip()
                return

            self.LoadMore()

        evt.Skip()

    def LoadMore(self):
        self._logger.info("getting new channels..")
        self.getting_channels = True

        def do_query_channels():
            RETURNED_CHANNELS = 30

            _, channels = self.guiutility.channelsearch_manager.getPopularChannels(20)
            dict_channels = {channel.dispersy_cid: channel for channel in channels}
            new_channels_ids = list(set(dict_channels.keys()) - set(self.channel_list.keys()))

            return_list = [dict_channels.get(new_channels_ids[i]) for i in range(0,
                len(new_channels_ids) if len(new_channels_ids) < RETURNED_CHANNELS else RETURNED_CHANNELS)]

            if return_list:
                return [l for l in sorted(return_list, key=lambda x: x.nr_favorites, reverse=True)]# if "tribler" in l.name.lower() or "linux" in l.name.lower()]
            else:
                None

        def do_update_gui(delayedResult):
            channels = delayedResult.get()

            if channels:
                for s in channels:
                    # s is channel object
                    self.channel_list[s.dispersy_cid] = s
                    self.CreateSourceItem(s)

            self.getting_channels = False

        startWorker(do_update_gui, do_query_channels, retryOnBusy=True, priority=GUI_PRI_DISPERSY)

    def CreateSourceItem(self, source):
        item_count = self.GetItemCount()

        if isinstance(source, RSSFeedSource):

            self.InsertStringItem(self.label_dir_idx, source.getSource(), 1)
            item = self.GetItem(self.label_dir_idx)
            item.Check(source.enabled)
            item.SetData(source)
            self.SetItem(item)
            self.label_dir_idx += 1
            self.label_channel_idx += 1
        elif isinstance(source, DirectorySource):
            self.InsertStringItem(self.label_channel_idx, source.getSource(), 1)
            item = self.GetItem(self.label_channel_idx)
            item.Check(source.enabled)
            item.SetData(source)
            self.SetItem(item)
            self.label_channel_idx += 1
        elif isinstance(source, ChannelSource):
            self.InsertStringItem(self.label_channel_idx+1, source.getSource() or "Loading..", 1)
            item = self.GetItem(self.label_channel_idx+1)
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

        self.boosting_manager.set_enable_mining(
            data.dispersy_cid if not isinstance(data, BoostingSource)
                else data.source, flag, True)

        if isinstance(data, Channel):
            # channel -> channel source
            channel_src = self.boosting_manager.boosting_sources.get(data.dispersy_cid)
            channel_src.channel = data
            item.SetData(channel_src)
            self.SetItem(item)


    def RefreshData(self, rerun=True):
        for i in range(0, self.GetItemCount()):
            item = self.GetItem(i)
            data = item.GetData()

            if isinstance(data, BoostingSource):
                source = data.getSource()
                if isinstance(data, RSSFeedSource):
                    sobj = self.boosting_manager.boosting_sources[source]
                elif isinstance(data, DirectorySource):
                    sobj = self.boosting_manager.boosting_sources[source]
                elif isinstance(data, ChannelSource):
                    source = data.source
                    sobj = self.boosting_manager.boosting_sources[source]
                    if item.GetText() == "Loading..":
                        item.SetText(data.getSource() or "Loading..")
                        self.SetItem(item)

            elif isinstance(data, Channel):
                pass

        if rerun:
            self.utility.session.lm.threadpool.add_task(self.RefreshData, 30,
                                            task_name=str(self)+"_refresh_data_ULC")

    def FixChannelPos(self, source):
        chn_source = self.boosting_manager.boosting_sources[source]

        chn = self.channel_list[source]

        idx = self.FindItemData(-1, chn)
        self.DeleteItem(idx)

        self.InsertStringItem(self.label_channel_idx+1,chn_source.getSource() or "Loading..", 1)
        item = self.GetItem(self.label_channel_idx+1)
        item.Check(chn_source.enabled)
        item.SetData(chn_source)
        self.SetItem(item)

        self.channel_list[source] = chn_source


class CreditMiningPanel(FancyPanel):
    def __init__(self, parent):
        self._logger = logging.getLogger(self.__class__.__name__)

        self._logger.debug("CreditMiningPanel: __init__")

        self.guiutility = GUIUtility.getInstance()
        self.utility = self.guiutility.utility
        self.installdir = self.utility.getPath()

        self.boosting_manager = BoostingManager.get_instance()

        self.tdb = self.utility.session.open_dbhandler(NTFY_TORRENTS)

        FancyPanel.__init__(self, parent, border=wx.BOTTOM)

        self.SetBorderColour(SEPARATOR_GREY)
        self.SetBackgroundColour(GRADIENT_LGREY, GRADIENT_DGREY)

        self.main_sizer = wx.BoxSizer(wx.VERTICAL)

        self.header = self.CreateHeader(self)
        if self.header:
            self.main_sizer.Add(self.header, 0, wx.EXPAND)

        self.main_splitter = wx.SplitterWindow(self, style=wx.SP_BORDER)

        self.sourcelist = CpanelCheckListCtrl(self.main_splitter, -1,
                                agwStyle=wx.LC_REPORT | wx.LC_NO_HEADER | wx.LC_VRULES
                                        | wx.LC_HRULES | wx.LC_SINGLE_SEL | ULC.ULC_HAS_VARIABLE_ROW_HEIGHT)

        self.AddComponents(self.main_splitter)
        self.SetSizer(self.main_sizer)


        self.guiutility.utility.session.lm.threadpool.add_task(self._PostInit, 2,
                                            task_name=str(self)+"_post_init")


    def AddComponents(self,parent):
        self.infoPanel = FancyPanel(parent, style=wx.BORDER_SUNKEN)

        if_sizer = wx.BoxSizer(wx.VERTICAL)
        self.top_info_p = FancyPanel(self.infoPanel, border=wx.ALL, style=wx.BORDER_SUNKEN, name="top_info_p")
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

        tinfo_spanel_sizer.Add(stat_sizer,-1)
        tinfo_spanel_sizer.Add(wx.StaticText(self.tnfo_subpanel_top, -1, 'Credit Mining Status: '))
        self.status_cm = wx.StaticText(self.tnfo_subpanel_top, -1, '-')
        tinfo_spanel_sizer.Add(self.status_cm)
        self.tnfo_subpanel_top.SetSizer(tinfo_spanel_sizer)

        tinfo_sizer.Add(self.tnfo_subpanel_top, 1, wx.EXPAND)
        tinfo_sizer.Add(wx.StaticLine(self.top_info_p), 0, wx.ALL|wx.EXPAND, 5)

        self.up_rate = wx.StaticText(self.top_info_p, -1, 'Upload rate : -', name="up_rate")
        tinfo_sizer.Add(self.up_rate)
        self.dwn_rate = wx.StaticText(self.top_info_p, -1, 'Download rate : -', name="dwn_rate")
        tinfo_sizer.Add(self.dwn_rate)
        self.storage_used = wx.StaticText(self.top_info_p, -1, 'Storage Used : -', name="storage_used")
        tinfo_sizer.Add(self.storage_used)

        self.top_info_p.SetSizer(tinfo_sizer)

        if_sizer.Add(self.top_info_p, 1, wx.EXPAND)

        self.cmlist = CreditMiningList(self.infoPanel)
        self.cmlist.do_or_schedule_refresh(True)
        self.cmlist.library_manager.add_download_state_callback(self.cmlist.RefreshItems)

        if_sizer.Add(self.cmlist, 1, wx.EXPAND)
        self.infoPanel.SetSizer(if_sizer)

        self.sourcelist.Hide()
        self.loading_holder =  wx.StaticText(self.main_splitter, -1, 'Loading..')

        parent.SplitVertically(self.loading_holder, self.infoPanel)
        parent.SetMinimumPaneSize(100)
        parent.SetSashGravity(0.25)
        self.main_sizer.Add(parent, 1, wx.EXPAND)

    def OnItemSelected(self, event):
        idx = event.m_itemIndex
        data = self.sourcelist.GetItem(idx).GetData()

        if isinstance(data, ChannelSource):
            self.cmlist.GotFilter(data.source)
        else:
            self.cmlist.GotFilter(data.getSource() if isinstance(data, BoostingSource) else '')

        self.ShowInfo(data)

    def ShowInfo(self, data):

        if isinstance(data, ChannelSource):
            self.last_updt.Show()
            self.votes_num.Show()
            self.rss_title.Hide()
            self.rss_desc.Hide()

            self.source_label.SetLabel("Source : Channel (stored)")
            self.source_name.SetLabel("Name : "+data.getSource())
            self.torrent_num.SetLabel("# Torrents : "+str(data.channel.nr_torrents))
            self.last_updt.SetLabel("Latest update : "+format_time(data.channel.modified))
            self.votes_num.SetLabel('Favorite votes : '+str(data.channel.nr_favorites))
            self.status_cm.SetLabel("Active" if data.enabled else "Inactive")


            debug_str = hexlify(data.source)
            self.debug_info.SetLabel("Debug Info : \n"+debug_str)

        elif isinstance(data, Channel):
            self.last_updt.Show()
            self.votes_num.Show()
            self.rss_title.Hide()
            self.rss_desc.Hide()

            self.source_label.SetLabel("Source : Channel")
            self.source_name.SetLabel("Name : "+data.name)
            self.torrent_num.SetLabel("# Torrents : "+str(data.nr_torrents))
            self.last_updt.SetLabel("Latest update : "+format_time(data.modified))
            self.votes_num.SetLabel('Favorite votes : '+str(data.nr_favorites))
            self.status_cm.SetLabel("Inactive")

            debug_str = hexlify(data.dispersy_cid)
            self.debug_info.SetLabel("Debug Info : \n"+debug_str)

        elif isinstance(data, RSSFeedSource):
            self.last_updt.Hide()
            self.votes_num.Hide()
            self.rss_title.Show()
            self.rss_desc.Show()

            self.source_label.SetLabel("Source : RSS Web Feed")
            self.source_name.SetLabel("Source URL : "+data.getSource())
            self.torrent_num.SetLabel("# Torrents : "+str(data.total_torrents))
            self.rss_title.SetLabel("Title : "+data.title)
            self.rss_desc.SetLabel("Description : "+data.description)
            self.status_cm.SetLabel("Active" if data.enabled else "Inactive")

            debug_str = "-"
            self.debug_info.SetLabel("Debug Info : \n"+debug_str)

        elif isinstance(data, DirectorySource):
            self.last_updt.Hide()
            self.votes_num.Hide()
            self.rss_title.Hide()
            self.rss_desc.Hide()

            self.source_label.SetLabel("Source : Directory")
            self.source_name.SetLabel("Name : "+data.getSource())
            self.torrent_num.SetLabel("# Torrents : "+str(12345))
            self.status_cm.SetLabel("Active" if data.enabled else "Inactive")

            debug_str = "-"
            self.debug_info.SetLabel("Debug Info : \n"+debug_str)

        else:
            self._logger.debug("Not implemented yet")
            pass

        # show/hide items
        self.tnfo_subpanel_top.Layout()


    def CreateHeader(self, parent):
        if self.guiutility.frame.top_bg:
            header = FancyPanel(parent, border=wx.BOTTOM, name="cm_header")
            text = wx.StaticText(header, -1, 'Investment overview')

            def OnAddSource(event):
                dlg = AddBoostingSource(None)
                if dlg.ShowModal() == wx.ID_OK:
                    source, archive = dlg.GetValue()
                    if source:
                        self.boosting_manager.add_source(source)
                        self.boosting_manager.set_archive(source, archive)

                        self.sourcelist.CreateSourceItem(self.boosting_manager.boosting_sources[source])

                dlg.Destroy()

            def OnRemoveSource(event):
                dlg = RemoveBoostingSource(None)
                if dlg.ShowModal() == wx.ID_OK and dlg.GetValue():
                    self.boosting_manager.remove_source(dlg.GetValue())
                    self.GetManager().refresh()
                dlg.Destroy()

            addsource = LinkStaticText(header, 'Add', icon=None)
            addsource.Bind(wx.EVT_LEFT_UP, OnAddSource)
            removesource = LinkStaticText(header, 'Remove', icon=None)
            removesource.Bind(wx.EVT_LEFT_UP, OnRemoveSource)
            self.b_up = wx.StaticText(header, -1, 'Total bytes up: -',name="b_up")
            self.b_down = wx.StaticText(header, -1, 'Total bytes down: -',name="b_down")
            self.s_up = wx.StaticText(header, -1, 'Total speed up: -',name="s_up")
            self.s_down = wx.StaticText(header, -1, 'Total speed down: -',name="s_down")
            self.iv_sum = wx.StaticText(header, -1, 'Investment summary: -',name="iv_sum")
            _set_font(text, size_increment=2, fontweight=wx.FONTWEIGHT_BOLD)
            sizer = wx.BoxSizer(wx.VERTICAL)
            sizer.AddStretchSpacer()
            titleSizer = wx.BoxSizer(wx.HORIZONTAL)
            titleSizer.Add(text, 0, wx.ALIGN_BOTTOM | wx.RIGHT, 5)
            titleSizer.Add(wx.StaticText(header, -1, '('), 0, wx.ALIGN_BOTTOM)
            titleSizer.Add(addsource, 0, wx.ALIGN_BOTTOM)
            titleSizer.Add(wx.StaticText(header, -1, '/'), 0, wx.ALIGN_BOTTOM)
            titleSizer.Add(removesource, 0, wx.ALIGN_BOTTOM)
            titleSizer.Add(wx.StaticText(header, -1, ' boosting source)'), 0, wx.ALIGN_BOTTOM)
            sizer.Add(titleSizer, 0, wx.LEFT | wx.BOTTOM, 5)
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

    def _PostInit(self):

        for i in self.boosting_manager.boosting_sources:
            if not self.boosting_manager.boosting_sources[i].ready:
                self.guiutility.utility.session.lm.threadpool.add_task(self._PostInit, 2, task_name=str(self)+"_post_init")
                return

        for source, source_obj in self.boosting_manager.boosting_sources.items():
            self.sourcelist.CreateSourceItem(source_obj)

        self.sourcelist.Show()
        self.main_splitter.ReplaceWindow(self.loading_holder, self.sourcelist)
        self.loading_holder.Close()

        self.Bind(ULC.EVT_LIST_ITEM_SELECTED, self.OnItemSelected, self.sourcelist)

        self.sourcelist.LoadMore()
        self.sourcelist.RefreshData()
