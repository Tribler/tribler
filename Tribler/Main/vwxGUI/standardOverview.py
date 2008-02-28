import wx, os, sys, os.path
import wx.xrc as xrc
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from traceback import print_exc,print_stack
from Tribler.Main.vwxGUI.torrentManager import TorrentDataManager
from Tribler.Main.vwxGUI.SearchDetails import SearchDetailsPanel
from Tribler.Main.vwxGUI.LoadingDetails import LoadingDetailsPanel
from Tribler.Core.Utilities.utilities import sort_dictlist
from Tribler.Core.Utilities.utilities import *
from Tribler.Main.Utility.constants import *
from Tribler.Core.Overlay.OverlayThreadingBridge import OverlayThreadingBridge
from peermanager import PeerDataManager
import peermanager
from Tribler.Subscriptions.rss_client import TorrentFeedThread
from Tribler.Core.Utilities.unicode import *
from threading import Thread,currentThread
from time import time
import web2


OVERVIEW_MODES = ['filesMode', 'personsMode', 'profileMode', 'friendsMode', 'subscriptionsMode', 'messageMode', 'libraryMode']

DEBUG = True

class standardOverview(wx.Panel):
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
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility
        self.categorykey = None
        self.data_manager = TorrentDataManager.getInstance(self.utility)
        self.peer_manager = PeerDataManager.getInstance(self.utility) #the updateFunc is called after the data is updated in the peer manager so that the GUI has the newest information

        def filterFuncFriend(peer_data):
            return peer_data.get('friend')
        self.peer_manager.registerFilter( 'friends', filterFuncFriend)
        
       
        #register for gui events
        self.peer_manager.registerGui(self.updateFunPersons) #no matter which of the two, persons or friends, is on, the same function is used

        class DataLoadingThread(Thread):
            def __init__(self,owner):
                Thread.__init__(self, name="DataLoadingThread")
                self.setDaemon(True)
                self.owner = owner
                self.buddycast = self.owner.utility.session.lm.overlay_apps.buddycast

            def run(self):
                try:
                    #first load the peer data
#                    peer_list = None
                    #wait for buddycast list only if the recommender is enabled
                    
                    #print >> sys.stderr, '[StartUpDebug]----------- thread data loading started'
                    #first load torrent data from database
                    self.owner.data_manager.loadData()
                    self.refreshView()
                    #print >> sys.stderr, '[StartUpDebug]----------- thread torrent data loaded'
                            
                    self.owner.peer_manager.loadData()
                            
    #                self.owner.sortData(self.owner.prepareData(buddycast_peer_list))
                    #this initialization can be done in another place also
                    
#                    bcactive = self.owner.utility.config.Read('buddycast', "boolean")
#                    if bcactive:
#                        self.buddycast.data_ready_evt.wait()   # called by buddycast
#                        # get the peer list in buddycast. Actually it is a dict, but it can be used
#                        peer_list = self.buddycast.getAllPeerList()
#                        if DEBUG:
#                            print >>sys.stderr,"standardOverview: Buddycast signals it has loaded, release data for GUI thread", len(peer_list), currentThread().getName()
                            
