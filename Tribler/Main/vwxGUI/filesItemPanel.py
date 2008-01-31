# Written by Jelle Roozenburg, Maarten ten Brinke, Lucan Musat
# see LICENSE.txt for license information

import wx, math, time, os, sys, threading
from traceback import print_exc,print_stack

from Tribler.Core.Utilities.utilities import *
#from wx.lib.stattext import GenStaticText as StaticText
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.tribler_topButton import tribler_topButton, SwitchButton
from Tribler.Main.vwxGUI.bgPanel import ImagePanel
from Tribler.Core.Utilities.unicode import *
from Tribler.Main.Utility.utility import getMetainfo
from Tribler.Main.vwxGUI.IconsManager import IconsManager
from copy import deepcopy
import cStringIO
import TasteHeart
from font import *

from Tribler.Core.Overlay.MetadataHandler import MetadataHandler

DEBUG = False

# font sizes
if sys.platform == 'darwin':
    FS_FILETITLE = 10
    FS_SIMILARITY = 10
    FS_HEARTRANK = 8
elif sys.platform == 'linux2':
    FS_FILETITLE = 8
    FS_SIMILARITY = 7
    FS_HEARTRANK = 7
else:
    FS_FILETITLE = 8
    FS_SIMILARITY = 10
    FS_HEARTRANK = 7
    

filesModeThumbSize = (125, 70)
#filesModeThumbSizeList = (32, 18)
libraryModeThumbSize = (32,18)#(43,24)#(66, 37)


class ItemPanel(wx.Panel):
    pass

