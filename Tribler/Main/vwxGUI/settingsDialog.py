# Written by Niels Zeilemaker

# see LICENSE.txt for license information
import atexit
import logging
import os
import shutil
import sys
import tempfile
import time

import wx.lib.imagebrowser as ib
import wx.lib.masked.textctrl

from Tribler.Core.Session import Session
from Tribler.Core.SessionConfig import SessionStartupConfig
from Tribler.Core.osutils import get_picture_dir
from Tribler.Core.simpledefs import UPLOAD, DOWNLOAD
from Tribler.Core.DownloadConfig import get_default_dscfg_filename
from Tribler.Main.globals import DefaultDownloadStartupConfig
from Tribler.Main.vwxGUI.GuiImageManager import GuiImageManager, data2wxBitmap, ICON_MAX_DIM
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.validator import DirectoryValidator, NetworkSpeedValidator, NumberValidator
from Tribler.Main.vwxGUI.widgets import _set_font, EditText, AnonymityDialog


def create_section(parent, hsizer, label):
    panel = wx.Panel(parent)

    vsizer = wx.BoxSizer(wx.VERTICAL)

    title = wx.StaticText(panel, label=label)
    _set_font(title, 1, wx.FONTWEIGHT_BOLD)
    vsizer.AddSpacer((1, 7))
    vsizer.Add(title, 0, wx.EXPAND | wx.BOTTOM, -7)

    hsizer.Add(panel, 1, wx.EXPAND)
    panel.SetSizer(vsizer)
    return panel, vsizer


def create_subsection(parent, parent_sizer, label, num_cols=1, vgap=0, hgap=0):
    line = wx.StaticLine(parent, size=(-1, 1), style=wx.LI_HORIZONTAL)
    parent_sizer.Add(line, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 7)

    title = wx.StaticText(parent, label=label)
    _set_font(title, 0, wx.FONTWEIGHT_BOLD)
    parent_sizer.Add(title, 0, wx.EXPAND | wx.BOTTOM, 5)

    if num_cols == 1:
        sizer = wx.BoxSizer(wx.VERTICAL)
    else:
        sizer = wx.FlexGridSizer(cols=num_cols, vgap=vgap, hgap=hgap)
        sizer.AddGrowableCol(1)

    parent_sizer.Add(sizer, 0, wx.EXPAND)
    return sizer


def add_label(parent, sizer, label):
    label = wx.StaticText(parent, label=label)
    label.SetMinSize((100, -1))
    sizer.Add(label)