#                    data = self.owner.peer_manager.prepareData()
##                    if bcactive:
##                        self.buddycast.removeAllPeerList()    # to reduce memory
#                        
#            #        self.sortData(data)
#                    self.owner.peer_manager.applyFilters(data)
#            #        print "<mluc> ################### size of data is ",len(self.filtered_data['all'])
#                    self.owner.peer_manager.isDataPrepared = True
                    #print >> sys.stderr, '[StartUpDebug]----------- thread peer data loaded'
                    
                except:
                    print_exc()
                wx.CallAfter(self.owner.OnLoadingDone)

            def refreshView(self):
                wx.CallAfter(self.owner.filterChanged)

        self.mode = None
        self.data = {} #keeps gui elements for each mode
        for mode in OVERVIEW_MODES:
            self.data[mode] = {} #each mode has a dictionary of gui elements with name and reference
        self.currentPanel = None
        self.addComponents()
        #self.Refresh()
        
        self.guiUtility.initStandardOverview(self)    # show file panel
        self.toggleLoadingDetailsPanel(True)
        
        # Jie TODO: add task to overlay bridge
        #overlay_bridge = OverlayThreadingBridge.getInstance()
        #overlay_bridge.add_task(run, 0)
        
        thr1=DataLoadingThread(self)
        thr1.setDaemon(True)
        thr1.start()
        #print 'thread.start()'
        
        #print >> sys.stderr, '[StartUpDebug]----------- standardOverview is in postinit ----------', currentThread().getName(), '\n\n'
        
    def OnLoadingDone(self):
        #self.data_manager.mergeData()
        self.filterChanged()
        self.toggleLoadingDetailsPanel(False)
        
    def addComponents(self):
        self.hSizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.hSizer)
        self.SetAutoLayout(1)
        self.Layout()
        
    def setMode(self, mode):
        # switch to another view, 
        # mode is one of the [filesMode, personsMode, friendsMode, profileMode, libraryMode, subscriptionsMode]
        if self.mode != mode:
            self.stopWeb2Search()
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
        wx.CallAfter(self.currentPanel.Layout)
        wx.CallAfter(self.currentPanel.Refresh)
        #self.Show(True)
        
        
    def loadPanel(self):
        currentPanel = self.data[self.mode].get('panel',None)
        modeString = self.mode[:-4]
        if DEBUG:
            print >>sys.stderr,'standardOverview: loadPanel: modeString='+modeString,'currentPanel:',currentPanel
        # create the panel for the first click. panel could be one of the [file,person,friend,library,profile,rss]
        if not currentPanel:    
            xrcResource = os.path.join(self.guiUtility.vwxGUI_path, modeString+'Overview.xrc')
            panelName = modeString+'Overview'
            try:
                currentPanel = grid = pager = None
                res = xrc.XmlResource(xrcResource)
                # create panel
                currentPanel = res.LoadPanel(self, panelName)
                grid = xrc.XRCCTRL(currentPanel, modeString+'Grid')    
                pager = xrc.XRCCTRL(currentPanel, 'standardPager')    # Jie:not really used for profile, rss and library?
                search = xrc.XRCCTRL(currentPanel, 'searchField')
                filter = xrc.XRCCTRL(currentPanel, modeString+'Filter')
                if not currentPanel:
                    raise Exception('standardOverview: Could not find panel, grid or pager')
                    #load dummy panel
                    dummyFile = os.path.join(self.guiUtility.vwxGUI_path, 'dummyOverview.xrc')
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
                        web2on = self.utility.config.Read('enableweb2search',"boolean")
                        if web2on:
                            txt = self.utility.lang.get('filesdefaultsearchweb2txt')
                        else:
                            txt = self.utility.lang.get('filesdefaultsearchtxt')
                        search.SetValue(txt)
                        search.Bind(wx.EVT_MOUSE_EVENTS, self.guiUtility.OnSearchMouseAction)
                                            
                pager.setGrid(grid)
                
                if self.mode in ['filesMode', 'personsMode']:
                    viewModeSelect = xrc.XRCCTRL(currentPanel, 'modeItems')
                    overviewSizeSelect = xrc.XRCCTRL(currentPanel, 'numberItems')                    
                    # set default values
                    viewModeSelect.Select(0) #SetValue('thumbnails')
                    overviewSizeSelect.Select(0) #SetValue('auto')
                    #viewModeSelect.Bind(wx.EVT_COMBOBOX, grid.onViewModeChange)
                    viewModeSelect.Bind(wx.EVT_CHOICE, grid.onViewModeChange)
                    #overviewSizeSelect.Bind(wx.EVT_COMBOBOX, grid.onSizeChange)
                    overviewSizeSelect.Bind(wx.EVT_CHOICE, grid.onSizeChange)
                    
                if self.mode == 'subscriptionsMode':
                    rssurlctrl = xrc.XRCCTRL(currentPanel,'pasteUrl')
                    rssurlctrl.Bind(wx.EVT_KEY_DOWN, self.guiUtility.OnSubscribeKeyDown)
                    rssurlctrl.Bind(wx.EVT_LEFT_UP, self.guiUtility.OnSubscribeMouseAction)
                    txt = self.utility.lang.get('rssurldefaulttxt')
                    rssurlctrl.SetValue(txt)

                    self.data[self.mode]['rssurlctrl'] = rssurlctrl
            except:
                if DEBUG:
                    print >>sys.stderr,'standardOverview: Error: Could not load panel, grid and pager for mode %s' % self.mode
                    print >>sys.stderr,'standardOverview: Tried panel: %s=%s, grid: %s=%s, pager: %s=%s' % (panelName, currentPanel, modeString+'Grid', grid, 'standardPager', pager)
                print_exc()
        return currentPanel
     
    def refreshData(self):        
        if DEBUG:
            print >>sys.stderr,"standardOverview: refreshData"
        
        grid = self.data[self.mode].get('grid')
        if grid:
            
            if DEBUG:
                data = self.data[self.mode].get('data')
                if type(data) == list:
                    print >>sys.stderr,"standardOverview: refreshData: refreshing",len(data)
            
            # load and show the data in the grid
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
        wx.CallAfter(self.refreshTorrentStats)
        
    def refreshTorrentStats(self):
        if self.mode == 'libraryMode':
            grid = self.data[self.mode].get('grid')
            grid.refreshData()
    
    def filterChanged(self, filterState = None, setgui = False):
        if DEBUG:
            print >>sys.stderr,"standardOverview: filterChanged",filterState,setgui,self.mode#,self.data[self.mode]
        
        oldFilterState = self.data[self.mode].get('filterState')
        
        if DEBUG:
            print >>sys.stderr,"standardOverview: filterChanged: from",oldFilterState,"to",filterState
        
        if filterState is None or len(filterState) == 0:
            filterState = oldFilterState
        
        if filterState and oldFilterState:
            for i in xrange(len(filterState)):
                if filterState[i] == None:
                    filterState[i] = oldFilterState[i]
                        
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
        
        if DEBUG:
            print >>sys.stderr,"standardOverview: before refreshData"

        
        if setgui:
            filter = self.data[self.mode]['filter']
            if filter is not None:
                filter.setSelectionToFilter(filterState)
        
        self.refreshData()
        self.data[self.mode]['filterState'] = filterState
                
            
    def loadTorrentData(self, cat, sort):
        # cat can be 'all', 'friends', 'search', 'search_friends', None, self.data[self.mode].get('filterState')[0]
        # sort can be 'seeder',..
        if DEBUG:
            print >>sys.stderr,'standardOverview: loadTorrentData: Category set to %s, %s' % (str(cat), str(sort))
        
        if cat is not None:
            # Unregister for old category
            self.data_manager.unregisterAll(self.updateFunTorrents)
            
            # Register for new one    
            
            self.data_manager.register(self.updateFunTorrents, cat, self.mode == 'libraryMode')
            self.type = sort
            
            torrentData = self.data_manager.getCategory(cat, self.mode)

            if DEBUG:
                if type(torrentData)  == list:
                    print >>sys.stderr,"standardOverview: getCategory returned",len(torrentData)
            
            # Jelle: This is now done in data_manager.getCategory()
