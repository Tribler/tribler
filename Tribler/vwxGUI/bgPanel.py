import wx, os, sys
import wx.xrc as xrc

class bgPanel(wx.Panel):
    """
    Panel with automatic backgroundimage control.
    """
    def __init__(self, *args):
        self.backgroundColour = wx.Colour(102,102,102)
        pre = wx.PrePanel()
        # the Create step is done by XRC.
        self.PostCreate(pre)
        self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate)
        
    def OnCreate(self, event):
        self.Unbind(wx.EVT_WINDOW_CREATE)
#        print self.Name
#        print '>> size'
#        print self.Size
#        print self.Position
        wx.CallAfter(self._PostInit)
        event.Skip()
        return True
    
    def _PostInit(self):
        # Do all init here
        self.searchBitmap()
        self.createBackgroundImage()
        #        print self.Name
#        print '> size'
#        print self.Size
#        print self.Position
        
        self.Refresh(True)
        self.Update()
        
        
    def setBackground(self, color):
        self.backgroundColour = color
        self.Refresh()
        
    def searchBitmap(self):
        self.bitmap = None
        
        # get the image directory
        abcpath = os.path.abspath(os.path.dirname(sys.argv[0]))
        self.imagedir = os.path.join(abcpath, 'Tribler','vwxGUI', 'images')
        if not os.path.isdir(self.imagedir):
            olddir = self.imagedir
            # Started app.py in vwxDir?
            self.imagedir = os.path.join(abcpath, 'images')
        if not os.path.isdir(self.imagedir):
            print 'Error: no image directory found in %s and %s' % (olddir, self.imagedir)
            return
        
        # find a file with same name as this panel
        self.bitmapPath = os.path.join(self.imagedir, self.GetName()+'.png')
        
        
        if os.path.isfile(self.bitmapPath):
            self.bitmap = wx.Bitmap(self.bitmapPath, wx.BITMAP_TYPE_ANY)
        else:
            print 'Could not load image: %s' % self.bitmapPath
        
        
    def createBackgroundImage(self):
        wx.EVT_PAINT(self, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnErase)
        
        
    
    def setBitmap(self, bitmap):
        self.bitmap = bitmap
        self.Refresh()
        
    def OnErase(self, event):
        pass
        #event.Skip()
        
    def OnPaint(self, evt):
        obj = evt.GetEventObject()
        dc = wx.BufferedPaintDC(obj)
        dc.SetBackground(wx.Brush(self.backgroundColour))
        dc.Clear()
        if self.bitmap:
            # Tile bitmap
            rec=wx.Rect()
            rec=self.GetClientRect()
            for y in range(0,rec.GetHeight(),self.bitmap.GetHeight()):
                for x in range(0,rec.GetWidth(),self.bitmap.GetWidth()):
                    dc.DrawBitmap(self.bitmap,x,y,0)
            # Do not tile
            #dc.DrawBitmap(self.bitmap, 0,0, True)
        

