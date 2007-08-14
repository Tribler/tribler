import wx, math, time, os, sys, threading
from traceback import print_exc
from Tribler.utilities import *
from wx.lib.stattext import GenStaticText as StaticText
from Tribler.Dialogs.makefriends import MakeFriendsDialog
from Tribler.vwxGUI.GuiUtility import GUIUtility
from Tribler.vwxGUI.PersonsItemPanel import ThumbnailViewer
from Tribler.unicode import *
from Tribler.utilities import show_permid_short
from font import *
from copy import deepcopy
import cStringIO
from tribler_topButton import *
from threading import Lock
import TasteHeart

DEBUG=False

# font sizes
if sys.platform == 'darwin':
    FS_FRIENDTITLE = 10
    FS_STATUS = 10
    FS_SIMILARITY = 10
    FS_HEARTRANK = 8
    FS_ONLINE = 10
else:
    FS_FRIENDTITLE = 8
    FS_STATUS = 8
    FS_SIMILARITY = 8
    FS_HEARTRANK = 7
    FS_ONLINE = 8

class FriendsItemPanel(wx.Panel):
    """
    PersonsItemPanel shows one persons item inside the PersonsGridPanel
    """
    def __init__(self, parent, keyTypedFun= None):
        global TORRENTPANEL_BACKGROUND
        
        wx.Panel.__init__(self, parent, -1)
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility
        self.parent = parent
        self.data = None
        self.datacopy = None
        self.titleLength = 77 # num characters
        self.triblerGrey = wx.Colour(128,128,128)
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
        self.SetMinSize((137,22+0))
        self.selectedColour = wx.Colour(255,200,187)       
        self.unselectedColour = wx.WHITE
        
        self.SetBackgroundColour(self.unselectedColour)
        
