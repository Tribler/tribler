import wx
from wx.lib.mixins.listctrl import ListCtrlAutoWidthMixin
import binascii
from collections import defaultdict

from Tribler.Main.vwxGUI import warnWxThread, LIST_GREY
from Tribler.Main.vwxGUI.widgets import _set_font, SimpleNotebook
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.Utility.GuiDBHandler import startWorker, GUI_PRI_DISPERSY

DATA_NONE = u""


class AutoWidthListCtrl(wx.ListCtrl, ListCtrlAutoWidthMixin):

    def __init__(self, parent, id, style):
        wx.ListCtrl.__init__(self, parent, id, style=style)
        ListCtrlAutoWidthMixin.__init__(self)

    def UpdateData(self, data_list):
        if not data_list:
            self.DeleteAllItems()
            return
        old_count = self.GetItemCount()
        new_count = len(data_list)

        to_modify_count = new_count if new_count < old_count else old_count
        to_append_count = new_count - to_modify_count
        to_delete_count = old_count - new_count

        row = 0
        for _ in xrange(to_modify_count):
            for col in xrange(len(data_list[row])):
                self.SetStringItem(row, col, data_list[row][col])
            row += 1
        for _ in xrange(to_append_count):
            self.Append(list(data_list[row]))
            row += 1
        for _ in xrange(to_delete_count):
            self.DeleteItem(row)


def set_small_modern_font(control):
    font = control.GetFont()
    font.SetPointSize(font.GetPointSize() - 1)
    font.SetFamily(wx.FONTFAMILY_MODERN)
    font.SetStyle(wx.FONTSTYLE_NORMAL)
    font.SetWeight(wx.FONTWEIGHT_NORMAL)
    control.SetFont(font)

def compute_ratio(i, j):
    return u"%d / %d ~%.1f%%" % (i, j, (100.0 * i / j) if j else 0.0)

def str2unicode(string):
    if isinstance(string, unicode):
        return string
    try:
        converted_str = string.decode('utf-8')
        converted_str = string
    except UnicodeDecodeError:
        converted_str = binascii.hexlify(string).encode('utf-8')
    return converted_str

# ==================================================
# Dispersy Detail Part
# ==================================================

class DispersyDetailPart(wx.Panel):

    def __init__(self, parent, id, dispersy):
        super(DispersyDetailPart, self).__init__(parent, id)
        self.SetBackgroundColour(LIST_GREY)
        self.__dispersy = dispersy

        self.__notebook = SimpleNotebook(self, show_single_tab=True, style=wx.NB_NOPAGETHEME)

        self.__summary_panel = DispersySummaryPanel(self.__notebook, -1, dispersy)
        self.__community_panel = CommunityPanel(self.__notebook, -1, dispersy)
        self.__rawinfo_panel = RawInfoPanel(self.__notebook, -1, dispersy)
        self.__runtime_panel = RuntimeProfilingPanel(self.__notebook, -1, dispersy)

        self.__notebook.AddPage(self.__summary_panel, u"Summary")
        self.__notebook.AddPage(self.__community_panel, u"Community")
        self.__notebook.AddPage(self.__rawinfo_panel, u"Raw Info")
        self.__notebook.AddPage(self.__runtime_panel, u"Runtime Profiling")

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.__incstuff_checkbox = wx.CheckBox(self, -1, u"include stuff")
        self.__incdebug_checkbox = wx.CheckBox(self, -1, u"include debug")
        self.__incdebug_checkbox.SetValue(True)

        self.__incstuff = False
        self.__incdebug = True

        startWorker(None, self.__change_debug, uId=u"DispersyPanel_ChangeDebug",
            priority=GUI_PRI_DISPERSY)

        hsizer.Add(self.__incstuff_checkbox, 0, wx.EXPAND)
        hsizer.Add(self.__incdebug_checkbox, 0, wx.EXPAND)

        self.__incstuff_checkbox.Bind(wx.EVT_CHECKBOX, self.OnIncludeStuffClicked)
        self.__incdebug_checkbox.Bind(wx.EVT_CHECKBOX, self.OnIncludeDebugClicked)

        vsizer = wx.BoxSizer(wx.VERTICAL)
        vsizer.Add(self.__notebook, 1, wx.EXPAND)
        vsizer.Add(hsizer, 0, wx.EXPAND)
        self.SetSizer(vsizer)

    def __change_debug(self):
        self.__dispersy.statistics.update(database=self.__incstuff)
        self.__dispersy.statistics.enable_debug_statistics(self.__incdebug)

    def __ChangeDebugOption(self):
        self.__incstuff = self.__incstuff_checkbox.GetValue()
        self.__incdebug = self.__incdebug_checkbox.GetValue()

        startWorker(None, self.__change_debug, uId=u"DispersyPanel_ChangeDebug",
            priority=GUI_PRI_DISPERSY)

    def SwitchTab(self, num):
        self.__notebook.SetSelection(num)

    def OnIncludeStuffClicked(self, event):
        self.__ChangeDebugOption()
        enabled = bool(self.__incstuff_checkbox.GetValue())
        self.__community_panel.ShowDatabaseInfo(enabled)
        self.Layout()

    def OnIncludeDebugClicked(self, event):
        self.__ChangeDebugOption()

    def UpdateInfo(self):
        self.__summary_panel.UpdateInfo()
        self.__community_panel.UpdateInfo()
        self.__rawinfo_panel.UpdateInfo()
        self.__runtime_panel.UpdateInfo()
        self.Layout()


