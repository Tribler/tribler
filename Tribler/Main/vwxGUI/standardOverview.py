# Written by Jelle Roozenburg, Maarten ten Brinke 
# see LICENSE.txt for license information

import wx, os, sys, os.path
import wx.xrc as xrc
from traceback import print_exc,print_stack

from Tribler.Core.simpledefs import *
from Tribler.Core.Utilities.unicode import *
from Tribler.Core.Utilities.utilities import sort_dictlist
from Tribler.Core.Utilities.utilities import *
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility

from traceback import print_exc,print_stack
from Tribler.Main.vwxGUI.SearchDetails import SearchDetailsPanel
from Tribler.Main.vwxGUI.LoadingDetails import LoadingDetailsPanel
from Tribler.Main.vwxGUI.standardGrid import GridState
from Tribler.Main.Utility.constants import *
from Tribler.Subscriptions.rss_client import TorrentFeedThread
from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue

from Tribler.Main.vwxGUI.TriblerStyles import TriblerStyles


from Tribler.Core.Utilities.unicode import *

from threading import Thread,currentThread
from time import time
import web2

from font import *


OVERVIEW_MODES = ['startpageMode','basicMode', 'statsMode', 'resultsMode', 'filesMode', 'settingsMode', 'personsMode', 'profileMode', 'friendsMode', 'subscriptionsMode',
                  'messageMode', 'libraryMode', 'itemdetailsMode', 'fileDetailsMode','playlistMode', 'personDetailsMode', 'playlistMode']
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

DEBUG = False

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
#        print 'standardOverview'
        self.Unbind(wx.EVT_WINDOW_CREATE)
        wx.CallAfter(self._PostInit)
        event.Skip()
        return True
    
    def _PostInit(self):
        # Do all init here
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility
        self.categorykey = None
      
        self.triblerStyles = TriblerStyles.getInstance()

        self.search_results = self.guiUtility.frame.top_bg.search_results
        self.results = {}
        
#        self.SetBackgroundColour((255,255,90))
        
        
#        self.Bind(wx.EVT_SIZE, self.standardOverviewResize)
        self.mode = None        
        self.selectedTorrent = None
        self.selectedPeer = None
        self.data = {} #keeps gui elements for each mode
        for mode in OVERVIEW_MODES:
            self.data[mode] = {} #each mode has a dictionary of gui elements with name and reference
        self.currentPanel = None
        self.addComponents()
        #self.Refresh()
        
#        self.guiUtility.frame.Bind(wx.EVT_SIZE, self.standardOverviewResize())
#        self.Bind(wx.EVT_SIZE, self.standardOverviewResize)

        print >>sys.stderr,"standardOverview: __init__: Setting GUIUtil"
        self.guiUtility.initStandardOverview(self)    # show file panel
        #self.toggleLoadingDetailsPanel(True)
        
        #print >> sys.stderr, '[StartUpDebug]----------- standardOverview is in postinit ----------', currentThread().getName(), '\n\n'
        
        
    def addComponents(self):
        self.hSizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.hSizer)
        self.SetAutoLayout(1)
        self.Layout()

                    
    def standardOverviewResize(self, event=None):
#        self.SetAutoLayout(0) 
#        self.SetSize((-1,(self.guiUtility.frame.GetSize()[1]-200)))
#        self.SetWindowStyleFlag(wx)
#        self.Layout()
#        self.currentPanel.SetSize((-1, (self.GetSize()[1]-250)))
#        print 'tb > standardOverviewResize Resize'     
#        print self.currentPanel.GetSize()
#        self.SetSize((-1, 1000))
#        