#            if type(data) == list:
#                self.filtered = []
#                for torrent in data:
#                    if torrent.get('status') == 'good' or torrent.get('myDownloadHistory'):
#                        
#                        if DEBUG:
#                            print >>sys.stderr,"standardOverview: prefilter adding",`torrent['content_name']`
#
#                        self.filtered.append(torrent)
#            elif data.isDod():
#                data.addFilter(lambda x:x.get('status') == 'good' or x.get('myDownloadHistory'))

        if type(torrentData) == list:
            if type(sort) == str:
                torrentData = sort_dictlist(torrentData, sort, 'decrease')
            elif type(sort) == tuple:
                torrentData = sort_dictlist(torrentData, sort[0], sort[1])

            if DEBUG:
                print >>sys.stderr,"standardOverview: filtering",len(torrentData)
        
        elif torrentData.isDod():
            keysort = ["web2"]
            if type(sort) == str:
                keysort.append((sort, 'decrease'))
            elif type(sort) == tuple:
                keysort.append(sort)
            torrentData.setSort(lambda list: multisort_dictlist(list, keysort))
            
        self.data[self.mode]['data'] = torrentData
    
    
    def loadPersonsData(self, cat, sort):
        if DEBUG:
            print >>sys.stderr,'standardOverview: <mluc>[',self.mode,'view] Category set to %s, %s' % (str(cat), str(sort))

        if self.mode in [ "personsMode","friendsMode"]:
            self.data[self.mode]['data'] = self.peer_manager.getFilteredData(cat)
            #check the current sorting for current filter
            self.peer_manager.setSortingMode(sort, cat)
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
        for torrent in self.utility.session.get_downloads():
            activeInfohashes[torrent.get_def().get_infohash()] = torrent
            if DEBUG:
                print >>sys.stderr,"standardOverview: Load library active is",`torrent.get_def().get_name()`
        
        if sort != 'latest':
            preSorting = sort
        else:
            # Sorting of torrents is redone, after loadTorrentData
            preSorting = 'date'
        self.loadTorrentData(cat, preSorting)
        
        libraryList = self.data[self.mode]['data']
        
        if type(libraryList) == web2.DataOnDemandWeb2:
            raise Exception('dod!!')
        
        if not libraryList:
            return
        # Add abctorrents to library data
        for torrent in libraryList:
            infohash = torrent.get('infohash')
            if infohash in activeInfohashes:
                torrent['abctorrent'] = activeInfohashes[infohash]
        
        if sort == 'latest':
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
            for t in libraryList:
                print >>sys.stderr,"standardOverview: Loading ITEM",`t['content_name']`, `t['seeder']`, `t['leecher']`
            #print >>sys.stderr,'standardOverview: Loading libraryList: %s' % [(self.isTorrentFinished(t), t.get('download_started',False)) for t in libraryList]
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
            state = abctorrent.network_get_state()
            progress = state.get_progress()
            return (progress == 100.0)
        
    def loadSubscriptionData(self):
        torrentfeed = TorrentFeedThread.getInstance()
        urls = torrentfeed.getURLs()
        
        bcsub = self.utility.lang.get('buddycastsubscription')
        web2sub = self.utility.lang.get('web2subscription')
        
        bcactive = self.utility.config.Read('startrecommender', "boolean")
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
            print >>sys.stderr,"standardOverview: updateFunTorrents called: %s, %s" % (operate, repr(torrent.get('content_name')))
        try:
            detailsPanel = self.guiUtility.standardDetails
        except:
            detailsPanel = None
            if DEBUG:
                print >>sys.stderr,'standardOverview: Error could not find standardDetailsPanel'
            
        if operate in ['update', 'delete']:
            if detailsPanel and detailsPanel.getIdentifier() == torrent['infohash']:
                wx.CallAfter(detailsPanel.setData,torrent)
        
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
            wx.CallAfter(self.filterChanged,None)
            return
            
        if operate == 'update':
            # unhealthy torrents are also updated
            torrentgrid_updateItem_lambda = lambda:torrentGrid.updateItem(torrent,onlyupdate=True) 
        elif operate == 'add' and torrent.get('status') == 'good' or torrent.get('myDownloadHistory'):
            #print "******** add torrent", torrent,self.mode,self.data_manager.inSearchMode(self.mode)
            
            # only show update if we are not searching or update is a RemoteSearchResult
            if not self.data_manager.inSearchMode(self.mode) or torrent.has_key('query_permid'):
                # new torrents are only added when healthy
                torrentgrid_updateItem_lambda = lambda:torrentGrid.updateItem(torrent)
            else:    
                torrentgrid_updateItem_lambda = None
                
        elif operate == 'delete':
            torrentgrid_updateItem_lambda = lambda:torrentGrid.updateItem(torrent,delete=True)
        if torrentgrid_updateItem_lambda is not None:
            wx.CallAfter(torrentgrid_updateItem_lambda)
        
    def updateFunPersons(self, peer_data, operate):    
        grid = None
        if peer_data == None:
            return
        if self.mode in ["personsMode","friendsMode"]:
            grid = self.data[self.mode].get('grid')
        if grid is not None:
            try:
                if DEBUG:
                    print >>sys.stderr,"standardOverview: updateFunPersons called with",operate,"for",peer_data.get('content_name'),"in mode",self.mode
                #something changed, so refresh data in grid
                wx.CallAfter(self.refreshData)
                #check if the changed peer_data is in the list of visible ones
