# Written by Richard Gwin
# see LICENSE.txt for license information
import wx
import wx.xrc as xrc
import random, sys
from time import time
from traceback import print_exc,print_stack
import urllib

from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.tribler_topButton import tribler_topButton
from Tribler.Main.vwxGUI.IconsManager import IconsManager, data2wxBitmap
from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue
from Tribler.Main.Dialogs.socnetmyinfo import MyInfoWizard
from Tribler.Main.globals import DefaultDownloadStartupConfig
from Tribler.Core.simpledefs import *
from Tribler.Core.SessionConfig import SessionConfigInterface

from wx.wizard import Wizard,WizardPageSimple,EVT_WIZARD_PAGE_CHANGED,EVT_WIZARD_PAGE_CHANGING,EVT_WIZARD_CANCEL,EVT_WIZARD_FINISHED


RELOAD_DELAY = 60 * 1000 # milliseconds

class SettingsOverviewPanel(wx.Panel):
    def __init__(self, *args, **kw):
#        print "<mluc> tribler_topButton in init"
        self.initDone = False
        self.elementsName = ['myNameField', 'thumb', 'edit','firewallValue','firewallStatus','uploadCtrl','downloadCtrl','zeroUp','fiftyUp','hundredUp','zeroDown','fiftyDown','hundredDown','diskLocationCtrl']
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
        #print >>sys.stderr,"settingsOverviewPanel: in _PostInit"
        # Do all init here
        self.guiUtility = GUIUtility.getInstance()

        self.standardOverview = self.guiUtility.standardOverview

        self.defaultDLConfig = DefaultDownloadStartupConfig.getInstance()


        self.firewallStatus = xrc.XRCCTRL(self,"firewallStatus")  

      
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
                print 'settingsOverviewPanel: Error: Could not identify xrc element:',element
            self.elements[element] = xrcElement

        self.getNameMugshot()
        self.showNameMugshot()
        #self.getGuiElement('myNameField').SetLabel('')


        #self.elements['firewallValue'].Bind(wx.EVT_KEY_DOWN,self.OnPortChange)

        self.elements['zeroUp'].Bind(wx.EVT_LEFT_UP, self.zeroUp)
        self.elements['fiftyUp'].Bind(wx.EVT_LEFT_UP, self.fiftyUp)
        self.elements['hundredUp'].Bind(wx.EVT_LEFT_UP, self.hundredUp)
        self.elements['zeroDown'].Bind(wx.EVT_LEFT_UP, self.zeroDown)
        self.elements['fiftyDown'].Bind(wx.EVT_LEFT_UP, self.fiftyDown)
        self.elements['hundredDown'].Bind(wx.EVT_LEFT_UP, self.hundredDown)


        self.elements['uploadCtrl'].Bind(wx.EVT_KEY_DOWN, self.uploadCtrlEnter)
        self.elements['downloadCtrl'].Bind(wx.EVT_KEY_DOWN, self.downloadCtrlEnter)
        self.elements['diskLocationCtrl'].Bind(wx.EVT_KEY_DOWN, self.diskLocationCtrlEnter)



        self.showPort()
       
        self.showMaxDLRate()
        self.showMaxULRate()

        self.showDiskLocation() # sic

        self.initDone = True
        
#        self.Update()
#        self.initData()
        self.timer = None
        self.Bind(wx.EVT_SHOW, self.OnShow)
         
        wx.CallAfter(self.Refresh)
        
    def OnShow(self, evt):
