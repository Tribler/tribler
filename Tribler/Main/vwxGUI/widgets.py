# Written by Niels Zeilemaker, Egbert Bouman
import wx, os, sys, math

from wx.lib.mixins.listctrl import CheckListCtrlMixin, ColumnSorterMixin, ListCtrlAutoWidthMixin
from wx.lib.scrolledpanel import ScrolledPanel
from wx.lib.buttons import GenBitmapButton

from traceback import print_exc, print_stack
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue
from __init__ import LIST_GREY, LIST_LIGHTBLUE, TRIBLER_RED, LIST_HIGHTLIGHT, GRADIENT_LRED, GRADIENT_DRED, GRADIENT_LGREY, GRADIENT_DGREY, SEPARATOR_GREY, FILTER_GREY
from wx.lib.stattext import GenStaticText
from wx.lib.stattext import GenStaticText
from wx.lib.colourutils import AdjustColour
from wx.lib.wordwrap import wordwrap
from Tribler.Main.vwxGUI import DEFAULT_BACKGROUND, COMPLETED_COLOUR,\
    SEEDING_COLOUR, DOWNLOADING_COLOUR, STOPPED_COLOUR
from Tribler.Main.Utility.GuiDBHandler import startWorker

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
            self.backgroundColor = DEFAULT_BACKGROUND
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
        self.SetCursor(wx.StockCursor(wx.CURSOR_HAND))
        
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
        
    def getEnabled(self):
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
            
            if not self.getEnabled():
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
        assert isinstance(background, wx.Colour), "we require a wx.colour object here, got %s"%type(background)
        if isinstance(background, wx.Colour):
            background = background.Get()
        else:
            background = wx.Brush(background).GetColour().Get()
        
        icons = self.icons.setdefault(type, {})
        if background not in icons:
            icons.setdefault(background, {})
            
            def fixSize(bitmap, width, height):
                if width != bitmap.GetWidth() or height != bitmap.GetHeight():
                
                    bmp = wx.EmptyBitmap(width,height)
                    dc = wx.MemoryDC(bmp)
                    dc.SetBackground(wx.Brush(background))
                    dc.Clear()
                    
                    offset_x = (width - bitmap.GetWidth())/2
                    offset_y = (height - bitmap.GetHeight())/2
                    
                    dc.DrawBitmap(bitmap, offset_x, offset_y)
                    dc.SelectObject(wx.NullBitmap)
                    del dc
                    
                    return bmp
                return bitmap
            
            #create both icons
            icons[background][0] = self.__createBitmap(parent, background, type, 0)
            icons[background][1] = self.__createBitmap(parent, background, type, 1)
            
            width = max(icons[background][0].GetWidth(), icons[background][1].GetWidth())
            height = max(icons[background][0].GetHeight(), icons[background][1].GetHeight())
            
            icons[background][0] = fixSize(icons[background][0], width, height)
            icons[background][1] = fixSize(icons[background][1], width, height)
            
        
        if state not in icons[background]:
            icons[background][state] = self.__createBitmap(parent, background, type, state)
        return icons[background][state]
    
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
            from wx.lib.embeddedimage import PyEmbeddedImage
            arrow = PyEmbeddedImage(
                "iVBORw0KGgoAAAANSUhEUgAAAAcAAAAECAIAAADNpLIqAAAAA3NCSVQICAjb4U/gAAAAGklE"
                "QVQImWNgwAo+fPiAKcKEJgFhMyFz4NIALdoQ5dJXG4AAAAAASUVORK5CYII=")
            return arrow.GetBitmap()
            
        dc.SelectObject(wx.NullBitmap)
        del dc
        
        #determine actual size of drawn icon, and return this subbitmap
        bb = wx.RegionFromBitmapColour(bmp, background).GetBox()
        return bmp.GetSubBitmap(bb)

class BetterText(wx.StaticText):
    def __init__(self, *args, **kwargs):
        wx.StaticText.__init__(self, *args, **kwargs)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackGround)
    
    def OnEraseBackGround(self, event):
        pass
    
    def SetLabel(self, text):
        if text != self.GetLabel():
            wx.StaticText.SetLabel(self, text)
            
class MaxBetterText(wx.BoxSizer):
    
    def __init__(self, parent, label, maxLines = 6, maxCharacters = 600, name = None, button = None):
        wx.BoxSizer.__init__(self, wx.VERTICAL)
        
        self.fullLabel = ''
        self.expand = button
        self.parent = parent
        
        self.maxLines = maxLines
        self.maxCharacters = maxCharacters
        self.name = name or 'item'
        self.name = self.name.lower()
        
        self.label = BetterText(parent, -1, '')
        self.Add(self.label, 0, wx.EXPAND)
        
        self.SetLabel(label)
        
        if sys.platform == 'win32': #lets do manual word wrapping
            self.label.Bind(wx.EVT_SIZE, self.OnSize)

    def SetLabel(self, label):
        if self.fullLabel != label:
            self.fullLabel = label
            self.shortLabel = self._limitLabel(label)
        
            self.label.SetLabel(self.shortLabel)
            
            if len(self.shortLabel) < len(self.fullLabel):
                self.hasMore = True
                
                if not self.expand:
                    self.expand = wx.Button(self.parent, -1, "Click to view full "+self.name, style = wx.BU_EXACTFIT)
                    self.expand.Bind(wx.EVT_BUTTON, self.OnFull)
                    self.Add(self.expand, 0, wx.ALIGN_RIGHT)
                else:
                    self.expand.Bind(wx.EVT_BUTTON, self.OnFull)
                    self.expand.SetLabel("Click to view full "+self.name)
            else:
                self.hasMore = False

    def OnFull(self, event):
        if not self.IsExpanded():
            self.expand.SetLabel('Click to collapse '+self.name)
            self.label.SetLabel(self.fullLabel)
        else:
            self.expand.SetLabel('Click to view full '+self.name)
            self.label.SetLabel(self.shortLabel)
        
        self.parent.OnChange()
    
    def IsExpanded(self):
        return self.expand == None or self.expand.GetLabel().startswith('Click to collapse')
        
    def OnSize(self, event):
        width = self.label.GetSize()[0]
        bestwidth = self.label.GetBestSize()[0]
        
        if width > 1 and bestwidth != width:
            dc = wx.ClientDC(self.label)
            dc.SetFont(self.label.GetFont())
            label = wordwrap(self.fullLabel, width, dc, breakLongWords = True, margin = 0)
            if not self.IsExpanded():
                self.shortLabel = label = self._limitLabel(label)
            self.label.SetLabel(label)    

    def SetMinSize(self, minsize):
        self.label.SetMinSize(minsize)
        self.Layout()
    
    def find_nth(self, haystack, needle, n):
        start = haystack.find(needle)
        while start >= 0 and n > 1:
            start = haystack.find(needle, start+len(needle))
            n -= 1
        return start
    
    def _limitLabel(self, label):
        #find 6th line or break at 600 characters
        breakAt = self.find_nth(label, '\n', self.maxLines)
        if breakAt != -1:
            breakAt = min(breakAt, self.maxCharacters)
        else:
            breakAt = self.maxCharacters
        
        return label[:breakAt]

        