# --------------------------------------------------
# Summary Panel
# --------------------------------------------------

class DispersySummaryPanel(wx.lib.scrolledpanel.ScrolledPanel):

    def __init__(self, parent, id, dispersy):
        super(DispersySummaryPanel, self).__init__(parent, id)
        self.__dispersy = dispersy
        self.__utility = GUIUtility.getInstance().utility

        self.SetBackgroundColour(wx.WHITE)

        gridsizer = wx.FlexGridSizer(0, 2, 3, 10)
        gridsizer.AddGrowableCol(1)

        self.SetSizer(gridsizer)
        self.__info_list = None
        self.__text_dict = {}

        # key, value, tip (optional)
        self.__info_list = [
            [u"WAN Address", DATA_NONE, None],
            [u"LAN Address", DATA_NONE, None],
            [u"Connection", DATA_NONE, None],
            [u"Runtime", DATA_NONE, None],
            [u"Download", DATA_NONE, None],
            [u"Upload", DATA_NONE, None],
            [u"Packets Sent", DATA_NONE,
                u"Packets sent vs Packets handled"],
            [u"Packets Received", DATA_NONE,
                u"Packets received vs Packets handled"],
            [u"Packets Dropped", DATA_NONE,
                u"Packets dropped vs Packets received"],
            [u"Packets Success", DATA_NONE,
                u"Messages successfully handled vs Packets received"],
            [u"Packets Delayed", DATA_NONE,
                u"Packets being delayed vs Packets reveived"],
            [u"Sync-Messages Created", DATA_NONE,
                u"Total number of messages created by us in this session which should be synced"],
            [u"Packets Delayed send", DATA_NONE,
                u"Total number of delaymessages or delaypacket messages being sent"],
            [u"Packets Delayed success", DATA_NONE,
                u"Total number of packets which were delayed, and did not timeout"],
            [u"Packets Delayed timeout", DATA_NONE,
                u"Total number of packets which were delayed, but got a timeout"],
            [u"Walker Success", DATA_NONE, None],
            [u"Walker Success (from trackers)", DATA_NONE,
                u"Comparing the successes to tracker to overall successes"],
            [u"Bloom New", DATA_NONE,
                u"Total number of bloomfilters created vs IntroductionRequest sent in this session"],
            [u"Bloom Reused", DATA_NONE,
                u"Total number of bloomfilters reused vs IntroductionRequest sent in this session"],
            [u"Bloom Skipped", DATA_NONE,
                u"Total number of bloomfilters skipped vs IntroductionRequest sent in this session"],
            [u"Debug Mode", DATA_NONE, None],
        ]

        for key, value, tooltip in self.__info_list:
            header = wx.StaticText(self, -1, key)
            _set_font(header, fontweight=wx.FONTWEIGHT_BOLD)
            gridsizer.Add(header)
            self.__text_dict[key] = wx.StaticText(self, -1, value)
            gridsizer.Add(self.__text_dict[key])

            if tooltip:
                header.SetToolTipString(tooltip)
                self.__text_dict[key].SetToolTipString(tooltip)

        self.SetupScrolling()

    def UpdateInfo(self, to_cleanup=False):
        if to_cleanup:
            for info in self.__info_list:
                info[1] = DATA_NONE
        else:
            stats = self.__dispersy.statistics
            self.__info_list[0][1] = u"%s:%d" % stats.wan_address
            self.__info_list[1][1] = u"%s:%d" % stats.lan_address
            self.__info_list[2][1] = unicode(stats.connection_type)

            self.__info_list[3][1] = u"%s" % self.__utility.eta_value(stats.timestamp - stats.start)
            self.__info_list[4][1] = u"%s or %s/s" % (
                self.__utility.size_format(stats.total_down),
                self.__utility.size_format(int(stats.total_down / (stats.timestamp - stats.start)))
            )
            self.__info_list[5][1] = u"%s or %s/s" % (
                self.__utility.size_format(stats.total_up),
                self.__utility.size_format(int(stats.total_up / (stats.timestamp - stats.start)))
            )
            self.__info_list[6][1] = compute_ratio(stats.total_send,
                stats.received_count + stats.total_send)
            self.__info_list[7][1] = compute_ratio(stats.received_count,
                stats.received_count + stats.total_send)
            self.__info_list[8][1] = compute_ratio(stats.drop_count, stats.received_count)
            self.__info_list[9][1] = compute_ratio(stats.success_count, stats.received_count)
            self.__info_list[10][1] = compute_ratio(stats.delay_count, stats.received_count)
            self.__info_list[11][1] = u"%s" % stats.created_count
            self.__info_list[12][1] = compute_ratio(stats.delay_send, stats.delay_count)
            self.__info_list[13][1] = compute_ratio(stats.delay_success, stats.delay_count)
            self.__info_list[14][1] = compute_ratio(stats.delay_timeout, stats.delay_count)
            self.__info_list[15][1] = compute_ratio(stats.walk_success, stats.walk_attempt)
            self.__info_list[16][1] = compute_ratio(stats.walk_bootstrap_success,
                stats.walk_bootstrap_attempt)
            self.__info_list[17][1] = compute_ratio(sum(c.sync_bloom_new for c in stats.communities),
                sum(c.sync_bloom_send + c.sync_bloom_skip for c in stats.communities))
            self.__info_list[18][1] = compute_ratio(sum(c.sync_bloom_reuse for c in stats.communities),
                sum(c.sync_bloom_send + c.sync_bloom_skip for c in stats.communities))
            self.__info_list[19][1] = compute_ratio(sum(c.sync_bloom_skip for c in stats.communities),
                sum(c.sync_bloom_send + c.sync_bloom_skip for c in stats.communities))
            self.__info_list[20][1] = u"yes" if __debug__ else u"no"

        for key, value, _ in self.__info_list:
            self.__text_dict[key].SetLabel(value)

        self.SetupScrolling()

