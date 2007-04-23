import wx, os, sys
from traceback import print_exc
from Tribler.vwxGUI.GuiUtility import GUIUtility
from Tribler.unicode import *

DEBUG = False

class tribler_List(wx.ListCtrl):
    """
    Button that changes the image shown if you move your mouse over it.
    It redraws the background of the parent Panel, if this is an imagepanel with
    a variable self.bitmap.
    """

    def __init__(self, *args, **kw):
        # self.SetWindowStyle(wx.LC_REPORT|wx.NO_BORDER|wx.LC_NO_HEADER|wx.LC_SINGLE_SEL)
        
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility
        self.backgroundColor = wx.Colour(102,102,102) 
        
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
#        pass

    def onListResize(self, event=None):
        if event!=None:
            event.Skip()
        if not self.InReportView() or self.GetColumnCount()==0:
            return
        size = self.GetClientSize()
        self.SetColumnWidth( 0, size.width-10) #vertical scrollbar width
        self.ScrollList(-100, 0) # Removes HSCROLLBAR
        print "<mluc> here"

class TorrentList(tribler_List):
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
        
    def setData(self, torrent):
        # Get the file(s)data for this torrent
        if not self.initReady:
            self._PostInit()
            
        print 'setData of FilesTabPanel called'
        torrent_dir = torrent.get('torrent_dir')
        torrent_file = torrent.get('torrent_name')
        try:
            
            if not os.path.exists(torrent_dir):
                torrent_dir = os.path.join(self.utility.getConfigPath(), "torrent2")
            
            torrent_filename = os.path.join(torrent_dir, torrent_file)
            
            if not os.path.exists(torrent_filename):
                if DEBUG:    
                    print >>sys.stderr,"contentpanel: Torrent: %s does not exist" % torrent_filename
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
            self.DeleteAllItems()
            for f in filelist:
                index = self.InsertStringItem(sys.maxint, f[0])
                self.SetStringItem(index, 1, f[1])
            self.onListResize(None)
            
        except:
            print 'standardDetails: error getting list of files in torrent'
            print_exc(file=sys.stderr)
            return {}                 
        
    def onListResize(self, event):
        size = self.GetClientSize()
        if size[0] > 50 and size[1] > 50:
            self.SetColumnWidth(1, wx.LIST_AUTOSIZE)
            self.SetColumnWidth(0, self.GetClientSize()[0]-self.GetColumnWidth(1)-15)
            self.ScrollList(-100, 0) # Removes HSCROLLBAR
        if event:
            event.Skip()