#Stripped down version of wx.lib.agw.HyperTextCtrl, thank you andrea.gavana@gmail.com
class LinkText(GenStaticText):
    def __init__(self, parent, label, fonts = [None, None], colours = [None, None], style = 0, parentsizer = None):
        if parentsizer:
            self.parentsizer = parentsizer
        else:
            self.parentsizer = parent

        GenStaticText.__init__(self, parent, -1, label, style = style)
        self.SetCursor(wx.StockCursor(wx.CURSOR_HAND)) 
        
        self.SetFonts(fonts)
        self.SetColours(colours)
        self.Reset()
        
        self.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouseEvent)
        self.Bind(wx.EVT_MOTION, self.OnMouseEvent)
        self.enter = False
    
    def SetFonts(self, fonts):
        self.fonts = []
        for font in fonts:
            if font is None:
                font = self.GetFont()
            self.fonts.append(font)
            
    def SetColours(self, colours):
        self.colours = []
        for colour in colours:
            if colour is None:
                colour = self.GetForegroundColour()
            self.colours.append(colour)
    
    def GetColours(self):
        return self.colours
            
    def Reset(self):
        self.SetFontColour(self.fonts[0], self.colours[0])
        self.enter = False
    
    def SetFontColour(self, font, colour):
        needRefresh = False
        
        if self.GetFont() != font:
            self.SetFont(font)
            
            needRefresh = True
        
        if self.GetForegroundColour() != colour:
            self.SetForegroundColour(colour)
                            
            needRefresh = True
        
        if needRefresh:
            self.Refresh()
            self.parentsizer.Layout()
    
    def OnMouseEvent(self, event):
        if event.Moving():
            self.SetFontColour(self.fonts[1], self.colours[1])
            self.enter = True
            
        elif event.LeftUp() or event.LeftDown():            
            pass
        else:
            self.SetFontColour(self.fonts[0], self.colours[0])
            self.enter = False
            
        event.Skip()
        
    def SetBackgroundColour(self, colour):
        GenStaticText.SetBackgroundColour(self, colour)
        self.Refresh()

class LinkStaticText(wx.BoxSizer):
    def __init__(self, parent, text, icon = "bullet_go.png", icon_type = None, icon_align = wx.ALIGN_RIGHT, font_increment = 0, font_colour = '#0473BB'):
        wx.BoxSizer.__init__(self, wx.HORIZONTAL)
        self.parent = parent
        
        self.icon_type = icon_type
        self.icon_align = icon_align
        
        if icon:
            self.icon = wx.StaticBitmap(parent, bitmap = wx.Bitmap(os.path.join(GUIUtility.getInstance().vwxGUI_path, 'images', icon), wx.BITMAP_TYPE_ANY))
            self.icon.SetCursor(wx.StockCursor(wx.CURSOR_HAND))
        elif icon_type:
            self.icon = wx.StaticBitmap(parent, bitmap = NativeIcon.getInstance().getBitmap(parent, self.icon_type, parent.GetBackgroundColour(), state=0))
        else:
            self.icon = None

        if self.icon and icon_align == wx.ALIGN_LEFT:
            self.Add(self.icon, 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 3)
            
        normalfont = parent.GetFont()
        normalfont.SetPointSize(normalfont.GetPointSize() + font_increment)

        selectedfont = parent.GetFont()
        selectedfont.SetPointSize(normalfont.GetPointSize() + font_increment)
        selectedfont.SetUnderlined(True)

        self.text = LinkText(parent, text, fonts = [normalfont, selectedfont], colours = [font_colour, (255, 0, 0, 255)], parentsizer = self)
        self.Add(self.text, 1, wx.ALIGN_CENTER_VERTICAL)
        
        if self.icon and icon_align == wx.ALIGN_RIGHT:
            self.Add(self.icon, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RESERVE_SPACE_EVEN_IF_HIDDEN, 3)
        
        if self.icon and text == '':
            self.icon.Hide()
        
        self.SetCursor(wx.StockCursor(wx.CURSOR_HAND))
        if parent.GetBackgroundStyle() != wx.BG_STYLE_SYSTEM:
            self.SetBackgroundColour(parent.GetBackgroundColour())
        
    def SetToolTipString(self, tip):
        self.text.SetToolTipString(tip)
        if self.icon:
            self.icon.SetToolTipString(tip)
        
    def SetLabel(self, text):
        if text != self.text.GetLabel():
            if self.icon:
                self.icon.Show(text != '')
            
            self.text.SetLabel(text)
            if self.icon and self.icon_align == wx.ALIGN_RIGHT:
                self.text.SetMaxSize((self.text.GetBestSize()[0], -1))    
            
            self.Layout()
    
    def GetLabel(self):
        return self.text.GetLabel()
    
    def SetFont(self, font):
        self.text.SetFont(font)
    
    def GetFont(self):
        return self.text.GetFont()
    
    def Show(self, show):
        if self.icon: self.icon.Show(show)
        if self.text: self.text.Show(show)        
    
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
            
    def SetMinSize(self, minsize):
        self.text.SetMinSize(minsize)
        self.Layout()
    
    def HighLight(self, timeout = 2.0):
        self.SetBackgroundColour(LIST_HIGHTLIGHT, blink=True)
        wx.CallLater(timeout * 1000, self.Revert)
        
    def Revert(self):
        self.SetBackgroundColour(self.originalColor, blink=True)
    
    def Blink(self):
        self.HighLight(0.15)
        wx.CallLater(300, self.HighLight, 0.15)
        
    def SetCursor(self, cursor):
        if self.icon:
            self.icon.SetCursor(cursor)
            
    def ClientToScreen(self, pt):
        if self.icon and self.icon_align != wx.ALIGN_RIGHT:
            return self.icon.ClientToScreen(pt)
        return self.text.ClientToScreen(pt)
        
    def Bind(self, event, handler, source=None, id=-1, id2=-1):
        def modified_handler(actual_event, handler=handler):
            actual_event.SetEventObject(self)
            handler(actual_event)
            
        self.text.Bind(event, modified_handler, source, id, id2)
        if self.icon:
            self.icon.Bind(event, modified_handler, source, id, id2)
            
    def Unbind(self, event):
        self.text.Unbind(event)
        if self.icon:
            self.icon.Unbind(event)
            
    def SetBackgroundColour(self, colour, blink = False):
        if not blink:
            self.originalColor = colour
        self.text.SetBackgroundColour(colour)
        
        if self.icon and self.icon_type:
            self.icon.SetBitmap(NativeIcon.getInstance().getBitmap(self.parent, self.icon_type, colour, state=0))
            self.icon.Refresh()

    def SetForegroundColour(self, colour):
        colours = self.text.GetColours()
        colours[0] = colour
        self.text.SetColours(colours)
        font = self.GetFont()
        if self.text.enter:
            self.text.SetFontColour(font, colours[1])
        else:
            self.text.SetFontColour(font, colours[0])


class ProgressStaticText(wx.Panel):
    def __init__(self, parent, text, progress):
        wx.Panel.__init__(self, parent, style = wx.NO_BORDER)
        self.SetBackgroundColour(parent.GetBackgroundColour())
        
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.text = wx.StaticText(self, -1, text)
        sizer.Add(self.text, 0, wx.ALIGN_CENTER_VERTICAL)

        sizer.AddStretchSpacer()
        
        self.gauge = VerticalGauge(self, progress, (7, -1))
        sizer.Add(self.gauge)
        
        self.SetSize((-1, self.text.GetBestSize()[1]))
        self.SetSizer(sizer)
    
    def SetProgress(self, progress):
        self.gauge.SetProgress(progress)

