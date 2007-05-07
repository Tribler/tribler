import wx, math, time, os, sys, threading
from traceback import print_exc
from Tribler.utilities import *
from wx.lib.stattext import GenStaticText as StaticText
from Tribler.Dialogs.ContentFrontPanel import ImagePanel
from Tribler.vwxGUI.GuiUtility import GUIUtility
from safeguiupdate import FlaglessDelayedInvocation
from Tribler.unicode import *
from copy import deepcopy
import cStringIO
from tribler_topButton import *
from urlparse import urlparse
from Tribler.timeouturlopen import urlOpenTimeout
import TasteHeart

DEBUG=True

class SubscriptionsItemPanel(wx.Panel):
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
        self.titleLength = 42 # num characters
        self.selected = False
        self.warningMode = False
        self.guiserver = parent.guiserver
        self.torrentfeed = parent.torrentfeed
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
        
        # Add Checkbox turn on/off
        self.cB = wx.CheckBox(self,-1,"",wx.Point(8,128),wx.Size(10,18))        
        self.cB.SetForegroundColour(wx.Colour(0,0,0))
        self.hSizer.Add(self.cB, 0, wx.ALL, 3)        
        
        # Add thumb / favicon from website?
        self.thumb = FavicoThumbnailViewer(self)
        self.thumb.setBackground(wx.BLACK)
        self.thumb.SetSize((16,16))
        self.hSizer.Add(self.thumb, 0, wx.ALL, 3)        
        # Add title
        self.title =wx.StaticText(self,-1,"Tribler discovery through other Tribler Users",wx.Point(0,0),wx.Size(550,20))        
        self.title.SetBackgroundColour(wx.BLUE)
        self.title.SetFont(wx.Font(12,74,90,wx.NORMAL,0,"Verdana"))
        self.title.SetMinSize((550,20))
        self.hSizer.Add(self.title, 1, wx.BOTTOM|wx.TOP, 3)     
        # Add title
        self.today =wx.StaticText(self,-1,"today: 10 files",wx.Point(0,0),wx.Size(140,18))        
        self.today.SetBackgroundColour(wx.WHITE)
        self.today.SetFont(wx.Font(10,74,90,wx.NORMAL,0,"Verdana"))
        self.today.SetMinSize((140,18))
        self.hSizer.Add(self.today, 0, wx.BOTTOM|wx.TOP|wx.RIGHT, 3)
       
        
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
        
        print "subip: setData called",peer_data
        if peer_data is None:
            self.datacopy = None
        
        if self.datacopy is not None and self.datacopy['url'] == peer_data['url']:
            if (self.datacopy['status'] == peer_data['status']):
                return
        
        self.data = peer_data

        if peer_data is not None:
            # deepcopy no longer works with 'ThumnailBitmap' on board
            self.datacopy = {}
            self.datacopy['url'] = peer_data['url']
            self.datacopy['status'] = peer_data['status']
        else:
            peer_data = {}
        
        if peer_data is None:
            peer_data = {}
        
        if peer_data.get('url'):
            title = peer_data['url'][:self.titleLength]
            self.title.Enable(True)
            self.title.SetLabel(title)
            self.title.Wrap(self.title.GetSize()[0])
            #self.title.SetToolTipString(peer_data['url'])
            self.cB.SetValue(peer_data['status'] == "active")
            if 'persistent' in self.data:
                self.delete.Disable()
            else:
                self.delete.Enable()
        else:
            self.title.SetLabel('')
            #self.title.SetToolTipString('')
            self.title.Enable(False)
            self.cB.SetValue(False)
            self.cB.Enable(False)
            self.delete.Enable(False)
       
        self.thumb.setData(peer_data)
               
        self.Layout()
        self.Refresh()
        #self.parent.Refresh()
        
          
        
    def select(self):
        print >>sys.stderr,'subip: selected',self.data
        self.thumb.setSelected(True)
        self.title.SetBackgroundColour(self.selectedColour)
        self.title.Refresh()
        
    def deselect(self, number = 0):
        #print >>sys.stderr,'subip: deselected',self.data
        if number % 2 == 0:
            colour = self.guiUtility.unselectedColour
        else:
            colour = self.guiUtility.unselectedColour2
            
        self.thumb.setSelected(False)
        self.title.SetBackgroundColour(colour)
        self.title.Refresh()
    
    def keyTyped(self, event):
        if self.selected:
            key = event.GetKeyCode()
            if (key == wx.WXK_DELETE):
                if self.data:
                    if DEBUG:
                        print >>sys.stderr,'subip: deleting'