#        print self.GetSize() 
        if event:
            event.Skip()
        
        self.SetAutoLayout(1)
        self.Layout()
        
    def setMode(self, mode, refreshGrid=True):
        # switch to another view, 
        # mode is one of the [filesMode, personsMode, friendsMode, profileMode, libraryMode, subscriptionsMode]
        if self.mode != mode or mode == 'fileDetailsMode' or mode == 'playlistMode':
            #self.stopWeb2Search()
            self.mode = mode
            self.refreshMode(refreshGrid=refreshGrid)
            
    def getMode(self):
        return self.mode
        
        self.guiUtility.filterStandard.SetData(self.mode)
            
    def refreshMode(self,refreshGrid=True):
        # load xrc
        self.oldpanel = self.currentPanel   
        
        self.currentPanel = self.loadPanel()

        print >> sys.stderr , 'self.oldpanel' , self.oldpanel
        print >> sys.stderr , 'self.currentPanel' , self.currentPanel



        assert self.currentPanel, "standardOverview: Panel could not be loaded"
        #self.currentPanel.GetSizer().Layout()
        #self.currentPanel.Enable(True)
        self.currentPanel.Show(True)
        if self.data[self.mode].get('grid') and refreshGrid:
            self.data[self.mode]['grid'].gridManager.reactivate()
        
        if self.oldpanel and self.oldpanel != self.currentPanel:
            self.hSizer.Detach(self.oldpanel)
            self.oldpanel.Hide()
            #self.oldpanel.Disable()

        assert len(self.hSizer.GetChildren()) == 0, 'Error: standardOverview self.hSizer has old-panel and gets new panel added (2 panel bug). Old panels are: %s' % self.hSizer.GetChildren()
            
        #if self.oldpanel != self.currentPanel: 
        #    self.hSizer.Add(self.currentPanel, 1, wx.ALL|wx.EXPAND, 0)   
        
        nameCP = self.currentPanel.GetName()
        if nameCP == 'profileOverview': 
            sizeCP = self.currentPanel.GetSize()
            sizeFrame = self.Parent.GetSize()
            
            heightCP = max(sizeCP[1], sizeFrame[1])
#            print 'heightCP = %s' % heightCP
            self.SetSize((-1, heightCP))        
            self.SetMinSize((500,sizeCP[1]))
        elif nameCP == 'settingsOverview':
            self.SetMinSize((900,500))
        else:
            self.SetMinSize((600,500)) ## before (10,400)

        self.hSizer.Layout()
        

        wx.CallAfter(self.Parent.Layout)
        if DEBUG:
            print >> sys.stderr, 'standardOverview: refreshMode: %s' % self.currentPanel.__class__.__name__
        wx.CallAfter(self.hSizer.Layout)
        wx.CallAfter(self.currentPanel.Layout)
        wx.CallAfter(self.currentPanel.Refresh)

        wx.CallAfter(self.guiUtility.scrollWindow.FitInside)
#        self.guiUtility.scrollWindow.FitInside()        

    def setPager(self, pager): ## added
        if DEBUG:
            print >>sys.stderr,'standardOverview: setPager called: %s' % pager
        self.standardPager = pager

    def lloadPanel(self):        
        currentPanel = self.data[self.mode].get('panel',None)

        modeString = self.mode[:-4]
        if DEBUG:
            print >>sys.stderr,'standardOverview: loadPanel: modeString='+modeString
        if not currentPanel:
            xrcResource = os.path.join(self.utility.getPath(),'Tribler','Main','vwxGUI', modeString+'Overview.xrc')
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
                    dummyFile = os.path.join(self.utility.getPath(),'Tribler','Main','vwxGUI', 'dummyOverview.xrc')
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
                
                if pager is not None:                            
                    pager.setGrid(grid)
                
                if self.mode in ['filesMode', 'personsMode']: 
                    print ''
                   
#                    print 'self.mode = %s' % self.mode  
#                    print currentPanel         
##                    self.standardOverview.data['filesMode'].get('grid')
##                    currentViewMode = currentPanel.grid.viewmode             
##                    currentPanel.viewModeSelect = xrc.XRCCTRL(currentPanel, 'modeItems')
###                    overviewSizeSelect = xrc.XRCCTRL(currentPanel, 'numberItems')                    
                    # set default values
                    
#                    self.mode.viewModeSelect = viewModeSelect

#                    currentPanel.viewModeSelect.Select(1) #SetValue('thumbnails')
                    ##overviewSizeSelect.Select(0) #SetValue('auto')
                    #viewModeSelect.Bind(wx.EVT_COMBOBOX, grid.onViewModeChange)
