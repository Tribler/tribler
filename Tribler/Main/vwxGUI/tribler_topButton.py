import wx, os, sys

from wx.lib.mixins.listctrl import CheckListCtrlMixin, ColumnSorterMixin, ListCtrlAutoWidthMixin
from wx.lib.scrolledpanel import ScrolledPanel

from traceback import print_exc, print_stack
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue
from Tribler.Main.vwxGUI import LIST_HIGHTLIGHT

DEBUG = False

class tribler_topButton(wx.Panel):
    """
    Button that changes the image shown if you move your mouse over it.
    It redraws the background of the parent Panel, if this is an imagepanel with
    a variable self.bitmap.
    """
    
    __bitmapCache = {}
    ENABLED = 0x1
    SELECTED = 0x2
    MOUSE_OVER = 0x4
    TOGGLED = 0x8
    
    def __init__(self, *args, **kw):
        self.ready = False
        if len(args) == 0: 
            self.backgroundColor = wx.WHITE
            pre = wx.PrePanel() 
            # the Create step is done by XRC. 
            self.PostCreate(pre) 
            self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate) 
        else:
            self.backgroundColor = ((230,230,230))
            wx.Panel.__init__(self, *args, **kw) 
            self._PostInit()
        
    def OnCreate(self, event):
        self.Unbind(wx.EVT_WINDOW_CREATE)
        wx.CallAfter(self._PostInit)
        event.Skip()
        return True
    
    def _PostInit(self):
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility
        
        self.location = None
        self.state = tribler_topButton.ENABLED
        self.parentBitmap = None
        self.parentColor = None
        
        self.loadBitmaps()
        self.setParentBitmap()
        
        self.SetMinSize(self.bitmaps[0].GetSize())
        
        self.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)
        self.Bind(wx.EVT_MOVE, self.setParentBitmap)
        self.Bind(wx.EVT_SIZE, self.setParentBitmap)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        
        self.Refresh()
        self.ready = True
        
    def loadBitmaps(self):
        self.bitmaps = [None, None]

        # get the image directory
        self.imagedir = os.path.join(self.guiUtility.vwxGUI_path, 'images')
       
        # find a file with same name as this panel
        self.bitmapPath = [os.path.join(self.imagedir, self.GetName()+'.png'), os.path.join(self.imagedir, self.GetName()+'_clicked.png')]
        i = 0
        for img in self.bitmapPath:
            if not os.path.isfile(img):
                print >>sys.stderr,"TopButton: Could not find image:",img
            try:
                if img not in tribler_topButton.__bitmapCache:
                    tribler_topButton.__bitmapCache[img] = wx.Bitmap(img, wx.BITMAP_TYPE_ANY)
                self.bitmaps[i] = tribler_topButton.__bitmapCache[img] 
            except:
                print_exc()
            i+=1
        
    def setEnabled(self, enabled):
        if enabled:
            self.state = self.state | tribler_topButton.ENABLED
        else:
            self.state = self.state ^ tribler_topButton.ENABLED
        self.Refresh()
        
    def IsEnabled(self):
        return self.state & tribler_topButton.ENABLED
    
    def mouseAction(self, event):
        event.Skip()
        if event.Entering():
            self.state = self.state | tribler_topButton.MOUSE_OVER
            self.Refresh()
            
        elif event.Leaving():
            self.state = self.state ^ tribler_topButton.MOUSE_OVER
            self.Refresh()
                 
    def setParentBitmap(self, event = None):
        try:
            parent = self.GetParent()
            bitmap = parent.bitmap
            
            location = self.GetPosition()
            if location != self.location:
                rect = [location[0], location[1], self.GetClientSize()[0], self.GetClientSize()[1]]
                bitmap = self.getBitmapSlice(bitmap, rect)
                self.parentBitmap = bitmap
                self.Refresh()
                self.location = location
        except:
            self.parentBitmap = None
            try:
                parent = self.GetParent()
                self.parentColor = parent.GetBackgroundColour()
            except:
                self.parentColor = None
 
    def getBitmapSlice(self, bitmap, rect):
        try:
            bitmapSize = bitmap.GetSize()
            rects = []
            
            rect[0] = max(0, rect[0])
            rect[1] = max(0, rect[1])
            
            #this bitmap could be smaller than the actual requested rect, due to repeated background
            #using % to modify start location
            if rect[0] > bitmapSize[0] or rect[1] > bitmapSize[1]:
                rect[0] %= bitmapSize[0]
                rect[1] %= bitmapSize[1]
                
            rect[2] = min(rect[2], bitmapSize[0])
            rect[3] = min(rect[3], bitmapSize[1])
                
            #request one part of the background starting at
            additionalWidth = rect[2]
            additionalHeight = rect[3]
            if rect[0] + rect[2] > bitmapSize[0]:
                additionalWidth = bitmapSize[0] - rect[0]
            if rect[1] + rect[3] > bitmapSize[1]:
                additionalHeight = bitmapSize[1] - rect[1]
                
            rects.append(((0,0),[rect[0], rect[1], additionalWidth, additionalHeight]))
            
            #check if image is smaller than requested width
            if rect[0] + rect[2] > bitmapSize[0]:
                additionalWidth = rect[0]
                additionalHeight = bitmapSize[1]
                
                if rect[1] + rect[3] > bitmapSize[1]:
                    additionalHeight = bitmapSize[1] - rect[1]
                    
                rects.append(((bitmapSize[0]-rect[0], 0),[0, rect[1], additionalWidth, additionalHeight]))
            
            #check if image is smaller than requested height 
            if rect[1]+ rect[3] > bitmapSize[1]:
                additionalWidth = bitmapSize[0]
                additionalHeight = rect[1]
                
                if rect[0] + rect[2] > bitmapSize[0]:
                    additionalWidth = bitmapSize[0] - rect[0]
                
                rects.append(((0,bitmapSize[1] - rect[1]),[rect[0], 0, additionalWidth, additionalHeight]))
            
            #if both width and height were smaller
            if rect[0] + rect[2] > bitmapSize[0] and rect[1] + rect[3] > bitmapSize[1]:
                rects.append(((bitmapSize[0]-rect[0],bitmapSize[1] - rect[1]),[0,0,rect[0],rect[1]]))
            
            bmp = wx.EmptyBitmap(rect[2], rect[3]) 
            dc = wx.MemoryDC(bmp)
            for location, rect in rects:
                subbitmap = bitmap.GetSubBitmap(rect)
                dc.DrawBitmapPoint(subbitmap, location)
            dc.SelectObject(wx.NullBitmap)
            del dc
            
            return bmp
        except:
            if DEBUG:
                print_exc()
            return None
    
    def setBackground(self, wxColor):
        self.backgroundColor = wxColor
        self.Refresh()
    
    def GetBitmap(self):
        if (self.state & tribler_topButton.MOUSE_OVER) and self.bitmaps[1]:
            return self.bitmaps[1]
        return self.bitmaps[0]
        
    def OnPaint(self, evt):
        if self.ready:
            dc = wx.BufferedPaintDC(self)
            dc.SetBackground(wx.Brush(self.backgroundColor))
            dc.Clear()
            
            if self.parentBitmap:
                dc.SetPen(wx.TRANSPARENT_PEN)
                dc.SetBrush(wx.BrushFromBitmap(self.parentBitmap))
                w, h = self.GetClientSize()
                dc.DrawRectangle(0, 0, w, h)
            elif self.parentColor:
                dc.SetPen(wx.TRANSPARENT_PEN)
                dc.SetBrush(wx.Brush(self.parentColor))
                w, h = self.GetClientSize()
                dc.DrawRectangle(0, 0, w, h)
            
            if not self.IsEnabled():
                return
    
            bitmap = self.GetBitmap()
            if bitmap:
                dc.DrawBitmap(bitmap, 0,0, True)

