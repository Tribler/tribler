# Written by Jelle Roozenburg, Maarten ten Brinke 
# see LICENSE.txt for license information

import wx, os, sys
from traceback import print_exc
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Core.Utilities.unicode import *
from Tribler.Core.API import *

DEBUG = False

class tribler_List(wx.ListCtrl):
 
    def __init__(self, *args, **kw):
        # self.SetWindowStyle(wx.LC_REPORT|wx.NO_BORDER|wx.LC_NO_HEADER|wx.LC_SINGLE_SEL)
        
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility
        self.backgroundColor = wx.Colour(102,102,102) 
        #self.ForegroundColour = wx.Colour(0,0,0)
        self.isEmpty = True    # used for DLFilesList.onListDClick
        self.updateFunc = None
        pre = wx.PreListCtrl() 
        # the Create step is done by XRC. 
        
        self.PostCreate(pre) 
        self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate) 
        
    def OnCreate(self, event):
        self.Unbind(wx.EVT_WINDOW_CREATE)
        wx.CallAfter(self._PostInit)
        event.Skip()
        return True
    
    def _PostInit(self):
        # Do all init here
        self.Bind(wx.EVT_SIZE, self.onListResize)
        # Turn on labeltips in list control
                

    def onListResize(self, event=None):
        if event!=None:
            event.Skip()
        if not self.InReportView() or self.GetColumnCount()==0:
            return
        size = self.GetClientSize()
        self.SetColumnWidth( 0, size.width - wx.SystemSettings.GetMetric(wx.SYS_VSCROLL_X)) #vertical scrollbar width
        self.ScrollList(-100, 0) # Removes HSCROLLBAR

class FilesList(tribler_List):
    def __init__(self):
        self.initReady = False
        tribler_List.__init__(self)
        
    def _PostInit(self):
        if not self.initReady:
            self.SetWindowStyle(wx.LC_REPORT|wx.NO_BORDER|wx.LC_SINGLE_SEL)
            self.InsertColumn(0, self.utility.lang.get('file'))
            self.InsertColumn(1, self.utility.lang.get('size'))
            self.Bind(wx.EVT_SIZE, self.onListResize)
        self.initReady = True

    def setData(self, torrent, metadatahandler=None):
        # Get the file(s)data for this torrent
        if not self.initReady:
            self._PostInit()
            
        if DEBUG:
            print >>sys.stderr,'tribler_List: setData of FilesTabPanel called'
        try:
            
            if torrent.get('web2') or 'query_permid' in torrent: # web2 or remote query result
                self.filelist = []
                self.DeleteAllItems()
                self.onListResize(None)
                return {}

            torrent_dir = self.utility.session.get_torrent_collecting_dir()
            torrent_filename = os.path.join(torrent_dir, torrent['torrent_file_name'])

            if not os.path.exists(torrent_filename):
                if DEBUG:    
                    print >>sys.stderr,"tribler_List: Torrent: %s does not exist" % torrent_filename
                return {}
            
            metadata = self.utility.getMetainfo(torrent_filename)
            if not metadata:
                return {}
            info = metadata.get('info')
            if not info:
                return {}
            
            #print metadata.get('comment', 'no comment')
                
                
            filedata = info.get('files')
            if not filedata:
                filelist = [(dunno2unicode(info.get('name')),self.utility.size_format(info.get('length')))]
            else:
                filelist = []
                for f in filedata:
                    filelist.append((dunno2unicode('/'.join(f.get('path'))), self.utility.size_format(f.get('length')) ))
                filelist.sort()
                
            
            # Add the filelist to the fileListComponent
            self.filelist = filelist
            self.DeleteAllItems()
            for f in filelist:
                index = self.InsertStringItem(sys.maxint, f[0])
                self.SetStringItem(index, 1, f[1])
            self.onListResize(None)
            
        except:
            if DEBUG:
                print >>sys.stderr,'tribler_List: error getting list of files in torrent'
            print_exc()
            return {}                 
       
    def getNumFiles(self):
        try:
            return len(self.filelist)
        except:
            return 0
        
    def onListResize(self, event):
        size = self.GetClientSize()
        if size[0] > 50 and size[1] > 50:
            self.SetColumnWidth(1, wx.LIST_AUTOSIZE)
            self.SetColumnWidth(0, self.GetClientSize()[0]-self.GetColumnWidth(1)-15)
            self.ScrollList(-100, 0) # Removes HSCROLLBAR
        if event:
            event.Skip()