class VerticalGauge(wx.Panel):
    def __init__(self, parent, progress, size = wx.DefaultSize):
        wx.Panel.__init__(self, parent, size = size, style = wx.NO_BORDER)
        self.SetBackgroundColour(parent.GetBackgroundColour())
        
        self.progress = progress
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
        
    def SetProgress(self, progress):
        self.progress = progress
        self.Refresh()
    
    def OnPaint(self, event):
        dc = wx.BufferedPaintDC(self)
        
        dc.SetBackground(wx.WHITE_BRUSH)
        dc.Clear()
        
        width, height = self.GetClientSize()

        barHeight = self.progress * height
            
        dc.SetPen(wx.TRANSPARENT_PEN)
        dc.SetBrush(wx.Brush(LIST_LIGHTBLUE))
        dc.DrawRectangle(0, height - barHeight, width, height)
        
        dc.SetPen(wx.BLACK_PEN)
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.DrawRectangle(0, 0, width, height)
        
    def OnEraseBackground(self, event):
        pass
    
class HorizontalGauge(wx.Control):
    def __init__(self, parent, background, bitmap, repeat = 1, bordersize = 0, size = wx.DefaultSize):
        wx.Control.__init__(self, parent, size = size, style = wx.NO_BORDER)
        
        self.background = background
        self.bitmap = bitmap
        self.repeat = repeat
        self.bordersize = bordersize
        self.percentage = 0
        self.hasBGColour = False
        
        if size == wx.DefaultSize:
            size = background.GetSize()
            self.SetMinSize((size.width * repeat, size.height))
            
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
    
    def SetPercentage(self, percentage):
        self.percentage = percentage
        self.Refresh()
    
    def SetBackgroundColour(self, colour):
        self.hasBGColour = True
        return wx.Control.SetBackgroundColour(self, colour)
        
    def OnPaint(self, event):
        dc = wx.PaintDC(self)
        if self.hasBGColour:
            dc.SetBackground(wx.Brush(self.GetBackgroundColour()))
            dc.Clear()
        
        bitmapWidth, bitmapHeight = self.bitmap.GetSize()
        
        width, height = self.GetClientSize()
        width -= self.bordersize * 2
        width = min(width, self.repeat * bitmapWidth)
        
        xpos = self.bordersize
        ypos = (height - bitmapHeight) / 2
        
        for i in range(self.repeat):
            dc.DrawBitmap(self.background, xpos + (i * bitmapWidth), ypos, True)

        dc.SetClippingRegion(xpos, ypos, width * self.percentage, bitmapHeight)
        for i in range(self.repeat):
            dc.DrawBitmap(self.bitmap, xpos + (i * bitmapWidth), ypos, True)
        
    def OnEraseBackground(self, event):
        pass
            
class EditText(wx.TextCtrl):
    def __init__(self, parent, text, multiLine = False):
        style = 0
        if multiLine:
            style = style | wx.TE_MULTILINE
            
        wx.TextCtrl.__init__(self, parent, -1, text, style = style)
        self.original_text = text
    
    def SetValue(self, value):
        wx.TextCtrl.SetValue(self, value)
        self.original_text = value
    
    def IsChanged(self):
        return self.original_text != self.GetValue()
    
    def Saved(self):
        self.original_text = self.GetValue()

    def GetChanged(self):
        if self.IsChanged():
            return self.GetValue()
            
class EditStaticText(wx.Panel):
    def __init__(self, parent, text, multiLine = False):
        wx.Panel.__init__(self, parent, style = wx.NO_BORDER)
        self.original_text = text
        
        vSizer = wx.BoxSizer(wx.VERTICAL)
        self.text = wx.StaticText(self, -1, text)
        self.text.SetMinSize((1, -1))
        vSizer.Add(self.text, 0, wx.EXPAND)
        
        self.edit = EditText(parent, text, multiLine)
        self.edit.Show(False)
        self.edit.SetMinSize((1, -1))
        vSizer.Add(self.edit, 0, wx.EXPAND)
        self.SetSizer(vSizer)
    
    def ShowEdit(self, show = True):
        if not show:
            self.text.SetLabel(self.edit.GetValue())
        
        self.text.Show(not show)
        self.edit.Show(show)
        self.GetParent().Layout()
    
    def IsEditShown(self):
        return self.edit.IsShown()
        
    def IsChanged(self):
        return self.edit.IsChanged()
    
    def Saved(self):
        self.edit.Saved()

    def GetChanged(self):
        return self.edit.GetChanged()
    
class NotebookPanel(wx.Panel):
    def __init__(self, *args, **kwargs):
        wx.Panel.__init__(self, *args, **kwargs)
        self.SetForegroundColour(self.GetParent().GetForegroundColour())
        
        self.sizer = wx.BoxSizer()
        self.SetSizer(self.sizer)
    
    def SetList(self, list, spacer = 0):
        self.list = list
        self.list.IsShownOnScreen = self.IsShownOnScreen
        self.sizer.Add(list, 1, wx.EXPAND|wx.ALL, spacer)
    
    def IsShownOnScreen(self):
        notebook = self.GetParent()
        page = notebook.GetCurrentPage()
        return page == self
    
    def __getattr__(self, name):
        try:
            wx.Panel.__getattr__(self, name)
        except:
            return getattr(self.list, name)
        
    def Show(self, show=True,isSelected=False):
        wx.Panel.Show(self, show)
        self.list.Show(show, isShown=isSelected)
        if show:
            self.Layout()
            
    def Focus(self):
        self.list.Focus()
        
    def Reset(self):
        self.list.Reset()
        
    def SetupScrolling(self, scroll_x=True, scroll_y=True, rate_x=20, rate_y=20, scrollToTop=True):
        if hasattr(self.list, 'SetupScrolling'):
            self.list.SetupScrolling(scroll_x, scroll_y, rate_x, rate_y, scrollToTop)

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
    def __init__(self, parent, style = wx.LC_REPORT|wx.LC_NO_HEADER|wx.NO_BORDER, tooltip = True):
        BetterListCtrl.__init__(self, parent, style, tooltip)
        self.allselected = False
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
                self.doSelectAll()
    
    def doSelectAll(self):
        for index in xrange(self.GetItemCount()):
            if self.allselected:
                self.Select(index, 0)
            else:
                self.Select(index, 1)
        self.allselected = not self.allselected
                
