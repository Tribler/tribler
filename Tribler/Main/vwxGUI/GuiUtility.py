# Written by Jelle Roozenburg, Maarten ten Brinke, Arno Bakker, Lucian Musat 
# see LICENSE.txt for license information

import wx, time, random, os
from wx import xrc
from traceback import print_exc,print_stack
from threading import Event, Thread
import urllib,urllib2
import webbrowser
from sets import Set
from webbrowser import open_new

from Tribler.Core.simpledefs import *
from Tribler.Core.Utilities.utilities import *
from Tribler.Core.Utilities.unicode import dunno2unicode

from Tribler.Core.NATFirewall.DialbackMsgHandler import DialbackMsgHandler
from Tribler.TrackerChecking.TorrentChecking import TorrentChecking
from Tribler.Subscriptions.rss_client import TorrentFeedThread
from Tribler.Category.Category import Category
from Tribler.Main.Dialogs.makefriends import MakeFriendsDialog, InviteFriendsDialog
from Tribler.Main.vwxGUI.bgPanel import *
from Tribler.Main.vwxGUI.GridState import GridState
from Tribler.Main.vwxGUI.SearchGridManager import TorrentSearchGridManager,PeerSearchGridManager
from Tribler.Main.Utility.constants import *

from Tribler.Core.CacheDB.sqlitecachedb import bin2str

from Tribler.Video.VideoPlayer import VideoPlayer,return_feasible_playback_modes,PLAYBACKMODE_INTERNAL



DEBUG = True

class GUIUtility:
    __single = None
    
    def __init__(self, utility = None, params = None):
        if GUIUtility.__single:
            raise RuntimeError, "GUIUtility is singleton"
        GUIUtility.__single = self 
        # do other init
        self.xrcResource = None
        self.utility = utility
        self.vwxGUI_path = os.path.join(utility.abcpath, 'Tribler', 'Main', 'vwxGUI')
        self.utility.guiUtility = self
        self.params = params
        self.frame = None
        self.selectedMainButton = None
        self.standardOverview = None
        self.reachable = False

        # Moderation cast
        self.moderatedinfohash = None
        self.modcast_db = None 
        self.fakeButton = None
        self.realButton = None

        # videoplayer
        self.videoplayer = VideoPlayer.getInstance()

        # current GUI page
        self.guiPage = None

        # standardGrid
        self.standardGrid = None
 

        # port number
        self.port_number = None




        # Arno: 2008-04-16: I want to keep this for searching, as an extension
        # of the standardGrid.GridManager
        self.torrentsearch_manager = TorrentSearchGridManager.getInstance(self)
        self.peersearch_manager = PeerSearchGridManager.getInstance(self)
        
        self.guiOpen = Event()
        
       
        self.gridViewMode = 'thumbnails' 
        self.thumbnailViewer = None
#        self.standardOverview = standardOverview()
        
        self.selectedColour = wx.Colour(216,233,240) ## 155,200,187
        self.unselectedColour = wx.Colour(255,255,255) ## 102,102,102      
        self.unselectedColour2 = wx.Colour(255,255,255) ## 230,230,230       
        self.unselectedColourDownload = wx.Colour(198,226,147)        
        self.unselectedColour2Download = wx.Colour(190,209,139)
        self.selectedColourDownload = wx.Colour(145,173,78)
        self.selectedColourPending = wx.Colour(216,233,240)  ## 208,251,244
        self.triblerRed = wx.Colour(255, 51, 0)
        self.bgColour = wx.Colour(102,102,102)
        self.darkTextColour = wx.Colour(51,51,51)
        
        self.max_remote_queries = 10    # max number of remote peers to query
        self.remote_search_threshold = 20    # start remote search when results is less than this number

    
    def getInstance(*args, **kw):
        if GUIUtility.__single is None:
            GUIUtility(*args, **kw)
        return GUIUtility.__single
    getInstance = staticmethod(getInstance)

    def open_dbs(self):
        self.modcast_db = self.utility.session.open_dbhandler(NTFY_MODERATIONCAST)
        
    def buttonClicked(self, event):
        "One of the buttons in the GUI has been clicked"
        self.frame.SetFocus()

        event.Skip(True) #should let other handlers use this event!!!!!!!
            
        name = ""
        obj = event.GetEventObject()
        
        print 'tb > name of object that is clicked = %s' % obj.GetName()

        try:
            name = obj.GetName()
        except:
            print >>sys.stderr,'GUIUtil: Error: Could not get name of buttonObject: %s' % obj
        
        if DEBUG:
            print >>sys.stderr,'GUIUtil: Button clicked %s' % name
            #print_stack()
        
        
        if name == 'moreFileInfo':
            self.standardFileDetailsOverview()
        elif name == 'moreFileInfoPlaylist':
            self.standardFileDetailsOverview()
#            self.standardPlaylistOverview()
        elif name == 'more info >': 
            self.standardPersonDetailsOverview()                      
        elif name == 'backButton':            
            self.standardStartpage() 
            
        elif name == 'All popular files':            
            self.standardFilesOverview()  ##
            
        elif name == 'viewThumbs' or name == 'viewList':
