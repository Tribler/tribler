
import wx, os, sys

class standardPager(wx.Panel):
    """
    Panel with automatic backgroundimage control.
    """
    def __init__(self, *args):
        if len(args) == 0:
            pre = wx.PrePanel()
            # the Create step is done by XRC.
            self.PostCreate(pre)
            self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate)
        else:
            wx.Panel.__init__(self, args[0], args[1], args[2], args[3])
            self._PostInit()
        
    def OnCreate(self, event):
        self.Unbind(wx.EVT_WINDOW_CREATE)
        wx.CallAfter(self._PostInit)
        event.Skip()
        return True
    
    def _PostInit(self):
        # Do all init here
        self.searchBitmap()
        self.createBackgroundImage()
        
        self.Refresh(True)
        self.Update()        
        
        
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
        print 'Trying image: %s' % self.bitmapPath
        
        if os.path.isfile(self.bitmapPath):
            self.bitmap = wx.Bitmap(self.bitmapPath, wx.BITMAP_TYPE_ANY)
        
        
    def createBackgroundImage(self):
        if self.bitmap:
            wx.EVT_PAINT(self, self.OnPaint)
            self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnErase)
        
        
    
    def OnErase(self, event):
        pass
        #event.Skip()
        
    def OnPaint(self, evt):
        dc = wx.PaintDC(self)
        
        if self.bitmap:
            # Tile bitmap
            rec=wx.Rect()
            rec=self.GetClientRect()
            for y in range(0,rec.GetHeight(),self.bitmap.GetHeight()):
                for x in range(0,rec.GetWidth(),self.bitmap.GetWidth()):
                    dc.DrawBitmap(self.bitmap,x,y,0)
            # Do not tile
            #dc.DrawBitmap(self.bitmap, 0,0, True)
        
