# written by Raynor Vliegendhart
# see LICENSE.txt for license information

import os
import sys
import wx
import logging
from Tribler.__init__ import LIBRARYNAME
from Tribler.Main.vwxGUI.list_body import ListItem, FixedListBody
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility, forceWxThread
from Tribler.Main.vwxGUI.GuiImageManager import GuiImageManager
from Tribler.Main.vwxGUI.list import GenericSearchList
from Tribler.Main.vwxGUI.list_header import ListHeader
from Tribler.Main.vwxGUI.list_details import TorrentDetails
from Tribler.Main.vwxGUI.widgets import LinkStaticText, BetterText as StaticText
from Tribler.Core.CacheDB.SqliteCacheDBHandler import UserEventLogDBHandler

from __init__ import *

BUNDLE_FONT_SIZE_DECREMENT = 0
BUNDLE_FONT_COLOR = (50, 50, 50)
BUNDLE_GRID_COLLAPSE = 800

BUNDLE_NUM_COLS = 2
BUNDLE_NUM_ROWS = 3


class BundleListItem(ListItem):

    def __init__(self, parent, parent_list, columns, data, original_data, leftSpacer=0, rightSpacer=0, showChange=False, list_selected=LIST_SELECTED):
        self._logger = logging.getLogger(self.__class__.__name__)

        # fetch bundle and descriptions
        self.bundle = original_data['bundle']
        self.general_description = original_data.get('bundle_general_description')
        self.description = original_data.get('bundle_description')

        # use the head as original_data (needed for SearchList)
        original_data = self.bundle[0]

        # call the original constructor
        ListItem.__init__(self, parent, parent_list, columns, data, original_data, leftSpacer, rightSpacer, showChange, list_selected)

        # Now add the BundleListView (after AddComponents)
        self.AddBundlePanel(self.bundle[1:])
        self.bundlepanel.Layout()

        self.expanded_panel = None
        self.expanded_panel_shown = False

    def AddBundlePanel(self, bundled):
        self.bundlepanel = BundlePanel(self, self.parent_list, bundled,
                                       self.general_description, self.description,
                                       - BUNDLE_FONT_SIZE_DECREMENT)
        self.AddEvents(self.bundlepanel)
        self.vSizer.Add(self.bundlepanel, 1, wx.EXPAND)

    def RefreshData(self, data):
        infohash, item_data, original_data = data

        if isinstance(original_data, dict) and 'bundle' in original_data:
            self.bundle = original_data['bundle']
            head_original_data, bundled = self.bundle[0], self.bundle[1:]

            ListItem.RefreshData(self, (infohash, item_data, head_original_data))

            showHighlight = self.bundlepanel.SetHits(bundled)
            if showHighlight:
                self.Highlight(1)

            self.bundlepanel.UpdateHeader(original_data['bundle_general_description'], original_data['bundle_description'])

            self._logger.debug("*** BundleListItem.RefreshData: bundle changed: %s #1+%s", original_data['key'], len(bundled))
        else:
            if infohash == self.original_data.infohash:  # update top row
                ListItem.RefreshData(self, data)

            else:  # update part of list
                self.bundlepanel.RefreshDataBundleList(infohash, original_data)

    def GetExpandedPanel(self):
        if self.expanded_panel_shown:
            return self.expanded_panel

        return self.bundlepanel.GetExpandedPanel()

    def Expand(self, panel):
        ListItem.Expand(self, panel)

        self.vSizer.Detach(panel)
        self.vSizer.Insert(1, panel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 3)

        self.expanded_panel = panel
        self.expanded_panel_shown = True

    def Collapse(self):
        panel = ListItem.Collapse(self)

        self.expanded_panel = None
        self.expanded_panel_shown = False
        self.bundlepanel.ChangeState(BundlePanel.COLLAPSED)

        return panel

    def OnClick(self, event=None):
        if event:
            # ignore onclick from bundlegrid
            control = event.GetEventObject()
            if getattr(control, 'action', False):
                self.showing_similar_item = True
                return

            if getattr(self, 'showing_similar_item', False):
                self.showing_similar_item = False
                self.parent_list.OnExpand(self)
                self.bundlepanel.SetBackgroundColour(self.bundlepanel.parent.GetBackgroundColour())

        if True:  # self.expanded == self.expanded_panel_shown:
            ListItem.OnClick(self, event)
        else:
            self.ShowExpandedPanel(not self.expanded_panel_shown)

    def ShowExpandedPanel(self, show=True):
        panel = self.expanded_panel

        if panel and panel.IsShown() != show:
            self.Freeze()

            self._logger.debug("BundleListItem: ShowExpandedPanel %s %s", show, self.expanded_panel_shown)

            panel.Show(show)

            self.expanded_panel_shown = show
            if self.expanded_panel_shown:
                self.bundlepanel.CollapseExpandedItem()

            self.parent_list.OnChange()
            self.Layout()

            self.Thaw()

            if show:
                panel.Layout()

    def BackgroundColor(self, color):
        if self.GetBackgroundColour() != color:
            self.Freeze()

            ListItem.BackgroundColor(self, color)
            self.bundlepanel.SetBackgroundColour(color)

            self.Thaw()

    def OnChange(self, scrollToTop=False):
        self.Layout()
        self.parent_list.OnChange(scrollToTop)

    def AddEvents(self, control):
        if isinstance(control, LinkStaticText):
            control.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouse)
        else:
            ListItem.AddEvents(self, control)

    def OnEventSize(self, width):
        ListItem.OnEventSize(self, width)
        return self.bundlepanel.OnEventSize(width)


