import wx
import wx.lib.scrolledpanel as scrolled

import sys
import time
import re

LIST_ITEM_BATCH_SIZE = 35
LIST_ITEM_MAX_SIZE = 250
DEBUG = False

class ListIcon:
    __single = None
    def __init__(self):
        if ListIcon.__single:
            raise RuntimeError, "ListIcon is singleton"
        ListIcon.__single = self
        
    def getInstance(*args, **kw):
        if ListIcon.__single is None:
            ListIcon(*args, **kw)
        return ListIcon.__single
    getInstance = staticmethod(getInstance)
    
    def getBitmaps(self, parent, type, selectedcolor, deselectedcolor):
        if not getattr(self, 'icons', False):
            self.icons = {}
            self.icons['tree'] = self.__createBitmaps('tree', parent, selectedcolor, deselectedcolor)
            self.icons['checkbox'] = self.__createBitmaps('checkbox', parent, selectedcolor, deselectedcolor)
        return self.icons[type]
    
    def __createBitmaps(self, type, parent, selectedcolor, deselectedcolor):
        unselectedcol = self.__createBitmap(parent, deselectedcolor, type)
        selectedcol = self.__createBitmap(parent, selectedcolor, type)
        
        if type == 'tree':
            expanded = self.__createBitmap(parent, selectedcolor, type, wx.CONTROL_EXPANDED)
        else:
            expanded = self.__createBitmap(parent, selectedcolor, type, wx.CONTROL_CHECKED)
        return [unselectedcol, selectedcol, expanded]
    def __createBitmap(self, parent, background, type, flag=0):
        #There are some strange bugs in RendererNative, the alignment is incorrect of the drawn images
        #Thus we create a larger bmp, allowing for borders
        bmp = wx.EmptyBitmap(24,24) 
        dc = wx.MemoryDC(bmp)
        dc.SetBackground(wx.Brush(background))
        dc.Clear()
        
        if type == 'checkbox':
            wx.RendererNative.Get().DrawCheckBox(parent, dc, (4, 4, 16, 16), flag) #max size is 16x16, using 4px as a border
        elif type == 'tree':
            wx.RendererNative.Get().DrawTreeItemButton(parent, dc, (4, 4, 16, 16), flag)
        dc.SelectObject(wx.NullBitmap)
        
        #determine actual size of drawn icon, and return this subbitmap
        bb = wx.RegionFromBitmapColour(bmp, background).GetBox()
        return bmp.GetSubBitmap(bb)

