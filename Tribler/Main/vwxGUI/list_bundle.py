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

from __init__ import *
from traceback import print_exc

DEBUG = True

BUNDLE_FONT_SIZE_DECREMENT = 1 # TODO: on my machine this results in fontsize 7, a bit too small I think? 
BUNDLE_FONT_COLOR = (50,50,50)

BUNDLE_NUM_COLS = 3
BUNDLE_NUM_ROWS = 3
BUNDLE_LIST_MAX_SIZE = 8

class BundleListItem(ListItem):
    
    def __init__(self, parent, parent_list, columns, data, original_data, leftSpacer = 0, rightSpacer = 0, showChange = False, list_selected = LIST_SELECTED):
        # fetch bundle and descriptions
        self.bundle = bundle = original_data['bundle']
        self.general_description = original_data.get('bundle_general_description')
        self.description = original_data.get('bundle_description')
        
        # use the head as original_data (needed for SearchList)
        original_data = bundle[0]
        
        # call the original constructor
        ListItem.__init__(self, parent, parent_list, columns, data, original_data, leftSpacer, rightSpacer, showChange, list_selected)
        
        # Now add the BundleListView (after AddComponents)
        self.AddBundlePanel()
        self.bundlepanel.Layout()
        
        self.expanded_panel = None
        self.expanded_panel_shown = False
        
    def AddBundlePanel(self):
        self.bundlepanel = BundlePanel(self, self.parent_list, self.bundle[1:], 
                                       self.general_description, self.description,
                                       -BUNDLE_FONT_SIZE_DECREMENT)
        self.AddEvents(self.bundlepanel)
        self.vSizer.Add(self.bundlepanel, 1, wx.EXPAND)
        
    def RefreshData(self, data):
        infohash, item_data, original_data = data
        if isinstance(original_data, dict) and 'bundle' in original_data:
            if DEBUG:
                print >>sys.stderr, "*** BundleListItem.RefreshData: bundle changed:", original_data['key'], '#1+%s' % (len(original_data['bundle'])-1)
            
            bundle = original_data['bundle']
            self.bundle = bundle
            
            if DEBUG:
                print >>sys.stderr, "*** BundleListItem.RefreshData: calling ListItem.RefreshData() with head"
            ListItem.RefreshData(self, (infohash, item_data, bundle[0]))
                        
            if DEBUG:
                print >>sys.stderr, "*** BundleListItem.RefreshData: calling BundlePanel.SetHits()"
            
            self.bundlepanel.SetHits(bundle[1:])
            self.bundlepanel.UpdateHeader(original_data['bundle_general_description'], original_data['bundle_description'])
            self.Highlight(1)
            
            # Rewire parentOnMouse in case new controls were added
            for text in self.bundlepanel.texts:
                text.parentOnMouse = self.OnMouse
        
        else:
            self._RefreshDataNonBundle(data)
            
    def _RefreshDataNonBundle(self, data):
        infohash, item_data, original_data = data
        if DEBUG:
            print >>sys.stderr, "*** BundleListItem._RefreshDataNonBundle: single hit changed:", repr(item_data[0])
        
        if isinstance(original_data, dict):
            hit_to_update = None
            for hit in self.bundle:
                if hit['infohash'] == infohash:
                    hit_to_update = hit
                    break
            
            if hit_to_update:
                for k, v in original_data.iteritems():
                    hit_to_update[k] = v
            elif DEBUG:
                print >>sys.stderr, "*** BundleListItem._RefreshDataNonBundle: couldn't find hit in self.bundle!"
            
        elif DEBUG:
            print >>sys.stderr, "*** BundleListItem._RefreshDataNonBundle: data[2] != dict!"
        
        if infohash == self.bundle[0]['infohash']:
            if DEBUG:
                print >>sys.stderr, "*** BundleListItem._RefreshDataNonBundle: calling ListItem.RefreshData() with head"
            ListItem.RefreshData(self, data)
            
        else:
            self.bundlepanel.RefreshDataBundleList(infohash, original_data)
    
    def GetExpandedPanel(self):
        return self.expanded_panel

    def Expand(self, panel):
        # Similar to ListItem base class logic, except we insert the panel
        # to the vSizer at a specific index, instead of adding it to the end.
        if getattr(panel, 'SetCursor', False):
            panel.SetCursor(wx.StockCursor(wx.CURSOR_DEFAULT))
            #panel.SetFont(panel.GetDefaultAttributes().font)
        
        self.expanded_panel = panel
        self.ShowExpandedPanel()
    
    def Collapse(self):
        # Do most important part of base class logic first:
        self.expanded = False
        self.ShowSelected()
        
        # But grab the correct panel to return!
        panel_item = self.expanded_panel 
        self.expanded_panel = None
        self.expanded_panel_shown = False
        
        # Also collapse the bundlepanel
        self.bundlepanel.ChangeState(BundlePanel.COLLAPSED)
        return panel_item
    
    
    def OnClick(self, event):
        if not self.expanded or self.expanded_panel_shown:
            ListItem.OnClick(self, event)
        else:
            self.ShowExpandedPanel()
    
    def ShowExpandedPanel(self, show=True):
        panel = self.expanded_panel
        if panel is not None and show != self.expanded_panel_shown:
            if show:
                panel.Show()
                # Insert, instead of add:
                self.vSizer.Insert(1, panel, 0, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.BOTTOM, 3)
                
                if getattr(self, 'expandedState', False):
                    self.expandedState.SetBitmap(self.GetIcon(self.list_selected, 1))
                
                self.button.Hide()
                
                # Only keep 1 panel open at all times, so close panels in the bundlepanel, if any:
                self.bundlepanel.CollapseExpandedItem()
            else:
                panel.Hide()
                self.vSizer.Remove(panel)
                
                if getattr(self, 'expandedState', False):
                    self.expandedState.SetBitmap(self.GetIcon(self.list_selected, 0))
                
                self.button.Show()
                
            self.expanded_panel_shown = show
            self.Layout()
    
    def AddEvents(self, control):
        if isinstance(control, BundleStaticText):
            # BundleStaticTexts will handle their own events
            control.parentOnMouse = self.OnMouse
        elif not isinstance(control, wx.Button):
            control.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouse)
        else:
            control.Bind(wx.EVT_ENTER_WINDOW, self.OnMouse)
            control.Bind(wx.EVT_LEAVE_WINDOW, self.OnMouse)
        control.SetCursor(wx.StockCursor(wx.CURSOR_HAND))
        
        func = getattr(control, 'GetChildren', False)
        if func and not isinstance(control, BundleStaticText):
            for child in func():
                self.AddEvents(child)
                
    def BackgroundColor(self, color):
        ListItem.BackgroundColor(self, color)
        self.bundlepanel.SetBackgroundColour(color)

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
        # preload icons
        self.load_icons()
        self.parent_listitem = parent
        self.parent_list = parent_list
        
        wx.Panel.__init__(self, parent)
        
        self.hits = hits
        self.state = BundlePanel.COLLAPSED
        
        self.general_description = general_description
        self.description = description
        
        self.font_increment = font_increment
        self.vsizer = wx.BoxSizer(wx.VERTICAL)
        
        self.AddHeader()
        self.AddGrid()
        
        self.SetSizer(self.vsizer)
    
    def AddHeader(self):
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.header = wx.StaticText(self, -1, '')
        # Keep header font the same...
        # TODO: perhaps introduce two font_increment params in constructor?
        #font = self.header.GetFont()
        #font.SetPointSize(font.GetPointSize() + self.font_increment)
        #self.header.SetFont(font)
        
        self.info_icon = wx.StaticBitmap(self, -1, self.icons['info'])
        
        self.SetGeneralDescription(self.general_description)
        self.SetDescription(self.description)
        
        #sizer.Add(self.info_icon, 0)
        #sizer.Add(self.header, 0, wx.LEFT, 2)
        
        sizer.Add(self.header, 0, wx.RIGHT, 5)
        sizer.Add(self.info_icon, wx.TOP, 7)
        self.vsizer.Add(sizer, 0, wx.LEFT, 22)
    
    def UpdateHeader(self, general_description, description):
        self.general_description = general_description
        self.description = description
        self.SetGeneralDescription(general_description)
        self.SetDescription(description)
    
    def AddGrid(self):
        VGAP, HGAP = 0, 0
        self.grid = wx.FlexGridSizer(BUNDLE_NUM_ROWS, BUNDLE_NUM_COLS, VGAP, HGAP)
        self.grid.SetFlexibleDirection(wx.HORIZONTAL)
        self.grid.SetNonFlexibleGrowMode(wx.FLEX_GROWMODE_NONE)
        self.grid.SetMinSize((1,-1))
        
        for i in xrange(BUNDLE_NUM_ROWS):
            self.grid.AddGrowableRow(i)
        
        for j in xrange(BUNDLE_NUM_COLS):
            self.grid.AddGrowableCol(j)
        
        self.texts = []
        self.num_hits_displayed_in_grid = 0
        self.UpdateGrid()
        
        self.vsizer.Add(self.grid, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 30)
        self.grid_shown = True
    
    def UpdateGrid(self):
        N = BUNDLE_NUM_ROWS * BUNDLE_NUM_COLS
        too_large = len(self.hits) > N
        if too_large:
            remaining = len(self.hits) - N + 1
            to_display = self.hits[:N-1]
            num_texts_needed = N
        else:
            to_display = self.hits
            num_texts_needed = len(to_display)
        
        num_texts_available = len(self.texts)
        num_to_display = len(to_display)
        self.num_hits_displayed_in_grid = num_to_display
        
        # corner case: we need to recreate the last text if
        # it contains an icon but we don't need one, or vice versa
        if num_texts_available == N:
            has_icon = hasattr(self.texts[-1], 'icon')
            icon_needed = not too_large
            if has_icon != icon_needed:
                self.grid.Remove(self.texts.pop())
                num_texts_available -= 1
        
        # create more text controls if needed
        if num_texts_available < num_to_display:
            for _ in xrange(num_to_display - num_texts_available):
                new_text = LinkStaticText(self, '', icon = False, icon_type = 'tree', icon_align = wx.ALIGN_LEFT, font_increment = self.font_increment, font_colour = BUNDLE_FONT_COLOR)
                new_text.Bind(wx.EVT_LEFT_UP, self.OnBundleLinkClick)
                new_text.SetMinSize((1,-1))
                self.grid.Add(new_text, 0, wx.ALL | wx.EXPAND, 5)
                
                self.texts.append(new_text)
        # else get rid of the excess of controls
        else:
            for _ in xrange(num_texts_available - num_texts_needed):
                self.grid.Remove(self.texts.pop())
        
        
        for i, hit in enumerate(to_display):
            self.texts[i].SetLabel(hit['name'])
            self.texts[i].action = hit
        
        if too_large:
            caption = '(%s more...)' % remaining
            if hasattr(self.texts[-1], 'icon'):
                more_label = LinkStaticText(self, caption, icon = False, icon_align = wx.ALIGN_LEFT, font_increment = self.font_increment, font_colour = BUNDLE_FONT_COLOR)
                more_label.Bind(wx.EVT_LEFT_UP, self.OnMoreClick)

                self.grid.Add(more_label, 0, wx.ALL | wx.EXPAND, 5)
                self.texts.append(more_label)
            else:
                more_label = self.texts[-1]
                more_label.SetLabel(caption)
                
            more_label.action = None
    
    def ShowGrid(self, show=True):
        if self.grid_shown != show:
            if show:
                self.grid.ShowItems(True)
                self.vsizer.Add(self.grid, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 30)
            else:
                self.grid.ShowItems(False)
                self.vsizer.Detach(self.grid)
            
            self.grid_shown = show
    
    def UpdateList(self):
        if self.state != BundlePanel.COLLAPSED:
            self.ShowList()
    
    def ShowList(self, show=True):
        bundlelist = getattr(self, 'bundlelist', None)
        if bundlelist is None and show:
            bundlelist = BundleListView(parent = self)
            bundlelist.SetData(self.hits)
            
            self.vsizer.Add(bundlelist, 0, wx.EXPAND | wx.LEFT, 20)
        
        elif bundlelist is not None and not show:
            self.vsizer.Detach(bundlelist)
            bundlelist.Destroy()
            bundlelist = None
            
        self.bundlelist = bundlelist
        
    def OnChange(self, scrollToTop = False):
        self.Layout()
        self.parent_listitem.Layout()
        self.parent_list.OnChange(scrollToTop)
    
    def CollapseExpandedItem(self):
        if self.state != BundlePanel.COLLAPSED:
            cur_expanded = self.bundlelist.list.cur_expanded
            if cur_expanded is not None:
                cur_expanded.OnClick(None)
    
    def RefreshDataBundleList(self, key, data):
        bundlelist = getattr(self, 'bundlelist', None)
        if bundlelist is not None:
            bundlelist.RefreshData(key, data)
    
    def SetDescription(self, description):
        self.description = description
        self.header.SetToolTipString(description)
        self.info_icon.SetToolTipString(description)
    
    def SetGeneralDescription(self, general_description):
        if general_description:
            general_description = unicode(self.general_description)
        else:
            general_description = u'Similar'
        
        self.general_description = general_description
        self.header.SetLabel(u'%s items (%s):' % (general_description, len(self.hits)))
    
    def SetHits(self, hits):
        if self.hits != hits:
            self.hits = hits
            self.UpdateGrid()
            self.UpdateList()
            self.Layout()
    
    def ChangeState(self, new_state, doLayout=True):
        if self.state != new_state:
            if new_state == BundlePanel.COLLAPSED:
                self.ShowList(False)
                self.ShowGrid()
            
            else:
                if new_state == BundlePanel.PARTIAL and self.num_hits_displayed_in_grid == len(self.hits):
                    new_state = BundlePanel.FULL
                
                if new_state == BundlePanel.PARTIAL or new_state == BundlePanel.FULL:
                    self.ShowGrid(False)
                    if self.state == BundlePanel.COLLAPSED:
                        self.ShowList()
                        
                    if new_state == BundlePanel.FULL:
                        self.bundlelist.OnLoadAll()
            
            if DEBUG:
                statestr = lambda st: ['COLLAPSED', 'PARTIAL', 'FULL'][st]
                print >>sys.stderr, '*** BundlePanel.ChangeState: %s --> %s' % (statestr(self.state), statestr(new_state))
            
            self.state = new_state
    
    def ExpandAndScrollToHit(self, hit):
        id = hit['infohash']
        
        self.bundlelist.ExpandItem(id)
        self.ScrollToId(id)
        self.parent_listitem.ShowSelected()
        
    def ScrollToId(self, id):
        parent_listitem_dy = self.parent_listitem.GetPosition()[1]
        self_dy = self.GetPosition()[1]
        hit_item_dy = self.bundlelist.VerticalItemOffset(id)
        
        total_y = parent_listitem_dy + self_dy + hit_item_dy
        
        ppu = self.parent_list.GetScrollPixelsPerUnit()[1]
        sy = total_y / ppu
        
        if DEBUG:
            print >>sys.stderr, \
            '*SCROLL*: p_li self hit (total) / ppu, sy:  %s %s %s (%s) / %s, %s' \
            % (parent_listitem_dy, self_dy, hit_item_dy, total_y, ppu, sy)
            sizer_h = self.parent_list.vSizer.GetSize()[1]
            print >>sys.stderr, '*SCROLL* parent_list vertical scroll height:', sizer_h/ppu
            # ^ This line confirms that we sometimes want to scroll beyond the size of the
            #   vsizer. Apparently the vsizer's size hasn't changed when we want to scroll...
        
        # ...therefore we should delay the scroll:
        #wx.CallAfter(self.parent_list.Scroll, -1, sy)
        wx.CallLater(100, self.parent_list.Scroll, -1, sy)
    
    def OnBundleLinkClick(self, event):
        listitem = self.GetParent()
        
        if not listitem.expanded:
            # Make sure the listitem is marked as expanded
            listitem.Freeze()
            listitem.OnClick(event)
            
            # but hide the panel
            listitem.ShowExpandedPanel(False)
            listitem.Thaw()
        
        staticText = event.GetEventObject()
        action = getattr(staticText, 'action', None)
        if action is not None:
            # Reason for non-persistence (for now) is least-surprise.
            # If the user collapses a bundled listitem, the previously 
            # clicked item is still at the same location.
            self.hits.remove(action)
            self.hits.insert(0, action)
        
            self.ChangeState(BundlePanel.PARTIAL)
            self.ExpandAndScrollToHit(action)
        
        event.Skip()
            
    def OnMoreClick(self, event):
        self.ChangeState(BundlePanel.FULL)
        
        event.Skip()
    
    def SetSelectedBundleLink(self, control=None):
        for bundletext in self.texts:
            bundletext.ShowSelected(bundletext == control)
            
    def SetBackgroundColour(self, colour):
        wx.Panel.SetBackgroundColour(self, colour)
        
        if self.grid_shown:
            for sizeritem in self.grid.GetChildren():
                if sizeritem.IsWindow():
                    child = sizeritem.GetWindow()
                    if isinstance(child, wx.Panel):
                        child.SetBackgroundColour(colour)
    