#                    currentPanel.viewModeSelect.Bind(wx.EVT_CHOICE, grid.onViewModeChange(mode = 'filesMode'))
                    #overviewSizeSelect.Bind(wx.EVT_COMBOBOX, grid.onSizeChange)
                    ##overviewSizeSelect.Bind(wx.EVT_CHOICE, grid.onSizeChange)
                    
                    
                    
                    
                if self.mode == 'subscriptionsMode':
                    rssurlctrl = xrc.XRCCTRL(currentPanel,'pasteUrl')
                    rssurlctrl.Bind(wx.EVT_KEY_DOWN, self.guiUtility.OnSubscribeKeyDown)
                    rssurlctrl.Bind(wx.EVT_LEFT_UP, self.guiUtility.OnSubscribeMouseAction)
                    txt = self.utility.lang.get('rssurldefaulttxt')
                    rssurlctrl.SetValue(txt)                
                    self.data[self.mode]['rssurlctrl'] = rssurlctrl
                    
                if self.mode == 'basicMode':    
                    # header styling
#                    self.data['status']['downSpeed']
                    
#                    self.data[mode][name] = xrcElement
                    self.searchCentre = xrc.XRCCTRL(currentPanel, 'searchFieldCentre')
                    ##self.triblerStyles.titleBar(xrc.XRCCTRL(currentPanel,'popVideosPanel'))
                    ##self.triblerStyles.titleBar(xrc.XRCCTRL(currentPanel,'popVideos'))
                    ##self.triblerStyles.titleBar(xrc.XRCCTRL(currentPanel,'popChannelsPanel'))
                    ##self.triblerStyles.titleBar(xrc.XRCCTRL(currentPanel,'popChannels'))
#                    self.triblerStyles.titleBar(self.data['status']['Downloading']) 
#                    self.triblerStyles.titleBar(self.data['status']['down_White']) 
#                    self.triblerStyles.titleBar(self.data['status']['downSpeed']) 
#                    self.triblerStyles.titleBar(self.data['status']['up_White'])                 
#                    self.triblerStyles.titleBar(self.data['status']['upSpeed']) 
#                    # content styling
#                    self.triblerStyles.setDarkText(self.data['status']['download1']) 
#                    self.triblerStyles.setDarkText(self.data['status']['percent1']) 
#                    self.triblerStyles.setDarkText(self.data['status']['download2']) 
#                    self.triblerStyles.setDarkText(self.data['status']['percent2']) 
#                    self.triblerStyles.setDarkText(self.data['status']['download3']) 
#                    self.triblerStyles.setDarkText(self.data['status']['percent3']) 
#                    self.triblerStyles.setDarkText(self.data['status']['download4']) 
#                    self.triblerStyles.setDarkText(self.data['status']['percent4']) 
        
            except:
                if DEBUG:
                    print >>sys.stderr,'standardOverview: Error: Could not load panel, grid and pager for mode %s' % self.mode
                    print >>sys.stderr,'standardOverview: Tried panel: %s=%s, grid: %s=%s, pager: %s=%s' % (panelName, currentPanel, modeString+'Grid', grid, 'standardPager', pager)
                print_exc()                
        
        
        if self.mode in ['filesMode', 'personsMode']:
            grid = self.data[self.mode].get('grid') 
            if self.guiUtility.gridViewMode != grid.viewmode :
                grid.onViewModeChange(mode=self.guiUtility.gridViewMode)
                
                  
                
        if self.mode == 'fileDetailsMode':
            print 'tb > fileDetailsMode'
            self.data[self.mode]['panel'].setData(self.selectedTorrent)
            
        if self.mode == 'playlistMode':
            print 'tb > playlistMode'
            self.data[self.mode]['panel'].setData(self.selectedTorrent)
        
        if self.mode == 'personDetailsMode':
            self.data[self.mode]['panel'].setData(self.selectedPeer)

        return currentPanel




        
    def loadPanel(self):        
        currentPanel = self.data[self.mode].get('panel',None)
        print >> sys.stderr, 'currentPanel' , currentPanel
        modeString = self.mode[:-4]
        print >> sys.stderr, 'modestring' , modeString
        if DEBUG:
            print >>sys.stderr,'standardOverview: loadPanel: modeString='+modeString,'currentPanel:',currentPanel

        xrcResource = os.path.join(self.guiUtility.vwxGUI_path, modeString+'Overview.xrc')
        panelName = modeString+'Overview'
        res = xrc.XmlResource(xrcResource)
        currentPanel = res.LoadPanel(self, panelName)
        grid = xrc.XRCCTRL(currentPanel, modeString+'Grid')    
        pager = xrc.XRCCTRL(self.guiUtility.frame, 'standardPager')    # Jie:not really used for profile, rss and library?
            
        self.data[self.mode]['panel'] = currentPanel
        self.data[self.mode]['grid'] = grid
        self.data[self.mode]['pager'] = pager

        if pager is not None:                            
            pager.setGrid(grid)

        if self.mode == 'settingsMode':
            self.firewallStatus = xrc.XRCCTRL(currentPanel,'firewallStatus')
            
            ##if self.guiUtility.isReachable():
            ##    self.firewallStatus.setToggled(True)
            ##    self.firewallStatus.Refresh()
            ##    print >> sys.stderr , "OK"
            ##else:
            ##    self.firewallStatus.setToggled(False)
            ##self.Refresh()



        # create the panel for the first click. panel could be one of the [file,person,friend,library,profile,rss]
        if not currentPanel:
            #xrcResource = os.path.join(self.guiUtility.vwxGUI_path, modeString+'Overview.xrc')
            #panelName = modeString+'Overview'
            try:
                #currentPanel = grid = pager = None
                #res = xrc.XmlResource(xrcResource)
                # create panel
                #currentPanel = res.LoadPanel(self, panelName)
                #grid = xrc.XRCCTRL(currentPanel, modeString+'Grid')    
                #pager = xrc.XRCCTRL(self.guiUtility.frame, 'standardPager')    # Jie:not really used for profile, rss and library?
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
                #self.data[self.mode]['grid'] = grid
                #self.data[self.mode]['pager'] = pager
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
                
                if pager is not None:                            
                    pager.setGrid(grid)
                
                if self.mode in ['filesMode', 'personsMode']: 
                    print ''
                   
