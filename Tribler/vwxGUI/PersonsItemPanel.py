import wx, math, time, os, sys, threading
import random
from traceback import print_exc
from Tribler.utilities import *
from wx.lib.stattext import GenStaticText as StaticText
from Tribler.vwxGUI.GuiUtility import GUIUtility
from safeguiupdate import FlaglessDelayedInvocation
from Tribler.unicode import *
from font import *
import cStringIO
import TasteHeart

DEBUG = False

# font sizes
if sys.platform == 'darwin':
    FS_PERSONSTITLE = 10
    FS_SIMILARITY = 10
    FS_HEARTRANK = 8
    FS_ONLINE = 10
    FS_DISCOVERED = 8
else:
    FS_PERSONSTITLE = 8
    FS_SIMILARITY = 10
    FS_HEARTRANK = 7
    FS_ONLINE = 8
    FS_DISCOVERED = 7

class PersonsItemPanel(wx.Panel):
    """
    PersonsItemPanel shows one persons item inside the PersonsGridPanel
    """
    def __init__(self, parent, keyTypedFun=None):
        global TORRENTPANEL_BACKGROUND
        
        wx.Panel.__init__(self, parent, -1)
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility
        self.parent = parent
        self.listItem = (self.parent.cols == 1)
        self.data = None
        self.datacopy = None
        self.titleLength = 137 # num characters
        self.triblerGrey = wx.Colour(128,128,128)
        self.selected = False
        self.warningMode = False
        self.oldCategoryLabel = None
        self.guiserver = parent.guiserver
        self.mm = parent.mm
        self.selected = False
        self.superpeer_db = parent.superpeer_db
        self.keyTypedFun = keyTypedFun
        self.addComponents()
        self.Show()
        self.Refresh()
        self.Layout()
        

    def addComponents(self):
        self.Show(False)
        
        self.selectedColour = wx.Colour(255,200,187)       
        self.unselectedColour = wx.WHITE
        
        self.SetBackgroundColour(self.unselectedColour)
        self.Bind(wx.EVT_LEFT_UP, self.mouseAction)
        self.Bind(wx.EVT_KEY_UP, self.keyTyped)
        
        if not self.listItem:
            self.SetMinSize((80,110))
