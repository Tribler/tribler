import wx, math, time, os, sys, threading
from traceback import print_exc
from Tribler.utilities import *
from wx.lib.stattext import GenStaticText as StaticText
from Tribler.Dialogs.ContentFrontPanel import ImagePanel
from Tribler.vwxGUI.GuiUtility import GUIUtility
from Tribler.vwxGUI.PersonsItemPanel import ThumbnailViewer
from Tribler.unicode import *
from copy import deepcopy
import cStringIO
from tribler_topButton import *
from threading import Lock
import TasteHeart

DEBUG=True

class FriendsItemPanel(wx.Panel):
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
        self.titleLength = 77 # num characters
        self.selected = False
        self.warningMode = False
        self.guiserver = parent.guiserver
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
        
        self.SetBackgroundColour(self.unselectedColour)
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.Bind(wx.EVT_LEFT_UP, self.mouseAction)
        self.Bind(wx.EVT_KEY_UP, self.keyTyped)
        
        # Add thumb
        self.thumb = FriendThumbnailViewer(self)
        self.thumb.setBackground(wx.BLACK)
        self.thumb.SetSize((37,37))
        self.hSizer.Add(self.thumb, 0, wx.ALL, 3)        
        # Add title
        self.title =wx.StaticText(self,-1,"",wx.Point(0,0),wx.Size(100,15))        
        self.title.SetBackgroundColour(wx.WHITE)
        self.title.SetFont(wx.Font(11,74,90,wx.NORMAL,0,"Verdana"))
        self.title.SetMinSize((100,15))        
        self.title.SetLabel('blabla')
        # Add status
        self.status =wx.StaticText(self,-1,"",wx.Point(0,0),wx.Size(80,12))        
        self.status.SetBackgroundColour(wx.WHITE)
        self.status.SetFont(wx.Font(9,74,90,wx.NORMAL,0,"Verdana"))
        self.status.SetForegroundColour(wx.Colour(128,128,128))        
        self.status.SetMinSize((80,12))
        self.status.SetLabel('blabla')
        
        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        self.vSizer.Add(self.title,1,wx.TOP|wx.EXPAND,3)
        self.vSizer.Add(self.status,1,wx.TOP|wx.EXPAND,3)
        
        self.hSizer.Add(self.vSizer, 1, wx.RIGHT|wx.EXPAND, 5)
        # Add Taste similarity
        self.taste =wx.StaticText(self,-1,"",wx.Point(0,0),wx.Size(40,15))        
        self.taste.SetBackgroundColour(wx.WHITE)
        self.taste.SetFont(wx.Font(10,74,90,wx.NORMAL,0,"Verdana"))
        self.taste.SetMinSize((40,15))
        self.taste.SetLabel('heart')
        self.hSizer.Add(self.taste, 0, wx.TOP|wx.RIGHT, 5)
        
        # Add delete button
        self.delete = tribler_topButton(self, -1, wx.Point(0,0), wx.Size(17,17),name='delete')                
        self.hSizer.Add(self.delete, 0, wx.TOP|wx.RIGHT, 3)
        

        self.SetSizer(self.hSizer);
        self.SetAutoLayout(1);
        self.Layout();
        self.Refresh()
        
        for window in self.GetChildren():
            window.Bind(wx.EVT_LEFT_UP, self.mouseAction)
            window.Bind(wx.EVT_KEY_UP, self.keyTyped)
                             
    def setData(self, peer_data):
        # set bitmap, rating, title
        
        if self.datacopy is not None and self.datacopy['permid'] == peer_data['permid']:
            if (self.datacopy['last_seen'] == peer_data['last_seen'] and
                self.datacopy['similarity'] == peer_data['similarity'] and
                self.datacopy['name'] == peer_data['name'] and
                self.datacopy['content_name'] == peer_data['content_name'] and
                self.datacopy.get('friend') == peer_data.get('friend')):
                return
        
        self.data = peer_data

        if peer_data is not None:
            # deepcopy no longer works with 'ThumnailBitmap' on board
            self.datacopy = {}
            self.datacopy['permid'] = peer_data['permid']
            self.datacopy['last_seen'] = peer_data['last_seen']
            self.datacopy['similarity'] = peer_data['similarity']
            self.datacopy['name'] = peer_data['name']
            self.datacopy['content_name'] = peer_data['content_name']
            self.datacopy['friend'] = peer_data.get('friend')

        if peer_data is None:
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
        
        
                

class FriendThumbnailViewer(ThumbnailViewer):
    def __init__(self, *args, **kw):    
        ThumbnailViewer.__init__(self, *args, **kw)
        
    def OnPaint(self, evt):
        dc = wx.BufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.backgroundColor))
        dc.Clear()
        
        if self.dataBitmap:
            dc.DrawBitmap(self.dataBitmap, self.xpos,self.ypos, True)
#        if self.mouseOver:
        if self.data!=None and type(self.data)==type({}) and self.data.get('permid'):            
            self.Parent.status.SetLabel('status unknown')
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
                recomm = -1
            if recomm >=0 or self.data.get('friend') or self.data.get('online'):
                mask = self.mm.get_default('personsMode','MASK_BITMAP')
                dc.DrawBitmap(mask,0 ,62, True)
            if recomm >=0:
                dc.DrawBitmap(TasteHeart.BITMAPS[recomm],5 ,64, True)
                dc.SetFont(wx.Font(7, wx.SWISS, wx.NORMAL, wx.BOLD, False))
                text = repr(rank)                
                dc.DrawText(text, 22, 66)
            if self.data.get('friend'):
                friend = self.mm.get_default('personsMode','MASK_BITMAP')
                dc.DrawBitmap(friend,60 ,65, True)            
            if self.data.get('online'):                
                self.Parent.status.SetLabel('online')
                dc.SetFont(wx.Font(8, wx.SWISS, wx.NORMAL, wx.BOLD, False))
                dc.SetTextForeground('#007303')
                dc.DrawText('online', 26, 66)

                
        
#        dc.SetTextForeground(wx.WHITE)
        #dc.DrawText('rating', 5, 60)
        if (self.selected and self.border):
            dc.SetPen(wx.Pen(wx.Colour(255,51,0), 2))
            dc.DrawLines(self.border)
        

