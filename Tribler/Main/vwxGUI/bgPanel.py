# Written by Jelle Roozenburg, Maarten ten Brinke, Arno Bakker 
# see LICENSE.txt for license information
import wx, os, sys

DEBUG = False

class ImagePanelBasic(wx.Panel):
    """
    Panel with automatic backgroundimage control.
    """
    
    __bitmapCache = {}

    def __init__(self, tile, *args, **kw):
        self.backgroundColour = wx.WHITE
        
        from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
        self.guiUtility = GUIUtility.getInstance()
        self.xpos = self.ypos = 0
        self.tile = tile
        self.bitmap = None
        
        if len(args) == 0: 
            pre = wx.PrePanel() 
            # the Create step is done by XRC. 
            self.PostCreate(pre) 
            self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate) 
        else:
            wx.Panel.__init__(self, *args, **kw) 
            self._PostInit()
            
        
    def OnCreate(self, event):
        self.Unbind(wx.EVT_WINDOW_CREATE)
        wx.CallAfter(self._PostInit)
        event.Skip()
        return True
    
    def _PostInit(self):
        # Do all init here
        
        if self.bitmap is None:
            self.loadBitmap()
            
        wx.EVT_PAINT(self, self.OnPaint)
        self.Refresh()
        
    def setBackground(self, colour):
        self.backgroundColour = colour

    def loadBitmap(self, name = None):
        self.bitmap = None
        
        # get the image directory
        self.imagedir = os.path.join(self.guiUtility.vwxGUI_path, 'images')

        # find a file with same name as this panel
        if name is None:
            self.bitmapPath = os.path.join(self.imagedir, self.GetName()+'.png')
        else:
            self.bitmapPath = os.path.join(self.imagedir, name)

        if os.path.isfile(self.bitmapPath):
            self.setBitmap(wx.Bitmap(self.bitmapPath, wx.BITMAP_TYPE_ANY))
        elif DEBUG:
            print >>sys.stderr,'bgPanel: Could not load image: %s' % self.bitmapPath

    def setBitmap(self, bitmap):
        self.bitmap = bitmap
        
        w, h = self.GetSize()
        iw, ih = self.bitmap.GetSize()
                
        self.xpos, self.ypos = (w-iw)/2, (h-ih)/2
        self.Refresh()
        
    def OnPaint(self, evt):
        obj = evt.GetEventObject()
        dc = wx.BufferedPaintDC(obj)
        if self.bitmap:
            if self.tile:
                dc.SetPen(wx.TRANSPARENT_PEN)
                dc.SetBrush(wx.BrushFromBitmap(self.bitmap))
                w, h = self.GetClientSize()
                dc.DrawRectangle(0, 0, w, h)
            else:
                dc.SetBackground(wx.Brush(self.backgroundColour))
                dc.Clear()
                dc.DrawBitmap(self.bitmap, self.xpos, self.ypos, True)
        else:
            dc.SetBackground(wx.Brush(self.backgroundColour))
            dc.Clear()
        
class bgPanel(ImagePanelBasic):
    def __init__(self, *args, **kw):
        tile = True     
        ImagePanelBasic.__init__(self, tile, *args, **kw)

class ImagePanel(ImagePanelBasic):
    def __init__(self, *args, **kw):
        tile = False
        ImagePanelBasic.__init__(self, tile, *args, **kw)
    
