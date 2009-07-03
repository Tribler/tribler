# Written by Richard Gwin
# see LICENSE.txt for license information
import wx
import wx.xrc as xrc
import sys, os
import cStringIO


from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.IconsManager import IconsManager, data2wxImage, data2wxBitmap
from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue
from Tribler.Main.Dialogs.socnetmyinfo import MyInfoWizard
from Tribler.Main.globals import DefaultDownloadStartupConfig,get_default_dscfg_filename
from Tribler.Core.simpledefs import *



#fonts
if sys.platform == 'darwin':
    FONT_SIZE_PROFILE_TITLE=12    
    FONT_SIZE_SHARING_TITLE=12    
    FONT_SIZE_FIREWALL_TITLE=12    
    FONT_SIZE_FILE_TEXT=12    

else:
    FONT_SIZE_PROFILE_TITLE=10    
    FONT_SIZE_SHARING_TITLE=10    
    FONT_SIZE_FIREWALL_TITLE=10    
    FONT_SIZE_FILE_TEXT=10    





class SettingsOverviewPanel(wx.Panel):
    def __init__(self, *args, **kw):
#        print "<mluc> tribler_topButton in init"
        self.initDone = False
        self.elementsName = ['profileTitle', \
                             'sharingTitle', \
                             'firewallTitle', \
                             'fileText', \
                             'myNameField', \
                             'thumb', \
                             'edit', \
                             'firewallValue', \
                             'firewallStatusText', \
                             'firewallStatus', \
                             'uploadCtrl', \
                             'downloadCtrl', \
                             'zeroUp', \
                             'fiftyUp', \
                             'hundredUp', \
                             'unlimitedUp', \
                             'seventyfiveDown', \
                             'threehundredDown', \
                             'sixhundreddDown', \
                             'unlimitedDown', \
                             'diskLocationCtrl', \
                             'portChange', \
                             'iconSaved', \
                             'Save']


        self.elements = {}
        self.data = {} #data related to profile information, to be used in details panel
        self.mypref = None
        self.currentPortValue = None
 
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


        #set fonts
        self.elements['profileTitle'].SetFont(wx.Font(FONT_SIZE_PROFILE_TITLE, wx.SWISS, wx.NORMAL, wx.BOLD, 0, "UTF-8"))
        self.elements['sharingTitle'].SetFont(wx.Font(FONT_SIZE_SHARING_TITLE, wx.SWISS, wx.NORMAL, wx.BOLD, 0, "UTF-8"))
        self.elements['firewallTitle'].SetFont(wx.Font(FONT_SIZE_FIREWALL_TITLE, wx.SWISS, wx.NORMAL, wx.BOLD, 0, "UTF-8"))
        self.elements['fileText'].SetFont(wx.Font(FONT_SIZE_FILE_TEXT, wx.SWISS, wx.NORMAL, wx.BOLD, 0, "UTF-8"))

        self.elements['zeroUp'].Bind(wx.EVT_LEFT_UP, self.zeroUp)
        self.elements['fiftyUp'].Bind(wx.EVT_LEFT_UP, self.fiftyUp)
        self.elements['hundredUp'].Bind(wx.EVT_LEFT_UP, self.hundredUp)
        self.elements['unlimitedUp'].Bind(wx.EVT_LEFT_UP, self.unlimitedUp)

        self.elements['seventyfiveDown'].Bind(wx.EVT_LEFT_UP, self.seventyfiveDown)
        self.elements['threehundredDown'].Bind(wx.EVT_LEFT_UP, self.threehundredDown)
        self.elements['sixhundreddDown'].Bind(wx.EVT_LEFT_UP, self.sixhundreddDown)
        self.elements['unlimitedDown'].Bind(wx.EVT_LEFT_UP, self.unlimitedDown)

        self.elements['uploadCtrl'].Bind(wx.EVT_KEY_DOWN, self.uploadCtrlEnter)
        self.elements['downloadCtrl'].Bind(wx.EVT_KEY_DOWN, self.downloadCtrlEnter)

        #self.elements['firewallValue'].Bind(wx.EVT_KEY_DOWN,self.OnPortChange)
        self.elements['diskLocationCtrl'].Bind(wx.EVT_KEY_DOWN,self.diskLocationCtrlEnter)

        self.elements['Save'].Bind(wx.EVT_LEFT_UP, self.saveAll)

     


        self.showPort()
        self.setCurrentPortValue()


       
        self.showMaxDLRate()
        self.showMaxULRate()

        self.showDiskLocation() # sic

        self.initDone = True
        
#        self.Update()
#        self.initData()
        self.timer = None
        
        wx.CallAfter(self.Refresh)
        

