import wx
from wx import xrc
from traceback import print_exc,print_stack
from threading import Event
import urllib,urllib2
import webbrowser
from sets import Set

from bgPanel import *
import updateXRC
from Tribler.TrackerChecking.ManualChecking import SingleManualChecking
from Tribler.CacheDB.CacheDBHandler import MyDBHandler
from Tribler.Overlay.permid import permid_for_user
from Tribler.Dialogs.makefriends import MakeFriendsDialog
from torrentManager import TorrentDataManager
from peermanager import PeerDataManager
from Tribler.Subscriptions.rss_client import TorrentFeedThread

#from Tribler.vwxGUI.filesFilter import filesFilter



from Tribler.utilities import *
from Utility.constants import *

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
        self.params = params
        self.selectedMainButton = None
        self.isReachable = False #reachability flag / port forwarding enabled / accessible from the internet
        self.guiOpen = Event()
        
        self.selectedColour = wx.Colour(255,200,187)       
        self.unselectedColour = wx.WHITE
        self.unselectedColour2 = wx.Colour(230,230,230)
        
            
    def getInstance(*args, **kw):
        if GUIUtility.__single is None:
            GUIUtility(*args, **kw)
        return GUIUtility.__single
    getInstance = staticmethod(getInstance)
    
    
    
        
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
        elif name == "addAsFriend" or name == 'deleteFriend':
            self.standardDetails.addAsFriend()
        elif name == 'download':
            self.standardDetails.download()
        elif name == 'addFriend':
            #print >>sys.stderr,"GUIUtil: buttonClicked: parent is",obj.GetParent().GetName()
            dialog = MakeFriendsDialog(obj,self.utility)
            ret = dialog.ShowModal()
            if ret == wx.ID_OK:
                #self.updateView()
                dialog.Destroy()
        elif name == 'inviteFriends':
            self.emailFriend(event)
       
            #else:
            #    print >>sys.stderr,"GUIUtil: buttonClicked: dlbooster: Torrent is None"
            
        elif (name == 'edit' or name.startswith('bgPanel')) and obj.GetParent().GetName() == "profileOverview":
            self.standardOverview.currentPanel.sendClick(event)
            self.detailsTabClicked(name) #a panel was clicked in the profile overview and this is the most elegant so far method of informing the others
        elif name == "takeMeThere0" : #a button to go to preferences was clicked
            panel_name = self.standardDetails.currentPanel.GetName()
            if panel_name == "profileDetails_Download":
                self.utility.actions[ACTION_PREFERENCES].action()
            elif panel_name == "profileDetails_Presence":
                self.mainButtonClicked( 'mainButtonPersons', self.frame.mainButtonPersons)
            #generate event to change page -> this should be done as a parameter to action because is modal
            #event = wx.TreeEvent(wx.EVT_TREE_ITEM_ACTIVATED)
            #wx.PostEvent()
        elif name == "takeMeThere1": #switch to another view
            panel_name = self.standardDetails.currentPanel.GetName()
            if panel_name == "profileDetails_Download":
                self.mainButtonClicked( 'mainButtonPersons', self.frame.mainButtonPersons)
            else:
                print 'GUIUtil: A button was clicked, but no action is defined for: %s' % name
        elif name == "search": # search files/persons button
            print 'GUIUtil: search button clicked'
            self.dosearch()
        elif name == 'subscribe':
            self.subscribe()
        elif name == 'firewallStatus':
            self.firewallStatusClick()
        else:
            print 'GUIUtil: A button was clicked, but no action is defined for: %s' % name
                
        
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
        elif DEBUG:
            print >>sys.stderr,"GUIUtil: MainButtonClicked: unhandled name",name
            
    def standardFilesOverview(self, filters = ['video', 'swarmsize']):        
        
        self.standardOverview.setMode('filesMode')
        self.standardOverview.filterChanged(filters)
        try:
            if self.standardDetails:
                self.standardDetails.setMode('filesMode', None)
        except:
            pass
        
    def standardPersonsOverview(self):
        self.standardOverview.setMode('personsMode')
        #should read the current filters, not put some default ones that have nothing to do with the ones in the combo boxes in the filter gui
        self.standardOverview.filterChanged(self.standardOverview.getFilter().getState())
        self.standardDetails.setMode('personsMode')
        
    def standardFriendsOverview(self):
        self.standardOverview.setMode('friendsMode')
        filterState = self.standardOverview.getFilter().getState()
        print "standardFriendsOverview, filter state:",filterState
        self.standardOverview.filterChanged(filterState)
        self.standardDetails.setMode('personsMode')
    
    def standardProfileOverview(self):
        profileList = []
        self.standardOverview.setMode('profileMode')
        self.standardDetails.setMode('profileMode')
        
    def standardLibraryOverview(self, filters = ['','']):       
        self.standardOverview.setMode('libraryMode')        
        self.standardOverview.filterChanged(filters)
        self.standardDetails.setMode('libraryMode')
        
    def standardSubscriptionsOverview(self, filters = ['','']):       
        self.standardOverview.setMode('subscriptionsMode')
        self.standardOverview.filterChanged(filters)
        self.standardDetails.setMode('subscriptionsMode')
         
    def standardMessagesOverview(self):
        print 'Not yet implemented;'
  
            