class SwitchButton(tribler_topButton):
    __bitmapCache = {}
    
    def loadBitmaps(self):
        self.bitmaps = [None, None, None, None]

        # get the image directory
        imagedir = os.path.join(self.guiUtility.vwxGUI_path, 'images')
        
        # find a file with same name as this panel
        bitmapPath = [os.path.join(imagedir, self.GetName()+'.png'), 
                        os.path.join(imagedir, self.GetName()+'_clicked.png'),
                        os.path.join(imagedir, self.GetName()+'Enabled.png'), 
                        os.path.join(imagedir, self.GetName()+'Enabled_clicked.png')
                        ]
        i = 0
        for img in bitmapPath:
            if not os.path.isfile(img):
                print >>sys.stderr,"SwitchButton: Could not find image:",img
            try:
                if img not in SwitchButton.__bitmapCache:
                    SwitchButton.__bitmapCache[img] = wx.Bitmap(img, wx.BITMAP_TYPE_ANY)
                self.bitmaps[i] = SwitchButton.__bitmapCache[img]
            except:
                print_exc()
            i+=1
        
    def setToggled(self, b):
        if b:
            self.state = self.state | tribler_topButton.TOGGLED
        else:
            self.state = self.state ^ tribler_topButton.TOGGLED
        self.Refresh()
        
    def isToggled(self):
        return self.state & tribler_topButton.TOGGLED

    def GetBitmap(self):
        add = 0
        if self.isToggled():
            add = 2
        
        if (self.state & tribler_topButton.MOUSE_OVER) and self.bitmaps[1+add]:
            return self.bitmaps[1+add]
        return self.bitmaps[0+add]