# --------------------------------------------------
# Community Panel and Widgets
# --------------------------------------------------

class CommunityPanel(wx.Panel):

    def __init__(self, parent, id, dispersy):
        super(CommunityPanel, self).__init__(parent, id)
        self.__dispersy = dispersy

        splitter = wx.SplitterWindow(self, -1, style=wx.SP_BORDER)
        splitter.SetSashGravity(0.5)

        self.__listctrl = AutoWidthListCtrl(splitter, -1,
            style=wx.LC_REPORT | wx.LC_ALIGN_LEFT | wx.LC_SINGLE_SEL)
        self.__listctrl.SetMinSize((600, 200))
        self.__listctrl.InsertColumn(0, u"Classification")
        self.__listctrl.InsertColumn(1, u"Identifier")
        self.__listctrl.InsertColumn(2, u"Database ID")
        self.__listctrl.InsertColumn(3, u"Member")
        self.__listctrl.InsertColumn(4, u"Candidates")

        self.__listctrl.SetColumnWidth(0, 200)
        for i in xrange(1, 4):
            self.__listctrl.SetColumnWidth(i, 100)
        self.__detail_panel = CommunityDetailPanel(splitter, -1)

        splitter.SplitHorizontally(self.__listctrl, self.__detail_panel)

        sizer = wx.BoxSizer()
        sizer.Add(splitter, 1, wx.EXPAND)
        self.SetSizer(sizer)

        self.__community_data_list = []
        self.__selected_community_identifier = None

        self.__listctrl.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnListCtrlSelected)

    def ShowDatabaseInfo(self, enable):
        self.__detail_panel.ShowDatabaseInfo(enable)

    def OnListCtrlSelected(self, event):
        community_data = self.__community_data_list[event.GetIndex()]
        if self.__selected_community_identifier == community_data[u"identifier"]:
            return

        self.__selected_community_identifier = community_data[u"identifier"]
        self.__detail_panel.UpdateInfo(community_data)

    def UpdateInfo(self):
        community_list = sorted(self.__dispersy.statistics.communities,
            key=lambda community:
                (not community.dispersy_enable_candidate_walker,
                community.classification, community.cid)
        )
        self.__community_data_list = []
        reselect_community_idx = None
        idx = 0
        community_list_for_update = []
        for community in community_list:
            candidate_list = None
            if community.dispersy_enable_candidate_walker or \
                    community.dispersy_enable_candidate_walker_responses:
                candidate_count = u"%d " % len(community.candidates)
                candidate_list = [(u"%s" % global_time, u"%s:%s" % lan, u"%s:%s" % wan)
                    for lan, wan, global_time in community.candidates]
                candidate_list.sort()
            elif community.candidates:
                candidate_count = u"%d*" % len(community.candidates)
            else:
                candidate_count = u"-"

            median_global_time = u"%d (%d difference)" % \
                (community.acceptable_global_time - community.dispersy_acceptable_global_time_range,
                 community.acceptable_global_time - community.global_time -
                    community.dispersy_acceptable_global_time_range)

            database_str = DATA_NONE
            database_list = []
            if community.database:
                database_str = u"%d packets" % \
                    sum(count for count in community.database.itervalues())
                for name, count in sorted(community.database.iteritems(), key=lambda tup: tup[1]):
                    database_list.append((u"%s" % count, u"%s" % name))

            community_data = {
                u"identifier": u"%s" % community.hex_cid,
                u"member": u"%s" % community.hex_mid,
                u"classification": u"%s" % community.classification,
                u"database id": u"%s" % community.database_id,
                u"global time": u"%s" % community.global_time,
                u"median global time": u"%s" % median_global_time,
                u"acceptable range": u"%s" % community.dispersy_acceptable_global_time_range,
                u"sync bloom created": u"%s" %  community.sync_bloom_new,
                u"sync bloom reused": u"%s" %  community.sync_bloom_reuse,
                u"sync bloom skipped": u"%s" %  community.sync_bloom_skip,
                u"candidates": u"%s" % candidate_count,
                u"candidate_list": candidate_list,
                u"database": database_str,
                u"database_list": database_list,
            }
            # update community data list
            self.__community_data_list.append(community_data)

            community_list_for_update.append((community_data[u"classification"],
                community_data[u"identifier"][:7], community_data[u"database id"],
                community_data[u"member"][:7], community_data[u"candidates"])
            )

            if self.__selected_community_identifier == community_data[u"identifier"]:
                reselect_community_idx = idx
            idx += 1

        # update community detail
        self.__listctrl.UpdateData(community_list_for_update)
        community_data_for_update = None
        if reselect_community_idx is not None:
            self.__listctrl.Select(reselect_community_idx)
            community_data_for_update = self.__community_data_list[reselect_community_idx]
        self.__detail_panel.UpdateInfo(community_data_for_update)