#            print 'currentpanel = %s' % self.standardOverview.currentPanel.GetName()
#            self.viewThumbs = xrc.XRCCTRL(self.frame, "viewThumbs")
#            self.viewList = xrc.XRCCTRL(self.frame, "viewList")  
            
            grid = self.standardOverview.data[self.standardOverview.mode].get('grid')
            if name == 'viewThumbs':
                self.viewThumbs.setSelected(True)
                self.viewList.setSelected(False)                
                grid.onViewModeChange(mode='thumbnails')
                self.gridViewMode = 'thumbnails'
            elif name == 'viewList':
                self.viewThumbs.setSelected(False)
                self.viewList.setSelected(True)                
                grid.onViewModeChange(mode='list')               
                self.gridViewMode = 'list'

        elif name.lower().find('detailstab') > -1:
            self.detailsTabClicked(name)
        elif name == 'refresh':
            self.refreshTracker()
        elif name == "addAsFriend" or name == 'deleteFriend':
            self.standardDetails.addAsFriend()

        elif name in ('download', 'download1'): 
            self.standardDetails.download()
        elif name == 'addFriend':
            #print >>sys.stderr,"GUIUtil: buttonClicked: parent is",obj.GetParent().GetName()
            dialog = MakeFriendsDialog(obj,self.utility)
            ret = dialog.ShowModal()
            dialog.Destroy()
        elif name == 'inviteFriends':
            self.emailFriend(event)
       
            #else:
            #    print >>sys.stderr,"GUIUtil: buttonClicked: dlbooster: Torrent is None"
            
        elif (name == 'edit' or name == "top10Sharers" or name.startswith('bgPanel')) and obj.GetParent().GetName() == "profileOverview":
            self.standardOverview.currentPanel.sendClick(event)
            self.detailsTabClicked(name) #a panel was clicked in the profile overview and this is the most elegant so far method of informing the others
        elif name == "takeMeThere0" : #a button to go to preferences was clicked
            panel_name = self.standardDetails.currentPanel.GetName()
            if panel_name == "profileDetails_Files":
                #self.utility.actions[ACTION_PREFERENCES].action()
                self.utility.actions[ACTION_PREFERENCES].action(openname=self.utility.lang.get('triblersetting'))
                self.selectData(self.standardDetails.getData())
            if panel_name == "profileDetails_Download":
                #self.utility.actions[ACTION_PREFERENCES].action(openname=self.utility.lang.get('triblersetting'))
                self.utility.actions[ACTION_PREFERENCES].action(openname=self.utility.lang.get('videosetting'))
                self.selectData(self.standardDetails.getData())
            elif panel_name == "profileDetails_Presence":
                self.emailFriend(event)
                #self.mainButtonClicked( 'mainButtonPersons', self.frame.mainButtonPersons)
            #generate event to change page -> this should be done as a parameter to action because is modal
            #event = wx.TreeEvent(wx.EVT_TREE_ITEM_ACTIVATED)
            #wx.PostEvent()
        elif name == "takeMeThere1": #switch to another view
            panel_name = self.standardDetails.currentPanel.GetName()
            if panel_name == "profileDetails_Download":
                self.emailFriend(event)
                #self.mainButtonClicked( 'mainButtonPersons', self.frame.mainButtonPersons)
            if panel_name == "profileDetails_Presence": 
                URL = 'http://www.tribler.org/'
                webbrowser.open(URL)  
            else:
                print >>sys.stderr,'GUIUtil: A button was clicked, but no action is defined for: %s' % name
                
        elif name == "takeMeThere2": #switch to another view
            panel_name = self.standardDetails.currentPanel.GetName()
            if panel_name == "profileDetails_Download":
                URL = 'http://www.tribler.org/'
                webbrowser.open(URL)                
        elif name == "search": # search files/persons button
#            print 'search'
            if DEBUG:
                print >>sys.stderr,'GUIUtil: search button clicked'
            
            self.standardFilesOverview()
            self.dosearch()
        elif name == 'subscribe':
            self.subscribe()
        elif name == 'firewallStatus':
            self.firewallStatusClick()
        elif name == 'options':            
            self.standardDetails.rightMouseButton(event)
        elif name == 'viewModus':            
            self.onChangeViewModus()
        elif name == 'searchClear':
            # this has to be a callafter to avoid segmentation fault
            # otherwise the panel with the event generating button is destroyed
            # in the execution of the event.
            self.clearSearch()
                        
            wx.CallAfter(self.standardOverview.toggleSearchDetailsPanel, False)
        elif name == 'familyfilter':
            catobj = Category.getInstance()
            ff_enabled = not catobj.family_filter_enabled()
            print 'Setting family filter to: %s' % ff_enabled
            catobj.set_family_filter(ff_enabled)
            self.familyButton.setToggled()
#            obj.setToggled(ff_enabled)
            for filtername in ['filesFilter', 'libraryFilter']:
                filterCombo = xrc.XRCCTRL(self.frame, filtername)
                if filterCombo:
                    filterCombo.refresh()

        elif name == 'familyFilterOn' or name == 'familyFilterOff': ## not used anymore
            if ((self.familyButtonOn.isToggled() and name == 'familyFilterOff') or
                (self.familyButtonOff.isToggled() and name == 'familyFilterOn')):

                catobj = Category.getInstance()
                ff_enabled = not catobj.family_filter_enabled()
                print 'Setting family filter to: %s' % ff_enabled
                catobj.set_family_filter(ff_enabled)
                self.familyButtonOn.setToggled()
                self.familyButtonOff.setToggled()