class CheckSelectableListCtrl(SelectableListCtrl, CheckListCtrlMixin):
    def __init__(self, parent, style = wx.LC_REPORT|wx.LC_NO_HEADER|wx.NO_BORDER, tooltip = True):
        SelectableListCtrl.__init__(self, parent, style, tooltip)
        CheckListCtrlMixin.__init__(self)
        
    def IsSelected(self, index):
        return self.IsChecked(index)
    
    def GetSelectedItems(self):
        selected = []
        for index in xrange(self.GetItemCount()):
            if self.IsChecked(index):
                selected.append(index)
        return selected
    
    def doSelectAll(self):
        for index in xrange(self.GetItemCount()):
            if self.allselected:
                self.CheckItem(index, False)
            else:
                self.CheckItem(index, True)
        self.allselected = not self.allselected
        
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

        self.text = ""
        self.choices = []
        self.screenheight = wx.SystemSettings.GetMetric(wx.SYS_SCREEN_Y)
         
        self.dropdown = wx.PopupWindow(self)
        self.dropdown.SetBackgroundColour(DEFAULT_BACKGROUND)
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
                def wx_callback(delayedResult, text):
                    choices = delayedResult.get()
                    if text == self.text:
                        self.SetChoices(choices)
                        if len(self.choices) == 0:
                            self.ShowDropDown(False)
                        else:
                            self.ShowDropDown(True)
    
                def db_callback(text):
                    if text == self.text:
                        return self.entrycallback(text)
                startWorker(wx_callback, db_callback, cargs = (text,), wargs = (text, ))

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
        
    
class ChannelPopularity(wx.Panel):
    def __init__(self, parent, background, bitmap, bordersize = 0, size = wx.DefaultSize):
        self.background = background
        self.bitmap = bitmap
        self.bordersize = bordersize
        
        if size == wx.DefaultSize:
            size = self.bitmap.GetSize()
            size = size[0] * 5, size[1]
            
        wx.Panel.__init__(self, parent, size = size, style = wx.NO_BORDER)
        
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
    
    def SetVotes(self, votes):
        self.votes = votes
        self.Refresh()
    
    def OnPaint(self, event):
        dc = wx.BufferedPaintDC(self)
        
        dc.SetBackground(wx.Brush(self.GetBackgroundColour()))
        dc.Clear()
        
        bitmapWidth, bitmapHeight = self.bitmap.GetSize()
        
        width, height = self.GetClientSize()
        width -= self.bordersize * 2
        width = min(width, 5 * bitmapWidth)
        
        xpos = self.bordersize
        ypos = (height - bitmapHeight) / 2

        for i in range(5):
            dc.DrawBitmap(self.background, xpos + (i * bitmapWidth), ypos, True)

        dc.SetClippingRegion(xpos, ypos, width * self.votes, bitmapHeight)
        for i in range(5):
            dc.DrawBitmap(self.bitmap, xpos + (i * bitmapWidth), ypos, True)
    
    def OnEraseBackground(self, event):
        pass
    
    
class SwarmHealth(wx.Panel):
    def __init__(self, parent, bordersize = 0, size = wx.DefaultSize, align = wx.ALIGN_LEFT):
        wx.Panel.__init__(self, parent, size = size, style = wx.NO_BORDER)
        self.bordersize = bordersize
        self.align = align
        
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
    
    def SetRatio(self, seeders, leechers):
        ratio = 0
        pop = 0
        
        self.blue = 0
        if leechers <= 0 and seeders <= 0:
            self.barwidth = 0
            
            self.green = 0
            self.red = 0
        else:
            if leechers == 0:
                ratio = sys.maxint
            elif seeders == 0:
                ratio = 0
            else:
                ratio = seeders/(leechers*1.0)
            
            if ratio == 0:
                self.barwidth = 1
                self.green = 0
                self.red = 0
            else:
                pop = seeders + leechers
                if pop > 0:

                    self.barwidth = min(max(math.log(pop*4,10) * 2, 1.1) / 10.0, 1) #let it max at 25k population
                else:
                    self.barwidth = 1
                
                self.green = max(0, min(255, 125 + (ratio * 130)))
                self.red = max(0, min(255, 125 + ((1 - ratio) * 130)))
        self.Refresh()

        if seeders < 0:
            seeders_str = 'Unknown number of seeders'
        elif seeders == 1:
            seeders_str = '1 seeder'
        else:
            seeders_str = '%d seeders' % seeders
        
        if leechers < 0:
            leechers_str = 'unknown number of leechers'
        elif leechers == 1:
            leechers_str = '1 leecher'
        else:
            leechers_str = '%d leechers' % seeders
            
        tooltip = '%s ; %s' % (seeders_str, leechers_str)
        self.SetToolTipString(tooltip)
        
    def OnPaint(self, event):
        dc = wx.BufferedPaintDC(self)
        
        dc.SetBackground(wx.Brush(self.GetBackgroundColour()))
        dc.Clear()
        
        width, height = self.GetClientSize()
        width -= self.bordersize * 2
        width -= 1
        width -= width % 10
        width += 1
        
        if self.align == wx.ALIGN_CENTER:
            xpos = (self.GetClientSize()[0] - width) / 2
        elif self.align == wx.ALIGN_RIGHT:
            xpos = self.GetClientSize()[0] - width
        else:
            xpos = 0
            
        dc.SetPen(wx.Pen(self.GetParent().GetForegroundColour()))
        dc.SetBrush(wx.WHITE_BRUSH)
        dc.DrawRectangle(xpos, 0, width, height)
                
        dc.SetPen(wx.TRANSPARENT_PEN)
        
        dc.SetBrush(wx.Brush((self.red, self.green, self.blue), wx.SOLID))
        
        if self.barwidth > 0:
            dc.DrawRectangle(xpos + 1, 1,  self.barwidth * (width - 2), height-2)
        
        if self.green > 0 or self.red > 0:
            dc.SetPen(wx.WHITE_PEN)
            for i in range(1,10):
                x = xpos + (width/10) * i
                dc.DrawLine(x, 1, x, height - 1)
        
        dc.SetPen(wx.BLACK_PEN)
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.DrawRectangle(xpos, 0, width, height)

    def OnEraseBackground(self, event):
        pass
        
        
def _set_font(control, size_increment = 0, fontweight = wx.FONTWEIGHT_NORMAL, fontcolour = None):
    font = control.GetFont()
    font.SetPointSize(font.GetPointSize() + size_increment)
    font.SetWeight(fontweight)
    control.SetFont(font)
    if fontcolour:
        control.SetForegroundColour(fontcolour)
    

class ActionButton(wx.Panel):
    def __init__(self, parent, id=-1, bitmap=wx.NullBitmap, **kwargs):
        wx.Panel.__init__(self, parent, id, size = bitmap.GetSize(), **kwargs)
        image = bitmap.ConvertToImage()
        self.bitmaps = [bitmap]
        self.bitmaps.append(wx.BitmapFromImage(image.AdjustChannels(1.0, 1.0, 1.0, 0.6)))
        self.bitmaps.append(wx.BitmapFromImage(image.ConvertToGreyscale().AdjustChannels(1.0, 1.0, 1.0, 0.3)))
        self.enabled = True
        self.handler = None
        self.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouseAction)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_CHILD_FOCUS, self.OnFocus)

    def OnEraseBackground(self, event):
        pass

    def OnPaint(self, event):
        width, height = self.GetClientSizeTuple()
        buffer = wx.EmptyBitmap(width, height)
        # Use double duffered drawing to prevent flickering
        dc = wx.BufferedPaintDC(self, buffer)
        if not getattr(self.GetParent(), 'bitmap', None):
            # Draw the background using the backgroundcolour from the parent
            dc.SetBackground(wx.Brush(self.GetParent().GetBackgroundColour()))
            dc.Clear()
        else:
            # Draw the background using the bitmap from the parent (TopSearchPanel)
            rect = self.GetRect().Intersect(wx.Rect(0, 0, *self.GetParent().bitmap.GetSize()))
            sub = self.GetParent().bitmap.GetSubBitmap(rect) 
            dc.DrawBitmap(sub, 0, 0)
        # Draw the button to the buffer
        dc.DrawBitmap(self.GetBitmap(), 0, 0)

    def OnMouseAction(self, event):
        if event.Entering() or event.Leaving():
            self.Refresh()
        event.Skip()

    def OnFocus(self, event):
        self.Refresh()

    def GetBitmap(self):
        if not self.IsEnabled():
            return self.bitmaps[2]
        if self.GetScreenRect().Contains(wx.GetMousePosition()):
            return self.bitmaps[1]
        return self.bitmaps[0]

    def Bind(self, event, handler, **kwargs):
        if event == wx.EVT_LEFT_UP:
            self.handler = handler
        wx.Panel.Bind(self, event, handler, **kwargs)

    def Enable(self, enable):
        if enable and self.handler:
            self.Bind(wx.EVT_LEFT_UP, self.handler)
        elif not enable:
            self.Unbind(wx.EVT_LEFT_UP)
        self.enabled = enable
        self.Refresh()

    def IsEnabled(self):
        return self.enabled


