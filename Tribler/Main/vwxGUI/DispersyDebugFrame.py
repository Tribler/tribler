import wx
from wx.lib.mixins.listctrl import ListCtrlAutoWidthMixin
import binascii
from collections import defaultdict

from Tribler.Main.vwxGUI import LIST_GREY
from Tribler.Main.vwxGUI.widgets import _set_font, SimpleNotebook
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.Utility.GuiDBHandler import startWorker, GUI_PRI_DISPERSY

DATA_NONE = ""


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
    return "%d / %d ~%.1f%%" % (i, j, (100.0 * i / j) if j else 0.0)

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
# Frame
# ==================================================

class DispersyDebugFrame(wx.Frame):

    def __init__(self, parent, id, dispersy):
        super(DispersyDebugFrame, self).__init__(parent, id,
            "Dispersy Debug Frame", size=(1280, 720), name="DispersyDebugFrame")
        self.__dispersy = dispersy
        self.SetBackgroundColour(LIST_GREY)

        self.__notebook = SimpleNotebook(self, show_single_tab=True, style=wx.NB_NOPAGETHEME)

        self.__summary_panel = DispersySummaryPanel(self.__notebook, -1)
        self.__community_panel = CommunityPanel(self.__notebook, -1)
        self.__rawinfo_panel = RawInfoPanel(self.__notebook, -1)
        self.__runtime_panel = RuntimeProfilingPanel(self.__notebook, -1)

        self.__notebook.AddPage(self.__summary_panel, "Summary")
        self.__notebook.AddPage(self.__community_panel, "Community")
        self.__notebook.AddPage(self.__rawinfo_panel, "Raw Info")
        self.__notebook.AddPage(self.__runtime_panel, "Runtime Profiling")

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.__incstuff_checkbox = wx.CheckBox(self, -1, "include stuff")
        self.__incdebug_checkbox = wx.CheckBox(self, -1, "include debug")
        self.__incdebug_checkbox.SetValue(self.__dispersy.statistics.are_debug_statistics_enabled())

        self.__incstuff = False
        self.__incdebug = True

        hsizer.Add(self.__incstuff_checkbox, 0, wx.EXPAND)
        hsizer.Add(self.__incdebug_checkbox, 0, wx.EXPAND)

        self.__incstuff_checkbox.Bind(wx.EVT_CHECKBOX, self.OnIncludeStuffClicked)
        self.__incdebug_checkbox.Bind(wx.EVT_CHECKBOX, self.OnIncludeDebugClicked)

        vsizer = wx.BoxSizer(wx.VERTICAL)
        vsizer.Add(self.__notebook, 1, wx.EXPAND)
        vsizer.Add(hsizer, 0, wx.EXPAND | wx.ALL, 3)
        self.SetSizer(vsizer)

        self.__dispersy_update_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.UpdateInfo, self.__dispersy_update_timer)
        self.__dispersy_update_timer.Start(5000, False)

        self.UpdateInfo()

    def SwitchTab(self, num):
        self.__notebook.SetSelection(num)

    def OnIncludeStuffClicked(self, event):
        self.UpdateInfo()

    def OnIncludeDebugClicked(self, event):
        self.__dispersy.statistics.enable_debug_statistics(self.__incdebug_checkbox.GetValue())
        self.UpdateInfo()

    def UpdateInfo(self, event=None):
        def do_db():
            self.__dispersy.statistics.update(database=self.__incstuff_checkbox.GetValue())
            return self.__dispersy.statistics

        def do_gui(delayedResult):
            stats = delayedResult.get()  # can contain an exception
            enabled = bool(self.__incstuff_checkbox.GetValue())
            self.__community_panel.ShowDatabaseInfo(enabled)

            self.__summary_panel.UpdateInfo(stats)
            self.__community_panel.UpdateInfo(stats)
            self.__rawinfo_panel.UpdateInfo(stats)
            self.__runtime_panel.UpdateInfo(stats)
            self.Layout()

        startWorker(do_gui, do_db, uId=u"DispersyDebugFrame_UpdateInfo", priority=GUI_PRI_DISPERSY)