class SettingsDialog(wx.Dialog):

    def __init__(self):
        super(SettingsDialog, self).__init__(None, size=(600, 600),
                                             title="Settings", name="settingsDialog", style=wx.DEFAULT_DIALOG_STYLE)
        self.SetExtraStyle(self.GetExtraStyle() | wx.WS_EX_VALIDATE_RECURSIVELY)
        self._logger = logging.getLogger(self.__class__.__name__)

        self.guiUtility = GUIUtility.getInstance()
        self.utility = self.guiUtility.utility
        self.defaultDLConfig = DefaultDownloadStartupConfig.getInstance()

        # create the dialog and widgets
        self._tree_ctrl = wx.TreeCtrl(self,
                                      style=wx.TR_DEFAULT_STYLE | wx.SUNKEN_BORDER | wx.TR_HIDE_ROOT | wx.TR_SINGLE)
        self._tree_ctrl.SetMinSize(wx.Size(150, -1))
        tree_root = self._tree_ctrl.AddRoot('Root')
        self._tree_ctrl.Bind(wx.EVT_TREE_SEL_CHANGING, self.OnSelectionChanging)

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        hsizer.Add(self._tree_ctrl, 0, wx.EXPAND | wx.RIGHT, 10)

        self._general_panel, self._general_id = self.__create_s1(tree_root, hsizer)
        self._conn_panel, self._conn_id = self.__create_s2(tree_root, hsizer)
        self._bandwidth_panel, self._bandwidth_id = self.__create_s3(tree_root, hsizer)
        self._seeding_panel, self._seeding_id = self.__create_s4(tree_root, hsizer)
        self._experimental_panel, self._experimental_id = self.__create_s5(tree_root, hsizer)
        self._tunnel_panel, self._tunnel_id = self.__create_s6(tree_root, hsizer)

        self._general_panel.Show(True)
        self._conn_panel.Show(False)
        self._bandwidth_panel.Show(False)
        self._seeding_panel.Show(False)
        self._experimental_panel.Show(False)
        self._tunnel_panel.Show(False)

        self._save_btn = wx.Button(self, wx.ID_OK, label="Save")
        self._cancel_btn = wx.Button(self, wx.ID_CANCEL, label="Cancel")

        btn_sizer = wx.StdDialogButtonSizer()
        btn_sizer.AddButton(self._save_btn)
        btn_sizer.AddButton(self._cancel_btn)
        btn_sizer.Realize()

        self._save_btn.Bind(wx.EVT_BUTTON, self.saveAll)
        self._cancel_btn.Bind(wx.EVT_BUTTON, self.cancelAll)

        vsizer = wx.BoxSizer(wx.VERTICAL)
        vsizer.Add(hsizer, 1, wx.EXPAND | wx.ALL, 10)
        vsizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 5)
        self.SetSizer(vsizer)

        # select General page by default
        self._tree_ctrl.SelectItem(self._general_id)

    def OnSelectionChanging(self, event):
        old_item = event.GetOldItem()
        new_item = event.GetItem()
        try:
            self.ShowPage(self._tree_ctrl.GetItemData(new_item).GetData(),
                          self._tree_ctrl.GetItemData(old_item).GetData())
        except:
            pass

    def ShowPage(self, page, oldpage):
        if oldpage is None:
            selection = self._tree_ctrl.GetSelection()
            oldpage = self._tree_ctrl.GetItemData(selection).GetData()

        oldpage.Hide()

        page.Show(True)
        page.Layout()

        self.Layout()
        self.Refresh()

    def setUp(self, value, event=None):
        self.resetUploadDownloadCtrlColour()
        self._upload_ctrl.SetValue(str(value))

        if event:
            event.Skip()

    def setDown(self, value, event=None):
        self.resetUploadDownloadCtrlColour()
        self._download_ctrl.SetValue(str(value))

        if event:
            event.Skip()

    def resetUploadDownloadCtrlColour(self):
        self._upload_ctrl.SetForegroundColour(wx.BLACK)
        self._download_ctrl.SetForegroundColour(wx.BLACK)

    def saveAll(self, event, skip_restart_dialog=False):
        if not self.Validate():
            return

        restart = False

        state_dir = self.utility.session.get_state_dir()
        cfgfilename = self.utility.session.get_default_config_filename(state_dir)
        scfg = SessionStartupConfig.load(cfgfilename)

        valdown = self._download_ctrl.GetValue()
        valup = self._upload_ctrl.GetValue()
        convert = lambda v: 0 if v == 'unlimited' else (-1 if v == '0' else int(v))
        for config_option, value in [('maxdownloadrate', convert(valdown)), ('maxuploadrate', convert(valup))]:
            if self.utility.read_config(config_option) != value:
                self.utility.write_config(config_option, value)
                if config_option == 'maxuploadrate':
                    self.guiUtility.utility.session.set_max_upload_speed(value)
                else:
                    self.guiUtility.utility.session.set_max_download_speed(value)

        valport = self._firewall_value.GetValue()
        if valport != str(self.utility.session.get_listen_port()):
            scfg.set_listen_port(int(valport))
            scfg.set_dispersy_port(int(valport) - 1)
            self.saveDefaultDownloadConfig(scfg)

            self.guiUtility.set_firewall_restart(True)
            restart = True

        showSave = int(self._disk_location_choice.IsChecked())
        if showSave != self.utility.read_config('showsaveas'):
            self.utility.write_config('showsaveas', showSave)
            self.saveDefaultDownloadConfig(scfg)

        valdir = self._disk_location_ctrl.GetValue()
        if valdir != self.utility.read_config(u'saveas'):
            self.utility.write_config(u'saveas', valdir)
            self.defaultDLConfig.set_dest_dir(valdir)

            self.saveDefaultDownloadConfig(scfg)
            restart = True

        default_number_hops = self._sliderhops.GetValue()
        if default_number_hops != self.utility.read_config('default_number_hops'):
            self.utility.write_config('default_number_hops', default_number_hops)
            self.saveDefaultDownloadConfig(scfg)

        default_anonymity_chkbox = self._default_anonymity_dialog.UseTunnels()
        if default_anonymity_chkbox != self.utility.read_config('default_anonymity_enabled'):
            self.utility.write_config('default_anonymity_enabled', default_anonymity_chkbox)
            self.saveDefaultDownloadConfig(scfg)

        default_safeseeding_chkbox = self._default_anonymity_dialog.UseSafeSeeding()
        if default_safeseeding_chkbox != self.utility.read_config('default_safeseeding_enabled'):
            self.utility.write_config('default_safeseeding_enabled', default_safeseeding_chkbox)
            self.saveDefaultDownloadConfig(scfg)

        becomeExitNode = self._become_exitnode.IsChecked()
        if becomeExitNode != scfg.get_tunnel_community_exitnode_enabled():
            scfg.set_tunnel_community_exitnode_enabled(becomeExitNode)
            restart = True

        useWebUI = self._use_webui.IsChecked()
        if useWebUI != self.utility.read_config('use_webui'):
            self.utility.write_config('use_webui', useWebUI)
            restart = True

        valwebuiport = self._webui_port.GetValue()
        if valwebuiport != str(self.utility.read_config('webui_port')):
            self.utility.write_config('webui_port', valwebuiport)
            restart = True

        useEMC = self._use_emc.IsChecked()
        if useEMC != self.utility.read_config('use_emc'):
            self.utility.write_config('use_emc', useEMC)

        valemcip = self._emc_ip.GetValue()
        if valemcip != str(self.utility.read_config('emc_ip')):
            self.utility.write_config('emc_ip', valemcip)

        valemcport = self._emc_port.GetValue()
        if valemcport != str(self.utility.read_config('emc_port')):
            self.utility.write_config('emc_port', valemcport)

        valemcusername = self._emc_username.GetValue()
        if valemcusername != str(self.utility.read_config('emc_username')):
            self.utility.write_config('emc_username', valemcusername)

        valemcpassword = self._emc_password.GetValue()
        if valemcpassword != str(self.utility.read_config('emc_password')):
            self.utility.write_config('emc_pasword', valemcpassword)

        curMintray = self.utility.read_config('mintray')
        if self._minimize_to_tray:
            minimizeToTray = 1 if self._minimize_to_tray.IsChecked() else 0
            if minimizeToTray != curMintray:
                self.utility.write_config('mintray', minimizeToTray)

        for target in [scfg, self.utility.session]:
            try:
                target.set_nickname(self._my_name_field.GetValue())
                if getattr(self, 'icondata', False):
                    target.set_mugshot(self.icondata, mime='image/jpeg')
            except:
                self._logger.exception("Could not set target")

        for target in [scfg, self.utility.session]:
            if target.get_watch_folder_enabled() != self._use_watch_folder.GetValue():
                target.set_watch_folder_enabled(self._use_watch_folder.GetValue())
                restart = True

            if target.get_watch_folder_path() != self._wf_location_ctrl.GetValue():
                target.set_watch_folder_path(self._wf_location_ctrl.GetValue())
                restart = True

        seeding_mode = self.utility.read_config('seeding_mode', 'downloadconfig')
        for i, mode in enumerate(('ratio', 'forever', 'time', 'never')):
            if getattr(self, '_seeding%d' % i).GetValue():
                self.utility.write_config('seeding_mode', mode, 'downloadconfig')

                if mode != seeding_mode:
                    restart = True

                break
        seeding_ratio = float(self._seeding0choice.GetStringSelection())
        self.utility.write_config("seeding_ratio", seeding_ratio, 'downloadconfig')

        hours_min = self._seeding2text.GetValue()
        hours_min = hours_min.split(':')
        if len(hours_min) > 0:
            if len(hours_min) > 1:
                seeding_time = (int(hours_min[0]) * 60 + int(hours_min[1]))
            else:
                seeding_time = int(hours_min[0])
        else:
            seeding_time = 0
        self.utility.write_config("seeding_time", seeding_time, 'downloadconfig')

        # Proxy settings
        old_ptype, old_server, old_auth = self.utility.session.get_libtorrent_proxy_settings()
        new_ptype = self._lt_proxytype.GetSelection()
        new_server = (self._lt_proxyserver.GetValue(), int(self._lt_proxyport.GetValue())
                      ) if self._lt_proxyserver.GetValue() and self._lt_proxyport.GetValue() else None
        new_auth = (self._lt_proxyusername.GetValue(), self._lt_proxypassword.GetValue()
                    ) if self._lt_proxyusername.GetValue() and self._lt_proxypassword.GetValue() else None
        if old_ptype != new_ptype or old_server != new_server or old_auth != new_auth:
            self.utility.session.set_libtorrent_proxy_settings(new_ptype, new_server, new_auth)
            scfg.set_libtorrent_proxy_settings(new_ptype, new_server, new_auth)

        enable_utp = self._enable_utp.GetValue()
        if enable_utp != self.utility.session.get_libtorrent_utp():
            self.utility.session.set_libtorrent_utp(enable_utp)
            scfg.set_libtorrent_utp(enable_utp)

        # Multichain
        use_multichain = self._use_multichain.IsChecked()
        if use_multichain != self.utility.session.get_enable_multichain():
            scfg.set_enable_multichain(use_multichain)
            restart = True

        scfg.save(cfgfilename)

        self.utility.flush_config()

        if restart and not skip_restart_dialog:
            dlg = wx.MessageDialog(
                self, "A restart is required for these changes to take effect.\nDo you want to restart Tribler now?",
                                   "Restart required", wx.ICON_QUESTION | wx.YES_NO | wx.YES_DEFAULT)
            result = dlg.ShowModal()
            dlg.Destroy()
            if result == wx.ID_YES:
                self.guiUtility.frame.Restart()
        self.EndModal(1)
        event.Skip()

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

    def BrowseDownloadLocationClicked(self, event=None):
        dlg = wx.DirDialog(None, "Choose download directory", style=wx.DEFAULT_DIALOG_STYLE)
        dlg.SetPath(self.defaultDLConfig.get_dest_dir())
        if dlg.ShowModal() == wx.ID_OK:
            self._disk_location_ctrl.SetForegroundColour(wx.BLACK)
            self._disk_location_ctrl.SetValue(dlg.GetPath())

    def BrowseWatchFolderClicked(self, event=None):
        dlg = wx.DirDialog(None, "Choose watch folder", style=wx.DEFAULT_DIALOG_STYLE)
        dlg.SetPath(self.utility.session.get_watch_folder_path())
        if dlg.ShowModal() == wx.ID_OK:
            self._wf_location_ctrl.SetForegroundColour(wx.BLACK)
            self._wf_location_ctrl.SetValue(dlg.GetPath())

    def ProxyTypeChanged(self, event=None):
        selection = self._lt_proxytype.GetStringSelection()
        self._lt_proxyusername.Enable(selection.endswith('with authentication'))
        self._lt_proxypassword.Enable(selection.endswith('with authentication'))
        self._lt_proxyserver.Enable(selection != 'None')
        self._lt_proxyport.Enable(selection != 'None')

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
        cfgfilename = Session.get_default_config_filename(state_dir)

        scfg.save(cfgfilename)

    def process_input(self):
        try:
            im = wx.Image(self.iconpath)
            if im is None:
                self.show_inputerror("Could not open thumbnail file")
            else:
                if sys.platform != 'darwin':
                    bm = wx.BitmapFromImage(im.Scale(ICON_MAX_DIM, ICON_MAX_DIM), -1)
                    thumbpanel = self._thumb
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
            self._logger.exception("Could not read thumbnail")
            self.show_inputerror("The icon you selected is not in a supported format")

    def show_inputerror(self, txt):
        dlg = wx.MessageDialog(self, txt, "Invalid input", wx.OK | wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()

    def OnChooseLocationChecked(self, event):
        to_show = not self._disk_location_choice.GetValue()
        self._default_anonymous_label.Show(to_show)
        self._default_anonymity_dialog.Show(to_show)
        self.Layout()

    def __create_s1(self, tree_root, sizer):
        general_panel, gp_vsizer = create_section(self, sizer, "General")

        item_id = self._tree_ctrl.AppendItem(tree_root, "General", data=wx.TreeItemData(general_panel))

        # Tribler Profile
        gp_s1_sizer = create_subsection(general_panel, gp_vsizer, "Tribler Profile", 2)

        add_label(general_panel, gp_s1_sizer, "Nickname")
        self._my_name_field = wx.TextCtrl(general_panel, style=wx.TE_PROCESS_ENTER)
        self._my_name_field.SetMaxLength(40)
        gp_s1_sizer.Add(self._my_name_field, 1, wx.EXPAND)

        add_label(general_panel, gp_s1_sizer, "Profile Image")
        self._thumb = wx.StaticBitmap(general_panel, size=(80, 80))
        self._edit = wx.Button(general_panel, label="Change Image")
        gp_s1_porfile_vsizer = wx.BoxSizer(wx.VERTICAL)
        gp_s1_porfile_vsizer.Add(self._thumb, 0, wx.LEFT, 1)
        gp_s1_porfile_vsizer.Add(self._edit)
        gp_s1_sizer.Add(gp_s1_porfile_vsizer, 0, wx.TOP, 3)

        # Download Location
        gp_s2_sizer = create_subsection(general_panel, gp_vsizer, "Download Location", 1)

        gp_s2_label = wx.StaticText(general_panel, label="Save files to:")
        gp_s2_sizer.Add(gp_s2_label)
        gp_s2_hsizer = wx.BoxSizer(wx.HORIZONTAL)
        self._disk_location_ctrl = EditText(general_panel, validator=DirectoryValidator())
        gp_s2_hsizer.Add(self._disk_location_ctrl, 1, wx.ALIGN_CENTER_VERTICAL)
        self._browse_download_location = wx.Button(general_panel, label="Browse")
        gp_s2_hsizer.Add(self._browse_download_location)
        gp_s2_sizer.Add(gp_s2_hsizer, 0, wx.EXPAND)
        self._disk_location_choice = wx.CheckBox(general_panel, label="Let me choose a location for every download")
        self._disk_location_choice.Bind(wx.EVT_CHECKBOX, self.OnChooseLocationChecked)
        self._disk_location_choice.SetValue(False)

        gp_s2_sizer.Add(self._disk_location_choice)
        self._default_anonymous_label = wx.StaticText(general_panel, label="Default Anonymous Level:")
        self._default_anonymity_dialog = AnonymityDialog(general_panel)
        gp_s2_sizer.Add(self._default_anonymous_label, 0, wx.EXPAND)
        gp_s2_sizer.Add(self._default_anonymity_dialog, 0, wx.EXPAND)

        # Settings related to the watch folder - the watch folder is a place where .torrent files can be put.
        # They are automatically picked up by Tribler and added to the download queue if not there yet.
        gp_s3_sizer = create_subsection(general_panel, gp_vsizer, "Watch Folder", 1)
        self._use_watch_folder = wx.CheckBox(general_panel, label="Enable watch folder")
        self._use_watch_folder.SetValue(self.utility.session.get_watch_folder_enabled())
        gp_s3_sizer.Add(self._use_watch_folder, 0, wx.EXPAND)

        gp_s3_wf_path_label = wx.StaticText(general_panel, label="Watch folder path:")
        gp_s2_sizer.Add(gp_s3_wf_path_label)
        gp_s3_wf_path_hsizer = wx.BoxSizer(wx.HORIZONTAL)
        self._wf_location_ctrl = EditText(general_panel, validator=DirectoryValidator())
        self._wf_location_ctrl.SetValue(self.utility.session.get_watch_folder_path())
        gp_s3_wf_path_hsizer.Add(self._wf_location_ctrl, 1, wx.ALIGN_CENTER_VERTICAL)
        self._browse_wf_location = wx.Button(general_panel, label="Browse")
        self._browse_wf_location.Bind(wx.EVT_BUTTON, self.BrowseWatchFolderClicked)
        gp_s3_wf_path_hsizer.Add(self._browse_wf_location)
        gp_s3_sizer.Add(gp_s3_wf_path_hsizer, 0, wx.EXPAND)

        # Minimize
        if sys.platform == "darwin":
            self._minimize_to_tray = None
        else:
            gp_s3_sizer = create_subsection(general_panel, gp_vsizer, "Minimize", 1)

            self._minimize_to_tray = wx.CheckBox(general_panel, label="Minimize to tray")
            self._minimize_to_tray.SetValue(False)
            gp_s3_sizer.Add(self._minimize_to_tray)

        self._edit.Bind(wx.EVT_BUTTON, self.EditClicked)
        self._browse_download_location.Bind(wx.EVT_BUTTON, self.BrowseDownloadLocationClicked)

        # nickname
        self._my_name_field.SetValue(self.utility.session.get_nickname())
        # thumbnail
        mime, data = self.utility.session.get_mugshot()
        if data is None:
            gui_image_manager = GuiImageManager.getInstance()
            mugshot = gui_image_manager.getImage(u"PEER_THUMB")
        else:
            mugshot = data2wxBitmap(mime, data)
        self._thumb.SetBitmap(mugshot)
        # download location
        if self.utility.read_config('saveas'):
            location_dir = self.utility.read_config('saveas')
        else:
            location_dir = self.defaultDLConfig.get_dest_dir()
        self._disk_location_ctrl.SetValue(location_dir)
        self._disk_location_choice.SetValue(self.utility.read_config('showsaveas'))
        self.OnChooseLocationChecked(None)
        # minimize to tray
        if sys.platform != "darwin":
            min_to_tray = self.utility.read_config('mintray') == 1
            self._minimize_to_tray.SetValue(min_to_tray)

        return general_panel, item_id

    def __create_s2(self, tree_root, sizer):
        conn_panel, cn_vsizer = create_section(self, sizer, "Connection")

        item_id = self._tree_ctrl.AppendItem(tree_root, "Connection", data=wx.TreeItemData(conn_panel))

        # Firewall-status
        cn_s1_sizer = create_subsection(conn_panel, cn_vsizer, "Firewall-status", 2, 3)
        add_label(conn_panel, cn_s1_sizer, "Current port")
        self._firewall_value = EditText(conn_panel, validator=NumberValidator(min=1, max=65535))
        self._firewall_value.SetMinSize(wx.Size(150, -1))
        cn_s1_sizer.Add(self._firewall_value)

        add_label(conn_panel, cn_s1_sizer, "Status")
        self._firewall_status_text = wx.StaticText(conn_panel)
        cn_s1_sizer.Add(self._firewall_status_text)

        # BitTorrent proxy settings
        cn_s2_sizer = create_subsection(conn_panel, cn_vsizer, "BitTorrent proxy settings", 2, 3)
        add_label(conn_panel, cn_s2_sizer, "Type")
        self._lt_proxytype = wx.Choice(conn_panel)
        self._lt_proxytype.AppendItems(["None", "Socks4", "Socks5",
                                        "Socks5 with authentication", "HTTP", "HTTP with authentication"])
        cn_s2_sizer.Add(self._lt_proxytype)

        add_label(conn_panel, cn_s2_sizer, "Server")
        self._lt_proxyserver = wx.TextCtrl(conn_panel, style=wx.TE_PROCESS_ENTER)
        self._lt_proxyserver.SetMaxLength(1024)
        cn_s2_sizer.Add(self._lt_proxyserver, 0, wx.EXPAND)

        add_label(conn_panel, cn_s2_sizer, "Port")
        self._lt_proxyport = EditText(conn_panel, validator=NumberValidator(min=1, max=65535))
        self._lt_proxyport.SetMinSize(wx.Size(150, -1))
        cn_s2_sizer.Add(self._lt_proxyport, 0, wx.EXPAND)

        add_label(conn_panel, cn_s2_sizer, "Username")
        self._lt_proxyusername = wx.TextCtrl(conn_panel, style=wx.TE_PROCESS_ENTER)
        self._lt_proxyusername.SetMaxLength(255)
        cn_s2_sizer.Add(self._lt_proxyusername, 0, wx.EXPAND)

        add_label(conn_panel, cn_s2_sizer, "Password")
        self._lt_proxypassword = wx.TextCtrl(conn_panel, style=wx.TE_PROCESS_ENTER | wx.TE_PASSWORD)
        self._lt_proxypassword.SetMaxLength(255)
        cn_s2_sizer.Add(self._lt_proxypassword, 0, wx.EXPAND)

        # BitTorrent features
        cn_s3_sizer = create_subsection(conn_panel, cn_vsizer, "BitTorrent features", 1)
        self._enable_utp = wx.CheckBox(conn_panel, size=(200, -1),
                                       label="Enable bandwidth management (uTP)")
        cn_s3_sizer.Add(self._enable_utp, 0, wx.EXPAND)

        self._lt_proxytype.Bind(wx.EVT_CHOICE, self.ProxyTypeChanged)

        # firewall status
        if self.guiUtility.frame.SRstatusbar.IsReachable():
            self._firewall_status_text.SetLabel('Your network connection is working properly.')
        else:
            self._firewall_status_text.SetLabel(
                'Tribler has not yet received any incoming\nconnections. Unless you\'re using a proxy, this\ncould indicate a problem with your network\nconnection.')
        self._firewall_value.SetValue(str(self.utility.session.get_listen_port()))
        # uTP
        self._enable_utp.SetValue(self.utility.session.get_libtorrent_utp())
        # proxy
        ptype, server, auth = self.utility.session.get_libtorrent_proxy_settings()
        self._lt_proxytype.SetSelection(ptype)
        if server:
            self._lt_proxyserver.SetValue(server[0])
            self._lt_proxyport.SetValue(str(server[1]))
        if auth:
            self._lt_proxyusername.SetValue(auth[0])
            self._lt_proxypassword.SetValue(auth[1])
        self.ProxyTypeChanged()

        return conn_panel, item_id

    def __create_s3(self, tree_root, sizer):
        bandwidth_panel, bp_vsizer = create_section(self, sizer, "Bandwidth")

        item_id = self._tree_ctrl.AppendItem(tree_root, "Bandwidth", data=wx.TreeItemData(bandwidth_panel))

        # Bandwidth Limits
        bp_s1_sizer = create_subsection(bandwidth_panel, bp_vsizer, "Bandwidth Limits", 1)
        bp_s1_limitupload_label = wx.StaticText(bandwidth_panel, label="Limit upload rate")
        bp_s1_sizer.Add(bp_s1_limitupload_label)
        bp_s1_hsizer1 = wx.BoxSizer(wx.HORIZONTAL)
        self._upload_ctrl = EditText(bandwidth_panel, validator=NetworkSpeedValidator())
        bp_s1_hsizer1.Add(self._upload_ctrl)
        bp_s1_p1_label = wx.StaticText(bandwidth_panel, label="KB/s")
        bp_s1_hsizer1.Add(bp_s1_p1_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 3)
        bp_s1_hsizer1.AddStretchSpacer(1)
        # up buttons
        for btn_label1 in ("0", "50", "100", "unlimited"):
            bp_s1_p1_btn = wx.Button(bandwidth_panel, label=btn_label1, style=wx.BU_EXACTFIT)
            bp_s1_p1_btn.Bind(wx.EVT_BUTTON, lambda event, label=btn_label1: self.setUp(label, event))
            bp_s1_hsizer1.Add(bp_s1_p1_btn)
        bp_s1_sizer.Add(bp_s1_hsizer1, 0, wx.EXPAND)

        bp_s1_limitdownload_label = wx.StaticText(bandwidth_panel, label="Limit download rate")
        bp_s1_sizer.Add(bp_s1_limitdownload_label)
        bp_s1_hsizer2 = wx.BoxSizer(wx.HORIZONTAL)
        self._download_ctrl = EditText(bandwidth_panel, validator=NetworkSpeedValidator())
        bp_s1_hsizer2.Add(self._download_ctrl)
        bp_s1_p2_label = wx.StaticText(bandwidth_panel, label="KB/s")
        bp_s1_hsizer2.Add(bp_s1_p2_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 3)
        bp_s1_hsizer2.AddStretchSpacer(1)
        # down buttons
        for btn_label2 in ("75", "300", "600", "unlimited"):
            bp_s1_p2_btn = wx.Button(bandwidth_panel, label=btn_label2, style=wx.BU_EXACTFIT)
            bp_s1_p2_btn.Bind(wx.EVT_BUTTON, lambda event, label=btn_label2: self.setDown(label, event))
            bp_s1_hsizer2.Add(bp_s1_p2_btn)
        bp_s1_sizer.Add(bp_s1_hsizer2, 0, wx.EXPAND)

        bp_s1_bandwitdh_note = wx.StaticText(bandwidth_panel, label="\nPlease note that these settings apply to plain and tunneled downloads separately.")
        bp_s1_sizer.Add(bp_s1_bandwitdh_note)

        # upload/download rate
        convert = lambda v: 'unlimited' if v == 0 else ('0' if v == -1 else str(v))
        self._download_ctrl.SetValue(convert(self.utility.read_config('maxdownloadrate')))
        self._upload_ctrl.SetValue(convert(self.utility.read_config('maxuploadrate')))

        return bandwidth_panel, item_id

    def __create_s4(self, tree_root, sizer):
        seeding_panel, sd_vsizer = create_section(self, sizer, "Seeding")

        item_id = self._tree_ctrl.AppendItem(tree_root, "Seeding", data=wx.TreeItemData(seeding_panel))

        # Create the widgets
        sd_s1_sizer = create_subsection(seeding_panel, sd_vsizer, "BitTorrent-peers", 2)
        self._seeding0 = wx.RadioButton(seeding_panel, label="Seed until UL/DL ratio >", style=wx.RB_GROUP)
        sd_s1_sizer.Add(self._seeding0, 0, wx.ALIGN_CENTER_VERTICAL)
        self._seeding0choice = wx.Choice(seeding_panel)
        self._seeding0choice.AppendItems(["0.5", "0.75", "1.0", "1.5", "2.0", "3.0", "5.0"])
        sd_s1_sizer.Add(self._seeding0choice, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)

        self._seeding1 = wx.RadioButton(seeding_panel, label="Unlimited seeding")
        sd_s1_sizer.Add(self._seeding1, 0, wx.ALIGN_CENTER_VERTICAL)
        sd_s1_sizer.AddStretchSpacer()

        self._seeding2 = wx.RadioButton(seeding_panel, label="Seeding for (hours:minutes)")
        sd_s1_sizer.Add(self._seeding2, 0, wx.ALIGN_CENTER_VERTICAL)
        self._seeding2text = wx.lib.masked.textctrl.TextCtrl(seeding_panel)
        self._seeding2text.SetCtrlParameters(mask="##:##", defaultValue="00:00", useFixedWidthFont=False)
        sd_s1_sizer.Add(self._seeding2text)

        self._seeding3 = wx.RadioButton(seeding_panel, label="No seeding")
        sd_s1_sizer.Add(self._seeding3, 0, wx.ALIGN_CENTER_VERTICAL)

        # Set the on-file config values
        seeding_ratio = self.utility.read_config('seeding_ratio', 'downloadconfig')
        index = self._seeding0choice.FindString(str(seeding_ratio))
        if index != wx.NOT_FOUND:
            self._seeding0choice.Select(index)

        seeding_time = self.utility.read_config('seeding_time', 'downloadconfig') or 0
        seeding_minutes = seeding_time % 60
        seeding_hours = (seeding_time - seeding_minutes) / 60
        self._seeding2text.SetValue("%02d:%02d" % (seeding_hours, seeding_minutes))

        seeding_mode = self.utility.read_config('seeding_mode', 'downloadconfig')
        radios = {'ratio': self._seeding0,
                  'forever': self._seeding1,
                  'time': self._seeding2,
                  'never': self._seeding3,}

        radios[seeding_mode].SetValue(True)
        return seeding_panel, item_id

    def __create_s5(self, tree_root, sizer):
        exp_panel, exp_vsizer = create_section(self, sizer, "Experimental")

        item_id = self._tree_ctrl.AppendItem(tree_root, "Experimental", data=wx.TreeItemData(exp_panel))

        # Web UI
        exp_s1_sizer = create_subsection(exp_panel, exp_vsizer, "Web UI", 2, 3)
        self._use_webui = wx.CheckBox(exp_panel, label="Enable webUI")
        exp_s1_sizer.Add(self._use_webui, 0, wx.EXPAND)
        exp_s1_sizer.AddStretchSpacer()

        add_label(exp_panel, exp_s1_sizer, label="Current port")
        self._webui_port = EditText(exp_panel, validator=NumberValidator(min=1, max=65535))
        exp_s1_sizer.Add(self._webui_port, 0, wx.EXPAND)

        exp_s1_faq_text = wx.StaticText(
            exp_panel, label="The Tribler webUI implements the same API as uTorrent.\nThus all uTorrent remotes are compatible with it.\n\nFurthermore, we additionally allow you to control Tribler\nusing your Browser. Go to http://localhost:PORT/gui to\nview your downloads in the browser.")
        exp_vsizer.Add(exp_s1_faq_text, 0, wx.EXPAND | wx.TOP, 10)

        # Emercoin
        exp_s2_sizer = create_subsection(exp_panel, exp_vsizer, "Emercoin", 2, 3)
        self._use_emc = wx.CheckBox(exp_panel, label="Enable Emercoin integration")
        exp_s2_sizer.Add(self._use_emc, 0, wx.EXPAND)
        exp_s2_sizer.AddStretchSpacer()

        add_label(exp_panel, exp_s2_sizer, "Server")
        self._emc_ip = wx.TextCtrl(exp_panel, style=wx.TE_PROCESS_ENTER)
        exp_s2_sizer.Add(self._emc_ip, 0, wx.EXPAND)

        add_label(exp_panel, exp_s2_sizer, "Port")
        self._emc_port = EditText(exp_panel, validator=NumberValidator(min=1, max=65535))
        exp_s2_sizer.Add(self._emc_port, 0, wx.EXPAND)

        add_label(exp_panel, exp_s2_sizer, "Username")
        self._emc_username = wx.TextCtrl(exp_panel, style=wx.TE_PROCESS_ENTER)
        self._emc_username.SetMaxLength(255)
        exp_s2_sizer.Add(self._emc_username, 0, wx.EXPAND)

        add_label(exp_panel, exp_s2_sizer, "Password")
        self._emc_password = wx.TextCtrl(exp_panel, style=wx.TE_PROCESS_ENTER | wx.TE_PASSWORD)
        self._emc_password.SetMaxLength(255)
        exp_s2_sizer.Add(self._emc_password, 0, wx.EXPAND)

        exp_s2_faq_text = wx.StaticText(
            exp_panel, label="Tribler connects to Emercoin over its JSON-RPC API.\nThis requires you to enable it by editing the emercoin.conf file and setting\nserver=1, rpcport, rpcuser, rpcpassword, and rpcconnect.")
        exp_vsizer.Add(exp_s2_faq_text, 0, wx.EXPAND | wx.TOP, 10)

        # load values
        self._use_webui.SetValue(self.utility.read_config('use_webui'))
        self._webui_port.SetValue(str(self.utility.read_config('webui_port')))

        self._use_emc.SetValue(self.utility.read_config('use_emc'))
        self._emc_ip.SetValue(self.utility.read_config('emc_ip'))
        self._emc_port.SetValue(str(self.utility.read_config('emc_port')))
        self._emc_username.SetValue(self.utility.read_config('emc_username'))
        self._emc_password.SetValue(self.utility.read_config('emc_password'))

        return exp_panel, item_id

    def __create_s6(self, tree_root, sizer):
        exp_panel, exp_vsizer = create_section(self, sizer, "Anonymity")

        item_id = self._tree_ctrl.AppendItem(tree_root, "Anonymity", data=wx.TreeItemData(exp_panel))

        exp_s1_sizer = create_subsection(exp_panel, exp_vsizer, "Anonymity in Tribler", 1, 3)
        self._become_exitnode = wx.CheckBox(exp_panel, label="Allow being an exit node")
        exp_s1_sizer.Add(self._become_exitnode, 0, wx.EXPAND)
        exp_s1_faq_text = wx.StaticText(
            exp_panel, label="By allowing Tribler to be an exit node, your computer will act as a proxy for other Tribler users' bittorrent traffic, be it seeding or downloading. \n"
            "Check your local laws and make sure you are aware of the implications of enabling this checkbox.")
        exp_s1_sizer.Add(exp_s1_faq_text, 0, wx.EXPAND | wx.TOP, 10)

        # Add slider
        self._lbls = []
        self.sliderlabels = wx.BoxSizer(wx.HORIZONTAL)
        lbl = wx.StaticText(exp_panel, -1, 'High speed\nMinimum anonymity', style=wx.ALIGN_CENTRE_HORIZONTAL)
        self._lbls.append(lbl)
        self.sliderlabels.Add(lbl)
        self.sliderlabels.AddStretchSpacer()
        lbl = wx.StaticText(exp_panel, -1, 'Low speed\nStrong anonymity', style=wx.ALIGN_CENTRE_HORIZONTAL)
        self._lbls.append(lbl)
        self.sliderlabels.Add(lbl)

        self.slider_images = [GuiImageManager.getInstance().getImage(u"scale_%d.png" % i) for i in range(6)]
        self.slider_bitmap = wx.StaticBitmap(exp_panel, -1, self.slider_images[0])

        self._sliderhops = wx.Slider(exp_panel, -1, 1, 1, 3, wx.DefaultPosition, style=wx.SL_AUTOTICKS | wx.SL_HORIZONTAL)
        self._sliderhops.Bind(wx.EVT_SLIDER, self.OnSlideHops)

        hop_count = wx.BoxSizer(wx.HORIZONTAL)
        hop_count.AddSpacer((10, -1))
        for count in xrange(1, 4):
            lbl = wx.StaticText(exp_panel, -1, '%d' % count, style=wx.ALIGN_CENTRE_HORIZONTAL)
            self._lbls.append(lbl)
            hop_count.Add(lbl)
            if count != 3:
                hop_count.AddStretchSpacer()
            else:
                hop_count.AddSpacer((10, -1))

        labels_and_slider = wx.BoxSizer(wx.VERTICAL)
        labels_and_slider.Add(self.sliderlabels, 0, wx.EXPAND)
        labels_and_slider.Add(self._sliderhops, 0, wx.EXPAND)
        labels_and_slider.Add(hop_count, 0, wx.EXPAND)

        slider_sizer = wx.BoxSizer(wx.HORIZONTAL)
        slider_sizer.Add(labels_and_slider, 1, wx.RIGHT, 10)
        slider_sizer.Add(self.slider_bitmap)

        proxytext = wx.StaticText(exp_panel, -1, 'Please select how many encrypted hops you want to use for your downloads:')

        exp_s2_sizer = create_subsection(exp_panel, exp_vsizer, "Proxy downloading", 1, 3)
        exp_s2_sizer.Add(proxytext, 0, wx.EXPAND | wx.BOTTOM, 10)
        exp_s2_sizer.Add(slider_sizer, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 5)

        exp_s3_sizer = create_subsection(exp_panel, exp_vsizer, "Multichain", 1, 3)
        multichain_text = wx.StaticText(exp_panel, -1, 'Multichain is a blockchain-based way to keep track of sharing ratio, and eventually prevent freeriding.\nIt is currently still in an early phase of development.')
        exp_s3_sizer.Add(multichain_text, 0, wx.EXPAND | wx.TOP, 5)
        self._use_multichain = wx.CheckBox(exp_panel, label="Enable multichain")
        exp_s3_sizer.Add(self._use_multichain, 0, wx.EXPAND)

        # load values
        self._become_exitnode.SetValue(self.utility.session.get_tunnel_community_exitnode_enabled())
        self._sliderhops.SetValue(self.utility.read_config('default_number_hops'))
        self._use_multichain.SetValue(self.utility.session.get_enable_multichain())

        return exp_panel, item_id

    def OnSlideHops(self, event):
        self.slider_bitmap.SetBitmap(self.slider_images[self._sliderhops.GetValue()])
