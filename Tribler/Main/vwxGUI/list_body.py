import wx
import wx.lib.scrolledpanel as scrolled

from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue

import sys
import time
import re

from __init__ import *

DEBUG = False

class ListIcon:
    __single = None
    def __init__(self):
        if ListIcon.__single:
            raise RuntimeError, "ListIcon is singleton"
        ListIcon.__single = self
        self.icons = {}
        
    def getInstance(*args, **kw):
        if ListIcon.__single is None:
            ListIcon(*args, **kw)
        return ListIcon.__single
    getInstance = staticmethod(getInstance)
    
    def getBitmap(self, parent, type, background, state):
        icons = self.icons.setdefault(type, {}).setdefault(background, {})
        if state not in icons:
            icons[state] = self.__createBitmap(parent, background, type, state)
        
        return icons[state]
    
    def __createBitmap(self, parent, background, type, state):
        if state == 1:
            if type == 'tree':
                state = wx.CONTROL_EXPANDED
            else:
                state = wx.CONTROL_CHECKED
        
        #There are some strange bugs in RendererNative, the alignment is incorrect of the drawn images
        #Thus we create a larger bmp, allowing for borders
        bmp = wx.EmptyBitmap(24,24) 
        dc = wx.MemoryDC(bmp)
        dc.SetBackground(wx.Brush(background))
        dc.Clear()
        
        #max size is 16x16, using 4px as a border
        if type == 'checkbox':
            wx.RendererNative.Get().DrawCheckBox(parent, dc, (4, 4, 16, 16), state)
        elif type == 'tree':
            wx.RendererNative.Get().DrawTreeItemButton(parent, dc, (4, 4, 16, 16), state)
        dc.SelectObject(wx.NullBitmap)
        
        #determine actual size of drawn icon, and return this subbitmap
        bb = wx.RegionFromBitmapColour(bmp, background).GetBox()
        return bmp.GetSubBitmap(bb)