class settingsButton(tribler_topButton):
    """
    Button with three states in the settings overview
    """
    __bitmapCache = {}
    def __init__(self, *args, **kw):
        tribler_topButton.__init__(self, *args, **kw)
        self.selected = 1
        
    def _PostInit(self):
        tribler_topButton._PostInit(self)
    
    def loadBitmaps(self):
        self.bitmaps = [None, None, None]
                
        # get the image directory
        imagedir = os.path.join(self.guiUtility.vwxGUI_path, 'images')
       
        # find a file with same name as this panel
        bitmapPath = [os.path.join(imagedir, self.GetName()+'_state1.png'), 
                        os.path.join(imagedir, self.GetName()+'_state2.png'),
                       os.path.join(imagedir, self.GetName()+'_state3.png')]

        i = 0
        for img in bitmapPath:
            if not os.path.isfile(img):
                print >>sys.stderr,"TopButton: Could not find image:",img
            try:
                if img not in settingsButton.__bitmapCache:
                    settingsButton.__bitmapCache[img] = wx.Bitmap(img, wx.BITMAP_TYPE_ANY)
                self.bitmaps[i] = settingsButton.__bitmapCache[img]
            except:
                print_exc()
            i+=1
            
    def setSelected(self, sel):
        self.selected = sel
        self.Refresh()
    
    def getSelected(self):
        return self.selected
            
    def mouseAction(self, event):
        pass
    
    def GetBitmap(self):
        return self.bitmaps[self.selected]

