import wx, math, time, os, sys, threading
from traceback import print_exc
from Tribler.utilities import *
from wx.lib.stattext import GenStaticText as StaticText
from Tribler.Dialogs.ContentFrontPanel import ImagePanel
from Tribler.vwxGUI.GuiUtility import GUIUtility
from safeguiupdate import DelayedInvocation
from Tribler.unicode import *
from copy import deepcopy
import cStringIO
from threading import Lock
import TasteHeart

DEBUG=True

class PersonsItemPanel(wx.Panel):
    """
    PersonsItemPanel shows one persons item inside the PersonsGridPanel
    """
    def __init__(self, parent):
        global TORRENTPANEL_BACKGROUND
        
        wx.Panel.__init__(self, parent, -1)
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility
        self.parent = parent
        self.data = None
        self.datacopy = None
        self.titleLength = 37 # num characters
        self.selected = False
        self.warningMode = False
        self.oldCategoryLabel = None
        self.addComponents()
        self.Show()
        self.Refresh()
        self.Layout()

    def addComponents(self):
        self.Show(False)
        #self.SetMinSize((50,50))
        self.selectedColour = wx.Colour(255,200,187)       
        self.unselectedColour = wx.WHITE
        
        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        
        self.Bind(wx.EVT_LEFT_UP, self.mouseAction)
        self.Bind(wx.EVT_KEY_UP, self.keyTyped)
        
        # Add title
        self.thumb = ThumbnailViewer(self)
        self.thumb.setBackground(wx.BLACK)
        self.thumb.SetSize((80,80))
        self.vSizer.Add(self.thumb, 0, wx.ALL, 0)        
        self.title =wx.StaticText(self,-1,"",wx.Point(0,0),wx.Size(80,15))        
        self.title.SetBackgroundColour(wx.WHITE)
        self.title.SetFont(wx.Font(10,74,90,wx.NORMAL,0,"Verdana"))
        self.title.SetMinSize((80,30))
        self.vSizer.Add(self.title, 0, wx.BOTTOM, 3)     

        self.SetSizer(self.vSizer);
        self.SetAutoLayout(1);
        self.Layout();
        self.Refresh()
        
        for window in self.GetChildren():
            window.Bind(wx.EVT_LEFT_UP, self.mouseAction)
            window.Bind(wx.EVT_KEY_UP, self.keyTyped)
                             
    def setData(self, peer_data):
        # set bitmap, rating, title
        
        try:
            if self.datacopy['permid'] == peer_data['permid']:
                if (self.datacopy['last_seen'] == peer['last_seen'] and
                    self.datacopy['similarity'] == peer['similarity'] and
                    self.datacopy['name'] == peer['name'] and
                    self.datacopy['content_name'] == peer['content_name'] and
                    self.datacopy.get('friend') == peer.get('friend')):
                    return
        except:
            pass
        
        self.data = peer_data
        self.datacopy = deepcopy(peer_data)
        
        if peer_data == None:
            peer_data = {}
        
        if peer_data.get('content_name'):
            title = peer_data['content_name'][:self.titleLength]
            self.title.Enable(True)
            self.title.SetLabel(title)
            self.title.Wrap(self.title.GetSize()[0])
            self.title.SetToolTipString(peer_data['content_name'])
        else:
            self.title.SetLabel('')
            self.title.SetToolTipString('')
            self.title.Enable(False)
            
       
        self.thumb.setData(peer_data)
               
        self.Layout()
        self.Refresh()
        #self.parent.Refresh()
        
          
        
    def select(self):
        print 'person selected'
        self.thumb.setSelected(True)
        self.title.SetBackgroundColour(self.selectedColour)
        self.title.Refresh()
        
    def deselect(self):
        self.thumb.setSelected(False)
        self.title.SetBackgroundColour(self.unselectedColour)
        self.title.Refresh()
    
    def keyTyped(self, event):
        if self.selected:
            key = event.GetKeyCode()
            if (key == wx.WXK_DELETE):
                if self.data:
                    if DEBUG:
                        print >>sys.stderr,'contentpanel: deleting'
#                    self.guiUtility.deleteTorrent(self.data)
        event.Skip()
        
    def mouseAction(self, event):
        print "set focus"
        self.SetFocus()
        if self.data:
            self.guiUtility.selectPeer(self.data)
            
    def getIdentifier(self):
        if self.data:
            return self.data['permid']
                
                