class FilesItemPanel(wx.Panel):
    """
    This Panel shows one content item inside the GridPanel
    """
    def __init__(self, parent, keyfun):
        
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
        self.metadatahandler = MetadataHandler.getInstance()
        self.addComponents()
        self.iconsManager = IconsManager.get_instance()
        self.Show()
        self.Refresh()
        self.Layout()
        self.gridKeyTyped = keyfun
        

    def addComponents(self):
        
        self.Show(False)
        
        self.selectedColour = wx.Colour(255,200,187)       
        self.unselectedColour = wx.WHITE
        
        self.SetBackgroundColour(self.unselectedColour)
       
        
        
        if not self.listItem:
            
            self.SetMinSize((138,110))
            
            self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
            self.hSizer.Add([7,5],0,wx.EXPAND|wx.FIXED_MINSIZE,3)
            
            self.vSizer = wx.BoxSizer(wx.VERTICAL)
            # Add thumb
            self.thumb = ThumbnailViewer(self, 'filesMode')
            self.thumb.setBackground(wx.BLACK)
            self.thumb.SetSize((125,70))
            self.vSizer.Add(self.thumb, 0, wx.ALL, 0)        

            self.title =wx.StaticText(self,-1,"",wx.Point(0,0),wx.Size(125,22))    # 
            self.title.SetBackgroundColour(wx.WHITE)
            self.title.SetFont(wx.Font(FS_FILETITLE,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
            self.title.SetMinSize((125,40))
            self.vSizer.Add(self.title, 0, wx.BOTTOM, 3)     
            self.vSizer.Add([100,5],0,wx.EXPAND|wx.FIXED_MINSIZE,3)        
            #
            self.hSizer.Add(self.vSizer,0,wx.ALL|wx.FIXED_MINSIZE,0)
            self.hSizer.Add([2,5],0,wx.EXPAND|wx.FIXED_MINSIZE,3)
            self.SetSizer(self.hSizer);
        else: # listitem
            self.SetMinSize((660,22))
            self.hSizer = wx.BoxSizer(wx.HORIZONTAL)
            self.hSizer.Add([10,5],0,wx.EXPAND|wx.FIXED_MINSIZE,3)
            self.thumb = ThumbnailViewer(self, 'filesMode')
            self.thumb.setBackground(wx.BLACK)
            self.thumb.SetSize((32,18))
            self.hSizer.Add(self.thumb, 0, wx.ALL, 2)  
            # Add title
            self.title =wx.StaticText(self,-1,"",wx.Point(0,0),wx.Size(105,18))        
            self.title.SetBackgroundColour(wx.WHITE)
            self.title.SetFont(wx.Font(FS_FILETITLE,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
            self.title.SetMinSize((105,14))
            self.hSizer.Add(self.title, 1,wx.TOP|wx.BOTTOM, 3)     
            #self.hSizer.Add([5,5],0,wx.EXPAND|wx.FIXED_MINSIZE,3) 
            # V Line
            self.vLine1 = self.addLine() 
            # Add size
            self.fileSize = wx.StaticText(self,-1,"size",wx.Point(0,0),wx.Size(75,18), wx.ALIGN_RIGHT | wx.ST_NO_AUTORESIZE)        
            self.fileSize.SetBackgroundColour(wx.WHITE)
            self.fileSize.SetFont(wx.Font(FS_FILETITLE,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
            self.fileSize.SetForegroundColour(self.triblerGrey) 
            self.fileSize.SetMinSize((75,18))
            self.hSizer.Add(self.fileSize, 0,wx.TOP|wx.BOTTOM, 2)  
            # V Line
            self.vLine2 = self.addLine() 
            # Add creation date
            self.creationDate = wx.StaticText(self,-1,"21-01-2007",wx.Point(0,0),wx.Size(110,18), wx.ALIGN_RIGHT | wx.ST_NO_AUTORESIZE)        
            self.creationDate.SetBackgroundColour(wx.WHITE)
            self.creationDate.SetFont(wx.Font(FS_FILETITLE,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
            self.creationDate.SetForegroundColour(self.triblerGrey) 
            self.creationDate.SetMinSize((110,18))
            self.hSizer.Add(self.creationDate, 0,wx.TOP|wx.BOTTOM, 2) 
            # V Line
            self.vLine3 = self.addLine() 
            # Add popularity
##            self.seeders = ImagePanel(self, -1, wx.DefaultPosition, wx.Size(16,16),name='up')
##            self.seeders.setBackground(wx.WHITE)
##            self.seeders.SetToolTipString(self.utility.lang.get('rNumberOfSeeders'))
            self.seedersNumber = wx.StaticText(self,-1,"203",wx.Point(0,0),wx.Size(125,18), wx.ALIGN_RIGHT | wx.ST_NO_AUTORESIZE)        
            self.seedersNumber.SetBackgroundColour(wx.WHITE)
            self.seedersNumber.SetForegroundColour(self.triblerGrey) 
            self.seedersNumber.SetFont(wx.Font(FS_FILETITLE,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
            self.seedersNumber.SetMinSize((45,18))
##            self.leechers = ImagePanel(self, -1, wx.DefaultPosition, wx.Size(16,16),name='down')
##            self.leechers.setBackground(wx.WHITE)
##            self.leechers.SetToolTipString(self.utility.lang.get('rNumberOfLeechers'))
            self.leechersNumber = wx.StaticText(self,-1,"678",wx.Point(0,0),wx.Size(125,18), wx.ALIGN_RIGHT | wx.ST_NO_AUTORESIZE)        
            self.leechersNumber.SetBackgroundColour(wx.WHITE)
            self.leechersNumber.SetForegroundColour(self.triblerGrey) 
            self.leechersNumber.SetFont(wx.Font(FS_FILETITLE,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
            self.leechersNumber.SetMinSize((45,18))
##            self.hSizer.Add(self.seeders, 0,wx.TOP|wx.BOTTOM|wx.RIGHT, 2) 
            self.hSizer.Add(self.seedersNumber, 0,wx.TOP|wx.BOTTOM|wx.RIGHT, 2) 
            self.vLine4 = self.addLine() 
##            self.hSizer.Add(self.leechers, 0,wx.TOP|wx.BOTTOM|wx.RIGHT, 2)
            self.hSizer.Add(self.leechersNumber, 0,wx.TOP|wx.BOTTOM|wx.RIGHT, 2) 
            # V Line
            self.vLine5 = self.addLine() 
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
            self.taste.SetMinSize((40,15))
            self.taste.SetLabel('2nd')
            self.hSizer2.Add(self.taste, 0, wx.TOP|wx.RIGHT, 0)
            self.vSizer2.Add(self.hSizer2,0, wx.EXPAND|wx.FIXED_MINSIZE, 0)
            self.hSizer.Add(self.vSizer2,0,wx.EXPAND|wx.FIXED_MINSIZE, 0)
            # V Line
            self.vLine6 = self.addLine() 
            # Add Source Icon
            self.sourceIcon = ImagePanel(self, -1, wx.DefaultPosition, wx.Size(16,16),name='bcIcon')
            self.sourceIcon.setBackground(wx.WHITE)
            #self.sourceIcon.SetToolTipString(self.utility.lang.get('---'))          
            self.hSizer.Add(self.sourceIcon, 0, wx.TOP, 2)
            self.hSizer.Add([10,5],0,wx.EXPAND|wx.FIXED_MINSIZE,3)

            
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
            window.Bind(wx.EVT_LEFT_DCLICK, self.doubleClicked)
            window.Bind(wx.EVT_RIGHT_DOWN, self.mouseAction)            
            #window.Bind(wx.EVT_RIGHT_DOWN, self.rightMouseButton)  
            
    def getColumns(self):
        return [{'sort':'content_name', 'reverse':True, 'title':'name', 'weight':1,'tip':self.utility.lang.get('C_filename')},
                {'sort':'length', 'title':'size', 'width':75, 'tip':self.utility.lang.get('C_filesize')},
                {'sort':'date', 'title':'creation date','width':110, 'tip':self.utility.lang.get('C_creationdate')},
                {'sort':'seeder', 'pic':'upSmall','title':'se', 'width':47, 'tip':self.utility.lang.get('C_uploaders')},
                {'sort':'leecher', 'pic':'downSmall','title':'le', 'width':47, 'tip':self.utility.lang.get('C_downloaders')},
                {'sort':'relevance', 'pic':'heartSmall', 'width':60, 'tip':self.utility.lang.get('C_recommfiles')},
                {'sort':'source', 'title':'-', 'width':26, 'tip':self.utility.lang.get('C_source')}
                ]

                 
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
            
        self.thumb.setTorrent(torrent)

        if torrent.get('content_name'):
            title = torrent['content_name'][:self.titleLength]
            self.title.Enable(True)
            self.title.SetLabel(title)
            self.title.Wrap(self.title.GetSize()[0])
            self.title.SetToolTipString(torrent['content_name'])
            self.setSourceIcon(torrent)
            if self.listItem:
                self.fileSize.Enable(True)
                if torrent.get('web2'):
                    self.fileSize.SetLabel('%s s' % torrent['length'])
                else:
                    self.fileSize.SetLabel(self.utility.size_format(torrent['length']))
                
                if torrent.get('date'):
                    self.creationDate.SetLabel(friendly_time(torrent['date']))
                else:
                    self.creationDate.SetLabel('')
                    
                self.creationDate.Enable(True)
                if torrent['seeder'] >= 0:
                    self.seedersNumber.SetLabel('%d' % torrent['seeder'])
                    self.leechersNumber.SetLabel('%d' % torrent['leecher'])
                else:
                    self.seedersNumber.SetLabel('?')
                    self.leechersNumber.SetLabel('?')
                    
                # -- tasteheart --        
                rank = torrent.get('simRank', -1)
                recommField = self.taste            
                if rank!=-1:
                    ##print '--tb-- there is taste'
                    print rank
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
                    #self.taste.SetLabel('')
                else:
                    self.taste.SetLabel('')
                    self.tasteHeart.Hide()
                    # -- END tasteheart --
                
##                self.leechers.Show()
##                self.seeders.Show()
    #            self.tasteHeart.Show()
    
                
                self.vLine1.Show()
                self.vLine2.Show()
                self.vLine3.Show()
                self.vLine4.Show()
                self.vLine5.Show()
                self.vLine6.Show()
                # -- END if list VIEW --
            
    
        else:
            self.thumb.Hide()
            self.title.SetLabel('')
            self.title.SetToolTipString('')
            self.title.Enable(False)
            if self.listItem:
                # -- if list VIEW --
                self.fileSize.SetLabel('')
                self.creationDate.SetLabel('')
                self.seedersNumber.SetLabel('')            
                self.leechersNumber.SetLabel('')
                self.taste.SetLabel('')
#                self.leechers.Hide()
#                self.seeders.Hide()
                self.tasteHeart.Hide()
                
                self.sourceIcon.Hide()
                self.vLine1.Hide()
                self.vLine2.Hide()
                self.vLine3.Hide()
                self.vLine4.Hide()
                self.vLine5.Hide()
                self.vLine6.Hide()
                
            
        self.Layout()
        self.Refresh()
        #self.parent.Refresh()
        
    def addLine(self):
        vLine = wx.StaticLine(self,-1,wx.DefaultPosition, wx.Size(2,22),wx.LI_VERTICAL)
#        vLine.SetForegroundColour(wx.Colour(64,128,128))
#        vLine.SetBackgroundColour(wx.Colour(255,51,0))
        self.hSizer.Add(vLine, 0, wx.RIGHT|wx.LEFT|wx.EXPAND, 3)
        return vLine
          
    def select(self, rowIndex, colIndex):
        self.selected = True
        if DEBUG:
            print >>sys.stderr,'fip: item selected'
        if self.data and self.data.get('myDownloadHistory'):
            colour = self.guiUtility.selectedColourDownload
        else:
            colour = self.guiUtility.selectedColour
        self.thumb.setSelected(True)        
        self.title.SetBackgroundColour(colour)
        
        
        if self.listItem:
            self.SetBackgroundColour(colour)
            self.fileSize.SetBackgroundColour(colour)
            self.creationDate.SetBackgroundColour(colour)
##            self.seeders.setBackground(colour)
            self.seedersNumber.SetBackgroundColour(colour)
##            self.leechers.setBackground(colour)
            self.leechersNumber.SetBackgroundColour(colour)
            self.tasteHeart.setBackground(colour)        
            self.sourceIcon.setBackground(colour)
            self.taste.SetBackgroundColour(colour)
            self.sourceIcon.SetBackgroundColour(colour)
            
        self.Refresh()
        self.guiUtility.standardOverview.SetFocus()
        
    def deselect(self, rowIndex, colIndex):
        self.selected = False
        #colour = self.guiUtility.unselectedColour

        downloading = self.data and self.data.get('myDownloadHistory')
        if rowIndex % 2 == 0 or not self.listItem:
            if downloading:
                colour = self.guiUtility.unselectedColourDownload
            else:
                colour = self.guiUtility.unselectedColour
        else:
            if downloading:
                colour = self.guiUtility.unselectedColour2Download
            else:
                colour = self.guiUtility.unselectedColour2
        
            
        self.thumb.setSelected(False)
        self.title.SetBackgroundColour(colour)
        
        if self.listItem:
            self.SetBackgroundColour(colour)
            self.fileSize.SetBackgroundColour(colour)
            self.creationDate.SetBackgroundColour(colour)
##            self.seeders.setBackground(colour)              
            self.seedersNumber.SetBackgroundColour(colour)
##            self.leechers.setBackground(colour)
            self.leechersNumber.SetBackgroundColour(colour)
            self.tasteHeart.setBackground(colour)        
            self.sourceIcon.setBackground(colour)
            self.taste.SetBackgroundColour(colour)
            self.sourceIcon.SetBackgroundColour(colour)
            
        self.Refresh()
        
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
        #self.SetFocus()
        if self.data and (event.LeftUp() or event.RightDown()):
            # torrent data is sent to guiUtility > standardDetails.setData
            self.guiUtility.selectTorrent(self.data)
            
        if event.RightDown():
            self.rightMouseButton(event)
            

    def rightMouseButton(self, event):       
        menu = self.guiUtility.OnRightMouseAction(event)
        if menu is not None:
            self.PopupMenu(menu, (-1,-1)) 

    def doubleClicked(self, event):
        self.guiUtility.standardDetails.download(self.data)
        
    def getIdentifier(self):
        return self.data['infohash']

    def setSourceIcon(self, torrent):
        desc = torrent.get('description', '')
        if torrent.has_key('query_permid'):
            source = 'remote'
        elif torrent.get('web2'):
            if desc.lower().find('youtube') != -1:
                source = 'youtube'
            elif desc.lower().find('liveleak') != -1:
                source = 'liveleak'
            else:
                source = ''
        elif self.listItem:
            source = 'tribler'
        else:
            source = ''
            
        si = self.iconsManager.getSourceIcon(source)
        if self.listItem:
            self.sourceIcon.setBitmap(si)
            self.sourceIcon.Show()
        else:
            self.thumb.setSourceIcon(si)
                
class ThumbnailViewer(wx.Panel):
    """
    Show thumbnail and mast with info on mouseOver
    """

    def __init__(self, parent, mode, **kw):
        self.parent = parent 
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
        self.backgroundColor = wx.WHITE
        self.torrentBitmap = None
        self.torrent = None
        self.mouseOver = False
        self.triblerGrey = wx.Colour(128,128,128)
        self.triblerLightGrey = wx.Colour(203,203,203)
        self.sourceIcon = None  
        self.guiUtility = GUIUtility.getInstance()
        self.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)
        self.Bind(wx.EVT_LEFT_UP, self.guiUtility.buttonClicked)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnErase)
        self.selected = False
        self.border = None
        self.downloading = False
        self.categoryIcon = None
        self.iconsManager = IconsManager.get_instance()

    
    def setTorrent(self, torrent):
        if not torrent:
            self.Hide()
            self.Refresh()
            return
        
        if not self.IsShown():
            self.Show()
                
        self.torrent = torrent
        self.setThumbnail(torrent)
        self.setCategoryIcon(torrent)
        # items in library should not show downloading color
        self.downloading = torrent.get('myDownloadHistory', False) and self.mode != 'libraryMode'
        
                            
    def setCategoryIcon(self, torrent):
        
        #print >>sys.stderr,"fip: ",`torrent['content_name']`,"has cat",torrent.get('category')
        self.categoryIcon = self.iconsManager.getCategoryIcon(self.mode, torrent.get('category'), thumbtype='icon', web2 = torrent.get('web2'))
    
    def setSourceIcon(self, si):
        self.sourceIcon = si
        
    def setThumbnail(self, torrent):
        #if torrent.get('web2'):
            #import pdb
            #pdb.set_trace()
        # Get the file(s)data for this torrent
        thumbtype = (self.parent.listItem) and 'small' or 'normal'
        bmp = None
        readable = torrent.get('metadata',{}).get('ThumbReadable')
        if readable == False:
            bmp = self.iconsManager.getCategoryIcon(self.mode,torrent.get('category'), thumbtype=thumbtype, web2 = torrent.get('web2'))
        
        else:        
            # Check if we have already read the thumbnail and metadata information from this torrent file
            if 'preview' in torrent:
                self.GetParent().guiserver.add_task(lambda:self.loadMetadata(torrent,None),0)
                
            elif torrent.get('metadata',{}).get('ThumbnailBitmap'):
                if self.mode == 'libraryMode' or self.parent.listItem:
                    # Make a resized thumb for lib view
                    bmp = torrent['metadata'].get('ThumbnailBitmap')
                    if bmp:
                        img = bmp.ConvertToImage()
                        bmp = getResizedBitmapFromImage(img, libraryModeThumbSize)
                        
                elif self.mode == 'filesMode':
                    bmp = torrent['metadata'].get('ThumbnailBitmap')
            else:
                (torrent_dir,torrent_name) = self.metadatahandler.get_std_torrent_dir_name(torrent)
                torrent_filename = os.path.join(torrent_dir, torrent_name)
                
                if DEBUG:
                    print "fip: Scheduling read of thumbnail for",torrent_filename
                self.GetParent().guiserver.add_task(lambda:self.loadMetadata(torrent,torrent_filename),0)
        
                # ARNO: TODO: The FileItemPanels that use this ThumbnailViewer now get deleted, and thus
                # also the ThumbnailViewer objects. Or at least the C++ part of them. As a result we
                # can no longer schedule these loadMetadata callbacks on the GUIServer thread. 
                #
                # At the moment, the wx code protects us, and throws an exception that the C++ part
                # of the ThumbnailViewer object is gone. But we should clean this up. 
            
        if not bmp:
            bmp = self.iconsManager.getCategoryIcon(self.mode, torrent.get('category'), thumbtype=thumbtype, web2 = torrent.get('web2'))
        
        assert bmp, 'No bitmap found for %s' % `torrent['content_name']`
        self.setBitmap(bmp)
        width, height = self.GetSize()
        d = 1
        self.border = [wx.Point(0,d), wx.Point(width-d, d), wx.Point(width-d, height-d), wx.Point(d,height-d), wx.Point(d,0)]
        self.Refresh()
        
        
        
         
    def setBitmap(self, bmp):
        # Recalculate image placement
        if not bmp:
            self.torrentBitmap = None
            self.xpos, self.ypos = 0,0
            raise Exception('Warning: Thumbnail set to None for %s' % `self.torrent`)
        else:
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

      
        wx.CallAfter(self.metadata_thread_gui_callback,torrent,newmetadata)

             
    def metadata_thread_gui_callback(self,torrent,metadata):
        """ Called by GUI thread """

        #print 'Azureus_thumb: %s' % thumbnailString
        thumbnailString = metadata.get('Thumbnail')
         
        if thumbnailString:
            #print 'Found thumbnail: %s' % thumbnailString
            
            img = createThumbImage(thumbnailString)
            if img is None:
                return           

            bmp = getResizedBitmapFromImage(img, filesModeThumbSize)
            
            if bmp:
                metadata['ThumbnailBitmap'] = bmp
                metadata['ThumbnailReadable'] = True
            ## We now scale live
            #bmplib = getResizedBitmapFromImage(img, libraryModeThumbSize)
            #if bmplib:
            #    metadata['ThumbnailBitmapLibrary'] = bmplib
                
            # Dump the raw data
            del metadata['Thumbnail']
        else:
            metadata['ThumbnailReadable'] = False
          
        torrent['metadata'] = metadata
        
        # This item may be displaying another torrent right now, only show the icon
        # when it's still the same torrent
        
        #print >>sys.stderr,"fip: meta_gui_cb: old torrent",`torrent['content_name']`,"new torrent",`self.torrent['content_name']`
        #print >>sys.stderr,"fip: meta_gui_cb: old torrent",`torrent['infohash']`,"new torrent",`self.torrent['infohash']`
        
        if torrent['infohash'] == self.torrent['infohash']:
            bmp = metadata.get('ThumbnailBitmap')
            if bmp:
                if self.parent.listItem:
                    bmp = getResizedBitmapFromImage(img, libraryModeThumbSize)
                self.setBitmap(bmp)
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

        if self.categoryIcon:
            dc.DrawBitmap(self.categoryIcon, 99, 7, True)      
        if self.sourceIcon:
            dc.DrawBitmap(self.sourceIcon, 101, 27, True)
            
        if self.mouseOver:
            dc.SetFont(wx.Font(6, FONTFAMILY,FONTWEIGHT, wx.BOLD, True, FONTFACE))
            mask = self.iconsManager.get_default('filesMode','MASK_BITMAP')
            dc.DrawBitmap(mask,0 ,0, True)
        
        if heartBitmap:
            mask = self.iconsManager.get_default('filesMode','MASK_BITMAP_BOTTOM')
            margin = 52
            dc.DrawBitmap(mask,0 ,margin, True)
            dc.DrawBitmap(heartBitmap,5 ,margin+2, True)
            dc.SetFont(wx.Font(FS_HEARTRANK, FONTFAMILY, FONTWEIGHT, wx.BOLD, False, FONTFACE))
            text = repr(rank)                
            dc.DrawText(text, 22, margin+4)
        
            
        if self.border:
            if self.selected:
                if self.downloading:
                    colour = self.guiUtility.selectedColourDownload
                else:
                    colour = self.guiUtility.triblerRed
            else:
                if self.downloading:
                    colour = self.guiUtility.unselectedColourDownload
                else:
                    colour = self.triblerLightGrey
            dc.SetPen(wx.Pen(colour, 2))
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

def getResizedBitmapFromImage(img, size):
        "Resize image to size of self"
        iw, ih = img.GetSize()
        w, h = size

        if iw == 0 or ih == 0:
            # Can happen when there is no handler for image type
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