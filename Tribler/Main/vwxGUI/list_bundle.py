# written by Raynor Vliegendhart
# see LICENSE.txt for license information

import os
import sys
import wx
from Tribler.__init__ import LIBRARYNAME
from Tribler.Main.vwxGUI.list_body import ListItem, FixedListBody, NativeIcon
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.list import GenericSearchList
from Tribler.Main.vwxGUI.list_header import ListHeader
from Tribler.Main.vwxGUI.list_details import TorrentDetails
from Tribler.Main.vwxGUI.tribler_topButton import LinkStaticText
from Tribler.Core.CacheDB.SqliteCacheDBHandler import UserEventLogDBHandler

from __init__ import *
from traceback import print_exc

DEBUG = True

BUNDLE_FONT_SIZE_DECREMENT = 1 # TODO: on my machine this results in fontsize 7, a bit too small I think? 
BUNDLE_FONT_COLOR = (50,50,50)

BUNDLE_NUM_COLS = 3
BUNDLE_NUM_ROWS = 3

class BundleListItem(ListItem):
    
    def __init__(self, parent, parent_list, columns, data, original_data, leftSpacer = 0, rightSpacer = 0, showChange = False, list_selected = LIST_SELECTED):
        # fetch bundle and descriptions
        bundle = original_data['bundle']
        self.general_description = original_data.get('bundle_general_description')
        self.description = original_data.get('bundle_description')
        
        # use the head as original_data (needed for SearchList)
        original_data = bundle[0]
        
        # call the original constructor
        ListItem.__init__(self, parent, parent_list, columns, data, original_data, leftSpacer, rightSpacer, showChange, list_selected)
        
        # Now add the BundleListView (after AddComponents)
        self.AddBundlePanel(bundle[1:])
        self.bundlepanel.Layout()
        
        self.expanded_panel = None
        self.expanded_panel_shown = False
        
    def AddBundlePanel(self, bundled):
        self.bundlepanel = BundlePanel(self, self.parent_list, bundled, 
                                       self.general_description, self.description,
                                       -BUNDLE_FONT_SIZE_DECREMENT)
        self.AddEvents(self.bundlepanel)
        self.vSizer.Add(self.bundlepanel, 1, wx.EXPAND)
        
    def RefreshData(self, data):
        infohash, item_data, original_data = data
        
        if isinstance(original_data, dict) and 'bundle' in original_data:
            #update top row
            ListItem.RefreshData(self, (infohash, item_data, original_data['bundle'][0]))
            bundle = original_data['bundle']
            
            if DEBUG:
                print >>sys.stderr, "*** BundleListItem.RefreshData: bundle changed:", original_data['key'], '#1+%s' % (len(bundle)-1)
                        
            self.bundlepanel.SetHits(bundle[1:])
            self.bundlepanel.UpdateHeader(original_data['bundle_general_description'], original_data['bundle_description'])
            self.Highlight(1)
        else:
            if infohash == self.original_data['infohash']: #update top row
                ListItem.RefreshData(self, data)
                
            else: #update part of list
                self.bundlepanel.RefreshDataBundleList(infohash, original_data)
   
    def GetExpandedPanel(self):
        if self.expanded_panel_shown:
            return self.expanded_panel
        
        return self.bundlepanel.GetExpandedPanel()

    def Expand(self, panel):
        ListItem.Expand(self, panel)
        
        self.vSizer.Detach(panel)
        self.vSizer.Insert(1, panel, 0, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.BOTTOM, 3)
        
        self.expanded_panel = panel
        self.expanded_panel_shown = True
    
    def Collapse(self):
        panel = ListItem.Collapse(self)
        
        self.expanded_panel = None
        self.expanded_panel_shown = False
        self.bundlepanel.ChangeState(BundlePanel.COLLAPSED)
        
        return panel
    
    def OnClick(self, event = None):
        if event:
            #ignore onclick from bundlegrid
            control = event.GetEventObject()
            if getattr(control, 'action', False): 
                return
        
        if self.expanded == self.expanded_panel_shown:
            ListItem.OnClick(self, event)
        else:
            self.ShowExpandedPanel(not self.expanded_panel_shown)
    
    def ShowExpandedPanel(self, show = True):
        panel = self.expanded_panel
        
        if panel:
            self.Freeze()
            
            if DEBUG:
                print >> sys.stderr, "BundleListItem: ShowExpandedPanel", show, self.expanded_panel_shown
            
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
        ListItem.BackgroundColor(self, color)
        self.bundlepanel.SetBackgroundColour(color)
        
    def AddEvents(self, control):
        if isinstance(control, LinkStaticText):
            control.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouse)
        else:
            ListItem.AddEvents(self, control)

