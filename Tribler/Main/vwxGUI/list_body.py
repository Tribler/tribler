import wx
import wx.lib.scrolledpanel as scrolled

import sys
from threading import currentThread
from traceback import print_stack
from time import time
import re

from Tribler.Main.vwxGUI.tribler_topButton import NativeIcon, BetterText as StaticText

from __init__ import *
from wx._core import PyDeadObjectError

DEBUG = False

class ListItem(wx.Panel):
    def __init__(self, parent, parent_list, columns, data, original_data, leftSpacer = 0, rightSpacer = 0, showChange = False, list_selected = LIST_SELECTED):
        wx.Panel.__init__(self, parent)
         
        self.parent_list = parent_list
        self.columns = columns
        self.data = data
        self.original_data = original_data
         
        self.showChange = showChange
        self.list_selected = list_selected
        
        self.highlightTimer = None
        self.selected = False
        self.expanded = False
        self.SetBackgroundColour(LIST_DESELECTED)
        self.SetForegroundColour(parent_list.GetForegroundColour())
        self.SetFont(parent_list.GetFont())
         
        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
         
        self.AddComponents(leftSpacer, rightSpacer)
        
        self.vSizer.Add(self.hSizer, 0, wx.EXPAND)
        self.SetSizer(self.vSizer)
    
    def AddComponents(self, leftSpacer, rightSpacer):
        self.controls = []
        if leftSpacer > 0:
            self.hSizer.AddSpacer((leftSpacer, -1))
         
        for i in xrange(len(self.columns)):
            if self.columns[i].get('icon', False):
                if self.columns[i]['icon'] == 'checkbox' or self.columns[i]['icon'] == 'tree':
                    self.icontype = self.columns[i]['icon']
                    self.expandedState = wx.StaticBitmap(self, -1, self.GetIcon(LIST_DESELECTED, 0))
                    self.hSizer.Add(self.expandedState, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 3)
                else:
                    icon = self.columns[i]['icon'](self)
                    if icon:
                        icon = wx.StaticBitmap(self, -1, icon)
                        self.hSizer.Add(icon, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 3)
                
            if self.columns[i]['width'] == wx.LIST_AUTOSIZE:
                option = 1
                size = wx.DefaultSize
            else:
                option = 0
                size = (self.columns[i]['width'],-1)
                
            type = self.columns[i].get('type', 'label')
            if type == 'label':
                str_data = self.columns[i].get('fmt', unicode)(self.data[i])
                control = StaticText(self, style=self.columns[i].get('style',0)|wx.ST_NO_AUTORESIZE|wx.ST_DOTS_END, size=size)
                
                fontWeight = self.columns[i].get('fontWeight', wx.FONTWEIGHT_NORMAL)
                if fontWeight != wx.FONTWEIGHT_NORMAL:
                    font = control.GetFont()
                    font.SetWeight(fontWeight)
                    control.SetFont(font)
                
                #niels: wx magic prevents us from passing this string with the constructor, ampersands will not work
                control.SetLabel(str_data.replace('&', "&&"))
                
            elif type == 'method':
                control = self.columns[i]['method'](self, self)
            
            if control:
                self.controls.append(control)
                self.hSizer.Add(control, option, wx.RESERVE_SPACE_EVEN_IF_HIDDEN|wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.TOP|wx.BOTTOM, 3)
                
                if self.columns[i]['width'] == wx.LIST_AUTOSIZE:
                    control.SetMinSize((1,-1))
                
                elif self.columns[i]['width'] == LIST_AUTOSIZEHEADER:
                    self.columns[i]['width'] = control.GetSize()[0]
                    if self.parent_list.parent_list.header:
                        self.parent_list.parent_list.header.ResizeColumn(i, self.columns[i]['width'])  
            else:
                if self.columns[i]['width'] != LIST_AUTOSIZEHEADER:
                    self.hSizer.Add((self.columns[i]['width'], -1), 0, wx.LEFT, 3)    
        
        #always end with a spacer of size 3
        rightSpacer += 3
        self.hSizer.AddSpacer((rightSpacer, -1))
        self.hSizer.Layout()
        
        self.AddEvents(self)
    
    def AddEvents(self, control):
        if getattr(control, 'GetWindow', False): #convert sizeritems
            control = control.GetWindow() or control.GetSizer()
        
        if getattr(control, 'Bind', False):
            if not isinstance(control, wx.Button):
                control.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouse)
                control.SetCursor(wx.StockCursor(wx.CURSOR_HAND))
            else:
                control.Bind(wx.EVT_ENTER_WINDOW, self.OnMouse)
                control.Bind(wx.EVT_LEAVE_WINDOW, self.OnMouse)
        
        func = getattr(control, 'GetChildren', False)
        if func:
            for child in func():
                self.AddEvents(child)
          
    def GetIcon(self, background, state):
        return NativeIcon.getInstance().getBitmap(self, self.icontype, background, state)
        
    def RefreshData(self, data):
        if isinstance(data[2], dict): #update original_data
            for key in data[2].keys():
                self.original_data[key] = data[2][key]
        else:
            self.original_data = data[2]
        
        control_index = 0
        
        new_controls = False
        has_changed = False
        
        self.Freeze()
        for i in xrange(len(self.columns)):
            type = self.columns[i].get('type','label')
            if type == 'label':
                str_data = self.columns[i].get('fmt', unicode)(data[1][i])
                
                #niels: we need to escape ampersand to allow them to be visible
                str_data = str_data.replace('&', "&&")
                
                if str_data != self.controls[control_index].GetLabel():
                    self.controls[control_index].SetLabel(str_data)
                    has_changed = True
                control_index += 1
            
            elif type == 'method':
                if self.data[i] != data[1][i]:
                    control = self.columns[i]['method'](self, self)
                    if control:
                        if isinstance(control, wx.Panel):
                            control.SetBackgroundColour(self.GetBackgroundColour())
                        
                        cur_sizeritem_index = 0
                        for child in self.hSizer.GetChildren():
                            if child.GetWindow() == self.controls[control_index]:
                                break
                            else:
                                cur_sizeritem_index += 1
                        self.hSizer.Insert(cur_sizeritem_index, control, 0, wx.RESERVE_SPACE_EVEN_IF_HIDDEN|wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.TOP|wx.BOTTOM, 3)
                        
                        self.hSizer.Detach(self.controls[control_index])
                        self.controls[control_index].Hide()
                        self.controls[control_index].Destroy()
                        self.controls[control_index] = control
                        new_controls = True
                        has_changed = True
                        
                        self.AddEvents(control)
                control_index += 1
            
        if new_controls:
            self.hSizer.Layout()
        
        if self.showChange and has_changed:
            self.Highlight()
            
        elif new_controls:
            self.ShowSelected()
        
        self.Thaw()
        self.data = data[1]
        
    def Highlight(self, timeout = 3.0, revert = True):
        if self.IsShownOnScreen():
            self.BackgroundColor(LIST_HIGHTLIGHT)
            
            if revert:
                if self.highlightTimer == None:
                    self.highlightTimer = wx.CallLater(timeout * 1000, self.Revert)
                else:
                    self.highlightTimer.Restart(timeout * 1000)
            return True
        return False
            
    def Revert(self):
        try:
            self.ShowSelected()
            self.highlightTimer = None
            
        except PyDeadObjectError: #PyDeadError
            pass
         
    def ShowSelected(self):
        def IsSelected(control):
            if getattr(control, 'GetWindow', False): #convert sizeritems
                control = control.GetWindow()
                
            if getattr(control, 'selected', False): 
                return True
        
            if getattr(control, 'GetChildren', False): 
                children = control.GetChildren()
                for child in children:
                    if IsSelected(child):
                        return True
            return False
                    
        selected = self.expanded or IsSelected(self)
        if selected:
            self.BackgroundColor(self.list_selected)
        else:
            self.BackgroundColor(LIST_DESELECTED)
    
    def BackgroundColor(self, color):
        if self.GetBackgroundColour() != color:
            self.Freeze()
            
            self.SetBackgroundColour(color)
            for sizeritem in self.hSizer.GetChildren():
                if sizeritem.IsWindow():
                    child = sizeritem.GetWindow()
                    if isinstance(child, wx.Panel):
                        child.SetBackgroundColour(color)
            
            #If this item has a icon and it is not checked
            if getattr(self, 'expandedState', False):
                if self.expanded:
                    state = 1
                else:
                    state = 0
                self.expandedState.SetBitmap(self.GetIcon(color, state))
                self.expandedState.Refresh()
            
            #self.Refresh()
            self.Thaw()
    
    def Deselect(self):
        if self.GetBackgroundColour() == self.list_selected:
            def SetDeselected(control):
                if getattr(control, 'GetWindow', False): #convert sizeritems
                    control = control.GetWindow()
                
                control.selected = False
                if getattr(control, 'GetChildren', False): 
                    children = control.GetChildren()
                    for child in children:
                        SetDeselected(child)
            
            SetDeselected(self)
            
            if self.expanded:
                self.DoCollapse()
            else:
                self.ShowSelected()
    
    def GetColumn(self, column):
        return self.data[column]

    def OnMouse(self, event):
        if event.Entering():
            event.GetEventObject().selected = True
            self.ShowSelected()
            
        elif event.Leaving():
            event.GetEventObject().selected = False
            self.ShowSelected()
            
        elif event.LeftDown():
            event.listitem = self
            self.parent_list.lastMouseLeftDownEvent = event
        
        elif event.LeftUp():
            if getattr(self.parent_list.lastMouseLeftDownEvent, 'listitem', None) == self:
                self.OnClick(event)
            
        event.Skip() #Allow windows to paint button hover
        
    def OnClick(self, event = None):
        if not self.expanded:
            if self.parent_list.OnExpand(self):
                self.expanded = True
            
                if getattr(self, 'expandedState', False):
                    self.expandedState.SetBitmap(self.GetIcon(self.list_selected, 1))
        else:
            self.DoCollapse()
        
    def Expand(self, panel):
        if getattr(panel, 'SetCursor', False):
            panel.SetCursor(wx.StockCursor(wx.CURSOR_DEFAULT))
            #panel.SetFont(panel.GetDefaultAttributes().font)
        
        panel.Show()
        self.vSizer.Add(panel, 0, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.BOTTOM, 3)
        self.Layout()
        
    def GetExpandedPanel(self):
        if len(self.vSizer.GetChildren()) > 1:
            return self.vSizer.GetChildren()[1].GetWindow()

    def DoCollapse(self):
        self.parent_list.OnCollapse(self)
        self.expanded = False
            
        if getattr(self, 'expandedState', False):
            self.expandedState.SetBitmap(self.GetIcon(self.list_selected, 0))

    def Collapse(self):
        self.expanded = False
        self.ShowSelected()
        
        if len(self.vSizer.GetChildren()) > 1:
            item = self.vSizer.GetItem(1).GetWindow()
            item.Hide()
            
            self.vSizer.Detach(1)
            self.vSizer.Layout()
            return item
        
    def OnEventSize(self, width):
        pass
        
    def __str__( self ):
        return "ListItem" + " ".join(map(str, self.data))
        
