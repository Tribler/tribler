# Written by Niels Zeilemaker

# see LICENSE.txt for license information
import wx
import wx.xrc as xrc
import wx.lib.imagebrowser as ib
import sys
import os
import cStringIO
import tempfile
import atexit


from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.IconsManager import IconsManager, data2wxImage, data2wxBitmap, ICON_MAX_DIM
from Tribler.Main.globals import DefaultDownloadStartupConfig, get_default_dscfg_filename
from Tribler.Main.vwxGUI.UserDownloadChoice import UserDownloadChoice
from Tribler.Core.simpledefs import DLSTATUS_SEEDING, DLSTATUS_DOWNLOADING
from Tribler.Core.API import *
from Tribler.Core.Utilities.utilities import isInteger
from Tribler.Core.CacheDB.sqlitecachedb import forceDBThread

from Tribler.Main.Utility.GuiDBHandler import startWorker, cancelWorker, GUI_PRI_DISPERSY
from Tribler.Main.Utility.GuiDBTuples import MergedDs
from Tribler.Main.Utility.GuiDBTuples import MergedDs


class SettingsDialog(wx.Dialog):

    def __init__(self):
        self.elementsName = ['myNameField',
                             'thumb',
                             'edit',
                             'browse',
                             'firewallValue',
                             'firewallStatusText',
                             'uploadCtrl',
                             'downloadCtrl',
                             'zeroUp',
                             'fiftyUp',
                             'hundredUp',
                             'unlimitedUp',
                             'seventyfiveDown',
                             'threehundredDown',
                             'sixhundreddDown',
                             'unlimitedDown',
                             'diskLocationCtrl',
                             'diskLocationChoice',
                             'portChange',
                             'minimize_to_tray',
                             't4t0', 't4t0choice', 't4t1', 't4t2', 't4t2text', 't4t3',
                             'g2g0', 'g2g0choice', 'g2g1', 'g2g2', 'g2g2text', 'g2g3',
                             'use_webui',
                             'webui_port',
                             'lt_proxytype',
                             'lt_proxyserver',
                             'lt_proxyport',
                             'lt_proxyusername',
                             'lt_proxypassword',
                             'enable_utp']

        self.myname = None
        self.elements = {}
        self.currentPortValue = None

        pre = wx.PreDialog()
        self.PostCreate(pre)
        if sys.platform == 'linux2':
            self.Bind(wx.EVT_SIZE, self.OnCreate)
        else:
            self.Bind(wx.EVT_WINDOW_CREATE, self.OnCreate)

    def OnCreate(self, event):
        if sys.platform == 'linux2':
            self.Unbind(wx.EVT_SIZE)
        else:
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
                print 'settingsOverviewPanel: Error: Could not identify xrc element:', element
            self.elements[element] = xrcElement

        # Building tree
        self.tree = xrc.XRCCTRL(self, "settings_tree")
        root = self.tree.AddRoot('Root')
        self.tree.SelectItem(self.tree.AppendItem(root, 'General', data=wx.TreeItemData(xrc.XRCCTRL(self, "general_panel"))), True)
        self.tree.AppendItem(root, 'Connection', data=wx.TreeItemData(xrc.XRCCTRL(self, "connection_panel")))
        self.tree.AppendItem(root, 'Limits', data=wx.TreeItemData(xrc.XRCCTRL(self, "bandwidth_panel")))
        self.tree.AppendItem(root, 'Seeding', data=wx.TreeItemData(xrc.XRCCTRL(self, "seeding_panel")))
        self.tree.AppendItem(root, 'Experimental', data=wx.TreeItemData(xrc.XRCCTRL(self, "exp_panel")))
        self.tree.Bind(wx.EVT_TREE_SEL_CHANGING, self.OnSelectionChanging)

        # Bind event listeners
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

        self.elements['lt_proxytype'].Bind(wx.EVT_CHOICE, self.ProxyTypeChanged)

        self.Bind(wx.EVT_BUTTON, self.saveAll, id=xrc.XRCID("wxID_OK"))
        self.Bind(wx.EVT_BUTTON, self.cancelAll, id=xrc.XRCID("wxID_CANCEL"))

        # Loading settings
        self.myname = self.utility.session.get_nickname()
        mime, data = self.utility.session.get_mugshot()
        if data is None:
            im = IconsManager.getInstance()
            self.mugshot = im.get_default('PEER_THUMB')
        else:
            self.mugshot = data2wxBitmap(mime, data)

        self.elements['myNameField'].SetValue(self.myname)
        self.elements['thumb'].SetBitmap(self.mugshot)

        if self.guiUtility.frame.SRstatusbar.IsReachable():
            self.elements['firewallStatusText'].SetLabel('Your network connection is working properly.')
        else:
            self.elements['firewallStatusText'].SetLabel('Tribler has not yet received any incoming connections. \nUnless you\'re using a proxy, this could indicate a problem\nwith your network connection.')

        self.currentPortValue = str(self.utility.session.get_listen_port())
        self.elements['firewallValue'].SetValue(self.currentPortValue)

        self.elements['downloadCtrl'].SetValue(self.utility.getMaxDown())
        self.elements['uploadCtrl'].SetValue(self.utility.getMaxUp())

        self.currentDestDir = self.defaultDLConfig.get_dest_dir()
        self.elements['diskLocationCtrl'].SetValue(self.currentDestDir)
        self.elements['diskLocationChoice'].SetValue(self.defaultDLConfig.get_show_saveas())

        if sys.platform != "darwin":
            min_to_tray = self.utility.read_config('mintray') == 1
            self.elements['minimize_to_tray'].SetValue(min_to_tray)
        else:
            self.elements['minimize_to_tray'].Enable(False)

        self.elements['t4t0'].SetLabel(self.utility.lang.get('no_leeching'))
        self.elements['t4t0'].Refresh()
        self.elements['t4t1'].SetLabel(self.utility.lang.get('unlimited_seeding'))
        self.elements['t4t2'].SetLabel(self.utility.lang.get('seed_sometime'))
        self.elements['t4t3'].SetLabel(self.utility.lang.get('no_seeding'))

        self.elements['g2g0'].SetLabel(self.utility.lang.get('seed_for_large_ratio'))
        self.elements['g2g1'].SetLabel(self.utility.lang.get('boost__reputation'))
        self.elements['g2g2'].SetLabel(self.utility.lang.get('seed_sometime'))
        self.elements['g2g3'].SetLabel(self.utility.lang.get('no_seeding'))

        t4t_option = self.utility.read_config('t4t_option')
        self.elements['t4t%d' % t4t_option].SetValue(True)
        t4t_ratio = self.utility.read_config('t4t_ratio') / 100.0
        index = self.elements['t4t0choice'].FindString(str(t4t_ratio))
        if index != wx.NOT_FOUND:
            self.elements['t4t0choice'].Select(index)

        t4t_hours = self.utility.read_config('t4t_hours')
        t4t_minutes = self.utility.read_config('t4t_mins')
        self.elements['t4t2text'].SetLabel("%d:%d" % (t4t_hours, t4t_minutes))

        g2g_option = self.utility.read_config('g2g_option')
        self.elements['g2g%d' % g2g_option].SetValue(True)
        g2g_ratio = self.utility.read_config('g2g_ratio') / 100.0
        index = self.elements['g2g0choice'].FindString(str(g2g_ratio))
        if index != wx.NOT_FOUND:
            self.elements['g2g0choice'].Select(index)

        g2g_hours = self.utility.read_config('g2g_hours')
        g2g_mins = self.utility.read_config('g2g_mins')
        self.elements['g2g2text'].SetLabel("%d:%d" % (g2g_hours, g2g_mins))

        self.elements['use_webui'].SetValue(self.utility.read_config('use_webui'))
        self.elements['webui_port'].SetValue(str(self.utility.read_config('webui_port')))

        ptype, server, auth = self.utility.session.get_libtorrent_proxy_settings()
        self.elements['lt_proxytype'].SetSelection(ptype)
        if server:
            self.elements['lt_proxyserver'].SetValue(server[0])
            self.elements['lt_proxyport'].SetValue(str(server[1]))
        if auth:
            self.elements['lt_proxyusername'].SetValue(auth[0])
            self.elements['lt_proxypassword'].SetValue(auth[1])
        self.ProxyTypeChanged()

        self.elements['enable_utp'].SetValue(self.utility.session.get_libtorrent_utp())

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

    def setUp(self, value, event=None):
        self.resetUploadDownloadCtrlColour()
        self.elements['uploadCtrl'].SetValue(str(value))

        if event:
            event.Skip()

    def setDown(self, value, event=None):
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
        if not isInteger(valport):
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

        valwebuiport = self.elements['webui_port'].GetValue().strip()
        if not isInteger(valwebuiport):
            errors['webui_port'] = 'Value must be a digit'

        valltproxyport = self.elements['lt_proxyport'].GetValue().strip()
        if not valltproxyport.isdigit() and (self.elements['lt_proxytype'].GetSelection() or valltproxyport != ''):
            errors['lt_proxyport'] = 'Value must be a digit'

        if len(errors) == 0:  # No errors found, continue saving
            restart = False

            state_dir = self.utility.session.get_state_dir()
            cfgfilename = self.utility.session.get_default_config_filename(state_dir)
            scfg = SessionStartupConfig.load(cfgfilename)

            self.utility.setMaxDown(valdown)
            self.utility.setMaxUp(valup)

            if valport != self.currentPortValue:
                scfg.set_listen_port(int(valport))

                scfg.set_dispersy_port(int(valport) - 1)
                self.saveDefaultDownloadConfig(scfg)

                self.guiUtility.set_firewall_restart(True)
                restart = True

            showSave = self.elements['diskLocationChoice'].IsChecked()
            if showSave != self.defaultDLConfig.get_show_saveas():
                self.defaultDLConfig.set_show_saveas(showSave)
                self.saveDefaultDownloadConfig(scfg)

            if valdir != self.currentDestDir:
                self.defaultDLConfig.set_dest_dir(valdir)

                self.saveDefaultDownloadConfig(scfg)
                self.moveCollectedTorrents(self.currentDestDir, valdir)
                restart = True

            useWebUI = self.elements['use_webui'].IsChecked()
            if useWebUI != self.utility.read_config('use_webui'):
                self.utility.write_config('use_webui', useWebUI)
                restart = True

            if valwebuiport != str(self.utility.read_config('webui_port')):
                self.utility.write_config('webui_port', valwebuiport)
                restart = True

            curMintray = self.utility.read_config('mintray')
            minimizeToTray = 1 if self.elements['minimize_to_tray'].IsChecked() else 0
            if minimizeToTray != curMintray:
                self.utility.write_config('mintray', minimizeToTray)

            for target in [scfg, self.utility.session]:
                try:
                    target.set_nickname(self.elements['myNameField'].GetValue())
                    if getattr(self, 'icondata', False):
                        target.set_mugshot(self.icondata, mime='image/jpeg')
                except:
                    print_exc()

            # tit-4-tat
            t4t_option = self.utility.read_config('t4t_option')
            for i in range(4):
                if self.elements['t4t%d' % i].GetValue():
                    self.utility.write_config('t4t_option', i)

                    if i != t4t_option:
                        restart = True

                    break
            t4t_ratio = int(float(self.elements['t4t0choice'].GetStringSelection()) * 100)
            self.utility.write_config("t4t_ratio", t4t_ratio)

            hours_min = self.elements['t4t2text'].GetValue()
            hours_min = hours_min.split(':')
            if len(hours_min) > 0:
                if len(hours_min) > 1:
                    self.utility.write_config("t4t_hours", hours_min[0])
                    self.utility.write_config("t4t_mins", hours_min[1])
                else:
                    self.utility.write_config("t4t_hours", hours_min[0])
                    self.utility.write_config("t4t_mins", 0)

            # give-2-get
            g2g_option = self.utility.read_config('g2g_option')
            for i in range(4):
                if self.elements['g2g%d' % i].GetValue():
                    self.utility.write_config("g2g_option", i)

                    if i != g2g_option:
                        restart = True
                    break
            g2g_ratio = int(float(self.elements['g2g0choice'].GetStringSelection()) * 100)
            self.utility.write_config("g2g_ratio", g2g_ratio)

            hours_min = self.elements['g2g2text'].GetValue()
            hours_min = hours_min.split(':')
            if len(hours_min) > 0:
                if len(hours_min) > 1:
                    self.utility.write_config("g2g_hours", hours_min[0])
                    self.utility.write_config("g2g_mins", hours_min[1])
                else:
                    self.utility.write_config("g2g_hours", hours_min[0])
                    self.utility.write_config("g2g_mins", 0)

            # Proxy settings
            old_ptype, old_server, old_auth = self.utility.session.get_libtorrent_proxy_settings()
            new_ptype = self.elements['lt_proxytype'].GetSelection()
            new_server = (self.elements['lt_proxyserver'].GetValue(), int(self.elements['lt_proxyport'].GetValue())) if self.elements['lt_proxyserver'].GetValue() and self.elements['lt_proxyport'].GetValue() else None
            new_auth = (self.elements['lt_proxyusername'].GetValue(), self.elements['lt_proxypassword'].GetValue()) if self.elements['lt_proxyusername'].GetValue() and self.elements['lt_proxypassword'].GetValue() else None
            if old_ptype != new_ptype or old_server != new_server or old_auth != new_auth:
                self.utility.session.set_libtorrent_proxy_settings(new_ptype, new_server, new_auth)
                scfg.set_libtorrent_proxy_settings(new_ptype, new_server, new_auth)

            enable_utp = self.elements['enable_utp'].GetValue()
            if enable_utp != self.utility.session.get_libtorrent_utp():
                self.utility.session.set_libtorrent_utp(enable_utp)
                scfg.set_libtorrent_utp(enable_utp)

            scfg.save(cfgfilename)

            self.utility.flush_config()

            if restart:
                dlg = wx.MessageDialog(self, "A restart is required for these changes to take effect.\nDo you want to restart Tribler now?", "Restart required", wx.ICON_QUESTION | wx.YES_NO | wx.YES_DEFAULT)
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

    def EditClicked(self, event=None):
        dlg = ib.ImageDialog(self, get_picture_dir())
        dlg.Centre()
        if dlg.ShowModal() == wx.ID_OK:
            self.iconpath = dlg.GetFile()
            self.process_input()
        else:
            pass
        dlg.Destroy()

    def BrowseClicked(self, event=None):
        dlg = wx.DirDialog(self, "Choose download directory", style=wx.DEFAULT_DIALOG_STYLE)
        dlg.SetPath(self.defaultDLConfig.get_dest_dir())
        if dlg.ShowModal() == wx.ID_OK:
            self.elements['diskLocationCtrl'].SetForegroundColour(wx.BLACK)
            self.elements['diskLocationCtrl'].SetValue(dlg.GetPath())
        else:
            pass

    def ProxyTypeChanged(self, event=None):
        selection = self.elements['lt_proxytype'].GetStringSelection()
        self.elements['lt_proxyusername'].Enable(selection.endswith('with authentication'))
        self.elements['lt_proxypassword'].Enable(selection.endswith('with authentication'))
        self.elements['lt_proxyserver'].Enable(selection != 'None')
        self.elements['lt_proxyport'].Enable(selection != 'None')

    def _SelectAll(self, dlg, event, nrchoices):
        if event.ControlDown():
            if event.GetKeyCode() == 65:  # ctrl + a
                if dlg.allselected:
                    dlg.SetSelections([])
                else:
                    select = list(range(nrchoices))
                    dlg.SetSelections(select)
                dlg.allselected = not dlg.allselected

    def saveDefaultDownloadConfig(self, scfg):
        state_dir = self.utility.session.get_state_dir()

        # Save DownloadStartupConfig
        dlcfgfilename = get_default_dscfg_filename(state_dir)
        self.defaultDLConfig.save(dlcfgfilename)

        # Save SessionStartupConfig
        # Also change torrent collecting dir, which is by default in the default destdir
        cfgfilename = Session.get_default_config_filename(state_dir)
        defaultdestdir = self.defaultDLConfig.get_dest_dir()
        for target in [scfg, self.utility.session]:
            try:
                target.set_torrent_collecting_dir(os.path.join(defaultdestdir, STATEDIR_TORRENTCOLL_DIR))
            except:
                print_exc()
            try:
                target.set_swift_meta_dir(os.path.join(defaultdestdir, STATEDIR_SWIFTRESEED_DIR))
            except:
                print_exc()

        scfg.save(cfgfilename)

    def moveCollectedTorrents(self, old_dir, new_dir):
        def rename_or_merge(old, new, ignore=True):
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
            # physical move
            old_dirtf = os.path.join(old_dir, 'collected_torrent_files')
            new_dirtf = os.path.join(new_dir, 'collected_torrent_files')
            rename_or_merge(old_dirtf, new_dirtf, False)

        atexit.register(move, old_dir, new_dir)

        msg = "Please wait while we update your MegaCache..."
        busyDlg = wx.BusyInfo(msg)
        try:
            time.sleep(0.3)
            wx.Yield()
        except:
            pass

        # update db
        self.guiUtility.torrentsearch_manager.torrent_db.updateTorrentDir(os.path.join(new_dir, 'collected_torrent_files'))

        busyDlg.Destroy()

    def process_input(self):
        try:
            im = wx.Image(self.iconpath)
            if im is None:
                self.show_inputerror(self.utility.lang.get('cantopenfile'))
            else:
                if sys.platform != 'darwin':
                    bm = wx.BitmapFromImage(im.Scale(ICON_MAX_DIM, ICON_MAX_DIM), -1)
                    thumbpanel = self.elements['thumb']
                    thumbpanel.SetBitmap(bm)

                # Arno, 2008-10-21: scale image!
                sim = im.Scale(ICON_MAX_DIM, ICON_MAX_DIM)
                [thumbhandle, thumbfilename] = tempfile.mkstemp("user-thumb")
                os.close(thumbhandle)
                sim.SaveFile(thumbfilename, wx.BITMAP_TYPE_JPEG)

                f = open(thumbfilename, "rb")
                self.icondata = f.read()
                f.close()
                os.remove(thumbfilename)
        except:
            print_exc()
            self.show_inputerror(self.utility.lang.get('iconbadformat'))

    def show_inputerror(self, txt):
        dlg = wx.MessageDialog(self, txt, self.utility.lang.get('invalidinput'), wx.OK | wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()
