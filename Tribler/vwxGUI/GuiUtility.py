import wx
from wx import xrc
from bgPanel import *
import updateXRC
from Tribler.TrackerChecking.ManualChecking import SingleManualChecking

#from Tribler.vwxGUI.filesFilter import filesFilter

from Tribler.Dialogs.abcfileframe import TorrentDataManager
from peermanager import PeerDataManager
from Tribler.utilities import *

DEBUG = True

class GUIUtility:
    __single = None

    def __init__(self, utility = None, params = None):
        if GUIUtility.__single:
            raise RuntimeError, "GUIUtility is singleton"
        GUIUtility.__single = self 
        # do other init
        
        self.guiObjects = {}
        self.xrcResource = None
        self.type = 'swarmsize'
        self.filesFilter1 = None
        self.filesFilter2 = None
        self.utility = utility
        self.params = params
        self.data_manager = TorrentDataManager.getInstance(self.utility)
        self.data_manager.register(self.updateFun, 'all')
        self.peer_manager = PeerDataManager.getInstance() #the updateFunc is called after the data is updated in the peer manager so that the GUI has the newest information
        self.peer_manager.register(self.updateFun, 'all')
        self.selectedMainButton = None
        self.isReachable = False #reachability flag / port forwarding enabled / accessible from the internet
            
    def getInstance(*args, **kw):
        if GUIUtility.__single is None:
            GUIUtility(*args, **kw)
        return GUIUtility.__single
    getInstance = staticmethod(getInstance)
    
    
    def setCategory(self, cat, sort):
        print 'Category set to %s' % cat            
        self.categorykey = cat
        self.type = sort
        return self.reloadData()
        
    def buttonClicked(self, event):
        "One of the buttons in the GUI has been clicked"
        
        if DEBUG:
            print 'Button clicked'

        event.Skip(True) #should let other handlers use this event!!!!!!!
            
        obj = event.GetEventObject()
        try:
            name = obj.GetName()
        except:
            print 'Error: Could not get name of buttonObject: %s' % obj
        
        if name.startswith('mainButton'):
            self.mainButtonClicked(name, obj)
        elif name.lower().find('detailstab') > -1:
            self.detailsTabClicked(name)
        elif name == 'refresh':
            self.refreshTracker()
        elif name == "addAsFriend":
            self.standardDetails.addAsFriend()
        elif name == 'download':
            self.standardDetails.download()
        elif name.startswith('bgPanel') and obj.GetParent().GetName() == "profileOverview":
            self.standardOverview.currentPanel.sendClick(event)
            self.detailsTabClicked(name) #a panel was clicked in the profile overview and this is the most elegant so far method of informing the others
        else:
            print 'A button was clicked, but no action is defined for: %s' % name
                
        
    def mainButtonClicked(self, name, button):
        "One of the mainbuttons in the top has been clicked"
        
        if not button.isSelected():
            if self.selectedMainButton:
                self.selectedMainButton.setSelected(False)
            button.setSelected(True)
            self.selectedMainButton = button

        
        if name == 'mainButtonFiles':
            self.standardFilesOverview()
        elif name == 'mainButtonPersons':
            self.standardPersonsOverview()
        elif name == 'mainButtonProfile':
            self.standardProfileOverview()
        elif name == 'mainButtonLibrary':
            self.standardLibraryOverview()
        elif name == 'mainButtonFriends':
            self.standardFriendsOverview()
        elif name == 'mainButtonRss':
            self.standardSubscriptionsOverview()
        elif name == 'mainButtonMessages':
            self.standardMessagesOverview()
            
    def standardFilesOverview(self, filter1String = "", filter2String = ""):        
        #self.categorykey = 'all'
        print 'Files > filter1String='+filter1String
        print 'Files > filter2String='+filter2String
        #if filesFilter1:
        if filter1String == "" :
            filter1String = self.filesFilter1
        if filter2String == "" :
            filter2String = self.filesFilter2
        else:    
            self.filesFilter1 = filter1String
            self.filesFilter2 = filter2String
        
        torrentList = self.setCategory(filter1String, filter2String)        
        #self.categorykey = 'all'
        torrentList = self.reloadData()
        self.standardOverview.setMode('filesMode', filter1String, filter2String, torrentList)
        try:
            if self.standardDetails:
                self.standardDetails.setMode('filesMode', None)
        except:
            pass
        
    def standardPersonsOverview(self, filter1String = "", filter2String = ""):
        self.categorykey = self.utility.lang.get('mypref_list_title')
        personsList = self.reloadPeers()
        self.standardOverview.setMode('personsMode', filter1String, filter2String, personsList)
        self.standardDetails.setMode('personsMode')
        
    def standardFriendsOverview(self):
        self.categorykey = "friends"
        friendsList = self.reloadPeers()
        self.standardOverview.setMode('friendsMode', '', '', friendsList)
        self.standardDetails.setMode('personsMode')
    
    def standardProfileOverview(self):
        #profileList = self.reloadData()
        profileList = []
        self.standardOverview.setMode('profileMode', '','', profileList)
        self.standardDetails.setMode('profileMode')
        
    def standardLibraryOverview(self, filter1String="audio", filter2String="swarmsize"):       
        print 'Library > filter1String='+filter1String 
        libraryList = self.loadLibrary()
        self.standardOverview.setMode('libraryMode', filter1String, filter2String, libraryList)        
        self.standardDetails.setMode('libraryMode')
        
    def standardSubscriptionsOverview(self, filter1String="audio", filter2String="swarmsize"):       
        subscriptionsList = self.reloadData()         
        self.standardOverview.setMode('subscriptionsMode', filter1String, filter2String, subscriptionsList)        
        self.standardDetails.setMode('subscriptionsMode')
         
    def standardMessagesOverview(self):
        messagesList = self.reloadData()
        #self.standardOverview.setMode('messagesMode', messagesList)       
         
    def reloadData(self):
        # load content category
        #self.categorykey = 'all'
        self.data = self.data_manager.getCategory(self.categorykey)
        self.filtered = []
        for torrent in self.data:
            if torrent.get('status') == 'good' or torrent.get('myDownloadHistory'):
                self.filtered.append(torrent)
        
        self.filtered = sort_dictlist(self.filtered, self.type, 'decrease')
        
        return self.filtered
            
    def reloadPeers(self):
        return self.peer_manager.sortData(self.categorykey)
    
    def loadLibrary(self):
        # Get infohashes of current downloads
        activeInfohashes = {}
        active = []
        inactive = []
        for torrent in self.utility.torrents['active']:
            activeInfohashes[torrent.torrent_hash] = torrent
            
        self.categorykey = self.utility.lang.get('mypref_list_title')
        libraryList = self.reloadData()
        for torrent in libraryList:
            infohash = torrent.get('infohash')
            if infohash in activeInfohashes:
                active.append(torrent)
                torrent['abctorrent'] = activeInfohashes[infohash]
            else:
                inactive.append(torrent)
        
        return active+inactive
        
    def updateFun(self, torrent, operate):    
        print "Updatefun called"
        
    def initStandardOverview(self, standardOverview):
        "Called by standardOverview when ready with init"
        self.standardOverview = standardOverview
        self.standardFilesOverview('video', 'swarmsize')

        # Preselect mainButtonFiles
        filesButton = xrc.XRCCTRL(self.frame, 'mainButtonFiles')
        filesButton.setSelected(True)
        self.selectedMainButton = filesButton 
     
    def getOverviewElement(self):
        """should get the last selected item for the current standard overview, or
        the first one if none was previously selected"""
        firstItem = self.standardOverview.getFirstItem()
        return firstItem
        
    def initStandardDetails(self, standardDetails):
        "Called by standardDetails when ready with init"
        self.standardDetails = standardDetails
        firstItem = self.standardOverview.getFirstItem()
        self.standardDetails.setMode('filesMode', firstItem)
        self.standardDetails.refreshStatusPanel(True)    
        
    def deleteTorrent(self, torrent):
        pass
    
    def selectData(self, data):
        "User clicked on item. Has to be selected in detailPanel"
        self.standardDetails.setData(data)
        self.standardOverview.updateSelection()
        
    def selectTorrent(self, torrent):
        "User clicked on torrent. Has to be selected in detailPanel"
        self.standardDetails.setData(torrent)
        self.standardOverview.updateSelection()

    def selectPeer(self, peer_data):
        "User clicked on peer. Has to be selected in detailPanel"
        self.standardDetails.setData(peer_data)
        self.standardOverview.updateSelection()
            
    def detailsTabClicked(self, name):
        "A tab in the detailsPanel was clicked"
        self.standardDetails.tabClicked(name)
        
    def refreshOnResize(self):
        try:
            #if DEBUG:
            #    print'GuiUtility: explicit refresh'
            self.standardDetails.Refresh()
            self.standardOverview.Refresh()
            self.frame.topBackgroundRight.Refresh()
        except:
            pass # When resize is done before panels are loaded: no refresh
        
    def refreshTracker(self):
        torrent = self.standardDetails.getData()
        if DEBUG:
            print >>sys.stderr,'GUIUtility: refresh ' + repr(torrent.get('content_name', 'no_name'))
        if torrent:
            check = SingleManualChecking(torrent)
            check.start()
            
    def refreshTorrentStats(self):
        "Called from launchmanycore to refresh statistics of downloading torrents"
        try:
            self.standardOverview.refreshTorrentStats()
        except:
            print 'GuiUtility: Error refreshing stats'
    