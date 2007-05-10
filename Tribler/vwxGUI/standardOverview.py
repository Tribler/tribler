import wx, os, sys, os.path
import wx.xrc as xrc
from Tribler.vwxGUI.GuiUtility import GUIUtility
from safeguiupdate import FlaglessDelayedInvocation
from traceback import print_exc,print_stack
from Tribler.vwxGUI.torrentManager import TorrentDataManager
from Tribler.utilities import *
from Utility.constants import *
from peermanager import PeerDataManager
import peermanager
from Tribler.Subscriptions.rss_client import TorrentFeedThread
from Tribler.unicode import *
from threading import Thread,currentThread
from time import time

OVERVIEW_MODES = ['filesMode', 'personsMode', 'profileMode', 'friendsMode', 'subscriptionsMode', 'messageMode', 'libraryMode']

DEBUG = True

class standardOverview(wx.Panel,FlaglessDelayedInvocation):
    """
    Panel that shows one of the overview panels
    """
    def __init__(self, *args):
        
        if len(args) == 0:
            pre = wx.PrePanel()
            # the Create step is done by XRC.
            self.PostCreate(pre)
            self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate)
        else:
            wx.Panel.__init__(self, *args)
            self._PostInit()
        
    def OnCreate(self, event):
        self.Unbind(wx.EVT_WINDOW_CREATE)
        wx.CallAfter(self._PostInit)
        event.Skip()
        return True
    
    def _PostInit(self):
        # Do all init here
        FlaglessDelayedInvocation.__init__(self)
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility
        self.categorykey = None
        self.data_manager = TorrentDataManager.getInstance(self.utility)
        
        self.peer_manager = PeerDataManager.getInstance(self.utility) #the updateFunc is called after the data is updated in the peer manager so that the GUI has the newest information
