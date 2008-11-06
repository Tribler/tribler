# Written by Jelle Roozenburg, Maarten ten Brinke 
# see LICENSE.txt for license information
import wx
import wx.xrc as xrc
import random, sys
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.tribler_topButton import tribler_topButton
from Tribler.Main.vwxGUI.IconsManager import IconsManager, data2wxBitmap
from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue
from Tribler.Main.Dialogs.socnetmyinfo import MyInfoWizard
from Tribler.Core.simpledefs import *
from time import time
from traceback import print_exc,print_stack
import urllib

RELOAD_DELAY = 60 * 1000 # milliseconds

class ProfileOverviewPanel(wx.Panel):
    def __init__(self, *args, **kw):
#        print "<mluc> tribler_topButton in init"
        self.initDone = False
        self.elementsName = [ 'bgPanel_Overall', 'perf_Overall', 'icon_Overall', 'text_Overall', 
                             'bgPanel_Quality', 'perf_Quality', 'text_Quality', 
                             'bgPanel_Files', 'perf_Files', 'text_Files', 
                             'bgPanel_Persons', 'perf_Persons', 'text_Persons', 
                             'bgPanel_Download', 'perf_Download', 'text_Download', 
                             'bgPanel_Presence', 'perf_Presence', 'text_Presence',
                             'myNameField', 'thumb', 'edit', 'downloadedNumber', 'uploadedNumber']
        self.elements = {}
        self.data = {} #data related to profile information, to be used in details panel
        self.mypref = None
        self.reload_counter = -1
        self.reload_cache = [None, None, None]
        
        # SELDOM cache
        self.bartercast_db = None
        self.barterup = 0
        self.barterdown = 0
        
        if len(args) == 0: 
            pre = wx.PrePanel() 
            # the Create step is done by XRC. 
            self.PostCreate(pre) 
            self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate) 
        else:
            wx.Panel.__init__(self, *args, **kw) 
            self._PostInit()     
        
    def OnCreate(self, event):
#        print "<mluc> tribler_topButton in OnCreate"
        self.Unbind(wx.EVT_WINDOW_CREATE)
        wx.CallAfter(self._PostInit)
        event.Skip()
        return True
    
    def _PostInit(self):
        #print >>sys.stderr,"profileOverviewPanel: in _PostInit"
        # Do all init here
        self.guiUtility = GUIUtility.getInstance()
        
        self.utility = self.guiUtility.utility
        # All mainthread, no need to close
        self.torrent_db = self.guiUtility.utility.session.open_dbhandler(NTFY_TORRENTS)
        self.peer_db = self.guiUtility.utility.session.open_dbhandler(NTFY_PEERS)
        self.friend_db = self.guiUtility.utility.session.open_dbhandler(NTFY_FRIENDS)
        self.bartercast_db = self.guiUtility.utility.session.open_dbhandler(NTFY_BARTERCAST)
        self.mypref = self.guiUtility.utility.session.open_dbhandler(NTFY_MYPREFERENCES)
#        self.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)
#        self.Bind(wx.EVT_LEFT_UP, self.guiUtility.buttonClicked)
        for element in self.elementsName:
            xrcElement = xrc.XRCCTRL(self, element)
            if not xrcElement:
                print 'profileOverviewPanel: Error: Could not identify xrc element:',element
            self.elements[element] = xrcElement

        self.getNameMugshot()

        self.buttons = []
        #add mouse over text and progress icon
        for elem_name in self.elementsName:
            if elem_name.startswith("bgPanel_"):
                self.buttons.append(elem_name)
                but_elem = self.getGuiElement(elem_name)
                but_elem.setBackground(wx.Colour(203,203,203))
                suffix = elem_name[8:]
                text_elem = self.getGuiElement('text_%s' % suffix)
                perf_elem = self.getGuiElement('perf_%s' % suffix)
                icon_elem = self.getGuiElement('icon_%s' % suffix)
                if isinstance(self.getGuiElement(elem_name),tribler_topButton) :
                    if text_elem:
                        text_elem.Bind(wx.EVT_MOUSE_EVENTS, but_elem.mouseAction)
                    if perf_elem:
                        perf_elem.Bind(wx.EVT_MOUSE_EVENTS, but_elem.mouseAction)
                    if icon_elem:
                        icon_elem.Bind(wx. EVT_MOUSE_EVENTS, but_elem.mouseAction)
                else:
                    but_elem.Bind(wx.EVT_LEFT_UP, self.guiUtility.buttonClicked)
                if text_elem:
                    text_elem.Bind(wx.EVT_LEFT_UP, self.sendClick)
                if perf_elem:
                    perf_elem.Bind(wx.EVT_LEFT_UP, self.sendClick)
                if icon_elem:
                    icon_elem.Bind(wx.EVT_LEFT_UP, self.sendClick)
                    
        self.getGuiElement('myNameField').SetLabel('')
        self.initDone = True
        
