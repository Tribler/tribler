# Written by Richard Gwin
# Modified by Niels Zeilemaker

# see LICENSE.txt for license information
import wx
import wx.xrc as xrc
import wx.lib.imagebrowser as ib
import sys, os
import cStringIO
import tempfile
import atexit


from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.IconsManager import IconsManager, data2wxImage, data2wxBitmap, ICON_MAX_DIM
from Tribler.Main.Dialogs.socnetmyinfo import MyInfoWizard
from Tribler.Main.globals import DefaultDownloadStartupConfig,get_default_dscfg_filename
from Tribler.Main.vwxGUI.UserDownloadChoice import UserDownloadChoice
from Tribler.Core.simpledefs import DLSTATUS_SEEDING, DLSTATUS_DOWNLOADING
from Tribler.Core.API import *
from Tribler.Main.vwxGUI import forceDBThread
from Tribler.Main.Dialogs.MoveTorrents import MoveTorrents
from Tribler.Main.Utility.GuiDBHandler import startWorker, cancelWorker

class SettingsDialog(wx.Dialog):
    def __init__(self):
        self.elementsName = ['myNameField', \
                             'thumb', \
                             'edit', \
                             'browse', \
                             'firewallValue', \
                             'firewallStatusText', \
                             'firewallStatus', \
                             'familyFilter', \
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
                             'diskLocationChoice', \
                             'portChange', \
                             'externalplayer',\
                             'batchstart',\
                             'batchstop',\
                             'batchmove',\
                             'use_bundle_magic',\
                             'minimize_to_tray',\
                             't4t0', 't4t0choice', 't4t1', 't4t2', 't4t2text', 't4t3',\
                             'g2g0', 'g2g0choice', 'g2g1', 'g2g2', 'g2g2text', 'g2g3']

        self.myname = None
        self.elements = {}
        self.currentPortValue = None
        
        pre = wx.PreDialog() 
        self.PostCreate(pre) 
        self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate) 
        
    def OnCreate(self, event):
        self.Unbind(wx.EVT_WINDOW_CREATE)
        wx.CallAfter(self._PostInit)
        event.Skip()
        return True
 
    def _PostInit(self):
        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility
        self.defaultDLConfig = DefaultDownloadStartupConfig.getInstance()

        dialog = xrc.XRCCTRL(self, "settingsDialog")
        for element in self.elementsName:
            xrcElement = xrc.XRCCTRL(dialog, element)
            if not xrcElement:    
                print 'settingsOverviewPanel: Error: Could not identify xrc element:',element
            self.elements[element] = xrcElement
        
        #Building tree
        self.tree = xrc.XRCCTRL(self,"settings_tree")
        root = self.tree.AddRoot('Root')
        self.tree.SelectItem(self.tree.AppendItem(root,'General',data=wx.TreeItemData(xrc.XRCCTRL(self,"general_panel"))),True)
        self.tree.AppendItem(root,'Connection',data=wx.TreeItemData(xrc.XRCCTRL(self,"connection_panel")))
        self.tree.AppendItem(root,'Limits',data=wx.TreeItemData(xrc.XRCCTRL(self,"bandwidth_panel")))
        self.tree.AppendItem(root,'Seeding',data=wx.TreeItemData(xrc.XRCCTRL(self,"seeding_panel")))
        self.tree.AppendItem(root,'Misc',data=wx.TreeItemData(xrc.XRCCTRL(self,"misc_panel")))
        self.tree.Bind(wx.EVT_TREE_SEL_CHANGING, self.OnSelectionChanging)

        #Bind event listeners
        self.elements['zeroUp'].Bind(wx.EVT_BUTTON, lambda event: self.setUp(0, event))
        self.elements['fiftyUp'].Bind(wx.EVT_BUTTON, lambda event: self.setUp(50, event))
        self.elements['hundredUp'].Bind(wx.EVT_BUTTON, lambda event: self.setUp(100, event))
        self.elements['unlimitedUp'].Bind(wx.EVT_BUTTON, lambda event: self.setUp('unlimited', event))

        self.elements['seventyfiveDown'].Bind(wx.EVT_BUTTON, lambda event: self.setDown(75, event))
        self.elements['threehundredDown'].Bind(wx.EVT_BUTTON, lambda event: self.setDown(300, event))
        self.elements['sixhundreddDown'].Bind(wx.EVT_BUTTON, lambda event: self.setDown(600, event))
        self.elements['unlimitedDown'].Bind(wx.EVT_BUTTON, lambda event: self.setDown('unlimited', event))

        self.elements['uploadCtrl'].Bind(wx.EVT_KEY_DOWN, self.removeUnlimited)
        self.elements['downloadCtrl'].Bind(wx.EVT_KEY_DOWN, self.removeUnlimited)
        
        self.elements['edit'].Bind(wx.EVT_BUTTON, self.EditClicked)
        self.elements['browse'].Bind(wx.EVT_BUTTON, self.BrowseClicked)
        
        self.elements['batchstart'].Bind(wx.EVT_BUTTON, self.OnMultiple)
        self.elements['batchstop'].Bind(wx.EVT_BUTTON, self.OnMultiple)
        self.elements['batchmove'].Bind(wx.EVT_BUTTON, self.OnMultipleMove)
        
        self.Bind(wx.EVT_BUTTON, self.saveAll, id = xrc.XRCID("wxID_OK"))
        self.Bind(wx.EVT_BUTTON, self.cancelAll, id = xrc.XRCID("wxID_CANCEL"))
        
        #Loading settings
        self.myname = self.utility.session.get_nickname()
        mime, data = self.utility.session.get_mugshot()
        if data is None:
            im = IconsManager.getInstance()
            self.mugshot = im.get_default('PEER_THUMB')
        else:
            self.mugshot = data2wxBitmap(mime, data)
        
        self.elements['myNameField'].SetValue(self.myname)
        self.elements['thumb'].setBitmap(self.mugshot)
        
        if self.guiUtility.frame.SRstatusbar.IsReachable():
            self.elements['firewallStatus'].setSelected(2)
            self.elements['firewallStatusText'].SetLabel('Port is working')
        
        if self.utility.config.Read('family_filter', "boolean"):
            self.elements['familyFilter'].SetSelection(0)
        else:
            self.elements['familyFilter'].SetSelection(1)

        self.currentPopup = self.utility.config.Read('popup_player', "boolean")
        if self.currentPopup:
            self.elements['externalplayer'].SetSelection(1)
        else:
            self.elements['externalplayer'].SetSelection(0)
        
        self.currentPortValue = str(self.guiUtility.get_port_number())
        self.elements['firewallValue'].SetValue(self.currentPortValue)
        
        maxdownloadrate = self.utility.config.Read('maxdownloadrate', 'int')
        if maxdownloadrate == 0:
            self.elements['downloadCtrl'].SetValue('unlimited')        
        else:
            self.elements['downloadCtrl'].SetValue(str(maxdownloadrate))
        
        maxuploadrate = self.utility.config.Read('maxuploadrate', 'int')
        if maxuploadrate == -1:
            self.elements['uploadCtrl'].SetValue('0')        
        elif maxuploadrate == 0:
            self.elements['uploadCtrl'].SetValue('unlimited')        
        else:
            self.elements['uploadCtrl'].SetValue(str(maxuploadrate))
        
        self.currentDestDir = self.defaultDLConfig.get_dest_dir()
        self.elements['diskLocationCtrl'].SetValue(self.currentDestDir)
        self.elements['diskLocationChoice'].SetValue(self.defaultDLConfig.get_show_saveas())
        
        self.elements['use_bundle_magic'].SetValue(self.utility.config.Read('use_bundle_magic', "boolean"))
        
        if sys.platform != "darwin":
            min_to_tray =  self.utility.config.Read('mintray', "int") == 1
            self.elements['minimize_to_tray'].SetValue(min_to_tray)
        else:
            self.elements['minimize_to_tray'].Enabled(False)
        
        self.elements['t4t0'].SetLabel(self.utility.lang.get('no_leeching'))
        self.elements['t4t1'].SetLabel(self.utility.lang.get('unlimited_seeding'))
        self.elements['t4t2'].SetLabel(self.utility.lang.get('seed_sometime'))
        self.elements['t4t3'].SetLabel(self.utility.lang.get('no_seeding'))
        
        self.elements['g2g0'].SetLabel(self.utility.lang.get('seed_for_large_ratio'))
        self.elements['g2g1'].SetLabel(self.utility.lang.get('boost__reputation'))
        self.elements['g2g2'].SetLabel(self.utility.lang.get('seed_sometime'))
        self.elements['g2g3'].SetLabel(self.utility.lang.get('no_seeding'))
        
        t4t_option = self.utility.config.Read('t4t_option', 'int')
        self.elements['t4t%d'%t4t_option].SetValue(True)
        t4t_ratio = self.utility.config.Read('t4t_ratio', 'int')/100.0
        index = self.elements['t4t0choice'].FindString(str(t4t_ratio))
        if index != wx.NOT_FOUND:
            self.elements['t4t0choice'].Select(index)
        
        t4t_hours = self.utility.config.Read('t4t_hours', 'int') 
        t4t_minutes = self.utility.config.Read('t4t_mins', 'int')
        self.elements['t4t2text'].SetLabel("%d:%d"%(t4t_hours, t4t_minutes))
        
        g2g_option = self.utility.config.Read('g2g_option', 'int')
        self.elements['g2g%d'%g2g_option].SetValue(True)
        g2g_ratio = self.utility.config.Read('g2g_ratio', 'int')/100.0
        index = self.elements['g2g0choice'].FindString(str(g2g_ratio))
        if index != wx.NOT_FOUND:
            self.elements['g2g0choice'].Select(index)

        g2g_hours = self.utility.config.Read('g2g_hours', 'int') 
        g2g_mins = self.utility.config.Read('g2g_mins', 'int')
        self.elements['g2g2text'].SetLabel("%d:%d"%(g2g_hours, g2g_mins))
        wx.CallAfter(self.Refresh)
    
    def OnSelectionChanging(self, event):
        old_item = event.GetOldItem() 
        new_item = event.GetItem()
        try:
            self.ShowPage(self.tree.GetItemData(new_item).GetData(), self.tree.GetItemData(old_item).GetData())
        except:
            pass
        
    def ShowPage(self, page, oldpage):
        if oldpage == None:
            selection = self.tree.GetSelection()
            oldpage = self.tree.GetItemData(selection).GetData()
        
        oldpage.Hide()
        
        page.Show(True)
        page.Layout()
        
        self.Layout()
        self.Refresh()

    def setUp(self, value, event = None):
        self.resetUploadDownloadCtrlColour()
        self.elements['uploadCtrl'].SetValue(str(value))
                
        if event:
            event.Skip()
        
    def setDown(self, value, event = None):
        self.resetUploadDownloadCtrlColour()
        self.elements['downloadCtrl'].SetValue(str(value))
        
        if event:
            event.Skip()    
    
    def resetUploadDownloadCtrlColour(self):
        self.elements['uploadCtrl'].SetForegroundColour(wx.BLACK)
        self.elements['downloadCtrl'].SetForegroundColour(wx.BLACK)

    def removeUnlimited(self, event):
        textCtrl = event.GetEventObject()
        if textCtrl.GetValue().strip() == 'unlimited':
            textCtrl.SetValue('')
        event.Skip()

    def saveAll(self, event):
        errors = {}
        
        valdown = self.elements['downloadCtrl'].GetValue().strip()
        if valdown != 'unlimited' and (not valdown.isdigit() or int(valdown) <= 0):
            errors['downloadCtrl'] = 'Value must be a digit'
        
        valup = self.elements['uploadCtrl'].GetValue().strip()
        if valup != 'unlimited' and (not valup.isdigit() or int(valup) < 0):
            errors['uploadCtrl'] = 'Value must be a digit'
        
        valport = self.elements['firewallValue'].GetValue().strip()
        if not valport.isdigit():
            errors['firewallValue'] = 'Value must be a digit'
        
        valdir = self.elements['diskLocationCtrl'].GetValue().strip()
        if not os.path.exists(valdir):
            errors['diskLocationCtrl'] = 'Location does not exist'
            
        valname = self.elements['myNameField'].GetValue()
        if len(valname) > 40:
            errors['myNameField'] = 'Max 40 characters'
            
        hours_min = self.elements['t4t2text'].GetValue()
        if len(hours_min) == 0:
            if self.elements['t4t2'].GetValue():
                errors['t4t2text'] = 'Need value'
        else:
            hours_min = hours_min.split(':')
            
            for value in hours_min:
                if not value.isdigit():
                    if self.elements['t4t2'].GetValue():
                        errors['t4t2text'] = 'Needs to be integer'
                    else:
                        self.elements['t4t2text'].SetValue('')
            
        
        hours_min = self.elements['g2g2text'].GetValue()
        if len(hours_min) == 0:
            if self.elements['g2g2'].GetValue():
                errors['g2g2text'] = 'Need value'
        else:
            hours_min = hours_min.split(':')
            for value in hours_min:
                if not value.isdigit():
                    if self.elements['g2g2'].GetValue():
                        errors['g2g2text'] = 'Needs to be hours:minutes'
                    else:
                        self.elements['g2g2text'].SetValue('')
        
        if len(errors) == 0: #No errors found, continue saving
            restart = False
            
            state_dir = self.utility.session.get_state_dir()
            cfgfilename = self.utility.session.get_default_config_filename(state_dir)
            scfg = SessionStartupConfig.load(cfgfilename)
            
            if valdown == 'unlimited':
                self.utility.ratelimiter.set_global_max_speed(DOWNLOAD, 0)
                self.utility.config.Write('maxdownloadrate', '0')
            else:
                self.utility.ratelimiter.set_global_max_speed(DOWNLOAD, int(valdown))
                self.utility.config.Write('maxdownloadrate', valdown)

            if valup == 'unlimited':
                self.utility.ratelimiter.set_global_max_speed(UPLOAD, 0)
                self.utility.ratelimiter.set_global_max_seedupload_speed(0)
                self.utility.config.Write('maxuploadrate', '0')
                self.utility.config.Write('maxseeduploadrate', '0')
            elif valup == '0':
                self.utility.ratelimiter.set_global_max_speed(UPLOAD, 0.0001)
                self.utility.ratelimiter.set_global_max_seedupload_speed(0.0001)
                self.utility.config.Write('maxuploadrate', '-1')
                self.utility.config.Write('maxseeduploadrate', '-1')
            else: 
                self.utility.ratelimiter.set_global_max_speed(UPLOAD, int(valup))
                self.utility.ratelimiter.set_global_max_seedupload_speed(int(valup))
                self.utility.config.Write('maxuploadrate', valup)
                self.utility.config.Write('maxseeduploadrate', valup)

            if valport != self.currentPortValue:
                self.utility.config.Write('minport', valport)
                self.utility.config.Write('maxport', int(valport) + 10)
                
                scfg.set_dispersy_port(int(valport) - 1)
                self.saveDefaultDownloadConfig()
                
                self.guiUtility.set_port_number(valport) 
                self.guiUtility.set_firewall_restart(True)
                restart = True
            
            showSave = self.elements['diskLocationChoice'].IsChecked()
            if showSave != self.defaultDLConfig.get_show_saveas():
                self.defaultDLConfig.set_show_saveas(showSave)
                self.saveDefaultDownloadConfig()
            
            if valdir != self.currentDestDir:
                self.defaultDLConfig.set_dest_dir(valdir)
                scfg.set_proxyservice_dir(os.path.join(valdir, PROXYSERVICE_DESTDIR))
                scfg.set_subtitles_collecting_dir(os.path.join(valdir, 'collected_subtitles_files'))
                
                self.saveDefaultDownloadConfig()
                self.moveCollectedTorrents(self.currentDestDir, valdir)
                restart = True
                
            useBundleMagic = self.elements['use_bundle_magic'].IsChecked()
            if useBundleMagic != self.utility.config.Read('use_bundle_magic', "boolean"):
                self.utility.config.Write('use_bundle_magic', useBundleMagic, "boolean")
                
            curMintray =  self.utility.config.Read('mintray', "int")
            minimizeToTray = 1 if self.elements['minimize_to_tray'].IsChecked() else 0 
            if minimizeToTray != curMintray:
                self.utility.config.Write('mintray', minimizeToTray, "int")
            
            for target in [scfg,self.utility.session]:
                try:
                    target.set_nickname(self.elements['myNameField'].GetValue())
                    if getattr(self, 'icondata', False):
                        target.set_mugshot(self.icondata, mime='image/jpeg')
                except:
                    print_exc()
                    
            scfg.save(cfgfilename)
            self.guiUtility.toggleFamilyFilter(self.elements['familyFilter'].GetSelection() == 0)
            
            selectedPopup = self.elements['externalplayer'].GetSelection() == 1
            if self.currentPopup != selectedPopup:
                self.utility.config.Write('popup_player', selectedPopup, "boolean")
                restart = True
            
            # tit-4-tat 
            for i in range (4):
                if self.elements['t4t%d'%i].GetValue():
                    self.utility.config.Write('t4t_option', i)
                    break
            t4t_ratio = int(float(self.elements['t4t0choice'].GetStringSelection())*100)
            self.utility.config.Write("t4t_ratio", t4t_ratio)
        
            hours_min = self.elements['t4t2text'].GetValue()
            hours_min = hours_min.split(':')
            if len(hours_min) > 0:
                if len(hours_min)>1:
                    self.utility.config.Write("t4t_hours", hours_min[0])
                    self.utility.config.Write("t4t_mins", hours_min[1])
                else:
                    self.utility.config.Write("t4t_hours", hours_min[0])
                    self.utility.config.Write("t4t_mins", 0)
            
            # give-2-get
            for i in range (4):
                if self.elements['g2g%d'%i].GetValue():
                    self.utility.config.Write("g2g_option", i)
                    break
            g2g_ratio = int(float(self.elements['g2g0choice'].GetStringSelection())*100)
            self.utility.config.Write("g2g_ratio", g2g_ratio)
            
            hours_min = self.elements['g2g2text'].GetValue()
            hours_min = hours_min.split(':')
            if len(hours_min) > 0:
                if len(hours_min)>1:
                    self.utility.config.Write("g2g_hours", hours_min[0])
                    self.utility.config.Write("g2g_mins", hours_min[1])
                else:
                    self.utility.config.Write("g2g_hours", hours_min[0])
                    self.utility.config.Write("g2g_mins", 0)
            
            self.utility.config.Flush()
            
            if restart:
                dlg = wx.MessageDialog(self, "A restart is required for these changes to take effect.\nDo you want to restart Tribler now?","Restart required", wx.ICON_QUESTION|wx.YES_NO|wx.YES_DEFAULT)
                if dlg.ShowModal() == wx.ID_YES:
                    self.guiUtility.frame.Restart()
                dlg.Destroy()
            self.EndModal(1)
            event.Skip()
        else:
            for error in errors.keys():
                if sys.platform != 'darwin':
                    self.elements[error].SetForegroundColour(wx.RED)
                self.elements[error].SetValue(errors[error])
            
            parentPanel = self.elements[error].GetParent()
            self.ShowPage(parentPanel, None)
                    
    def cancelAll(self, event):
        self.EndModal(1)
    
    def EditClicked(self, event = None):
        dlg = ib.ImageDialog(self, get_picture_dir())
        dlg.Centre()
        if dlg.ShowModal() == wx.ID_OK:
            self.iconpath = dlg.GetFile()
            self.process_input()
        else:
            pass
        dlg.Destroy()
    
    def BrowseClicked(self, event = None):
        dlg = wx.DirDialog(self,"Choose download directory", style = wx.DEFAULT_DIALOG_STYLE)
        dlg.SetPath(self.defaultDLConfig.get_dest_dir())
        if dlg.ShowModal() == wx.ID_OK:
            self.elements['diskLocationCtrl'].SetForegroundColour(wx.BLACK)
            self.elements['diskLocationCtrl'].SetValue(dlg.GetPath())
        else:
            pass
    
    def OnMultiple(self, event):
        button = event.GetEventObject()
        button.Enable(False)
        wx.CallLater(5000, button.Enable, True)
        
        start = button == self.elements['batchstart']
        
        def do_db():
            choices = []
            dstates = []
            infohashes = []
            _,_,downloads = self.guiUtility.library_manager.getHitsInCategory()
        
            def sort_by_name(a, b):
                return cmp(a.name, b.name)
        
            downloads.sort(cmp = sort_by_name)
            for item in downloads:
                started = 'active' in item.state
                if start != started:
                    choices.append(item.name)
                    dstates.append(item.ds)
                    infohashes.append(item.infohash)
            
            return choices, dstates, infohashes
                
        def do_gui(delayedResult):
            choices, dstates, infohashes = delayedResult.get()
            user_download_choice = UserDownloadChoice.get_singleton()
            
            if len(choices) > 0:
                message = 'Please select all torrents which should be '
                if start:
                    message += 'started.'
                else:
                    message += 'stopped.'
                message += "\nUse ctrl+a to select all/deselect all."
                
                def bindAll(control):
                    control.Bind(wx.EVT_KEY_DOWN, lambda event: self._SelectAll(dlg, event, len(choices)))
                    func = getattr(control, 'GetChildren', False)
                    if func:
                        for child in func():
                            bindAll(child)
                
                dlg = wx.MultiChoiceDialog(self, message, 'Select torrents', choices)
                dlg.allselected = False
                bindAll(dlg)
                
                if dlg.ShowModal() == wx.ID_OK:
                    selections = dlg.GetSelections()
                    for selection in selections:
                        if start:
                            if dstates[selection]:
                                dstates[selection].get_download().restart()
                            user_download_choice.set_download_state(infohashes[selection], "restart")
                            
                        else:
                            if dstates[selection]:
                                dstates[selection].get_download().stop()
                            
                            user_download_choice.set_download_state(infohashes[selection], "stop")
                            
                    user_download_choice.flush()
            else:
                message = "No torrents in library which could be "
                if start:
                    message += "started."
                else:
                    message += "stopped."
                dlg = wx.MessageDialog(self, message, 'No torrents found.', wx.OK | wx.ICON_INFORMATION)
                dlg.ShowModal()
            dlg.Destroy()
        
        cancelWorker("OnMultiple")
        startWorker(do_gui, do_db, uId = "OnMultiple")
        
    def OnMultipleMove(self, event):
        button = event.GetEventObject()
        button.Enable(False)
        wx.CallLater(5000, button.Enable, True)
        
        start = button == self.elements['batchstart']
        
        def do_db():
            choices = []
            dstates = []
            _,_,downloads = self.guiUtility.library_manager.getHitsInCategory()
            
            def sort_by_name(a, b):
                return cmp(a.name, b.name)
            
            downloads.sort(cmp = sort_by_name)
            for item in downloads:
                if item.ds:
                    choices.append(item.name)
                    dstates.append(item.ds.get_download())
            
            return choices, dstates
        
        def do_gui(delayedResult):
            choices, dstates = delayedResult.get()
            
            dlg = MoveTorrents(self, choices, dstates)
            if dlg.ShowModal() == wx.ID_OK:
                selectedDownloads, new_dir, moveFiles, ignoreIfExists = dlg.GetSettings()
                for download in selectedDownloads:
                    self.moveDownload(download, new_dir, moveFiles, ignoreIfExists)
            dlg.Destroy()
        
        startWorker(do_gui, do_db, uId="OnMultipleMove")
        
    def _SelectAll(self, dlg, event, nrchoices):
        if event.ControlDown():
            if event.GetKeyCode() == 65: #ctrl + a
                if dlg.allselected:
                    dlg.SetSelections([])
                else:
                    select = list(range(nrchoices))
                    dlg.SetSelections(select)
                dlg.allselected = not dlg.allselected

    def saveDefaultDownloadConfig(self):
        # Save DownloadStartupConfig
        dlcfgfilename = get_default_dscfg_filename(self.utility.session)
        self.defaultDLConfig.save(dlcfgfilename)
        
        # Arno, 2010-03-08: Apparently not copied correctly from abcoptions.py
        # Save SessionStartupConfig
        # Also change torrent collecting dir, which is by default in the default destdir
        state_dir = self.utility.session.get_state_dir()
        cfgfilename = Session.get_default_config_filename(state_dir)
        scfg = SessionStartupConfig.load(cfgfilename)

        defaultdestdir = self.defaultDLConfig.get_dest_dir()
        dirname = os.path.join(defaultdestdir,STATEDIR_TORRENTCOLL_DIR)
        for target in [scfg,self.utility.session]:
            try:
                target.set_torrent_collecting_dir(dirname)
            except:
                print_exc()
        scfg.save(cfgfilename)
    
    def moveCollectedTorrents(self, old_dir, new_dir):
        def rename_or_merge(old, new, ignore = True):
            if os.path.exists(old):
                if os.path.exists(new):
                    files = os.listdir(old)
                    for file in files:
                        oldfile = os.path.join(old, file)
                        newfile = os.path.join(new, file)
                        
                        if os.path.isdir(oldfile):
                            self.rename_or_merge(oldfile, newfile)
                            
                        elif os.path.exists(newfile):
                            if not ignore:
                                os.remove(newfile)
                                os.rename(oldfile, newfile)
                        else:
                            os.rename(oldfile, newfile)
                else:
                    os.renames(old, new)
        
        def move(old_dir, new_dir):
            #physical move
            old_dirtf = os.path.join(old_dir, 'collected_torrent_files')
            new_dirtf = os.path.join(new_dir, 'collected_torrent_files')
            rename_or_merge(old_dirtf, new_dirtf, False)
            
            old_dirsf = os.path.join(old_dir, 'collected_subtitles_files')
            new_dirsf = os.path.join(new_dir, 'collected_subtitles_files')
            rename_or_merge(old_dirsf, new_dirsf, False)
        
            # ProxyService_
            old_dirdh = os.path.join(old_dir, PROXYSERVICE_DESTDIR)
            new_dirdh = os.path.join(new_dir, PROXYSERVICE_DESTDIR)
            rename_or_merge(old_dirdh, new_dirdh, False)
            
        atexit.register(move, old_dir, new_dir)
        
        msg = "Please wait while we update your MegaCache..."
        busyDlg = wx.BusyInfo(msg)
        try:
            time.sleep(0.3)
            wx.Yield()
        except:
            pass
        
        #update db
        self.guiUtility.torrentsearch_manager.torrent_db.updateTorrentDir(os.path.join(new_dir, 'collected_torrent_files'))
        
        busyDlg.Destroy()
        
    def moveDownload(self, download, new_dir, movefiles, ignore):
        destdirs = download.get_dest_files()
        if len(destdirs) > 1:
            old = os.path.commonprefix([os.path.split(path)[0] for _,path in destdirs])
            _, old_dir = new = os.path.split(old)
            new = os.path.join(new_dir, old_dir)
        else:
            old = destdirs[0][1]
            _, old_file = os.path.split(old)
            new = os.path.join(new_dir, old_file)
        
        print >> sys.stderr, "Creating new donwloadconfig"
        tdef = download.get_def()
        dscfg = DownloadStartupConfig(download.dlconfig)
        dscfg.set_dest_dir(new_dir)
        
        self.guiUtility.library_manager.deleteTorrentDownload(download, None, removestate = False)
        
        def rename_or_merge(old, new, ignore = True):
            if os.path.exists(old):
                if os.path.exists(new):
                    files = os.listdir(old)
                    for file in files:
                        oldfile = os.path.join(old, file)
                        newfile = os.path.join(new, file)
                        
                        if os.path.isdir(oldfile):
                            self.rename_or_merge(oldfile, newfile)
                            
                        elif os.path.exists(newfile):
                            if not ignore:
                                os.remove(newfile)
                                os.rename(oldfile, newfile)
                        else:
                            os.rename(oldfile, newfile)
                else:
                    os.renames(old, new)
        
        def after_stop():
            print >> sys.stderr, "Moving from",old,"to",new,"newdir",new_dir
            if movefiles:
                rename_or_merge(old, new, ignore)
        
            self.utility.session.start_download(tdef, dscfg)
        
        #use rawserver as remove is scheduled on rawserver 
        self.utility.session.lm.rawserver.add_task(after_stop,0.0)
        
    def process_input(self):
        try:
            im = wx.Image(self.iconpath)
            if im is None:
                self.show_inputerror(self.utility.lang.get('cantopenfile'))
            else:
                if sys.platform != 'darwin':
                    bm = wx.BitmapFromImage(im.Scale(ICON_MAX_DIM,ICON_MAX_DIM),-1)
                    thumbpanel = self.elements['thumb']
                    thumbpanel.setBitmap(bm)
                
                # Arno, 2008-10-21: scale image!
                sim = im.Scale(ICON_MAX_DIM,ICON_MAX_DIM)
                [thumbhandle,thumbfilename] = tempfile.mkstemp("user-thumb")
                os.close(thumbhandle)
                sim.SaveFile(thumbfilename,wx.BITMAP_TYPE_JPEG)
                
                f = open(thumbfilename,"rb")
                self.icondata = f.read()
                f.close()
                os.remove(thumbfilename)
        except:
            print_exc()
            self.show_inputerror(self.utility.lang.get('iconbadformat'))

    def show_inputerror(self,txt):
        dlg = wx.MessageDialog(self, txt, self.utility.lang.get('invalidinput'), wx.OK | wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()