class ListItem(wx.Panel):
    def __init__(self, parent, parent_list, columns, data, original_data, leftSpacer = 0, rightSpacer = 0, showChange = False):
        wx.Panel.__init__(self, parent)
         
        self.parent_list = parent_list
        self.columns = columns
        self.data = data
        self.original_data = original_data
         
        self.showChange = showChange
        
        self.taskserver = None
        self.selected = False
        self.expanded = False
        self.SetBackgroundColour(LIST_DESELECTED)
         
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
                    self.hSizer.Add(self.expandedState, 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 3)
                else:
                    icon = self.columns[i]['icon'](self)
                    if icon:
                        icon = wx.StaticBitmap(self, -1, icon)
                        self.hSizer.Add(icon, 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 3)
                        
            type = self.columns[i].get('type','label')
            if type == 'label':
                str_data = self.columns[i].get('fmt', unicode)(self.data[i])
            
                if self.columns[i]['width'] == wx.LIST_AUTOSIZE:
                    option = 1
                    size = wx.DefaultSize
                else:
                    option = 0
                    size = (self.columns[i]['width'],-1)
                
                label = wx.StaticText(self, -1, str_data, style=self.columns[i].get('style',0)|wx.ST_NO_AUTORESIZE|wx.ST_DOTS_END, size=size)
                self.controls.append(label)
                
                self.hSizer.Add(label, option, wx.RESERVE_SPACE_EVEN_IF_HIDDEN|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 3)
                if self.columns[i]['width'] == wx.LIST_AUTOSIZE:
                    label.SetMinSize((1,-1))
                     
            elif type == 'method':
                control = self.columns[i]['method'](self, self)
                if control:
                    self.hSizer.Add(control, 0, wx.RESERVE_SPACE_EVEN_IF_HIDDEN|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 3)
                    self.controls.append(control)
                    
                    if self.columns[i]['width'] == -1:
                        self.columns[i]['width'] = control.GetSize()[0]
                        self.parent_list.parent_list.header.ResizeColumn(i, self.columns[i]['width'])
                else:
                    if self.columns[i]['width'] != -1:
                        self.hSizer.Add((self.columns[i]['width'], -1), 0, wx.LEFT|wx.RIGHT, 3)
        
        if rightSpacer > 0:
            self.hSizer.AddSpacer((rightSpacer, -1))
        self.hSizer.Layout()
        
        self.AddEvents(self)
    
    def AddEvents(self, control):
        control.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouse)
        control.SetCursor(wx.StockCursor(wx.CURSOR_HAND))
        
        func = getattr(control, 'GetChildren', False)
        if func:
            for child in func():
                self.AddEvents(child)
      
    def GetIcon(self, background, state):
        return ListIcon.getInstance().getBitmap(self, self.icontype, background, state)
        
    def RefreshData(self, data):
        if isinstance(data[2], dict): #update original_data
            for key in data[2].keys():
                self.original_data[key] = data[2][key]
        else:
            self.original_data = data[2]
        
        control_index = 0
        
        new_controls = False
        has_changed = False
        
        for i in xrange(len(self.columns)):
            type = self.columns[i].get('type','label')
            if type == 'label':
                str_data = self.columns[i].get('fmt', unicode)(data[1][i])
                
                if str_data != self.controls[control_index].GetLabel():
                    self.controls[control_index].SetLabel(str_data)
                    self.controls[control_index].Refresh()
                    
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
                        self.hSizer.Insert(cur_sizeritem_index, control, 0, wx.RESERVE_SPACE_EVEN_IF_HIDDEN|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 3)
                        
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
            
        self.data = data[1]
        
    def Highlight(self, timeout = 3.0):
        def removeHighlight():
            try:
                self.ShowSelected()
            except: #PyDeadError
                pass
        
        if self.IsShownOnScreen():
            if self.taskserver == None:
                self.taskserver = GUITaskQueue.getInstance()
            
            self.taskserver.add_task(lambda:wx.CallAfter(removeHighlight), timeout, self)
            self.BackgroundColor(LIST_HIGHTLIGHT)
         
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
            self.BackgroundColor(LIST_SELECTED)
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
            if getattr(self, 'expandedState', False) and not self.expanded:
                self.expandedState.SetBitmap(self.GetIcon(color, 0))
            
            self.Refresh()
            self.Thaw()
    
    def Deselect(self):
        if self.selected or self.expanded:
            self.selected = False
            self.expanded = False
            self.ShowSelected()
    
    def GetColumn(self, column):
        return self.data[column]

    def OnMouse(self, event):
        if event.Entering():
            event.GetEventObject().selected = True
            self.selected = True
            self.ShowSelected()
            
        elif event.Leaving():
            event.GetEventObject().selected = False
            self.selected = False
            self.ShowSelected()
            
        elif event.LeftUp():
            self.OnClick(event)
            
        event.Skip() #Allow windows to paint button hover
        
    def OnClick(self, event):
        if not self.expanded:
            if self.parent_list.OnExpand(self):
                self.expanded = True
            
                if getattr(self, 'expandedState', False):
                    self.expandedState.SetBitmap(self.GetIcon(LIST_SELECTED, 1))
        else:
            self.parent_list.OnCollapse(self)
            self.expanded = False
            
            if getattr(self, 'expandedState', False):
                self.expandedState.SetBitmap(self.GetIcon(LIST_SELECTED, 0))
        
    def Expand(self, panel):
        if getattr(panel, 'SetCursor', False):
            panel.SetCursor(wx.StockCursor(wx.CURSOR_DEFAULT))
        
        panel.Show()
        self.vSizer.Add(panel, 0, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.BOTTOM, 3)
        self.Layout()
        
    def GetExpandedPanel(self):
        if len(self.vSizer.GetChildren()) > 1:
            return self.vSizer.GetChildren()[1].GetWindow()

    def Collapse(self):
        self.expanded = False
        self.ShowSelected()
        
        if len(self.vSizer.GetChildren()) > 1:
            item = self.vSizer.GetItem(1).GetWindow()
            item.Hide()
            
            self.vSizer.Detach(1)
            self.vSizer.Layout()
            return item
        