#                obj.setToggled(ff_enabled)
                for filtername in ['filesFilter', 'libraryFilter']:
                    filterCombo = xrc.XRCCTRL(self.frame, filtername)
                    if filterCombo:
                        filterCombo.refresh()

        elif name == 'playAdd' or name == 'play' or name == 'playAdd1' or name == 'play1':   
            playableFiles = self.standardOverview.data['fileDetailsMode']['panel'].selectedFiles[:]
            
            if name == 'play' or name == 'play1':
                self.standardDetails.addToPlaylist(name = '', add=False)
            
            for p in playableFiles:
                if p != '':
                    self.standardDetails.addToPlaylist(name = p.GetLabel(), add=True)

        elif name == 'advancedFiltering':    
            if self.filterStandard.visible:
                self.filterStandard.Hide()
                self.filterStandard.visible = False
                self.standardOverview.GetParent().Layout()
                #                self.frame.Refresh()
            else:
                self.filterStandard.Show()
                self.filterStandard.visible = True
                self.standardOverview.GetParent().Layout()
                #                self.frame.Refresh()

        elif name == 'fake':    
            self.realButton.setState(False) # disabled real button
            moderation = self.modcast_db.getModeration(bin2str(self.moderatedinfohash))
            # ARNO50: Please turn DB records into dicts. Not doing this makes
            # the whole code DB schema dependent!
            self.modcast_db.blockModerator(bin2str(moderation[0]))

        elif name == 'real':    
            self.fakeButton.setState(False) # disable fake button
            moderation = self.modcast_db.getModeration(bin2str(self.moderatedinfohash))
            self.modcast_db.forwardModerator(bin2str(moderation[0]))



        elif name == 'remove':
            self.onDeleteTorrentFromLibrary()


        elif name == 'settings':
            self.settingsOverview()


        elif name == 'my_files':
            self.standardLibraryOverview()

        elif name == 'edit':
            self.standardOverview.currentPanel.sendClick(event)
            self.detailsTabClicked(name) 

             
        elif DEBUG:
            print >> sys.stderr, 'GUIUtil: A button was clicked, but no action is defined for: %s' % name
                
        
#    def mainButtonClicked(self, name, button):
#        "One of the mainbuttons in the top has been clicked"
#        
#        if not button.isSelected():
#            if self.selectedMainButton:
#                self.selectedMainButton.setSelected(False)
#            button.setSelected(True)
#            self.selectedMainButton = button
#
#        if name == 'mainButtonStartpage':
#            self.standardStartpage()
#        if name == 'mainButtonStats':
#            self.standardStats()
#        elif name == 'mainButtonFiles':
#            self.standardFilesOverview()
#        elif name == 'mainButtonPersons':
#            self.standardPersonsOverview()
#        elif name == 'mainButtonProfile':
#            self.standardProfileOverview()
#        elif name == 'mainButtonLibrary':
#            self.standardLibraryOverview()
#        elif name == 'mainButtonFriends':
#            self.standardFriendsOverview()
#        elif name == 'mainButtonRss':
#            self.standardSubscriptionsOverview()
#        elif name == 'mainButtonFileDetails':
#            self.standardFileDetailsOverview()
##            print 'tb debug> guiUtility button press ready'
#        elif name == 'mainButtonPersonDetails':
#            self.standardPersonDetailsOverview()
#        elif name == 'mainButtonMessages':
#            self.standardMessagesOverview()
#        elif DEBUG:
#            print >>sys.stderr,"GUIUtil: MainButtonClicked: unhandled name",name
    
    def set_port_number(self, port_number):
        self.port_number = port_number

    def get_port_number(self):
        return self.port_number



    def OnResultsClicked(self):
        if self.guiPage == None:
            self.guiPage = 'search_results'
        if self.guiPage != 'search_results':
            self.guiPage = 'search_results'
            if self.frame.top_bg.ag.IsPlaying():
                self.frame.top_bg.ag.Show() 

            #self.standardGrid.deselectAll()
            #self.standardGrid.clearAllData()

            self.standardFilesOverview()
            self.frame.videoframe.show_videoframe()
            self.frame.videoparentpanel.Show()            


            self.frame.top_bg.search_results.SetForegroundColour(wx.BLACK)

            self.frame.top_bg.settings.SetForegroundColour((255,51,0))
            self.frame.top_bg.my_files.SetForegroundColour((255,51,0))

            #if self.frame.settings.isToggled():
            #    self.frame.settings.setToggled()
            #if self.frame.my_files.isToggled():
            #    self.frame.my_files.setToggled()

            self.frame.pagerPanel.Show()
        

    def toggleFamilyFilter(self):
        catobj = Category.getInstance()
        ff_enabled = not catobj.family_filter_enabled()
        print 'Setting family filter to: %s' % ff_enabled
        catobj.set_family_filter(ff_enabled)
        if ff_enabled:
            self.frame.top_bg.familyfilter.SetLabel('Family Filter:ON')
        else:
            self.frame.top_bg.familyfilter.SetLabel('Family Filter:OFF')
        #obj.setToggled(ff_enabled)
        for filtername in ['filesFilter', 'libraryFilter']:
            filterCombo = xrc.XRCCTRL(self.frame, filtername)
            if filterCombo:
                filterCombo.refresh()
        



    def standardStartpage(self, filters = ['','']):
        self.frame.pageTitle.SetLabel('START PAGE')               
        filesDetailsList = []
        self.standardOverview.setMode('startpageMode')
        ##self.frame.files_friends.Hide()
        ##self.frame.ag.Hide()
        ##self.frame.go.Hide()
        ##self.frame.search.Hide()
        ##self.standardOverview.searchCentre.SetFocus()
        ##self.standardOverview.searchCentre.Bind(wx.EVT_KEY_DOWN, self.OnSearchKeyDow)
        ##self.standardOverview.Refresh()
         
#        self.standardOverview.filterChanged(filters)
#        self.standardDetails.setMode('fileDetails') 

    def standardStats(self, filters = ['','']):
        self.frame.pageTitle.SetLabel('STATS')               