class ProgressButton(ActionButton):
    def __init__(self, parent, id=-1, label = 'Search', **kwargs):
        ActionButton.__init__(self, parent, id = id, bitmap = wx.EmptyBitmap(1,1), **kwargs)
        self.icon    = None
        self.icon_hl = None
        self.icon_gs = None
        self.label   = label
        self.maxval  = 25
        self.curval  = 25
        self.ResetSize()

    def GetRange(self):
        return self.maxval

    def SetRange(self, maximum):
        self.maxval = maximum
        self.Refresh()

    def GetValue(self):
        return self.curval

    def SetValue(self, current):
        self.curval = current
        self.Refresh()
        
    def SetIcon(self, icon):
        if isinstance(icon, wx.Bitmap):
            self.icon = icon
            self.icon_hl = icon.ConvertToImage().AdjustChannels(1.0, 1.0, 1.0, 0.6).ConvertToBitmap()
            self.icon_gs = icon.ConvertToImage().ConvertToGreyscale().ConvertToBitmap()
            self.ResetSize()
    
    def ResetSize(self):
        w, h = self.GetTextExtent(self.label)
        w += 30
        h += 10
        if self.icon:
            w = w+self.icon.GetSize()[0]+5
            h = max(h, self.icon.GetSize()[1])
        self.SetMinSize((w, h))

    def OnPaint(self, event):
        dc = wx.BufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        # Draw the background using the bitmap from the parent (if it exists)
        if not getattr(self.GetParent(), 'bitmap', None):
            # Draw the background using the backgroundcolour from the parent
            dc.SetBackground(wx.Brush(self.GetParent().GetBackgroundColour()))
            dc.Clear()
        else:
            # Draw the background using the bitmap from the parent (TopSearchPanel)
            rect = self.GetRect().Intersect(wx.Rect(0, 0, *self.GetParent().bitmap.GetSize()))
            try:
                sub = self.GetParent().bitmap.GetSubBitmap(rect) 
                dc.DrawBitmap(sub, 0, 0)
            except:
                pass
        x, y, width, height = self.GetClientRect()
        # If there is currently something in progress, first paint a black&white background
        if self.curval != self.maxval:
            col1 = wx.Colour(199,199,199)
            col2 = wx.Colour(162,162,162)
            br = gc.CreateLinearGradientBrush(x, y, x, y+height, col1, col2)
            gc.SetBrush(br)
            gc.SetPen(wx.TRANSPARENT_PEN)
            path = gc.CreatePath()
            path.AddRoundedRectangle(x, y, width-1, height-1, 5)
            path.CloseSubpath()
            gc.DrawPath(path)
        # Depending on the state of the button, paint the progress made thus far
        highlight = self.GetScreenRect().Contains(wx.GetMousePosition())
        if not self.IsEnabled():
            col1 = wx.Colour(199,199,199)
            col2 = wx.Colour(162,162,162)
        elif highlight:
            col1 = wx.Colour(255,169,148)
            col2 = wx.Colour(255,150,127)
        else:
            col1 = GRADIENT_LRED
            col2 = GRADIENT_DRED
        br = gc.CreateLinearGradientBrush(x, y, x, y+height, col1, col2)
        gc.SetBrush(br)
        gc.SetPen(wx.TRANSPARENT_PEN)
        path = gc.CreatePath()
        if self.curval > 1:
            progress = max(self.curval*1.0/self.maxval, 0.15)
            path.AddRoundedRectangle(x, y, progress*width-1, height-1, 5)
            path.CloseSubpath()
            gc.DrawPath(path)
        # Draw the button label and icon (if any)
        font = self.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        dc.SetFont(font)
        dc.SetTextForeground(wx.WHITE)
        textWidth, textHeight = dc.GetFullTextExtent(self.label)[:2]
        if self.icon:
            x_icon = ( width-textWidth-self.icon.GetSize()[0]-5 ) / 2
            y_icon = ( height-self.icon.GetSize()[1] ) / 2
            if highlight:
                dc.DrawBitmap(self.icon_hl, x_icon, y_icon)
            elif not self.IsEnabled():
                dc.DrawBitmap(self.icon_gs, x_icon, y_icon)
            else:
                dc.DrawBitmap(self.icon, x_icon, y_icon)
            x = x_icon+5+self.icon.GetSize()[0]
            y = (height-textHeight)/2
            dc.DrawText(self.label, x, y)
        else:
            x = (width-textWidth)/2
            y = (height-textHeight)/2
            dc.DrawText(self.label, x, y)


class GradientPanel(wx.Panel):

    def __init__(self, *args, **kwargs):
        self.border = kwargs.pop('border', 0)
        self.colour1 = kwargs.pop('colour1', GRADIENT_LGREY)
        self.colour2 = kwargs.pop('colour2', GRADIENT_DGREY)
        wx.Panel.__init__(self, *args, **kwargs)
        self.bitmap = wx.EmptyBitmap(*self.GetClientSizeTuple())
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
        
    def OnEraseBackground(self, event):
        pass

    def OnPaint(self, event):
        x, y, width, height = self.GetClientRect()
        buffer = wx.EmptyBitmap(width, height)
        dc = wx.BufferedPaintDC(self, buffer)
        gc = wx.GraphicsContext.Create(dc)
        gc.SetPen(wx.TRANSPARENT_PEN)
        br = gc.CreateLinearGradientBrush(x, y, x, y+height, self.colour1, self.colour2)
        gc.SetBrush(br)
        path = gc.CreatePath()
        path.AddRectangle(x, y, width, height)
        path.CloseSubpath()
        gc.DrawPath(path)
        dc.SetPen(wx.Pen(SEPARATOR_GREY, 1, wx.SOLID))
        if bool(self.border & wx.RIGHT):
            dc.DrawLine(x+width-1, y, x+width-1, y+height-1)
        if bool(self.border & wx.LEFT):
            dc.DrawLine(x, y, x, y+height-1)
        if bool(self.border & wx.TOP):
            dc.DrawLine(x, y, x+width-1, y)
        if bool(self.border & wx.BOTTOM):
            dc.DrawLine(x, y+height-1, x+width-1, y+height-1)
        self.bitmap = buffer
        