class AbstractListBody():
    def __init__(self, parent, background, columns, leftSpacer = 0, rightSpacer = 0, singleExpanded = False, showChange = False):
        self.columns = columns
        self.leftSpacer = leftSpacer
        self.rightSpacer = rightSpacer
        self.parent_list = parent
        self.singleExpanded = singleExpanded
        self.showChange = showChange
        
        self.SetBackgroundColour(wx.WHITE)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(hSizer)
        
        self.listpanel = wx.Panel(self)
        self.listpanel.SetBackgroundColour(background)
        
        #vertical sizer containing all items
        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        self.listpanel.SetSizer(self.vSizer)
        hSizer.Add(self.listpanel, 1)
    
        #messagePanel text
        self.messagePanel = wx.Panel(self.listpanel)
        self.messagePanel.SetBackgroundColour(wx.WHITE)
        messageVSizer = wx.BoxSizer(wx.VERTICAL)
        
        self.messageText = wx.StaticText(self.messagePanel)
        self.loadNext = wx.Button(self.messagePanel, -1, "Show next %d items"%LIST_ITEM_MAX_SIZE)
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
        self.filtercolumn = 0
        
        #queue lists
        self.done = True
        self.data = None
        self.raw_data = None
        self.items = {}
        self.Bind(wx.EVT_IDLE, self.OnIdle)
        
    def OnSort(self, column, reverse):
        self.Scroll(-1, 0)
        self.Freeze()
        
        def sortby(b, a):
            if a[0] in self.items:
                a = self.items[a[0]].data[column]
            else:
                a = a[1][column]
                
            if b[0] in self.items:
                b = self.items[b[0]].data[column]
            else:
                b = b[1][column] 
            
            return cmp(a, b)

        self.data = sorted(self.data, cmp = sortby, reverse=reverse)
        
        self.vSizer.ShowItems(False)
        self.vSizer.Clear()
        self.CreateItems()
        
        self.Thaw()
    
    def FilterItems(self, keyword, column = 0):
        new_filter = keyword.lower()
        if new_filter != self.filter or column != self.filtercolumn:
            self.filter = new_filter
            self.filtercolumn = column
            
            try:
                re.compile(self.filter)
            except: #regex incorrect
                self.filter = ''
                return False
            
            finally:
                self.Scroll(-1, 0)
                self.Freeze()
                    
                self.vSizer.ShowItems(False)
                self.vSizer.Clear()
                self.SetData()
                
                self.Thaw()
        return True
        
    def MatchFilter(self, item):
        return re.search(self.filter, item[1][self.filtercolumn].lower())
    
    def OnExpand(self, item, raise_event = False):
        self.Freeze()
        
        if self.singleExpanded:
            if self.cur_expanded:
                self.OnCollapse(self.cur_expanded, False)
        
        panel = self.parent_list.OnExpand(item)
        if panel and not isinstance(panel, bool):
            item.Expand(panel)
            self.OnChange()
            
        self.cur_expanded = item
        self.Thaw()
        return panel
    
    def OnCollapse(self, item, onchange = True):
        self.Freeze()
        
        panel = item.Collapse()
        self.parent_list.OnCollapse(item, panel)
        self.cur_expanded = None
        
        if onchange:
            self.OnChange()
        self.Thaw()
        
    def OnChange(self, scrollToTop = False):
        self.Layout()
        self.vSizer.Layout()
        
        #Determine scrollrate
        if not self.rate:
            rate_y = 20
            nritems = len(self.vSizer.GetChildren())
            if nritems > 0:
                height = self.vSizer.GetSize()[1]
                rate_y = height / nritems
                self.rate = rate_y
            self.SetupScrolling(scrollToTop = scrollToTop, scroll_x = False, rate_y = rate_y)
        else:
            self.SetupScrolling(scrollToTop = scrollToTop, scroll_x = False, rate_y = self.rate)
    
    def Reset(self):
        self.Freeze()
        
        self.filter = ''
        self.filtercolumn = 0
        
        self.vSizer.ShowItems(False)
        self.vSizer.Clear()
        for key in self.items.keys():
            self.items[key].Destroy()
            
        self.items = {}
        self.data = None
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
    
    def RefreshData(self, key, data):
        if key in self.items:
            if DEBUG:
                print >> sys.stderr, "ListBody: refresh item"
            self.items[key].RefreshData(data)
    
    def SetData(self, data = None):
        if DEBUG:
            print >> sys.stderr, "ListBody: new data"
        
        #store raw data
        if not data:
            data = self.raw_data
        self.raw_data = data
        
        #apply quickfilter
        if self.filter != '':
            data = filter(self.MatchFilter, data)
            self.parent_list.SetFilteredResults(len(data))
        
        self.vSizer.Clear()
        if data:
            if len(self.items) == 0:
                #new data
                if len(data) > LIST_ITEM_BATCH_SIZE:
                    self.ShowMessage('Loading, please wait.')
                    
                    #Try to yield, allows us to show loading text
                    try:
                        wx.Yield()
                    except:
                        pass
                self.highlightSet = set()
            else:
                #updated data, takes roughly 0.007s for 650+ results
                cur_keys = [key for key,_,_ in self.data]
                self.highlightSet = set([key for key,_,_ in data if key not in cur_keys])

            self.data = data
            self.CreateItems()
        
            return len(data)
        return 0
        
    def OnIdle(self, event):
        if not self.done and self.data:
            self.CreateItems()
            event.RequestMore(not self.done)

    def OnLoadMore(self, event):
        self.loadNext.Disable()
        self.CreateItems(nr_items_to_create=LIST_ITEM_MAX_SIZE, nr_items_to_add=sys.maxint)

    def CreateItems(self, nr_items_to_create = LIST_ITEM_BATCH_SIZE, nr_items_to_add = LIST_ITEM_MAX_SIZE):
        if DEBUG:
            print >> sys.stderr, "ListBody: Creating items"
        
        done = True
        t1 = time.time()

        self.Freeze()
        
        #Check if we need to clear vSizer
        self.messagePanel.Show(False)
        self.vSizer.Remove(self.messagePanel)
            
        #Add created/cached items
        for key, item_data, original_data in self.data:
            if nr_items_to_add > 0:
                if key in self.items:
                    item = self.items[key]
                elif nr_items_to_create > 0:
                    item = ListItem(self.listpanel, self, self.columns, item_data, original_data, self.leftSpacer, self.rightSpacer, showChange = self.showChange)
                    self.items[key] = item
                    
                    nr_items_to_create -= 1
                else:
                    done = False
                    break
                
                sizer = self.vSizer.GetItem(item)
                if not sizer:
                    self.vSizer.Add(item, 0, wx.EXPAND|wx.BOTTOM, 1)
                    item.Show()
                    
                    if key in self.highlightSet:
                        item.Highlight(1)
                        self.highlightSet.remove(key)
                                            
                nr_items_to_add -= 1
            else:
                self.messageText.SetLabel('Only showing the first %d of %d items in this list.\nSearch within results to reduce the number of items, or click the button below.'%(len(self.vSizer.GetChildren()), len(self.data)))
                self.loadNext.Enable()
                self.loadNext.Show()
                self.vSizer.Add(self.messagePanel, 0, wx.EXPAND|wx.BOTTOM, 1)
                self.messagePanel.Layout()
                self.messagePanel.Show()
                done = True
                break
        
        self.OnChange()
        self.Thaw()
        self.done = done
        if DEBUG:
            print >> sys.stderr, "List created", len(self.vSizer.GetChildren()),"rows of", len(self.data),"took", time.time() - t1
        
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
        
        if raise_event:
            self.items[key].OnClick(None)
        else:
            self.items[key].expanded = True
            self.cur_expanded = self.items[key]
            
        self.items[key].ShowSelected()
    
    def DeselectAll(self):
        for _, item in self.items.iteritems():
            item.Deselect()
 
class ListBody(scrolled.ScrolledPanel, AbstractListBody):
    def __init__(self, parent, background, columns, leftSpacer = 0, rightSpacer = 0, singleExpanded = False, showChange = False):
        scrolled.ScrolledPanel.__init__(self, parent)
        AbstractListBody.__init__(self, parent, background, columns, leftSpacer, rightSpacer, singleExpanded, showChange)
        
        self.SetupScrolling(scroll_x = False)
        
    def OnChildFocus(self, event):
        event.Skip()
    
class FixedListBody(wx.Panel, AbstractListBody):
    def __init__(self, parent, background, columns, leftSpacer = 0, rightSpacer = 0, singleExpanded = False, showChange = False):
        wx.Panel.__init__(self, parent)
        AbstractListBody.__init__(self, parent, background, columns, leftSpacer, rightSpacer, singleExpanded, showChange)
    
    def Scroll(self, x, y):
        pass
    def SetupScrolling(self, scroll_x=True, scroll_y=True, rate_x=20, rate_y=20, scrollToTop=True):
        pass
    def GetScrollPixelsPerUnit(self):
        return [0,0]
 