#        filesDetailsList = []
        self.standardOverview.setMode('statsMode')
            
    def standardFilesOverview(self, filters = ['','']):
        self.frame.pageTitle.SetLabel('ALL FILES')
        self.standardOverview.setMode('filesMode')
        #gridState = self.standardOverview.getFilter().getState()
        #if filters:
        #    filters[1] = 'seeder'
        #if not gridState or not gridState.isValid():
        gridState = GridState('filesMode', 'all', 'rameezmetric')

        self.standardOverview.filterChanged(gridState)
        try:
            if self.standardDetails:
                self.standardDetails.setMode('filesMode', None)
        except:
            pass
        


    def settingsOverview(self):
        if self.guiPage != 'settings':
            self.guiPage = 'settings' 
            self.frame.top_bg.ag.Hide()
            self.frame.top_bg.settings.SetForegroundColour((0,105,156))
            self.frame.top_bg.my_files.SetForegroundColour((255,51,0))

            #if self.standardGrid:
            #    self.standardGrid.deselectAll()
            #    self.standardGrid.clearAllData()

            self.frame.videoframe.hide_videoframe()
            self.frame.videoparentpanel.Hide()            

            self.frame.pagerPanel.Hide()
            if self.frame.top_bg.search_results.GetLabel() != '':
                self.frame.top_bg.search_results.SetLabel('Return to Results')
                self.frame.top_bg.search_results.SetForegroundColour(wx.RED)
            self.frame.Layout()
            self.standardOverview.setMode('settingsMode')
            #if self.standardOverview.firewallStatus.initDone == True:
            #    self.standardOverview.firewallStatus.setToggled(True)
         
        
        
    def standardPersonsOverview(self):
        self.frame.pageTitle.SetLabel('TRIBLER')
        self.standardOverview.setMode('personsMode')
        if not self.standardOverview.getSorting():
            gridState = GridState('personsMode', 'all', 'last_connected', reverse=False)
            self.standardOverview.filterChanged(gridState)
        self.standardDetails.setMode('personsMode')
        #self.standardOverview.clearSearch()
        #self.standardOverview.toggleSearchDetailsPanel(False)
        
    def standardFriendsOverview(self):
        self.frame.pageTitle.SetLabel('ALL FRIENDS')
        self.standardOverview.setMode('friendsMode')
        if not self.standardOverview.getSorting():
            gridState = GridState('friendsMode', 'all', 'name', reverse=True)
            self.standardOverview.filterChanged(gridState)
        self.standardDetails.setMode('friendsMode')
        #self.standardOverview.clearSearch()
        #self.standardOverview.toggleSearchDetailsPanel(False)
        
    def standardProfileOverview(self):
        self.frame.pageTitle.SetLabel('PROFILE')
        profileList = []
        panel = self.standardOverview.data['profileMode'].get('panel',None)
        if panel is not None:
            panel.seldomReloadData()
        self.standardOverview.setMode('profileMode')
        self.standardDetails.seldomReloadData()
        self.standardDetails.setMode('profileMode')

        
    def standardLibraryOverview(self, filters = None, refresh=False):
        
        setmode = refresh
        if self.guiPage != 'my_files':
            self.guiPage = 'my_files' 
            self.frame.top_bg.ag.Hide()
            self.frame.top_bg.my_files.SetForegroundColour((0,105,156))
            self.frame.top_bg.settings.SetForegroundColour((255,51,0))

            #if self.standardGrid:
            #    self.standardGrid.deselectAll()
            #    self.standardGrid.clearAllData()


            self.frame.videoframe.show_videoframe()
            self.frame.videoparentpanel.Show()


            if self.frame.top_bg.search_results.GetLabel() != '':
                self.frame.top_bg.search_results.SetLabel('Return to Results')
                self.frame.top_bg.search_results.SetForegroundColour(wx.RED)
            self.frame.top_bg.Layout()
            self.frame.pagerPanel.Show()
            
            setmode = True
            
        if setmode:
            #self.frame.pageTitle.SetLabel('DOWNLOADS')      
            self.standardOverview.setMode('libraryMode',refreshGrid=refresh)
            #gridState = self.standardOverview.getFilter().getState()
            #if not gridState or not gridState.isValid():
            gridState = GridState('libraryMode', 'all', 'name')
            self.standardOverview.filterChanged(gridState)

            wx.CallAfter(self.frame.videoframe.show_videoframe)
        
        self.standardDetails.setMode('libraryMode')
        
    def standardSubscriptionsOverview(self):
        self.frame.pageTitle.SetLabel('SUBSCRIPTIONS')       
        self.standardOverview.setMode('subscriptionsMode')
        gridState = GridState('subscriptionMode', 'all', 'name')
        self.standardOverview.filterChanged(gridState)
        self.standardDetails.setMode('subscriptionsMode')
    
    def standardFileDetailsOverview(self, filters = ['','']):               
        filesDetailsList = []
        self.standardOverview.setMode('fileDetailsMode')
#        print 'tb > self.standardOverview.GetSize() 1= %s ' % self.standardOverview.GetSize()
#        print 'tb > self.frame = %s ' % self.frame.GetSize()
        
        frameSize = self.frame.GetSize()
#        self.standardOverview.SetMinSize((1000,2000))
#        self.scrollWindow.FitInside()
#        print 'tb > self.standardOverview.GetSize() 2= %s ' % self.standardOverview.GetSize()
#        self.scrollWindow.SetScrollbars(1,1,1024,2000)
        