#                    print 'self.mode = %s' % self.mode  
#                    print currentPanel         
##                    self.standardOverview.data['filesMode'].get('grid')
##                    currentViewMode = currentPanel.grid.viewmode             
##                    currentPanel.viewModeSelect = xrc.XRCCTRL(currentPanel, 'modeItems')
###                    overviewSizeSelect = xrc.XRCCTRL(currentPanel, 'numberItems')                    
                    # set default values
                    
#                    self.mode.viewModeSelect = viewModeSelect

#                    currentPanel.viewModeSelect.Select(1) #SetValue('thumbnails')
                    ##overviewSizeSelect.Select(0) #SetValue('auto')
                    #viewModeSelect.Bind(wx.EVT_COMBOBOX, grid.onViewModeChange)
#                    currentPanel.viewModeSelect.Bind(wx.EVT_CHOICE, grid.onViewModeChange(mode = 'filesMode'))
                    #overviewSizeSelect.Bind(wx.EVT_COMBOBOX, grid.onSizeChange)
                    ##overviewSizeSelect.Bind(wx.EVT_CHOICE, grid.onSizeChange)
                    
                    
                    
                    
                if self.mode == 'subscriptionsMode':
                    rssurlctrl = xrc.XRCCTRL(currentPanel,'pasteUrl')
                    rssurlctrl.Bind(wx.EVT_KEY_DOWN, self.guiUtility.OnSubscribeKeyDown)
                    rssurlctrl.Bind(wx.EVT_LEFT_UP, self.guiUtility.OnSubscribeMouseAction)
                    txt = self.utility.lang.get('rssurldefaulttxt')
                    rssurlctrl.SetValue(txt)                
                    self.data[self.mode]['rssurlctrl'] = rssurlctrl
                    
                if self.mode == 'basicMode':    
                    # header styling
#                    self.data['status']['downSpeed']
                    
#                    self.data[mode][name] = xrcElement


                    self.searchCentre = xrc.XRCCTRL(currentPanel, 'searchFieldCentre')
                    self.triblerStyles.titleBar(xrc.XRCCTRL(currentPanel,'popVideosPanel'))
                    self.triblerStyles.titleBar(xrc.XRCCTRL(currentPanel,'popVideos'))
                    self.triblerStyles.titleBar(xrc.XRCCTRL(currentPanel,'popChannelsPanel'))
                    self.triblerStyles.titleBar(xrc.XRCCTRL(currentPanel,'popChannels'))
