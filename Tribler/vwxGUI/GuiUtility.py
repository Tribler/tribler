
import wx, time, random
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
from peermanager import PeerDataManager
from Tribler.Subscriptions.rss_client import TorrentFeedThread
from Tribler.SocialNetwork.RemoteQueryMsgHandler import RemoteQueryMsgHandler
from Tribler.NATFirewall.DialbackMsgHandler import DialbackMsgHandler

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
        self.frame = None
        self.selectedMainButton = None
        self.peer_manager = None
        self.data_manager = None
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

        event.Skip(True) #should let other handlers use this event!!!!!!!
            
        name = ""
        obj = event.GetEventObject()
        try:
            name = obj.GetName()
        except:
            print 'Error: Could not get name of buttonObject: %s' % obj
        
        if DEBUG:
            print >>sys.stderr,'GUIUtil: Button clicked %s' % name
        
        if name.startswith('mainButton'):
            self.mainButtonClicked(name, obj)
        elif name.lower().find('detailstab') > -1:
            self.detailsTabClicked(name)
        elif name == 'refresh':
            self.refreshTracker()
        elif name == "addAsFriend" or name == 'deleteFriend':
            self.standardDetails.addAsFriend()
            self.standardOverview.refreshData()
        elif name == 'download':
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
            
        elif (name == 'edit' or name.startswith('bgPanel')) and obj.GetParent().GetName() == "profileOverview":
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
                print 'GUIUtil: A button was clicked, but no action is defined for: %s' % name
                
        elif name == "takeMeThere2": #switch to another view
            panel_name = self.standardDetails.currentPanel.GetName()
            if panel_name == "profileDetails_Download":
                URL = 'http://www.tribler.org/'
                webbrowser.open(URL)                
        elif name == "search": # search files/persons button
            print 'GUIUtil: search button clicked'
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
            self.standardOverview.clearSearch()
                        
            wx.CallAfter(self.standardOverview.toggleSearchDetailsPanel, False)
        elif DEBUG:
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
            
    def standardFilesOverview(self ):        
        
        self.standardOverview.setMode('filesMode')
        filters = self.standardOverview.getFilter().getState()
        self.standardOverview.filterChanged(filters,setgui=True)
        try:
            if self.standardDetails:
                self.standardDetails.setMode('filesMode', None)
        except:
            pass
        
    def standardPersonsOverview(self):
        self.standardOverview.setMode('personsMode')
        self.standardOverview.filterChanged(self.standardOverview.getFilter().getState())
        self.standardDetails.setMode('personsMode')
        
    def standardFriendsOverview(self):
        self.standardOverview.setMode('friendsMode')
        filterState = self.standardOverview.getFilter().getState()
        if DEBUG:
            print >>sys.stderr,"standardFriendsOverview, filter state:",filterState
        self.standardOverview.filterChanged(filterState)
        self.standardDetails.setMode('friendsMode')
    
    def standardProfileOverview(self):
        profileList = []
        self.standardOverview.setMode('profileMode')
        self.standardDetails.setMode('profileMode')
        
    def standardLibraryOverview(self):       
        self.standardOverview.setMode('libraryMode')
        filters = self.standardOverview.getFilter().getState()        
        self.standardOverview.filterChanged(filters, setgui = True)
        self.standardDetails.setMode('libraryMode')
        
    def standardSubscriptionsOverview(self, filters = ['','']):       
        self.standardOverview.setMode('subscriptionsMode')
        self.standardOverview.filterChanged(filters)
        self.standardDetails.setMode('subscriptionsMode')
         
    def standardMessagesOverview(self):
        if DEBUG:
            print >>sys.stderr,'GUIUtil: standardMessagesOverview: Not yet implemented;'
  
            