#        print "<mluc> in onshow in settingsOverviewPanel"
#        if evt.show:
#            print "<mluc> settingsOverviewPanel is visible"
#            self.timer.Start() #restarts the timer
#        else:
#            print "<mluc> settingsOverviewPanel is visible"
        #pass
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



    def getGuiElement(self, name):
        if not self.elements.has_key(name) or not self.elements[name]:
            return None
        return self.elements[name]


        
    def sendClick(self, event):
        source = event.GetEventObject()
        source_name = source.GetName()
        if source_name == "edit":
            self.OnMyInfoWizard(event)
        elif source_name == "browse":
            self.BrowseClicked(event)


    def setCurrentPortValue(self):
        self.currentPortValue = self.elements['firewallValue'].GetValue()



    def OnPortChange(self, event):
        keycode = event.GetKeyCode()
        if keycode == wx.WXK_RETURN:
            self.saveAll()
        else:
            event.Skip()


    def diskLocationCtrlEnter(self, event):
        self.elements['diskLocationCtrl'].SetForegroundColour(wx.BLACK)
        event.Skip()



    def showPort(self):
        self.elements['firewallValue'].SetValue(str(self.guiUtility.get_port_number()))

    def show_message(self):
        self.elements['portChange'].SetLabel('Your changes will occur \nthe next time you restart \nTribler.')
        self.guiserver.add_task(lambda:wx.CallAfter(self.hide_message), 3.0)


    def hide_message(self):
        self.elements['portChange'].SetLabel('')

    def updateSaveIcon(self):
        self.guiserver = GUITaskQueue.getInstance()
        self.guiserver.add_task(lambda:wx.CallAfter(self.showSaveIcon), 0.0)

    def showSaveIcon(self):
        self.elements['iconSaved'].Show(True)
        sizer = self.elements['iconSaved'].GetContainingSizer()
        sizer.Layout()
        self.guiserver.add_task(lambda:wx.CallAfter(self.hideSaveIcon), 3.0)

    def hideSaveIcon(self):
        self.elements['iconSaved'].Show(False)

    def showMaxDLRate(self):
        maxdownloadrate = self.guiUtility.utility.config.Read('maxdownloadrate', 'int') #kB/s
        if maxdownloadrate == 0:
            self.elements['downloadCtrl'].SetValue('unlimited')        
        else:
            self.elements['downloadCtrl'].SetValue(str(maxdownloadrate))        

    def showMaxULRate(self):
        maxuploadrate = self.guiUtility.utility.config.Read('maxuploadrate', 'int') #kB/s
        if maxuploadrate == -1:
            self.elements['uploadCtrl'].SetValue('0')        
        elif maxuploadrate == 0:
            self.elements['uploadCtrl'].SetValue('unlimited')        
        else:
            self.elements['uploadCtrl'].SetValue(str(maxuploadrate))        

    def showDiskLocation(self):
        path = self.defaultDLConfig.get_dest_dir()
        self.elements['diskLocationCtrl'].SetValue(path)


    def zeroUp(self, event):
        self.resetUploadDownloadCtrlColour()
        self.elements['uploadCtrl'].SetValue('0') 
        #self.saveAll()

    def fiftyUp(self, event):
        self.resetUploadDownloadCtrlColour()
        self.elements['uploadCtrl'].SetValue('50')        
        #self.saveAll()

    def hundredUp(self, event):
        self.resetUploadDownloadCtrlColour()
        self.elements['uploadCtrl'].SetValue('100')        
        #self.saveAll()

    def unlimitedUp(self, event):
        self.resetUploadDownloadCtrlColour()
        self.elements['uploadCtrl'].SetValue('unlimited')        
        #self.saveAll()

    def seventyfiveDown(self, event):
        self.resetUploadDownloadCtrlColour()
        self.elements['downloadCtrl'].SetValue('75')        
        #self.saveAll()

    def threehundredDown(self, event):
        self.resetUploadDownloadCtrlColour()
        self.elements['downloadCtrl'].SetValue('300')        
        #self.saveAll()

    def sixhundreddDown(self, event):
        self.resetUploadDownloadCtrlColour()
        self.elements['downloadCtrl'].SetValue('600')        
        #self.saveAll()

    def unlimitedDown(self, event):
        self.resetUploadDownloadCtrlColour()
        self.elements['downloadCtrl'].SetValue('unlimited')        
        #self.saveAll()



    def resetUploadDownloadCtrlColour(self):
        self.elements['uploadCtrl'].SetForegroundColour(wx.BLACK)
        self.elements['downloadCtrl'].SetForegroundColour(wx.BLACK)
 



    def uploadCtrlEnter(self, event):
        self.elements['uploadCtrl'].SetForegroundColour(wx.BLACK)
        if self.elements['uploadCtrl'].GetValue().strip() == 'unlimited':
            self.elements['uploadCtrl'].SetValue('')
        event.Skip()

     
    def downloadCtrlEnter(self, event):
        self.elements['downloadCtrl'].SetForegroundColour(wx.BLACK)
        if self.elements['downloadCtrl'].GetValue().strip() == 'unlimited':
            self.elements['downloadCtrl'].SetValue('')
        event.Skip()


    def saveAll(self, download = True, upload = True, diskLocation = True, port = True):
        saved = True
        maxdownload = None
        maxupload = None

        valdown = self.elements['downloadCtrl'].GetValue().strip()
        if valdown != '':
            if valdown == 'unlimited':
                maxdownload = 'unlimited'
            elif valdown.isdigit() and int(valdown) > 0:
                maxdownload = 'value'
            else:
                saved = False
                self.elements['downloadCtrl'].SetForegroundColour(wx.RED)
                self.elements['downloadCtrl'].SetValue('Error')
                 
     
        valup = self.elements['uploadCtrl'].GetValue().strip()
        if valup != '':
            if valup == 'unlimited':
                maxupload = 'unlimited'
                self.utility.ratelimiter.set_global_max_speed(UPLOAD, 0)
                self.guiUtility.utility.config.Write('maxuploadrate', '0')
            elif valup == '0':
                maxupload = '0'
                self.utility.ratelimiter.set_global_max_speed(UPLOAD, 0.0001)
                self.guiUtility.utility.config.Write('maxuploadrate', '-1')
            elif valup.isdigit():
                maxupload = 'value'
                self.utility.ratelimiter.set_global_max_speed(UPLOAD, int(valup))
                self.guiUtility.utility.config.Write('maxuploadrate', valup)
            else:
                saved = False
                self.elements['uploadCtrl'].SetForegroundColour(wx.RED)
                self.elements['uploadCtrl'].SetValue('Error')


        if not self.elements['firewallValue'].GetValue().isdigit():
            saved = False

        if not os.path.exists(self.elements['diskLocationCtrl'].GetValue()):
            saved = False
            self.elements['diskLocationCtrl'].SetForegroundColour(wx.RED)
            self.elements['diskLocationCtrl'].SetValue('Error')




        # save settings parameters
        if saved: 

            # max download
            if download:
                if maxdownload == 'unlimited':
                    self.utility.ratelimiter.set_global_max_speed(DOWNLOAD, 0)
                    self.guiUtility.utility.config.Write('maxdownloadrate', '0')
                else:
                    self.utility.ratelimiter.set_global_max_speed(DOWNLOAD, int(valdown))
                    self.guiUtility.utility.config.Write('maxdownloadrate', valdown)

            # max upload
            if upload:
                if maxupload == 'unlimited':
                    self.utility.ratelimiter.set_global_max_speed(UPLOAD, 0)
                    self.guiUtility.utility.config.Write('maxuploadrate', '0')
                elif maxupload == '0':
                    self.utility.ratelimiter.set_global_max_speed(UPLOAD, 0.0001)
                    self.guiUtility.utility.config.Write('maxuploadrate', '-1')
                else: 
                    self.utility.ratelimiter.set_global_max_speed(UPLOAD, int(valup))
                    self.guiUtility.utility.config.Write('maxuploadrate', valup)

            # disk location
            if diskLocation:
                self.defaultDLConfig.set_dest_dir(self.elements['diskLocationCtrl'].GetValue())
                self.saveDefaultDownloadConfig()


            # port number
            if port and self.elements['firewallValue'].GetValue() != self.currentPortValue:
                self.currentPortValue = self.elements['firewallValue'].GetValue()
                self.utility.config.Write('minport', self.elements['firewallValue'].GetValue())
                self.utility.config.Flush()
                self.guiUtility.set_port_number(self.elements['firewallValue'].GetValue()) 
                self.guiUtility.set_firewall_restart(True) 
                self.guiserver = GUITaskQueue.getInstance()
                self.guiserver.add_task(lambda:wx.CallAfter(self.show_message), 0.0)
                self.elements['firewallStatus'].setSelected(1)
                self.elements['firewallStatusText'].SetLabel('Restart Tribler')
                tt = self.elements['firewallStatus'].GetToolTip()
                if tt is not None:
                    tt.SetTip(self.utility.lang.get('restart_tooltip'))


            self.updateSaveIcon()

   
        

    def BrowseClicked(self, event = None):
        dlg = wx.DirDialog(self,"Choose download directory", style = wx.DEFAULT_DIALOG_STYLE)
        dlg.SetPath(self.defaultDLConfig.get_dest_dir())
        if dlg.ShowModal() == wx.ID_OK:
            self.elements['diskLocationCtrl'].SetForegroundColour(wx.BLACK)
            self.elements['diskLocationCtrl'].SetValue(dlg.GetPath())
            #self.saveAll()
        else:
            pass


    def saveDefaultDownloadConfig(self):
        dlcfgfilename = get_default_dscfg_filename(self.utility.session)
        self.defaultDLConfig.save(dlcfgfilename)


    def OnMyInfoWizard(self, event = None):
        wizard = MyInfoWizard(self)
        wizard.RunWizard(wizard.getFirstPage())

    def WizardFinished(self,wizard):
        wizard.Destroy()

        self.getNameMugshot()
        self.showNameMugshot()

        #self.saveAll()