class BundlePanel(wx.BoxSizer):

    COLLAPSED, PARTIAL, FULL = range(3)

    icons = None

    @classmethod
    def load_icons(cls):
        if not cls.icons:
            icons = cls.icons = {}

            icons['info'] = GuiImageManager.getInstance().getImage(u"info.png")

    def __init__(self, parent, parent_list, hits, general_description=None, description=None, font_increment=0):
        wx.BoxSizer.__init__(self, wx.HORIZONTAL)

        self._logger = logging.getLogger(self.__class__.__name__)

        # preload icons
        self.load_icons()

        self.parent = parent
        self.parent_listitem = parent
        self.parent_list = parent_list

        listbody_width = parent_list.GetSize()[0]
        if listbody_width < BUNDLE_GRID_COLLAPSE:
            self.num_cols = 1
        else:
            self.num_cols = BUNDLE_NUM_COLS

        # logging
        self.guiutility = GUIUtility.getInstance()
        self.uelog = UserEventLogDBHandler.getInstance()

        self.state = BundlePanel.COLLAPSED
        self.nrhits = -1
        self.bundlelist = None

        self.font_increment = font_increment
        self.vsizer = wx.BoxSizer(wx.VERTICAL)

        self.SetBackgroundColour(DEFAULT_BACKGROUND)

        self.indent = 3 + 3 + self.parent_list.leftSpacer  # width of 3px left spacer + 3px right spacer

        self.AddHeader()
        self.AddGrid()

        self.SetHits(hits, noChange=True)
        self.UpdateHeader(general_description, description)

        self.AddSpacer((self.indent, -1))
        self.Add(self.vsizer, 1, wx.EXPAND | wx.BOTTOM, 7)

    def AddHeader(self):
        sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.header = StaticText(self.parent, -1, ' ')
        self.info_icon = wx.StaticBitmap(self.parent, -1, self.icons['info'])

        sizer.Add(self.header, 0, wx.RIGHT, 7)
        sizer.Add(self.info_icon, 0, wx.ALIGN_CENTER_VERTICAL)
        self.vsizer.Add(sizer, 0, wx.BOTTOM, 3)

    def UpdateHeader(self, general_description, description):
        self.SetGeneralDescription(general_description)
        self.SetDescription(description)

    def AddGrid(self):
        self.grid = wx.FlexGridSizer(0, self.num_cols, 3, 7)
        self.grid.SetFlexibleDirection(wx.HORIZONTAL)
        self.grid.SetNonFlexibleGrowMode(wx.FLEX_GROWMODE_NONE)
        self.grid.SetMinSize((1, -1))

        for i in xrange(BUNDLE_NUM_ROWS):
            self.grid.AddGrowableRow(i, 1)

        for j in xrange(self.num_cols):
            self.grid.AddGrowableCol(j, 1)
        self.vsizer.Add(self.grid, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 14 + self.indent)

    def RebuildGrid(self, new_cols):
        if self.num_cols != new_cols:
            self.num_cols = new_cols

            children = self.grid.GetChildren()
            children_controls = []
            for child in children:
                children_controls.append(child.GetWindow() or child.GetSizer())

            for child in children_controls:
                self.grid.Detach(child)

            self.vsizer.Detach(self.grid)
            self.grid.Destroy()

            self.grid = wx.FlexGridSizer(0, self.num_cols, 3, 7)
            for child in children_controls:
                self.grid.Add(child, 0, wx.EXPAND)

            for j in xrange(self.num_cols):
                self.grid.AddGrowableCol(j, 1)

            self.vsizer.Add(self.grid, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 14 + self.indent)

            self.Layout()
            self.parent_listitem.Layout()

            return True
        return False

    def UpdateGrid(self, hits, noChange=False):
        N = BUNDLE_NUM_ROWS * BUNDLE_NUM_COLS
        items_to_add = min(N, self.nrhits)
        if self.nrhits > N:
            items_to_add -= 1

        self.parent.Freeze()
        children = self.grid.GetChildren()
        didChange = len(children) < min(N, self.nrhits)
        if not didChange:
            self._logger.debug("*** BundlePanel.UpdateGrid: total nr items did not change, updating labels only")

            # total nr items did not change
            for i in range(items_to_add):
                link_static_text = children[i].GetWindow() or children[i].GetSizer()
                if link_static_text and getattr(link_static_text, 'SetLabel', False):
                    link_static_text.SetLabel(hits[i].name)
                    link_static_text.action = hits[i]
                else:
                    didChange = True
                    break

            if self.nrhits > N:
                more_caption = '(%s more...)' % (self.nrhits - N + 1)
                link_static_text = children[i + 1].GetWindow() or children[i + 1].GetSizer()
                if link_static_text and getattr(link_static_text, 'SetLabel', False):
                    link_static_text.SetLabel(more_caption)
                    link_static_text.Unbind(wx.EVT_LEFT_UP)
                    link_static_text.Bind(wx.EVT_LEFT_UP, self.OnMoreClick)
                else:
                    didChange = True

        if didChange:
            self._logger.debug("*** BundlePanel.UpdateGrid: something did change rebuilding grid %s %s", len(children), min(N, self.nrhits))

            curRows = len(children) / BUNDLE_NUM_COLS
            newRows = min(self.nrhits / BUNDLE_NUM_COLS, BUNDLE_NUM_ROWS)
            rowsChanged = curRows != newRows

            self.grid.ShowItems(False)
            self.grid.Clear(deleteWindows=True)
            for i in range(items_to_add):
                hit = hits[i]

                new_text = LinkStaticText(self.parent, hit.name, icon=False, icon_align=wx.ALIGN_LEFT, font_increment=self.font_increment, font_colour=BUNDLE_FONT_COLOR)
                new_text.Bind(wx.EVT_LEFT_UP, self.OnBundleLinkClick)
                new_text.SetMinSize((1, -1))
                new_text.action = hit
                self.grid.Add(new_text, 0, wx.EXPAND)

            if self.nrhits > N:
                caption = '(%s more...)' % (self.nrhits - N + 1)

                more_label = LinkStaticText(self.parent, caption, icon=False, icon_align=wx.ALIGN_LEFT, font_increment=self.font_increment, font_colour=BUNDLE_FONT_COLOR)
                more_label.Bind(wx.EVT_LEFT_UP, self.OnMoreClick)
                self.grid.Add(more_label, 0, wx.EXPAND)

            self.parent_listitem.AddEvents(self.grid)

            if self.state != self.COLLAPSED:
                self.ShowGrid(False)

            if rowsChanged and not noChange:
                self.parent_listitem.OnChange()

        self.parent.Thaw()

        return didChange

    def OnEventSize(self, width):
        if width < BUNDLE_GRID_COLLAPSE:
            return self.RebuildGrid(1)

        return self.RebuildGrid(BUNDLE_NUM_COLS)

    def ShowGrid(self, show):
        if show:
            self.grid.ShowItems(True)
        else:
            self.grid.ShowItems(False)

    def UpdateList(self, hits):
        self.hits = hits

        if self.bundlelist:
            self.bundlelist.SetData(hits)
            if self.state == BundlePanel.FULL:
                self.bundlelist.OnLoadAll()

    def ShowList(self, show):
        if self.bundlelist is None and show:
            max_list = BUNDLE_NUM_ROWS * BUNDLE_NUM_COLS
            if len(self.hits) != BUNDLE_NUM_ROWS * BUNDLE_NUM_COLS:
                max_list -= 1

            self.bundlelist = BundleListView(parent=self.parent, list_item_max=max_list)
            self.vsizer.Add(self.bundlelist, 0, wx.EXPAND | wx.BOTTOM, self.indent - 7)  # a 7px spacer is already present

            # SetData does wx.Yield, which could cause a collapse event to be processed within the setdata
            # method. Thus we have to do this after the add to the sizer
            self.bundlelist.SetData(self.hits)

        elif self.bundlelist is not None and not show:
            self.vsizer.Detach(self.bundlelist)
            self.bundlelist.Show(False)
            self.bundlelist.Destroy()
            self.bundlelist = None

    def CollapseExpandedItem(self):
        if self.state != BundlePanel.COLLAPSED:
            self.bundlelist.list.OnCollapse()

    def RefreshDataBundleList(self, key, data):
        if self.bundlelist is not None:
            self.bundlelist.RefreshData(key, data)

    def SetDescription(self, description):
        self.header.SetToolTipString(description)
        self.info_icon.SetToolTipString(description)

    def SetGeneralDescription(self, general_description):
        if general_description:
            general_description = unicode(general_description)
        else:
            general_description = u'Similar'
        self.header.SetLabel(u'%s items (%s):' % (general_description, self.nrhits))

    def SetHits(self, hits, noChange=False):
        self.nrhits = len(hits)

        gridChanged = self.UpdateGrid(hits, noChange)
        self.UpdateList(hits)

        self.Layout()
        return gridChanged

    def ChangeState(self, new_state, doLayout=True):
        if self.state != new_state:
            old_state = self.state
            self.state = new_state

            if new_state == BundlePanel.COLLAPSED:
                self.ShowList(False)
                self.ShowGrid(True)
            else:
                if new_state == BundlePanel.PARTIAL or new_state == BundlePanel.FULL:
                    self.ShowGrid(False)
                    if old_state == BundlePanel.COLLAPSED:
                        self.ShowList(True)

                    if new_state == BundlePanel.FULL and self.bundlelist:
                        self.bundlelist.OnLoadAll()

            statestr = lambda st: ['COLLAPSED', 'PARTIAL', 'FULL'][st]
            self._logger.debug('*** BundlePanel.ChangeState: %s --> %s', statestr(old_state), statestr(new_state))

    def ExpandHit(self, hit):
        id = hit.infohash

        self.bundlelist.ExpandItem(id)
        self.parent_listitem.ShowSelected()

    def OnBundleLinkClick(self, event):
        # do expand
        # self.ExpandAndHideParent()

        staticText = event.GetEventObject()
        action = getattr(staticText, 'action', None)
        if action is not None:
            # Reason for non-persistence (for now) is least-surprise.
            # If the user collapses a bundled listitem, the previously
            # clicked item is still at the same location.
            if action in self.hits:
                self.hits.remove(action)
                self.hits.insert(0, action)

            # self.ChangeState(BundlePanel.PARTIAL)
            # self.ExpandHit(action)
            self.SetBackgroundColour(self.parent.GetBackgroundColour())
            from __init__ import TRIBLER_RED, LIST_HIGHTLIGHT
            event.GetEventObject().SetBackgroundColour(LIST_HIGHTLIGHT)
            for item in self.parent_listitem.bundle:
                if action.infohash == item.infohash:
                    detailspanel = self.guiutility.SetBottomSplitterWindow(TorrentDetails)
                    detailspanel.setTorrent(item.original_data)
                    item.expandedPanel = detailspanel

        def db_callback():
            self.uelog.addEvent(message="Bundler GUI: BundleLink click; %s; %s;" %
                                (self.nrhits, self.parent_listitem.general_description), type=3)
        self.guiutility.frame.guiserver.add_task(db_callback)

    def OnMoreClick(self, event):
        return
        # do expand
        self.ExpandAndHideParent()
        self.ChangeState(BundlePanel.FULL)

        def db_callback():
            self.uelog.addEvent(message="Bundler GUI: More click; %s; %s;" %
                                (self.nrhits, self.parent_listitem.general_description), type=3)
        self.guiutility.frame.guiserver.add_task(db_callback)

    def ExpandAndHideParent(self):
        self.parent.Freeze()

        if not self.parent_listitem.expanded:
            # Make sure the listitem is marked as expanded
            self.parent_listitem.OnClick()

        # but hide the panel
        self.parent_listitem.ShowExpandedPanel(False)
        self.parent.Thaw()

    # Called from GUI to get expanded torrentdetails panel
    def GetExpandedPanel(self):
        if self.bundlelist:
            item = self.bundlelist.GetExpandedItem()
            if item:
                return item.GetExpandedPanel()

    def SetBackgroundColour(self, colour):
        self.parent.Freeze()
        if getattr(self, 'grid', False):
            for sizeritem in self.grid.GetChildren():
                child = sizeritem.GetWindow() or sizeritem.GetSizer()
                if child and getattr(child, 'SetBackgroundColour', False):
                    child.SetBackgroundColour(colour)

        self.parent.Thaw()


