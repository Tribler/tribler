import os
import wx
import wx.xrc as xrc
import random

from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.tribler_topButton import tribler_topButton
from Tribler.Core.CacheDB.CacheDBHandler import MyDBHandler
from Tribler.Main.Dialogs.MugshotManager import MugshotManager
from Tribler.Main.Dialogs.socnetmyinfo import MyInfoWizard
from Tribler.Core.CacheDB.CacheDBHandler import MyPreferenceDBHandler
from Tribler.Core.CacheDB.CacheDBHandler import BarterCastDBHandler
from time import time
from traceback import print_exc
from Tribler.Main.vwxGUI.TriblerStyles import TriblerStyles
import urllib

class statsOverviewPanel(wx.Panel):
    def __init__(self, *args, **kw):
#        print "<mluc> tribler_topButton in init"
        self.initDone = False
        self.elementsName = ['top10', 'top10Panel', 'perf', 'perfPanel','totalBT', 'totalBTPanel', 
                             'totalTribler', 'totalTriblerPanel','networkDisc', 'networkDiscPanel',
                             'yrNetwork', 'yrNetworkPanel',
                             'files', 'persons', 'numberFiles', 'numberPersons',
                             'bgPanel_Overall', 'perf_Overall', 'icon_Overall', 'text_Overall', 
                             'bgPanel_Quality', 'perf_Quality', 'text_Quality', 
                             'bgPanel_Files', 'perf_Files', 'text_Files', 
                             'bgPanel_Persons', 'perf_Persons', 'text_Persons', 
                             'bgPanel_Download', 'perf_Download', 'text_Download', 
                             'bgPanel_Presence', 'perf_Presence', 'text_Presence',
                             'downloadedNumber', 'uploadedNumber',
                             'descriptionField0', 'downloadedNumberT', 'uploadedNumberT']
        self.elements = {}
        self.data = {} #data related to profile information, to be used in details panel
        if len(args) == 0: 
            pre = wx.PrePanel() 
            # the Create step is done by XRC. 
            self.PostCreate(pre) 
            self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate) 
        else:
            wx.Panel.__init__(self, *args, **kw) 
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
        self.data_manager = self.guiUtility.standardOverview.data_manager
        self.bartercastdb = BarterCastDBHandler()
        self.mydb = MyPreferenceDBHandler()
#        self.Bind(wx.EVT_MOUSE_EVENTS, self.mouseAction)
#        self.Bind(wx.EVT_LEFT_UP, self.guiUtility.buttonClicked)
        for element in self.elementsName:
            xrcElement = xrc.XRCCTRL(self, element)
            if not xrcElement:
                print 'profileOverviewPanel: Error: Could not identify xrc element:',element
            self.elements[element] = xrcElement

#        self.getNameMugshot()

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
                    
#        self.getGuiElement('myNameField').SetLabel('')
        self.addComponents()
        self.setData()
        self.initDone = True
        
#        self.Update()
        self.initData()
        self.timer = None
        self.Bind(wx.EVT_SHOW, self.OnShow) 
        wx.CallAfter(self.reloadData)
        wx.CallAfter(self.Refresh)
    
    def addComponents(self):
        self.triblerStyles = TriblerStyles.getInstance()
        
        self.perfPanel = self.getGuiElement('perfPanel')
        self.perf = self.getGuiElement('perf')
        self.totalBTPanel = self.getGuiElement('totalBTPanel')
        self.totalBT = self.getGuiElement('totalBT')
        self.totalTriblerPanel = self.getGuiElement('totalTriblerPanel')
        self.totalTribler = self.getGuiElement('totalTribler')
        self.top10Panel = self.getGuiElement('top10Panel')
        self.top10 = self.getGuiElement('top10')
        self.networkDiscPanel = self.getGuiElement('networkDiscPanel')
        self.networkDisc = self.getGuiElement('networkDisc')
        self.yrNetworkPanel = self.getGuiElement('yrNetworkPanel')
        self.yrNetwork = self.getGuiElement('yrNetwork')
        self.files = self.getGuiElement('files')
        self.persons = self.getGuiElement('persons')
        self.numberFiles = self.getGuiElement('numberFiles')
        self.numberPersons = self.getGuiElement('numberPersons')
        
        self.triblerStyles.titleBar(self.perfPanel)
        self.triblerStyles.titleBar(self.perf)
        self.triblerStyles.titleBar(self.totalBTPanel)
        self.triblerStyles.titleBar(self.totalBT)
        self.triblerStyles.titleBar(self.totalTriblerPanel)
        self.triblerStyles.titleBar(self.totalTribler)        
        self.triblerStyles.titleBar(self.top10Panel)
        self.triblerStyles.titleBar(self.top10)
        self.triblerStyles.titleBar(self.networkDiscPanel)
        self.triblerStyles.titleBar(self.networkDisc)
        self.triblerStyles.titleBar(self.yrNetworkPanel)
        self.triblerStyles.titleBar(self.yrNetwork)
        self.triblerStyles.setDarkText(self.files)
        self.triblerStyles.setDarkText(self.persons)     
        self.triblerStyles.setDarkText(self.numberFiles)
        self.triblerStyles.setDarkText(self.numberPersons)    
        
        
    def setData(self):
        self.topNListText()
        self.numberFiles.SetLabel(str(self.guiUtility.data_manager.getNumDiscoveredFiles()))
        self.numberPersons.SetLabel(str(self.guiUtility.peer_manager.getNumEncounteredPeers()))
        
        
    def OnShow(self, evt):