##        self.scrollWindow.SetScrollbars(1,1,frameSize[0],frameSize[1])
#        self.standardOverview.SetSize((-1, 2000))
#        print 'tb > self.standardOverview.GetSize() = %s' % self.standardOverview.GetSize()
#        self.standardOverview.filterChanged(filters)
#        self.standardDetails.setMode('fileDetails')
    def standardPlaylistOverview(self, filters = ['','']):               
        filesDetailsList = []
        self.standardOverview.setMode('playlistMode')
        

    def standardPersonDetailsOverview(self, filters = ['','']):               
        filesDetailsList = []
        self.standardOverview.setMode('personDetailsMode')
         
    def standardMessagesOverview(self):
        if DEBUG:
            print >>sys.stderr,'GUIUtil: standardMessagesOverview: Not yet implemented;'
  
            
    def initStandardOverview(self, standardOverview):
        "Called by standardOverview when ready with init"
        self.standardOverview = standardOverview
#        self.standardFilesOverview(filters = ['all', 'seeder'])


        self.standardStartpage()
        self.standardOverview.Show(True)
        wx.CallAfter(self.refreshOnResize)
        
        # Preselect mainButtonFiles
#        filesButton = xrc.XRCCTRL(self.frame, 'Start page')
#        filesButton.setSelected(True)
#        self.selectedMainButton = filesButton

        # init thumb / list view
        self.gridViewMode = 'list'
        
        self.filterStandard.Hide() ## hide the standardOverview at startup

        # Init family filter        
        ##self.familyButton = xrc.XRCCTRL(self.frame, 'familyfilter')
        
        # Family filter on by default
        ##self.familyButton.setToggled()
        catobj = Category.getInstance()
        catobj.set_family_filter(True)

        
    def initFilterStandard(self, filterStandard):
        self.filterStandard = filterStandard
        self.advancedFiltering = xrc.XRCCTRL(self.frame, "advancedFiltering")
            
     
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
#        self.standardDetails.Hide()
        # init player here?    
        self.standardDetails.refreshStatusPanel(True)         
        self.guiOpen.set()
        
    def deleteTorrent(self, torrent):
        if torrent.get('web2'):
            return
        self.torrentsearch_manager.deleteTorrent(torrent['infohash'],delete_file=True)
    
    def deleteSubscription(self,subscrip):
        self.standardOverview.loadSubscriptionData()
        self.standardOverview.refreshData()
    
    def addTorrentAsHelper(self):
        if self.standardOverview.mode == 'libraryMode':
            self.standardOverview.filterChanged(None)
            #self.standardOverview.refreshData()
    
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

    def selectSubscription(self, sub_data):
        "User clicked on subscription. Has to be selected in detailPanel"
        self.standardDetails.setData(sub_data)
        self.standardOverview.updateSelection()
            
    def detailsTabClicked(self, name):
        "A tab in the detailsPanel was clicked"
        self.standardDetails.tabClicked(name)
        
    def refreshOnResize(self):
#        print 'tb > REFRESH ON RESIZE'
#        print self.standardOverview.GetContainingSizer().GetItem(0)