DEFAULT_THUMB = wx.Bitmap(os.path.join('Tribler', 'vwxGUI', 'images', 'defaultThumbPeer.png'))
MASK_BITMAP = wx.Bitmap(os.path.join('Tribler', 'vwxGUI', 'images', 'itemMask.png'))
HEART_BITMAP = wx.Bitmap(os.path.join('Tribler', 'vwxGUI', 'images', 'heart1.png'))
FRIEND_BITMAP = wx.Bitmap(os.path.join('Tribler', 'vwxGUI', 'images', 'friend.png'))

class ThumbnailViewer(wx.Panel, DelayedInvocation):
    """
    Show thumbnail and mast with info on mouseOver
    """

    def __init__(self, *args, **kw):    
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
        DelayedInvocation.__init__(self)
        self.backgroundColor = wx.WHITE
        self.dataBitmap = self.maskBitmap = None
        self.data = None
        self.dataLock = Lock()
        self.mouseOver = False
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility
        self.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)
        self.Bind(wx.EVT_LEFT_UP, self.guiUtility.buttonClicked)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnErase)
        self.selected = False
        self.border = None
        #create the heart
        #I will use TasteHeart.BITMAPS to paint the right one
        
        
    
    def setData(self, data):
        if not data:
            self.Hide()
            self.Refresh()
            return
        
        if not self.IsShown():
                self.Show()
                
        if data != self.data:
            self.data = data
            self.setThumbnail(data)
                      
    def setThumbnail(self, data):
        # Get the file(s)data for this torrent
        try:
            bmp = DEFAULT_THUMB
            # Check if we have already read the thumbnail and metadata information from this torrent file
            if data.get('metadata'):
                bmp = data['metadata'].get('ThumbnailBitmap')
                if not bmp:
                    print 'ThumbnailViewer: Error: thumbnailBitmap not found in torrent %s' % torrent
                    bmp = DEFAULT_THUMB
            else:
                # Do the loading of metadata and thumbnail in new thread
                # so that navigation is not slowed down
                pass
#                Thread(target = self.loadMetadata, args=(torrent,)).start()
            
            self.setBitmap(bmp)
            width, height = self.GetSize()
            d = 1
            self.border = [wx.Point(0,d), wx.Point(width-d, d), wx.Point(width-d, height-d), wx.Point(d,height-d), wx.Point(d,0)]
            self.Refresh()
            
        except:
            print_exc(file=sys.stderr)
            return {}           
        
         
    def setBitmap(self, bmp):
        # Recalculate image placement
        w, h = self.GetSize()
        iw, ih = bmp.GetSize()
                
        self.dataLock.acquire()
        self.dataBitmap = bmp
        self.xpos, self.ypos = (w-iw)/2, (h-ih)/2
        self.dataLock.release()
        
    
    
    def OnErase(self, event):
        pass
        #event.Skip()
        
    def setSelected(self, sel):
        self.selected = sel
        self.Refresh()
        
    def isSelected(self):
        return self.selected
        
    def mouseAction(self, event):
        if event.Entering():
            print 'enter' 
            self.mouseOver = True
            self.Refresh()
        elif event.Leaving():
            self.mouseOver = False
            print 'leave'
            self.Refresh()
        elif event.ButtonUp():
            self.ClickedButton()
        #event.Skip()
        """
    def ClickedButton(self):
        print 'Click'
        """
                
    def setBackground(self, wxColor):
        self.backgroundColor = wxColor
        
    def OnPaint(self, evt):
        dc = wx.BufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.backgroundColor))
        dc.Clear()
        
        if self.dataBitmap:
            dc.DrawBitmap(self.dataBitmap, self.xpos,self.ypos, True)
#        if self.mouseOver:
#        if self.data!=None and type(self.data)==type({}) and self.data.get('permid'):
        dc.SetFont(wx.Font(6, wx.SWISS, wx.NORMAL, wx.BOLD, True))
        dc.DrawBitmap(MASK_BITMAP,0 ,62, True)
        rank = self.guiUtility.peer_manager.getRank(self.data['permid'])
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
            recomm = 4
#        if rank != -1:
#            self.getGuiObj('recommendationField').SetLabel("%d" % rank)
#        else:
#            self.getGuiObj('recommendationField').SetLabel("")
        dc.DrawBitmap(TasteHeart.BITMAPS[recomm],5 ,64, True)
        if self.data['friend']:
            dc.DrawBitmap(FRIEND_BITMAP,60 ,65, True)            
        
        dc.SetTextForeground(wx.WHITE)
        #dc.DrawText('rating', 5, 60)
        dc.SetTextForeground(wx.BLACK)
        #dc.DrawText('rating', 8, 50)
        if (self.selected and self.border):
            dc.SetPen(wx.Pen(wx.Colour(255,51,0), 2))
            dc.DrawLines(self.border)
        