#        print "<mluc> in onshow in profileOverviewPanel"
#        if evt.show:
#            print "<mluc> profileOverviewPanel is visible"
#            self.timer.Start() #restarts the timer
#        else:
#            print "<mluc> profileOverviewPanel is visible"
            pass
        #wx.CallAfter(self.reloadData())

#    def getNameMugshot(self):
#        my_db = MyDBHandler()
#        self.myname = my_db.get('name', '')
#        mypermid = my_db.getMyPermid()
#        mm = MugshotManager.getInstance()
#        self.mugshot = mm.load_wxBitmap(mypermid)
#        if self.mugshot is None:
#            print "profileOverviewPanel: Bitmap for mypermid not found"
#            self.mugshot = mm.get_default('personsMode','DEFAULT_THUMB')
        
#    def showNameMugshot(self):
#        self.getGuiElement('myNameField').SetLabel(self.myname)
#        thumbpanel = self.getGuiElement('thumb')
#        thumbpanel.setBitmap(self.mugshot)
        
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
#        elif source_name == "edit":
#            self.OnMyInfoWizard(event)

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
        
    def reloadData(self, event=None):
        """updates the fields in the panel with new data if it has changed"""
        
        if not self.IsShown(): #should not update data if not shown
            return
        #print "<mluc> profileOverviewPanel in reloadData"
        
#        self.showNameMugshot()

        bShouldRefresh = False
        max_index_bar = 5 #the maximal value the normal bar can have
        max_overall_index_bar = 6 #the maximal value the overall bar can have
        
        #--- Quality of tribler recommendation
        #<<<get the number of downloads for this user
        count = len(self.mydb.getPrefList())
        index_q = self.indexValue(count,100, max_index_bar) #from 0 to 5
        if count != self.quality_value:
            self.data['downloaded_files'] = count
            bShouldRefresh = True
            self.quality_value = count
            if self.getGuiElement("perf_Quality"):
                self.getGuiElement("perf_Quality").setIndex(index_q)
                    
        #--- Discovered files
        #<<<get the number of files
        count = int(self.guiUtility.data_manager.getNumDiscoveredFiles())
        index_f = self.indexValue(count,3000, max_index_bar) #from 0 to 5
        if count != self.discovered_files:
            self.data['discovered_files'] = count
            bShouldRefresh = True
            self.discovered_files = count
            if self.getGuiElement("perf_Files"):
                self.getGuiElement("perf_Files").setIndex(index_f)

        #--- Discovered persons
        #<<<get the number of peers
        count = int(self.guiUtility.peer_manager.getNumEncounteredPeers())
        index_p = self.indexValue(count,2000, max_index_bar) #from 0 to 5
        if count != self.discovered_persons:
            self.data['discovered_persons'] = count
            bShouldRefresh = True
            self.discovered_persons = count
            if self.getGuiElement("perf_Persons"):
                self.getGuiElement("perf_Persons").setIndex(index_p)

        #--- Optimal download speed
        #<<<set the download stuff
        index_1 = 0
        #get upload rate, download rate, upload slots: maxupload': '5', 'maxuploadrate': '0', 'maxdownloadrate': '0'
        maxuploadrate = self.guiUtility.utility.config.Read('maxuploadrate', 'int') #kB/s