#                for index in range(grid.currentData,grid.currentData+grid.items):
#                    if index<len(grid.data) and grid.data[index]['permid'] == peer_data['permid']:
#                        if operate in ["update","add","online","offline"]:
#                            wx.CallAfter(self.refreshData)#grid.setDataOfPanel,[index-grid.currentData, grid.data[index]])
#                        elif operate in ["delete","hide"]:
#                            wx.CallAfter(self.refreshData)#grid.setData,[grid.data,False])
#                        elif operate.endswith("and top_changed"):
#                            wx.CallAfter(grid.refreshPanels)
#                print "#===============================================================================#"
#                print "#                         dump visible peers                                    #"
#                for index in range(grid.currentData,grid.currentData+grid.items):
#                    if index<len(grid.data):
#                        print "#     %d. %s     %f" % (grid.data[index]['simTop'],unicode2str(grid.data[index]['content_name']),grid.data[index]['similarity'])
#                print "#===============================================================================#"
            except:
                print_exc()
                wx.CallAfter(grid.refreshPanels)
    
    def getSearchField(self,mode=None):
        if mode is None:
            mode = self.mode
        return self.data[mode]['search']
    
    def getGrid(self):
        return self.data.get(self.mode, {}).get('grid')
    
    def clearSearch(self):
        self.data[self.mode]['search'].Clear()
        if self.mode in ['filesMode', 'libraryMode']:
            self.guiUtility.data_manager.setSearchKeywords([], self.mode)
            self.filterChanged(None)
        elif self.mode == 'personsMode':
            self.filterChanged(['all', None])
        elif self.mode == 'friendsMode':
            self.filterChanged(['friends', None])
        
    def getSorting(self):
        fs = self.data[self.mode].get('filterState')
        if fs:
            return fs[1]
        else:
            return None
    
    def getFilter(self):
        return self.data[self.mode]['filter']

    def getPager(self):
        return self.data[self.mode]['pager']
        
    def getRSSUrlCtrl(self):
        return self.data[self.mode]['rssurlctrl']
    
    def gridIsAutoResizing(self):
        return self.getGrid().sizeMode == 'auto'
        
    def setSearchFeedback(self,*args,**kwargs):
        """ May be called by web2.0 thread """
        setSearchFeedback_lambda = lambda:self._setSearchFeedback(args,kwargs)
        wx.CallAfter(setSearchFeedback_lambda)
        
    def getSearchBusy(self):
        searchDetailsPanel = self.data[self.mode].get('searchDetailsPanel')
        if searchDetailsPanel:
            return searchDetailsPanel.searchBusy
        else:
            return False
            
    def _setSearchFeedback(self, type, finished, num, keywords = []):
        #print 'standardOverview: _setSearchFeedback called by', currentThread().getName()
        searchDetailsPanel = self.data[self.mode].get('searchDetailsPanel')
        if searchDetailsPanel:
            searchDetailsPanel.setMessage(type, finished, num, keywords)
        
    def growWithGrid(self):
        gridHeight = self.data[self.mode]['grid'].GetSize()[1]
        pagerHeight = 29
        filterHeight = 21 + 8+ self.data[self.mode]['filter'].GetSize()[1]
        
        newSize = (-1, gridHeight + pagerHeight + filterHeight)
        self.SetSize(newSize)
        self.SetMinSize(newSize)
        self.GetSizer().Layout()
        self.GetContainingSizer().Layout()
        self.guiUtility.scrollWindow.FitInside()
        self.guiUtility.refreshOnResize()
        
    def removeTorrentFromLibrary(self, torrent):
        "Remove torrent from the library. Add it to discovered files?"
        infohash = torrent['infohash']
        self.data_manager.setBelongsToMyDowloadHistory(infohash, False)
        
    def gotRemoteHits(self,permid,kws,answers):
        """ Called by RemoteQueryMsgHandler """
        if self.mode == 'filesMode':
            if self.data_manager.gotRemoteHits(permid,kws,answers,self.mode):
                # remote info still valid, repaint if we're showing search results
                fs = self.data[self.mode]['filterState']
                #print "****** fs remote hits:", fs, len(self.data_manager.hits)
                #if fs[0] == 'search':
                #    self.filterChanged(['search','swarmsize'])
                #self.filterChanged([fs[0],'swarmsize'])
                    
    def toggleLoadingDetailsPanel(self, visible):
        loadingDetails = self.data[self.mode].get('loadingDetailsPanel')
        sizer = self.data[self.mode]['grid'].GetContainingSizer()
        if visible:
            if not loadingDetails:
                loadingDetails = LoadingDetailsPanel(self.data[self.mode]['panel'])
                
                sizer.Insert(3,loadingDetails, 0, wx.ALL|wx.EXPAND, 0)
                self.data[self.mode]['loadingDetailsPanel'] = loadingDetails
                loadingDetails.Show()
            else:
                loadingDetails.startSearch()
                loadingDetails.Show()
                
        else:
            if loadingDetails:
                #print 'standardOverview: removing loading details'
                sizer.Detach(loadingDetails)
                loadingDetails.Destroy()
                self.data[self.mode]['loadingDetailsPanel'] = None
        sizer.Layout()
        self.data[self.mode]['panel'].Refresh()
        self.hSizer.Layout()

    def setLoadingCount(self,count):
        loadingDetails = self.data[self.mode].get('loadingDetailsPanel')
        if not loadingDetails:
            return
        loadingDetails.setMessage('loaded '+str(count)+' more files from database (not yet shown)')


    def toggleSearchDetailsPanel(self, visible):
        searchDetails = self.data[self.mode].get('searchDetailsPanel')
        sizer = self.data[self.mode]['grid'].GetContainingSizer()
        #print 'standardOverview: Sizer: %s' % sizer
        #print 'standardOverview: SearchDetails: %s' % searchDetails
        #if searchDetails:
        #    print 'standardOverview: %s, %s' % (str(searchDetails.GetSize()), str(searchDetails.GetMinSize()))
        
        if visible:
            if not searchDetails:
                searchDetails = SearchDetailsPanel(self.data[self.mode]['panel'])
                
                #print 'standardOverview: Inserting search details'
                sizer.Insert(3,searchDetails, 0, wx.ALL|wx.EXPAND, 0)
                #sizer.Layout()
                #self.data[self.mode]['panel'].Refresh()
#                print 'Size: %s' % str(self.searchDetails.GetSize())
#                print 'Parent: %s' % str(self.searchDetails.GetParent().GetName())
#                print 'GParent: %s' % str(self.searchDetails.GetParent().GetParent().GetName())
                self.data[self.mode]['searchDetailsPanel'] = searchDetails
                searchDetails.Show()
            else:
                searchDetails.startSearch()
                searchDetails.Show()
                
        else:
            if searchDetails:
                #print 'standardOverview: removing search details'
                sizer.Detach(searchDetails)
                searchDetails.Destroy()
                self.data[self.mode]['searchDetailsPanel'] = None
        sizer.Layout()
        self.data[self.mode]['panel'].Refresh()
        self.hSizer.Layout()


    def stopWeb2Search(self):
        grid = self.getGrid()
        if grid:
            grid.stopWeb2Search()