class BundleStaticText(wx.Panel):
    def __init__(self, bundlepanel, text, font_increment = 0, icon = True):
        wx.Panel.__init__(self, bundlepanel, style = wx.NO_BORDER)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.text = wx.StaticText(self, -1, text)
        font = self.text.GetFont()
        font.SetPointSize(font.GetPointSize() + font_increment)
        self.text.SetFont(font)
        #self.text.SetBackgroundColour(bundlepanel.GetBackgroundColour())
        self.text.SetForegroundColour(BUNDLE_FONT_COLOR)
        self.text.SetCursor(wx.StockCursor(wx.CURSOR_HAND))
        
        if icon:
            bitmap = self.__createBitmap()
            self.icon = wx.StaticBitmap(self, bitmap = bitmap)
            self.icon.SetCursor(wx.StockCursor(wx.CURSOR_HAND))
        
            hSizer.Add(self.icon, 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 3)
        
        hSizer.Add(self.text, 0, wx.ALIGN_CENTER_VERTICAL)
        
        self.SetSizer(hSizer)
        self.SetCursor(wx.StockCursor(wx.CURSOR_HAND))
        
        self.selected = False
        self.bundlepanel = bundlepanel
        
        self.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouse)
        
    def __createBitmap(self):
        color = (255,0,0) # apparently it doesn't matter which color is used?
        return NativeIcon.getInstance().getBitmap(self.GetParent(), 'tree', color, state=0)
        
    def SetToolTipString(self, tip):
        wx.Panel.SetToolTipString(self, tip)
        self.text.SetToolTipString(tip)
        if getattr(self, 'icon', False):
            self.icon.SetToolTipString(tip)
        
    def SetLabel(self, text):
        self.text.SetLabel(text)
    
    def GetLabel(self):
        return self.text.GetLabel()
    
    def Bind(self, event, handler, source=None, id=-1, id2=-1):
        wx.Panel.Bind(self, event, handler, source, id, id2)
        
        def modified_handler(actual_event, handler=handler):
            actual_event.SetEventObject(self)
            handler(actual_event)
        
        self.text.Bind(event, modified_handler, source, id, id2)
        if getattr(self, 'icon', False):
            self.icon.Bind(event, modified_handler, source, id, id2)
    
    def ShowSelected(self, selected=True):
        font = self.text.GetFont()
        if selected:
            #Niels: Underline not working on Linux, using italic instead
            if sys.platform == 'linux2': 
                font.SetStyle(wx.ITALIC)
            else:
                font.SetUnderlined(True)
        else:
            if sys.platform == 'linux2':
                font.SetStyle(wx.NORMAL)
            else:
                font.SetUnderlined(False)
        
        self.text.SetFont(font)
        self.selected = selected
    
    def OnMouse(self, event):
        selected = getattr(self, 'selected', False)
        
        if event.Entering() or event.Moving():
            if not selected:
                self.bundlepanel.SetSelectedBundleLink(self)
        
        elif event.Leaving():
            if selected:
                self.ShowSelected(False)
        
        elif event.LeftUp():
            self.OnClick(event)
        
        parentOnMouse = getattr(self, 'parentOnMouse', False)
        if parentOnMouse and not event.LeftUp:
            parentOnMouse(event)
        else:
            event.Skip() #Allow for windows button hovering
    
    def OnClick(self, event):
        self.bundlepanel.OnBundleLinkClick(event, action=self.action)
    
