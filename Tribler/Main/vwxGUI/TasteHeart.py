import wx, os, sys,time
from traceback import print_exc
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility

DEBUG = False

# find the heart bitmaps

NUM_HEARTS = 5 #??
BITMAPS = []
                
class TasteHeart(wx.Panel):
    """
    Show an image of a heart
    """

    def __init__(self, *args, **kw):    
        if len(args) == 0: 
            self.backgroundColor = wx.Colour(102,102,102) 
            pre = wx.PrePanel() 
            # the Create step is done by XRC. 
            self.PostCreate(pre) 
            self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate) 
        else:
            self.backgroundColor = wx.Colour(102,102,102) 
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
        self.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)
        self.Bind(wx.EVT_LEFT_UP, self.guiUtility.buttonClicked)
        self.searchBitmaps()
        self.createBackgroundImage()
        self.setHeartIndex(0)
        #if self.bitmaps[0]:
        #    self.SetSize(self.bitmaps[0].GetSize())
#        print self.Name
#        print 'size'
#        print self.Size
        
        self.Refresh(True)
        self.Update()
        
    def searchBitmaps(self):
        self.parentBitmap = None
        self.mouseOver = False
        
        if not BITMAPS:
            print 'TastHeart: Error: Bitmaps of hearts were not loaded'        
                       
        
    def createBackgroundImage(self):
        wx.EVT_PAINT(self, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnErase)
                
    
    def OnErase(self, event):
        pass
        #event.Skip()
        
    def setRank(self, rank):
        if rank > 0 and rank <= 5:
            recomm = 0
        elif rank > 5 and rank <= 10:
            recomm = 1
        elif rank > 10 and rank <= 15:
            recomm = 2
        elif rank > 15 and rank <= 20:
            recomm = 3
        else:
            recomm = 4
        
        self.setHeartIndex(recomm)
        
    def setHeartIndex(self, index):
        if not BITMAPS:
            return
        self.heartIndex = index
        self.SetSize(BITMAPS[self.heartIndex].GetSize())
        self.SetMinSize(BITMAPS[self.heartIndex].GetSize())
        self.Refresh()
        
    def mouseAction(self, event):
        if event.Entering():
            #print 'enter' 
            self.mouseOver = True
            self.Refresh()
        elif event.Leaving():
            self.mouseOver = False
            #print 'leave'
            self.Refresh()
#        elif event.ButtonUp():
#            self.ClickedButton()
        
        
    def getParentBitmap(self):
        try:
            parent = self.GetParent()
            bitmap = parent.bitmap
            #print bitmap
        except:
            return None
        
        if bitmap:
            location = self.GetPosition()
            #location[0] -= parent.GetPosition()[0]
            #location[1] -= parent.GetPosition()[1]
            if DEBUG:
                print 'Mypos: %s, Parentpos: %s' % (self.GetPosition(), parent.GetPosition())
            rect = [location[0], location[1], self.GetClientSize()[0], self.GetClientSize()[1]]
            if DEBUG:
                print 'Slicing rect(%d,%d) size(%s) from parent image size(%s)' % (location[0], location[1], str(self.GetClientSize()), str(bitmap.GetSize()))
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
            if rect[0]+rect[2] >= bitmapSize[0]:
                rect1 = (rect[0], rect[1], bitmapSize[0]-rect[0], rect[3])
                rect2 = (0, rect[1], rect[0]+rect[2] - bitmapSize[0], rect[3])
                rects = [rect1, rect2]
            if rect[1]+ rect[3] >= bitmapSize[1]:
                rects2 = []
                for r in rects:
                    r1 = (r[0], r[1], r[2], bitmapSize[1] - r[3])
                    r2 = (r[0], 0, r[2], r[1]+r[3] - bitmapSize[1])
                    rects2.append(r1)
                    rects2.append(r2)
                rects = rects2
            images = []
            if len(rects) > 1:
                #print "Result: %s" % rects
                image = wx.EmptyImage(rect[2], rect[3])
                for r in rects:    
                    subBitmap = bitmap.GetSubBitmap(wx.Rect(r[0], r[1], r[2], r[3]))
                    subImage = subBitmap.ConvertToImage()
                    if r == rects[0]:
                        place = (0,0)
                    elif r == rects[1]:
                        if len(rects) == 4:
                            place = (0, bitmapSize[1]-rect[1])
                        elif len(rects) == 2:
                            place = (bitmapSize[0]-rect[0], 0)
                    elif r == rects[2]:
                        place = (bitmapSize[0] - rect[0], 0)
                    elif r == rects[3]:
                        place = (bitmapSize[0] - rect[0], bitmapSize[1] - rect[1])
                    #print "Place: %s" % str(place)
                    self.joinImage(image, subImage, place[0], place[1])
                return image.ConvertToBitmap()
            else:
                return bitmap.GetSubBitmap(wx.Rect(rect[0], rect[1], rect[2], rect[3]))
        except:
            print_exc()
            return None
                                            
        
    def setBackground(self, wxColor):
        self.backgroundColor = wxColor
        
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
        
        if BITMAPS and BITMAPS[self.heartIndex]:
            dc.DrawBitmap(BITMAPS[self.heartIndex], 0,0, True)
        #if (self.mouseOver or self.selected) and self.bitmaps[1]:
        #    dc.DrawBitmap(self.bitmaps[1], 0,0, True)
        

def getHeartBitmap(rank):
    global BITMAPS
    #because of the fact that hearts are coded so that lower index means higher ranking, then:
    if rank > 0 and rank <= 5:
        recomm = 0
    elif rank > 5 and rank <= 10:
        recomm = 1
    elif rank > 10 and rank <= 15:
        recomm = 2
    elif rank > 15 and rank <= 20:
        recomm = 3
    else:
        recomm = -1
        
    if recomm >= 0:
        b = BITMAPS[recomm]
        if not b:
            raise Exception('No heart bitmap: %s' % BITMAPS)
        else:
            return b
        
    else:
        return None
                
def set_tasteheart_bitmaps(syspath):
    global BITMAPS
    imagedir = os.path.join(syspath, 'vwxGUI', 'images')
    for i in xrange(NUM_HEARTS):
        filename = os.path.join(imagedir, 'heart%d.png' % (i+1))
        if os.path.isfile(filename):
            BITMAPS.append(wx.Bitmap(filename, wx.BITMAP_TYPE_ANY))
        else:
            print >>sys.stderr,'TasteHeart: Could not find image: %s' % filename
    print 'Adding %d BITMAPS' % len(BITMAPS)