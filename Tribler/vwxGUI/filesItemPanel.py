import wx, math, time, os, sys, threading
from traceback import print_exc
from threading import Thread, Lock
from Tribler.utilities import *
from wx.lib.stattext import GenStaticText as StaticText
from Tribler.Dialogs.ContentFrontPanel import ImagePanel
from Tribler.vwxGUI.GuiUtility import GUIUtility
from Tribler.unicode import *
from copy import deepcopy
import cStringIO

DEBUG=True

class FilesItemPanel(wx.Panel):
    """
    TorrentPanel shows one content item inside the StaticGridPanel
    Currently, TorrentPanel only shows torretname, seeders, leechers and size
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
        self.selectedColour = wx.Colour(245,208,120)       
        self.unselectedColour = wx.WHITE
        
        
        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        
        self.Bind(wx.EVT_LEFT_UP, self.mouseAction)
        self.Bind(wx.EVT_KEY_UP, self.keyTyped)
        
        # Add title
        self.thumb = ThumbnailViewer(self)
        self.thumb.setBackground(wx.BLACK)
        self.thumb.SetSize((125,70))
        self.vSizer.Add(self.thumb, 0, wx.ALL, 0)        
        self.title =wx.StaticText(self,-1,"",wx.Point(0,0),wx.Size(125,15))        
        self.title.SetBackgroundColour(wx.WHITE)
        self.title.SetFont(wx.Font(10,74,90,wx.NORMAL,0,"Verdana"))
        self.title.SetMinSize((125,40))
        self.vSizer.Add(self.title, 0, wx.ALL|wx.EXPAND, 3)     

        self.SetSizer(self.vSizer);
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
        try:
            self.datacopy = deepcopy(torrent)
        except:
            print 'Error: could not datacopy: %s' % torrent
        
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
            
       
        self.thumb.setTorrent(torrent)
        self.torrentBitmap = self.thumb.torrentBitmap
        
        self.Layout()
        self.Refresh()
        #self.parent.Refresh()
        
          
        
    def select(self):
        print 'item selected'
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
            # torrent data is sent to guiUtility > standardDetails.setData
            self.guiUtility.selectTorrent(self.data)
                
                
DEFAULT_THUMB = wx.Bitmap(os.path.join('Tribler', 'vwxGUI', 'images', 'defaultThumb.png'))
MASK_BITMAP = wx.Bitmap(os.path.join('Tribler', 'vwxGUI', 'images', 'itemMask.png'))
        

class ThumbnailViewer(wx.Panel):
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
        self.backgroundColor = wx.WHITE
        self.torrentBitmap = None
        self.torrentLock = Lock()
        self.torrent = None
        self.mouseOver = False
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility
        self.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)
        self.Bind(wx.EVT_LEFT_UP, self.guiUtility.buttonClicked)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnErase)
        self.selected = False
        
        
        
    
    def setTorrent(self, torrent):
        if not torrent:
            self.Hide()
            self.Refresh()
            return
        
        if not self.IsShown():
                self.Show()
                
        if torrent != self.torrent:
            self.torrent = torrent
            self.setThumbnail(torrent)
                                        
    
    def setThumbnail(self, torrent):
        # Get the file(s)data for this torrent
        try:
            bmp = DEFAULT_THUMB
            # Check if we have already read the thumbnail and metadata information from this torrent file
            if torrent.get('metadata'):
                bmp = torrent['metadata'].get('ThumbnailBitmap')
                if not bmp:
                    print 'ThumbnailViewer: Error: thumbnailBitmap not found in torrent %s' % torrent
                    bmp = DEFAULT_THUMB
            else:
                # Do the loading of metadata and thumbnail in new thread
                # so that navigation is not slowed down
                Thread(target = self.loadMetadata, args=(torrent,)).start()
            
            self.setBitmap(bmp)
            self.Refresh()
            
        except:
            print_exc(file=sys.stderr)
            return {}           
        
         
    def setBitmap(self, bmp):
        # Recalculate image placement
        w, h = self.GetSize()
        iw, ih = bmp.GetSize()
                
        self.torrentLock.acquire()
        self.torrentBitmap = bmp
        self.xpos, self.ypos = (w-iw)/2, (h-ih)/2
        self.torrentLock.release()
        
        
    def loadMetadata(self, torrent):
         torrent_dir = torrent['torrent_dir']
         torrent_file = torrent['torrent_name']
        
         if not os.path.exists(torrent_dir):
             torrent_dir = os.path.join(self.utility.getConfigPath(), "torrent2")
        
         torrent_filename = os.path.join(torrent_dir, torrent_file)
        
         if not os.path.exists(torrent_filename):
             if DEBUG:    
                 print >>sys.stderr,"contentpanel: Torrent: %s does not exist" % torrent_filename
             return None
        
         metadata = self.utility.getMetainfo(torrent_filename)
         if not metadata:
             return None
        
         self.torrentLock.acquire()
         torrent['metadata'] = metadata.get('azureus_properties', {}).get('Content',{})
         self.torrentLock.release()
         
         #print 'Azureus_thumb: %s' % thumbnailString
         thumbnailString = torrent.get('metadata', {}).get('Thumbnail')
         
         if thumbnailString:
             #print 'Found thumbnail: %s' % thumbnailString
             stream = cStringIO.StringIO(thumbnailString)
             img =  wx.ImageFromStream( stream )
             iw, ih = img.GetSize()
             w, h = self.GetSize()
             if (iw/float(ih)) > (w/float(h)):
                 nw = w
                 nh = int(ih * w/float(iw))
             else:
                 nh = h
                 nw = int(iw * h/float(ih))
             if nw != iw or nh != ih:
                 #print 'Rescale from (%d, %d) to (%d, %d)' % (iw, ih, nw, nh)
                 img.Rescale(nw, nh)
             bmp = wx.BitmapFromImage(img)
            
             
             self.torrentLock.acquire()
             torrent['metadata']['ThumbnailBitmap'] = bmp
             self.setBitmap(bmp)
             
             # should this be done by the GUI thread??
             self.Refresh()
             
    
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
            #print 'enter' 
            self.mouseOver = True
            self.Refresh()
        elif event.Leaving():
            self.mouseOver = False
            #print 'leave'
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
        
        if self.torrentBitmap:
            dc.DrawBitmap(self.torrentBitmap, self.xpos,self.ypos, True)
        if (self.mouseOver or self.selected):
            dc.SetFont(wx.Font(6, wx.SWISS, wx.NORMAL, wx.BOLD, True))
            dc.DrawBitmap(MASK_BITMAP,0 ,0, True)
            dc.SetTextForeground(wx.WHITE)
            dc.DrawText('rating', 5, 40)
        

