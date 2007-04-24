import wx, os, sys
from traceback import print_exc
from Tribler.vwxGUI.GuiUtility import GUIUtility

DEBUG = False

# find the heart bitmaps

NUM_PERFS = 7 #number of performance states for vertical bar
NUM_GRADES = 5 #nuber of tribler grades
BITMAPS_BIG = []
BITMAPS_SMALL = []
TRIBLER_GRADES = []
IMAGEDIR = os.path.join(os.path.abspath(os.path.dirname(sys.argv[0])), 'Tribler','vwxGUI', 'images')
for i in xrange(NUM_PERFS):
    filename = os.path.join(IMAGEDIR, 'perfL%d.png' % i)
    if os.path.isfile(filename):
        BITMAPS_BIG.append(wx.Bitmap(filename, wx.BITMAP_TYPE_ANY))
    else:
        print 'Could not find image: %s' % filename
    filename = os.path.join(IMAGEDIR, 'perfM%d.png' % i)
    if os.path.isfile(filename):
        BITMAPS_SMALL.append(wx.Bitmap(filename, wx.BITMAP_TYPE_ANY))
    else:
        print 'Could not find image: %s' % filename
for i in xrange(NUM_GRADES):
    filename = os.path.join(IMAGEDIR, 'Level%d.png' % (i+1))
    if os.path.isfile(filename):
        TRIBLER_GRADES.append(wx.Bitmap(filename, wx.BITMAP_TYPE_ANY))
    else:
        print 'Could not find image: %s' % filename
        
class ProgressIcon(wx.Panel):
    """
    Shows a vertical bar filled at different levels
    Any class that subclasses this one must provide a bitmapsList array
    """

    def __init__(self, *args, **kw):    
        self.backgroundColor = wx.Colour(102,102,102)
        pre = wx.PrePanel()
        # the Create step is done by XRC.
        self.PostCreate(pre)
        self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate)
        
    def OnCreate(self, event):
        self.Unbind(wx.EVT_WINDOW_CREATE)
        wx.CallAfter(self._PostInit)
        event.Skip()
        return True
    
    def _PostInit(self):
        # Do all init here
        self.guiUtility = GUIUtility.getInstance()
#        self.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)
        self.Bind(wx.EVT_LEFT_UP, self.guiUtility.buttonClicked)
        self.createBackgroundImage()
        self.setIndex(0)
        #if self.bitmaps[0]:
        #    self.SetSize(self.bitmaps[0].GetSize())
#        print self.Name
#        print 'size'
#        print self.Size
        self.mouseOver = False
        
        self.Refresh(True)
        self.Update()
                       
        
    def createBackgroundImage(self):
        wx.EVT_PAINT(self, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnErase)
                
    
    def OnErase(self, event):
        pass
        #event.Skip()
        
    def setIndex(self, index):
        if index < 0:
            index = 0
        if index > len(self.bitmapsList):
            index = len(self.bitmapsList)-1
        self.index = index
#        self.SetSize(BITMAPS[self.heartIndex].GetSize())
#        self.SetMinSize(BITMAPS[self.heartIndex].GetSize())
        self.Refresh()
        
    def getIndex(self):
        return self.index
        
    def mouseAction(self, event):
        if event.Entering():
            #print 'enter' 
            self.mouseOver = True
            self.Refresh()
        elif event.Leaving():
            self.mouseOver = False
            #print 'leave'
            self.Refresh()
        elif event.ButtonUp():
            self.ClickedButton()
        
    def setBackground(self, wxColor):
        self.backgroundColor = wxColor
        
    def OnPaint(self, evt):
        dc = wx.BufferedPaintDC(self)
#        dc.SetBackground(wx.Brush(self.backgroundColor))
        dc.Clear()
        
        if self.bitmapsList[self.index]:
            dc.DrawBitmap(self.bitmapsList[self.index], 0,0, True)
        #if (self.mouseOver or self.selected) and self.bitmaps[1]:
        #    dc.DrawBitmap(self.bitmaps[1], 0,0, True)
        

class SmallPerfBar(ProgressIcon):                
    def __init__(self, *args, **kw):
        self.bitmapsList = BITMAPS_SMALL
        ProgressIcon.__init__(self)

class BigPerfBar(ProgressIcon):                
    def __init__(self, *args, **kw):
        self.bitmapsList = BITMAPS_BIG
        ProgressIcon.__init__(self)

class TriblerGrade(ProgressIcon):
    def __init__(self, *args, **kw):
        self.bitmapsList = TRIBLER_GRADES
        ProgressIcon.__init__(self)
