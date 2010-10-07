import wx, os, sys
from traceback import print_exc
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility

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
        self.state = self.state | tribler_topButton.TOGGLED
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

class NoFocusButton(wx.Button):
    def __init__(self, *args, **kw):
        wx.Button.__init__(self, *args, **kw)
        self.Bind(wx.EVT_SET_FOCUS , self.OnFocus)
    
    def OnFocus(self, event):
        self.Navigate()
    def AcceptsFocus(self):
        return False
    def AcceptsFocusFromKeyboard(self):
        return False
    
class LinkStaticText(wx.Panel):
    def __init__(self, parent, text, icon = "bullet_go.png", font_increment = 0):
        wx.Panel.__init__(self, parent, style = wx.NO_BORDER)
        self.SetBackgroundColour(parent.GetBackgroundColour())
        
        self.icon = wx.StaticBitmap(self, bitmap = wx.Bitmap(os.path.join(GUIUtility.getInstance().vwxGUI_path, 'images', icon), wx.BITMAP_TYPE_ANY))
        self.text = wx.StaticText(self, -1, text)
        font = self.text.GetFont()
        font.SetUnderlined(True)
        font.SetPointSize(font.GetPointSize() + font_increment)
        self.text.SetFont(font)
        
        if sys.platform != 'linux2':
            self.text.SetCursor(wx.StockCursor(wx.CURSOR_HAND))
        
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(self.text, 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 3)
        hSizer.Add(self.icon, 0, wx.ALIGN_CENTER_VERTICAL)
        self.SetSizer(hSizer)
        
    def SetToolTipString(self, tip):
        wx.Panel.SetToolTipString(self, tip)
        self.icon.SetToolTipString(tip)
        self.text.SetToolTipString(tip)
        
    def Bind(self, event, handler, source=None, id=-1, id2=-1):
        wx.Panel.Bind(self, event, handler, source, id, id2)
        
        self.icon.Bind(event, handler, source, id, id2)
        self.text.Bind(event, handler, source, id, id2)