# Written by Jelle Roozenburg, Maarten ten Brinke, Arno Bakker 
# see LICENSE.txt for license information

import wx, math, time, os, sys, threading
from traceback import print_exc
from copy import deepcopy
import cStringIO
from wx.lib.stattext import GenStaticText as StaticText

from Tribler.Core.simpledefs import *
from Tribler.Core.Utilities.utilities import *
from Tribler.Core.Utilities.unicode import *
from Tribler.Main.Dialogs.makefriends import MakeFriendsDialog
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.PersonsItemPanel import ThumbnailViewer
from Tribler.Main.Utility.utility import similarPeer, copyPeer
from Tribler.Main.vwxGUI.IconsManager import IconsManager, data2wxBitmap
from font import *
from tribler_topButton import *
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
        self.datacopy = {}
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
        
        # Add Taste Heart - Add Spacer to keep space occupied when no heart available
        self.vSizer = wx.BoxSizer(wx.VERTICAL)                
        self.vSizer.Add([60,2],0,wx.FIXED_MINSIZE,0)  
        self.hSizer2 = wx.BoxSizer(wx.HORIZONTAL)    
        self.tasteHeart = TasteHeart.TasteHeart(self, -1, wx.DefaultPosition, wx.Size(14,14),name='TasteHeart')
        self.hSizer2.Add(self.tasteHeart, 0, wx.TOP, 0)        
        # Add Taste similarity
        self.taste =wx.StaticText(self,-1,"",wx.Point(0,0),wx.Size(40,15))        
        self.taste.SetBackgroundColour(wx.WHITE)
        self.taste.SetFont(wx.Font(FS_HEARTRANK,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
        self.taste.SetMinSize((40,15))
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
        
        # 2.8.4.2 return value of GetChildren changed
        wl = []
        for c in self.GetChildren():
            wl.append(c)
        for window in wl:
            window.Bind(wx.EVT_LEFT_UP, self.mouseAction)
            window.Bind(wx.EVT_KEY_UP, self.keyTyped)
            window.Bind(wx.EVT_RIGHT_DOWN, self.mouseAction) 
            
    def getColumns(self):
        return [{'sort':'', 'title':'', 'width':20, 'tip':''},
                {'sort':'name', 'reverse':True,'title':'name', 'weight':1,'tip':self.utility.lang.get('C_friendname') },
                {'sort':'last_connected', 'title':'status', 'width':165, 'tip':self.utility.lang.get('C_friendstatus'), 'order':'down'},
                {'sort':'??', 'dummy':True, 'title':'boosting','weight':1, 'tip':self.utility.lang.get('C_helping')},
                {'sort':'similarity','pic':'heartSmall', 'width':65, 'tip':self.utility.lang.get('C_recommpersons')}
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
        
        
        #if self.data is None:
        #    oldpermid = None
        #else:
        #    oldpermid = self.data['permid']
        
        self.data = peer_data
        # do not reload similar peers
        if peer_data is not None and 'coopdlstatus' in peer_data:
            pass
        elif similarPeer(peer_data, self.datacopy):
            return
        self.datacopy = copyPeer(peer_data)
                        
        if peer_data is None:
            peer_data = {}

        if peer_data.get('name'):
            title = peer_data['name'][:self.titleLength]
            self.title.Enable(True)
            self.title.SetLabel(title)
            self.title.Wrap(self.title.GetSize()[0])
            self.title.SetToolTipString(peer_data['ip']+':'+str(peer_data['port']))
            
            # status issues
            self.status.Enable(True)
            label = peer2status(peer_data)
            self.status.SetLabel(label)

            if 'coopdlstatus' in peer_data:
                self.helping.SetLabel(peer_data['coopdlstatus'])
                self.helping.SetToolTipString(peer_data['coopdlstatus'])
                
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
            
        rank = peer_data.get('simRank',-1) 
        recommField = self.taste
        if rank!=-1:
            if rank == 1:
                self.tasteHeart.SetToolTipString("%d" % rank + "st of top 20 of all discovered persons")
                recommField.SetLabel("%d" % rank + "st")
            elif rank == 2:
                self.tasteHeart.SetToolTipString("%d" % rank + "nd of top 20 of all discovered persons")
                recommField.SetLabel("%d" % rank + "nd")                        
            elif rank == 3:
                self.tasteHeart.SetToolTipString("%d" % rank + "rd of top 20 of all discovered persons")
                recommField.SetLabel("%d" % rank + "rd")
            else:
                self.tasteHeart.SetToolTipString("%d" % rank + "th of top 20 of all discovered persons")
                recommField.SetLabel("%d" % rank + "th")
            self.tasteHeart.Show()
            self.tasteHeart.setRank(rank)
        else:
            self.taste.SetLabel('')
            self.tasteHeart.Hide()

        #if oldpermid is None or oldpermid != peer_data['permid']:
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
        if menu is not None:
            self.PopupMenu(menu, (-1,-1)) 
            
    def getIdentifier(self):
        if self.data:
            return self.data['permid']
        

    
                

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
                bmp = self.iconsManager.get_default('friendsMode','DEFAULT_THUMB')

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

            rank = self.data.get('simRank',-1) 
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
                mask = self.iconsManager.get_default('friendsMode','MASK_BITMAP_OVERLAY')
                y_pos = 0
                m_height = mask.GetSize()[1]
                y_height = self.GetSize()[1]
                while y_pos<y_height:
                    dc.DrawBitmap(mask,0 ,y_pos, True)
                    y_pos = y_pos + m_height
            if recomm >=0 or self.data.get('friend') or self.data.get('online'):
                mask = self.iconsManager.get_default('personsMode','MASK_BITMAP')
                dc.DrawBitmap(mask,0 ,62, True)
            if recomm >=0:
                dc.DrawBitmap(TasteHeart.BITMAPS[recomm],5 ,64, True)
                dc.SetFont(wx.Font(FS_HEARTRANK, FONTFAMILY, FONTWEIGHT, wx.BOLD, False, FONTFACE))
                text = repr(rank)                
                dc.DrawText(text, 22, 66)
            if self.data.get('friend'):
                friend = self.iconsManager.get_default('personsMode','MASK_BITMAP')
                dc.DrawBitmap(friend,60 ,65, True)            
            if self.data.get('online'):
                dc.SetFont(wx.Font(FS_ONLINE, FONTFAMILY, FONTWEIGHT, wx.BOLD, False, FONTFACE))
                dc.SetTextForeground('#007303')
                dc.DrawText('online', 26, 66)
                
        
#        dc.SetTextForeground(wx.WHITE)
        #dc.DrawText('rating', 5, 60)
        if (self.selected and self.border):
            dc.SetPen(wx.Pen(wx.Colour(255,51,0), 2))
            dc.DrawLines(self.border)


def peer2status(peer):
    label = peer2seenstatus(peer)
    
    # Friend status to show whether this is an approved friend, or not
    fs = peer.get('friend',FS_NOFRIEND)
        
    #if fs == FS_NOFRIEND or fs == FS_MUTUAL:
    #    pass
    #else:
    fstext = fs2text(fs)
    label = label+", "+fstext
    return label

def peer2seenstatus(peer):
    if peer.get('online'):
        label = 'online'
    elif peer.get('last_connected') is not None:
        if peer['last_connected'] < 0:
            label = 'never seen'
        else:
            label = 'met %s' % friendly_time(peer['last_connected'])
    else:
        label = 'unknown'
    return label
        
def fs2text(fs):
    if fs == FS_NOFRIEND:
        return "no friend"
    elif fs == FS_MUTUAL:
        return "is friend"
    elif fs == FS_I_INVITED:
        return "pending"
    elif fs == FS_HE_INVITED:
        return "invited you"
    elif fs == FS_I_DENIED:
        return "you refused"
    elif fs == FS_HE_DENIED:
        return "refused"