#        self.vSizerAll = wx.BoxSizer(wx.VERTICAL)
        
        self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.Bind(wx.EVT_LEFT_UP, self.mouseAction)
        self.Bind(wx.EVT_KEY_UP, self.keyTyped)
 
        # Add Spacer
        self.hSizer.Add([8,22],0,wx.EXPAND|wx.FIXED_MINSIZE,0) 
        
        # Add thumb
        self.thumb = FriendThumbnailViewer(self)
        self.thumb.setBackground(wx.BLACK)
        self.thumb.SetSize((18,18))
        self.hSizer.Add(self.thumb, 0, wx.ALL, 2)        
        
        # Add title
        self.title =wx.StaticText(self,-1,"",wx.Point(0,0),wx.Size(100,15))        
        self.title.SetBackgroundColour(wx.WHITE)
        self.title.SetFont(wx.Font(FS_FRIENDTITLE,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
        self.title.SetMinSize((100,14))        
        self.title.SetLabel('')
        self.hSizer.Add(self.title,1,wx.TOP,4)
        
        # Add left vertical line
        self.vLine1 = self.addLine()        
        
        # Add status
        self.status =wx.StaticText(self,-1,"",wx.Point(0,0),wx.Size(130,12), wx.ALIGN_RIGHT | wx.ST_NO_AUTORESIZE )        
        self.status.SetBackgroundColour(wx.WHITE)
        self.status.SetFont(wx.Font(FS_STATUS,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
        self.status.SetForegroundColour(self.triblerGrey)        
        self.status.SetMinSize((165,12))
        self.status.SetLabel("") 
        self.hSizer.Add(self.status,0,wx.TOP|wx.EXPAND,4)
        
        # Add left vertical line
        self.vLine2 = self.addLine()           
                
        # Add message > if today new content is discovered from him/her
        self.helping =wx.StaticText(self,-1,"",wx.Point(0,0),wx.Size(130,12), wx.ALIGN_RIGHT | wx.ST_NO_AUTORESIZE)        
        self.helping.SetBackgroundColour(wx.WHITE)
        self.helping.SetFont(wx.Font(FS_STATUS,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
        self.helping.SetForegroundColour(self.triblerGrey)        
        self.helping.SetMinSize((30,14))
        self.helping.SetLabel('') 
        self.hSizer.Add(self.helping,1,wx.TOP,4)
        
        # Add left vertical line
        self.vLine3 = self.addLine() 
        
        # Add Spacer to keep space occupied when no heart available
        self.vSizer = wx.BoxSizer(wx.VERTICAL)                
        self.vSizer.Add([60,2],0,wx.FIXED_MINSIZE,0)  
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
        self.vSizer.Add(self.hSizer2, 0, wx.TOP, 2)
        self.hSizer.Add(self.vSizer, 0, wx.LEFT|wx.RIGHT, 2)
        
        # Add delete button
##        self.delete = tribler_topButton(self, -1, wx.Point(0,0), wx.Size(16,16),name='deleteFriend')                
##        self.hSizer.Add(self.delete, 0, wx.TOP|wx.RIGHT, 4)

#        self.vSizerAll.Add(self.hSizer, 0, wx.EXPAND, 0)
        #Add bottom horizontal line
#        self.addLine(False)
        self.SetSizer(self.hSizer);
        self.SetAutoLayout(1);
        self.Layout();
        self.Refresh()
        
        for window in self.GetChildren():
            window.Bind(wx.EVT_LEFT_UP, self.mouseAction)
            window.Bind(wx.EVT_KEY_UP, self.keyTyped)
            window.Bind(wx.EVT_LEFT_DCLICK, self.doubleClicked)
            window.Bind(wx.EVT_RIGHT_DOWN, self.mouseAction) 
            
    def getColumns(self):
        return [{'sort':'content_name', 'title':'name', 'weight':1,'tip':self.utility.lang.get('filename') },
                {'sort':'last_seen', 'title':'status', 'width':165, 'tip':self.utility.lang.get('filesize'), 'order':'down'},
                {'sort':'??', 'title':'helping','weight':1, 'tip':self.utility.lang.get('creationdate')},
                {'sort':'similarity', 'pic':'heartSmall', 'width':60, 'tip':self.utility.lang.get('recommendation')}
                ]
            
    def addLine(self, vertical=True):
        if vertical:
            vLine = wx.StaticLine(self,-1,wx.DefaultPosition, wx.Size(2,22),wx.LI_VERTICAL)
            self.hSizer.Add(vLine, 0, wx.RIGHT|wx.LEFT|wx.EXPAND, 3)
            return vLine
        else:
            hLine = wx.StaticLine(self,-1,wx.DefaultPosition, wx.Size(-1,1),wx.LI_HORIZONTAL)
            self.vSizer.Add(hLine, 0, wx.EXPAND, 0)
            return hLine
                                     
    def setData(self, peer_data):
        # set bitmap, rating, title
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
            self.title.Wrap(self.title.GetSize()[0])
            self.title.SetToolTipString(peer_data['ip']+':'+str(peer_data['port']))
            # status issues
            self.status.Enable(True)            
            statusPeer = peer_data['last_seen']
            print '==tb=='
            print statusPeer                
            if peer_data.get('online'):
                self.status.SetLabel('online')
            elif statusPeer is not None:
                if statusPeer < 0:
                    self.status.SetLabel('never seen')
                else:                    
                    self.status.SetLabel('conn.  %s' % friendly_time(statusPeer))
            else:
                self.status.SetLabel( 'unknown')
                
#            self.delete.Show()
            self.tasteHeart.Show()
            self.vLine1.Show()
            self.vLine2.Show()
            self.vLine3.Show()
        else:
            self.title.SetLabel('')
            self.title.SetToolTipString('')
            self.title.Enable(False)
            self.status.SetLabel('')
            self.helping.SetLabel('') 
#            self.delete.Hide()
            self.tasteHeart.Hide()
            self.vLine1.Hide()
            self.vLine2.Hide()
            self.vLine3.Hide()
            
        rank = peer_data.get('simTop',-1) 
        recommField = self.taste
        if rank!=-1:
            if rank == 1:
                recommField.SetLabel("%d" % rank + "st")
            elif rank == 2:
                recommField.SetLabel("%d" % rank + "nd")                        
            elif rank == 3:
                recommField.SetLabel("%d" % rank + "rd")
            else:
                recommField.SetLabel("%d" % rank + "th")
            self.tasteHeart.Show()
            self.tasteHeart.setRank(rank)
        else:
            self.taste.SetLabel('')
            self.tasteHeart.Hide()
                  
        self.thumb.setData(peer_data)
               
        self.Layout()
        self.Refresh()
        #self.parent.Refresh()
        
          
        
    def select(self, rowIndex, colIndex):
        self.selected = True
#        if colIndex == 0:
#            self.vLine.Hide()            
#        else:
#            self.vLine.Show()
        self.thumb.setSelected(True)
        self.title.SetBackgroundColour(self.selectedColour)
        self.status.SetBackgroundColour(self.selectedColour)
        self.helping.SetBackgroundColour(self.selectedColour)
        self.taste.SetBackgroundColour(self.selectedColour)
        self.tasteHeart.setBackground(self.selectedColour)
        self.SetBackgroundColour(self.selectedColour)
        self.Refresh()
        self.SetFocus()
        
    def deselect(self, rowIndex, colIndex):
        self.selected = False
#        if colIndex == 0:
#            self.vLine.Hide()
#        else:
#            self.vLine.Show()
        if rowIndex % 2 == 0:
            colour = self.guiUtility.unselectedColour
        else:
            colour = self.guiUtility.unselectedColour2
            
        self.thumb.setSelected(False)
        self.title.SetBackgroundColour(colour)
        self.status.SetBackgroundColour(colour)
        self.helping.SetBackgroundColour(colour)
        self.taste.SetBackgroundColour(colour)
        self.tasteHeart.setBackground(colour)
        self.SetBackgroundColour(colour)
        self.Refresh()
    
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
        event.Skip()
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
        

    def doubleClicked(self, event):
        if self.data is not None:
            dialog = MakeFriendsDialog(self,self.utility,self.data)
            ret = dialog.ShowModal()
            dialog.Destroy()
            
        event.Skip()
      
                

class FriendThumbnailViewer(ThumbnailViewer):
    def __init__(self, *args, **kw):    
        ThumbnailViewer.__init__(self, *args, **kw)
        
    def setThumbnail(self, data):
        # Get the file(s)data for this torrent
        try:
            width, height = self.GetSize()
            bmp = None
            # Check if we have already read the thumbnail and metadata information from this torrent file
            if data.get('metadata') and data['metadata'].get('ThumbnailBitmapAsFriend'):
                bmp = data['metadata'].get('ThumbnailBitmapAsFriend')
            else:
                self.GetParent().guiserver.add_task(lambda:self.loadMetadata(data,type="AsFriend"),0)
            if not bmp:
                bmp = self.mm.get_default('friendsMode','DEFAULT_THUMB')

            self.setBitmap(bmp)
            d = 1
            self.border = [wx.Point(0,d), wx.Point(width-d, d), wx.Point(width-d, height-d), wx.Point(d,height-d), wx.Point(d,0)]
            self.Refresh()
            
        except:
            print_exc(file=sys.stderr)
            return {} 

#===============================================================================
#    def setBitmap(self, bmp, default=False):
#        # Recalculate image placement
#        w, h = self.GetSize()
#        iw, ih = bmp.GetSize()
#                
#        self.dataBitmap = bmp
#        self.xpos, self.ypos = (w-iw)/2, (h-ih)/2
#===============================================================================
                        
    def OnPaint(self, evt):
        dc = wx.BufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.backgroundColor))
        dc.Clear()
        
        if self.dataBitmap:
            dc.DrawBitmap(self.dataBitmap, self.xpos,self.ypos, True)
#        if self.mouseOver:
        if self.data is not None and type(self.data)==type({}) and self.data.get('permid'):

#            print "DATA IS",self.data

            helping = None
            if self.data.get('friend'):
                torrentname = self.is_helping(self.data.get('permid'))
                if DEBUG:
                    print >>sys.stderr,"fip: Friend",self.data['name'],"is helping with torrent",torrentname
                if torrentname is not None:
                    helping = "helping with "+torrentname
            if helping is None:
                print '-nothing-'
                self.GetParent().helping.SetLabel('')
                self.GetParent().helping.SetToolTipString('')
                #self.GetParent().status.SetLabel('status unknown')
            else:                
                self.GetParent().helping.SetLabel(helping)
                self.GetParent().helping.SetToolTipString(helping)
#                self.GetParent().status.SetLabel(helping)
            rank = self.guiUtility.peer_manager.getRank(peer_data = self.data)#['permid'])
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
            if self.mouseOver:
                mask = self.mm.get_default('friendsMode','MASK_BITMAP_OVERLAY')
                y_pos = 0
                m_height = mask.GetSize()[1]
                y_height = self.GetSize()[1]
                while y_pos<y_height:
                    dc.DrawBitmap(mask,0 ,y_pos, True)
                    y_pos = y_pos + m_height
            if recomm >=0 or self.data.get('friend') or self.data.get('online'):
                mask = self.mm.get_default('personsMode','MASK_BITMAP')
                dc.DrawBitmap(mask,0 ,62, True)
            if recomm >=0:
                dc.DrawBitmap(TasteHeart.BITMAPS[recomm],5 ,64, True)
                dc.SetFont(wx.Font(FS_HEARTRANK, FONTFAMILY, FONTWEIGHT, wx.BOLD, False, FONTFACE))
                text = repr(rank)                
                dc.DrawText(text, 22, 66)
            if self.data.get('friend'):
                friend = self.mm.get_default('personsMode','MASK_BITMAP')
                dc.DrawBitmap(friend,60 ,65, True)            
            if self.data.get('online'):
                #label = 'online'
                label = ''
                if helping is not None:
                    #label = 'online,'+helping
                    label = helping
                self.GetParent().helping.SetLabel(label)
                self.GetParent().helping.SetToolTipString(label)
                #self.GetParent().status.SetLabel(label)
                dc.SetFont(wx.Font(FS_ONLINE, FONTFAMILY, FONTWEIGHT, wx.BOLD, False, FONTFACE))
                dc.SetTextForeground('#007303')
                dc.DrawText('online', 26, 66)
                
        
#        dc.SetTextForeground(wx.WHITE)
        #dc.DrawText('rating', 5, 60)
        if (self.selected and self.border):
            dc.SetPen(wx.Pen(wx.Colour(255,51,0), 2))
            dc.DrawLines(self.border)
        

    def is_helping(self,permid):
        utility = self.GetParent().utility
        for ABCTorrentTemp in self.utility.torrents["active"]:
            engine = ABCTorrentTemp.connection.engine
            if engine is not None:
                coordinator = engine.getDownloadhelpCoordinator()
                if coordinator is not None:
                    helpingFriends = coordinator.get_asked_helpers_copy()
                    for rec in helpingFriends:
                        if permid == rec['permid']:
                            return ABCTorrentTemp.info['name']
        return None
                