class CommunityDetailPanel(wx.Panel):

    def __init__(self, parent, id):
        super(CommunityDetailPanel, self).__init__(parent, id, style=wx.RAISED_BORDER)
        self.SetBackgroundColour(LIST_GREY)

        self.__FIELDS = (u"identifier", u"member", u"classification", u"global time", \
            u"median global time", u"acceptable range", u"sync bloom created", \
            u"sync bloom reused", u"sync bloom skipped", u"candidates", \
            u"database")

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        info_panel = wx.Panel(self, -1)
        info_panel.SetBackgroundColour(wx.WHITE)
        info_panel.SetMinSize((450, 300))
        self.__info_panel = info_panel

        self.__text = {}
        gridsizer = wx.FlexGridSizer(0, 2, 3, 3)
        for title in self.__FIELDS:
            key_text = wx.StaticText(info_panel, -1, title)
            _set_font(key_text, fontweight=wx.FONTWEIGHT_BOLD)

            value_text = wx.StaticText(info_panel, -1)
            set_small_modern_font(value_text)
            gridsizer.AddMany([
                (key_text, 0, wx.EXPAND),
                (value_text, 0, wx.EXPAND)])

            self.__text[title] = (key_text, value_text)
            if title == u"database":
                key_text.Hide()
                value_text.Hide()
        info_panel.SetSizer(gridsizer)

        self.__candidate_list = AutoWidthListCtrl(self, -1,
            style=wx.LC_REPORT | wx.LC_ALIGN_LEFT)
        self.__candidate_list.InsertColumn(0, u"global time")
        self.__candidate_list.InsertColumn(1, u"LAN")
        self.__candidate_list.InsertColumn(2, u"WAN")

        set_small_modern_font(self.__candidate_list)

        self.__candidate_list.SetColumnWidth(0, 70)
        self.__candidate_list.SetColumnWidth(1, 130)

        self.__database_list = AutoWidthListCtrl(self, -1,
            style=wx.LC_REPORT | wx.LC_ALIGN_LEFT)
        self.__database_list.InsertColumn(0, u"Count")
        self.__database_list.InsertColumn(1, u"Info")
        set_small_modern_font(self.__database_list)

        hsizer.Add(self.__info_panel, 0, wx.EXPAND | wx.ALL, 2)
        hsizer.Add(self.__candidate_list, 1, wx.EXPAND | wx.ALL, 2)
        hsizer.Add(self.__database_list, 1, wx.EXPAND | wx.ALL, 2)
        self.SetSizer(hsizer)

        self.__to_show_database = False

        self.UpdateInfo(None)

    def ShowDatabaseInfo(self, enabled):
        self.__to_show_database = enabled
        self.__text[u"database"][0].Show(self.__to_show_database)
        self.__text[u"database"][1].Show(self.__to_show_database)
        self.__database_list.Show(self.__to_show_database)

    def UpdateInfo(self, community_data):
        if community_data == None:
            for field_name in self.__FIELDS:
                self.__text[field_name][1].SetLabel(DATA_NONE)
            self.__database_list.DeleteAllItems()
            self.__candidate_list.DeleteAllItems()
        else:
            for field_name in self.__FIELDS:
                self.__text[field_name][1].SetLabel(community_data[field_name])
            self.__database_list.UpdateData(community_data[u"database_list"])
            self.__candidate_list.UpdateData(community_data[u"candidate_list"])