class BundlePanel(wx.Panel):
    
    COLLAPSED, PARTIAL, FULL = range(3)
    
    icons = None
    @classmethod
    def load_icons(cls):
        if not cls.icons:
            icons = cls.icons = {}
            guiUtility = GUIUtility.getInstance()
            utility = guiUtility.utility
            base_path = os.path.join(utility.getPath(), LIBRARYNAME, "Main", "vwxGUI", "images")
            
            icons['info'] = wx.Bitmap(os.path.join(base_path, "info.png"), wx.BITMAP_TYPE_ANY)
    
    def __init__(self, parent, parent_list, hits, general_description = None, description = None, font_increment=0):
        wx.Panel.__init__(self, parent)
        
        # preload icons
        self.load_icons()
        self.parent_listitem = parent
        self.parent_list = parent_list
        
        # logging
        self.guiutility = GUIUtility.getInstance()
        self.uelog = UserEventLogDBHandler.getInstance()
        
        self.state = BundlePanel.COLLAPSED
        self.nrhits = -1
        self.bundlelist = None
        
        self.font_increment = font_increment
        self.vsizer = wx.BoxSizer(wx.VERTICAL)
        
        self.SetBackgroundColour(wx.WHITE)
        
        self.AddHeader()
        self.AddGrid()
        
        self.SetHits(hits)
        self.UpdateHeader(general_description, description)
        
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.AddSpacer((22, -1))
        sizer.Add(self.vsizer, 1, wx.EXPAND|wx.BOTTOM|wx.RIGHT, 3)
        self.SetSizer(sizer)
    
    def AddHeader(self):
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.header = wx.StaticText(self, -1, ' ')
        self.info_icon = wx.StaticBitmap(self, -1, self.icons['info'])

        sizer.Add(self.header, 0, wx.RIGHT, 7)
        sizer.Add(self.info_icon, 0, wx.ALIGN_CENTER_VERTICAL)
        self.vsizer.Add(sizer, 0, wx.BOTTOM, 3)
    
    def UpdateHeader(self, general_description, description):
        self.SetGeneralDescription(general_description)
        self.SetDescription(description)
    
    def AddGrid(self):
        self.grid = wx.FlexGridSizer(BUNDLE_NUM_ROWS, BUNDLE_NUM_COLS, 3, 7)
        self.grid.SetFlexibleDirection(wx.HORIZONTAL)
        self.grid.SetNonFlexibleGrowMode(wx.FLEX_GROWMODE_NONE)
        self.grid.SetMinSize((1,-1))
        
        for i in xrange(BUNDLE_NUM_ROWS):
            self.grid.AddGrowableRow(i, 1)
        
        for j in xrange(BUNDLE_NUM_COLS):
            self.grid.AddGrowableCol(j, 1)
        self.vsizer.Add(self.grid, 1, wx.EXPAND)
    
    def UpdateGrid(self, hits):
        N = BUNDLE_NUM_ROWS * BUNDLE_NUM_COLS
        items_to_add = min(N, self.nrhits)
        if self.nrhits > N:
            items_to_add -= 1

        self.Freeze()
        
        children = self.grid.GetChildren()
        didChange = len(children) < min(N, self.nrhits)
        if not didChange:
            if DEBUG:
                print >> sys.stderr, "*** BundlePanel.UpdateGrid: total nr items did not change, updating labels only"
            
            #total nr items did not change
            for i in range(min(len(children), items_to_add)):
                link_static_text = children[i].GetWindow()
                if link_static_text and getattr(link_static_text, 'GetLabel', False):
                    if hits[i]['name'] != link_static_text.GetLabel():
                        link_static_text.SetLabel(hits[i]['name'])
                        link_static_text.action = hits[i]
                else:
                    didChange = True
                    break
            
            if self.nrhits > N:
                more_caption = '(%s more...)' % (self.nrhits - N + 1)
                link_static_text = children[i+1].GetWindow()
                if link_static_text and getattr(link_static_text, 'GetLabel', False):
                    if link_static_text.GetLabel() != more_caption:
                        link_static_text.SetLabel(more_caption)
                        link_static_text.Unbind(wx.EVT_LEFT_UP)
                        link_static_text.Bind(wx.EVT_LEFT_UP, self.OnMoreClick)
                else:
                    didChange = True

        if didChange:
            self.grid.ShowItems(False)
            self.grid.Clear(deleteWindows = True)
            for i in range(items_to_add):
                hit = hits[i] 
    
                new_text = LinkStaticText(self, hit['name'], icon = False, icon_type = 'tree', icon_align = wx.ALIGN_LEFT, font_increment = self.font_increment, font_colour = BUNDLE_FONT_COLOR)
                new_text.Bind(wx.EVT_LEFT_UP, self.OnBundleLinkClick)
                new_text.SetMinSize((1,-1))
                new_text.action = hit
                self.grid.Add(new_text, 0, wx.EXPAND)
                
            for i in range(BUNDLE_NUM_COLS - items_to_add):
                self.grid.AddSpacer((1,-1))
            
            if self.nrhits > N:
                caption = '(%s more...)' % (self.nrhits - N + 1)
                
                more_label = LinkStaticText(self, caption, icon = False, icon_align = wx.ALIGN_LEFT, font_increment = self.font_increment, font_colour = BUNDLE_FONT_COLOR)
                more_label.Bind(wx.EVT_LEFT_UP, self.OnMoreClick)
                self.grid.Add(more_label, 0, wx.EXPAND)
                
            self.parent_listitem.AddEvents(self.grid)
            
            if self.state != self.COLLAPSED:
                self.ShowGrid(False)
                    
        self.Thaw()
    
    def ShowGrid(self, show):
        if show:
            self.grid.ShowItems(True)
        else:
            self.grid.ShowItems(False)
    
    def UpdateList(self, hits):
        self.hits = hits
        
        if self.bundlelist:
            self.bundlelist.SetData(hits)
    
    def ShowList(self, show):
        if self.bundlelist is None and show:
            max_list = BUNDLE_NUM_ROWS * BUNDLE_NUM_COLS
            if len(self.hits) != BUNDLE_NUM_ROWS * BUNDLE_NUM_COLS:
                max_list -= 1
            
            self.bundlelist = BundleListView(parent = self, list_item_max = max_list)
            self.vsizer.Add(self.bundlelist, 0, wx.EXPAND|wx.BOTTOM, 17) #20 - 3 = 17
            
            # SetData does wx.Yield, which could cause a collapse event to be processed within the setdata
            # method. Thus we have to do this after the add to the sizer
            self.bundlelist.SetData(self.hits)
        
        elif self.bundlelist is not None and not show:
            self.vsizer.Detach(self.bundlelist)
            self.bundlelist.Show(False)
            self.bundlelist.Destroy()
            self.bundlelist = None
        
    def OnChange(self, scrollToTop = False):
        self.Layout()
        self.parent_listitem.Layout()
        self.parent_list.OnChange(scrollToTop)
    
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
    
    def SetHits(self, hits):
        self.nrhits = len(hits)
        
        self.UpdateGrid(hits)
        self.UpdateList(hits)
        
        self.Layout()
    
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

            if DEBUG:
                statestr = lambda st: ['COLLAPSED', 'PARTIAL', 'FULL'][st]
                print >>sys.stderr, '*** BundlePanel.ChangeState: %s --> %s' % (statestr(old_state), statestr(new_state))
    
    def ExpandHit(self, hit):
        id = hit['infohash']
        
        self.bundlelist.ExpandItem(id)
        self.parent_listitem.ShowSelected()
    
    def OnBundleLinkClick(self, event):
        #do expand
        self.ExpandAndHideParent()
        
        staticText = event.GetEventObject()
        action = getattr(staticText, 'action', None)
        if action is not None:
            # Reason for non-persistence (for now) is least-surprise.
            # If the user collapses a bundled listitem, the previously 
            # clicked item is still at the same location.
            self.hits.remove(action)
            self.hits.insert(0, action)
        
            self.ChangeState(BundlePanel.PARTIAL)
            self.ExpandHit(action)
        
        def db_callback():
            self.uelog.addEvent(message="Bundler GUI: BundleLink click; %s; %s;" %
                                (self.nrhits, self.parent_listitem.general_description), type = 3)
        self.guiutility.frame.guiserver.add_task(db_callback)
    
    def OnMoreClick(self, event):
        #do expand
        self.ExpandAndHideParent()
        self.ChangeState(BundlePanel.FULL)
        
        def db_callback():
            self.uelog.addEvent(message="Bundler GUI: More click; %s; %s;" %
                                (self.nrhits, self.parent_listitem.general_description), type = 3)
        self.guiutility.frame.guiserver.add_task(db_callback)
    
    def ExpandAndHideParent(self):
        listitem = self.GetParent()
        
        listitem.Freeze()
        
        if not listitem.expanded:
            # Make sure the listitem is marked as expanded
            listitem.OnClick()
        
        # but hide the panel
        listitem.ShowExpandedPanel(False)
        
        listitem.Thaw()
    
    #Called from GUI to get expanded torrentdetails panel
    def GetExpandedPanel(self):
        if self.bundlelist:
            item = self.bundlelist.GetExpandedItem()
            if item:
                return item.GetExpandedPanel()
            
    def SetBackgroundColour(self, colour):
        wx.Panel.SetBackgroundColour(self, colour)
        
        if getattr(self, 'grid', False):
            for sizeritem in self.grid.GetChildren():
                if sizeritem.IsWindow():
                    child = sizeritem.GetWindow()
                    if isinstance(child, wx.Panel):
                        child.SetBackgroundColour(colour)
    