#                    self.triblerStyles.titleBar(self.data['status']['Downloading']) 
#                    self.triblerStyles.titleBar(self.data['status']['down_White']) 
#                    self.triblerStyles.titleBar(self.data['status']['downSpeed']) 
#                    self.triblerStyles.titleBar(self.data['status']['up_White'])                 
#                    self.triblerStyles.titleBar(self.data['status']['upSpeed']) 
#                    # content styling
#                    self.triblerStyles.setDarkText(self.data['status']['download1']) 
#                    self.triblerStyles.setDarkText(self.data['status']['percent1']) 
#                    self.triblerStyles.setDarkText(self.data['status']['download2']) 
#                    self.triblerStyles.setDarkText(self.data['status']['percent2']) 
#                    self.triblerStyles.setDarkText(self.data['status']['download3']) 
#                    self.triblerStyles.setDarkText(self.data['status']['percent3']) 
#                    self.triblerStyles.setDarkText(self.data['status']['download4']) 
#                    self.triblerStyles.setDarkText(self.data['status']['percent4']) 

        
            except:
                if DEBUG:
                    print >>sys.stderr,'standardOverview: Error: Could not load panel, grid and pager for mode %s' % self.mode
                    print >>sys.stderr,'standardOverview: Tried panel: %s=%s, grid: %s=%s, pager: %s=%s' % (panelName, currentPanel, modeString+'Grid', grid, 'standardPager', pager)
                print_exc()                
        
        
        if self.mode in ['filesMode', 'personsMode']:
            grid = self.data[self.mode].get('grid') 
            if self.guiUtility.gridViewMode != grid.viewmode :
                grid.onViewModeChange(mode=self.guiUtility.gridViewMode)
                
                  
                
        if self.mode == 'fileDetailsMode':
            print 'tb > fileDetailsMode'
            self.data[self.mode]['panel'].setData(self.selectedTorrent)
            
        if self.mode == 'playlistMode':
            print 'tb > playlistMode'
            self.data[self.mode]['panel'].setData(self.selectedTorrent)
        
        if self.mode == 'personDetailsMode':
            self.data[self.mode]['panel'].setData(self.selectedPeer)

        return currentPanel
     
    def refreshData(self):        
        if DEBUG:
            print >>sys.stderr,"standardOverview: refreshData"
            #print_stack()
            
        grid = self.data[self.mode].get('grid')
        if grid:
            
            if DEBUG:
                data = self.data[self.mode].get('data')
                if type(data) == list:
                    print >>sys.stderr,"standardOverview: refreshData: refreshing",len(data)
            
            # load and show the data in the grid
            grid.setData(self.data[self.mode].get('data'))

    def refreshGridManager(self):        
        if DEBUG:
            print >>sys.stderr,"standardOverview: refreshGridManager"
            #print_stack()
            
        try:
            grid = self.data[self.mode].get('grid')
            if grid:
                gridmgr = grid.getGridManager().refresh()
        except:
            print_exc()
        
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
        


    def filterChanged(self, filterState):
        """ filterState is GridState object """
        if DEBUG:
            print >>sys.stderr,"standardOverview: filterChanged",filterState,self.mode#,self.data[self.mode]
        
        assert filterState is None or 'GridState' in str(type(filterState)), 'filterState is %s' % str(filterState)
        oldFilterState = self.data[self.mode].get('filterState')
        
#        print 'tb >FILTERCHANGED!!!!!'
        if DEBUG:
            print >>sys.stderr,"standardOverview: filterChanged: from",oldFilterState,"to",filterState
        
        if filterState:
            filterState.setDefault(oldFilterState)
            
        #if filterState.db == 'libraryMode':
        #    print >> sys.stderr, 'standardOverview: ********************** VALID LIBRARY Filterstate:', filterState
            
        if filterState and filterState.isValid():
            if self.mode in ('filesMode', 'personsMode', 'libraryMode', 'friendsMode','settingsMode'):
                #self.loadTorrentData(filterState[0], filterState[1])
                self.data[filterState.db]['grid'].gridManager.set_state(filterState)
                pass
            elif self.mode in ('subscriptionsMode'):
                self.loadSubscriptionData()
                self.refreshData()