class NativeIcon:
    __single = None
    def __init__(self):
        if NativeIcon.__single:
            raise RuntimeError, "NativeIcon is singleton"
        NativeIcon.__single = self
        self.icons = {}
        
    def getInstance(*args, **kw):
        if NativeIcon.__single is None:
            NativeIcon(*args, **kw)
        return NativeIcon.__single
    getInstance = staticmethod(getInstance)
    
    def getBitmap(self, parent, type, background, state):
        if isinstance(background, wx.Colour):
            background = background.Get()
        else:
            background = wx.Brush(background).GetColour().Get()
        
        icons = self.icons.setdefault(type, {}).setdefault(background, {})
        if state not in icons:
            icons[state] = self.__createBitmap(parent, background, type, state)
        return icons[state]
    
    def __createBitmap(self, parent, background, type, state):
        if state == 1:
            if type == 'tree':
                state = wx.CONTROL_EXPANDED
            elif type == 'checkbox':
                state = wx.CONTROL_CHECKED
            else:
                state = wx.CONTROL_PRESSED
        
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
            
        elif type == 'arrow':
            wx.RendererNative.Get().DrawDropArrow(parent, dc, (4, 4, 16, 16), state)
            
        dc.SelectObject(wx.NullBitmap)
        del dc
        
        #determine actual size of drawn icon, and return this subbitmap
        bb = wx.RegionFromBitmapColour(bmp, background).GetBox()
        return bmp.GetSubBitmap(bb)

class LinkStaticText(wx.Panel):
    def __init__(self, parent, text, icon = "bullet_go.png", icon_type = None, icon_align = wx.ALIGN_RIGHT, font_increment = 0, font_colour = '#0473BB'):
        wx.Panel.__init__(self, parent, style = wx.NO_BORDER)
        self.icon_type = icon_type
        
        if icon:
            self.icon = wx.StaticBitmap(self, bitmap = wx.Bitmap(os.path.join(GUIUtility.getInstance().vwxGUI_path, 'images', icon), wx.BITMAP_TYPE_ANY))
            self.icon.SetCursor(wx.StockCursor(wx.CURSOR_HAND))
        elif icon_type:
            self.icon = wx.StaticBitmap(self, bitmap = NativeIcon.getInstance().getBitmap(self.GetParent(), self.icon_type, self.GetBackgroundColour(), state=0))
        else:
            self.icon = None

        hSizer = wx.BoxSizer(wx.HORIZONTAL)

        if self.icon and icon_align == wx.ALIGN_LEFT:
            hSizer.Add(self.icon, 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 3)
        
        #Niels: text or url needs to be non-empty, we don't use url thus fixing it to 'url' 
        self.text = wx.HyperlinkCtrl(self, -1, text, 'url') 
        self.text.SetNormalColour(font_colour)
        self.text.SetVisitedColour(font_colour)
        font = self.text.GetFont()
        font.SetPointSize(font.GetPointSize() + font_increment)
        self.text.SetFont(font)
        
        hSizer.Add(self.text, 0, wx.ALIGN_CENTER_VERTICAL)
            
        if self.icon and icon_align == wx.ALIGN_RIGHT:
            hSizer.Add(self.icon, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RESERVE_SPACE_EVEN_IF_HIDDEN, 3)
        
        if self.icon and text == '':
            self.icon.Hide()
        
        self.SetSizer(hSizer)
        self.SetCursor(wx.StockCursor(wx.CURSOR_HAND))
       
        if parent.GetBackgroundStyle() != wx.BG_STYLE_SYSTEM:
            self.SetBackgroundColour(parent.GetBackgroundColour())
        
    def SetToolTipString(self, tip):
        wx.Panel.SetToolTipString(self, tip)
        self.text.SetToolTipString(tip)
        if self.icon:
            self.icon.SetToolTipString(tip)
        
    def SetLabel(self, text):
        if self.icon:
            self.icon.Show(text != '')
            
        self.text.SetLabel(text)
        self.Layout()
    
    def GetLabel(self):
        return self.text.GetLabel()
    
    def SetFont(self, font):
        self.text.SetFont(font)
        
    def GetFont(self):
        return self.text.GetFont()
    
    def ShowIcon(self, show = True):
        if self.icon and self.icon.IsShown() != show:
            self.icon.Show(show)
    def IsIconShown(self):
        if self.icon:
            return self.icon.IsShown()
        return False
            
    def SetIconToolTipString(self, tip):
        if self.icon:
            self.icon.SetToolTipString(tip)
    
    def HighLight(self, timeout = 2.0):
        self.SetBackgroundColour(LIST_HIGHTLIGHT, blink=True)
        self.Refresh()
        wx.CallLater(timeout * 1000, self.Revert)
        
    def Revert(self):
        self.SetBackgroundColour(self.originalColor, blink=True)
        self.Refresh()
    
    def Blink(self):
        self.HighLight(0.15)
        wx.CallLater(300, self.HighLight, 0.15)
        
    def Bind(self, event, handler, source=None, id=-1, id2=-1):
        wx.Panel.Bind(self, event, handler, source, id, id2)
        
        def modified_handler(actual_event, handler=handler):
            actual_event.SetEventObject(self)
            handler(actual_event)
            
        def text_handler(actual_event, handler=handler):
            mouse_event = wx.MouseEvent(wx.wxEVT_LEFT_UP)
            mouse_event.SetEventObject(self)
            handler(mouse_event)
            
        if event == wx.EVT_LEFT_UP:
            self.text.Bind(wx.EVT_HYPERLINK, text_handler, source, id, id2)
        if self.icon:
            self.icon.Bind(event, modified_handler, source, id, id2)
            
    def SetBackgroundColour(self, colour, blink = False):
        if not blink:
            self.originalColor = colour
        wx.Panel.SetBackgroundColour(self, colour)
        self.text.SetBackgroundColour(colour)
        
        if self.icon and self.icon_type:
            self.icon.SetBitmap(NativeIcon.getInstance().getBitmap(self.GetParent(), self.icon_type, colour, state=0))
            self.icon.Refresh()