class RoundedPanel(wx.Panel):

    def __init__(self, *args, **kwargs):
        self.border_colour = kwargs.pop('border_colour', None)
        wx.Panel.__init__(self, *args, **kwargs)
        self.focus = False
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
        self.Bind(wx.EVT_CHILD_FOCUS, self.OnSetFocus)
        self.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocus)
        self.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouseAction)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)

    def OnEraseBackground(self, event):
        pass

    def OnSetFocus(self, event):
        self.focus = True
        self.Refresh()
 
    def OnKillFocus(self, event):
        self.focus = False
        self.Refresh()

    def OnMouseAction(self, event):
        if event.Entering() or event.Leaving():
            self.Refresh()
        event.Skip()

    def OnPaint(self, event):
        dc = wx.BufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.GetBackgroundColour()))
        dc.Clear()
        if getattr(self.GetParent(), 'bitmap', None):
            rect = self.GetRect().Intersect(wx.Rect(0, 0, *self.GetParent().bitmap.GetSize()))
            sub = self.GetParent().bitmap.GetSubBitmap(rect) 
            dc.DrawBitmap(sub, 0, 0)
        gc = wx.GraphicsContext.Create(dc)
        x, y, width, height = self.GetClientRect()
        gc.SetBrush(wx.Brush(self.GetBackgroundColour()))
        if not self.border_colour:
            if self.focus:
                gc.SetPen(wx.Pen(GRADIENT_LRED, 1, wx.SOLID))
            elif self.GetScreenRect().Contains(wx.GetMousePosition()):
                gc.SetPen(wx.Pen(AdjustColour(SEPARATOR_GREY, -10), 1, wx.SOLID))
            else:
                gc.SetPen(wx.Pen(SEPARATOR_GREY, 1, wx.SOLID))
        else:
            gc.SetPen(wx.Pen(self.border_colour, 1, wx.SOLID))
        path = gc.CreatePath()
        path.AddRoundedRectangle(x, y, width-1, height-1, 5)
        path.CloseSubpath()
        gc.DrawPath(path)
            

class DottedBetterText(BetterText):
    def __init__(self, parent, id, label, *args, **kwargs):
        wx.StaticText.__init__(self, parent, id, label, *args, **kwargs)
        if label:
            self.SetLabel(label)
            
    def SetLabel(self, text):
        if text:
            text = self.DetermineText(text, self.GetSize()[0])
        wx.StaticText.SetLabel(self, text)
            
    def DetermineText(self, text, maxWidth):
        for i in xrange(len(text), 0, -1):
            newText = text[0:i]
            if i != len(text):
                newText += ".."
            width, _ = self.GetTextExtent(newText)
            if width <= maxWidth:
                return newText

            
class MinMaxSlider(wx.Panel):
    
    def __init__(self, *args, **kwargs):
        wx.Panel.__init__(self, *args, **kwargs)
        self.SetBackgroundColour(self.GetParent().GetBackgroundColour())
        self.base = 1.7
        self.LoadIcons()
        self.SetMinMax(0, 0)
        self.text_spacers = [60, 60]
        self.Reset()
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.Bind(wx.EVT_LEFT_UP, self.OnLeftUp)
        
    def SetMinMax(self, min, max):
        if max < min:
            return
        self.min = min
        self.max = max
        self.Refresh()
        
    def GetMinMax(self):
        return (self.min, self.max)
    
    def SetCurrentValues(self, min_val, max_val):
        if self.max - self.min == 0 or min_val == 0:
            w, h = self.arrow_up.GetSize()
            self.arrow_up_rect = [self.range[0], self.GetClientRect()[3]/2+1, w, h]
        else:
            length = self.range[1] - self.range[0]
            min_val = (min_val-self.min) / float(self.max-self.min)
            min_val = min_val*math.pow(length, self.base)            
            self.arrow_up_rect[0] = math.exp((math.log(min_val) / self.base)) + self.range[0]            
    
        if self.max - self.min == 0 or max_val == 0:       
            w, h = self.arrow_down.GetSize()
            self.arrow_down_rect = [self.range[1], self.GetClientRect()[3]/2-h-1, w, h]    
        else:
            length = self.range[1] - self.range[0]
            max_val = (max_val-self.min) / float(self.max-self.min)
            max_val = max_val*math.pow(length, self.base)
            self.arrow_down_rect[0] = math.exp((math.log(max_val) / self.base)) + self.range[0]
        
        self.Refresh()
    
    def GetCurrentValues(self):
        length = self.range[1] - self.range[0]
        min_val = math.pow(self.arrow_up_rect[0]-self.range[0], self.base) / math.pow(length, self.base)
        max_val = math.pow(self.arrow_down_rect[0]-self.range[0], self.base) / math.pow(length, self.base)
        min_val = self.min + min_val*(self.max-self.min)
        max_val = self.min + max_val*(self.max-self.min)
        return (min_val, max_val)

    def OnLeftDown(self, event):
        if wx.Rect(*self.arrow_down_rect).Contains(event.GetPositionTuple()):
            self.arrow_down_drag = True
        if wx.Rect(*self.arrow_up_rect).Contains(event.GetPositionTuple()):
            self.arrow_up_drag = True
        self.Bind(wx.EVT_MOTION, self.OnMotion)

    def OnLeftUp(self, event):
        self.arrow_down_drag = False
        self.arrow_up_drag = False
        self.Unbind(wx.EVT_MOTION)
        #Call parent
        min_val, max_val = self.GetCurrentValues()
        self.GetParent().GetParent().OnSlider(min_val, max_val)

    def OnMotion(self, event):
        if event.LeftIsDown():
            self.SetIcon(event)
        
    def SetIcon(self, event):
        mx = event.GetPositionTuple()[0]
        if self.arrow_up_drag and mx < self.arrow_down_rect[0]:
            self.arrow_up_rect[0] = max(mx, self.range[0])
        elif self.arrow_down_drag and mx > self.arrow_up_rect[0]:
            self.arrow_down_rect[0] = min(mx, self.range[1])
        self.Refresh()
        
    def LoadIcons(self):
        self.arrow_down = NativeIcon.getInstance().getBitmap(self, 'arrow', self.GetBackgroundColour(), state=0)
        img = self.arrow_down.ConvertToImage()
        self.arrow_up = img.Rotate90().Rotate90().ConvertToBitmap()
        
    def Reset(self):
        w, h = self.arrow_down.GetSize()
        self.range = [self.text_spacers[0], self.GetSize()[0]-w-self.text_spacers[1]]
        self.arrow_down_rect = [self.range[1], self.GetClientRect()[3]/2-h-1, w, h]
        self.arrow_down_drag = False
        self.arrow_up_rect = [self.range[0], self.GetClientRect()[3]/2+1, w, h]
        self.arrow_up_drag = False
        
    def SetFormatter(self, formatter):
        self.formatter = formatter
        
    def Format(self, i):
        return self.formatter(i)

    def OnEraseBackground(self, event):
        pass

    def OnPaint(self, event):
        dc = wx.BufferedPaintDC(self)
        bg_colour = self.GetBackgroundColour()
        fg_colour = self.GetForegroundColour()
        dc.SetBackground(wx.Brush(bg_colour))
        dc.SetTextForeground(fg_colour)
        dc.Clear()
        
        _, _, width, height = self.GetClientRect()
        min_val, max_val = self.GetCurrentValues()
        min_val = self.Format(min_val)
        max_val = self.Format(max_val)
        dc.SetFont(self.GetFont())
        text_height = dc.GetTextExtent(min_val)[1]
        dc.DrawText(min_val, 0, (height-text_height)/2)
        text_width, text_height = dc.GetTextExtent(max_val)
        dc.DrawText(max_val, width-text_width, (height-text_height)/2)
        
        dc.SetPen(wx.Pen(fg_colour, 2, wx.SOLID))
        dc.DrawLine(self.range[0], height/2, self.range[1]+self.arrow_down.GetSize()[0], height/2)

        gc = wx.GraphicsContext.Create(dc)        
        gc.DrawBitmap(self.arrow_down, *self.arrow_down_rect)
        gc.DrawBitmap(self.arrow_up, *self.arrow_up_rect)
        