#        if DEBUG:
#            print >> sys.stderr, 'standardOverview: filterstate: %s' % filterState
            
            else:
                if DEBUG:
                    print >>sys.stderr,'standardOverview: Filters not yet implemented in this mode'
                return
                            
            if DEBUG:
                print >>sys.stderr,"standardOverview: before refreshData"
                
    
          
            #self.refreshData()
            self.data[self.mode]['filterState'] = filterState
            
       
        else:
            print >> sys.stderr, 'standardOverview: Invalid Filterstate:', filterState
            #print_stack()    
    

    def loadSubscriptionData(self):
        if DEBUG:
            print >> sys.stderr, 'load subscription data'
            
        torrentfeed = TorrentFeedThread.getInstance()
        urls = torrentfeed.getURLs()
        
        bcsub = self.utility.lang.get('buddycastsubscription')
        web2sub = self.utility.lang.get('web2subscription')
        
        bcactive = self.utility.session.get_buddycast() and self.utility.session.get_start_recommender()
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
        self.data[self.mode]['grid'].setData(reclist)
        
   
   
    
    def getSearchField(self,mode=None):
        if mode is None:
            mode = self.mode
        return self.data[mode]['search']
    
    def getGrid(self):
        return self.data.get(self.mode, {}).get('grid')
    
        
    def getSorting(self):
        fs = self.data[self.mode].get('filterState')
        if fs:
            return fs.sort
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
        #print >>sys.stderr,'standardOverview: setSearchFeedback',args,kwargs
        setSearchFeedback_lambda = lambda:self._setSearchFeedback(*args,**kwargs)
        wx.CallAfter(setSearchFeedback_lambda)
        
    def getSearchBusy(self):
        searchDetailsPanel = self.data[self.mode].get('searchDetailsPanel')
        if searchDetailsPanel:
            return searchDetailsPanel.searchBusy
        else:
            return False
    def _setSearchFeedback(self, type, finished, num, keywords = [], searchresults = None):
        #print 'standardOverview: _setSearchFeedback called by', currentThread().getName()

        self.setMessage(type, finished, num, keywords)


        ##searchDetailsPanel = self.data[self.mode].get('searchDetailsPanel')
        ##if searchDetailsPanel:
        ##    searchDetailsPanel.setMessage(type, finished, num, searchresults, keywords)

    def setMessage(self, stype, finished, num, keywords = []):
        if stype:
            self.results[stype] = num # FIXME different remote search overwrite eachother
        
        total = sum([v for v in self.results.values() if v != -1])
        #if total > 30:
        #    finished = True
        if keywords:
            if type(keywords) == list:
                self.keywords = " ".join(keywords)
            else:
                self.keywords = keywords

        if finished:  
            msg = self.guiUtility.utility.lang.get('finished_search') % (self.keywords, total)
            self.guiUtility.stopSearch()
            #self.searchFinished(set_message=False)
        else:
            msg = self.guiUtility.utility.lang.get('going_search') % (total)

        self.search_results.SetFont(wx.Font(FS_FILETITLE,FONTFAMILY,FONTWEIGHT,wx.NORMAL,True,FONTFACE))
        if self.mode not in ['filesMode']:
            self.search_results.SetForegroundColour(wx.RED)
        else:
            self.search_results.SetForegroundColour(wx.BLACK)
 
        if self.mode in ['filesMode']:
            self.search_results.SetLabel(msg)    
        else:
            self.search_results.SetLabel('Return to Results')    
  
        
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
        infohash = torrent['infohash']
        guiserver = GUITaskQueue.getInstance()
        
        mypreference_db = self.utility.session.open_dbhandler(NTFY_MYPREFERENCES)
        # LAYERVIOLATION LAYERVIOLATION
        # ARNO50: Implement this via Notifier: we remove from DB, BuddyCast
        # listens to notifies.
        from Tribler.Core.BuddyCast.buddycast import BuddyCastFactory
        bc = BuddyCastFactory.getInstance()
        if bc.registered:
            bc.overlay_bridge.add_task(lambda:bc.delMyPref(infohash))
        mypreference_db.deletePreference(infohash)
        
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
        
           
        
    