class ListItem(wx.Panel):
    def __init__(self, parent, parent_list, columns, data, original_data, leftSpacer = 0, rightSpacer = 0):
         wx.Panel.__init__(self, parent)
         
         self.parent_list = parent_list
         self.columns = columns
         self.data = data
         self.original_data = original_data
         self.leftSpacer = leftSpacer
         self.rightSpacer = rightSpacer
         
         self.selectedColor = wx.Colour(216,233,240)
         self.deselectedColor = wx.WHITE
         self.SetBackgroundColour(self.deselectedColor)
         
         self.vSizer = wx.BoxSizer(wx.VERTICAL)
         self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
         
         self.AddComponents()
         
         self.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouse)
         self.vSizer.Add(self.hSizer, 0, wx.EXPAND)
         self.SetSizer(self.vSizer)
         
         self.SetCursor(wx.StockCursor(wx.CURSOR_HAND))
    
    def AddComponents(self):
         self.controls = []
         if self.leftSpacer > 0:
             self.hSizer.AddSpacer((self.leftSpacer, -1))
         
         for i in xrange(len(self.columns)):
             if self.columns[i].get('icon', False):
                 if self.columns[i]['icon'] == 'checkbox' or self.columns[i]['icon'] == 'tree':

                     self.expandedState = wx.StaticBitmap(self, -1, self.GetIcons(self.columns[i]['icon']))
                     self.expandedState.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouse)
                     self.expandedState.SetCursor(wx.StockCursor(wx.CURSOR_HAND))
                     self.hSizer.Add(self.expandedState, 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 3)
                 else:
                     icon = self.columns[i]['icon'](self)
                     if icon:
                         icon = wx.StaticBitmap(self, -1, icon)
                         icon.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouse)
                         icon.SetCursor(wx.StockCursor(wx.CURSOR_HAND))
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
                 label.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouse)
                 label.SetCursor(wx.StockCursor(wx.CURSOR_HAND))
                 self.controls.append(label)
                 
                 self.hSizer.Add(label, option, wx.RESERVE_SPACE_EVEN_IF_HIDDEN|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 3)
                 if self.columns[i]['width'] == wx.LIST_AUTOSIZE:
                     label.SetMinSize((1,-1))
                     
             elif type == 'method':
                 control = self.columns[i]['method'](self, self)
                 if control:
                     control.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouse)
                     control.SetCursor(wx.StockCursor(wx.CURSOR_HAND))
                     
                     if getattr(control, 'GetChildren', False):
                         children = control.GetChildren()
                         for child in children:
                            child.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouse)
                            child.SetCursor(wx.StockCursor(wx.CURSOR_HAND))
                     self.hSizer.Add(control, 0, wx.RESERVE_SPACE_EVEN_IF_HIDDEN|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 3)
                     self.controls.append(control)
                     
                     if self.columns[i]['width'] == -1:
                         self.columns[i]['width'] = control.GetSize()[0]
                         self.parent_list.parent_list.header.ResizeColumn(i, self.columns[i]['width'])
                 else:
                     if self.columns[i]['width'] != -1:
                        self.hSizer.Add((self.columns[i]['width'], -1), 0, wx.LEFT|wx.RIGHT, 3)
         
         if self.rightSpacer > 0:
             self.hSizer.AddSpacer((self.rightSpacer, -1))

         self.hSizer.Layout()
         
    def GetIcons(self, type):
        self.uncheckimage, self.mouseoveruncheckimage, self.checkimage = ListIcon.getInstance().getBitmaps(self, type, self.selectedColor, self.deselectedColor)
        return self.uncheckimage
        
    def RefreshData(self, data):
        if isinstance(data[2], dict): #update original_data
            for key in data[2].keys():
                self.original_data[key] = data[2][key]
        else:
            self.original_data = data[2]
        
        control_index = 0
        new_controls = False
        
        for i in xrange(len(self.columns)):
            type = self.columns[i].get('type','label')
            if type == 'label':
                str_data = self.columns[i].get('fmt', unicode)(data[1][i])
                
                if str_data != self.controls[control_index].GetLabel():
                    self.controls[control_index].SetLabel(str_data)
                    self.controls[control_index].Refresh()
                control_index += 1
            
            elif type == 'method':
                if self.data[i] != data[1][i]:
                    control = self.columns[i]['method'](self, self)
                    if control:
                        control.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouse)
                        control.SetCursor(wx.StockCursor(wx.CURSOR_HAND))
                         
                        if getattr(control, 'GetChildren', False):
                            children = control.GetChildren()
                            for child in children:
                                child.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouse)
                                child.SetCursor(wx.StockCursor(wx.CURSOR_HAND))
                        
                        cur_sizeritem_index = 0
                        cur_sizeritem = self.hSizer.GetItem(self.controls[control_index])
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
                control_index += 1
            
        if new_controls:
            self.hSizer.Layout()
            self.ShowSelected()
        
        self.data = data[1]
         
    def ShowSelected(self):
        selected = getattr(self, 'selected', False) or getattr(self, 'expanded', False)
        for sizeritem in self.hSizer.GetChildren():
            if sizeritem.IsWindow():
                child = sizeritem.GetWindow()
                if getattr(child, 'selected', False):
                    selected = True
                    break
                
                if getattr(child, 'GetChildren', False):
                    sub_children = child.GetChildren()
                    for sub_child in sub_children:
                        if getattr(sub_child, 'selected', False):
                            selected = True
                            break
        if selected:
            color = self.selectedColor
        else:
            color = self.deselectedColor
            
        self.SetBackgroundColour(color)
        for sizeritem in self.hSizer.GetChildren():
            if sizeritem.IsWindow():
                child = sizeritem.GetWindow()
                if isinstance(child, wx.Panel):
                    child.SetBackgroundColour(color)
        
        #If this item has a checkbox and it is not checked
        if getattr(self, 'expandedState', False) and not getattr(self, 'expanded', False): 
            if selected: #then show mouseover version upon select
                self.expandedState.SetBitmap(self.mouseoveruncheckimage)
            else:
                self.expandedState.SetBitmap(self.uncheckimage)
        self.Refresh()
    
    def Deselect(self):
        self.selected = False
        self.expanded = False
        
        for child in self.GetChildren():
            child.selected = False
                        
            if getattr(child, 'GetChildren', False):
                sub_children = child.GetChildren()
                for sub_child in sub_children:
                    sub_child.selected = False
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
        elif event.LeftUp():
            self.OnClick(event)
            
        event.Skip() #Allow windows to paint button hover
        
    def OnClick(self, event):
        if not getattr(self, 'expanded', False):
            if self.parent_list.OnExpand(self):
                self.expanded = True
            
                if getattr(self, 'expandedState', False):
                    self.expandedState.SetBitmap(self.checkimage)
        else:
            self.parent_list.OnCollapse(self)
            self.expanded = False
            
            if getattr(self, 'expandedState', False):
                self.expandedState.SetBitmap(self.mouseoveruncheckimage)
        
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
        
        if len(self.vSizer.GetChildren()) > 1:
            item = self.vSizer.GetItem(1).GetWindow()
            item.Hide()
            
            self.vSizer.Detach(1)
            self.vSizer.Layout()
            return item
        