#                    self.guiUtility.deleteTorrent(self.data)
        event.Skip()
        
    def mouseAction(self, event):
        print "subip: mouseAction",event.ButtonUp()
        obj = event.GetEventObject()
        name = obj.GetName()
        print "subip: mouseAction: name is",name
        
        
        self.SetFocus()
        if self.data:
            self.guiUtility.selectSubscription(self.data)

        
        if self.data is not None:
            if name == 'check':
                newstatus = not self.cB.GetValue()
                #self.cB.SetValue(newstatus)
                if 'persistent' in self.data:
                    self.toggleBuddycast(newstatus)
                else:
                    self.torrentfeed.setURLStatus(self.data['url'],newstatus)
            elif name == 'delete':
                self.torrentfeed.deleteURL(self.data['url'])
                # TODO: refresh view, hack it
                self.setData(None)
            
    def getIdentifier(self):
        if self.data:
            return self.data['url']
        
    def toggleBuddycast(self,status):
        self.utility.config.Write('enablerecommender',status, "boolean")                



class FavicoThumbnailViewer(wx.Panel, FlaglessDelayedInvocation):
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
        self.dataBitmap = self.maskBitmap = None
        self.data = None
        self.mouseOver = False
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnErase)
        self.selected = False
        self.border = None
    
        self.mm = self.GetParent().parent.mm
        
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
            bmp = self.mm.get_default('subscriptionsMode','DEFAULT_THUMB')
            # Check if we have already read the thumbnail and metadata information from this torrent file
            if data.get('metadata'):
                bmp = data['metadata'].get('ThumbnailBitmap')
                if not bmp:
                    bmp = self.mm.get_default('subscriptionMode','DEFAULT_THUMB')
            else:
                self.GetParent().guiserver.add_task(lambda:self.loadMetadata(data),0)
            
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
                
        self.dataBitmap = bmp
        self.xpos, self.ypos = (w-iw)/2, (h-ih)/2
        

    def loadMetadata(self,data):
        """ Called by non-GUI thread """
        
        if DEBUG:
            print "subip: ThumbnailViewer: loadMetadata: url",data['url']
        mimetype = None
        bmpdata = None
        if not ('persistent' in data):
            try:
                t = urlparse(data['url'])
                print "subip: ThumbnailViewer: loadMetadata: parsed url",t
                newurl = t[0]+'://'+t[1]+'/'+'favicon.ico'
                print "subip: ThumbnailViewer: loadMetadata: newurl",newurl
                stream = urlOpenTimeout(newurl,timeout=5)
                mimetype = 'image/x-ico' # 'image/vnd.microsoft.icon' # 'image/ico'
                bmpdata = stream.read()
                stream.close()
            except:
                print_exc()
        
        self.invokeLater(self.metadata_thread_gui_callback,[data,mimetype,bmpdata])
             
    def metadata_thread_gui_callback(self,data,mimetype,bmpdata):
        """ Called by GUI thread """

        if DEBUG:
            print "pip: ThumbnailViewer: GUI callback"

        metadata = {}
        if 'persistent' in data:
            metadata['ThumbnailBitmap'] = self.mm.get_default('subscriptionsMode','BUDDYCAST_THUMB')
        else:
            if mimetype is not None:
                metadata['ThumbnailBitmap'] = self.mm.data2wxBitmap(mimetype,bmpdata,dim=16)
            else:
                metadata['ThumbnailBitmap'] = None

        data['metadata'] = metadata
        
        # This item may be displaying another subscription right now, only show the icon
        # when it's still the same person
        if data['url'] == self.data['url']:
            if 'ThumbnailBitmap' in metadata and metadata['ThumbnailBitmap'] is not None:
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
            if DEBUG:
                print 'pip: enter' 
            self.mouseOver = True
            self.Refresh()
        elif event.Leaving():
            self.mouseOver = False
            if DEBUG:
                print 'pip: leave'
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
            #dc.DrawBitmap(self.dataBitmap, self.xpos,self.ypos, True)
            dc.DrawBitmap(self.dataBitmap, 0, 0, True)