#        print "<mluc> in onshow in settingsOverviewPanel"
#        if evt.show:
#            print "<mluc> settingsOverviewPanel is visible"
#            self.timer.Start() #restarts the timer
#        else:
#            print "<mluc> settingsOverviewPanel is visible"
            pass
        #wx.CallAfter(self.reloadData)

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
        thumbpanel.createBackgroundImage()
        thumbpanel.setBitmap(self.mugshot)
        
    def sendClick(self, event):
        source = event.GetEventObject()
        source_name = source.GetName()
        if source_name == "edit":
            self.OnMyInfoWizard(event)
        elif source_name == "browse":
            self.BrowseClicked(event)


    def showPort(self):
        self.elements['firewallValue'].SetValue(str(self.guiUtility.get_port_number()))



    def showMaxDLRate(self):
        maxdownloadrate = self.guiUtility.utility.config.Read('maxdownloadrate', 'int') #kB/s
        self.elements['downloadCtrl'].SetValue(str(maxdownloadrate))        



    def showMaxULRate(self):
        maxuploadrate = self.guiUtility.utility.config.Read('maxuploadrate', 'int') #kB/s
        self.elements['uploadCtrl'].SetValue(str(maxuploadrate))        


    def showDiskLocation(self):
        print >>sys.stderr,"settingsOverviewPanel: SETTING DEFAULT DEST DIR"
        path = self.defaultDLConfig.get_dest_dir()
        self.elements['diskLocationCtrl'].SetValue(path)


    def zeroUp(self, event):
        self.elements['uploadCtrl'].SetValue('0') 
        self.guiUtility.utility.config.Write('maxuploadrate', '0')
        self.utility.ratelimiter.set_global_max_speed(UPLOAD, 0)

    def fiftyUp(self, event):
        self.elements['uploadCtrl'].SetValue('50')        
        self.guiUtility.utility.config.Write('maxuploadrate', '50')
        self.utility.ratelimiter.set_global_max_speed(UPLOAD, 50)


    def hundredUp(self, event):
        self.elements['uploadCtrl'].SetValue('100')        
        self.guiUtility.utility.config.Write('maxuploadrate', '100')
        self.utility.ratelimiter.set_global_max_speed(UPLOAD, 100)


    def zeroDown(self, event):
        self.elements['downloadCtrl'].SetValue('0')        
        self.guiUtility.utility.config.Write('maxdownloadrate', '0')
        self.utility.ratelimiter.set_global_max_speed(DOWNLOAD, 0)

    def fiftyDown(self, event):
        self.elements['downloadCtrl'].SetValue('50')        
        self.guiUtility.utility.config.Write('maxdownloadrate', '50')
        self.utility.ratelimiter.set_global_max_speed(DOWNLOAD, 50)


    def hundredDown(self, event):
        self.elements['downloadCtrl'].SetValue('100')        
        self.guiUtility.utility.config.Write('maxdownloadrate', '100')
        self.utility.ratelimiter.set_global_max_speed(DOWNLOAD, 100)


    def uploadCtrlEnter(self, event):
        keycode = event.GetKeyCode()
        if keycode == wx.WXK_RETURN and self.elements['uploadCtrl'].GetValue().strip() != '':
            self.utility.ratelimiter.set_global_max_speed(UPLOAD,int(self.elements['uploadCtrl'].GetValue()))
            self.standardOverview.updateSaveIcon()
        else:
            event.Skip()     

     
    def downloadCtrlEnter(self, event):
        keycode = event.GetKeyCode()
        if keycode == wx.WXK_RETURN and self.elements['downloadCtrl'].GetValue().strip() != '':
            self.utility.ratelimiter.set_global_max_speed(DOWNLOAD,int(self.elements['downloadCtrl'].GetValue()))
            self.standardOverview.updateSaveIcon()
        else:
            event.Skip()     


    def diskLocationCtrlEnter(self, event):
        keycode = event.GetKeyCode()
        if keycode == wx.WXK_RETURN and self.elements['diskLocationCtrl'].GetValue().strip() != '':
            self.defaultDLConfig.set_dest_dir(self.elements['diskLocationCtrl'].GetValue())
            self.standardOverview.updateSaveIcon()
        else:
            event.Skip()     




    def getGuiElement(self, name):
        if not self.elements.has_key(name) or not self.elements[name]:
#            print "[settingsOverviewPanel] gui element %s not available" % name
            return None
        return self.elements[name]
    
        self.nat_type = -1
        
    def reloadData(self, event=None):
        """updates the fields in the panel with new data if it has changed"""

        #print >>sys.stderr,"settingsOverviewPanel: reloadData, shown is",self.IsShown()

        if not self.IsShown(): #should not update data if not shown
            return
            
        #print "<mluc> settingsOverviewPanel in reloadData"
        
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



    def BrowseClicked(self, event = None):
        dlg = wx.DirDialog(self,"Choose download directory", style = wx.DEFAULT_DIALOG_STYLE)
        dlg.SetPath(self.defaultDLConfig.get_dest_dir())
        if dlg.ShowModal() == wx.ID_OK:
            self.defaultDLConfig.set_dest_dir(dlg.GetPath())
            self.elements['diskLocationCtrl'].SetValue(dlg.GetPath())
            self.standardOverview.updateSaveIcon()
        else:
            pass


    def OnMyInfoWizard(self, event = None):
        wizard = MyInfoWizard(self)
        wizard.RunWizard(wizard.getFirstPage())

    def WizardFinished(self,wizard):
        wizard.Destroy()

        self.getNameMugshot()
        self.showNameMugshot()

 