#        self.Update()
        self.initData()
        self.timer = None
        self.Bind(wx.EVT_SHOW, self.OnShow)

        self.newversion = False
        self.checkNewVersion()
        self.seldomReloadData()
         
        wx.CallAfter(self.reloadData)
        wx.CallAfter(self.Refresh)
        
    def OnShow(self, evt):
#        print "<mluc> in onshow in profileOverviewPanel"
#        if evt.show:
#            print "<mluc> profileOverviewPanel is visible"
#            self.timer.Start() #restarts the timer
#        else:
#            print "<mluc> profileOverviewPanel is visible"
            pass
        #wx.CallAfter(self.reloadData())

    def getNameMugshot(self):
        self.myname = self.utility.session.get_nickname()
        mime, data = self.utility.session.get_mugshot()
        if data is None:
            im = IconsManager.getInstance()
            self.mugshot = im.get_default('personsMode','DEFAULT_THUMB')
        else:
            self.mugshot = data2wxBitmap(mime, data)
        
    def showNameMugshot(self):
        self.getGuiElement('myNameField').SetLabel(self.myname)
        thumbpanel = self.getGuiElement('thumb')
        thumbpanel.setBitmap(self.mugshot)
        
    def sendClick(self, event):
        source = event.GetEventObject()
        source_name = source.GetName()
#        print "<mluc> send event from",source_name
        if source_name.startswith('text_') or source_name.startswith('perf_') or source_name.startswith('icon_'):
            #send event to background button
            but_name = 'bgPanel_'+source_name[5:]
            self.selectNewButton(but_name)
#            print "<mluc> send event to",but_name
            new_owner = self.getGuiElement(but_name)
            event.SetEventObject(new_owner)
            wx.PostEvent( new_owner, event)
        elif source_name.startswith('bgPanel_'):
            self.selectNewButton(source_name)
        elif source_name == "edit":
            self.OnMyInfoWizard(event)

    def selectNewButton(self, sel_but):
        for button in self.buttons:
            butElem = self.getGuiElement(button)
            if button == sel_but:
                if isinstance(butElem,tribler_topButton):
                    butElem.setSelected(True)
            elif isinstance(butElem, tribler_topButton) and butElem.isSelected():
                butElem.setSelected(False)

    def getGuiElement(self, name):
        if not self.elements.has_key(name) or not self.elements[name]:
#            print "[profileOverviewPanel] gui element %s not available" % name
            return None
        return self.elements[name]
    
    def indexValue(self, value, max_value, max_index=5):
        """given a value and a maximal value, computes an index from 0 to max_index 
        so that when value >= max_value, it returns max_index
        uses an algorithm that complies to this example:
        max_index = 5
        max_value = 100
        |---------------|
        | value | index |
        |---------------|
        |   0   |   0   |
        |  1-24 |   1   |
        | 25-49 |   2   |
        | 50-74 |   3   |
        | 75-99 |   4   |
        | >=100 |   5   |
        |---------------|
        """
        if max_index <= 0:
            return 0
        if value <= 0:
            return 0
        if value >= max_value:
            return max_index
        index = 1 + int(value * (max_index-1) / max_value)
        if index > max_index:
            index = max_index
        if index < 0:
            index = 0
        return index
    
    def initData(self):
        self.quality_value = -1
        self.discovered_files = -1
        self.discovered_persons = -1
        self.number_friends = -1
        self.max_upload_rate = -1
        self.is_reachable = False
        self.last_version_check_time = -1
        self.update_url = 'http://tribler.org'
        self.new_version = 'unknown'
        self.check_result = -3 #unknown check result, -2 means error, -1 means newer version on the client, 0 means same version, 1 means newer version on the website
        self.nat_type = -1
        
    def reloadData(self, event=None):
        """updates the fields in the panel with new data if it has changed"""

        #print >>sys.stderr,"profileOverviewPanel: reloadData, shown is",self.IsShown()

        if not self.IsShown(): #should not update data if not shown
            return
            
        #print "<mluc> profileOverviewPanel in reloadData"
        
        # 28/07/08 boudewijn: the reloadData method is called every
        # twice when first displayed and every 5 seconds
        # afterwards. We do not need to recalculate all the statistics
        # on each of these calls. The self.reload_counter ensures that
        # either the preference list, the number of torrents, or the
        # number of peers is calculated during a single run of this
        # method.
        if self.reload_counter >= 3:
            self.reload_counter = 0
        else:
            self.reload_counter += 1

        self.showNameMugshot()

        bShouldRefresh = False
        max_index_bar = 5 #the maximal value the normal bar can have
        max_overall_index_bar = 6 #the maximal value the overall bar can have

        #--- Quality of tribler recommendation
        #get the number of downloads for this user
        if self.reload_counter == 0 or self.reload_cache[0] is None:
            count = len(self.mypref.getMyPrefList())
            index_q = self.indexValue(count,100, max_index_bar) #from 0 to 5
            if count != self.quality_value:
                self.data['downloaded_files'] = count
                bShouldRefresh = True
                self.quality_value = count
                guiElement = self.getGuiElement("pref_Quality")
                if guiElement:
                    guiElement.setIndex(index_q)
            self.reload_cache[0] = index_q
        else:
            index_q = self.reload_cache[0]

        #--- Discovered files
        #get the number of files
        if self.reload_counter == 1 or self.reload_cache[1] is None:
            count = int(self.torrent_db.getNumberTorrents())
            index_f = self.indexValue(count,3000, max_index_bar) #from 0 to 5
            if count != self.discovered_files:
                self.data['discovered_files'] = count
                bShouldRefresh = True
                self.discovered_files = count
                guiElement = self.getGuiElement("perf_Files")
                if guiElement:
                    guiElement.setIndex(index_f)
            self.reload_cache[1] = index_f
        else:
            index_f = self.reload_cache[1]

        #--- Discovered persons
        #get the number of peers
        if self.reload_counter == 2 or self.reload_cache[2] is None:
            count = int(self.peer_db.getNumberPeers())
            index_p = self.indexValue(count,2000, max_index_bar) #from 0 to 5
            if count != self.discovered_persons:
                self.data['discovered_persons'] = count
                bShouldRefresh = True
                self.discovered_persons = count
                guiElement = self.getGuiElement("perf_Persons")
                if guiElement:
                    guiElement.setIndex(index_p)
            self.reload_cache[2] = index_p
        else:
            index_p = self.reload_cache[2]

        #--- Optimal download speed
        #set the download stuff
        index_1 = 0
        #get upload rate, download rate, upload slots: maxupload': '5', 'maxuploadrate': '0', 'maxdownloadrate': '0'
        maxuploadrate = self.guiUtility.utility.config.Read('maxuploadrate', 'int') #kB/s
