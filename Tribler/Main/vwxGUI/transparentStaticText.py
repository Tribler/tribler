# Written by Jelle Roozenburg, Maarten ten Brinke, Arno Bakker 
# see LICENSE.txt for license information

import wx
from traceback import print_exc

DEBUG = False
BUFFERED = False

class TransparentStaticText(wx.StaticText):
    
    def __init__(self):
        pre = wx.PreStaticText() 
        # the Create step is done by XRC. 
        self.parentBitmap = None
        self.PostCreate(pre) 
        self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate) 
        
        
        
    def OnCreate(self, event):
        self.Unbind(wx.EVT_WINDOW_CREATE)
        wx.CallAfter(self._PostInit)
        event.Skip()
        return True
    
    def _PostInit(self):
#        while self.Unbind(wx.EVT_PAINT):
#            pass
#        self.Disconnect(-1, -1, wx.wxEVT_PAINT)
        
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.onEraseBackground)
        self.OnPaint = self.OnPaint
        pass
        
    def onEraseBackground(self, event):
        return
        dc = wx.ClientDC(self)
        dc.SetBackground(wx.BLACK_BRUSH)
        dc.Clear()
        
        if self.parentBitmap:
            dc.DrawBitmap(self.parentBitmap, 0,0, True)
        else:
            self.parentBitmap = self.getParentBitmap()
            if self.parentBitmap:
                dc.DrawBitmap(self.parentBitmap, 0,0, True)
        event.Skip(False)
    
    
    def SetLabel(self, label):
        """
        Sets the static text label and updates the control's size to exactly
        fit the label unless the control has wx.ST_NO_AUTORESIZE flag.
        """
        print 'setLabel()'
        wx.StaticText.SetLabel(self, label)
        self.Refresh()

    def OnPaint(self, event):
        print 'paint()'
        if BUFFERED:
            dc = wx.BufferedPaintDC(self)
        else:
            dc = wx.PaintDC(self)
        width, height = self.GetClientSize()
        if not width or not height:
            return

        if BUFFERED:
            clr = self.GetBackgroundColour()
            backBrush = wx.Brush(clr, wx.SOLID)
            if wx.Platform == "__WXMAC__" and clr == self.defBackClr:
                # if colour is still the default then use the striped background on Mac
                backBrush.MacSetTheme(1) # 1 == kThemeBrushDialogBackgroundActive
            dc.SetBackground(backBrush)
            dc.Clear()
        
        if not self.parentBitmap:
            self.parentBitmap = self.getParentBitmap()
        
        if self.parentBitmap:
            print 'paint parent()'
            dc.DrawBitmap(self.parentBitmap, 0,0, True)

        if self.IsEnabled():
            dc.SetTextForeground(self.GetForegroundColour())
        else:
            dc.SetTextForeground(wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT))
            
        dc.SetFont(self.GetFont())
        label = self.GetLabel()
        style = self.GetWindowStyleFlag()
        x = y = 0
        for line in label.split('\n'):
            if line == '':
                w, h = self.GetTextExtent('W')  # empty lines have height too
            else:
                w, h = self.GetTextExtent(line)
            if style & wx.ALIGN_RIGHT:
                x = width - w
            if style & wx.ALIGN_CENTER:
                x = (width - w)/2
            dc.DrawText(line, x, y)
            y += h
            
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
                print '(button %s) Mypos: %s, Parentpos: %s' % (self.GetName(), self.GetPosition(), parent.GetPosition())
            rect = [location[0], location[1], self.GetClientSize()[0], self.GetClientSize()[1]]
            if DEBUG:
                print '(button %s) Slicing rect(%d,%d) size(%s) from parent image size(%s)' % (self.GetName(), location[0], location[1], str(self.GetClientSize()), str(bitmap.GetSize()))
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