class SimpleNotebook(wx.Panel):
    
    def __init__(self, *args, **kwargs):
        wx.Panel.__init__(self, *args, **kwargs)
        self.ad     = None
        self.labels = []
        self.panels = []
        self.pshown = None
        self.lspace = 10
        self.hSizer_labels = wx.BoxSizer(wx.HORIZONTAL)
        self.hSizer_panels = wx.BoxSizer(wx.HORIZONTAL)
        self.hSizer_panel = wx.Panel(self, -1)
        self.hSizer_panel.SetSizer(self.hSizer_labels)
        self.hSizer_panel.SetBackgroundColour(FILTER_GREY)
        self.hSizer_panel.SetMinSize((-1,25))
        vSizer = wx.BoxSizer(wx.VERTICAL)
        separator = wx.Panel(self, size = (-1, 1))
        separator.SetBackgroundColour(SEPARATOR_GREY)
        vSizer.Add(separator, 0, wx.EXPAND)
        vSizer.Add(self.hSizer_panel, 0, wx.EXPAND)
        separator = wx.Panel(self, size = (-1, 1))
        separator.SetBackgroundColour(SEPARATOR_GREY)
        vSizer.Add(separator, 0, wx.EXPAND)
        vSizer.Add(self.hSizer_panels, 1, wx.EXPAND)
        self.SetSizer(vSizer)
        
    def OnLeftUp(self, event):
        obj = event.GetEventObject()
        for index, control in enumerate(self.hSizer_labels.GetChildren()):
            if getattr(control, 'IsSizer', False) and control.GetSizer() == obj:
                self.SetSelection(index/2)
                self.hSizer_panel.Refresh()
                break
            
    def GetPage(self, num_page):
        if num_page >= 0 and num_page < self.GetPageCount():
            return self.panels[num_page]
        return None 
        
    def AddPage(self, page, text, select = True):
        label = LinkStaticText(self.hSizer_panel, text, None, font_colour=wx.BLACK)
        label.Bind(wx.EVT_LEFT_UP, self.OnLeftUp)
        sline = wx.StaticLine(self.hSizer_panel, -1, style=wx.LI_VERTICAL)
        self.hSizer_labels.Add(label, 0, wx.RIGHT|wx.LEFT|wx.CENTER, self.lspace)
        self.hSizer_labels.Add(sline, 0, wx.EXPAND|wx.ALL|wx.CENTER|wx.TOP|wx.BOTTOM, 5)
        page.Show(False)
        index = len(self.hSizer_panels.GetChildren())-1 if self.ad else len(self.hSizer_panels.GetChildren())
        self.hSizer_panels.Insert(index, page, 100, wx.EXPAND)
        self.labels.append(label)
        self.panels.append(page)
        if select or not self.GetCurrentPage():
            self.SetSelection(self.GetPageCount()-1)
        else:
            self.Layout()
    
    def InsertPage(self, index, page, text, select = True):
        if not ( index >= 0 and index < self.GetPageCount() ):
            return
        label = LinkStaticText(self.hSizer_panel, text, None, font_colour=wx.BLACK)
        label.Bind(wx.EVT_LEFT_UP, self.OnLeftUp)
        sline = wx.StaticLine(self.hSizer_panel, -1, style=wx.LI_VERTICAL)
        self.hSizer_labels.Insert(index*2, label, 0, wx.RIGHT|wx.LEFT|wx.CENTER, self.lspace)
        self.hSizer_labels.Insert(index*2+1, sline, 0, wx.EXPAND|wx.CENTER|wx.TOP|wx.BOTTOM, 5)
        page.Show(False)
        szr_index = index-1 if self.ad else index
        self.hSizer_panels.Insert(szr_index, page, 100, wx.EXPAND)
        self.labels.insert(index, label)
        self.panels.insert(index, page)
        if select or not self.GetCurrentPage():
            self.SetSelection(self.GetPageCount()-1)
        else:
            self.Layout()
    
    def RemovePage(self, index):
        pass
    
    def GetPageText(self, num_page):
        if num_page >= 0 and num_page < self.GetPageCount():
            return self.labels[num_page].GetLabel()
        return ''
    
    def SetPageText(self, num_page, text):
        if num_page >= 0 and num_page < self.GetPageCount():
            self.labels[num_page].SetLabel(text)
            self.Layout()

    def GetPageCount(self):
        return len(self.labels)
    
    def GetCurrentPage(self):
        if self.pshown != None:
            return self.GetPage(self.pshown)
        return None
    
    def SetSelection(self, num_page):
        if not ( num_page >= 0 and num_page < self.GetPageCount() ) or self.pshown == num_page:
            return
        old_page = self.GetCurrentPage()
        if old_page:
            old_page.Show(False)
            self.labels[self.pshown].SetForegroundColour(self.GetForegroundColour())
        self.labels[num_page].SetForegroundColour(TRIBLER_RED)
        self.panels[num_page].Show(True)
        self.pshown = num_page
        self.Layout()

    def ChangeSelection(self, num_page):
        self.SetSelection(num_page)
    
    def CalcSizeFromPage(self, *args):
        return GUIUtility.getInstance().frame.splitter_bottom_window.GetSize()
    
    def GetThemeBackgroundColour(self):
        return self.GetBackgroundColour()
    
    def SetAdSpace(self, panel):
        if self.ad:
            self.ad.Show(False)
            self.hSizer_panels.Replace(self.ad, panel)
            self.ad.Destroy()
        else:
            self.hSizer_panels.Add(panel, 0, wx.EXPAND)
        self.ad = panel
        panel.Show(True)
        self.Layout()


class TagText(wx.Panel):

    def __init__(self, parent, id=-1, label='', fill_colour = wx.Colour(240,255,204), edge_colour = wx.Colour(200,200,200), text_colour = wx.BLACK, **kwargs):
        wx.Panel.__init__(self, parent, id, **kwargs)
        self.fill_colour = fill_colour
        self.edge_colour = edge_colour
        self.text_colour = text_colour
        self.prnt_colour = parent.GetBackgroundColour()
        self.label = label
        w, h = self.GetTextExtent(self.label)
        w += 10
        self.SetMinSize((w, h))
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
        
    def SetValue(self, label):
        self.label = label
        w, h = self.GetTextExtent(self.label)
        w += 10
        self.SetMinSize((w, h))
        self.Refresh()
        
    def SetBackgroundColour(self, colour):
        self.prnt_colour = colour
        self.Refresh()

    def OnEraseBackground(self, event):
        pass

    def OnPaint(self, event):
        # Draw the background
        dc = wx.BufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.prnt_colour))
        dc.Clear()
        if getattr(self.GetParent(), 'bitmap', None):
            rect = self.GetRect().Intersect(wx.Rect(0, 0, *self.GetParent().bitmap.GetSize()))
            sub = self.GetParent().bitmap.GetSubBitmap(rect) 
            dc.DrawBitmap(sub, 0, 0)
            
        # Draw the rounded rectangle which will contain the text.
        gc = wx.GraphicsContext.Create(dc)
        x, y, width, height = self.GetClientRect()
        gc.SetBrush(wx.Brush(self.fill_colour))
        gc.SetPen(wx.Pen(self.edge_colour, 1, wx.SOLID))
        path = gc.CreatePath()
        path.AddRoundedRectangle(x, y, width-1, height-1, 5)
        path.CloseSubpath()
        gc.DrawPath(path)
        
        # Draw the text
        font =  self.GetFont()
        dc.SetFont(font)
        dc.SetTextForeground(self.text_colour)
        dc.DrawText(self.label, 5, 0)

        