#    def reloadPeers(self):
#        return self.peer_manager.getFiltered Data('all') #sortData(self.categorykey)
        
   
    def initStandardOverview(self, standardOverview):
        "Called by standardOverview when ready with init"
        self.standardOverview = standardOverview
        self.peer_manager = standardOverview.peer_manager
        self.data_manager = standardOverview.data_manager
        self.standardFilesOverview()
        wx.CallAfter(self.refreshOnResize)

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
        if torrent.get('web2'):
            return
        self.data_manager.deleteTorrent(torrent['infohash'],delete_file=True)
    
    def deleteSubscription(self,subscrip):
        self.standardOverview.loadSubscriptionData()
        self.standardOverview.refreshData()
    
    def addTorrentAsHelper(self):
        self.standardOverview.loadLibraryData('all','latest')
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
            if DEBUG:
                print'GuiUtility: explicit refresh'
                    
            self.standardDetails.Refresh()
            self.frame.topBackgroundRight.Refresh()
            self.updateSizeOfStandardOverview()
            self.standardDetails.Layout()
            self.standardDetail.GetContainingSizer.Layout()
            self.standardOverview.Refresh()
            
        except:
            pass # When resize is done before panels are loaded: no refresh
    
    def updateSizeOfStandardOverview(self):
        if self.standardOverview.gridIsAutoResizing():
           
            margin = 10
            newSize = (-1, self.scrollWindow.GetClientSize()[1] - 
                               self.scrollWindow.CalcUnscrolledPosition(self.standardOverview.GetPosition())[1] - 
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
        invitation_body += ip_txt + '\n\r'
        invitation_body += port_txt + '\n\r'
        invitation_body += permid_txt + '\n\r\n\r\n\r'
       
        if sys.platform == "darwin":
            body = invitation_body.replace('\\r','')
            body = body.replace('\r','')
        else:
            body = urllib.quote(invitation_body)
        mailToURL = 'mailto:%s?subject=%s&body=%s'%('', subject, body)
        webbrowser.open(mailToURL)
        
    def dosearch(self):
        self.standardOverview.toggleSearchDetailsPanel(True)
        if self.standardOverview.mode in ["filesMode", "libraryMode"]:
            self.searchFiles(self.standardOverview.mode)
        elif self.standardOverview.mode == "personsMode":
            self.searchPersons()
        elif self.standardOverview.mode == "friendsMode":
            self.searchFriends()

        
        
        
    def searchFiles(self, mode):
        sf = self.standardOverview.getSearchField()
        if sf is None:
            return
        input = sf.GetValue()
        if DEBUG:
            print >>sys.stderr,"GUIUtil: searchFiles:",input
        low = input.lower()
        wantkeywords = low.split(' ')
        self.data_manager.setSearchKeywords(wantkeywords, mode)
        sorting = None
        self.standardOverview.filterChanged(None)

        #
        # Query the peers we are connected to
        #
        if mode == 'filesMode':
            rqmh = RemoteQueryMsgHandler.getInstance()
            rqmh.register2(self.data_manager)
            q = ''
            for kw in wantkeywords:
                q += kw+' '
                
            # For TEST suite
            #rqmh.test_sendQuery(q) 
            rqmh.sendQuery(q) 

        
    def searchPersons(self):
        sf = self.standardOverview.getSearchField()
        if sf is None:
            return
        input = sf.GetValue()
        if DEBUG:
            print >>sys.stderr,"GUIUtil: searchPersons:",input
        low = input.lower()
        wantkeywords = low.split(' ')
        wantkeywords += low.split('-')
        wantkeywords += low.split('_')
        wantkeywords += low.split('.')
        zet = Set(wantkeywords)
        wantkeywords = list(zet)
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
        if DEBUG:
            print "GUIUtil: searchFriends:",input
        low = input.lower()
        wantkeywords = low.split(' ')
        wantkeywords += low.split('-')
        wantkeywords += low.split('_')
        wantkeywords += low.split('.')
        zet = Set(wantkeywords)
        wantkeywords = list(zet)
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
        # TODO: smarter behavior
        sf.SetSelection(-1,-1)
        event.Skip()

    def getSearchField(self,mode=None):
       return self.standardOverview.getSearchField(mode=mode)
   
    def isReachable(self):
       #reachability flag / port forwarding enabled / accessible from the internet
       return DialbackMsgHandler.getInstance().isConnectable()
   
   
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
                print 'Used right mouse menu, but no item in DetailWindow'
            return
        
        rightMouse = wx.Menu()        
        #--tb--
        
        self.utility.makePopup(rightMouse, None, 'rOptions')
        if self.standardOverview.mode == "filesMode":
            
            self.utility.makePopup(rightMouse, self.onRecommend, 'rRecommend')        
            #if secret:
            self.utility.makePopup(rightMouse, self.onDownloadOpen, 'rDownloadOpenly')
            #else:
            self.utility.makePopup(rightMouse, self.onDownloadSecret, 'rDownloadSecretly')
            
            # if in library:
        elif self.standardOverview.mode == "libraryMode":
            self.utility.makePopup(rightMouse, self.onRecommend, 'rRecommend')        
            rightMouse.AppendSeparator()
            self.utility.makePopup(rightMouse, None, 'rLibraryOptions')
            self.utility.makePopup(rightMouse, self.onOpenFileDest, 'rOpenfilename')
            self.utility.makePopup(rightMouse, self.onOpenDest, 'rOpenfiledestination')
            self.utility.makePopup(rightMouse, self.onDeleteTorrentFromLibrary, 'rRemoveFromList')
            self.utility.makePopup(rightMouse, self.onDeleteTorrentFromDisk, 'rRemoveFromListAndHD')  
        elif self.standardOverview.mode == "personsMode" or self.standardOverview.mode == "friendsMode":     
            if item.get('friend'):
                self.utility.makePopup(rightMouse, self.onChangeFriendStatus, 'rRemoveAsFriend')
            else:
                self.utility.makePopup(rightMouse, self.onChangeFriendStatus, 'rAddAsFriend')
            
            # if in friends:
            if self.standardOverview.mode == "friendsMode":
                rightMouse.AppendSeparator()
                self.utility.makePopup(rightMouse, None, 'rFriendsOptions')
                self.utility.makePopup(rightMouse, None, 'rSendAMessage')
        elif self.standardOverview.mode == "subscriptionsMode":
            self.utility.makePopup(rightMouse, None, 'rChangeSubscrTitle')
            self.utility.makePopup(rightMouse, None, 'rRemoveSubscr')
            

        
        return (rightMouse)
        #self.PopupMenu(rightMouse, (-1,-1))  
        
# ================== actions for rightMouse button ========================================== 
    def onOpenFileDest(self, event = None):
        # open File
        item = self.standardDetails.getData()
        abctorrent = item.get('abctorrent')
        
        if abctorrent:
            abctorrent.files.onOpenFileDest(index = abctorrent.listindex)
        else:
            print "niet gelukt"
            # TODO: TB> This state doesn't occur because torrents stay active, when tribler is 
            #       closed within 1 hour after torrent is stopped or finished (see action.py)
            #       This else statement is also empty for the playback button
  
    def onOpenDest(self, event = None):
        # open Destination
        item = self.standardDetails.getData()
        abctorrent = item.get('abctorrent')
        
        if abctorrent:
            abctorrent.files.onOpenDest(index = abctorrent.listindex)
        else:
            print "niet gelukt"
            
    def onDeleteTorrentFromDisk(self, event = None):
        item = self.standardDetails.getData()
        abctorrent = item.get('abctorrent')
        
        if abctorrent:
            self.utility.actionhandler.procREMOVE([abctorrent], removefiles = True)
        self.standardOverview.removeTorrentFromLibrary(item)
                
    def onDeleteTorrentFromLibrary(self, event = None):
        item = self.standardDetails.getData()
        abctorrent = item.get('abctorrent')
        
        if abctorrent:
            self.utility.actionhandler.procREMOVE([abctorrent], removefiles = False)
        self.standardOverview.removeTorrentFromLibrary(item)
        
    def onModerate(self, event = None):
        print '---tb--- Moderate event'
        print event
        # todo
        event.Skip()
    
    def onRecommend(self, event = None):
        # todo
        event.Skip()
   
    def onDownloadOpen(self, event = None):
        item = self.standardDetails.getData()
        self.standardDetails.download(item)
        event.Skip()
    
    def onDownloadSecret(self, event = None):
        # todo secret download
        self.onDownloadOpen(event)
        event.Skip()
        
    def onChangeFriendStatus(self, event = None):
        self.standardDetails.addAsFriend()
        self.standardOverview.refreshData()
        event.Skip()
        
# =========END ========= actions for rightMouse button ==========================================
        