# --------------------------------------------------
# Summary Panel
# --------------------------------------------------
class DispersySummaryPanel(wx.lib.scrolledpanel.ScrolledPanel):

    def __init__(self, parent, id):
        super(DispersySummaryPanel, self).__init__(parent, id)
        self.__utility = GUIUtility.getInstance().utility

        self.SetBackgroundColour(wx.WHITE)

        gridsizer = wx.FlexGridSizer(0, 2, 3, 10)
        gridsizer.AddGrowableCol(1)

        spacer = wx.BoxSizer()
        spacer.Add(gridsizer, 1, wx.EXPAND | wx.ALL, 3)

        self.SetSizer(spacer)
        self.__info_list = None
        self.__text_dict = {}

        # key, value, tip (optional)
        self.__info_list = [
            ["WAN Address", DATA_NONE, None],
            ["LAN Address", DATA_NONE, None],
            ["Connection", DATA_NONE, None],
            ["Runtime", DATA_NONE, None],
            ["Download", DATA_NONE, None],
            ["Upload", DATA_NONE, None],
            ["Packets Sent", DATA_NONE,
                "Packets sent vs Packets handled"],
            ["Packets Received", DATA_NONE,
                "Packets received vs Packets handled"],
            ["Packets Success", DATA_NONE,
                "Messages successfully handled vs Packets received"],
            ["Packets Dropped", DATA_NONE,
                "Packets dropped vs Packets received"],
            ["Packets Delayed", DATA_NONE,
                "Packets being delayed vs Packets received"],
            ["Packets Delayed send", DATA_NONE,
                "Total number of delaymessages or delaypacket messages being sent"],
            ["Packets Delayed success", DATA_NONE,
                "Total number of packets which were delayed, and did not timeout"],
            ["Packets Delayed timeout", DATA_NONE,
                "Total number of packets which were delayed, but got a timeout"],
            ["Walker Success", DATA_NONE, None],
            ["Walker Success (from trackers)", DATA_NONE,
                "Comparing the successes to tracker to overall successes"],
            ["Sync-Messages Created", DATA_NONE,
                "Total number of messages created by us in this session which should be synced"],
            ["Bloom New", DATA_NONE,
                "Total number of bloomfilters created vs IntroductionRequest sent in this session"],
            ["Bloom Reused", DATA_NONE,
                "Total number of bloomfilters reused vs IntroductionRequest sent in this session"],
            ["Bloom Skipped", DATA_NONE,
                "Total number of bloomfilters skipped vs IntroductionRequest sent in this session"],
            ["Debug Mode", DATA_NONE, None],
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

    def UpdateInfo(self, stats, to_cleanup=False):
        if to_cleanup:
            for info in self.__info_list:
                info[1] = DATA_NONE
        else:
            self.__info_list[0][1] = "%s:%d" % stats.wan_address
            self.__info_list[1][1] = "%s:%d" % stats.lan_address
            self.__info_list[2][1] = unicode(stats.connection_type)

            self.__info_list[3][1] = "%s" % self.__utility.eta_value(stats.timestamp - stats.start)
            self.__info_list[4][1] = "%s or %s/s" % (
                self.__utility.size_format(stats.total_down),
                self.__utility.size_format(int(stats.total_down / (stats.timestamp - stats.start)))
            )
            self.__info_list[5][1] = "%s or %s/s" % (
                self.__utility.size_format(stats.total_up),
                self.__utility.size_format(int(stats.total_up / (stats.timestamp - stats.start)))
            )
            self.__info_list[6][1] = compute_ratio(stats.total_send,
                stats.received_count + stats.total_send)
            self.__info_list[7][1] = compute_ratio(stats.received_count,
                stats.received_count + stats.total_send)
            self.__info_list[8][1] = compute_ratio(stats.success_count, stats.received_count)
            self.__info_list[9][1] = compute_ratio(stats.drop_count, stats.received_count)
            self.__info_list[10][1] = compute_ratio(stats.delay_count, stats.received_count)
            self.__info_list[11][1] = compute_ratio(stats.delay_send, stats.delay_count)
            self.__info_list[12][1] = compute_ratio(stats.delay_success, stats.delay_count)
            self.__info_list[13][1] = compute_ratio(stats.delay_timeout, stats.delay_count)
            self.__info_list[14][1] = compute_ratio(stats.walk_success, stats.walk_attempt)
            self.__info_list[15][1] = compute_ratio(stats.walk_bootstrap_success,
                stats.walk_bootstrap_attempt)
            self.__info_list[16][1] = "%s" % stats.created_count
            self.__info_list[17][1] = compute_ratio(sum(c.sync_bloom_new for c in stats.communities),
                sum(c.sync_bloom_send + c.sync_bloom_skip for c in stats.communities))
            self.__info_list[18][1] = compute_ratio(sum(c.sync_bloom_reuse for c in stats.communities),
                sum(c.sync_bloom_send + c.sync_bloom_skip for c in stats.communities))
            self.__info_list[19][1] = compute_ratio(sum(c.sync_bloom_skip for c in stats.communities),
                sum(c.sync_bloom_send + c.sync_bloom_skip for c in stats.communities))
            self.__info_list[20][1] = "yes" if __debug__ else "no"

        for key, value, _ in self.__info_list:
            self.__text_dict[key].SetLabel(value)

        self.SetupScrolling()

# --------------------------------------------------
# Community Panel and Widgets
# --------------------------------------------------

class CommunityPanel(wx.Panel):

    def __init__(self, parent, id):
        super(CommunityPanel, self).__init__(parent, id)
        self.SetBackgroundColour(wx.WHITE)

        splitter = wx.SplitterWindow(self, -1, style=wx.SP_BORDER)
        splitter.SetSashGravity(0.5)

        self.__listctrl = AutoWidthListCtrl(splitter, -1,
            style=wx.LC_REPORT | wx.LC_ALIGN_LEFT | wx.LC_SINGLE_SEL)
        self.__listctrl.SetMinSize((600, 200))
        self.__listctrl.InsertColumn(0, "Classification", width=200)
        self.__listctrl.InsertColumn(1, "Identifier", width=100)
        self.__listctrl.InsertColumn(2, "Database ID", width=100)
        self.__listctrl.InsertColumn(3, "Member", width=100)
        self.__listctrl.InsertColumn(4, "Candidates")

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
        if self.__selected_community_identifier == community_data["Identifier"]:
            return

        self.__selected_community_identifier = community_data["Identifier"]
        self.__detail_panel.UpdateInfo(community_data)

    def UpdateInfo(self, stats):
        community_list = sorted(stats.communities,
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
                candidate_count = "%d " % len(community.candidates)
                candidate_list = [("%s" % global_time, "%s:%s" % lan, "%s:%s" % wan)
                    for lan, wan, global_time in community.candidates]
                candidate_list.sort()
            elif community.candidates:
                candidate_count = "%d*" % len(community.candidates)
            else:
                candidate_count = "-"

            median_global_time = "%d (%d difference)" % \
                (community.acceptable_global_time - community.dispersy_acceptable_global_time_range,
                 community.acceptable_global_time - community.global_time -
                    community.dispersy_acceptable_global_time_range)

            database_list = []
            if community.database:
                database_str = "%d packets" % \
                    sum(count for count in community.database.itervalues())
                for name, count in sorted(community.database.iteritems(), key=lambda tup: tup[1]):
                    database_list.append(("%s" % count, "%s" % name))
            else:
                database_str = "? packets"

            community_data = {
                "Identifier": "%s" % community.hex_cid,
                "Member": "%s" % community.hex_mid,
                "Classification": "%s" % community.classification,
                "Database id": "%s" % community.database_id,
                "Global time": "%s" % community.global_time,
                "Median global time": "%s" % median_global_time,
                "Acceptable range": "%s" % community.dispersy_acceptable_global_time_range,
                "Sync bloom created": "%s" % community.sync_bloom_new,
                "Sync bloom reused": "%s" % community.sync_bloom_reuse,
                "Sync bloom skipped": "%s" % community.sync_bloom_skip,
                "Candidates": "%s" % candidate_count,
                "Candidate_list": candidate_list,
                "Database": database_str,
                "Database_list": database_list,
            }
            # update community data list
            self.__community_data_list.append(community_data)

            community_list_for_update.append((community_data["Classification"],
                community_data["Identifier"][:7], community_data["Database id"],
                community_data["Member"][:7], community_data["Candidates"])
            )

            if self.__selected_community_identifier == community_data["Identifier"]:
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

        self.__FIELDS = ("Identifier", "Member", "Classification", "Global time", \
            "Median global time", "Acceptable range", "Sync bloom created", \
            "Sync bloom reused", "Sync bloom skipped", "Candidates", \
            "Database")

        hsizer = wx.BoxSizer(wx.HORIZONTAL)

        info_panel = wx.Panel(self, -1, style=wx.BORDER_SUNKEN)
        info_panel.SetBackgroundColour(wx.WHITE)
        info_panel.SetMinSize((470, 300))
        self.__info_panel = info_panel

        self.__text = {}
        gridsizer = wx.FlexGridSizer(0, 2, 3, 3)
        for title in self.__FIELDS:
            key_text = wx.StaticText(info_panel, -1, title)
            _set_font(key_text, fontweight=wx.FONTWEIGHT_BOLD)

            value_text = wx.StaticText(info_panel, -1)
            gridsizer.AddMany([
                (key_text, 0, wx.EXPAND),
                (value_text, 0, wx.EXPAND)])

            self.__text[title] = (key_text, value_text)
        info_panel.SetSizer(gridsizer)

        self.__candidate_list = AutoWidthListCtrl(self, -1,
            style=wx.LC_REPORT | wx.LC_ALIGN_LEFT | wx.BORDER_SUNKEN)
        self.__candidate_list.InsertColumn(0, "Global time", width=70)
        self.__candidate_list.InsertColumn(1, "LAN", width=130)
        self.__candidate_list.InsertColumn(2, "WAN")

        self.__database_list = AutoWidthListCtrl(self, -1,
            style=wx.LC_REPORT | wx.LC_ALIGN_LEFT | wx.BORDER_SUNKEN)
        self.__database_list.InsertColumn(0, "Count")
        self.__database_list.InsertColumn(1, "Info")

        self.__to_show_database = False
        self.__database_list.Show(self.__to_show_database)

        hsizer.Add(self.__info_panel, 0, wx.EXPAND | wx.RIGHT, 2)
        hsizer.Add(self.__candidate_list, 1, wx.EXPAND)
        hsizer.Add(self.__database_list, 1, wx.EXPAND | wx.LEFT, 2)
        self.SetSizer(hsizer)

    def ShowDatabaseInfo(self, enabled):
        if enabled != self.__to_show_database:
            self.__to_show_database = enabled
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
            self.__database_list.UpdateData(community_data["Database_list"])
            self.__candidate_list.UpdateData(community_data["Candidate_list"])

        self.Layout()

# --------------------------------------------------
# RawInfo Panel
# --------------------------------------------------

class RawInfoPanel(wx.Panel):

    def __init__(self, parent, id):
        super(RawInfoPanel, self).__init__(parent, id)
        self.SetBackgroundColour(LIST_GREY)

        self.__info = None
        self.__selected_category = None

        self.__CATEGORIES = ("drop", "delay", "success", "outgoing",
            "created", "walk_fail", "attachment", "database",
            "endpoint_recv", "endpoint_send", "bootstrap_candidates")
        self.__IP_CATEGORIES = ("bootstrap_candidates", "walk_fail")

        self.__category_list = AutoWidthListCtrl(self, -1,
            style=wx.LC_REPORT | wx.LC_ALIGN_LEFT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN)
        self.__category_list.InsertColumn(0, "Category", width=150)
        self.__category_list.InsertColumn(1, "Total Count")
        self.__category_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnCategorySelected)

        self.__detail_list = AutoWidthListCtrl(self, -1, style=wx.LC_REPORT | wx.BORDER_SUNKEN)
        self.__detail_list.InsertColumn(0, "Count", width=50)
        self.__detail_list.InsertColumn(1, "Info")

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        hsizer.Add(self.__category_list, 1, wx.EXPAND | wx.RIGHT, 2)
        hsizer.Add(self.__detail_list, 2, wx.EXPAND)
        self.SetSizer(hsizer)

    def OnCategorySelected(self, event):
        category = self.__info[event.GetIndex()][0]
        if self.__selected_category == category:
            return

        self.__selected_category = category
        self.__detail_list.UpdateData(self.__info[event.GetIndex()][1])

    def UpdateInfo(self, stats):
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
                count_str = "%s" % value
                total_count += value

                if category in self.__IP_CATEGORIES:
                    if isinstance(key, tuple):
                        info_str = "%s:%s" % key
                    else:
                        info_str = str2unicode(key)
                elif category == "attachment":
                    info_str = "%s" % binascii.hexlify(key)
                else:
                    info_str = str2unicode(key)
                self.__info[idx][1].append((count_str, info_str))

            # update category list
            total_count = "%s" % total_count
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

    def __init__(self, parent, id):
        super(RuntimeProfilingPanel, self).__init__(parent, id)
        self.SetBackgroundColour(LIST_GREY)

        self.__current_selection_name = None
        self.__combined_list = []

        sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.__list1 = AutoWidthListCtrl(self, -1,
            style=wx.LC_REPORT | wx.LC_ALIGN_LEFT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN)
        self.__list1.InsertColumn(0, "Duration", width=70)
        self.__list1.InsertColumn(1, "Entry", width=250)
        self.__list1.InsertColumn(2, "Average", width=70)
        self.__list1.InsertColumn(3, "Count")
        set_small_modern_font(self.__list1)

        self.__list1.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnList1Selected)

        self.__list2 = AutoWidthListCtrl(self, -1, style=wx.LC_REPORT | wx.BORDER_SUNKEN)
        self.__list2.InsertColumn(0, "Duration", width=70)
        self.__list2.InsertColumn(1, "Entry", width=250)
        self.__list2.InsertColumn(2, "Average", width=70)
        self.__list2.InsertColumn(3, "Count")
        set_small_modern_font(self.__list2)

        sizer.Add(self.__list1, 1, wx.EXPAND | wx.RIGHT, 2)
        sizer.Add(self.__list2, 1, wx.EXPAND)
        self.SetSizer(sizer)

    def OnList1Selected(self, event):
        this_idx = event.GetIndex()
        if self.__current_selection_name == self.__combined_list[this_idx][1]:
            return

        self.__current_selection_name = self.__combined_list[this_idx][1]
        self.__list2.DeleteAllItems()
        data_list = self.__combined_list[this_idx][4]
        for duration, entry, average, count in data_list:
            self.__list2.Append([u"%7.2f" % duration, u"%s" % entry,
                u"%7.2f" % average, u"%s" % count])

    def UpdateInfo(self, stats):
        self.__list1.DeleteAllItems()
        self.__list2.DeleteAllItems()
        prev_selection_name = self.__current_selection_name
        self.__current_selection_name = None

        if not getattr(stats, "runtime", None):
            return

        combined_dict = {}
        for stat_dict in stats.runtime:
            processed_data = {}
            for k, v in stat_dict.iteritems():
                if k == "entry":
                    v = v.replace("\n", "\n          ")
                processed_data[k] = v

            name = processed_data["entry"].split("\n")[0]
            combined_name = name.split()[0]

            data = (processed_data["duration"], name,
                processed_data["average"], processed_data["count"])

            if combined_name not in combined_dict:
                # total-duration, average, count, and data-list
                combined_dict[combined_name] = [0, 0, 0, list()]

            combined_dict[combined_name][0] += processed_data["duration"]
            combined_dict[combined_name][1] += processed_data["average"]
            combined_dict[combined_name][2] += processed_data["count"]
            combined_dict[combined_name][3].append(data)

        # convert dict to list
        combined_list = []
        for k, v in combined_dict.iteritems():
            v[3].sort(reverse=True)
            combined_list.append((v[0], k, v[1], v[2], v[3]))
        combined_list.sort(reverse=True)
        self.__combined_list = combined_list

        prev_selection_idx = None
        idx = 0
        for duration, entry, average, count, _ in combined_list:
            if entry == prev_selection_name:
                prev_selection_idx = idx
            idx += 1
            self.__list1.Append([u"%7.2f" % duration, u"%s" % entry,
                u"%7.2f" % average, u"%s" % count])

        if prev_selection_idx is not None:
            self.__list1.Select(prev_selection_idx)