class BundleListView(GenericSearchList):
    
    def __init__(self, parent = None):
        columns = [{'name':'Name', 'width': wx.LIST_AUTOSIZE, 'sortAsc': True, 'icon': 'tree'}, \
                   {'name':'Size', 'width': '8em', 'style': wx.ALIGN_RIGHT, 'fmt': self.format_size, 'sizeCol': True}, \
                   #{'name':'Seeders', 'width': wx.LIST_AUTOSIZE_USEHEADER, 'style': wx.ALIGN_RIGHT, 'fmt': self.format}, \
                   #{'name':'Leechers', 'width': wx.LIST_AUTOSIZE_USEHEADER, 'style': wx.ALIGN_RIGHT, 'fmt': self.format}, \
                   {'type':'method', 'width': wx.LIST_AUTOSIZE_USEHEADER, 'method': self.CreateRatio, 'name':'Popularity'}, \
                   {'type':'method', 'width': -1, 'method': self.CreateDownloadButton}]
        
        GenericSearchList.__init__(self, columns, LIST_GREY, [7,7], True, parent=parent)
    
    def CreateHeader(self):
        # Normally, the column-widths are fixed during this phase
        # Since we aren't creating a header, we have to do this manually...
        # columns = self.columns
        # for i in xrange(len(columns)):
        #     if isinstance(columns[i]['width'], basestring) and columns[i]['width'].endswith('em'):
        #         test_string = 'T' * int(columns[i]['width'][:-2])
        #         columns[i]['width'] = self.GetTextExtent(test_string)[0] + 6
        
        # Or perhaps easier... just create the simplest header, but don't return it:
        header = ListHeader(self, self.columns)
        header.Destroy()
        
    def CreateFooter(self):
        pass 
    
    def CreateList(self):
        return ExpandableFixedListBody(self, self, self.columns, self.spacers[0], self.spacers[1], self.singleSelect, self.showChange, list_item_max = BUNDLE_LIST_MAX_SIZE)
    
    def OnExpand(self, item):
        # Keep only one panel open at all times:
        bundlepanel = self.parent
        bundlepanel.parent_listitem.ShowExpandedPanel(False)
        
        return BundleTorrentDetails(item, item.original_data)
    
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
    
class BundleTorrentDetails(TorrentDetails):
    def __init__(self, parent, torrent, compact=True):
        TorrentDetails.__init__(self, parent, torrent, compact=True)
    
    def _showTorrent(self, torrent, information):
        TorrentDetails._showTorrent(self, torrent, information)
        self.buttonPanel.Hide()
        self.details.Layout()
    
    def ShowPanel(self, *args, **kwargs):
        pass
