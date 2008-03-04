import wx, math, time, os, sys, threading
from traceback import print_exc
from wx.lib.stattext import GenStaticText as StaticText

# LAYERVIOLATION
from Tribler.Core.BuddyCast.buddycast import BuddyCastFactory


from Tribler.Core.Utilities.unicode import *
from Tribler.Core.Utilities.utilities import *
from Tribler.Core.Utilities.timeouturlopen import urlOpenTimeout

from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.IconsManager import IconsManager,data2wxBitmap


from font import *
from tribler_topButton import *
import TasteHeart

DEBUG = False

# font sizes
if sys.platform == 'darwin':
    FS_SUBSCRTITLE = 10
    FS_TOTALNUMBER = 10
#    FS_SIMILARITY = 10
#    FS_HEARTRANK = 10
#    FS_ONLINE = 10
else:
    FS_SUBSCRTITLE = 8
    FS_TOTALNUMBER = 9
#    FS_SIMILARITY = 10
#    FS_HEARTRANK = 7
#    FS_ONLINE = 8


class SubscriptionsItemPanel(wx.Panel):
    """
    PersonsItemPanel shows one persons item inside the PersonsGridPanel
    """
    def __init__(self, parent, keyTypedFun = None):
        global TORRENTPANEL_BACKGROUND
        
        wx.Panel.__init__(self, parent, -1)
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility
        self.parent = parent
        self.data = None
        self.datacopy = None
        self.titleLength = 172 # num characters
        self.selected = False
        self.warningMode = False
        self.guiserver = parent.guiserver
        self.torrentfeed = parent.torrentfeed
        self.iconsManager = IconsManager.getInstance()
        
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
        
        # Add Spacer
        self.hSizer.Add([8,22],0,wx.EXPAND|wx.FIXED_MINSIZE,0)  
              
        # Add Checkbox turn on/off
        self.cB = wx.CheckBox(self,-1,"",wx.Point(8,128),wx.Size(18,18))        
        self.cB.SetForegroundColour(wx.Colour(0,0,0))
        self.hSizer.Add(self.cB, 0, wx.TOP|wx.LEFT|wx.RIGHT, 3)        
        
        # Add Spacer
        self.hSizer.Add([0,20],0,wx.EXPAND|wx.FIXED_MINSIZE,0)        
        
        # Add thumb / favicon from website?
        self.thumb = FavicoThumbnailViewer(self)
        self.thumb.setBackground(wx.BLACK)
        self.thumb.SetSize((16,16))
        self.hSizer.Add(self.thumb, 0, wx.TOP|wx.RIGHT, 3)        
        
        # Add title                
        self.title =wx.StaticText(self,-1,"Tribler discovery through other Tribler Users",wx.Point(0,0),wx.Size(800,20))                
        #self.title.SetBackgroundColour(wx.BLUE)        
        self.title.SetFont(wx.Font(FS_SUBSCRTITLE,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
        self.title.SetMinSize((550,20))
        self.hSizer.Add(self.title, 1, wx.TOP|wx.RIGHT, 5)     
        
        # Add title        
        #self.today =wx.StaticText(self,-1,"today: 10 files",wx.Point(0,0),wx.Size(140,18))        
        #self.today.SetBackgroundColour(wx.WHITE)
        #self.today.SetFont(wx.Font(10,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
        #self.today.SetMinSize((140,18))
        #self.hSizer.Add(self.today, 0, wx.BOTTOM|wx.TOP|wx.RIGHT, 3)
        
        # Add left vertical line
#        self.vLine1 = self.addLine()
        
        """
        # Add total number of received files
        self.totalnumber =wx.StaticText(self,-1,"",wx.Point(0,0),wx.Size(130,12))        
        self.totalnumber.SetBackgroundColour(wx.WHITE)
        self.totalnumber.SetFont(wx.Font(FS_TOTALNUMBER,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
        self.totalnumber.SetForegroundColour(wx.Colour(128,128,128))        
        self.totalnumber.SetMinSize((60,12))
        self.totalnumber.SetLabel('') 
        self.hSizer.Add(self.totalnumber,0,wx.TOP|wx.EXPAND,3)
        
        # Add left vertical line
        self.vLine2 = self.addLine()
        """         
        
        # Add Spacer to keep space occupied when no delete button is available
        self.vSizer = wx.BoxSizer(wx.VERTICAL)                
        self.vSizer.Add([20,1],0,wx.FIXED_MINSIZE,0)          
        
        # Add delete button
        self.delete = tribler_topButton(self, -1, wx.Point(0,0), wx.Size(16,16),name='deleteSubscriptionItem')                
        self.vSizer.Add(self.delete, 0, wx.TOP, 3)        
        
        self.hSizer.Add(self.vSizer, 0, wx.LEFT|wx.RIGHT|wx.TOP, 0)
        
        
        # Add Spacer
        self.hSizer.Add([8,20],0,wx.EXPAND|wx.FIXED_MINSIZE,0)        

        self.SetSizer(self.hSizer);
        self.SetAutoLayout(1);
        self.Layout();
        self.Refresh()

        self.Bind(wx.EVT_CHECKBOX, self.checkboxAction, self.cB)
        
        # 2.8.4.2 return value of GetChildren changed
        wl = []
        for c in self.GetChildren():
            wl.append(c)
        for window in wl:
            window.Bind(wx.EVT_LEFT_UP, self.mouseAction)
            window.Bind(wx.EVT_KEY_UP, self.keyTyped)
            window.Bind(wx.EVT_RIGHT_DOWN, self.mouseAction) 
            
    def addLine(self, vertical=True):
        if vertical:
            vLine = wx.StaticLine(self,-1,wx.DefaultPosition, wx.Size(2,22),wx.LI_VERTICAL)
            self.hSizer.Add(vLine, 0, wx.RIGHT|wx.EXPAND, 3)
            return vLine
        else:
            hLine = wx.StaticLine(self,-1,wx.DefaultPosition, wx.Size(-1,1),wx.LI_HORIZONTAL)
            self.vSizer.Add(hLine, 0, wx.EXPAND, 0)
            return hLine
                             
    def setData(self, peer_data):
        # set bitmap, rating, title
        
        if DEBUG:
            print >>sys.stderr,"subip: setData called",peer_data
            
        if peer_data is not None and 'content_name' in peer_data:
            print >>sys.stderr,"subip: ERROR! setData called with torrent data!"
            peer_data = None
            
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
            self.cB.Show()
            self.cB.SetValue(peer_data['status'] == "active")
#            self.vLine1.Show()
            #self.vLine2.Show()
            if 'persistent' in self.data:
                self.delete.Hide()
            else:
                self.delete.Show()
        else:
            self.title.SetLabel('')
            #self.title.SetToolTipString('')
            self.title.Enable(False)
            self.cB.SetValue(False)
            self.cB.Hide()
#            self.vLine1.Hide()
            #self.vLine2.Hide()
            #self.delete.Enable(False)
            self.delete.Hide()
       
        self.thumb.setData(peer_data)
               
        self.Layout()
        self.Refresh()
        #self.parent.Refresh()
        
          
        
    def select(self, rowIndex, colIndex):
        colour = self.guiUtility.selectedColour
        if DEBUG:
            print >>sys.stderr,'subip: selected'
        self.thumb.setSelected(True)
        self.SetBackgroundColour(self.selectedColour)
        #self.totalnumber.SetBackgroundColour(self.selectedColour)
        self.Refresh()
        
    def deselect(self, rowIndex, colIndex):
        #print >>sys.stderr,'subip: deselected',self.data
        if rowIndex % 2 == 0:
            colour = self.guiUtility.unselectedColour
        else:
            colour = self.guiUtility.unselectedColour2
            
        self.thumb.setSelected(False)
        self.SetBackgroundColour(colour)
        #self.totalnumber.SetBackgroundColour(colour)
        self.Refresh()
    
    def keyTyped(self, event):
        if self.selected:
            key = event.GetKeyCode()
            if (key == wx.WXK_DELETE):
                if self.data:
                    if DEBUG:
                        print >>sys.stderr,'subip: deleting'
                    self.guiUtility.deleteSubscription(self.data)
        event.Skip()

    def toggleStatus(self,newstatus):
        if not self.data:
            return

        if DEBUG:
            print >>sys.stderr,"subip: new status: ",newstatus

        self.guiUtility.selectSubscription(self.data)

        if 'persistent' in self.data:
            if self.data['persistent'] == 'BC':
                self.toggleBuddycast(newstatus)
            elif self.data['persistent'] == 'Web2.0':
                self.toggleWeb2Search(newstatus)
        else:
            self.torrentfeed.setURLStatus(self.data['url'],newstatus)

    def checkboxAction(self,event):
        if DEBUG:
            print >>sys.stderr,"subip: checkboxAction"

	newstatus = self.cB.GetValue()
	self.toggleStatus( newstatus )
	
	event.Skip()
        
    def mouseAction(self, event):
        if DEBUG:
            print >>sys.stderr,"subip: mouseAction"
        obj = event.GetEventObject()
        name = obj.GetName()
        #print "subip: mouseAction: name is",name
        
        #self.SetFocus()
        if self.data:
            self.guiUtility.selectSubscription(self.data)
        
        if self.data is not None:
            if name == 'deleteSubscriptionItem':
                self.torrentfeed.deleteURL(self.data['url'])
                self.guiUtility.deleteSubscription(self.data)
        if event.RightDown():
            self.rightMouseButton(event)
            
        event.Skip()    

    def rightMouseButton(self, event):       
        menu = self.guiUtility.OnRightMouseAction(event)
        if menu is not None:
            self.PopupMenu(menu, (-1,-1))
            
    def getIdentifier(self):
        if self.data:
            return self.data['url']
        
    def toggleBuddycast(self,status):
        self.utility.config.Write('startrecommender',status, "boolean")
        bcfac = BuddyCastFactory.getInstance()
        if status == True:
            bcfac.restartBuddyCast()
        else:
            bcfac.pauseBuddyCast()

    def toggleWeb2Search(self,status):
        if status and sys.platform == 'linux2':
            dlg = wx.MessageDialog(None, self.utility.lang.get('vlc_linux_start_bug') ,self.utility.lang.get('vlc_linux_start_bug_title'), wx.OK|wx.ICON_INFORMATION)
            dlg.ShowModal()
            dlg.Destroy()

            
            print 'Are you sure?'
        self.utility.config.Write('enableweb2search',status, "boolean")
        search = self.guiUtility.getSearchField(mode='filesMode')
        if status:
            txt = self.utility.lang.get('filesdefaultsearchweb2txt')
        else:
            txt = self.utility.lang.get('filesdefaultsearchtxt')
        search.SetValue(txt)



class FavicoThumbnailViewer(wx.Panel):
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
        self.dataBitmap = self.maskBitmap = None
        self.data = None
        self.mouseOver = False
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnErase)
        self.selected = False
        self.border = None
    
        self.iconsManager = IconsManager.getInstance()
        
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
            bmp = self.iconsManager.get_default('subscriptionsMode','DEFAULT_THUMB')
            # Check if we have already read the thumbnail and metadata information from this torrent file
            if data.get('metadata'):
                bmp = data['metadata'].get('ThumbnailBitmap')
                if not bmp:
                    bmp = self.iconsManager.get_default('subscriptionMode','DEFAULT_THUMB')
            else:
                self.GetParent().guiserver.add_task(lambda:self.loadMetadata(data),0)
            
            self.setBitmap(bmp)
            width, height = self.GetSize()
            d = 1
            self.border = [wx.Point(0,d), wx.Point(width-d, d), wx.Point(width-d, height-d), wx.Point(d,height-d), wx.Point(d,0)]
            self.Refresh()
            
        except:
            print_exc()
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
            print >>sys.stderr,"subip: ThumbnailViewer: loadMetadata: url",data['url']
        mimetype = None
        bmpdata = None
        if not ('persistent' in data):
            try:
                t = urlparse.urlparse(data['url'])
                #print >>sys.stderr,"subip: ThumbnailViewer: loadMetadata: parsed url",t
                newurl = t[0]+'://'+t[1]+'/'+'favicon.ico'
                if DEBUG:
                    print >>sys.stderr,"subip: ThumbnailViewer: loadMetadata: newurl",newurl
                stream = urlOpenTimeout(newurl,timeout=5)
                mimetype = 'image/x-ico' # 'image/vnd.microsoft.icon' # 'image/ico'
                bmpdata = stream.read()
                stream.close()
            except:
                print_exc()
        
        wx.CallAfter(self.metadata_thread_gui_callback,data,mimetype,bmpdata)
             
    def metadata_thread_gui_callback(self,data,mimetype,bmpdata):
        """ Called by GUI thread """

        if DEBUG:
            print "subip: ThumbnailViewer: GUI callback"

        metadata = {}
        if 'persistent' in data:
            metadata['ThumbnailBitmap'] = self.iconsManager.get_default('subscriptionsMode','BUDDYCAST_THUMB')
        else:
            if mimetype is not None:
                metadata['ThumbnailBitmap'] = data2wxBitmap(mimetype,bmpdata,dim=16)
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
                print 'subip: enter' 
            self.mouseOver = True
            self.Refresh()
        elif event.Leaving():
            self.mouseOver = False
            if DEBUG:
                print 'subip: leave'
            self.Refresh()
        elif event.ButtonUp():
            self.ClickedButton()
        #event.Skip()

    def ClickedButton(self):
        if DEBUG:
            print 'subip: Click'
        pass
                
    def setBackground(self, wxColor):
        self.backgroundColor = wxColor
        
    def OnPaint(self, evt):
        dc = wx.BufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.backgroundColor))
        dc.Clear()
        
        if self.dataBitmap:
            #dc.DrawBitmap(self.dataBitmap, self.xpos,self.ypos, True)
            dc.DrawBitmap(self.dataBitmap, 0, 0, True)
