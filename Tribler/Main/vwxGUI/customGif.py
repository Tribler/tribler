# Written by Richard Gwin
import wx, os, sys
from traceback import print_exc

from Tribler.Main.vwxGUI.GuiUtility import GUIUtility

DEBUG = False

class customGif(wx.Panel):
    __bitmapCache = {}

    def __init__(self, *args, **kw):
        self.enabled = True
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
        # Do all init here
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility

        self.searchBitmaps()
        self.createBackgroundImage()
        

        self.value=0
        self.agtimer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnPaint)


        if self.bitmaps[0]:
            self.SetSize(self.bitmaps[0].GetSize())

        
        self.Refresh()
        self.Update()
        



    def Play(self):
        self.agtimer.Start(100) 

    def Stop(self):
        self.agtimer.Stop()

    def hide(self):
        self.Hide()

    def Show(self):
        self.Show()

       
    def searchBitmaps(self):
        self.bitmaps = [None, None,None,None,None,None,None,None,None]
        self.parentBitmap = None
                
        # get the image directory
        self.imagedir = os.path.join(self.guiUtility.vwxGUI_path, 'images')
       
        # find a file with same name as this panel
        self.bitmapPath = [os.path.join(self.imagedir, self.GetName()+'.png'), 
                        os.path.join(self.imagedir, self.GetName()+'_1.png'),
                        os.path.join(self.imagedir, self.GetName()+'_2.png'),
                        os.path.join(self.imagedir, self.GetName()+'_3.png'),
                        os.path.join(self.imagedir, self.GetName()+'_4.png'),
                        os.path.join(self.imagedir, self.GetName()+'_5.png'),
                        os.path.join(self.imagedir, self.GetName()+'_6.png'),
                        os.path.join(self.imagedir, self.GetName()+'_7.png'),
                        os.path.join(self.imagedir, self.GetName()+'_8.png')]


        i = 0
        for img in self.bitmapPath:
            if not os.path.isfile(img):
                print >>sys.stderr,"customGif: Could not find image:",img
            try:
                if img in customGif.__bitmapCache:
                    self.bitmaps[i] = customGif.__bitmapCache[img]
                else:
                    self.bitmaps[i] = wx.Bitmap(img, wx.BITMAP_TYPE_ANY)
                    customGif.__bitmapCache[img] = self.bitmaps[i] 
            except:
                print_exc()
            i+=1         
           
        
    def createBackgroundImage(self):
        if self.bitmaps[0]:
            wx.EVT_PAINT(self, self.OnPaint)
            self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnErase)
    
    def OnErase(self, event):
        pass
        #event.Skip()
        
                
    def getParentBitmap(self):
        try:
            parent = self.GetParent()
            bitmap = parent.bitmap
        except:
            return None
        
        if bitmap:
            location = self.GetPosition()
            rect = [location[0], location[1], self.GetClientSize()[0], self.GetClientSize()[1]]
            bitmap = self.getBitmapSlice(bitmap, rect)
            return bitmap
        else:
            return None
    
    def joinImage(self, im1,im2,offsetx=0,offsety=0):
        "Draw im2 on im1"
        stopx = im2.GetWidth()
        if stopx > (im1.GetWidth()-offsetx):
            stopx = im1.GetWidth()-offsetx
        stopy = im2.GetHeight()
        if stopy > (im1.GetHeight()-offsety):
            stopy = im1.GetHeight()-offsety
        if stopx>0 and stopy>0:
            for x in range(0,stopx):
                for y in range(0,stopy):
                    rgb2 = (im2.GetRed(x,y),im2.GetGreen(x,y),im2.GetBlue(x,y))
                    if rgb2 !=(255,0,255):
                        im1.SetRGB(x+offsetx,y+offsety,rgb2[0],rgb2[1],rgb2[2])
        return im1
 
    def getBitmapSlice(self, bitmap, rect):
        try:
            #print rect
            bitmapSize = bitmap.GetSize()
            rect[0] %= bitmapSize[0]
            rect[1] %= bitmapSize[1]
            rects = [rect]
            if rect[0]+rect[2] > bitmapSize[0]:
                rect1 = (rect[0], rect[1], bitmapSize[0]-rect[0], rect[3])
                rect2 = (0, rect[1], rect[0]+rect[2] - bitmapSize[0], rect[3])
                rects = [rect1, rect2]
            if rect[1]+ rect[3] > bitmapSize[1]:
                rects2 = []
                for r in rects:
                    r1 = (r[0], r[1], r[2], bitmapSize[1] - r[3])
                    r2 = (r[0], 0, r[2], r[1]+r[3] - bitmapSize[1])
                    rects2.append(r1)
                    rects2.append(r2)
                rects = rects2
            images = []
            if len(rects) > 1:
                if DEBUG:
                    print >>sys.stderr,"customGif: Result: %s" % (self.GetName(), rects)
                image = wx.EmptyImage(rect[2], rect[3])
                for r in rects:    
                    rect = wx.Rect(r[0], r[1], r[2], r[3])
                    if DEBUG:
                        print >>sys.stderr,'customGif: Trying to get rect: %s from bitmap: %s' % (self.GetName(), rect, bitmap.GetSize())
                    subBitmap = bitmap.GetSubBitmap(rect)
                    subImage = subBitmap.ConvertToImage()
                    if len(rects) == 2:
                        if r == rects[0]:
                            place = (0,0)
                        elif r == rects[1]:
                            place = (rects[0][2], 0)
                    elif len(rects) == 4:
                        if r == rects[0]:
                            place = (0,0)
                        elif r == rects[1]:
                            place = (0, rects[0][3])
                        elif r == rects[2]:
                            place = (rects[0][2],0)
                        elif r == rects[3]:
                            place = (rects[0][2], rects[0][3])
                    if DEBUG:
                        print >>sys.stderr,"customGif: Place subbitmap: %s" % (self.GetName(), str(place))
                    self.joinImage(image, subImage, place[0], place[1])
                if DEBUG:
                    print >>sys.stderr,'customGif: Result img size: %s' % (self.GetName(), str(image.GetSize()))
                return image.ConvertToBitmap()
            else:
                return bitmap.GetSubBitmap(wx.Rect(rect[0], rect[1], rect[2], rect[3]))
        except:
            if DEBUG:
                print_exc()
            return None

        
    def OnPaint(self, evt):
        dc = wx.BufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.backgroundColor))
        dc.Clear()
        
        if self.parentBitmap:
            dc.DrawBitmap(self.parentBitmap, 0,0, True)
        else:
            self.parentBitmap = self.getParentBitmap()
            if self.parentBitmap:
                dc.DrawBitmap(self.parentBitmap, 0,0, True)
        
        if not self.enabled:
            return
        
        if self.bitmaps[0]:
            dc.DrawBitmap(self.bitmaps[0], 0,0, True)
        dc.DrawBitmap(self.bitmaps[self.value], 0,0, True)        
        self.value+=1
        self.value%=9
        if self.value==0:
            self.value=1