#        self.peer_manager.register(self.updateFun, 'all')
        def filterFuncFriend(peer_data):
            return peer_data.get('friend')
        self.peer_manager.registerFilter( 'friends', filterFuncFriend)
        #register for gui events
        self.peer_manager.registerGui(self.updateFunPersons) #no matter which of the two, persons or friends, is on, the same function is used

        class DataLoadingThread(Thread):
            def __init__(self,owner):
                Thread.__init__(self, name="DataLoadingThread")
                self.owner = owner

            def run(self):
                try:
                    print >> sys.stderr, '[StartUpDebug]----------- thread data loading started'
                    #first load torrent data from database
                    self.owner.data_manager.loadData()
                    print >> sys.stderr, '[StartUpDebug]----------- thread torrent data loaded'
                    #then load the peer data
                    peer_list = None
                    #wait for buddycast list only if the recommender is enabled
                    bcactive = self.owner.utility.config.Read('enablerecommender', "boolean")
                    if bcactive:
                        self.owner.utility.buddycast.data_ready_evt.wait()   # called by buddycast
                        # get the peer list in buddycast. Actually it is a dict, but it can be used
                        peer_list = self.owner.utility.buddycast.data_handler.peers
                        if DEBUG:
                            print >>sys.stderr,"standardOverview: Buddycast signals it has loaded, release data for GUI thread", len(peer_list), currentThread().getName()
    #                self.owner.sortData(self.owner.prepareData(buddycast_peer_list))
                    #this initialization can be done in another place also
                    data = self.owner.peer_manager.prepareData(peer_list)
            #        self.sortData(data)
                    self.owner.peer_manager.applyFilters(data)
            #        print "<mluc> ################### size of data is ",len(self.filtered_data['all'])
                    self.owner.peer_manager.isDataPrepared = True
                    print >> sys.stderr, '[StartUpDebug]----------- thread peer data loaded'
                except:
                    print_exc()
                wx.CallAfter(self.owner.filterChanged)

        thr1=DataLoadingThread(self)
        thr1.setDaemon(True)
        thr1.start()

        self.mode = None
        self.data = {} #keeps gui elements for each mode
        for mode in OVERVIEW_MODES:
            self.data[mode] = {} #each mode has a dictionary of gui elements with name and reference
        self.currentPanel = None
        self.addComponents()
        #self.Refresh()
        self.guiUtility.initStandardOverview(self)
        print >> sys.stderr, '[StartUpDebug]----------- standardOverview is in postinit ----------', currentThread().getName(), '\n\n'
        
        
    def addComponents(self):
        self.hSizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.hSizer)
        self.SetAutoLayout(1)
        self.Layout()
        
    def setMode(self, mode):
        if self.mode != mode: 
            self.mode = mode
            self.refreshMode()
            
            
    def refreshMode(self):
        # load xrc
        self.oldpanel = self.currentPanel
        #self.Show(False)
        
        self.currentPanel = self.loadPanel()
        assert self.currentPanel, "Panel could not be loaded"
        #self.currentPanel.GetSizer().Layout()
        #self.currentPanel.Enable(True)
        self.currentPanel.Show(True)
        
        if self.oldpanel:
            self.hSizer.Detach(self.oldpanel)
            self.oldpanel.Hide()
            #self.oldpanel.Disable()
        
        self.hSizer.Add(self.currentPanel, 1, wx.ALL|wx.EXPAND, 0)
        
        self.hSizer.Layout()
        wx.CallAfter(self.hSizer.Layout)
        wx.CallAfter(self.currentPanel.Refresh)
        #self.Show(True)
        
        
    def loadPanel(self):
        currentPanel = self.data[self.mode].get('panel',None)
        modeString = self.mode[:-4]
        if DEBUG:
            print >>sys.stderr,'standardOverview: loadPanel: modeString='+modeString
        if not currentPanel:
            xrcResource = os.path.join(self.utility.getPath(),'Tribler','vwxGUI', modeString+'Overview.xrc')
            panelName = modeString+'Overview'
            try:
                currentPanel = grid = pager = None
                res = xrc.XmlResource(xrcResource)
                # create panel
                currentPanel = res.LoadPanel(self, panelName)
                grid = xrc.XRCCTRL(currentPanel, modeString+'Grid')
                pager = xrc.XRCCTRL(currentPanel, 'standardPager')
                search = xrc.XRCCTRL(currentPanel, 'searchField')
                filter = xrc.XRCCTRL(currentPanel, modeString+'Filter')
                if not currentPanel:
                    raise Exception('standardOverview: Could not find panel, grid or pager')
                    #load dummy panel
                    dummyFile = os.path.join(self.utility.getPath(),'Tribler','vwxGUI', 'dummyOverview.xrc')
                    dummy_res = xrc.XmlResource(dummyFile)
                    currentPanel = dummy_res.LoadPanel(self, 'dummyOverview')
                    grid = xrc.XRCCTRL(currentPanel, 'dummyGrid')
                    pager = xrc.XRCCTRL(currentPanel, 'standardPager')
                if not currentPanel: # or not grid or not pager:
                    raise Exception('standardOverview: Could not find panel, grid or pager')
                
                # Save paneldata in self.data
                self.data[self.mode]['panel'] = currentPanel
                self.data[self.mode]['grid'] = grid
                self.data[self.mode]['pager'] = pager
                self.data[self.mode]['search'] = search
                self.data[self.mode]['filter'] = filter
                #search.Bind(wx.EVT_COMMAND_TEXT_ENTER, self.OnSearchKeyDown)
                if search is not None:
                    search.Bind(wx.EVT_KEY_DOWN, self.guiUtility.OnSearchKeyDown)
                    if modeString == "files":
                        search.SetValue(self.utility.lang.get('filesdefaultsearchtxt'))
                        search.Bind(wx.EVT_LEFT_UP, self.guiUtility.OnSearchMouseAction)
                    
                pager.setGrid(grid)
                
                if self.mode == 'subscriptionsMode':
                    rssurlctrl = xrc.XRCCTRL(currentPanel,'pasteUrl')
                    rssurlctrl.Bind(wx.EVT_KEY_DOWN, self.guiUtility.OnSubscribeKeyDown)
                    self.data[self.mode]['rssurlctrl'] = rssurlctrl
            except:
                if DEBUG:
                    print >>sys.stderr,'standardOverview: Error: Could not load panel, grid and pager for mode %s' % self.mode
                    print >>sys.stderr,'standardOverview: Tried panel: %s=%s, grid: %s=%s, pager: %s=%s' % (panelName, currentPanel, modeString+'Grid', grid, 'standardPager', pager)
                print_exc()
        return currentPanel
     
    def refreshData(self):        
        grid = self.data[self.mode].get('grid')
        if grid:
            grid.setData(self.data[self.mode].get('data'), resetPages = False)
        
    def updateSelection(self):
        grid = self.data[self.mode].get('grid')
        if grid:
            grid.updateSelection()
        elif DEBUG:
            print >>sys.stderr,'standardOverview: Could not update selection: No grid'
        
        
    def getFirstItem(self):
        data = self.data[self.mode].get('data')
        if data and len(data) > 0:
            return data[0]
        else:
            if DEBUG:
                print >>sys.stderr,'standardOverview: Error, could not return firstItem, data=%s' % data
            return None
        
    def refreshTorrentStats_network_callback(self):
        """ Called by network thread """
        self.invokeLater(self.refreshTorrentStats)
        
    def refreshTorrentStats(self):
        if self.mode == 'libraryMode':
            grid = self.data[self.mode].get('grid')
            grid.refreshData()
    
    def filterChanged(self, filterState = None, setgui = False):
        oldFilterState = self.data[self.mode].get('filterState')
        
        if DEBUG:
            print >>sys.stderr,"standardOverview: filterChanged: from",oldFilterState,"to",filterState
        
        if filterState is None or len(filterState) == 0:
            filterState = oldFilterState
        if filterState is not None:
                
            if self.mode == 'filesMode':
                self.loadTorrentData(filterState[0], filterState[1])
                
            elif self.mode == 'personsMode':
                self.loadPersonsData(filterState[0], filterState[1])
            
            elif self.mode == 'libraryMode':
                self.loadLibraryData(filterState[0], filterState[1])
            elif self.mode == 'friendsMode':
                self.loadPersonsData(filterState[0], filterState[1])
                
            elif self.mode == 'subscriptionsMode':
                self.loadSubscriptionData()
            else:
                if DEBUG:
                    print >>sys.stderr,'standardOverview: Filters not yet implemented in this mode'
                return
        
        if setgui:
            filter = self.data[self.mode]['filter']
            if filter is not None:
                filter.setSelectionToFilter(filterState)
        
        self.refreshData()
        self.data[self.mode]['filterState'] = filterState
                
            
    def loadTorrentData(self, cat, sort):
        if DEBUG:
            print >>sys.stderr,'standardOverview: loadTorrentData: Category set to %s, %s' % (str(cat), str(sort))
        
        if cat is not None:
            # Unregister for old category
            if self.categorykey:
                self.data_manager.unregister(self.updateFunTorrents, self.categorykey)
            
            # Register for new one    
            self.categorykey = cat
            self.data_manager.register(self.updateFunTorrents, self.categorykey)
            self.type = sort
            
            data = self.data_manager.getCategory(self.categorykey)
        
            self.filtered = []
            for torrent in data:
                if torrent.get('status') == 'good' or torrent.get('myDownloadHistory'):
                    self.filtered.append(torrent)
            
        
        if type(sort) == str:
            self.filtered = sort_dictlist(self.filtered, sort, 'decrease')
        elif type(sort) == tuple:
            self.filtered = sort_dictlist(self.filtered, sort[0], sort[1])
        
        self.data[self.mode]['data'] = self.filtered
    
    
    def loadPersonsData(self, cat, sort):