class BundleListView(GenericSearchList):

    def __init__(self, parent=None, list_item_max=None):
        self.list_item_max = list_item_max
        columns = [{'name': 'Name', 'width': wx.LIST_AUTOSIZE, 'sortAsc': True, 'icon': 'tree'},
                   {'name': 'Size', 'width': '9em', 'style': wx.ALIGN_RIGHT, 'fmt': format_size},
                   {'type': 'method', 'width': wx.LIST_AUTOSIZE_USEHEADER, 'method': self.CreateRatio, 'name': 'Popularity'},
                   {'type': 'method', 'width': LIST_AUTOSIZEHEADER, 'method': self.CreateDownloadButton}]

        GenericSearchList.__init__(self, columns, LIST_GREY, [7, 7], True, showChange=True, parent=parent)

    def CreateHeader(self, parent):
        # Normally, the column-widths are fixed during this phase
        # Or perhaps easier... just create the simplest header, but don't return it:
        header = ListHeader(parent, self, self.columns)
        header.Destroy()

    def CreateFooter(self, parent):
        pass

    def CreateList(self, parent):
        pass
        # return ExpandableFixedListBody(parent, self, self.columns, self.spacers[0], self.spacers[1], self.singleSelect, self.showChange, list_item_max = self.list_item_max)

    def OnExpand(self, item):
        # Keep only one panel open at all times, thus we make sure the parent is closed
        self.parent.ShowExpandedPanel(False)
        td = TorrentDetails(self.guiutility.frame.splitter_bottom_window, item.original_data, compact=True)
        self.guiutility.SetBottomSplitterWindow(td)
        return True

    def OnCollapseInternal(self, item):
        self.guiutility.frame.top_bg.ClearButtonHandlers()
        self.guiutility.SetBottomSplitterWindow(None)

    def SetFilteredResults(self, nr):
        pass

    def OnChange(self, scrollToTop=False):
        self.parent.OnChange(scrollToTop)

    def ExpandItem(self, id):
        # id == infohash
        self.list.Select(id, raise_event=True)

    def VerticalItemOffset(self, id):
        # id == infohash
        item = self.list.items[id]
        return item.GetPosition()[1]


class ExpandableFixedListBody(FixedListBody):

    def OnChange(self, scrollToTop=False):
        FixedListBody.OnChange(self, scrollToTop)
        self.parent_list.OnChange(scrollToTop)