class AutoWidthListCtrl(wx.ListCtrl, ListCtrlAutoWidthMixin):
    def __init__(self, parent, style):
        wx.ListCtrl.__init__(self, parent, style=style)
        ListCtrlAutoWidthMixin.__init__(self)

class BetterListCtrl(wx.ListCtrl, ListCtrlAutoWidthMixin):
    def __init__(self, parent, style = wx.LC_REPORT|wx.LC_NO_HEADER|wx.NO_BORDER, tooltip = True):
        wx.ListCtrl.__init__(self, parent, -1, style=style)
        ListCtrlAutoWidthMixin.__init__(self)

        if tooltip:
            self.Bind(wx.EVT_MOTION, self.OnMouseMotion)
    
    def GetListCtrl(self):
        return self
    
    def OnMouseMotion(self, event):
        tooltip = ''
        row, _ = self.HitTest(event.GetPosition())
        if row >= 0:
            try:
                for col in xrange(self.GetColumnCount()):
                    tooltip += self.GetItem(row, col).GetText() + "    "
                
                if len(tooltip) > 0:
                    tooltip = tooltip[:-4]
            except:
                pass
        self.SetToolTipString(tooltip)
        
class SelectableListCtrl(BetterListCtrl):
    def __init__(self, parent, style = wx.LC_REPORT|wx.LC_NO_HEADER, tooltip = True):
        BetterListCtrl.__init__(self, parent, style, tooltip)
        self.Bind(wx.EVT_KEY_DOWN, self._CopyToClipboard)
    
    def _CopyToClipboard(self, event):
        if event.ControlDown():
            if event.GetKeyCode() == 67: #ctrl + c
                data = ""
                
                selected = self.GetFirstSelected()
                while selected != -1:
                    for col in xrange(self.GetColumnCount()):
                        data += self.GetItem(selected, col).GetText() + "\t"
                    data += "\n"
                    selected = self.GetNextSelected(selected)
                    
                do = wx.TextDataObject()
                do.SetText(data)
                wx.TheClipboard.Open()
                wx.TheClipboard.SetData(do)
                wx.TheClipboard.Close()
                
            elif event.GetKeyCode() == 65: #ctrl + a
                for index in xrange(self.GetItemCount()):
                    self.Select(index)
        