#        print '<mluc>[',self.mode,'view] Category set to %s, %s' % (str(cat), str(sort))

        if self.mode in [ "personsMode","friendsMode"]:
            self.data[self.mode]['data'] = self.peer_manager.getFilteredData(cat)
            #check the current sorting for current filter
            currentSortFunc = self.peer_manager.getCmpFunc(cat)
            newSortFunc = None
            if type(sort) == str:
                if sort == 'similarity':
                    newSortFunc = peermanager.cmpFuncSimilarity
                elif sort == 'last_seen':
                    newSortFunc = peermanager.cmpFuncConnectivity
            elif type(sort) == tuple:
                if sort[0] == "content_name":
                    if sort[1] == "increase":
                        newSortFunc = peermanager.cmpFuncNameAsc
                    else:
                        newSortFunc = peermanager.cmpFuncNameDesc
            if currentSortFunc != newSortFunc:
                self.peer_manager.setCmpFunc(newSortFunc, cat)
        else:
            if DEBUG:
                print >>sys.stderr,"standardOverview: loadPersonsData: <mluc> not correct standard overview mode for loading peers:",self.mode
    
    def loadLibraryData(self, cat, sort):
        # Get infohashes of current downloads
        if DEBUG:
            print >>sys.stderr,'standardOverview: Loaded library data list'
        activeInfohashes = {}
        active = []
        inactive = []
        for torrent in self.utility.torrents['all']:
            activeInfohashes[torrent.torrent_hash] = torrent
            
        
        self.loadTorrentData(self.utility.lang.get('mypref_list_title'), 'date')
        libraryList = self.data[self.mode]['data']
        # Add abctorrents to library data
        for torrent in libraryList:
            infohash = torrent.get('infohash')
            if infohash in activeInfohashes:
                torrent['abctorrent'] = activeInfohashes[infohash]
        
        def librarySort(x, y):
            xFin = self.isTorrentFinished(x)
            yFin = self.isTorrentFinished(y)
            if xFin and not yFin:
                return 1
            elif not xFin and yFin:
                return -1
            else:
                xDate = self.getDownloadStartedTime(x)
                yDate = self.getDownloadStartedTime(y)
                diff = int(yDate - xDate)
                assert type(diff) == int, 'Difference should be a int value'
                return diff
            
        libraryList.sort(librarySort)
        if DEBUG:
            print >>sys.stderr,'standardOverview: Loading libraryList: %s' % [(self.isTorrentFinished(t), t.get('download_started',False)) for t in libraryList]
        self.data[self.mode]['data'] = libraryList
        if DEBUG:
            print >>sys.stderr,'standardOverview: Loaded %d library items' % len(self.data[self.mode]['data'])
        
    def getDownloadStartedTime(self, torrent):
        if torrent.get('download_started'):
            return torrent['download_started']
        else:
            # get from mypref db
            t = self.utility.mypref_db.getCreationTime(torrent['infohash'])
            if t:
                torrent['download_started'] = t
                return t
            else:
                raise Exception('standardOverview: cannot get downloadStartedTime')
                return 0
            
    def isTorrentFinished(self, torrent):
        "Is this torrent ready downloading (active or inactive)"
        abctorrent = torrent.get('abctorrent')
        progression = torrent.get('progress')
        if abctorrent == None:
            if progression != None:
                return (progression == 100.0)
            else:
                if DEBUG:
                    print >>sys.stderr,'standardOverview: isTorrentFinished: Could not get progression'
                #print 'standardOverview: Error could not get progression of torrent: %s' % torrent
                return False
        else:
            progresstxt = abctorrent.getColumnText(COL_PROGRESS)
            progress = float(progresstxt[:-1])
            return (progress == 100.0)
        
    def loadSubscriptionData(self):
        torrentfeed = TorrentFeedThread.getInstance()
        urls = torrentfeed.getURLs()
        
        bcsub = self.utility.lang.get('buddycastsubscription')
        web2sub = self.utility.lang.get('web2subscription')
        
        bcactive = self.utility.config.Read('enablerecommender', "boolean")
        bcstatus = 'inactive'
        if bcactive:
            bcstatus = 'active'
        web2active = self.utility.config.Read('enableweb2search', "boolean")
        web2status = 'inactive'
        if web2active:
            web2status = 'active'
        
        reclist = []
        record = {'url':bcsub,'status':bcstatus,'persistent':'BC'}
        reclist.append(record)
        record = {'url':web2sub,'status':web2status,'persistent':'Web2.0'}
        reclist.append(record)
        for url in urls:
            record = {}
            record['url'] = url
            record['status'] = urls[url]
            reclist.append(record)
        self.data[self.mode]['data'] = reclist
        
    def updateFunTorrents(self, torrent, operate):    
        if DEBUG:
            print >>sys.stderr,"standardOverview: updateFunTorrents called: %s, %s" % (operate, str(torrent))
        try:
            detailsPanel = self.guiUtility.standardDetails
        except:
            detailsPanel = None
            if DEBUG:
                print >>sys.stderr,'standardOverview: Error could not find standardDetailsPanel'
            
        if operate in ['update', 'delete']:
            if detailsPanel and detailsPanel.getIdentifier() == torrent['infohash']:
                self.invokeLater(detailsPanel.setData, [torrent])
        
        #<mluc>[04.05.2007]: using self.mode corrupts the data in peermanager if the 
        #current view selected is persons or friends, so, the solution would be to
        #always try to update the data in filesMode
        # PLEASE, DON'T REMOVE ALERT MESSAGE UNTIL A CORRECT SOLUTION IS FOUND!!!!

        if self.mode in [ "personsMode", "friendsMode", "subscriptionsMode"]:
            raise Exception("standardOverview: updateFunTorrents called while in non-torrent mode",self.mode,"!!!!!")
            return
        
        torrentGrid = self.data[self.mode]['grid']
        assert torrentGrid, 'standardOverview: could not find Grid of %s' % self.mode
        
        if self.mode == 'libraryMode':
            # Reload whole library to make sorting ok
            self.invokeLater(self.filterChanged, [None])
            return
            
        if operate == 'update':
            # unhealthy torrents are also updated
            self.invokeLater(torrentGrid.updateItem, [torrent])
        elif operate == 'add' and torrent.get('status') == 'good' or torrent.get('myDownloadHistory'):
            # new torrents are only added when healthy
            self.invokeLater(torrentGrid.updateItem, [torrent])
        elif operate == 'delete':
            self.invokeLater(torrentGrid.updateItem, [torrent], {'delete':True})
            
        
    def updateFunPersons(self, peer_data, operate):    
        grid = None
        if self.mode in ["personsMode","friendsMode"]:
            grid = self.data[self.mode].get('grid')
        if grid is not None:
            try:
                if DEBUG:
                    print >>sys.stderr,"standardOverview: updateFunPersons called for ",peer_data['content_name']
                #check if the changed peer_data is in the list of visible ones
                for index in range(grid.currentData,grid.currentData+grid.items):
                    if index<len(grid.data) and grid.data[index]['permid'] == peer_data['permid']:
                        if operate in ["update","add"]:
                            self.invokeLater(grid.setDataOfPanel,[index-grid.currentData, grid.data[index]])
                        elif operate in ["delete","hide"]:
                            self.invokeLater(grid.setData,[grid.data,False])
                        elif operate.endswith("and top_changed"):
                            self.invokeLater(grid.refreshPanels)
#                print "#===============================================================================#"
#                print "#                         dump visible peers                                    #"
#                for index in range(grid.currentData,grid.currentData+grid.items):
#                    if index<len(grid.data):
#                        print "#     %d. %s     %f" % (grid.data[index]['simTop'],unicode2str(grid.data[index]['content_name']),grid.data[index]['similarity'])
#                print "#===============================================================================#"
            except:
                print_exc()
                self.invokeLater(grid.refreshPanels)
    
    def getSearchField(self):
        return self.data[self.mode]['search']
    
    def getFilter(self):
        return self.data[self.mode]['filter']

        
    def getRSSUrlCtrl(self):
        return self.data[self.mode]['rssurlctrl']
    
        
    def removeTorrentFromLibrary(self, torrent):
        "Remove torrent from the library. Add it to discovered files?"
        infohash = torrent['infohash']
        self.utility.mypref_db.deletePreference(infohash)
        self.utility.mypref_db.sync()
        self.data_manager.setBelongsToMyDowloadHistory(infohash, False)
        