class AbstractListBody():
    def __init__(self, parent, columns, leftSpacer = 0, rightSpacer = 0, singleExpanded = False, showChange = False, list_item_max = None, hasFilter = True):
        self.columns = columns
        self.leftSpacer = leftSpacer
        self.rightSpacer = rightSpacer
        self.parent_list = parent
        self.singleExpanded = singleExpanded
        self.showChange = showChange
        self.list_selected = LIST_SELECTED
        if not list_item_max:
            list_item_max = LIST_ITEM_MAX_SIZE
        self.list_item_max = list_item_max
        self.hasFilter = hasFilter
        
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.listpanel = wx.Panel(self)
        
        #vertical sizer containing all items
        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        self.listpanel.SetSizer(self.vSizer)
        hSizer.Add(self.listpanel, 1)
        self.SetSizer(hSizer)
    
        #messagePanel text
        self.messagePanel = wx.Panel(self.listpanel)
        self.messagePanel.SetBackgroundColour(wx.WHITE)
        self.messagePanel.Show(False)
        messageVSizer = wx.BoxSizer(wx.VERTICAL)
        
        self.messageText = StaticText(self.messagePanel)
        self.loadNext = wx.Button(self.messagePanel)
        self.loadNext.Bind(wx.EVT_BUTTON, self.OnLoadMore)
        self.loadNext.Hide()
        
        messageVSizer.Add(self.messageText)
        messageVSizer.Add(self.loadNext, 0, wx.ALIGN_CENTER)
        
        messageSizer = wx.BoxSizer(wx.HORIZONTAL)
        messageSizer.AddStretchSpacer()
        messageSizer.Add(messageVSizer)
        messageSizer.AddStretchSpacer()
        self.messagePanel.SetSizer(messageSizer)
        
        #vertical scrollrate
        self.rate = None
        
        #states
        self.cur_expanded = None
        
        #quick filter
        self.filter = ''
        self.sizefiler = None
        self.filtercolumn = 0
        self.filtersizecolumn = -1
        for i in xrange(len(self.columns)):
            if self.columns[i].get('sizeCol', False):
                self.filtersizecolumn = i
                break
            
        #sorting
        self.sortcolumn = None
        
        #queue lists
        self.done = True
        self.lastData = 0
        self.dataTimer = None
        self.data = None
        self.raw_data = None
        self.items = {}
        
        # Allow list-items to store the most recent mouse left-down events:
        self.lastMouseLeftDownEvent = None
        self.curWidth = -1
        self.Bind(wx.EVT_SIZE, self.OnEventSize)
    
    def SetBackgroundColour(self, colour):
        wx.Panel.SetBackgroundColour(self, wx.WHITE)
        self.listpanel.SetBackgroundColour(colour)
    
    def SetStyle(self, font = None, foregroundcolour = None, list_selected = LIST_SELECTED):
        if font:
            self.SetFont(font)
        if foregroundcolour:
            self.SetForegroundColour(foregroundcolour)

        self.list_selected = list_selected
        
    def OnSort(self, column, reverse):
        self.Scroll(-1, 0)
        
        #Niels: translating between -1 and None conventions
        if column == -1:
            column = None
            
        self.sortcolumn = column
        self.sortreverse = reverse
        
        if self.data:
            if self.sortcolumn >= 0:
                self.Freeze()
                
                self.DoSort()
                
                self.vSizer.ShowItems(False)
                self.vSizer.Clear()
                self.CreateItems()
            
                self.Thaw()
            else:
                self.SetData()
                        
    def DoSort(self):
        def sortby(b, a):
            if a[0] in self.items:
                a = self.items[a[0]].data[self.sortcolumn]
            else:
                a = a[1][self.sortcolumn]
                
            if b[0] in self.items:
                b = self.items[b[0]].data[self.sortcolumn]
            else:
                b = b[1][self.sortcolumn] 
            
            return cmp(a, b)
        
        if self.sortcolumn != None:
            self.data = sorted(self.data, cmp = sortby, reverse=self.sortreverse)
    
    def FilterItems(self, keyword, column = 0):
        if __debug__ and currentThread().getName() != "MainThread":
            print  >> sys.stderr,"ListBody: FilterItems thread",currentThread().getName(),"is NOT MainThread"
            print_stack()
        
        new_filter = keyword.lower().strip()
        if new_filter != self.filter or column != self.filtercolumn:
            self.sizefiler = None
            if self.filtersizecolumn > -1 and new_filter.find("size=") > -1:
                try:
                    minSize = 0
                    maxSize = sys.maxint
                    
                    start = new_filter.find("size=") + 5
                    end = new_filter.find(" ", start)
                    if end == -1:
                        end = len(new_filter)
                        
                    sizeStr = new_filter[start:end]
                    if sizeStr.find(":") > -1:
                        sizes = sizeStr.split(":")
                        if sizes[0] != '':
                            minSize = int(sizes[0])
                        if sizes[1] != '':
                            maxSize = int(sizes[1])
                    else:
                        minSize = maxSize = int(sizeStr)
                        
                    self.sizefiler = [minSize, maxSize]
                    new_filter = new_filter[:start - 5] + new_filter[end:]
                except:
                    pass
                
            self.filter = new_filter.strip()
            self.filtercolumn = column
            try:
                re.compile(self.filter)
            except: #regex incorrect
                self.filter = ''
                return False
            
            finally:
                self.Scroll(-1, 0)
                self.SetData()
        return True
        
    def MatchFilter(self, item):
        if self.sizefiler:
            size = int(item[1][self.filtersizecolumn]/1048576.0)
            if size < self.sizefiler[0] or size > self.sizefiler[1]:
                return False
        return re.search(self.filter, item[1][self.filtercolumn].lower())
    
    def __GetFilterMessage(self):
        if self.filter != '':
            message = 'Only showing items matching "%s"'%self.filter
        elif self.sizefiler:
            message = 'Only showing items'
        else:
            message = ''
            
        if self.sizefiler:
            if self.sizefiler[0] == self.sizefiler[1]:
                message += " equal to %d MB in size."%self.sizefiler[0]
            elif self.sizefiler[0] == 0:
                message += " smaller than %d MB in size."%self.sizefiler[1]
            elif self.sizefiler[1] == sys.maxint:
                message += " larger than %d MB in size"%self.sizefiler[0]
            else:
                message += " between %d and %d MB in size."%(self.sizefiler[0], self.sizefiler[1])
        return message
    
    def OnExpand(self, item, raise_event = False):
        self.Freeze()
        
        if self.singleExpanded:
            if self.cur_expanded:
                self.OnCollapse(self.cur_expanded, False)
        
        panel = self.parent_list.OnExpand(item)
        if panel and not isinstance(panel, bool):
            item.Expand(panel)
            self.OnChange()
            
            #Niels: Windows 7 needs this refresh otherwise it will show some paint errors
            self.Refresh()
            
        self.cur_expanded = item
        self.Thaw()
        return panel
    
    def OnCollapse(self, item = None, onchange = True):
        self.Freeze()
        
        if not item:
            item = self.cur_expanded
        
        if item:
            panel = item.Collapse()
            self.parent_list.OnCollapse(item, panel)
            self.cur_expanded = None
        
        if onchange:
            self.OnChange()
            
            #Niels: Windows 7 needs this refresh otherwise it will show some paint errors
            self.Refresh()
            
        self.Thaw()
        
    def OnChange(self, scrollToTop = False):
        self.Freeze()
        
        self.vSizer.Layout()
        self.listpanel.Layout()
        self.Layout()
        
        #Determine scrollrate
        if self.rate is None:
            nritems = len(self.vSizer.GetChildren()) / 2
            if nritems > 1:
                height = self.vSizer.GetSize()[1]
                self.rate = height / nritems
                
                self.SetupScrolling(scrollToTop = scrollToTop, rate_y = self.rate)
            else:
                self.SetupScrolling(scrollToTop = scrollToTop)
        else:
            self.SetupScrolling(scrollToTop = scrollToTop, rate_y = self.rate)
            
        self.Thaw()
    
    def Reset(self):
        if DEBUG:
            print >> sys.stderr, "ListBody: reset"
            
        self.Freeze()
        
        self.filter = ''
        self.sizefiler = None
        self.filtercolumn = 0
        self.sortcolumn = None
        self.rate = None
        
        self.vSizer.ShowItems(False)
        self.vSizer.Clear()
        for key in self.items.keys():
            self.items[key].Destroy()
            
        self.items = {}
        self.data = None
        self.lastData = 0
        self.raw_data = None
        self.OnChange()
        self.Thaw()
    
    def IsEmpty(self):
        return len(self.items) == 0
    
    def InList(self, key):
        return key in self.items

    def ScrollToEnd(self, scroll_to_end):
        if scroll_to_end:
            self.Scroll(-1, self.vSizer.GetSize()[1])
        else:
            self.Scroll(-1, 0)
    
    def ShowMessage(self, message):
        if not self.messagePanel.IsShown():
            self.Freeze()
            
            self.messageText.SetLabel(message)
            self.loadNext.Hide()
            self.vSizer.ShowItems(False)
            self.vSizer.Clear()
    
            self.vSizer.Add(self.messagePanel, 0, wx.EXPAND|wx.BOTTOM, 1)
            self.messagePanel.Layout()
            self.messagePanel.Show()
            
            self.OnChange()
            self.Thaw()
        else:
            self.messageText.SetLabel(message)
            self.messagePanel.Layout()
    
    def ShowLoading(self):
        self.ShowMessage('Loading, please wait.')
        #Try to yield, allows us to show loading text
        try:
            wx.Yield()
        except:
            pass
    
    def RefreshData(self, key, data):
        if key in self.items:
            if DEBUG:
                print >> sys.stderr, "ListBody: refresh item", self.items[key]
            self.items[key].RefreshData(data)
            
            #forward update to expandedPanel
            panel = self.items[key].GetExpandedPanel()
            if panel and getattr(panel, 'RefreshData', False):
                if DEBUG:
                    print >> sys.stderr, "ListBody: refresh item (Calling expandedPanel refreshdata)", self.items[key]
                
                panel.RefreshData(data)
    
    def SetData(self, data = None):
        if DEBUG:
            print >> sys.stderr, "ListBody: new data", time()
        
        if data == None:
            data = self.raw_data
        else:
            self.raw_data = data
        
        def doSetData():
            self.lastData = time()
            self.dataTimer = None
            
            self.__SetData()
        
        diff = time() - (LIST_RATE_LIMIT + self.lastData)
        if diff >= 0:
            doSetData()
        else:
            call_in = -diff * 1000
            if self.dataTimer == None:
                self.dataTimer = wx.CallLater(call_in, doSetData) 
            else:
                self.dataTimer.Restart(call_in)
        
        if data:
            #apply quickfilter
            if self.filter != '' or self.sizefiler:
                data = filter(self.MatchFilter, data)
            
            #return filtered nr_items after quickfilter is applied
            return len(data)
        
    def __SetData(self):
        if DEBUG:
            print >> sys.stderr, "ListBody: __SetData", time()
        
        if __debug__ and currentThread().getName() != "MainThread":
            print  >> sys.stderr,"ListBody: __SetData thread",currentThread().getName(),"is NOT MAIN THREAD"
            print_stack()
        
        self.Freeze()
        
        message = ''
        
        #apply quickfilter
        if self.filter != '' or self.sizefiler:
            data = filter(self.MatchFilter, self.raw_data)
            self.parent_list.SetFilteredResults(len(data))

            if len(data) == 0:
                message = "0" + self.__GetFilterMessage()[12:]
        else:
            self.parent_list.SetFilteredResults(None)
            data = self.raw_data
            
        if not data:
            data = []
        
        self.vSizer.ShowItems(False)
        self.vSizer.Clear()
        if len(self.items) == 0:
            #new data
            if len(data) > LIST_ITEM_BATCH_SIZE:
                self.ShowLoading()
            self.highlightSet = set()
        else:
            cur_keys = set([curdata[0] for curdata in self.data[:self.list_item_max]])
            self.highlightSet = set([curdata[0] for curdata in data[:self.list_item_max] if curdata[0] not in cur_keys])

        self.data = data
        self.DoSort()
        self.done = False
        
        if len(data) > 0:
            self.CreateItems(nr_items_to_create = 3 * LIST_ITEM_BATCH_SIZE)
            
            #Try to yield
            try:
                wx.Yield()
            except:
                pass
            
        elif message != '':
            self.ShowMessage(message)
        
        if self.done:
            self.Unbind(wx.EVT_IDLE) #unbinding unnecessary event handler seems to improve visual performance
        else:
            self.Bind(wx.EVT_IDLE, self.OnIdle)
        
        self.Thaw()
        
    def OnIdle(self, event):
        if not self.done and self.data:
            self.CreateItems()
            
            #idle event also paints search animation, use request more to show this update
            event.RequestMore(not self.done)
            if self.done:
                self.Unbind(wx.EVT_IDLE)

    def OnLoadMore(self, event):
        self.loadNext.Disable()
        wx.CallAfter(self.CreateItems, LIST_ITEM_MAX_SIZE, sys.maxint)
        
    def OnLoadAll(self):
        self.loadNext.Disable()
        wx.CallAfter(self.CreateItems, sys.maxint, sys.maxint)

    def CreateItems(self, nr_items_to_create = LIST_ITEM_BATCH_SIZE, nr_items_to_add = None):
        if not nr_items_to_add:
            nr_items_to_add = self.list_item_max
        
        if DEBUG:
            print >> sys.stderr, "ListBody: Creating items", time()
        
        initial_nr_items_to_add = nr_items_to_add    
        done = True
        t1 = time()

        self.Freeze()
        
        #Check if we need to clear vSizer
        self.messagePanel.Show(False)
        self.loadNext.Show(False)
        self.vSizer.Remove(self.messagePanel)
        
        revertList = []
        
        message = self.__GetFilterMessage()
        #Add created/cached items
        for curdata in self.data:
            if len(curdata) > 3:
                key, item_data, original_data, create_method = curdata
            else:
                key, item_data, original_data = curdata
                create_method = ListItem
            
            if nr_items_to_add > 0 and nr_items_to_create > 0:
                if key not in self.items:
                    self.items[key] = create_method(self.listpanel, self, self.columns, item_data, original_data, self.leftSpacer, self.rightSpacer, showChange = self.showChange, list_selected=self.list_selected)
                    nr_items_to_create -= 1
                
                item = self.items[key]
                sizer = self.vSizer.GetItem(item)
                if not sizer:
                    self.vSizer.Add(item, 0, wx.EXPAND|wx.BOTTOM, 1)
                    item.Show()
                    
                    if key in self.highlightSet:
                        self.highlightSet.remove(key)
                        
                        if item.Highlight(revert = False):
                            revertList.append(key)
                                            
                nr_items_to_add -= 1
            else:
                done = nr_items_to_add == 0 or initial_nr_items_to_add == sys.maxint

                if done:
                    if message != '':
                        message = 'Only showing the first %d of %d'%(len(self.vSizer.GetChildren()), len(self.data)) + message[12:] + '\nFurther specify keywords to reduce the number of items, or click the button below.'
                    else:
                        message = 'Only showing the first %d of %d items in this list.'%(len(self.vSizer.GetChildren()), len(self.data))
                        if self.hasFilter:
                            message +='\nSearch within results to reduce the number of items, or click the button below.'
                        
                    remainingItems = min(LIST_ITEM_MAX_SIZE, len(self.data) - len(self.vSizer.GetChildren()))
                    self.loadNext.SetLabel("Show next %d items"%remainingItems)
                    self.loadNext.Enable()
                    self.loadNext.Show()
                break
       
        if message != '':
            self.messageText.SetLabel(message)
            
            self.vSizer.Add(self.messagePanel, 0, wx.EXPAND|wx.BOTTOM, 1)
            self.messagePanel.Layout()
            self.messagePanel.Show()
            
        self.OnChange()
        self.Thaw()
        
        if len(revertList) > 0:
            wx.CallLater(1000, self.Revert, revertList)
        
        self.done = done
        if DEBUG:
            print >> sys.stderr, "List created", len(self.vSizer.GetChildren()),"rows of", len(self.data),"took", time() - t1, "done:", self.done
        
    def GetItem(self, key):
        return self.items[key]
       
    def RemoveItem(self, remove):
        for key, item in self.items.iteritems():
            if item == remove:
                self.items.pop(key)
                
                self.vSizer.Detach(item)
                item.Destroy()
                
                self.OnChange()
                break
            
    def GetExpandedItem(self):
        return self.cur_expanded
    
    def GetExpandedItems(self):
        return [(key, item) for key, item in self.items.iteritems() if item.expanded]
    
    def Select(self, key, raise_event = True):
        self.DeselectAll()
        
        if key in self.items:
            if raise_event:
                self.items[key].OnClick(None)
            else:
                self.items[key].expanded = True
                self.cur_expanded = self.items[key]
                
            self.items[key].ShowSelected()
    
    def DeselectAll(self):
        for _, item in self.items.iteritems():
            item.Deselect()
            
    def Revert(self, revertList):
        for key in revertList:
            if key in self.items:
                self.items[key].Revert()
            
    def OnEventSize(self, event):
        width = self.GetSize()[0]
        if width != self.curWidth:
            doOnChange = False
        
            self.Freeze()
            self.curWidth = width
            
            for item in self.items.itervalues():
                if item.OnEventSize(width):
                    doOnChange = True

            if doOnChange:
                self.OnChange()
            
            self.Thaw()
        event.Skip()
 
