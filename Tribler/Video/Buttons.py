# Written by Jelle Roozenburg, Maarten ten Brinke 
# see LICENSE.txt for license information
import wx, os, sys
from traceback import print_exc

DEBUG = False

class PlayerButton(wx.Panel):
    """
    Button that changes the image shown if you move your mouse over it.
    It redraws the background of the parent Panel, if this is an imagepanel with
    a variable self.bitmap.
    """

    def __init__(self, parent, imagedir, imagename):
        self.imagedir = imagedir
        self.imagename = imagename
        self.parent = parent
        self.init()
        
    def init(self):
        self.initDone = False
        self.enabled = True
        self.backgroundColor = wx.WHITE
        wx.Panel.__init__(self, self.parent) 
        self.selected = False
        self.tooltip = None
        self.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)
        
        
        self.searchBitmaps()
        self.createBackgroundImage()
        
        #<mluc> on mac, the button doesn't get a size
        #if self.bitmaps[0] and self.GetSize()==(0,0):
        if self.bitmaps[0]:
            self.SetSize(self.bitmaps[0].GetSize())
#        print self.Name
#        print 'size'
#        print self.Size
        
        
        self.initDone = True
        self.Refresh(True)
        self.Update()


    def GetImageName(self):
        return self.imagename
        
        
    def searchBitmaps(self):
        self.bitmaps = [None, None ,None]
        self.parentBitmap = None
        self.mouseOver = False
                
        if not os.path.isdir(self.imagedir):
            print 'Error: no image directory found in %s' % self.imagedir
            return
        
        # find a file with same name as this panel
        self.bitmapPath = [os.path.join(self.imagedir, self.imagename+'.png'), 
                           os.path.join(self.imagedir, self.imagename+'_hover.png'),
                           os.path.join(self.imagedir, self.imagename+'_dis.png')]
        
        i = 0
        for img in self.bitmapPath:
            if os.path.isfile(img):
                self.bitmaps[i] = wx.Bitmap(img, wx.BITMAP_TYPE_ANY)
                i+=1
            elif DEBUG:
                print 'Could not find image: %s' % img
         
           
        
        
    def createBackgroundImage(self):
        if self.bitmaps[0]:
            wx.EVT_PAINT(self, self.OnPaint)
            self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnErase)
                
    
    def OnErase(self, event):
        pass
        #event.Skip()
        
    def setSelected(self, sel):
        self.selected = sel
        self.Refresh()
        
    def isSelected(self):
        return self.selected
        
    def mouseAction(self, event):
        event.Skip()
        if event.Entering():
            #print 'enter' 
            self.mouseOver = True
            self.Refresh()
        elif event.Leaving():
            self.mouseOver = False
            #print 'leave'
            self.Refresh()


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
            #if DEBUG:
            #    print '(button %s) Mypos: %s, Parentpos: %s' % (self.GetName(), self.GetPosition(), parent.GetPosition())
            rect = [location[0], location[1], self.GetClientSize()[0], self.GetClientSize()[1]]
            #if DEBUG:
            #    print '(button %s) Slicing rect(%d,%d) size(%s) from parent image size(%s)' % (self.GetName(), location[0], location[1], str(self.GetClientSize()), str(bitmap.GetSize()))
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
                    print "(button %s) Result: %s" % (self.GetName(), rects)
                image = wx.EmptyImage(rect[2], rect[3])
                for r in rects:    
                    rect = wx.Rect(r[0], r[1], r[2], r[3])
                    if DEBUG:
                        print '(button %s) Trying to get rect: %s from bitmap: %s' % (self.GetName(), rect, bitmap.GetSize())
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
                        print "(button %s) Place subbitmap: %s" % (self.GetName(), str(place))
                    self.joinImage(image, subImage, place[0], place[1])
                if DEBUG:
                    print '(button %s) Result img size: %s' % (self.GetName(), str(image.GetSize()))
                return image.ConvertToBitmap()
            else:
                return bitmap.GetSubBitmap(wx.Rect(rect[0], rect[1], rect[2], rect[3]))
        except:
            if DEBUG:
                print_exc()
            return None
                                            
    def setEnabled(self, e):
        self.enabled = e
        if not e:
            self.SetToolTipString('')
#        else:
#            if self.tooltip:
#                self.SetToolTipString(self.tooltip)
        self.Refresh()
        
    def isEnabled(self):
        return self.enabled
    
    def setBackground(self, wxColor):
        self.backgroundColor = wxColor
        self.Refresh()
        
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


        if self.selected == 2:
            dc.DrawBitmap(self.bitmaps[2], 0,0, True)
            return


        if self.bitmaps[0]:
            dc.DrawBitmap(self.bitmaps[0], 0,0, True)
        if (self.mouseOver or self.selected) and self.bitmaps[1]:
            dc.DrawBitmap(self.bitmaps[1], 0,0, True)
        

class PlayerSwitchButton(PlayerButton):
        
    def __init__(self, parent, imagedir, imagename, imagename2):
        self.imagedir = imagedir
        self.imagename = imagename
        self.imagename2 = imagename2
        self.parent = parent
        self.init()
        
    def searchBitmaps(self):
        self.toggled = False
        self.allBitmaps = [None, None, None, None, None, None]
        self.parentBitmap = None
        self.mouseOver = False
                
                    
        if not os.path.isdir(self.imagedir):
            print >>sys.stderr,'PlayerSwitchButton: Error: no image directory found in',self.imagedir
            return
        
        # find a file with same name as this panel
        self.bitmapPath = [os.path.join(self.imagedir, self.imagename+'.png'), 
                           os.path.join(self.imagedir, self.imagename+'_hover.png'),
                           os.path.join(self.imagedir, self.imagename+'_dis.png'),
                           os.path.join(self.imagedir, self.imagename2+'.png'), 
                           os.path.join(self.imagedir, self.imagename2+'_hover.png'),
                           os.path.join(self.imagedir, self.imagename2+'_dis.png')
                           ]
        
        i = 0
        for img in self.bitmapPath:
            if os.path.isfile(img):
                self.allBitmaps[i] = wx.Bitmap(img, wx.BITMAP_TYPE_ANY)
                i+=1
            elif DEBUG:
                print 'Could not find image: %s' % img
                

        if self.toggled:
            self.bitmaps = self.allBitmaps[3:]
        else:
            self.bitmaps = self.allBitmaps[:3]
                
    def setToggled(self, b, tooltip = { "enabled": "", "disabled": ""}):
        self.toggled = b

        if not self.initDone:
            return

        if b:
            self.bitmaps=self.allBitmaps[3:]
            if self.enabled:
                self.SetToolTipString(tooltip["enabled"])
        else:
            self.bitmaps=self.allBitmaps[:3]
            if self.enabled:
                self.SetToolTipString(tooltip["disabled"])
            
        #print 'Bitmaps is now: %s' % self.bitmaps
        #should Refresh?
        self.Refresh()
        
    def isToggled(self):
        return self.toggled



##class VolumeButton(PlayerButton):




    