# --------------------------------------------------
# RawInfo Panel
# --------------------------------------------------

class RawInfoPanel(wx.Panel):

    def __init__(self, parent, id, dispersy):
        super(RawInfoPanel, self).__init__(parent, id)
        self.__dispersy = dispersy

        self.__info = None
        self.__selected_category = None

        self.__CATEGORIES = (u"drop", u"delay", u"success", u"outgoing",
            u"created", u"walk_fail", u"attachment", u"database",
            u"endpoint_recv", u"endpoint_send", u"bootstrap_candidates")
        self.__IP_CATEGORIES = (u"bootstrap_candidates", u"walk_fail")

        self.__category_list = AutoWidthListCtrl(self, -1,
            style=wx.LC_REPORT | wx.LC_ALIGN_LEFT | wx.LC_SINGLE_SEL)
        self.__category_list.InsertColumn(0, u"Category")
        self.__category_list.InsertColumn(1, u"Total Count")
        self.__category_list.SetColumnWidth(0, 150)
        self.__category_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnCategorySelected)

        self.__detail_list = AutoWidthListCtrl(self, -1, style=wx.LC_REPORT)
        set_small_modern_font(self.__detail_list)
        self.__detail_list.InsertColumn(0, u"Count")
        self.__detail_list.InsertColumn(1, u"Info")
        self.__detail_list.SetColumnWidth(0, 50)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        hsizer.Add(self.__category_list, 1, wx.EXPAND | wx.ALL, 5)
        hsizer.Add(self.__detail_list, 2, wx.EXPAND | wx.ALL, 5)
        self.SetSizer(hsizer)

    def OnCategorySelected(self, event):
        category = self.__info[event.GetIndex()][0]
        if self.__selected_category == category:
            return

        self.__selected_category = category
        self.__detail_list.UpdateData(self.__info[event.GetIndex()][1])

    def UpdateInfo(self):
        stats = self.__dispersy.statistics
        raw_info = {}
        self.__info = []
        category_list = []
        for category in self.__CATEGORIES:
            if getattr(stats, category):
                raw_info[category] = getattr(stats, category).items()
                category_list.append(category)
                self.__info.append((category, []))

        idx = 0
        reselect_category_idx = None
        for category in category_list:
            data_list = raw_info[category]
            data_list.sort(key=lambda kv: kv[1], reverse=True)
            total_count = 0
            for key, value in data_list:
                count_str = u"%sx" % value
                total_count += value

                if category in self.__IP_CATEGORIES:
                    if isinstance(key, tuple):
                        info_str = u"%s:%s" % key
                    else:
                        info_str = str2unicode(key)
                elif category == u"attachment":
                    info_str = u"%s" % binascii.hexlify(key)
                else:
                    info_str = str2unicode(key)
                self.__info[idx][1].append((count_str, info_str))

            # update category list
            total_count = u"%s" % total_count
            if idx < self.__category_list.GetItemCount():
                self.__category_list.SetStringItem(idx, 0, category_list[idx])
                self.__category_list.SetStringItem(idx, 1, total_count)
            else:
                self.__category_list.Append([category_list[idx], total_count])

            # check selected category
            if self.__selected_category == category:
                reselect_category_idx = idx
            idx += 1

        # reselect the previous selection
        category_data_for_update = None
        if reselect_category_idx is not None:
            self.__category_list.Select(reselect_category_idx)
            category_data_for_update = self.__info[reselect_category_idx][1]
        self.__detail_list.UpdateData(category_data_for_update)