class ListBody(AbstractListBody, scrolled.ScrolledPanel):
    def __init__(self, parent, parent_list, columns, leftSpacer = 0, rightSpacer = 0, singleExpanded = False, showChange = False, list_item_max = LIST_ITEM_MAX_SIZE):
        scrolled.ScrolledPanel.__init__(self, parent)
        AbstractListBody.__init__(self, parent_list, columns, leftSpacer, rightSpacer, singleExpanded, showChange)
        
        homeId = wx.NewId()
        endId = wx.NewId()
        self.Bind(wx.EVT_MENU, lambda event: self.ScrollToEnd(False), id = homeId)
        self.Bind(wx.EVT_MENU, lambda event: self.ScrollToEnd(True), id = endId)
        
        accelerators = [(wx.ACCEL_NORMAL, wx.WXK_HOME, homeId)]
        accelerators.append((wx.ACCEL_NORMAL, wx.WXK_END, endId))
        self.SetAcceleratorTable(wx.AcceleratorTable(accelerators))
        
        self.SetupScrolling()
                
    def OnChildFocus(self, event):
        event.Skip()
    
class FixedListBody(wx.Panel, AbstractListBody):
    def __init__(self, parent, parent_list, columns, leftSpacer = 0, rightSpacer = 0, singleExpanded = False, showChange = False, list_item_max = LIST_ITEM_MAX_SIZE):
        wx.Panel.__init__(self, parent)
        AbstractListBody.__init__(self, parent_list, columns, leftSpacer, rightSpacer, singleExpanded, showChange, list_item_max = list_item_max, hasFilter = False)
    
    def Scroll(self, x, y):
        pass
    def SetupScrolling(self, scroll_x=True, scroll_y=True, rate_x=20, rate_y=20, scrollToTop=True):
        pass
    def GetScrollPixelsPerUnit(self):
        return [0,0]
 
