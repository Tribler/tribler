import wx
from wx import xrc
from traceback import print_exc,print_stack
from threading import Event
import urllib
import webbrowser

from bgPanel import *
import updateXRC
from Tribler.TrackerChecking.ManualChecking import SingleManualChecking
from Tribler.CacheDB.CacheDBHandler import MyDBHandler
from Tribler.Overlay.permid import permid_for_user

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
        elif name == "addAsFriend":
            self.standardDetails.addAsFriend()
        elif name == 'download':
            self.standardDetails.download()
        elif name == 'addFriends':
            print "PARENT IS",obj.GetParent().GetName() # obj.GetParent().GetName() == "friendsOverview":
            self.emailFriend(event)
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
                print 'A button was clicked, but no action is defined for: %s' % name
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
            
    def standardFilesOverview(self, filters = ['video', 'swarmsize']):        
        
        self.standardOverview.setMode('filesMode')
        self.standardOverview.filterChanged(filters)
        try:
            if self.standardDetails:
                self.standardDetails.setMode('filesMode', None)
        except:
            pass
        
    def standardPersonsOverview(self, filters = ['', '']):
        
        self.standardOverview.setMode('personsMode')
        self.standardOverview.filterChanged(filters)
        self.standardDetails.setMode('personsMode')
        
    def standardFriendsOverview(self, filters = ['friends','']):
        self.categorykey = "friends"
        self.standardOverview.setMode('friendsMode')
        self.standardOverview.filterChanged(filters)
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
  
            
    
   
        
   
    def initStandardOverview(self, standardOverview):
        "Called by standardOverview when ready with init"
        self.standardOverview = standardOverview
        self.peer_manager = standardOverview.peer_manager
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
        