# --------------------------------------------------
# Runtime Profiling Panel
# --------------------------------------------------

class RuntimeProfilingPanel(wx.Panel):

    def __init__(self, parent, id, dispersy):
        super(RuntimeProfilingPanel, self).__init__(parent, id)
        self.__dispersy = dispersy

        sizer = wx.BoxSizer()

        self.__treectrl = wx.TreeCtrl(self, -1, style=wx.NO_BORDER |
            wx.TR_DEFAULT_STYLE | wx.TR_HIDE_ROOT | wx.TR_NO_LINES |
            wx.TR_HAS_VARIABLE_ROW_HEIGHT)
        set_small_modern_font(self.__treectrl)

        sizer.Add(self.__treectrl, 1, wx.EXPAND)
        self.SetSizer(sizer)

    def UpdateInfo(self):
        self.__treectrl.DeleteAllItems()
        parent_node = self.__treectrl.AddRoot(u"runtime stats")
        runtime = {}
        combined_runtime = defaultdict(list)
        stats = self.__dispersy.statistics
        if getattr(stats, u"runtime", None):
            for stat_dict in stats.runtime:
                stat_list = []
                for k, v in stat_dict.iteritems():
                    if isinstance(v, basestring):
                        v = v.replace(u"\n", u"\n          ")
                    stat_list.append(u"%-10s%s" % (k, v))

                name = stat_dict[u"entry"].split(u"\n")[0]
                combined_name = name.split()[0]

                label = u"duration = %7.2f ; entry = %s" % (stat_dict[u"duration"], name)
                combined_runtime[combined_name].append((stat_dict[u"duration"], label, tuple(stat_list)))

            for key, runtimes in combined_runtime.iteritems():
                if len(runtimes) > 1:
                    total_duration = 0

                    subcalls = defaultdict(list)
                    for duration, label, stat_list in runtimes:
                        total_duration += duration
                        subcalls[label].append(stat_list)

                    _subcalls = {}
                    for label, subcall_list in subcalls.iteritems():
                        if len(subcall_list) > 1:
                            _subcalls[label] = subcall_list
                        else:
                            _subcalls[label] = subcall_list[0]

                    runtime[u"duration = %7.2f ; entry = %s" % (total_duration, key)] = _subcalls

                else:
                    duration, label, stat_list = runtimes[0]
                    runtime[label] = stat_list

        self.__AddDataToTree(runtime, parent_node, self.__treectrl, prepend=False, sort_dict=True)

    def __AddDataToTree(self, data, parent, tree, prepend=True, sort_dict=False):
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


class DispersyDebugFrame(wx.Frame):

    def __init__(self, parent, id, dispersy):
        super(DispersyDebugFrame, self).__init__(parent, id,
            "Dispersy Debug Frame", size=(1280, 720), name="DispersyDebugFrame")
        self.__dispersy = dispersy

        self.__dispersy_detail_part = DispersyDetailPart(self, -1, dispersy)
        sizer = wx.BoxSizer()
        sizer.Add(self.__dispersy_detail_part, 1, wx.EXPAND)
        self.SetSizer(sizer)

        self.__dispersy_update_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnDispersyUpdateTimer, self.__dispersy_update_timer)
        self.__dispersy_update_timer.Start(5000, False)

    @warnWxThread
    def SwitchTab(self, num):
        self.__dispersy_detail_part.SwitchTab(num)

    @warnWxThread
    def OnDispersyUpdateTimer(self, event):
        self.__dispersy_detail_part.UpdateInfo()
        self.__dispersy_detail_part.Update()