#        self.standardOverview.GetContainingSizer().GetItem(self.standardOverview).SetProportion(1)
#        self.standardOverview.SetProportion(1)
        try:
            if DEBUG:
                print >>sys.stderr,'GuiUtility: explicit refresh'
            self.mainSizer.FitInside(self.frame)
            self.standardDetails.Refresh()
            self.frame.topBackgroundRight.Refresh()
            self.frame.topBackgroundRight.GetSizer().Layout()
            self.frame.topBackgroundRight.GetContainingSizer().Layout()
            self.updateSizeOfStandardOverview()
            self.standardDetails.Layout()
            self.standardDetail.GetContainingSizer.Layout()
            self.standardOverview.Refresh()
            
        except:
            pass # When resize is done before panels are loaded: no refresh
    
    def updateSizeOfStandardOverview(self):
        print 'tb > SetProportion'
        self.standardOverview.SetProportion(1)
        
        
        if self.standardOverview.gridIsAutoResizing():
            #print 'size1: %d, size2: %d' % (self.frame.GetClientSize()[1], self.frame.window.GetClientSize()[1])
            margin = 10
            newSize = (-1, #self.scrollWindow.GetClientSize()[1] - 
                           self.frame.GetClientSize()[1] - 
                               100 - # height of top bar
                               self.standardOverview.getPager().GetSize()[1] -
                               margin)
        else:
            newSize = self.standardOverview.GetSize()
                    
        #print 'ClientSize: %s, virtual : %s' % (str(self.scrollWindow.GetClientSize()), str(self.scrollWindow.GetVirtualSize()))
        #print 'Position: %s' % str(self.standardOverview.GetPosition())
        self.standardOverview.SetSize(newSize)
        self.standardOverview.SetMinSize(newSize)
        self.standardOverview.SetMaxSize(newSize)            
        #print 'Overview is now: %s' % str(self.standardOverview.GetSize())
        self.standardOverview.GetContainingSizer().Layout()
            
    def refreshTracker(self):
        torrent = self.standardDetails.getData()
        if not torrent:
            return
        if DEBUG:
            print >>sys.stderr,'GUIUtility: refresh ' + repr(torrent.get('content_name', 'no_name'))
        if torrent:
            check = TorrentChecking(torrent['infohash'])
            check.start()
            
            
    def refreshTorrentStats(self,dslist):
        """ Called from ABCApp by MainThread to refresh statistics of downloading torrents"""
        try:
            if self.guiOpen.isSet():
                self.standardDetails.refreshTorrentStats(dslist)
        except:
            print_exc()
    
    def refreshUploadStats(self, dslist):
        try:
            if self.guiOpen.isSet():
                self.standardDetails.refreshUploadStats(dslist)
        except:
            print_exc()
   
    def emailFriend(self, event):
        ip = self.utility.config.Read('bind')
        if ip is None or ip == '':
            ip = self.utility.session.get_external_ip()
        mypermid = self.utility.session.get_permid()

        permid_txt = self.utility.lang.get('permid')+": "+show_permid(mypermid)
        ip_txt = self.utility.lang.get('ipaddress')+": "+ip

        port = self.utility.session.get_listen_port()
        port_txt = self.utility.lang.get('portnumber')+" "+str(port)

        subject = self.utility.lang.get('invitation_subject')
        invitation_body = self.utility.lang.get('invitation_body')
        invitation_body = invitation_body.replace('\\n', '\n')
        invitation_body += ip_txt + '\n\r'
        invitation_body += port_txt + '\n\r'
        invitation_body += permid_txt + '\n\r\n\r\n\r'
       
        if sys.platform == "darwin":
            body = invitation_body.replace('\\r','')
            body = body.replace('\r','')
        else:
            body = urllib.quote(invitation_body)
        mailToURL = 'mailto:%s?subject=%s&body=%s'%('', subject, body)
        try:
            webbrowser.open(mailToURL)
        except:
            text = invitation_body.split("\n")
            InviteFriendsDialog(text)

    def get_nat_type(self, callback=None):
        return self.utility.session.get_nat_type(callback=callback)

    def dosearch(self):
        sf = self.frame.top_bg.searchField
        #sf = self.standardOverview.getSearchField()
        if sf is None:
            return
        input = sf.GetValue().strip()
        if input == '':
            return

        ##sizer = self.frame.search.GetContainingSizer()
        ##self.frame.go.setToggled(True)
        ##self.frame.go.SetMinSize((61,24))
        ##sizer.Layout()
        ##self.frame.top_bg.Refresh()
        ##self.frame.top_bg.Update()

        #self.standardOverview.toggleSearchDetailsPanel(True)
        if self.standardOverview.mode in ["filesMode", "libraryMode"]:
            self.searchFiles(self.standardOverview.mode, input)
        elif self.standardOverview.mode in ["personsMode", 'friendsMode']:
            self.searchPersons(self.standardOverview.mode, input)
        
        
        
        
    def searchFiles(self, mode, input):
        
        if DEBUG:
            print >>sys.stderr,"GUIUtil: searchFiles:",input
        low = input.lower()
        wantkeywords = [i for i in low.split(' ') if i]
        self.torrentsearch_manager.setSearchKeywords(wantkeywords, mode)
        self.torrentsearch_manager.set_gridmgr(self.standardOverview.getGrid().getGridManager())
        #print "******** gui uti searchFiles", wantkeywords
        gridstate = GridState(self.standardOverview.mode, 'all', 'rameezmetric')
        self.standardOverview.filterChanged(gridstate)
        

        if mode == 'filesMode':
            #
            # Query the peers we are connected to
            #
            nhits = self.torrentsearch_manager.getCurrentHitsLen()
            if nhits < self.remote_search_threshold and mode == 'filesMode':
                q = 'SIMPLE '
                for kw in wantkeywords:
                    q += kw+' '
                    
                num_remote_queries = min((self.remote_search_threshold - nhits)/2, self.max_remote_queries)
                if num_remote_queries > 0:
                    self.utility.session.query_connected_peers(q,self.sesscb_got_remote_hits,num_remote_queries)
                     
                    self.standardOverview.setSearchFeedback('remote', False, 0, wantkeywords,self.frame.top_bg.search_results)
                    
            #
            # Query YouTube, etc.
            #
            #web2on = self.utility.config.Read('enableweb2search',"boolean")
            #if mode == 'filesMode' and web2on:
            #    self.torrentsearch_manager.searchWeb2(60) # 3 pages, TODO: calc from grid size

        


    def sesscb_got_remote_hits(self,permid,query,hits):
        # Called by SessionCallback thread 
        if DEBUG:
            print >>sys.stderr,"GUIUtil: sesscb_got_remote_hits",len(hits)

        kwstr = query[len('SIMPLE '):]
        kws = kwstr.split()
        wx.CallAfter(self.torrentsearch_manager.gotRemoteHits,permid,kws,hits,self.standardOverview.getMode())

    def stopSearch(self):
        self.frame.go.setToggled(False)
        self.frame.top_bg.createBackgroundImage()
        self.frame.top_bg.Refresh()
        self.frame.top_bg.Update()
        self.frame.search.SetFocus()
        mode = self.standardOverview.getMode() 
        if mode == 'filesMode' or mode == 'libraryMode':
            self.torrentsearch_manager.stopSearch()
        if mode == 'personsMode' or mode == 'friendsMode':
            self.peersearch_manager.stopSearch()
        
    def clearSearch(self):
        mode = self.standardOverview.getMode()
        self.standardOverview.data[mode]['search'].Clear()
        if mode == 'filesMode'  or mode == 'libraryMode':
            self.torrentsearch_manager.setSearchKeywords([],mode)
            gridState = self.standardOverview.getFilter().getState()
            if not gridState or not gridState.isValid():
                gridState = GridState(mode, 'all', 'num_seeders')
            if DEBUG:
                print >> sys.stderr, 'GUIUtil: clearSearch, back to: %s' % gridState
            self.standardOverview.filterChanged(gridState)
        if mode == 'personsMode'  or mode == 'friendsMode':
            self.peersearch_manager.setSearchKeywords([],mode)
            gridState = GridState(mode, 'all', 'last_connected', reverse=False)
            self.standardOverview.filterChanged(gridState)
        
    def searchPersons(self, mode, input):
        if DEBUG:
            print >>sys.stderr,"GUIUtil: searchPersons:",input
        low = input.lower().strip()
        wantkeywords = low.split(' ')

        self.peersearch_manager.setSearchKeywords(wantkeywords, mode)
        self.peersearch_manager.set_gridmgr(self.standardOverview.getGrid().getGridManager())
        #print "******** gui uti searchFiles", wantkeywords
        gridstate = GridState(self.standardOverview.mode, 'all', 'last_connected')
        self.standardOverview.filterChanged(gridstate)
   

    def OnSearchKeyDown(self,event):
        
        keycode = event.GetKeyCode()
        #if event.CmdDown():
        #print "OnSearchKeyDown: keycode",keycode
        if keycode == wx.WXK_RETURN:
            app.frame.Hide()
            self.standardFilesOverview()
            self.dosearch()
        else:
            event.Skip()     

    def OnSubscribeKeyDown(self,event):
        keycode = event.GetKeyCode()
        if keycode == wx.WXK_RETURN:
            self.subscribe()
        event.Skip()     

    def OnSubscribeMouseAction(self,event):
        obj = event.GetEventObject()

        # TODO: smarter behavior
        obj.SetSelection(-1,-1)
        event.Skip()


    def subscribe(self):
        rssurlctrl = self.standardOverview.getRSSUrlCtrl()
        url = rssurlctrl.GetValue()
        if not url:
            return
        if not "://" in url:
            url = "http://" + url

        if DEBUG:
            print >>sys.stderr,"GUIUtil: subscribe:",url
        try:
            stream = urllib2.urlopen(url)
            stream.close()
        except Exception,e:
            dlg = wx.MessageDialog(self.standardOverview, "Could not resolve URL:\n\n"+str(e), 'Tribler Warning',wx.OK | wx.ICON_WARNING)
            result = dlg.ShowModal()
            dlg.Destroy()
            return
        
        torrentfeed = TorrentFeedThread.getInstance()
        torrentfeed.addURL(url)
        self.standardOverview.loadSubscriptionData()
        self.standardOverview.refreshData()

    def firewallStatusClick(self,event=None):
        
        if self.isReachable():
            title = self.utility.lang.get('tribler_information')
            type = wx.ICON_INFORMATION
            msg = self.utility.lang.get('reachable_tooltip')
        else:
            title = self.utility.lang.get('tribler_warning')
            type = wx.ICON_WARNING
            msg = self.utility.lang.get('tribler_unreachable_explanation')
            
        dlg = wx.MessageDialog(None, msg, title, wx.OK|type)
        result = dlg.ShowModal()
        dlg.Destroy()

    def OnSearchMouseAction(self,event):
        sf = self.standardOverview.getSearchField()
        if sf is None:
            return

        eventType = event.GetEventType()
        #print 'event: %s, double: %s, leftup: %s' % (eventType, wx.EVT_LEFT_DCLICK, wx.EVT_LEFT_UP)
        #print 'value: "%s", 1: "%s", 2: "%s"' % (sf.GetValue(), self.utility.lang.get('filesdefaultsearchweb2txt'),self.utility.lang.get('filesdefaultsearchtxt')) 
        if event.LeftDClick() or \
           ( event.LeftUp() and sf.GetValue() in [self.utility.lang.get('filesdefaultsearchweb2txt'),self.utility.lang.get('filesdefaultsearchtxt')]):
            ##print 'select'
            sf.SetSelection(-1,-1)
            
        if not event.LeftDClick():
            event.Skip()

    def getSearchField(self,mode=None):
       return self.standardOverview.getSearchField(mode=mode)
   
    def isReachable(self):
        #return DialbackMsgHandler.getInstance().isConnectable()
        return self.reachable
   
    def set_reachable(self):
        self.reachable = True
   
   
    def onChangeViewModus(self):
        # clicked on changemodus button in title bar of overviewPanel
        changeViewModus = wx.Menu() 
        self.utility.makePopup(changeViewModus, None, 'rChangeViewModusThumb', type="checkitem", status="active")
        self.utility.makePopup(changeViewModus, None, 'rChangeViewModusList', type="checkitem") 
        return (changeViewMouse)
        
        
        
    def OnRightMouseAction(self,event):
        # called from  "*ItemPanel" or from "standardDetails"
        item = self.standardDetails.getData()
        if not item:
            if DEBUG:
                print >>sys.stderr,'GUIUtil: Used right mouse menu, but no item in DetailWindow'
            return
        
        rightMouse = wx.Menu()        

        
        
        if self.standardOverview.mode == "filesMode" and not item.get('myDownloadHistory', False):
            self.utility.makePopup(rightMouse, None, 'rOptions')
            if item.get('web2'):
                self.utility.makePopup(rightMouse, self.onDownloadOpen, 'rPlay')
            else:
                #self.utility.makePopup(rightMouse, self.onRecommend, 'rRecommend')        
                #if secret:
                self.utility.makePopup(rightMouse, self.onDownloadOpen, 'rDownloadOpenly')
                #else:
                #self.utility.makePopup(rightMouse, self.onDownloadSecret, 'rDownloadSecretly')
            
            # if in library:
        elif self.standardOverview.mode == "libraryMode" or item.get('myDownloadHistory'):
            #self.utility.makePopup(rightMouse, self.onRecommend, 'rRecommend')        
            #rightMouse.AppendSeparator()
            self.utility.makePopup(rightMouse, None, 'rLibraryOptions')
            self.utility.makePopup(rightMouse, self.onOpenFileDest, 'rOpenfilename')
            self.utility.makePopup(rightMouse, self.onOpenDest, 'rOpenfiledestination')
            self.utility.makePopup(rightMouse, self.onDeleteTorrentFromLibrary, 'rRemoveFromList')
            self.utility.makePopup(rightMouse, self.onDeleteTorrentFromDisk, 'rRemoveFromListAndHD') 
            #rightMouse.AppendSeparator()
            #self.utility.makePopup(rightMouse, self.onAdvancedInfoInLibrary, 'rAdvancedInfo')
        elif self.standardOverview.mode == "personsMode" or self.standardOverview.mode == "friendsMode":     
            self.utility.makePopup(rightMouse, None, 'rOptions')
            fs = item.get('friend') 
            if fs == FS_MUTUAL or fs == FS_I_INVITED:
                self.utility.makePopup(rightMouse, self.onChangeFriendStatus, 'rRemoveAsFriend')
                self.utility.makePopup(rightMouse, self.onChangeFriendInfo, 'rChangeInfo')
            else:
                self.utility.makePopup(rightMouse, self.onChangeFriendStatus, 'rAddAsFriend')
            
            # if in friends:
##            if self.standardOverview.mode == "friendsMode":
##                rightMouse.AppendSeparator()
##                self.utility.makePopup(rightMouse, None, 'rFriendsOptions')
##                self.utility.makePopup(rightMouse, None, 'rSendAMessage')
        elif self.standardOverview.mode == "subscriptionsMode":
            event.Skip()
##            self.utility.makePopup(rightMouse, None, 'rOptions')
##            self.utility.makePopup(rightMouse, None, 'rChangeSubscrTitle')
##            self.utility.makePopup(rightMouse, None, 'rRemoveSubscr')
            

        
        return (rightMouse)
        #self.PopupMenu(rightMouse, (-1,-1))  
        
# ================== actions for rightMouse button ========================================== 
    def onOpenFileDest(self, event = None):
        # open File
        self.onOpenDest(event, openFile=True)
  
    def onOpenDest(self, event = None, openFile=False):
        # open Destination
        item = self.standardDetails.getData()
        state = item.get('ds')
        
        if state:
            dest = state.get_download().get_dest_dir()
            if openFile:
                destfiles = state.get_download().get_dest_files()
                if len(destfiles) == 1:
                    dest = destfiles[0][1]
            if sys.platform == 'darwin':
                dest = 'file://%s' % dest
            
            print >> sys.stderr,"GUIUtil: onOpenDest",dest
            complete = True
            # check if destination exists
            assert dest is not None and os.access(dest, os.R_OK), 'Could not retrieve destination'
            try:
                t = Thread(target = open_new, args=(str(dest),))
                t.setName( "FilesOpenNew"+t.getName() )
                t.setDaemon(True)
                t.start()
            except:
                print_exc()
                pass
                
        elif DEBUG:
            print >>sys.stderr,'GUIUtil: onOpenFileDest failed: no torrent selected'
            
    def onDeleteTorrentFromDisk(self, event = None):
        item = self.standardDetails.getData()
        
        if item.get('ds'):
            self.utility.session.remove_download(item['ds'].get_download(),removecontent = True)
            
        self.standardOverview.removeTorrentFromLibrary(item)

                
    def onDeleteTorrentFromLibrary(self, event = None):
        item = self.standardDetails.getData()
        
        if item.get('ds'):
            self.utility.session.remove_download(item['ds'].get_download(),removecontent = False)
            
        self.standardOverview.removeTorrentFromLibrary(item)
    
    def onAdvancedInfoInLibrary(self, event = None):
        # open torrent details frame
        item = self.standardDetails.getData()
        abctorrent = item.get('abctorrent')
        if abctorrent:
            abctorrent.dialogs.advancedDetails(item)
            
        event.Skip()
        
    def onModerate(self, event = None):
        if DEBUG:
            print >>sys.stderr,'GUIUtil: ---tb--- Moderate event'
            print >>sys.stderr,event
        # todo
        event.Skip()
    
    def onRecommend(self, event = None):
        # todo
        event.Skip()
   
    def onDownloadOpen(self, event = None):
        self.standardDetails.download()
        event.Skip()
    
    def onDownloadSecret(self, event = None):
        self.standardDetails.download(secret=True)
        event.Skip()
        
    def onChangeFriendStatus(self, event = None):
        self.standardDetails.addAsFriend()
        event.Skip()

    def onChangeFriendInfo(self, event = None):
        item = self.standardDetails.getData()       
        dialog = MakeFriendsDialog(self.frame,self.utility, item)
        ret = dialog.ShowModal()
        dialog.Destroy()
        event.Skip()
        
    def filesList(self, torrent):
        # tb > code is copied from Tribler > vwxGUI > tribler>List.py [FilesList]
        # Get the file(s)data for this torrent

            
        if DEBUG:
            print >>sys.stderr,'tribler_List: setData of FilesTabPanel called'
        try:
            
            if torrent.get('web2') or 'query_permid' in torrent: # web2 or remote query result
                self.filelist = []
    #                self.DeleteAllItems()
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
                
            
            return filelist
            
        except:
            if DEBUG:
                print >>sys.stderr,'tribler_List: error getting list of files in torrent'
            print_exc()
            return {}
       
    def getGuiElement(self, name):
        if not self.elements.has_key(name) or not self.elements[name]:
            return None
        return self.elements[name]
    


    
# =========END ========= actions for rightMouse button ==========================================
    
    def superRefresh(self, sizer):
        print 'supersizer to the rescue'
        for item in sizer.GetChildren():
            if item.IsSizer():
                self.superRefresh(item.GetSizer())
                item.GetSizer().Layout()
            elif item.IsWindow():
                item.GetWindow().Refresh()