#        maxuploadslots = self.guiUtility.utility.config.Read('maxupload', "int")
#        maxdownloadrate = self.guiUtility.utility.config.Read('maxdownloadrate', "int")
        if maxuploadrate == 0:
            index_1 = max_index_bar
        else: #between 0 and 100KB/s
            index_1 = self.indexValue(maxuploadrate,100, max_index_bar) #from 0 to 5
        #<<<set the reachability value
        index_2 = 0
        if self.guiUtility.isReachable():
            index_2 = max_index_bar
        #<<<get the number of friends
        count = self.guiUtility.peer_manager.getCountOfFriends()
        index_h = self.indexValue(count,20, max_index_bar) #from 0 to 5
        bMoreFriends = False
        if self.number_friends!=count:
            bMoreFriends = True
            self.number_friends = count
        index_s = self.indexValue(index_1+index_2+index_h, 3*max_index_bar, max_index_bar)
        if self.max_upload_rate!=maxuploadrate or self.is_reachable!=self.guiUtility.isReachable or bMoreFriends:
            self.data['number_friends']=count
            bShouldRefresh = True
            self.max_upload_rate = maxuploadrate
            self.is_reachable = self.guiUtility.isReachable
            if self.getGuiElement("perf_Download"):
                self.getGuiElement("perf_Download").setIndex(index_s)

        #--- Network reach
        #<<<get the number of friends
        #use index_h computed above
        #<<<get new version
        index_v = 0
        bCheckVersionChange = self.checkNewVersion()
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
            if self.getGuiElement("perf_Presence"):
                self.getGuiElement("perf_Presence").setIndex(index_n)

        #--- Overall performance
        #<<<set the overall performance to a random number
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
        topinfo = self.bartercastdb.getTopNPeers(0, local_only = True)
        up = self.utility.size_format(topinfo.get('total_up'))
        down = self.utility.size_format(topinfo.get('total_down'))
        old_up = self.getGuiElement('uploadedNumber').GetLabel()
        old_down = self.getGuiElement('downloadedNumber').GetLabel()
        if up != old_up:
            self.getGuiElement('uploadedNumber').SetLabel(up)
        if down != old_down:
            self.getGuiElement('downloadedNumber').SetLabel(down)
            
            
        if bShouldRefresh:
            self.Refresh()
            #also set data for details panel
            self.guiUtility.selectData(self.data)
        #wx.CallAfter(self.reloadData) #should be called from time to time
        if not self.timer:
            self.timer = wx.Timer(self, -1)
            self.Bind(wx.EVT_TIMER, self.reloadData, self.timer)
            self.timer.Start(5000)
        
#    def OnMyInfoWizard(self, event = None):
#        wizard = MyInfoWizard(self)
#        wizard.RunWizard(wizard.getFirstPage())

#    def WizardFinished(self,wizard):
#        wizard.Destroy()
#
#        self.getNameMugshot()
#        self.showNameMugshot()

    def checkNewVersion(self):
        """check for new version on the website
        saves compare result between version on site and the 
        one the user has, that means a value of -1,0,1, or -2 if there was an 
        error connecting; and url for new version
        the checking is done once each day day the client runs
        returns True if anything changed, False otherwise"""
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
    
    def topNListText(self):
        if not self.bartercastdb:
            self.bartercastdb = BarterCastDBHandler()
        
        top_stats = self.bartercastdb.getTopNPeers(10)
        top = top_stats['top']
        #total_up = top_stats['total_up']
        #total_down = top_stats['total_down']
        tribler_up = top_stats['tribler_up']
        tribler_down = top_stats['tribler_down']
        
        rank = 1
        topText = ''
        for permid, up, down in top:
            
            # up and down are integers in KB in the database
            # (for overhead limitation)
            amount_str_up = self.utility.size_format(up)
            amount_str_down = self.utility.size_format(down)

            name = self.bartercastdb.getName(permid)

            topText += '%d. %s%s     up: %s (down: %s)%s%s' % (rank, name, os.linesep, 
                                                     amount_str_up, amount_str_down, os.linesep, os.linesep)
            rank+=1
        
        self.getGuiElement('descriptionField0').SetLabel(topText)
        self.getGuiElement('descriptionField0').Refresh()
        self.getGuiElement('downloadedNumberT').SetLabel(self.utility.size_format(tribler_down))
        self.getGuiElement('uploadedNumberT').SetLabel(self.utility.size_format(tribler_up))
        
#    def getInstance(*args, **kw):
#        if standardDetails.__single is None:
#            standardDetails(*args, **kw)
#        return standardDetails.__single
#    getInstance = staticmethod(getInstance)