class TorrentStatus(wx.Panel):

    def __init__(self, parent, id=-1, status='Initializing', fill_colour = wx.Colour(132,194,255), back_colour = wx.Colour(235,235,235), **kwargs):
        wx.Panel.__init__(self, parent, id, **kwargs)
        self.status      = status
        self.value       = None
        self.fill_colour = fill_colour
        self.back_colour = back_colour
        self.prnt_colour = parent.GetBackgroundColour()
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
        
    def SetMinSize(self, size):
        w, h = size
        if h == -1:
            h = self.GetTextExtent(self.status)[1]
        wx.Panel.SetMinSize(self, (w, h))
        
    def SetValue(self, value):
        if isinstance(value, float) or isinstance(value, int):
            self.value = float(value)

    def SetStatus(self, status):
        if isinstance(status, str):
            self.status = status
            
        if status == 'Seeding':
            self.fill_colour = SEEDING_COLOUR
        if status == 'Completed':
            self.fill_colour = COMPLETED_COLOUR
        if status == 'Waiting':
            self.fill_colour = self.back_colour
        if status == 'Checking':
            self.fill_colour = self.back_colour
        if status == 'Downloading':
            self.fill_colour = DOWNLOADING_COLOUR
        if status == 'Stopped':
            self.fill_colour = STOPPED_COLOUR
            
        self.SetMinSize((-1, -1))
            
    def SetBackgroundColour(self, colour):
        self.prnt_colour = colour
        self.Refresh()
            
    def Update(self, torrent):
        progress = torrent.progress
        torrent_state = torrent.state
        finished = progress == 1.0

        if 'seeding' in torrent_state:
            status = 'Seeding'
        elif finished:
            status = 'Completed'
        elif 'allocating' in torrent_state:
            status = 'Waiting'
        elif 'checking' in torrent_state:
            status = 'Checking'
        elif 'downloading' in torrent_state:
            status = 'Downloading'
        else:
            status = 'Stopped'
            
        self.SetValue(progress)
        self.SetStatus(status)
        self.Refresh()
        if self.value != None:
            return int(self.value*self.GetSize().width)
        return 0

    def OnEraseBackground(self, event):
        pass

    def OnPaint(self, event):
        # Draw the background
        dc = wx.BufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.prnt_colour))
        dc.Clear()
        if getattr(self.GetParent(), 'bitmap', None):
            rect = self.GetRect().Intersect(wx.Rect(0, 0, *self.GetParent().bitmap.GetSize()))
            sub = self.GetParent().bitmap.GetSubBitmap(rect) 
            dc.DrawBitmap(sub, 0, 0)
            
        # Draw an empty progress bar and text
        gc = wx.GraphicsContext.Create(dc)
        x, y, width, height = self.GetClientRect()
        gc.SetBrush(wx.Brush(self.back_colour))
        gc.SetPen(wx.TRANSPARENT_PEN)
        path = gc.CreatePath()
        path.AddRoundedRectangle(x, y, width, height, 2)
        path.CloseSubpath()
        gc.DrawPath(path)
        self.TextToDC(dc, self.TextColour(self.back_colour))
        
        if self.value != None:
            # Draw a full progress bar and text
            rect = wx.EmptyBitmap(width, height)
            rect_dc = wx.MemoryDC(rect)
            rect_dc.SetBackground(wx.Brush(self.prnt_colour))
            rect_dc.Clear()
            
            rect_gc = wx.GraphicsContext.Create(rect_dc)
            rect_gc.SetBrush(wx.Brush(self.fill_colour))
            rect_gc.SetPen(wx.TRANSPARENT_PEN)
            path = rect_gc.CreatePath()
            path.AddRoundedRectangle(x, y, width, height, 2)
            path.CloseSubpath()
            rect_gc.DrawPath(path)
            self.TextToDC(rect_dc, self.TextColour(self.fill_colour))
            
            # Combine the two dc's
            dc.Blit(0, 0, int(self.value*width), height, rect_dc, 0, 0)
            rect_dc.SelectObject(wx.NullBitmap)
        
    def TextToDC(self, dc, colour):
        font =  self.GetFont()
        dc.SetFont(font)
        dc.SetTextForeground(colour)
        if self.value == None:
            todraw = self.status
        else:
            todraw = "%s %.1f%%" % (self.status, self.value*100)
        dc.DrawLabel(todraw, self.GetClientRect(), alignment=wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER_VERTICAL)
        
    def TextColour(self, bg):
        rgb = bg.Get()
        brightness = (rgb[0] + rgb[1] + rgb[2]) / 3
        return wx.Colour(80,80,80) if brightness > 150 else wx.WHITE 

    
class TransparentText(wx.StaticText):

    def __init__(self, parent, id = wx.ID_ANY, label = '', pos = wx.DefaultPosition, size = wx.DefaultSize, style = wx.TRANSPARENT_WINDOW):
        wx.StaticText.__init__(self, parent, id, label, pos, size, style)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda event: None)
        self.Bind(wx.EVT_SIZE, self.OnSize)
    
    def OnPaint(self, event):
        dc = wx.PaintDC(self)
        dc.SetFont(self.GetFont())
        dc.SetTextForeground(self.GetForegroundColour())
        dc.DrawLabel(self.GetLabel(), self.GetClientRect()) 

    def OnSize(self, event):
        self.Refresh()
        event.Skip()
        

class TextCtrl(wx.TextCtrl):

    def __init__(self, *args, **kwargs):
        wx.TextCtrl.__init__(self, *args, **kwargs)
        self.descr_label  = ''
        self.descr_shown  = False
        self.descr_colour = wx.Colour(80,80,80)
        self.Bind(wx.EVT_CHILD_FOCUS, self.OnGetFocus)
        self.Bind(wx.EVT_SET_FOCUS, self.OnGetFocus)
        self.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocus)
        
    def SetDescriptiveText(self, descr_label):
        self.descr_label = descr_label
        self._SetDescriptiveText()
        
    def _SetDescriptiveText(self):
        if not self.GetValue():
            wx.TextCtrl.SetValue(self, self.descr_label)
            self.SetForegroundColour(self.descr_colour)
            self.descr_shown = True            
        
    def GetValue(self):
        if self.descr_shown:
            return ''
        return wx.TextCtrl.GetValue(self)
        
    def SetValue(self, value):
        if value:
            self.descr_shown = False
            wx.TextCtrl.SetValue(self, value)
    
    def OnGetFocus(self, event):
        if self.descr_shown:
            wx.TextCtrl.SetValue(self, '')
        self.SetForegroundColour(self.GetParent().GetForegroundColour())
        self.descr_shown = False
        
    def OnKillFocus(self, event):
        self._SetDescriptiveText()