class BundleListView(GenericSearchList):
    
    def __init__(self, parent = None, list_item_max = None):
        self.list_item_max = list_item_max
        columns = [{'name':'Name', 'width': wx.LIST_AUTOSIZE, 'sortAsc': True, 'icon': 'tree'}, \
                   {'name':'Size', 'width': '9em', 'style': wx.ALIGN_RIGHT, 'fmt': self.format_size, 'sizeCol': True}, \
                   {'type':'method', 'width': wx.LIST_AUTOSIZE_USEHEADER, 'method': self.CreateRatio, 'name':'Popularity'}, \
                   {'type':'method', 'width': -1, 'method': self.CreateDownloadButton}]
        
        GenericSearchList.__init__(self, columns, LIST_GREY, [3,3], True, showChange = True, parent=parent)
    
    def CreateHeader(self):
        # Normally, the column-widths are fixed during this phase
        # Or perhaps easier... just create the simplest header, but don't return it:
        header = ListHeader(self, self.columns)
        header.Destroy()
        
    def CreateFooter(self):
        pass 
    
    def CreateList(self):
        return ExpandableFixedListBody(self, self, self.columns, self.spacers[0], self.spacers[1], self.singleSelect, self.showChange, list_item_max = self.list_item_max)
    
    def OnExpand(self, item):
        # Keep only one panel open at all times, thus we make sure the parent is closed
        bundlepanel = self.parent
        bundlepanel.parent_listitem.ShowExpandedPanel(False)
        
        return TorrentDetails(item, item.original_data, compact = True)
    
    def OnCollapseInternal(self, item):
        pass
    
    def OnChange(self, scrollToTop = False):
        self.parent.OnChange(scrollToTop)
    
    def ExpandItem(self, id):
        # id == infohash
        self.list.Select(id, raise_event=True)
        
    def VerticalItemOffset(self, id):
        # id == infohash
        item = self.list.items[id]
        return item.GetPosition()[1]

class ExpandableFixedListBody(FixedListBody):
    
    def OnChange(self, scrollToTop = False):
        FixedListBody.OnChange(self, scrollToTop)
        
        self.parent_list.OnChange(scrollToTop)