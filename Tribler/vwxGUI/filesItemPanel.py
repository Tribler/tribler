# Written by Jelle Roozenburg, Maarten ten Brinke, Lucan Musat
# see LICENSE.txt for license information

import wx, math, time, os, sys, threading
from traceback import print_exc,print_stack

from Tribler.utilities import *
#from wx.lib.stattext import GenStaticText as StaticText
from Tribler.vwxGUI.GuiUtility import GUIUtility
from safeguiupdate import FlaglessDelayedInvocation
from Tribler.unicode import *
from Utility.utility import getMetainfo
from copy import deepcopy
import cStringIO
import TasteHeart
from font import *

from Tribler.Overlay.MetadataHandler import MetadataHandler

DEBUG=False

# font sizes
if sys.platform == 'darwin':
    FS_FILETITLE = 10
    FS_HEARTRANK = 10
else:
    FS_FILETITLE = 8
    FS_HEARTRANK = 7

filesModeThumbSize = (125, 70)
libraryModeThumbSize = (66, 37)



class FilesItemPanel(wx.Panel):
    """
    This Panel shows one content item inside the GridPanel
    """
    def __init__(self, parent, keyfun):
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
        self.metadatahandler = MetadataHandler.getInstance()
        self.addComponents()
        self.Show()
        self.Refresh()
        self.Layout()
        self.gridKeyTyped = keyfun

    def addComponents(self):
        self.Show(False)
        self.SetMinSize((125,110))
        self.selectedColour = wx.Colour(255,200,187)       
        self.unselectedColour = wx.WHITE
        
        self.SetBackgroundColour(self.unselectedColour)
        self.vSizer = wx.BoxSizer(wx.VERTICAL)
        
        self.Bind(wx.EVT_LEFT_UP, self.mouseAction)
        self.Bind(wx.EVT_KEY_UP, self.keyTyped)
        
        # Add title
        self.thumb = ThumbnailViewer(self, 'filesMode')
        self.thumb.setBackground(wx.BLACK)
        self.thumb.SetSize((125,70))
        self.vSizer.Add(self.thumb, 0, wx.ALL, 0)        
        self.title =wx.StaticText(self,-1,"",wx.Point(0,0),wx.Size(125,22), wx.ST_NO_AUTORESIZE)        
        self.title.SetBackgroundColour(wx.WHITE)
        self.title.SetFont(wx.Font(FS_FILETITLE,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
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
            window.Bind(wx.EVT_LEFT_DCLICK, self.doubleClicked)
            window.Bind(wx.EVT_RIGHT_DOWN, self.mouseAction)            
            #window.Bind(wx.EVT_RIGHT_DOWN, self.rightMouseButton)  
            
                             
    def setData(self, torrent):
        
        """
        if DEBUG:
            if torrent is None:
                stat = 'None'
            else:
                stat = `torrent['content_name']`
            print >>sys.stderr,"fip: setData:",stat
        """
        
        if torrent is None:
            self.datacopy = None
            
        # set bitmap, rating, title
        if self.datacopy and torrent and self.datacopy['infohash'] == torrent['infohash']:
            # Do not update torrents that have no new seeders/leechers/size
            if (self.datacopy['seeder'] == torrent['seeder'] and
                self.datacopy['leecher'] == torrent['leecher'] and
                self.datacopy['length'] == torrent['length'] and
                self.datacopy.get('myDownloadHistory') == torrent.get('myDownloadHistory')):
                return
        
        self.data = torrent

        if torrent is not None:
            # deepcopy no longer works with 'ThumnailBitmap' on board
            self.datacopy = {}
            self.datacopy['infohash'] = torrent['infohash']
            self.datacopy['seeder'] = torrent['seeder']
            self.datacopy['leecher'] = torrent['leecher']
            self.datacopy['length'] = torrent.get('length')
            self.datacopy['myDownloadHistory'] = torrent.get('myDownloadHistory')
            #web2.0 item elements
            self.datacopy['web2'] = torrent.get('web2')
            self.datacopy['preview'] = torrent.get('preview')
        else:
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
        
        self.Layout()
        self.Refresh()
        #self.parent.Refresh()
        
          
    def select(self, rowIndex, colIndex):
        self.selected = True
        if DEBUG:
            print >>sys.stderr,'fip: item selected'
        colour = self.guiUtility.selectedColour
        self.thumb.setSelected(True)
        self.title.SetBackgroundColour(colour)
        self.title.Refresh()
        
    def deselect(self, rowIndex, colIndex):
        self.selected = False
        colour = self.guiUtility.unselectedColour
            
        self.thumb.setSelected(False)
        self.title.SetBackgroundColour(colour)
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
        try:
            self.gridKeyTyped(event)
        except:
            print 'Exception in keytyped'
            
            
        
    def mouseAction(self, event):        
        self.SetFocus()
        if self.data:
            # torrent data is sent to guiUtility > standardDetails.setData
            self.guiUtility.selectTorrent(self.data)
            
        if event.RightDown():
            self.rightMouseButton(event)
            

    def rightMouseButton(self, event):       
        menu = self.guiUtility.OnRightMouseAction(event)
        self.PopupMenu(menu, (-1,-1)) 

    def doubleClicked(self, event):
        self.guiUtility.standardDetails.download(self.data)
        
    def getIdentifier(self):
        return self.data['infohash']


                
class ThumbnailViewer(wx.Panel, FlaglessDelayedInvocation):
    """
    Show thumbnail and mast with info on mouseOver
    """

    def __init__(self, parent, mode, **kw):    
        wx.Panel.__init__(self, parent, **kw)
        self.metadatahandler = parent.metadatahandler
        self.mode = mode
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
        self.triblerGrey = wx.Colour(128,128,128)
        self.triblerLightGrey = wx.Colour(203,203,203)   
        self.guiUtility = GUIUtility.getInstance()
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
        #if torrent.get('web2'):
            #import pdb
            #pdb.set_trace()
        # Get the file(s)data for this torrent
        try:
            bmp = self.mm.get_default(self.mode,'DEFAULT_THUMB')
            # Check if we have already read the thumbnail and metadata information from this torrent file
            if torrent.get('metadata'):
                if self.mode == 'libraryMode':
                    # Make a resized thumb for lib view
                    bmp = torrent['metadata'].get('ThumbnailBitmap')
                    img = bmp.ConvertToImage()
                    bmp = self.getResizedBitmapFromImage(img, libraryModeThumbSize)
                        
                elif self.mode == 'filesMode':
                    bmp = torrent['metadata'].get('ThumbnailBitmap')
                if not bmp:
                    #print 'fip: ThumbnailViewer: Error: thumbnailBitmap not found in torrent %s' % torrent
                    bmp = self.mm.get_default(self.mode,'DEFAULT_THUMB')
            else:
                #print "fip: ThumbnailViewer: set: Scheduling read of metadata"
                # web2.0 elements already have the thumbnail stored at key 'preview'
                if 'query_permid' in torrent:
                    # Remote query result, no .torrent file avail
                    return
                elif torrent.get('preview'):
                    self.GetParent().guiserver.add_task(lambda:self.loadMetadata(torrent,None),0)
                else:
                    (torrent_dir,torrent_name) = self.metadatahandler.get_std_torrent_dir_name(torrent)
                    torrent_filename = os.path.join(torrent_dir, torrent_name)
                    
                    if DEBUG:
                        print "fip: Scheduling read of thumbnail for",torrent_filename
                    self.GetParent().guiserver.add_task(lambda:self.loadMetadata(torrent,torrent_filename),0)
            
            self.setBitmap(bmp)
            width, height = self.GetSize()
            d = 1
            self.border = [wx.Point(0,d), wx.Point(width-d, d), wx.Point(width-d, height-d), wx.Point(d,height-d), wx.Point(d,0)]
            self.Refresh()
            
        except:
            print_exc()
        
         
    def setBitmap(self, bmp):
        # Recalculate image placement
        w, h = self.GetSize()
        iw, ih = bmp.GetSize()
                
        self.torrentBitmap = bmp
        self.xpos, self.ypos = (w-iw)/2, (h-ih)/2
        
        
    def loadMetadata(self, torrent,torrent_filename):
        """ Called by separate non-GUI thread """
        
        if DEBUG:
            print >>sys.stderr,"fip: ThumbnailViewer: loadMetadata",torrent_filename
        if not torrent.get('preview'):
            if not os.path.exists(torrent_filename):
                if DEBUG:    
                    print >>sys.stderr,"fip: ThumbnailViewer: loadMetadata: %s does not exist" % torrent_filename
                return None

            # We can't do any wx stuff here apparently, so the only thing we can do is to
            # read the data from the torrent file and create the wxBitmap in the GUI callback.

            newmetadata = loadAzureusMetadataFromTorrent(torrent_filename)
        else:
            newmetadata = { 'Thumbnail' : torrent['preview'] }

      
        self.invokeLater(self.metadata_thread_gui_callback,[torrent,newmetadata])

             
    def metadata_thread_gui_callback(self,torrent,metadata):
        """ Called by GUI thread """

        #print 'Azureus_thumb: %s' % thumbnailString
        thumbnailString = metadata.get('Thumbnail')
         
        if thumbnailString:
            #print 'Found thumbnail: %s' % thumbnailString
            
            img = createThumbImage(thumbnailString)
            if img is None:
                return
            bmp = self.getResizedBitmapFromImage(img, filesModeThumbSize)
            if bmp:
                metadata['ThumbnailBitmap'] = bmp
                
            ## We now scale live
            #bmplib = self.getResizedBitmapFromImage(img, libraryModeThumbSize)
            #if bmplib:
            #    metadata['ThumbnailBitmapLibrary'] = bmplib
                
            # Dump the raw data
            del metadata['Thumbnail']
          
        torrent['metadata'] = metadata
        
        # This item may be displaying another torrent right now, only show the icon
        # when it's still the same torrent
        
        #print >>sys.stderr,"fip: meta_gui_cb: old torrent",`torrent['content_name']`,"new torrent",`self.torrent['content_name']`
        #print >>sys.stderr,"fip: meta_gui_cb: old torrent",`torrent['infohash']`,"new torrent",`self.torrent['infohash']`
        
        if torrent['infohash'] == self.torrent['infohash']:
            bmp = metadata.get('ThumbnailBitmap')
            if bmp:
                if self.mode == 'libraryMode':
                    bmp = self.getResizedBitmapFromImage(img, libraryModeThumbSize)
                self.setBitmap(bmp)
                self.Refresh()

             
    def getResizedBitmapFromImage(self, img, size):
        "Resize image to size of self"
        iw, ih = img.GetSize()
        w, h = size

        if iw == 0 or ih == 0:
            # Can happen when there is not handler for image type
            return None
        
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
        return bmp
            
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
        

        if self.torrent and self.mode == 'filesMode':
            rank = self.torrent.get('simRank', -1)
        else:
            rank = -1
            
        heartBitmap = TasteHeart.getHeartBitmap(rank)
        
        
        if self.torrentBitmap:
            dc.DrawBitmap(self.torrentBitmap, self.xpos,self.ypos, True)
#            dc.SetFont(wx.Font(6, wx.SWISS, wx.NORMAL, wx.BOLD, True))
#            dc.DrawBitmap(MASK_BITMAP,0 ,52, True)
#            dc.SetTextForeground(wx.BLACK)
            #dc.DrawText('rating', 8, 50)
        if self.mouseOver:
            dc.SetFont(wx.Font(6, FONTFAMILY,FONTWEIGHT, wx.BOLD, True, FONTFACE))
            mask = self.mm.get_default('filesMode','MASK_BITMAP')
            dc.DrawBitmap(mask,0 ,0, True)
        
        if heartBitmap:
            mask = self.mm.get_default('filesMode','MASK_BITMAP_BOTTOM')
            margin = 52
            dc.DrawBitmap(mask,0 ,margin, True)
            dc.DrawBitmap(heartBitmap,5 ,margin+2, True)
            dc.SetFont(wx.Font(FS_HEARTRANK, FONTFAMILY, FONTWEIGHT, wx.BOLD, False, FONTFACE))
            text = repr(rank)                
            dc.DrawText(text, 22, margin+4)
                
            
        if self.border:
            if self.selected:
                dc.SetPen(wx.Pen(wx.Colour(255,51,0), 2))
            else:
                dc.SetPen(wx.Pen(self.triblerLightGrey, 2))
            dc.DrawLines(self.border)


def loadAzureusMetadataFromTorrent(torrent_filename):
    metadata = getMetainfo(torrent_filename)
    if not metadata:
        return None
            
    newmetadata = metadata.get('azureus_properties', {}).get('Content',{})
    for key in ['encoding','comment','comment-utf8']: # 'created by'
        if key in metadata:
            newmetadata[key] = metadata[key]
    return newmetadata


def createThumbImage(imgdata):
    try:
        # Simple protection against bad parsing of websites, if the
        # image data is HTML, ignore it.
        
        low = imgdata[:5].lower()
        if low == '<html' or low == '<!doc':
            return None
    except:
        #print_exc()
        pass
    
    stream = cStringIO.StringIO(imgdata)
    img =  wx.ImageFromStream(stream)
    if not img.Ok():
        return None
    return img