class TextCtrlAutoComplete(wx.TextCtrl):
    def __init__ (self, parent, entrycallback = None, selectcallback = None, **therest):
        '''
            Constructor works just like wx.TextCtrl
        ''' 
        if therest.has_key('style'): 
            therest['style']=wx.TE_PROCESS_ENTER|therest['style'] 
        else:
            therest['style']= wx.TE_PROCESS_ENTER 
    
        wx.TextCtrl.__init__(self , parent , **therest)

        # we need the GUITaskQueue to offload database activity, otherwise we may lock the GUI
        self.text = ""
        self.choices = []
        self.guiserver = GUITaskQueue.getInstance()
        
        self.screenheight = wx.SystemSettings.GetMetric(wx.SYS_SCREEN_Y)
         
        self.dropdown = wx.PopupWindow(self)
        self.dropdown.SetBackgroundColour(wx.WHITE)
        sizer = wx.BoxSizer()
        
        self.dropdownlistbox = AutoWidthListCtrl(self.dropdown, style=wx.LC_REPORT | wx.BORDER_NONE | wx.LC_SINGLE_SEL | wx.LC_NO_HEADER) 
        self.dropdownlistbox.Bind(wx.EVT_LEFT_DOWN, self.ListClick)
        self.dropdownlistbox.Bind(wx.EVT_LEFT_DCLICK, self.ListClick)
        sizer.Add(self.dropdownlistbox, 1, wx.EXPAND|wx.ALL, 3)
        self.dropdown.SetSizer(sizer)
        
        self.entrycallback = entrycallback
        self.selectcallback = selectcallback
        
        self.Bind (wx.EVT_KILL_FOCUS, self.ControlChanged, self)
        self.Bind (wx.EVT_TEXT , self.EnteredText, self)
        self.Bind (wx.EVT_KEY_DOWN , self.KeyDown, self)
        
        self.dropdown.Bind(wx.EVT_LISTBOX, self.ListItemSelected, self.dropdownlistbox)
        
    def ListClick(self, evt):
        toSel, _ = self.dropdownlistbox.HitTest(evt.GetPosition()) 
        if toSel == -1:
            return
        
        self.dropdownlistbox.Select(toSel)
        self.SetValueFromSelected()

    def SetChoices (self, choices = [""]) :
        ''' Sets the choices available in the popup wx.ListBox. ''' 
        self.choices = choices 
        
        #delete, if need, all the previous data
        if self.dropdownlistbox.GetColumnCount() != 0:
            self.dropdownlistbox.DeleteAllColumns()
            self.dropdownlistbox.DeleteAllItems()
            
        self.dropdownlistbox.InsertColumn(0, "Select")

        for num, it in enumerate(choices): 
            self.dropdownlistbox.InsertStringItem(num, it)
            
        self.dropdownlistbox.SetColumnWidth(0, wx.LIST_AUTOSIZE) #autosize only works after adding rows

        
        itemcount = min(len(choices), 7) + 2
        charheight = self.dropdownlistbox.GetCharHeight()
        
        self.popupsize = wx.Size(self.GetClientSize()[0], (charheight*itemcount) + 6)
        self.dropdown.SetClientSize(self.popupsize)
        self.dropdown.Layout()

    def ControlChanged (self, event) : 
        self.ShowDropDown(False)
        event.Skip()

    def EnteredText(self, event):
        text = event.GetString()
        if text != self.text: 
            self.text = text

            if self.entrycallback:
                def wx_callback(choices):
                    """
                    Will update the gui IF the user did not yet change the input text
                    """
                    if text == self.text:
                        self.SetChoices(choices)
                        if len(self.choices) == 0:
                            self.ShowDropDown(False)
                        else:
                            self.ShowDropDown(True)
    
                def db_callback():
                    """
                    Will try to find completions in the database IF the user did not yet change the
                    input text
                    """
                    if text == self.text:
                        choices = self.entrycallback(text)
                        wx.CallAfter(wx_callback, choices)
    
                self.guiserver.add_task(db_callback, id = "DoAutoComplete")

    def KeyDown(self, event): 
        skip = True 
        
        sel = self.dropdownlistbox.GetFirstSelected() 
        visible = self.dropdown.IsShown() 
        if event.GetKeyCode() == wx.WXK_DOWN : 
            if sel < (self.dropdownlistbox.GetItemCount () - 1) : 
                self.dropdownlistbox.Select(sel + 1) 
                self.ListItemVisible()
                
            self.ShowDropDown() 
            skip = False
             
        if event.GetKeyCode() == wx.WXK_UP : 
            if sel > 0 : 
                self.dropdownlistbox.Select (sel - 1) 
                self.ListItemVisible() 
            self.ShowDropDown () 
            skip = False 

        if visible : 
            if event.GetKeyCode() == wx.WXK_RETURN or event.GetKeyCode() == wx.WXK_SPACE:
                if sel > -1: #we select the current item if enter or space is pressed
                    skip = event.GetKeyCode() == wx.WXK_RETURN
                    self.SetValueFromSelected(addSpace = (event.GetKeyCode() == wx.WXK_SPACE))
                    self.ShowDropDown(False)
                
            if event.GetKeyCode() == wx.WXK_ESCAPE : 
                self.ShowDropDown(False) 
                skip = False
         
        if skip: 
            event.Skip()

    def SetValueFromSelected(self, addSpace = False) : 
        ''' 
            Sets the wx.TextCtrl value from the selected wx.ListBox item.
            Will do nothing if no item is selected in the wx.ListBox. 
        ''' 
        sel = self.dropdownlistbox.GetFirstSelected() 
        if sel > -1 : 
            newval = self.dropdownlistbox.GetItemText(sel)
            if addSpace:
                newval += " "
            
            if newval != self.GetValue():
                self.text = newval
                
                self.SetValue(newval)
                self.SetInsertionPointEnd()
                
                self.selectcallback()

    def ShowDropDown(self, show = True) : 
        ''' Either display the drop down list (show = True) or hide it (show = False). '''
        if show:
            show = len(self.choices) > 0
            
        if show:
            focusWin = wx.Window.FindFocus()
            show = focusWin == self
            
        if show and not self.dropdown.IsShown():
            size = self.dropdown.GetSize() 
            width, height = self.GetSizeTuple() 
            x, y = self.ClientToScreenXY (0, height) 
            if size.GetWidth() <> width : 
                size.SetWidth(width) 
                self.dropdown.SetSize(size)

            if (y + size.GetHeight()) < self.screenheight : 
                self.dropdown.SetPosition (wx.Point(x, y)) 
            else: 
                self.dropdown.SetPosition (wx.Point(x, y - height - size.GetHeight())) 
        self.dropdown.Show(show)

    def ListItemVisible(self) : 
        ''' Moves the selected item to the top of the list ensuring it is always visible. ''' 
        self.dropdownlistbox.EnsureVisible(self.dropdownlistbox.GetFirstSelected())

    def ListItemSelected(self, event):
        self.SetValueFromSelected() 
    
class ImageScrollablePanel(ScrolledPanel):
    def __init__(self, parent, id=-1, pos=wx.DefaultPosition, size=wx.DefaultSize, style=wx.HSCROLL|wx.VSCROLL):
        ScrolledPanel.__init__(self, parent, id, pos, size, style)
        
        self.bitmap = None
        wx.EVT_PAINT(self, self.OnPaint)
        
    def OnPaint(self, evt):
        if self.bitmap:
            obj = evt.GetEventObject()
            dc = wx.BufferedPaintDC(obj)
            
            dc.SetPen(wx.TRANSPARENT_PEN)
            dc.SetBrush(wx.BrushFromBitmap(self.bitmap))
            w, h = self.GetClientSize()
            dc.DrawRectangle(0, 0, w, h)
        else:
            evt.Skip()
    
    def SetBitmap(self, bitmap):
        self.bitmap = bitmap
        self.Refresh()