#        maxuploadslots = self.guiUtility.utility.config.Read('maxupload', "int")
#        maxdownloadrate = self.guiUtility.utility.config.Read('maxdownloadrate', "int")
        if maxuploadrate == 0:
            index_1 = max_index_bar
        else: #between 0 and 100KB/s
            index_1 = self.indexValue(maxuploadrate,100, max_index_bar) #from 0 to 5
        #set the reachability value
        index_2 = 0
        if self.guiUtility.isReachable():
            index_2 = max_index_bar
        #get the number of friends
        count = len(self.friend_db.getFriends())
        index_h = self.indexValue(count,20, max_index_bar) #from 0 to 5
        bMoreFriends = False
        if self.number_friends!=count:
            bMoreFriends = True
            self.number_friends = count
        index_s = self.indexValue(index_1+index_2+index_h, 3*max_index_bar, max_index_bar)
        if self.max_upload_rate!=maxuploadrate or self.is_reachable!=self.guiUtility.isReachable or bMoreFriends:
            self.data['number_friends']=count

        #get the NAT type
        natinfo = self.guiUtility.get_nat_type()
        natChange = False
        if self.nat_type!=natinfo:
            natChange = True
            self.nat_type= natinfo
        if self.max_upload_rate!=maxuploadrate or self.is_reachable!=self.guiUtility.isReachable or natChange:
            self.data['nat_type']=natinfo

            bShouldRefresh = True
            self.max_upload_rate = maxuploadrate
            self.is_reachable = self.guiUtility.isReachable
            guiElement = self.getGuiElement("perf_Download")
            if guiElement:
                guiElement.setIndex(index_s)

        #--- Network reach
        #get the number of friends
        #use index_h computed above
        #get new version
        index_v = 0
        bCheckVersionChange = self.newversion
        if bCheckVersionChange:
            self.data['new_version']=self.new_version
            self.data['update_url'] = self.update_url
            self.data['compare_result'] = self.check_result
        if self.check_result == -1: #it means the user has a newer version, that's good
            index_v = max_index_bar
        elif self.check_result == 0: #it means the same version user has as on web site
            index_v = max_index_bar
        else: #for 1, -2, -3 cases, the version isn't good enough
            index_v = 0
        index_n = self.indexValue(index_h+index_v, 2*max_index_bar, max_index_bar)
        if bMoreFriends or bCheckVersionChange:
            bShouldRefresh = True
            guiElement = self.getGuiElement("perf_Presence")
            if guiElement:
                guiElement.setIndex(index_n)

        #--- Overall performance
        #set the overall performance to a random number
        overall_index = self.indexValue(index_q+index_p+index_f+index_s+index_n, 5*max_index_bar, max_overall_index_bar)
        elem = self.getGuiElement("perf_Overall")
        if overall_index != elem.getIndex() or self.data.get('overall_rank') is None:
            elem.setIndex(overall_index)
            if overall_index < 2:
                self.data['overall_rank'] = "beginner"
            elif overall_index < 3:
                self.data['overall_rank'] = "experienced"
            elif overall_index < 5:
                self.data['overall_rank'] = "top user"
            else:
                self.data['overall_rank'] = "master"
            self.getGuiElement('text_Overall').SetLabel("Overall performance (%s)" % self.data['overall_rank'])
            bShouldRefresh = True
        
        # --- Upload and download amounts
        # Arno: this involves reading a potentially huge db, do only on
        # clicks that show overview panel. See seldomReloadData()
            
        old_up = self.getGuiElement('uploadedNumber').GetLabel()
        old_down = self.getGuiElement('downloadedNumber').GetLabel()
        if self.barterup != old_up:
            self.getGuiElement('uploadedNumber').SetLabel(self.barterup)
        if self.barterdown != old_down:
            self.getGuiElement('downloadedNumber').SetLabel(self.barterdown)
            
            
        if bShouldRefresh:
            self.Refresh()
            #also set data for details panel
            self.guiUtility.selectData(self.data)
        #wx.CallAfter(self.reloadData) #should be called from time to time
        if not self.timer:
            self.timer = wx.Timer(self, -1)
            self.Bind(wx.EVT_TIMER, self.reloadData, self.timer)
            self.timer.Start(RELOAD_DELAY)


    def seldomReloadData(self):
        #print >>sys.stderr,"profileOverviewPanel: seldomReloadData!!!!!!" 
        
        if self.bartercast_db is None:
            up = 'n/a'
            down = 'n/a'
        else:
            topinfo = self.bartercast_db.getTopNPeers(0, local_only = True)
            up = self.utility.size_format(topinfo.get('total_up'))
            down = self.utility.size_format(topinfo.get('total_down'))

        self.barterup = up
        self.barterdown = down


    def OnMyInfoWizard(self, event = None):
        wizard = MyInfoWizard(self)
        wizard.RunWizard(wizard.getFirstPage())

    def WizardFinished(self,wizard):
        wizard.Destroy()

        self.getNameMugshot()
        self.showNameMugshot()

    def checkNewVersion(self):
        # delegate to GUIServer
        guiserver = GUITaskQueue.getInstance()
        guiserver.add_task(self.guiserver_checkVersion,0)
        
    def guiserver_checkVersion(self):
        self.guiserver_DoCheckVersion()
        wx.CallAfter(self.setVersion)
        
    def setVersion(self):
        self.reloadData()
        
    def guiserver_DoCheckVersion(self):
        """check for new version on the website
        saves compare result between version on site and the 
        one the user has, that means a value of -1,0,1, or -2 if there was an 
        error connecting; and url for new version
        the checking is done once each day day the client runs
        returns True if anything changed, False otherwise"""
        
        # TODO: make sure there is no concurrency on the self.* fields
        
        if self.last_version_check_time!=-1 and time() - self.last_version_check_time < 86400:
            return False#check for a new version once a day
        self.last_version_check_time = time()
        bChanged = False
        my_version = self.utility.getVersion()
        try:
            curr_status = urllib.urlopen('http://tribler.org/version').readlines()
            line1 = curr_status[0]
            if len(curr_status) > 1:
                new_url = curr_status[1].strip()
                if self.update_url!=new_url:
                    self.update_url = new_url
                    bChanged = True
            _curr_status = line1.split()
            new_version = _curr_status[0]
            if new_version != self.new_version:
                self.new_version = new_version
                bChanged = True
            result = self.compareVersions(self.new_version, my_version)
            if result != self.check_result:
                self.check_result = result
                bChanged = True
        except:
            print_exc()
            if self.check_result!=-2:
                self.check_result = -2
                bChanged = True
        return bChanged
        
    def compareVersions(self, curr_version, my_version):
        """compares two version strings, copied from Dialogs.aboutme.py
        changed the return value: 1 for newer version on the website,
        0 for same version, -1 for newer version on the client"""
        curr = curr_version.split('.')
        my = my_version.split('.')
        if len(my) >= len(curr):
            nversion = len(my)
        else:
            nversion = len(curr)
        for i in range(nversion):
            if i < len(my):
                my_v = int(my[i])
            else:
                my_v = 0
            if i < len(curr):
                curr_v = int(curr[i])
            else:
                curr_v = 0
            if curr_v > my_v:
                return 1
            elif curr_v < my_v:
                return -1
        return 0 