class DLFilesList(tribler_List):
    """ File List with downloadable items """
    def __init__(self):
        self.infohash_List = None #list of infohashes for current items in the gui list
        self.other_List = None #the other list that should received the downloaded item
        tribler_List.__init__(self)
        
    def _PostInit(self):
        tribler_List._PostInit(self)
        self.Bind(wx.EVT_LEFT_DCLICK, self.onListDClick)
        
    def setInfoHashList(self, alist):
        self.infohash_List = alist
        
    def setOtherList(self, olist):
        """the other list that should received the downloaded item"""
        self.other_List = olist 

    def setFieldsUpdateFunction(self, func):
        self.updateFunc = func
        
    def onListDClick(self, event):
        if self.infohash_List:
            item = self.GetFirstSelected()
            if item != -1 and item < len(self.infohash_List):
                infohash = self.infohash_List[item] 
                # jie.done: click to download. fix it by replacing by db
                torrent_db = self.utility.session.open_dbhandler(NTFY_TORRENTS)
                torrent = torrent_db.getTorrent(infohash)
                torrent['infohash'] = infohash
                ret = self.guiUtility.standardDetails.download(torrent)
                if ret:
                    self.infohash_List.pop(item)
                    self.DeleteItem(item)
                    if self.other_List is not None:    
                        # only used to move items to common item list in peer view
                        if self.other_List.isEmpty:
                            self.other_List.DeleteAllItems()
                        self.other_List.InsertStringItem(sys.maxint, torrent['name'])
                        self.other_List.isEmpty = False
            event.Skip()
            if self.updateFunc:
                self.updateFunc(self.other_List, self)

class T4TSeedingList(tribler_List):
    def __init__(self):
        self.initReady = False
        tribler_List.__init__(self)
    
    def setData(self, dslist, metadatahandler=None):
        # Get the file(s)data for this torrent
        if not self.initReady:
            self._PostInit()
        
        try:
            # refresh the lists
            self.DeleteAllItems()
            
            for ds in dslist: 
                peer_list = ds.get_peerlist()
                    
                if not peer_list:
                    # fault tolerance
                    peer_list = []
                     
                for p in peer_list:   
                    uprate, utotal = p['uprate'], p['utotal']  
                    if uprate == 0 and utotal == 0:
                        continue
                    if not p['g2g']:
                        index = self.InsertStringItem(sys.maxint, p['ip'])
                        self.SetStringItem(index, 1, self.utility.speed_format(uprate, 1, "KB"))
                        self.SetStringItem(index, 2, self.utility.size_format(utotal, 1, "MB"))
                    
            self.onListResize(None)
            
        except:
            print_exc()
            return {}
    
    def _PostInit(self):
        if not self.initReady:
            self.SetWindowStyle(wx.LC_REPORT|wx.NO_BORDER|wx.LC_SINGLE_SEL)
            self.InsertColumn(0, self.utility.lang.get('peer_ip'))
            self.InsertColumn(1, self.utility.lang.get('curr_ul_rate'))
            self.InsertColumn(2, self.utility.lang.get('ul_amount'))
            
            self.SetColumnWidth(0, 140)
            self.SetColumnWidth(1, 75)
            self.SetColumnWidth(2, 75)
            
            self.Bind(wx.EVT_SIZE, self.onListResize)
        self.initReady = True
    
    def onListResize(self, event):
        size = self.GetClientSize()
        if size[0] > 50 and size[1] > 50:
            self.ScrollList(-100, 0) # Removes HSCROLLBAR
        if event:
            event.Skip()   
            
class G2GSeedingList(tribler_List):
    def __init__(self):
        self.initReady = False
        tribler_List.__init__(self)
    
    def setData(self, dslist, metadatahandler=None):
        # Get the file(s)data for this torrent
        if not self.initReady:
            self._PostInit()
        
        try:
            peer_db = self.utility.session.open_dbhandler(NTFY_PEERS)
                        
            # refresh the lists
            self.DeleteAllItems()
            
            for ds in dslist:    
                peer_list = ds.get_peerlist()
                    
                if not peer_list:
                    peer_list = []
                    
                for p in peer_list:
                    uprate, utotal = p['uprate'], p['utotal']  
                    if uprate == 0 and utotal == 0:
                        continue
                    
                    if p['g2g']:
                        tribler_id = peer_db.getPeerID(p['id'])
                        
                        if not tribler_id:   
                            tribler_id = p['ip']
                            
                        index = self.InsertStringItem(sys.maxint, str(tribler_id))
                        self.SetStringItem(index, 1, self.utility.speed_format(uprate, 1, "KB"))
                        self.SetStringItem(index, 2, self.utility.size_format(utotal, 1, "MB"))
                    
            self.onListResize(None)
            
        except:
            print_exc()
            return {}
    
    def _PostInit(self):
        if not self.initReady:
            self.SetWindowStyle(wx.LC_REPORT|wx.NO_BORDER|wx.LC_SINGLE_SEL)
            self.InsertColumn(0, self.utility.lang.get('tribler_name'))
            self.InsertColumn(1, self.utility.lang.get('curr_ul_rate'))
            self.InsertColumn(2, self.utility.lang.get('ul_amount'))
            
            self.SetColumnWidth(0, 140)
            self.SetColumnWidth(1, 75)
            self.SetColumnWidth(2, 75)
            
            self.Bind(wx.EVT_SIZE, self.onListResize)
        self.initReady = True   
    
    def onListResize(self, event):
        size = self.GetClientSize()
        if size[0] > 50 and size[1] > 50:
            self.ScrollList(-100, 0) # Removes HSCROLLBAR
        if event:
            event.Skip()
