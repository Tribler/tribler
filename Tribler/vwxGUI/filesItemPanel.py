import wx, math, time, os, sys, threading
from traceback import print_exc,print_stack
from Tribler.utilities import *
#from wx.lib.stattext import GenStaticText as StaticText
from Tribler.Dialogs.ContentFrontPanel import ImagePanel
from Tribler.vwxGUI.GuiUtility import GUIUtility
from safeguiupdate import FlaglessDelayedInvocation
from Tribler.unicode import *
from copy import deepcopy
import cStringIO

DEBUG=True

class FilesItemPanel(wx.Panel):
    """
    This Panel shows one content item inside the GridPanel
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
        self.guiserver = parent.guiserver
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
        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        
        self.Bind(wx.EVT_LEFT_UP, self.mouseAction)
        self.Bind(wx.EVT_KEY_UP, self.keyTyped)
        
        # Add title
        self.thumb = ThumbnailViewer(self)
        self.thumb.setBackground(wx.BLACK)
        self.thumb.SetSize((125,70))
        self.vSizer.Add(self.thumb, 0, wx.ALL, 0)        
        self.title =wx.StaticText(self,-1,"",wx.Point(0,0),wx.Size(125,22), wx.ST_NO_AUTORESIZE)        
        self.title.SetBackgroundColour(wx.WHITE)
        self.title.SetFont(wx.Font(8,74,90,wx.NORMAL,0,"Verdana"))
        self.title.SetMinSize((125,40))
        self.vSizer.Add(self.title, 0, wx.BOTTOM, 3)     
        self.vSizer.Add([100,5],0,wx.EXPAND|wx.FIXED_MINSIZE,3)        
        self.SetSizer(self.vSizer);
        self.SetAutoLayout(1);
        self.Layout();
        self.Refresh()
        
        for window in self.GetChildren():
            window.Bind(wx.EVT_LEFT_UP, self.mouseAction)
            window.Bind(wx.EVT_KEY_UP, self.keyTyped)
                             
    def setData(self, torrent):
        
        if torrent is None:
            torrent = {}
            
        # set bitmap, rating, title
        if self.datacopy and torrent and self.datacopy['infohash'] == torrent['infohash']:
            # Do not update torrents that have no new seeders/leechers/size
            if (self.datacopy['seeder'] == torrent['seeder'] and
                self.datacopy['leecher'] == torrent['leecher'] and
                self.datacopy['length'] == torrent['length'] and
                self.datacopy.get('myDownloadHistory') == torrent.get('myDownloadHistory')):
                return
        
        self.data = torrent

        if torrent:
            # deepcopy no longer works with 'ThumnailBitmap' on board
            self.datacopy = {}
            self.datacopy['infohash'] = torrent['infohash']
            self.datacopy['seeder'] = torrent['seeder']
            self.datacopy['leecher'] = torrent['leecher']
            self.datacopy['length'] = torrent['length']
            self.datacopy['myDownloadHistory'] = torrent.get('myDownloadHistory')
        else:
            self.datacopy = {}

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
        
        self.Layout()
        self.Refresh()
        #self.parent.Refresh()
        
          
    def select(self):
        if DEBUG:
            print 'fip: item selected',self.data.keys()
            
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
                        print >>sys.stderr,'fip: deleting'
                    self.guiUtility.deleteTorrent(self.data)
        event.Skip()
        
    def mouseAction(self, event):
        
        self.SetFocus()
        if self.data:
            # torrent data is sent to guiUtility > standardDetails.setData
            self.guiUtility.selectTorrent(self.data)
          
    def getIdentifier(self):
        return self.data['infohash']
                
class ThumbnailViewer(wx.Panel, FlaglessDelayedInvocation):
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
        FlaglessDelayedInvocation.__init__(self)
        self.backgroundColor = wx.WHITE
        self.torrentBitmap = None
        self.torrent = None
        self.mouseOver = False
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility
        self.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)
        self.Bind(wx.EVT_LEFT_UP, self.guiUtility.buttonClicked)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnErase)
        self.selected = False
        self.border = None
        self.mm = self.GetParent().parent.mm
        
    
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
            bmp = self.mm.get_default('filesMode','DEFAULT_THUMB')
            # Check if we have already read the thumbnail and metadata information from this torrent file
            if torrent.get('metadata'):
                bmp = torrent['metadata'].get('ThumbnailBitmap')
                if not bmp:
                    #print 'fip: ThumbnailViewer: Error: thumbnailBitmap not found in torrent %s' % torrent
                    bmp = self.mm.get_default('filesMode','DEFAULT_THUMB')
            else:
                #print "fip: ThumbnailViewer: set: Scheduling read of metadata"
                torrent_dir = torrent['torrent_dir']
                torrent_file = torrent['torrent_name']
        
                if not os.path.exists(torrent_dir):
                    torrent_dir = os.path.join(self.utility.getConfigPath(), "torrent2")
                torrent_filename = os.path.join(torrent_dir, torrent_file)
                
                print "fip: Scheduling read of thumbnail for",torrent_filename
                self.GetParent().guiserver.add_task(lambda:self.loadMetadata(torrent,torrent_filename),0)
            
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
                
        self.torrentBitmap = bmp
        self.xpos, self.ypos = (w-iw)/2, (h-ih)/2
        
        
    def loadMetadata(self, torrent,torrent_filename):
        """ Called by separate non-GUI thread """
        
        if DEBUG:
            print "fip: ThumbnailViewer: loadMetadata",torrent_filename
        if not os.path.exists(torrent_filename):
            if DEBUG:    
                print >>sys.stderr,"fip: ThumbnailViewer: loadMetadata: %s does not exist" % torrent_filename
            return None

        # We can't do any wx stuff here apparently, so the only thing we can do is to
        # read the data from the torrent file and create the wxBitmap in the GUI callback.
        
        metadata = self.utility.getMetainfo(torrent_filename)
        if not metadata:
            return None
        
        metadata = metadata.get('azureus_properties', {}).get('Content',{})
      
        self.invokeLater(self.metadata_thread_gui_callback,[torrent,metadata])
             
    def metadata_thread_gui_callback(self,torrent,metadata):
        """ Called by GUI thread """

        #print 'Azureus_thumb: %s' % thumbnailString
        thumbnailString = metadata.get('Thumbnail')
         
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
            
            metadata['ThumbnailBitmap'] = bmp
          
        torrent['metadata'] = metadata
        
        # This item may be displaying another torrent right now, only show the icon
        # when it's still the same torrent
        if torrent['infohash'] == self.torrent['infohash']:
            if 'ThumbnailBitmap' in metadata:
                self.setBitmap(metadata['ThumbnailBitmap'])
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
#            dc.SetFont(wx.Font(6, wx.SWISS, wx.NORMAL, wx.BOLD, True))
#            dc.DrawBitmap(MASK_BITMAP,0 ,52, True)
#            dc.SetTextForeground(wx.BLACK)
            #dc.DrawText('rating', 8, 50)
        if self.mouseOver:
            dc.SetFont(wx.Font(6, wx.SWISS, wx.NORMAL, wx.BOLD, True))
            mask = self.mm.get_default('filesMode','MASK_BITMAP')
            heart = self.mm.get_default('filesMode','HEART_BITMAP')
            dc.DrawBitmap(mask,0 ,52, True)
            dc.DrawBitmap(heart,5 ,54, True)
            dc.SetTextForeground(wx.BLACK)
            #dc.DrawText('rating', 8, 50)
        if (self.selected and self.border):
            dc.SetPen(wx.Pen(wx.Colour(255,51,0), 2))
            dc.DrawLines(self.border)