#    def reloadPeers(self):
#        return self.peer_manager.getFiltered Data('all') #sortData(self.categorykey)
        
   
    def initStandardOverview(self, standardOverview):
        "Called by standardOverview when ready with init"
        self.standardOverview = standardOverview
        self.peer_manager = standardOverview.peer_manager
        self.data_manager = standardOverview.data_manager
        self.standardFilesOverview()

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
        self.guiOpen.set()
        
    def deleteTorrent(self, torrent):
        pass
    
    def deleteSubscription(self,subscrip):
        self.standardOverview.loadSubscriptionData()
        self.standardOverview.refreshData()
    
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
        try:
            #if DEBUG:
            #    print'GuiUtility: explicit refresh'
            self.standardDetails.Refresh()
            self.standardOverview.Refresh()
            self.frame.topBackgroundRight.Refresh()
            #self.frame.topBackgroundRight.GetSizer.Layout()
        except:
            pass # When resize is done before panels are loaded: no refresh
        
    def refreshTracker(self):
        torrent = self.standardDetails.getData()
        if not torrent:
            return
        if DEBUG:
            print >>sys.stderr,'GUIUtility: refresh ' + repr(torrent.get('content_name', 'no_name'))
        if torrent:
            check = SingleManualChecking(torrent)
            check.start()
            
    def refreshTorrentStats(self):
        "Called from launchmanycore by network thread to refresh statistics of downloading torrents"
        try:
            if self.guiOpen.isSet():
                self.standardOverview.refreshTorrentStats_network_callback()
                self.standardDetails.refreshTorrentStats_network_callback()
        except:
            print 'GuiUtility: Error refreshing stats'
            print_exc()


    def refreshTorrentTotalStats(self,*args,**kwargs):
        "Called from ABCScheduler by network thread to refresh statistics of downloading torrents"
        try:
            if self.guiOpen.isSet():
                self.standardDetails.refreshTorrentTotalStats_network_callback(*args,**kwargs)
        except:
            print 'GuiUtility: Error refreshing total stats'
            print_exc()
   
   
    def emailFriend(self, event):
        
        my_db = MyDBHandler()
        ip = self.utility.config.Read('bind')
        if ip is None or ip == '':
            ip = my_db.getMyIP()
        mypermid = my_db.getMyPermid()
        permid_txt = self.utility.lang.get('permid')+": "+permid_for_user(mypermid)
        ip_txt = self.utility.lang.get('ipaddress')+": "+ip

        # port = self.utility.controller.listen_port
        port = self.utility.config.Read('minport', 'int')
        port_txt = self.utility.lang.get('portnumber')+" "+str(port)

        
        subject = self.utility.lang.get('invitation_subject')
        invitation_body = self.utility.lang.get('invitation_body')
        invitation_body = invitation_body.replace('\\n', '\n')
        invitation_body += permid_txt + '\n'
        invitation_body += ip_txt + '\n'
        invitation_body += port_txt + '\n\n\n'
       
        if sys.platform == "darwin":
            body = invitation_body.replace('\\r','\r')
            body = invitation_body.replace('\\n','\n')
        else:
            body = urllib.quote(invitation_body)
        mailToURL = 'mailto:%s?subject=%s&body=%s'%('', subject, body)
        webbrowser.open(mailToURL)
        
    def dosearch(self):
        if self.standardOverview.mode == "filesMode":
            self.searchFiles()
        elif self.standardOverview.mode == "personsMode":
            self.searchPersons()
        elif self.standardOverview.mode == "friendsMode":
            self.searchFriends()

        
    def searchFiles(self):
        sf = self.standardOverview.getSearchField()
        if sf is None:
            return
        input = sf.GetValue()
        print "GUIUtil: searchFiles:",input
        low = input.lower()
        wantkeywords = low.split(' ')
        wantkeywords += low.split('-')
        wantkeywords += low.split('_')
        wantkeywords += low.split('.')
        zet = Set(wantkeywords)
        wantkeywords = list(zet)
        print "GUIUtil: searchFiles: keywords",wantkeywords
        #self.peer_manager = standardOverview.peer_manager
        self.data_manager.setSearchKeywords(wantkeywords)
        self.standardOverview.filterChanged(['search','swarmsize'],setgui=True)
        
    def searchPersons(self):
        sf = self.standardOverview.getSearchField()
        if sf is None:
            return
        input = sf.GetValue()
        print "GUIUtil: searchPersons:",input
        low = input.lower()
        wantkeywords = low.split(' ')
        wantkeywords += low.split('-')
        wantkeywords += low.split('_')
        wantkeywords += low.split('.')
        zet = Set(wantkeywords)
        wantkeywords = list(zet)
        print "GUIUtil: searchPersons: keywords",wantkeywords
        def searchFilterFunc(peer_data):
            low = peer_data['content_name'].lower()
            for wantkw in wantkeywords:
                if low.find(wantkw) != -1:
                    return True
            return False
        self.peer_manager.registerFilter("search",searchFilterFunc)
        filterState = self.standardOverview.getFilter().getState()
        sort = None
        if filterState is not None and type(filterState) == 'list' and len(filterState) == 2 and filterState[1] is not None:
            sort = filterState[1]
        self.standardOverview.filterChanged(['search',sort],setgui=True)
        
    def searchFriends(self):
        sf = self.standardOverview.getSearchField()
        if sf is None:
            return
        input = sf.GetValue()
        print "GUIUtil: searchFriends:",input
        low = input.lower()
        wantkeywords = low.split(' ')
        wantkeywords += low.split('-')
        wantkeywords += low.split('_')
        wantkeywords += low.split('.')
        zet = Set(wantkeywords)
        wantkeywords = list(zet)
        print "GUIUtil: searchPersons: keywords",wantkeywords
        def searchFriendsFilterFunc(peer_data):
            if not peer_data.get('friend',False):
                return False
            low = peer_data['content_name'].lower()
            for wantkw in wantkeywords:
                if low.find(wantkw) != -1:
                    return True
            return False
        self.peer_manager.registerFilter("search_friends",searchFriendsFilterFunc)
        filterState = self.standardOverview.getFilter().getState()
        sort = None
        if filterState is not None and type(filterState) == 'list' and len(filterState) == 2 and filterState[1] is not None:
            sort = filterState[1]
        self.standardOverview.filterChanged(['search_friends',sort],setgui=True)

    def OnSearchKeyDown(self,event):
        keycode = event.GetKeyCode()
        #if event.CmdDown():
        #print "OnSearchKeyDown: keycode",keycode
        if keycode == wx.WXK_RETURN:
            self.dosearch()
        event.Skip()     

    def OnSubscribeKeyDown(self,event):
        keycode = event.GetKeyCode()
        if keycode == wx.WXK_RETURN:
            self.subscribe()
        event.Skip()     

    def subscribe(self):
        rssurlctrl = self.standardOverview.getRSSUrlCtrl()
        url = rssurlctrl.GetValue()
        print "GUIUtil: subscribe:",url
        try:
            stream = urllib2.urlopen(url)
            stream.close()
        except Exception,e:
            dlg = wx.MessageDialog(self.standardOverview, "Invalid URL"+str(e), 'Tribler Warning',wx.OK | wx.ICON_WARNING)
            result = dlg.ShowModal()
            dlg.Destroy()
            return
        
        torrentfeed = TorrentFeedThread.getInstance()
        torrentfeed.addURL(url)
        self.standardOverview.loadSubscriptionData()
        self.standardOverview.refreshData()

    def firewallStatusClick(self,event=None):
        if self.isReachable:
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