class AbstractListBody():
    def __init__(self, parent, background, columns, leftSpacer = 0, rightSpacer = 0, singleExpanded = False):
        self.columns = columns
        self.leftSpacer = leftSpacer
        self.rightSpacer = rightSpacer
        self.parent_list = parent
        self.singleExpanded = singleExpanded
        
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
        self.loadNext = wx.Button(self.messagePanel, -1, "Show remaining items")
        self.loadNext.Bind(wx.EVT_BUTTON, self.OnLoadAll)
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
        
        #quick filter
        self.filter = ''
        self.filtercolumn = 0
        
        #queue lists
        self.done = True
        self.data = []
        self.items = {}
        self.Bind(wx.EVT_IDLE, self.OnIdle)
        
    def OnSort(self, column, reverse):
        self.Scroll(-1, 0)
        self.Freeze()
        
        self.data = sorted(self.data, cmp = lambda b,a: cmp(a[1][column], b[1][column]), reverse=reverse)
        
        self.vSizer.ShowItems(False)
        self.vSizer.Clear()
        self.CreateItems()
        
        self.Thaw()
    
    def FilterItems(self, keyword, column = 0):
        new_filter = keyword.lower()
        if new_filter != self.filter or column != self.filtercolumn:
            self.filter = new_filter
            self.filtercolumn = column
            
            self.Scroll(-1, 0)
            self.Freeze()
                
            self.vSizer.ShowItems(False)
            self.vSizer.Clear()
            self.CreateItems()
            
            self.Thaw()
        
    def MatchFilter(self, item):
        return re.search(self.filter, item[1][self.filtercolumn].lower())
    
    def OnExpand(self, item, raise_event = False):
        self.Freeze()
        
        panel = self.parent_list.OnExpand(item)
        if panel and not isinstance(panel, bool):
            item.Expand(panel)
            self.OnChange()
            
        if self.singleExpanded:
            cur_expanded = getattr(self, 'cur_expanded', None)
            if cur_expanded:
                self.OnCollapse(cur_expanded)
                cur_expanded.ShowSelected()
                
            self.cur_expanded = item
            
        self.Thaw()
        return panel
    
    def OnCollapse(self, item):
        self.Freeze()
        
        panel = item.Collapse()
        self.parent_list.OnCollapse(item, panel)
        self.cur_expanded = None
        
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
        self.OnChange()
        self.Thaw()
    
    def IsEmpty(self):
        return len(self.items) == 0
    
    def InList(self, key):
        return key in self.items
    
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
    
    def SetData(self, data):
        if DEBUG:
            print >> sys.stderr, "ListBody: new data"
        
        self.vSizer.Clear()
        if len(self.items) == 0 and len(data) > LIST_ITEM_BATCH_SIZE:
            self.ShowMessage('Loading, please wait.')
            
            #Try to yield, allows us to show loading text
            try:
                wx.Yield()
            except:
                pass
        
        self.data = data
        self.CreateItems()
        
    def OnIdle(self, event):
        if not self.done:
            self.CreateItems()
            event.RequestMore(not self.done)

    def OnLoadAll(self, event):
        self.loadNext.Disable()
        self.CreateItems(sys.maxint, sys.maxint)

    def CreateItems(self, nr_items_to_create = LIST_ITEM_BATCH_SIZE, nr_items_to_add = LIST_ITEM_MAX_SIZE):
        if DEBUG:
            print >> sys.stderr, "ListBody: Creating items"
        
        done = True
        t1 = time.time()

        self.Freeze()
        
        #Check if we need to clear vSizer
        self.messagePanel.Show(False)
        self.vSizer.Remove(self.messagePanel)

        #Apply quickfilter
        if self.filter != '':
            data = filter(self.MatchFilter, self.data)
        else:
            data = self.data
            
        #Add created/cached items
        for key, item_data, original_data in data:
            if nr_items_to_add > 0:
                if key in self.items:
                    item = self.items[key]
                elif nr_items_to_create > 0:
                    item = ListItem(self.listpanel, self, self.columns, item_data, original_data, self.leftSpacer, self.rightSpacer)
                    self.items[key] = item
                    
                    nr_items_to_create -= 1
                else:
                    done = False
                    break
                
                sizer = self.vSizer.GetItem(item)
                if not sizer:
                    self.vSizer.Add(item, 0, wx.EXPAND|wx.BOTTOM, 1)
                    item.Show()
                    nr_items_to_add -= 1
                else:
                    nr_items_to_add -= 1
            else:
                self.messageText.SetLabel('Only showing the first %d of %d items in this list.\nUse the filter to reduce the number of items, or click the button below.'%(LIST_ITEM_MAX_SIZE, len(self.data)))
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
        return getattr(self, 'cur_expanded', None)
    
    def GetExpandedItems(self):
        expanded = []
        for key, item in self.items.iteritems():
            if getattr(item, 'expanded', False):
                expanded.append((key,item))
        return expanded
    
    def Select(self, key, raise_event = True):
        self.DeselectAll()
        
        if raise_event:
            self.items[key].OnClick(None)
        else:
            self.items[key].expanded = True
            self.cur_expanded = self.items[key]
            
        self.items[key].ShowSelected()
    
    def DeselectAll(self):
        for key, item in self.items.iteritems():
            item.Deselect()
 
class ListBody(scrolled.ScrolledPanel, AbstractListBody):
    def __init__(self, parent, background, columns, leftSpacer = 0, rightSpacer = 0, singleExpanded = False):
        scrolled.ScrolledPanel.__init__(self, parent)
        AbstractListBody.__init__(self, parent, background, columns, leftSpacer, rightSpacer, singleExpanded)
        
        self.SetupScrolling(scroll_x = False)
        
    def OnChildFocus(self, event):
        event.Skip()
    
class FixedListBody(wx.Panel, AbstractListBody):
    def __init__(self, parent, background, columns, leftSpacer = 0, rightSpacer = 0, singleExpanded = False):
        wx.Panel.__init__(self, parent)
        AbstractListBody.__init__(self, parent, background, columns, leftSpacer, rightSpacer, singleExpanded)
    
    def Scroll(self, x, y):
        pass
    def SetupScrolling(self, scroll_x=True, scroll_y=True, rate_x=20, rate_y=20, scrollToTop=True):
        pass
    def GetScrollPixelsPerUnit(self):
        return [0,0]
 
