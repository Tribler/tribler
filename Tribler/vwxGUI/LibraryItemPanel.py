import wx, math, time, os, sys, threading
from traceback import print_exc
from Tribler.utilities import *
from wx.lib.stattext import GenStaticText as StaticText
from Tribler.Dialogs.ContentFrontPanel import ImagePanel
from Tribler.vwxGUI.GuiUtility import GUIUtility
from Tribler.unicode import *
from tribler_topButton import *
from copy import deepcopy
from bgPanel import *
import cStringIO

DEBUG=True

class LibraryItemPanel(wx.Panel):
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
        self.selectedColour = wx.Colour(245,208,120)
        self.unselectedColour = wx.WHITE
        
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.Bind(wx.EVT_LEFT_UP, self.mouseAction)
        self.Bind(wx.EVT_KEY_UP, self.keyTyped)
        
        # Add thumb        
        self.thumbnail = bgPanel(self, -1, wx.Point(0,0), wx.Size(66,37))
        self.thumbnail.setBackground(wx.BLACK)
        self.thumbnail.SetSize((66,37))
        #self.hSizer.Add(self.thumbnail, 0, wx.ALL|wx.EXPAND, 0)        
        # Add title
        self.title = wx.StaticText(self,-1,"",wx.Point(0,0),wx.Size(225,15))        
        self.title.SetBackgroundColour(wx.WHITE)
        self.title.SetFont(wx.Font(10,74,90,wx.NORMAL,0,"Verdana"))
        self.title.SetMinSize((225,40))
        self.hSizer.Add(self.title, 0, wx.ALL|wx.EXPAND, 3)             
        # Add checkBox -Private & -Archive
        self.cbPrivate = wx.CheckBox(self,-1,"",wx.Point(258,3),wx.Size(13,13))
        self.cbPrivateLabel = wx.StaticText(self,-1,"",wx.Point(274,3),wx.Size(77,15),wx.ST_NO_AUTORESIZE)
        self.cbPrivateLabel.SetLabel("archive")
        self.cbPrivateSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.cbPrivateSizer.Add(self.cbPrivate, 0, wx.LEFT|wx.EXPAND, 3)     
        self.cbPrivateSizer.Add(self.cbPrivateLabel, 0, wx.LEFT|wx.EXPAND, 3)     

        self.cbArchive = wx.CheckBox(self,-1,"",wx.Point(258,18),wx.Size(13,13))
        self.cbArchiveLabel = wx.StaticText(self,-1,"",wx.Point(274,3),wx.Size(77,15),wx.ST_NO_AUTORESIZE)
        self.cbArchiveLabel.SetLabel("private")
        self.cbArchiveSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.cbArchiveSizer.Add(self.cbArchive, 0, wx.LEFT|wx.EXPAND, 3)     
        self.cbArchiveSizer.Add(self.cbArchiveLabel, 0, wx.LEFT|wx.EXPAND, 3)     
        
        self.cbSizer = wx.BoxSizer(wx.VERTICAL)
        self.cbSizer.Add(self.cbPrivateSizer,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.cbSizer.Add(self.cbArchiveSizer,0,wx.TOP|wx.EXPAND|wx.FIXED_MINSIZE,3)
        self.hSizer.Add(self.cbSizer, 0, wx.ALL|wx.EXPAND, 3)     
        # Add Gauge/progressbar
        self.pb = wx.Gauge(self,-1,100,wx.Point(359,0),wx.Size(100,15),wx.EXPAND|wx.GA_HORIZONTAL)
        self.pause = tribler_topButton(self, -1, wx.Point(542,3), wx.Size(17,17),name='pause' )
        self.delete = tribler_topButton(self, -1, wx.Point(542,3), wx.Size(17,17),name='delete')        
        self.pauseStopSizer = wx.BoxSizer(wx.HORIZONTAL|wx.EXPAND)
        self.pauseStopSizer.Add(self.pb,0,wx.TOP|wx.FIXED_MINSIZE,3)
        self.pauseStopSizer.Add(self.pause,0,wx.TOP|wx.EXPAND|wx.LEFT|wx.FIXED_MINSIZE,3)
        self.pauseStopSizer.Add(self.delete,0,wx.TOP|wx.EXPAND|wx.LEFT|wx.FIXED_MINSIZE,3)
       
        self.pbLabel = wx.StaticText(self,-1,"10min30",wx.Point(274,3),wx.Size(100,15),wx.ST_NO_AUTORESIZE|wx.ALIGN_CENTRE)                        
        
        self.pbSizer = wx.BoxSizer(wx.VERTICAL|wx.EXPAND)
        self.pbSizer.Add(self.pauseStopSizer,0,wx.FIXED_MINSIZE)
        self.pbSizer.Add(self.pbLabel,0,wx.TOP|wx.FIXED_MINSIZE,3)
        
        self.hSizer.Add(self.pbSizer, 0, wx.ALL|wx.EXPAND, 3)         
        
        # Upload speed
        #self.pbLabel = wx.StaticText(self,-1,"10min30",wx.Point(274,3),wx.Size(100,15),wx.ST_NO_AUTORESIZE|wx.ALIGN_CENTRE)                        

        # Add message        
        self.messageLabel = wx.StaticText(self,-1,"message",wx.Point(274,3),wx.Size(130,15),wx.ST_NO_AUTORESIZE|wx.ALIGN_CENTRE)        
        self.hSizer.Add(self.messageLabel, 0, wx.ALL|wx.EXPAND, 8) 
        # Add Refresh        
        self.SetSizer(self.hSizer);
        self.SetAutoLayout(1);
        self.Layout();
        self.Refresh()
        
        for window in self.GetChildren():
            window.Bind(wx.EVT_LEFT_UP, self.mouseAction)
            window.Bind(wx.EVT_KEY_UP, self.keyTyped)
                             
    def setData(self, torrent):
        # set bitmap, rating, title
        
        try:
            if self.datacopy['infohash'] == torrent['infohash']:
                # Do not update torrents that have no new seeders/leechers/size
                if (self.datacopy['seeder'] == torrent['seeder'] and
                    self.datacopy['leecher'] == torrent['leecher'] and
                    self.datacopy['length'] == torrent['length'] and
                    self.datacopy.get('myDownloadHistory') == torrent.get('myDownloadHistory')):
                    return
        except:
            pass
        
        self.data = torrent
        self.datacopy = deepcopy(torrent)
        
        if torrent == None:
            torrent = {}
        
        if torrent.get('content_name'):
            title = torrent['content_name'][:self.titleLength]
            self.title.Enable(True)
            self.title.SetLabel(title)
            self.title.Wrap(self.title.GetSize()[0])
            self.title.SetToolTipString(torrent['content_name'])
        else:
            self.title.SetLabel('')
            self.title.SetToolTipString('')
            self.title.Enable(False)
            
       
        #self.thumb.setTorrent(torrent)
               
        self.Layout()
        self.Refresh()
        #self.parent.Refresh()
        
          
        
    def select(self):
        self.selected = True
        old = self.title.GetBackgroundColour()
        if old != self.selectedColour:
            self.title.SetBackgroundColour(self.selectedColour)
            self.Refresh()
        
        
    def deselect(self):
        self.selected = False
        old = self.title.GetBackgroundColour()
        if old != self.unselectedColour:
            self.title.SetBackgroundColour(self.unselectedColour)
            self.Refresh()
    
    def keyTyped(self, event):
        if self.selected:
            key = event.GetKeyCode()
            if (key == wx.WXK_DELETE):
                if self.data:
                    if DEBUG:
                        print >>sys.stderr,'contentpanel: deleting'
                    self.guiUtility.deleteTorrent(self.data)
        event.Skip()
        
    def mouseAction(self, event):
        
        self.SetFocus()
        if self.data:
            self.guiUtility.selectTorrent(self.data)
                
                
DEFAULT_THUMB = wx.Bitmap(os.path.join('Tribler', 'vwxGUI', 'images', 'defaultThumb.png'))

#class ThumbnailViewer(wx.Panel):
#    """
#    Show thumbnail and mast with info on mouseOver
#    """
#
#    def __init__(self, *args, **kw):    
#        if len(args) == 0:
#            pre = wx.PrePanel()
#            # the Create step is done by XRC.
#            self.PostCreate(pre)
#            self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate)
#        else:
#            wx.Panel.__init__(self, *args, **kw)
#            self._PostInit()
#        
#    def OnCreate(self, event):
#        self.Unbind(wx.EVT_WINDOW_CREATE)
#        wx.CallAfter(self._PostInit)
#        event.Skip()
#        return True
#    
#    def _PostInit(self):
#        # Do all init here
#        self.backgroundColor = wx.WHITE
#        self.torrentBitmap = self.maskBitmap = None
#        self.torrent = None
#        self.mouseOver = False
#        self.guiUtility = GUIUtility.getInstance()
#        self.utility = self.guiUtility.utility
#        self.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)
#        self.Bind(wx.EVT_LEFT_UP, self.guiUtility.buttonClicked)
#        self.Bind(wx.EVT_PAINT, self.OnPaint)
#        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnErase)
#        self.selected = False
#        
#        
#        
#    
#    def setTorrent(self, torrent):
#        if not torrent:
#            self.Hide()
#            self.Refresh()
#            return
#        
#        if not self.IsShown():
#                self.Show()
#                
#        if torrent != self.torrent:
#            self.torrent = torrent
#            self.torrentBitmap = self.getThumbnail(torrent)
#            # If failed, choose standard thumb
#            if not self.torrentBitmap:
#                self.torrentBitmap = DEFAULT_THUMB
#            # Recalculate image placement
#            w, h = self.GetSize()
#            iw, ih = self.torrentBitmap.GetSize()
#            self.xpos, self.ypos = (w-iw)/2, (h-ih)/2
#        if not self.maskBitmap:
#            self.maskBitmap = wx.Bitmap(os.path.join('Tribler', 'vwxGUI', 'images', 'itemMask.png'))
#        self.Refresh()
#                                        
#    
#    def getThumbnail(self, torrent):
#        # Get the file(s)data for this torrent
#        try:
#            torrent_dir = torrent['torrent_dir']
#            torrent_file = torrent['torrent_name']
#            
#            if not os.path.exists(torrent_dir):
#                torrent_dir = os.path.join(self.utility.getConfigPath(), "torrent2")
#            
#            torrent_filename = os.path.join(torrent_dir, torrent_file)
#            
#            if not os.path.exists(torrent_filename):
#                if DEBUG:    
#                    print >>sys.stderr,"contentpanel: Torrent: %s does not exist" % torrent_filename
#                return None
#            
#            metadata = self.utility.getMetainfo(torrent_filename)
#            if not metadata:
#                return None
#            
#            thumbnailString = metadata.get('azureus_properties', {}).get('Content',{}).get('Thumbnail')
#            #print 'Azureus_thumb: %s' % thumbnailString
#            
#            if thumbnailString:
#                #print 'Found thumbnail: %s' % thumbnailString
#                stream = cStringIO.StringIO(thumbnailString)
#                img =  wx.ImageFromStream( stream )
#                iw, ih = img.GetSize()
#                w, h = self.GetSize()
#                if (iw/float(ih)) > (w/float(h)):
#                    nw = w
#                    nh = int(ih * w/float(iw))
#                else:
#                    nh = h
#                    nw = int(iw * h/float(ih))
#                if nw != iw or nh != ih:
#                    print 'Rescale from (%d, %d) to (%d, %d)' % (iw, ih, nw, nh)
#                    img.Rescale(nw, nh)
#                bmp = wx.BitmapFromImage(img)
#                # Rescale the image so that its
#                return bmp
#        except:
#            print_exc(file=sys.stderr)
#            return {}           
#        
#                       
#        
#    
#    
#    def OnErase(self, event):
#        pass
#        #event.Skip()
#        
#    def setSelected(self, sel):
#        self.selected = sel
#        self.Refresh()
#        
#    def isSelected(self):
#        return self.selected
#        
#    def mouseAction(self, event):
#        if event.Entering():
#            print 'enter' 
#            self.mouseOver = True
#            self.Refresh()
#        elif event.Leaving():
#            self.mouseOver = False
#            print 'leave'
#            self.Refresh()
#        elif event.ButtonUp():
#            self.ClickedButton()
#        #event.Skip()
#        """
#    def ClickedButton(self):
#        print 'Click'
#        """
#                
#    def setBackground(self, wxColor):
#        self.backgroundColor = wxColor
#        
#    def OnPaint(self, evt):
#        dc = wx.BufferedPaintDC(self)
#        dc.SetBackground(wx.Brush(self.backgroundColor))
#        dc.Clear()
#        
#        if self.torrentBitmap:
#            dc.DrawBitmap(self.torrentBitmap, self.xpos,self.ypos, True)
#        if (self.mouseOver or self.selected) and self.maskBitmap:
#            dc.SetFont(wx.Font(6, wx.SWISS, wx.NORMAL, wx.BOLD, True))
#            dc.DrawBitmap(self.maskBitmap,0 ,0, True)
#            dc.SetTextForeground(wx.WHITE)
#            dc.DrawText('rating', 5, 40)
#        

