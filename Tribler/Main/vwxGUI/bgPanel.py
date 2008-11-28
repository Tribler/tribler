# Written by Jelle Roozenburg, Maarten ten Brinke, Arno Bakker 
# see LICENSE.txt for license information
import wx, os, sys
import wx.xrc as xrc

from traceback import print_stack,print_exc

DEBUG = False

class ImagePanelBasic(wx.Panel):
    """
    Panel with automatic backgroundimage control.
    """
    
    __bitmapCache = {}

    def __init__(self, tile, *args, **kw):
        self.backgroundColour = wx.Colour(102,102,102)
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
#        print self.Name
#        print '>> size'
#        print self.Size
#        print self.Position
        wx.CallAfter(self._PostInit)
        event.Skip()
        return True
    
    def _PostInit(self):
        # Do all init here
        if self.bitmap is None: #mluc: search for bitmap only if not already set; it may happen as the setBitmap might be called before the _PostInit
            self.searchBitmap()
        ##self.createBackgroundImage()
        #        print self.Name
#        print '> size'
#        print self.Size
#        print self.Position
        
        self.Refresh(True)
        self.Update()
        
        
    def setBackground(self, colour):
        self.backgroundColour = colour
        self.Refresh()
        


    def searchBitmap(self, name = None):
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
            print 'bgPanel: Could not load image: %s' % self.bitmapPath

##        try:
            # These unnamed things popup on LibraryView
##            if self.bitmapPath.endswith('panel.png'):
##                return
##            
##            img = self.bitmapPath
##            if img in ImagePanelBasic.__bitmapCache:
##                bitmap = ImagePanelBasic.__bitmapCache[img]
##            else:
##                bitmap = wx.Bitmap(img, wx.BITMAP_TYPE_ANY)
##                ImagePanelBasic.__bitmapCache[img] = bitmap
            
##            self.setBitmap(bitmap)
##        except:
##            print_exc()
        
    def createBackgroundImage(self):
        wx.EVT_PAINT(self, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnErase)
        

    def setBitmapFromFile(self, filename):
        self.setBitmap(wx.Bitmap(os.path.join(self.imagedir, filename+'.png')))
        
    def setBitmap(self, bitmap):
        self.bitmap = bitmap
        
        w, h = self.GetSize()
        iw, ih = self.bitmap.GetSize()
                
        self.xpos, self.ypos = (w-iw)/2, (h-ih)/2
#        self.SetMinSize((iw, ih))
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
            
            if self.tile:
                for y in range(0,rec.GetHeight(),self.bitmap.GetHeight()):
                    for x in range(0,rec.GetWidth(),self.bitmap.GetWidth()):
                        dc.DrawBitmap(self.bitmap,x,y,0)
            else:
                # Do not tile
                
                dc.DrawBitmap(self.bitmap, self.xpos,self.ypos, True)
        


class bgPanel(ImagePanelBasic):
    def __init__(self, *args, **kw):
        tile = True     
        ImagePanelBasic.__init__(self, tile, *args, **kw)
        
class ImagePanel(ImagePanelBasic):
    def __init__(self, *args, **kw):
        tile = False
        ImagePanelBasic.__init__(self, tile, *args, **kw)
    