#            # Add spacer
            self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
            self.hSizer.Add([10,5],0,wx.EXPAND|wx.FIXED_MINSIZE,3)
            self.vSizer = wx.BoxSizer(wx.VERTICAL)            
            # Add thumb
            self.thumb = ThumbnailViewer(self)
            self.thumb.setBackground(wx.BLACK)
            self.thumb.SetSize((80,80))
            self.vSizer.Add(self.thumb, 0, wx.ALL, 0)
            # Add title        
            self.title =wx.StaticText(self,-1,"",wx.Point(0,0),wx.Size(80,15))        
            self.title.SetBackgroundColour(wx.WHITE)
            self.title.SetFont(wx.Font(FS_PERSONSTITLE,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
            self.title.SetMinSize((80,30))
            self.vSizer.Add(self.title, 0, wx.BOTTOM, 3)  
            #
            self.hSizer.Add(self.vSizer,0,wx.ALL,0)
            self.hSizer.Add([5,5],0,wx.EXPAND|wx.FIXED_MINSIZE,3)
            self.SetSizer(self.hSizer);
            
        else: #list item
            self.SetMinSize((670,22))
            self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
            self.hSizer.Add([10,5],0,wx.EXPAND|wx.FIXED_MINSIZE,3)
            self.thumb = ThumbnailViewer(self)
            self.thumb.setBackground(wx.BLACK)
            self.thumb.SetSize((18,18))
            self.hSizer.Add(self.thumb, 0, wx.ALL, 2)  
            # Add title
            self.title =wx.StaticText(self,-1,"",wx.Point(0,0),wx.Size(105,18), wx.ST_NO_AUTORESIZE)        
            self.title.SetBackgroundColour(wx.WHITE)
            self.title.SetFont(wx.Font(FS_PERSONSTITLE,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
            self.title.SetMinSize((105,14))
            self.hSizer.Add(self.title, 1,wx.TOP|wx.BOTTOM, 2) 
            # V Line
            self.vLine3 = self.addLine()
            # Add status
            self.status= wx.StaticText(self,-1,"10",wx.Point(0,0),wx.Size(110,18), wx.ALIGN_RIGHT | wx.ST_NO_AUTORESIZE)        
            self.status.SetBackgroundColour(wx.WHITE)
            self.status.SetFont(wx.Font(FS_PERSONSTITLE,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
            self.status.SetForegroundColour(self.triblerGrey)  
            self.status.SetMinSize((165,18))
            self.hSizer.Add(self.status, 0,wx.TOP|wx.BOTTOM, 2)     
            # V Line
            self.vLine1 = self.addLine() 
            # Add discovered Files
            self.discFiles = wx.StaticText(self,-1,"110000",wx.Point(0,0),wx.Size(75,18), wx.ALIGN_RIGHT | wx.ST_NO_AUTORESIZE)        
            self.discFiles.SetBackgroundColour(wx.WHITE)
            self.discFiles.SetFont(wx.Font(FS_DISCOVERED,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
            self.discFiles.SetForegroundColour(self.triblerGrey) 
            self.discFiles.SetMinSize((40,18))
            self.hSizer.Add(self.discFiles, 0,wx.TOP, 3)  
            # V Line
            self.vLine2 = self.addLine() 
            # Add discovered Persons
            self.discPersons= wx.StaticText(self,-1,"100000",wx.Point(0,0),wx.Size(110,18), wx.ALIGN_RIGHT | wx.ST_NO_AUTORESIZE)        
            self.discPersons.SetBackgroundColour(wx.WHITE)
            self.discPersons.SetFont(wx.Font(FS_DISCOVERED,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
            self.discPersons.SetForegroundColour(self.triblerGrey) 
            self.discPersons.SetMinSize((40,18))
            self.hSizer.Add(self.discPersons, 0,wx.TOP,3)  
            # V Line
            self.vLine4 = self.addLine() 
            # Add Taste Heart
            self.vSizer2 = wx.BoxSizer(wx.VERTICAL)
            self.vSizer2.Add([60,2],0,wx.EXPAND|wx.FIXED_MINSIZE,3)            
            self.hSizer2 = wx.BoxSizer(wx.HORIZONTAL)
            self.tasteHeart = TasteHeart.TasteHeart(self, -1, wx.DefaultPosition, wx.Size(14,14),name='TasteHeart')
            self.hSizer2.Add(self.tasteHeart, 0, wx.TOP, 0)            
            # Add Taste similarity
            self.taste =wx.StaticText(self,-1,"",wx.Point(0,0),wx.Size(40,15))        
            self.taste.SetBackgroundColour(wx.WHITE)
            self.taste.SetFont(wx.Font(FS_HEARTRANK,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
            self.taste.SetMinSize((20,15))
            self.taste.SetLabel('')
            self.hSizer2.Add(self.taste, 0, wx.LEFT, 2)
            self.vSizer2.Add(self.hSizer2,0, wx.EXPAND|wx.FIXED_MINSIZE, 0)
            self.hSizer.Add(self.vSizer2,0,wx.EXPAND|wx.FIXED_MINSIZE, 0)
            # Add Source Icon
#            self.sourceIcon = tribler_topButton(self, -1, wx.DefaultPosition, wx.Size(16,16),name='bcIcon')
#            self.sourceIcon.setBackground(wx.WHITE)
#            #self.sourceIcon.SetToolTipString(self.utility.lang.get('---'))          
#            self.hSizer.Add(self.sourceIcon, 0, wx.TOP|wx.RIGHT, 0)
#            self.hSizer.Add([10,5],0,wx.EXPAND|wx.FIXED_MINSIZE,3)
            self.SetSizer(self.hSizer);
               

        
        self.SetAutoLayout(1);
        self.Layout();
        self.Refresh()
        
        for window in self.GetChildren():
            window.Bind(wx.EVT_LEFT_UP, self.mouseAction)
            window.Bind(wx.EVT_KEY_UP, self.keyTyped)
            window.Bind(wx.EVT_RIGHT_DOWN, self.mouseAction)            


                         
    def setData(self, peer_data):
        # set bitmap, rating, title
        
        #print >>sys.stderr,"pip: setData:",peer_data
            
        if peer_data is None:
            self.datacopy = None
        
        if self.datacopy is not None and peer_data is not None and self.datacopy['permid'] == peer_data['permid']:
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
            
        else:
            peer_data = {}
        
        if peer_data.get('content_name'):
            title = peer_data['content_name'][:self.titleLength]
            self.title.Enable(True)
            self.title.SetLabel(title)
            
            if not self.listItem:
                self.title.Wrap(self.title.GetSize()[0])
                
            self.title.SetToolTipString(peer_data['content_name'])            
            
            if self.listItem:
    #            self.discFiles.Enable(True)
    #            self.discFiles.SetLabel(peer_data['??'])
    #            self.discPersons.Enable(True)
    #            self.discPersons.SetLabel(peer_data['??'])
                
                
                # -- status issues
                self.status.Enable(True)
                #self.status.SetLabel(peer_data['last_seen'])
                statusPeer = peer_data['last_seen']
                    
                if peer_data.get('online'):
                    self.status.SetLabel('online')
                elif statusPeer is not None:
                    if statusPeer < 0:
                        self.status.SetLabel('never seen')
                    else:
                        self.status.SetLabel('conn.  %s' % friendly_time(statusPeer))
                else:
                    self.status.SetLabel( 'unknown')
                
                # number of Discovered files and persons
                if peer_data.get('npeers'):
                    n = unicode(peer_data.get('npeers'))
                    self.discPersons.SetLabel(n)
                    #self.getGuiObj('discPersonsField').SetLabel(n)
                if peer_data.get('ntorrents'):
                    n = unicode(item['ntorrents'])
                    self.discFiles.SetLabel(n)
                    #self.getGuiObj('discFilesField').SetLabel(n)
                
                # -- taste issues
                rank = peer_data.get('simTop',-1) 
                recommField = self.taste
                if rank!=-1:
                    if rank == 1:
                        self.tasteHeart.SetToolTipString("%d" % rank + "st of top 20 of all discovered persons")
                        recommField.SetLabel("%d" % rank + "")                    
                    elif rank == 2:
                        self.tasteHeart.SetToolTipString("%d" % rank + "nd of top 20 of all discovered persons")
                        recommField.SetLabel("%d" % rank + "")                        
                    elif rank == 3:
                        self.tasteHeart.SetToolTipString("%d" % rank + "rd of top 20 of all discovered persons")
                        recommField.SetLabel("%d" % rank + "")
                    else:
                        self.tasteHeart.SetToolTipString("%d" % rank + "th of top 20 of all discovered persons")
                        recommField.SetLabel("%d" % rank + "")
                    self.tasteHeart.Show()
                    self.tasteHeart.setRank(rank)
                else:                    
                    self.tasteHeart.Hide()
                    self.taste.SetLabel('')
                

                
        else:
            self.title.SetLabel('')
            self.title.SetToolTipString('')
            self.title.Enable(False)
            
            if self.listItem:
                self.discFiles.SetLabel('')
                self.discPersons.SetLabel('')
                self.status.SetLabel('')
                self.taste.SetLabel('')
                self.tasteHeart.Hide()
                self.vLine1.Hide()
                self.vLine2.Hide()
                self.vLine3.Hide()
                self.vLine4.Hide()            

        self.thumb.setData(peer_data)
               
        self.Layout()
        self.Refresh()
        #self.parent.Refresh()
        
    def addLine(self):
        vLine = wx.StaticLine(self,-1,wx.DefaultPosition, wx.Size(2,22),wx.LI_VERTICAL)
        self.hSizer.Add(vLine, 0, wx.RIGHT|wx.LEFT|wx.EXPAND, 3)
        return vLine
        
    def select(self, rowIndex, colIndex):
        if DEBUG:
            print 'pip: person selected'
        colour = self.guiUtility.selectedColour
        
        self.selected = True
        self.thumb.setSelected(True)        
        self.title.SetBackgroundColour(colour)
        
        if self.listItem:
            self.SetBackgroundColour(colour)
            self.discFiles.SetBackgroundColour(colour)
            self.discPersons.SetBackgroundColour(colour)
            self.status.SetBackgroundColour(colour)
            self.tasteHeart.setBackground(colour)  
            self.taste.SetBackgroundColour(colour)       
            
        self.Refresh()
                
    def deselect(self, rowIndex, colIndex):
        
        if rowIndex % 2 == 0 or not self.listItem:
            colour = self.guiUtility.unselectedColour
        else:
            colour = self.guiUtility.unselectedColour2
        
        self.selected = False
        self.thumb.setSelected(False)        
        self.title.SetBackgroundColour(colour)
        
        if self.listItem:
            self.SetBackgroundColour(colour)
            self.discFiles.SetBackgroundColour(colour)
            self.discPersons.SetBackgroundColour(colour)
            self.status.SetBackgroundColour(colour)
            self.tasteHeart.setBackground(colour) 
            self.taste.SetBackgroundColour(colour) 
        
        self.Refresh()
    
    def keyTyped(self, event):
        if self.selected:
            key = event.GetKeyCode()
            if (key == wx.WXK_DELETE):
                if self.data:
                    if DEBUG:
                        print >>sys.stderr,'pip: deleting'
#                    self.guiUtility.deleteTorrent(self.data)
        event.Skip()
        
    def mouseAction(self, event):
        if DEBUG:
            print "pip: set focus"
        self.SetFocus()
        if self.data:
            self.guiUtility.selectPeer(self.data)
            
        if event.RightDown():
            self.rightMouseButton(event)
            

    def rightMouseButton(self, event):       
        menu = self.guiUtility.OnRightMouseAction(event)
        self.PopupMenu(menu, (-1,-1)) 
            
    def getIdentifier(self):
        if self.data:
            return self.data['permid']

class ThumbnailViewer(wx.Panel, FlaglessDelayedInvocation):
    """
    Show thumbnail and mast with info on mouseOver
    """

    def __init__(self, *args, **kw):
        self.triblerGrey = wx.Colour(128,128,128)   
        self.triblerLightGrey = wx.Colour(203,203,203)   
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
        self.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)
        self.Bind(wx.EVT_LEFT_UP, self.guiUtility.buttonClicked)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnErase)
        self.selected = False
        self.border = None
        #create the heart
        #I will use TasteHeart.BITMAPS to paint the right one

        self.mm = self.GetParent().parent.mm
        self.superpeer_db = self.GetParent().parent.superpeer_db
    
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
            bmp = self.mm.get_default('personsMode','DEFAULT_THUMB')
            # Check if we have already read the thumbnail and metadata information from this torrent file
            if data.get('metadata'):
                bmp = data['metadata'].get('ThumbnailBitmap')
                tt = data['metadata'].get('triend_time')
                if not bmp:
                    now = time()
                    #print "BMP IS NONE",data['name']
                    bmp = self.mm.get_default('personsMode','DEFAULT_THUMB')
                    if now > tt+(15*60.0):
                        #print "REFRESH OF PEER IMAGE SCHEDULED"
                        self.GetParent().guiserver.add_task(lambda:self.loadMetadata(data),0)
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
        

    def loadMetadata(self,data,type=None):
        """ Called by non-GUI thread """
        
        if DEBUG:
            print "pip: ThumbnailViewer: loadMetadata: Peer",show_permid_short(data['permid']),data['name']
            
        # We can't do any wx stuff here apparently, so the only thing we can do is to
        # read the data from the file and create the wxBitmap in the GUI callback.
        [mimetype,bmpdata] = self.mm.load_data(data['permid'],data['name'])
        #print "PersonsItemPanel: ThumbnailViewer: loadMetadata: Got",show_permid_short(permid),mimetype

        self.invokeLater(self.metadata_thread_gui_callback,[data,mimetype,bmpdata,type])
             
    def metadata_thread_gui_callback(self,data,mimetype,bmpdata,type=None):
        """ Called by GUI thread """

        metadata = {}
        metadata['triend_time'] = time()+(random.random()*100)
        if mimetype is not None:
            metadata['ThumbnailBitmap'] = self.mm.data2wxBitmap(mimetype,bmpdata)
        else:
            superpeers = self.superpeer_db.getSuperPeerList()
            
            """
            if data['name'].lower().startswith("superpeer"):
                print >>sys.stderr,"pip: Name is superpeer",data['name'],"permid",show_permid_short(data['permid'])
                for speer in superpeers:
                    print >>sys.stderr,"pip: Comparing to superpeer",show_permid_short(speer)
            """
            if data['permid'] in superpeers:
                bm = self.mm.get_default('personsMode','SUPERPEER_BITMAP')
                metadata['ThumbnailBitmap'] = bm
            else:
                metadata['ThumbnailBitmap'] = None

        if type and metadata['ThumbnailBitmap'] is not None:
            iw, ih = metadata['ThumbnailBitmap'].GetSize()
            w, h = self.GetSize()
            if (iw/float(ih)) > (w/float(h)):
                nw = w
                nh = int(ih * w/float(iw))
            else:
                nh = h
                nw = int(iw * h/float(ih))
            if nw != iw or nh != ih:
                #print 'Rescale from (%d, %d) to (%d, %d)' % (iw, ih, nw, nh)
                img = wx.ImageFromBitmap(metadata['ThumbnailBitmap'])
                img.Rescale(nw, nh)
                metadata['ThumbnailBitmap'+type] = wx.BitmapFromImage(img)
            #print >>sys.stderr,"pip: Netresult is",metadata['ThumbnailBitmap']

        if DEBUG:
            print "pip: ThumbnailViewer: GUI callback"
        data['metadata'] = metadata
        
        # This item may be displaying another person right now, only show the icon
        # when it's still the same person
        if data['permid'] == self.data['permid']:
            thumb_type = 'ThumbnailBitmap'
            if type:
                thumb_type = thumb_type+type
            if thumb_type in metadata and metadata[thumb_type] is not None:
                self.setBitmap(metadata[thumb_type])
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
#        elif event.ButtonUp():
#            self.ClickedButton()
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
        if self.data is not None and type(self.data)==type({}) and self.data.get('permid'):
            rank = self.guiUtility.peer_manager.getRank(peer_data = self.data)#['permid'])
            #because of the fact that hearts are coded so that lower index means higher ranking, then:
            heartBitmap = TasteHeart.getHeartBitmap(rank)
            if self.mouseOver:
                mask = self.mm.get_default('personsMode','MASK_BITMAP_CLEAN')
                y_pos = 0
                m_height = mask.GetSize()[1]
                y_height = self.GetSize()[1]
                while y_pos<y_height:
                    dc.DrawBitmap(mask,0 ,y_pos, True)
                    y_pos = y_pos + m_height
            if heartBitmap or self.data.get('friend') or self.data.get('online'):
                mask = self.mm.get_default('personsMode','MASK_BITMAP')
                dc.DrawBitmap(mask,0 ,62, True)
            if heartBitmap:
                dc.DrawBitmap(heartBitmap,5 ,64, True)
                dc.SetFont(wx.Font(FS_HEARTRANK,FONTFAMILY,FONTWEIGHT, wx.BOLD, False, FONTFACE))
                text = repr(rank)                
                dc.DrawText(text, 22, 66)
            if self.data.get('friend'):
                if self.data.get('online'):
                    friend = self.mm.get_default('personsMode','FRIEND_ONLINE_BITMAP')
                else:
                    friend = self.mm.get_default('personsMode','FRIEND_OFFLINE_BITMAP')
                dc.DrawBitmap(friend,60 ,65, True)   
            elif self.data.get('online'):         
                dc.SetFont(wx.Font(FS_ONLINE,FONTFAMILY,FONTWEIGHT, wx.BOLD, False,FONTFACE))
                dc.SetTextForeground('#007303')
                dc.DrawText('online', 38, 64)
        
#        dc.SetTextForeground(wx.WHITE)
        #dc.DrawText('rating', 5, 60)

        if self.border:
            if self.selected:
                dc.SetPen(wx.Pen(wx.Colour(255,51,0), 2))
            else:
                dc.SetPen(wx.Pen(self.triblerLightGrey, 2))
            dc.DrawLines(self.border)
        

