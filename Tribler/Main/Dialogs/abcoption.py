# ARNOCOMMENT: Rewrite this such that it uses SessionConfig and cleanup of
# unused abc.conf params. See also Tribler/Utility/utility.py and others.

# TODO: 
# - Add ratelimiter to tribler Session. Wait on Jelle checkin
# - Adhere to SeedingOptions. Wait on Jelle checkin
# - Make Core adhere to diskfullthreshold
# - Remove old config params from Tribler.Main.Utility class

import sys
import wx
import os

from random import shuffle
from traceback import print_exc
from cStringIO import StringIO

from wx.lib import colourselect

from Tribler.Main.Dialogs.abcmenu import MenuDialog
from Tribler.Main.Utility.configreader import ConfigReader
from Tribler.Main.Utility.constants import * #IGNORE:W0611
from Tribler.Main.globals import DefaultDownloadStartupConfig,get_default_dscfg_filename

from Tribler.Main.Dialogs.socnetmyinfo import MyInfoWizard
from Tribler.Video.VideoPlayer import *

from Tribler.Core.API import *
from Tribler.Core.Utilities.utilities import show_permid
from Tribler.Core.osutils import getfreespace

DEBUG = False


################################################################
#
# Class: ABCOptionPanel
#
# Basic structure for options window panels
#
# Adds a button for "Restore Defaults"
# at the bottom of each panel
#
################################################################
class ABCOptionPanel(wx.Panel):
    def __init__(self, parent, dialog):
        wx.Panel.__init__(self, parent, -1)
        
        self.dialog = dialog
        self.utility = dialog.utility
        
        self.changed = False
        
        self.outersizer = wx.BoxSizer(wx.VERTICAL)
        
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        
        self.defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
        
    # Things to do after the subclass has finished its init stage
    def initTasks(self):
        self.loadValues()
        
        self.outersizer.Add(self.sizer, 1, wx.EXPAND)
        
        defaultsButton = wx.Button(self, -1, self.utility.lang.get('reverttodefault'))
        wx.EVT_BUTTON(self, defaultsButton.GetId(), self.setDefaults)
        self.outersizer.Add(defaultsButton, 0, wx.ALIGN_RIGHT|wx.TOP|wx.BOTTOM, 10)

        self.SetSizerAndFit(self.outersizer)

    def loadValues(self, Read = None):
        # Dummy function that class members should override
        pass

    def setDefaults(self, event = None):
        self.loadValues(self.utility.config.ReadDefault)
        
    def apply(self):
        # Dummy function that class members should override
        pass


################################################################
#
# Class: NetworkPanel
#
# Contains network settings
#
################################################################
class NetworkPanel(ABCOptionPanel):
    def __init__(self, parent, dialog):
        ABCOptionPanel.__init__(self, parent, dialog)
        sizer = self.sizer

        ip = self.utility.session.get_external_ip()
        ip_txt = self.utility.lang.get('currentdiscoveredipaddress')+": "+ip
        label = wx.StaticText(self, -1, ip_txt )
        sizer.Add( label, 0, wx.EXPAND|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)


        self.minport = self.utility.makeNumCtrl(self, 1, min = 1, max = 65536)
        port_box = wx.BoxSizer(wx.HORIZONTAL)
        port_box.Add(wx.StaticText(self, -1, self.utility.lang.get('portnumber')), 0, wx.ALIGN_CENTER_VERTICAL)
        port_box.Add(self.minport, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        port_box.Add(wx.StaticText(self, -1, self.utility.lang.get('restartabc')), 0, wx.ALIGN_CENTER_VERTICAL)

        sizer.Add(port_box, 0, wx.EXPAND|wx.ALL, 5)

        self.kickban = wx.CheckBox(self, -1, self.utility.lang.get('kickban'))
        sizer.Add(self.kickban, 0, wx.ALIGN_LEFT|wx.ALL, 5)

        # Do or don't get scrape data
        ###################################################################
        self.scrape = wx.CheckBox(self, -1, self.utility.lang.get('scrape'))
        sizer.Add(self.scrape, 0, wx.ALIGN_LEFT|wx.ALL, 5)
        self.scrape.SetToolTipString(self.utility.lang.get('scrape_hint'))

        ###################################################################        
        #self.ipv6 = wx.CheckBox(self, -1, "Initiate and receive connections via IPv6")
        #if self.utility.config.Read('ipv6') == "1":
        #    self.ipv6.SetValue(True)
        #else:
        #    self.ipv6.SetValue(False)
        ####################################################################

        # URL of internal tracker, user should use it in annouce box / announce-list
        itrack_box = wx.BoxSizer(wx.HORIZONTAL)
        self.itrack = wx.TextCtrl(self, -1, "")
        itrack_box.Add(wx.StaticText(self, -1, self.utility.lang.get('internaltrackerurl')), 0, wx.ALIGN_CENTER_VERTICAL)
        itrack_box.Add(self.itrack, 1, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT|wx.EXPAND, 5)
        sizer.Add(itrack_box, 0, wx.ALIGN_LEFT|wx.ALL|wx.EXPAND, 5)

        self.initTasks()
        
    def loadValues(self, Read = None):
        
        self.minport.SetValue(self.utility.session.get_listen_port())
        itrackerurl = self.utility.session.get_internal_tracker_url()
        self.itrack.SetValue(itrackerurl)

        #self.scrape.SetValue(Read('scrape', "boolean")) # TODO: cannot find it being used
        
        self.kickban.SetValue(self.defaultDLConfig.get_auto_kick())
        
    def apply(self):
        minport = int(self.minport.GetValue())
        if minport > 65535:
            minport = 65535

        itrackerurl = self.itrack.GetValue()

        # Save SessionStartupConfig
        state_dir = self.utility.session.get_state_dir()
        cfgfilename = Session.get_default_config_filename(state_dir)
        scfg = SessionStartupConfig.load(cfgfilename)
        
        for target in [scfg,self.utility.session]:
            try:
                target.set_listen_port(minport)
            except:
                print_exc()
            try:
                target.set_internal_tracker_url(itrackerurl)
            except:
                print_exc()


        scfg.save(cfgfilename)

        #self.utility.config.Write('scrape', self.scrape.GetValue(), "boolean")

        kickban = self.kickban.GetValue()

        # Save DownloadStartupConfig
        self.defaultDLConfig.set_auto_kick(kickban)
        
        dlcfgfilename = get_default_dscfg_filename(self.utility.session)
        self.defaultDLConfig.save(dlcfgfilename)


################################################################
#
# Class: AdvancedNetworkPanel
#
# Contains advanced network settings
# (defaults should be fine for most users)
#
################################################################
class AdvancedNetworkPanel(ABCOptionPanel):
    def __init__(self, parent, dialog):
        ABCOptionPanel.__init__(self, parent, dialog)
        sizer = self.sizer

        warningtext = wx.StaticText(self, -1, self.utility.lang.get('changeownrisk'))
        sizer.Add(warningtext, 0, wx.ALIGN_CENTER|wx.ALL, 5)
       
        #self.ipv6bindsv4_data=wx.Choice(self, -1,
        #                 choices = ['separate sockets', 'single socket'])
        #self.ipv6bindsv4_data.SetSelection(int(self.advancedConfig['ipv6_binds_v4']))
        
        datasizer = wx.FlexGridSizer(cols = 2, vgap = 5, hgap = 10)

        # Local IP
        self.ip_data = wx.TextCtrl(self, -1)
        datasizer.Add(wx.StaticText(self, -1, self.utility.lang.get('localip')), 1, wx.ALIGN_CENTER_VERTICAL)
        datasizer.Add(self.ip_data)

        # IP to Bind to
        self.bind_data = wx.TextCtrl(self, -1)
        datasizer.Add(wx.StaticText(self, -1, self.utility.lang.get('iptobindto')), 1, wx.ALIGN_CENTER_VERTICAL)
        datasizer.Add(self.bind_data)

        # Minimum Peers
        self.minpeers_data = wx.SpinCtrl(self, size = wx.Size(60, -1))
        self.minpeers_data.SetRange(10, 100)
        datasizer.Add(wx.StaticText(self, -1, self.utility.lang.get('minnumberofpeer')), 1, wx.ALIGN_CENTER_VERTICAL)
        datasizer.Add(self.minpeers_data)

        # Maximum Connections
        self.maxconnections_data=wx.SpinCtrl(self, size = wx.Size(60, -1))
        self.maxconnections_data.SetRange(0, 1000)
        datasizer.Add(wx.StaticText(self, -1, self.utility.lang.get('maxpeerconnection')), 1, wx.ALIGN_CENTER_VERTICAL)
        datasizer.Add(self.maxconnections_data)
        
        # UPnP Settings
        if (sys.platform == 'win32'):
            self.upnp_choices = [ self.utility.lang.get('upnp_0'), 
                             self.utility.lang.get('upnp_1'), 
                             self.utility.lang.get('upnp_2'),
                             self.utility.lang.get('upnp_3')]
        else:
            self.upnp_choices = [ self.utility.lang.get('upnp_0'), 
                             self.utility.lang.get('upnp_3')]
        self.upnp_data = wx.ComboBox(self, -1, "", wx.Point(-1, -1), wx.Size(-1, -1), self.upnp_choices, wx.CB_DROPDOWN|wx.CB_READONLY)
        datasizer.Add(wx.StaticText(self, -1, self.utility.lang.get('upnp')), 1, wx.ALIGN_CENTER_VERTICAL)
        datasizer.Add(self.upnp_data)


        # ut_pex maximum Peers
        self.ut_pex_maxaddrs_data = wx.SpinCtrl(self, size = wx.Size(60, -1))
        self.ut_pex_maxaddrs_data.SetRange(0, 1024)
        t1 = wx.StaticText(self, -1, self.utility.lang.get('ut_pex_maxaddrs1'))
        t2 = wx.StaticText(self, -1, self.utility.lang.get('ut_pex_maxaddrs2'))
        tsizer = wx.BoxSizer(wx.VERTICAL)
        tsizer.Add(t1, 1, wx.ALIGN_LEFT)
        tsizer.Add(t2, 1, wx.ALIGN_LEFT)
        datasizer.Add(tsizer, 1, wx.ALIGN_CENTER_VERTICAL)
        datasizer.Add(self.ut_pex_maxaddrs_data)
        sizer.Add(datasizer, 0, wx.ALL, 5)
        
        # Set tooltips
        self.ip_data.SetToolTipString(self.utility.lang.get('iphint'))
        self.bind_data.SetToolTipString(self.utility.lang.get('bindhint'))
        self.minpeers_data.SetToolTipString(self.utility.lang.get('minpeershint'))
        self.ut_pex_maxaddrs_data.SetToolTipString(self.utility.lang.get('ut_pex_maxaddrs_hint'))
        self.maxconnections_data.SetToolTipString(self.utility.lang.get('maxconnectionhint'))
               
        self.initTasks()

    def loadValues(self, Read = None):
        if Read is None:
            Read = self.utility.config.Read
        session = self.utility.session
        
        addrlist = session.get_bind_to_addresses()
        addrstr = ','.join(addrlist)
        
        self.ip_data.SetValue(session.get_ip_for_tracker())
        self.bind_data.SetValue(addrstr)
        
        self.minpeers_data.SetValue(self.defaultDLConfig.get_min_peers())
        self.maxconnections_data.SetValue(self.defaultDLConfig.get_max_conns())
        
        upnp_val = session.get_upnp_mode()
        selected = self.upnp_val2selected(upnp_val)
        self.upnp_data.SetStringSelection(self.upnp_choices[selected])

        self.ut_pex_maxaddrs_data.SetValue(self.defaultDLConfig.get_ut_pex_max_addrs_from_peer())

        
    def upnp_val2selected(self,upnp_val):
        if (sys.platform == 'win32'):
            selected = upnp_val
        else:
            if upnp_val <= 2:
                selected = 0
            else:
                selected = 1
        return selected

    def selected2upnp_val(self,selected):
        if (sys.platform == 'win32'):
            upnp_val = selected
        else:
            if selected == 1:
                upnp_val = UPNPMODE_UNIVERSAL_DIRECT
            else:
                upnp_val = UPNPMODE_DISABLED
        return upnp_val
        

    def apply(self):
        
        ip4track = self.ip_data.GetValue()
        ip2bind2 = self.bind_data.GetValue()
        ip2bind2list = ip2bind2.split(",")

        selected = self.upnp_choices.index(self.upnp_data.GetValue())
        upnp_val = self.selected2upnp_val(selected)

        minpeers = int(self.minpeers_data.GetValue())
        maxconnections = int(self.maxconnections_data.GetValue())
        if maxconnections == 0:
            maxinitiate = 2 * minpeers
        else:
            maxinitiate = min(2 * minpeers, maxconnections)
        utmaxaddrs = int(self.ut_pex_maxaddrs_data.GetValue())


        # Save SessConfig
        state_dir = self.utility.session.get_state_dir()
        cfgfilename = Session.get_default_config_filename(state_dir)
        scfg = SessionStartupConfig.load(cfgfilename)
        
        for target in [scfg,self.utility.session]:
            try:
                target.set_ip_for_tracker(ip4track)
            except:
                print_exc()
            try:
                target.set_bind_to_addresses(ip2bind2list)
            except:
                print_exc()
            try:
                target.set_upnp_mode(upnp_val)
            except:
                print_exc()

        scfg.save(cfgfilename)

        # Save DownloadStartupConfig
        self.defaultDLConfig.set_min_peers(minpeers)
        self.defaultDLConfig.set_max_conns(maxconnections)
        self.defaultDLConfig.set_max_conns_to_initiate(maxinitiate)
        self.defaultDLConfig.set_ut_pex_max_addrs_from_peer(utmaxaddrs)
        
        dlcfgfilename = get_default_dscfg_filename(self.utility.session)
        self.defaultDLConfig.save(dlcfgfilename)
            

################################################################
#
# Class: QueuePanel
#
# Contains settings that control how many torrents to start
# at once and when to start them
#
################################################################

# Arno, 2008-03-27: Currently disabled. Need to write queueing support on top 
# of core


################################################################
#
# Class: MiscPanel
#
# Contains settings that don't seem to fit well anywhere else
#
################################################################
class MiscPanel(ABCOptionPanel):
    def __init__(self, parent, dialog):
        ABCOptionPanel.__init__(self, parent, dialog)
        sizer = self.sizer
        
        self.trayoptions = [self.utility.lang.get('showtray_never'), 
                            self.utility.lang.get('showtray_min'), 
                            self.utility.lang.get('showtray_always')]
        self.mintray = wx.RadioBox(self, 
                                    -1, 
                                    self.utility.lang.get('showtray'), 
                                    wx.DefaultPosition, 
                                    wx.DefaultSize, 
                                    self.trayoptions, 
                                    3, 
                                    wx.RA_SPECIFY_COLS)

        # On the Mac, the option exists but is not shown, to support
        # the widget being read & written.
        if sys.platform != "darwin":
            sizer.Add(self.mintray, 0, wx.ALIGN_LEFT|wx.ALL, 5)
        else:
            self.mintray.Hide()
               
        self.confirmonclose = wx.CheckBox(self, -1, self.utility.lang.get('confirmonexit'))
        sizer.Add(self.confirmonclose, 0, wx.ALIGN_LEFT|wx.ALL, 5)

        # Registry association (only makes sense under windows)
        if (sys.platform == 'win32'):
            self.associate = wx.CheckBox(self, -1, self.utility.lang.get('associate'))
            sizer.Add(self.associate, 0, wx.ALIGN_LEFT|wx.ALL, 5)

        # Languages option
        if self.utility.languages == {}:
            self.getLanguages()
        self.language_names = []
        self.language_filenames = []
        for item in self.utility.languages:
            self.language_names.append(item)
            self.language_filenames.append(self.utility.languages[item])
       
        self.language_choice = wx.ComboBox(self, -1, "", wx.Point(-1, -1), wx.Size(-1, -1), self.language_names, wx.CB_DROPDOWN|wx.CB_READONLY)
        
        lang_box = wx.BoxSizer(wx.HORIZONTAL)
        lang_box.Add(wx.StaticText(self, -1, self.utility.lang.get('choose_language')), 0, wx.ALIGN_CENTER_VERTICAL)
        lang_box.Add(self.language_choice, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        lang_box.Add(wx.StaticText(self, -1, self.utility.lang.get('restartabc')), 0, wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(lang_box, 0, wx.ALL, 5)
        
        self.initTasks()
        
    def loadValues(self, Read = None):
        if Read is None:
            Read = self.utility.config.Read
        
        mintray = Read('mintray', "int")
        if mintray >= len(self.trayoptions):
            mintray = len(self.trayoptions) - 1
        self.mintray.SetSelection(mintray)
        
        self.confirmonclose.SetValue(Read('confirmonclose', "boolean"))
        
        if (sys.platform == 'win32'):
            self.associate.SetValue(Read('associate', "boolean"))        
        
        index = self.language_filenames.index(Read('language_file'))
        if not self.language_names:
            # Should never get here -- this means there are no valid language files found!
            sys.stderr.write("\nNO LANGUAGE FILES FOUND!  Please add a valid language file\n")
            defaultlang = ""
        elif (index > -1):
            defaultlang = self.language_names[index]
        self.language_choice.SetStringSelection(defaultlang)
              
    def apply(self):       
        self.utility.config.Write('mintray', self.mintray.GetSelection())
        if self.utility.frame.tbicon is not None:
            self.utility.frame.tbicon.updateIcon(False)
        
        # FIXME: quick hack to prevent Unicode problem, will still give problems
        # when French, i.e. "fran\,cais" is selected.
        #
        val = str(self.language_choice.GetValue())
        langname_index = self.language_names.index(val)
        self.utility.config.Write('language_file', self.language_filenames[langname_index])
        
        self.utility.config.Write('confirmonclose', self.confirmonclose.GetValue(), "boolean")
        
        if (sys.platform == 'win32'):
            self.utility.config.Write('associate', self.associate.GetValue(), "boolean")

    def getLanguages(self):
        langpath = os.path.join(self.utility.getPath(),"Tribler","Lang")
        
        dirlist = os.listdir(langpath)
        dirlist2 = []
        for filename in dirlist:
            if (filename[-5:] == '.lang'):
                dirlist2.append(filename)
        dirlist2.sort()
        
        # Remove user.lang from the list
        try:
            dirlist2.remove("user.lang")
        except:
            pass
        
        self.utility.languages = {}
        
        for filename in dirlist2:
            filepath = os.path.join(langpath, filename)

            config = wx.FileConfig(localFilename = filepath)
            config.SetPath("ABC/language")
            if config.Exists('languagename'):
                self.utility.languages[config.Read('languagename')] = filename


################################################################
#
# Class: DiskPanel
#
# Contains settings related to saving files
#
################################################################
class DiskPanel(ABCOptionPanel):
    def __init__(self, parent, dialog):
        ABCOptionPanel.__init__(self, parent, dialog)
        sizer = self.sizer
                      
        self.torrentbackup = wx.CheckBox(self, -1, self.utility.lang.get('removebackuptorrent'))
        sizer.Add(self.torrentbackup, 0, wx.ALIGN_LEFT|wx.ALL, 5)

        self.defaultdir = wx.StaticText(self, -1, self.utility.lang.get('setdefaultfolder'))
        self.dir = wx.TextCtrl(self, -1, "")
        browsebtn = wx.Button(self, -1, "...", style = wx.BU_EXACTFIT)
        self.Bind(wx.EVT_BUTTON, self.onBrowseDir, browsebtn)

        dirbox = wx.BoxSizer(wx.HORIZONTAL)
        dirbox.Add(self.defaultdir, 0, wx.ALIGN_CENTER_VERTICAL)
        dirbox.Add(self.dir, 1, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT|wx.EXPAND, 5)
        dirbox.Add(browsebtn, 0, wx.ALIGN_CENTER_VERTICAL)

        sizer.Add(dirbox, 0, wx.ALIGN_LEFT|wx.ALL|wx.EXPAND, 5)

        diskfullbox = wx.BoxSizer(wx.HORIZONTAL)
        self.diskfullcheckbox = wx.CheckBox(self, -1, self.utility.lang.get('diskfullthreshold'))
        self.diskfullthreshold = self.utility.makeNumCtrl(self, 1, integerWidth = 4)
        diskfullbox.Add(self.diskfullcheckbox, 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)
        diskfullbox.Add(self.diskfullthreshold, 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)
        diskfullbox.Add(wx.StaticText(self, -1, self.utility.lang.get('MB')), 0, wx.ALIGN_CENTER_VERTICAL)
        
        sizer.Add(diskfullbox, 0, wx.ALIGN_LEFT|wx.ALL, 5)

        self.initTasks()

    def loadValues(self, Read = None):
        if Read is None:
            Read = self.utility.config.Read

        self.dir.SetValue(self.defaultDLConfig.get_dest_dir())
        self.torrentbackup.SetValue(Read('removetorrent', "boolean"))
        
        diskfullthreshold = Read('diskfullthreshold', "int") # TODO: make sure Core uses this
        if diskfullthreshold > 0:
            self.diskfullcheckbox.SetValue(True)
            self.diskfullthreshold.SetValue(diskfullthreshold)
        
    def apply(self):
        self.utility.config.Write('removetorrent', self.torrentbackup.GetValue(), "boolean")

        if self.diskfullcheckbox.GetValue():
            diskfullthreshold = self.diskfullthreshold.GetValue()
        else:
            diskfullthreshold = 0
        self.utility.config.Write('diskfullthreshold', diskfullthreshold)

        # Save DownloadStartupConfig
        defaultdestdir = self.dir.GetValue()
        self.defaultDLConfig.set_dest_dir(defaultdestdir)
        
        dlcfgfilename = get_default_dscfg_filename(self.utility.session)
        self.defaultDLConfig.save(dlcfgfilename)
        

        
    def onBrowseDir(self, event = None):
        dlg = wx.DirDialog(self.utility.frame, 
                           self.utility.lang.get('choosedefaultdownloadfolder'), 
                           style = wx.DD_DEFAULT_STYLE | wx.DD_NEW_DIR_BUTTON)
        if dlg.ShowModal() == wx.ID_OK:
            self.dir.SetValue(dlg.GetPath())
        dlg.Destroy()


################################################################
#
# Class: AdvancedDiskPanel
#
# Contains advanced settings controlling how data is written to
# and read from disk.
# (defaults should be fine for most users)
#
################################################################
class AdvancedDiskPanel(ABCOptionPanel):
    def __init__(self, parent, dialog):
        ABCOptionPanel.__init__(self, parent, dialog)
        sizer = self.sizer

        warningtext = wx.StaticText(self, -1, self.utility.lang.get('changeownrisk'))
        sizer.Add(warningtext, 0, wx.ALIGN_CENTER|wx.ALL, 5)
       
        datasizer = wx.FlexGridSizer(cols = 2, vgap = 5, hgap = 10)

        # Allocation Type
        
        alloc_choices = [self.utility.lang.get('alloc_normal'), 
                         self.utility.lang.get('alloc_background'), 
                         self.utility.lang.get('alloc_prealloc'), 
                         self.utility.lang.get('alloc_sparse')]
        self.alloc_types = [DISKALLOC_NORMAL, DISKALLOC_BACKGROUND, DISKALLOC_PREALLOCATE, DISKALLOC_SPARSE]
        self.alloc_type2int = {}
        for i in range(len(self.alloc_types)):
            t = self.alloc_types[i]
            self.alloc_type2int[t]=i
        self.alloctype_data=wx.Choice(self, -1, wx.Point(-1, -1), wx.Size(-1, -1), alloc_choices)

        datasizer.Add(wx.StaticText(self, -1, self.utility.lang.get('diskalloctype')), 1, wx.ALIGN_CENTER_VERTICAL)
        datasizer.Add(self.alloctype_data)

        # Allocation Rate
        self.allocrate_data = wx.SpinCtrl(self, size = wx.Size(60, -1))
        self.allocrate_data.SetRange(1, 100)
        datasizer.Add(wx.StaticText(self, -1, self.utility.lang.get('allocrate')), 1, wx.ALIGN_CENTER_VERTICAL)
        
        allocrate_box = wx.BoxSizer(wx.HORIZONTAL)
        allocrate_box.Add(self.allocrate_data)
        allocrate_box.Add(wx.StaticText(self, -1, " " + self.utility.lang.get('mb') + "/" + self.utility.lang.get("l_second")), 1, wx.ALIGN_CENTER_VERTICAL)
        
        datasizer.Add(allocrate_box)

        # Locking Method
        locking_choices = [self.utility.lang.get('lock_never'), 
                           self.utility.lang.get('lock_writing'), 
                           self.utility.lang.get('lock_always')]
        self.locking_data=wx.Choice(self, -1, wx.Point(-1, -1), wx.Size(-1, -1), locking_choices)
        datasizer.Add(wx.StaticText(self, -1, self.utility.lang.get('filelocking')), 1, wx.ALIGN_CENTER_VERTICAL)
        datasizer.Add(self.locking_data)

        # Doublecheck Method
        doublecheck_choices = [self.utility.lang.get('check_none'), 
                               self.utility.lang.get('check_double'), 
                               self.utility.lang.get('check_triple')]
        self.doublecheck_data=wx.Choice(self, -1, wx.Point(-1, -1), wx.Size(-1, -1), doublecheck_choices)
        datasizer.Add(wx.StaticText(self, -1, self.utility.lang.get('extradatachecking')), 1, wx.ALIGN_CENTER_VERTICAL)
        datasizer.Add(self.doublecheck_data)

        # Maximum Files Open
        self.maxfilesopen_data=wx.SpinCtrl(self, size = wx.Size(60, -1))
        self.maxfilesopen_data.SetRange(0,200)

        datasizer.Add(wx.StaticText(self, -1, self.utility.lang.get('maxfileopen')), 1, wx.ALIGN_CENTER_VERTICAL)
        datasizer.Add(self.maxfilesopen_data)        
      
        # Flush data        
        self.flush_data_enable = wx.CheckBox(self, -1, self.utility.lang.get('flush_data'))

        self.flush_data = wx.SpinCtrl(self, size = wx.Size(60, -1))
        self.flush_data.SetRange(0, 999)
        
        datasizer.Add(self.flush_data_enable, 0, wx.ALIGN_CENTER_VERTICAL)

        flush_box = wx.BoxSizer(wx.HORIZONTAL)
        flush_box.Add(self.flush_data, 0, wx.ALIGN_CENTER_VERTICAL)
        flush_box.Add(wx.StaticText(self, -1, self.utility.lang.get('minute_long')), 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)

        datasizer.Add(flush_box)

        sizer.Add(datasizer, 0, wx.ALL, 5)

        # Disk buffering
        buffer_title = wx.StaticBox(self, -1, self.utility.lang.get('bufferdisk'))
        buffer = wx.StaticBoxSizer(buffer_title, wx.VERTICAL)

        self.buffer_read_enable = wx.CheckBox(self, -1, self.utility.lang.get('buffer_read'))
                   
        buffer.Add(self.buffer_read_enable, 0, wx.ALL, 5)
        sizer.Add(buffer, 0, wx.EXPAND|wx.ALL, 5)

        self.alloctype_data.SetToolTipString(self.utility.lang.get('alloctypehint'))
        self.allocrate_data.SetToolTipString(self.utility.lang.get('allocratehint'))
        self.locking_data.SetToolTipString(self.utility.lang.get('lockinghint'))
        self.doublecheck_data.SetToolTipString(self.utility.lang.get('doublecheckhint'))
        self.maxfilesopen_data.SetToolTipString(self.utility.lang.get('maxfileopenhint'))
        
        self.initTasks()

    def loadValues(self, Read = None):
        if Read is None:
            Read = self.utility.config.Read
        
        alloctype = self.defaultDLConfig.get_alloc_type()
        alloc_selection = self.alloc_type2int[alloctype] 
        self.alloctype_data.SetSelection(alloc_selection)
        
        self.allocrate_data.SetValue(self.defaultDLConfig.get_alloc_rate())
        
        lockfiles = self.defaultDLConfig.get_lock_files()
        lockread = self.defaultDLConfig.get_lock_while_reading()
        if lockfiles:
            if lockread:
                self.locking_data.SetSelection(2)
            else:
                self.locking_data.SetSelection(1)
        else:
            self.locking_data.SetSelection(0)
        
        doublecheck = self.defaultDLConfig.get_double_check_writes()
        triplecheck = self.defaultDLConfig.get_triple_check_writes()
        if doublecheck:
            if triplecheck:
                self.doublecheck_data.SetSelection(2)
            else:
                self.doublecheck_data.SetSelection(1)
        else:
            self.doublecheck_data.SetSelection(0)
        
        self.maxfilesopen_data.SetValue(self.defaultDLConfig.get_max_files_open())
        self.buffer_read_enable.SetValue(self.defaultDLConfig.get_buffer_reads())


        flushval = self.defaultDLConfig.get_auto_flush()
        self.flush_data.SetValue(flushval)
        self.flush_data_enable.SetValue(flushval > 0)

    def apply(self):
        alloctype = self.alloc_types[self.alloctype_data.GetSelection()]
        allocrate = int(self.allocrate_data.GetValue())
        maxopen = int(self.maxfilesopen_data.GetValue())
        lockfiles = self.locking_data.GetSelection() >= 1
        lockread  = self.locking_data.GetSelection() > 1
        doublecheck = self.doublecheck_data.GetSelection() >= 1
        triplecheck = self.doublecheck_data.GetSelection() > 1
        bufferread = self.buffer_read_enable.GetValue()
        
        if not self.flush_data_enable.GetValue():
            flushval = 0
        else:
            flushval = self.flush_data.GetValue()

        # Save DownloadStartupConfig
        self.defaultDLConfig.set_alloc_type(alloctype)
        self.defaultDLConfig.set_alloc_rate(allocrate)
        self.defaultDLConfig.set_lock_files(lockfiles)
        self.defaultDLConfig.set_lock_while_reading(lockread)
        self.defaultDLConfig.set_double_check_writes(doublecheck)
        self.defaultDLConfig.set_triple_check_writes(triplecheck)
        self.defaultDLConfig.set_max_files_open(maxopen)
        self.defaultDLConfig.set_buffer_reads(bufferread)
        self.defaultDLConfig.set_auto_flush(flushval)
        
        dlcfgfilename = get_default_dscfg_filename(self.utility.session)
        self.defaultDLConfig.save(dlcfgfilename)
            



################################################################
#
# Class: SchedulerRulePanel
#
# Contains settings related to timeouts
#
################################################################

# Arno, 2008-02-27: Currently disabled, as there is no queuing

################################################################
#
# Class: RateLimitPanel
#
# Contains settings related to setting limits on upload and
# download rates
#
################################################################
class RateLimitPanel(ABCOptionPanel):
    def __init__(self, parent, dialog):
        ABCOptionPanel.__init__(self, parent, dialog)
        sizer = self.sizer
        
        # GUI dialog for Global upload setting
        ########################################

        # Upload settings
        ########################################
       
        uploadsection_title = wx.StaticBox(self, -1, self.utility.lang.get('uploadsetting'))
        uploadsection = wx.StaticBoxSizer(uploadsection_title, wx.VERTICAL)
        
        """
        # Arno, 2008-03-27: Currently disabled, no queuing
        self.maxupload = wx.SpinCtrl(self, size = wx.Size(60, -1))
        self.maxupload.SetRange(2, 100)
        
        maxuploadsbox = wx.BoxSizer(wx.HORIZONTAL)
        maxuploadsbox.Add(wx.StaticText(self, -1, self.utility.lang.get('maxuploads')), 0, wx.ALIGN_CENTER_VERTICAL)
        maxuploadsbox.Add(self.maxupload, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
        
        uploadsection.Add(maxuploadsbox, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
        """

        maxoverall_down_label = wx.BoxSizer(wx.VERTICAL)
        maxoverall_down_label.Add(wx.StaticText(self, -1, self.utility.lang.get('maxoveralluploadrate')), 0, wx.ALIGN_CENTER_VERTICAL)
        maxoverall_down_label.Add(wx.StaticText(self, -1, self.utility.lang.get('whendownload')), 0, wx.ALIGN_CENTER_VERTICAL)

        self.uploadrate = self.utility.makeNumCtrl(self, 0, integerWidth = 4)
        self.uploadrate.SetToolTipString(self.utility.lang.get('global_uprate_hint'))

        maxoverall_down = wx.BoxSizer(wx.HORIZONTAL)
        maxoverall_down.Add(maxoverall_down_label, 0, wx.ALIGN_CENTER_VERTICAL)
        maxoverall_down.Add(self.uploadrate, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
        maxoverall_down.Add(wx.StaticText(self, -1, self.utility.lang.get('KB') + "/" + self.utility.lang.get('l_second')), 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 3)
        
        uploadsection.Add(maxoverall_down, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
        
        maxoverall_nodown_label = wx.BoxSizer(wx.VERTICAL)
        maxoverall_nodown_label.Add(wx.StaticText(self, -1, self.utility.lang.get('maxoveralluploadrate')), 0, wx.ALIGN_CENTER_VERTICAL)
        maxoverall_nodown_label.Add(wx.StaticText(self, -1, self.utility.lang.get('whennodownload')), 0, wx.ALIGN_CENTER_VERTICAL)

        self.seeduploadrate = self.utility.makeNumCtrl(self, 0, integerWidth = 4)
        self.seeduploadrate.SetToolTipString(self.utility.lang.get('global_uprate_hint'))

        maxoverall_nodown = wx.BoxSizer(wx.HORIZONTAL)
        maxoverall_nodown.Add(maxoverall_nodown_label, 0, wx.ALIGN_CENTER_VERTICAL)
        maxoverall_nodown.Add(self.seeduploadrate, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
        maxoverall_nodown.Add(wx.StaticText(self, -1, self.utility.lang.get('KB') + "/" + self.utility.lang.get('l_second')), 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 3)

        uploadsection.Add(maxoverall_nodown, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)       

        uploadsection.Add(wx.StaticText(self, -1, self.utility.lang.get('zeroisunlimited')), 0, wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_RIGHT|wx.ALL, 5)

        sizer.Add(uploadsection, 0, wx.EXPAND|wx.ALL, 5)

        # Download Section
        downloadsection_title = wx.StaticBox(self, -1, self.utility.lang.get('downloadsetting'))
        downloadsection = wx.StaticBoxSizer(downloadsection_title, wx.VERTICAL)

        self.downloadrate = self.utility.makeNumCtrl(self, 0, integerWidth = 4)

        maxdownoverall_down = wx.BoxSizer(wx.HORIZONTAL)
        maxdownoverall_down.Add(wx.StaticText(self, -1, self.utility.lang.get('maxoveralldownloadrate')), 0, wx.ALIGN_CENTER_VERTICAL)
        maxdownoverall_down.Add(self.downloadrate, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
        maxdownoverall_down.Add(wx.StaticText(self, -1, self.utility.lang.get('KB') + "/" + self.utility.lang.get('l_second')), 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 3)
        
        downloadsection.Add(maxdownoverall_down, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        downloadsection.Add(wx.StaticText(self, -1, self.utility.lang.get('zeroisunlimited')), 0, wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_RIGHT|wx.ALL, 5)        

        sizer.Add(downloadsection, 0, wx.EXPAND|wx.ALL, 5)
        
        self.initTasks()

    def loadValues(self, Read = None):
        if Read is None:
            Read = self.utility.config.Read
        
        #self.maxupload.SetValue(Read('maxupload', "int"))
        self.uploadrate.SetValue(Read('maxuploadrate', "int"))
        self.downloadrate.SetValue(Read('maxdownloadrate', "int"))
        self.seeduploadrate.SetValue(Read('maxseeduploadrate', "int"))
        
    def apply(self):
        # Check max upload rate input must be integer
        ##############################################
        upload_rate     = int(self.uploadrate.GetValue())
        seedupload_rate = int(self.seeduploadrate.GetValue())
        
        download_rate = int(self.downloadrate.GetValue())

        # Check max upload rate must not be less than 3 kB/s
        ######################################################
        if (upload_rate < 3 and upload_rate != 0) or (seedupload_rate < 3 and seedupload_rate != 0):
            #display warning
            dlg = wx.MessageDialog(self, self.utility.lang.get('uploadrateminwarning'), self.utility.lang.get('error'), wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            return False

        # Set new value to parameters
        ##############################
        ##self.utility.config.Write('maxupload', self.maxupload.GetValue())
        self.utility.config.Write('maxuploadrate', upload_rate)
        self.utility.config.Write('maxseeduploadrate', seedupload_rate)
        
        self.utility.config.Write('maxdownloadrate', download_rate)

        # Change at Runtime
        self.utility.ratelimiter.set_global_max_speed(UPLOAD,upload_rate)
        self.utility.ratelimiter.set_global_max_speed(DOWNLOAD,download_rate)
        self.utility.ratelimiter.set_global_max_seedupload_speed(seedupload_rate)


################################################################
#
# Class: SeedingOptionsPanel
#
# Contains options controlling how long torrents should remain
# seeding.
#
################################################################
class SeedingOptionsPanel(ABCOptionPanel):
    def __init__(self, parent, dialog):
        ABCOptionPanel.__init__(self, parent, dialog)
        sizer = self.sizer
        
        # GUI dialog for Global upload setting
        ########################################

        # Upload setting for completed files
        ########################################

        continuesection_title = wx.StaticBox(self, -1, self.utility.lang.get('uploadoptforcompletedfile'))
        continuesection = wx.StaticBoxSizer(continuesection_title, wx.VERTICAL)
        
        uploadlist = [self.utility.lang.get('unlimitedupload'), self.utility.lang.get('continueuploadfor'), self.utility.lang.get('untilratio')]
       
        rb1 = wx.RadioButton(self, -1, uploadlist[0], wx.Point(-1, -1), wx.Size(-1, -1), wx.RB_GROUP)
        rb2 = wx.RadioButton(self, -1, uploadlist[1], wx.Point(-1, -1), wx.Size(-1, -1))
        rb3 = wx.RadioButton(self, -1, uploadlist[2], wx.Point(-1, -1), wx.Size(-1, -1))
        self.rb = [rb1, rb2, rb3]
              
        mtimeval = ['30', '45', '60', '75']
        htimeval = []
        for i in range(24):
            htimeval.append(str(i))
            
        self.cbhtime = wx.ComboBox(self, -1, "", wx.Point(-1, -1), 
                                  wx.Size(55, -1), htimeval, wx.CB_DROPDOWN|wx.CB_READONLY)
        self.cbmtime = wx.ComboBox(self, -1, "", wx.Point(-1, -1), 
                                  wx.Size(55, -1), mtimeval, wx.CB_DROPDOWN|wx.CB_READONLY)

        continuesection.Add(rb1, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        time_sizer = wx.BoxSizer(wx.HORIZONTAL)
        time_sizer.Add(rb2, 0, wx.ALIGN_CENTER_VERTICAL)
        time_sizer.Add(self.cbhtime, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        time_sizer.Add(wx.StaticText(self, -1, self.utility.lang.get('hour')), 0, wx.ALIGN_CENTER_VERTICAL)
        time_sizer.Add(self.cbmtime, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        time_sizer.Add(wx.StaticText(self, -1, self.utility.lang.get('minute')), 0, wx.ALIGN_CENTER_VERTICAL)
        
        continuesection.Add(time_sizer, -1, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        ratioval = ['50', '75', '100', '125', '150', '175', '200', '300', '400', '500']
        self.cbratio = wx.ComboBox(self, -1, "", 
                                  wx.Point(-1, -1), wx.Size(65, -1), ratioval, wx.CB_DROPDOWN|wx.CB_READONLY)
       
        percent_sizer = wx.BoxSizer(wx.HORIZONTAL)
        percent_sizer.Add(rb3, 0, wx.ALIGN_CENTER_VERTICAL)
        percent_sizer.Add(self.cbratio, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
        percent_sizer.Add(wx.StaticText(self, -1, "%"), 0, wx.ALIGN_CENTER_VERTICAL)
        
        continuesection.Add(percent_sizer, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        sizer.Add(continuesection, 0, wx.EXPAND|wx.ALL, 5)
        
        self.initTasks()

    def loadValues(self, Read = None):
        if Read is None:
            Read = self.utility.config.Read

        self.cbratio.SetValue(Read('uploadratio'))
        self.cbhtime.SetValue(Read('uploadtimeh'))
        self.cbmtime.SetValue(Read('uploadtimem'))
            
        self.rb[Read('uploadoption', "int")].SetValue(True)
        
    def apply(self):
        # Set new value to parameters
        ##############################
        for i in range (3):
            if self.rb[i].GetValue():
                self.utility.config.Write('uploadoption', i)

        self.utility.config.Write('uploadtimeh', self.cbhtime.GetValue())
        self.utility.config.Write('uploadtimem', self.cbmtime.GetValue())
        self.utility.config.Write('uploadratio', self.cbratio.GetValue())



        





################################################################
#
# Class: TriblerPanel
#
# Contains settings for Tribler's features
#
################################################################
class TriblerPanel(ABCOptionPanel):
    def __init__(self, parent, dialog):
        ABCOptionPanel.__init__(self, parent, dialog)
        sizer = self.sizer

        funcsection_title = wx.StaticBox(self, -1, self.utility.lang.get('corefuncsetting'))
        funcsection = wx.StaticBoxSizer(funcsection_title, wx.VERTICAL)

        self.rec_enable = wx.CheckBox(self, -1, self.utility.lang.get('enablerecommender')+" "+self.utility.lang.get('restartabc'))
        funcsection.Add(self.rec_enable, 0, wx.ALIGN_LEFT|wx.ALL, 5)

        self.dlhelp_enable = wx.CheckBox(self, -1, self.utility.lang.get('enabledlhelp')+" "+self.utility.lang.get('restartabc'))
        funcsection.Add(self.dlhelp_enable, 0, wx.ALIGN_LEFT|wx.ALL, 5)

        self.collect_enable = wx.CheckBox(self, -1, self.utility.lang.get('enabledlcollecting')+" "+self.utility.lang.get('restartabc'))
        funcsection.Add(self.collect_enable, 0, wx.ALIGN_LEFT|wx.ALL, 5)

        sizer.Add(funcsection, 0, wx.EXPAND|wx.ALL, 5)

        tcsection_title = wx.StaticBox(self, -1, self.utility.lang.get('torrentcollectsetting'))
        tcsection = wx.StaticBoxSizer(tcsection_title, wx.VERTICAL)

        self.timectrl = self.utility.makeNumCtrl(self, 1, min = 1, max = 3600)
        time_box = wx.BoxSizer(wx.HORIZONTAL)
        time_box.Add(wx.StaticText(self, -1, self.utility.lang.get('torrentcollectsleep')), 0, wx.ALIGN_CENTER_VERTICAL)
        time_box.Add(self.timectrl, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        time_box.Add(wx.StaticText(self, -1, self.utility.lang.get('restartabc')), 0, wx.ALIGN_CENTER_VERTICAL)
        tcsection.Add(time_box, 0, wx.EXPAND|wx.ALL, 5)

        ntorrents_box = wx.BoxSizer(wx.HORIZONTAL)    # set the max num of torrents to collect
        self.ntorrents = self.utility.makeNumCtrl(self, 5000, min = 0, max = 999999)
        ntorrents_box.Add(wx.StaticText(self, -1, self.utility.lang.get('maxntorrents')), 0, wx.ALIGN_CENTER_VERTICAL)
        ntorrents_box.Add(self.ntorrents, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        tcsection.Add(ntorrents_box, 0, wx.EXPAND|wx.ALL, 5)
        
        npeers_box = wx.BoxSizer(wx.HORIZONTAL)    # set the max num of peers to be used by buddycast
        self.npeers = self.utility.makeNumCtrl(self, 2000, min = 0, max = 999999)
        npeers_box.Add(wx.StaticText(self, -1, self.utility.lang.get('maxnpeers')), 0, wx.ALIGN_CENTER_VERTICAL)
        npeers_box.Add(self.npeers, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        tcsection.Add(npeers_box, 0, wx.EXPAND|wx.ALL, 5)
        
        tc_threshold_box = wx.BoxSizer(wx.HORIZONTAL)    # set the min space to stop torrent collecting
        self.tc_threshold = self.utility.makeNumCtrl(self, 200, min = 1, max = 999999)
        tc_threshold_box.Add(wx.StaticText(self, -1, self.utility.lang.get('tc_threshold')), 0, wx.ALIGN_CENTER_VERTICAL)
        tc_threshold_box.Add(self.tc_threshold, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        tc_threshold_box.Add(wx.StaticText(self, -1, self.utility.lang.get('MB')), 0, wx.ALIGN_CENTER_VERTICAL)
        tc_threshold_box.Add(wx.StaticText(self, -1, ' ('+self.utility.lang.get('current_free_space')+' '), 0, wx.ALIGN_CENTER_VERTICAL)
        
        current_free_space = getfreespace(self.utility.session.get_download_help_dir())/(2**20)
        tc_threshold_box.Add(wx.StaticText(self, -1, str(current_free_space)), 0, wx.ALIGN_CENTER_VERTICAL)
        tc_threshold_box.Add(wx.StaticText(self, -1, self.utility.lang.get('MB')+')'), 0, wx.ALIGN_CENTER_VERTICAL)
        tcsection.Add(tc_threshold_box, 0, wx.EXPAND|wx.ALL, 5)
        
        tc_rate_box = wx.BoxSizer(wx.HORIZONTAL)    # set the rate of torrent collecting
        self.tc_rate = self.utility.makeNumCtrl(self, 5, min = 0, max = 999999)
        tc_rate_box.Add(wx.StaticText(self, -1, self.utility.lang.get('torrentcollectingrate')), 0, wx.ALIGN_CENTER_VERTICAL)
        tc_rate_box.Add(self.tc_rate, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        tcsection.Add(tc_rate_box, 0, wx.EXPAND|wx.ALL, 5)

        sizer.Add(tcsection, 0, wx.EXPAND|wx.ALL, 5)

        myinfosection_title = wx.StaticBox(self, -1, self.utility.lang.get('myinfosetting'))
        myinfosection = wx.StaticBoxSizer(myinfosection_title, wx.VERTICAL)

        # Show PermID
        mypermid = self.utility.session.get_permid()
        pb64 = show_permid(mypermid)
        if True:
            # Make it copy-and-paste able
            permid_box = wx.BoxSizer(wx.HORIZONTAL)
            self.permidctrl = wx.TextCtrl(self, -1, pb64, size = (400, 30), style = wx.TE_READONLY)
            permid_box.Add(wx.StaticText(self, -1, self.utility.lang.get('mypermid')), 0, wx.ALIGN_CENTER_VERTICAL)
            permid_box.Add(self.permidctrl, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
            myinfosection.Add(permid_box, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        else:
            permid_txt = self.utility.lang.get('mypermid')+": "+pb64
            label = wx.StaticText(self, -1, permid_txt )
            myinfosection.Add( label, 1, wx.EXPAND|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
        
        self.myinfo = wx.Button(self, -1, self.utility.lang.get('myinfo') + "...")
        self.Bind(wx.EVT_BUTTON, self.OnMyInfoWizard, self.myinfo)
        myinfosection.Add(self.myinfo, 0, wx.ALL, 5)

        sizer.Add(myinfosection, 0, wx.EXPAND|wx.ALL, 5)

        if self.utility.frame.oldframe is not None:
            self.debug = wx.Button(self, -1, 'Open debug window')
            sizer.Add(self.debug, 0, wx.ALL, 5)
            self.Bind(wx.EVT_BUTTON, self.OnDebug, self.debug)
        
        self.initTasks()

        
    def loadValues(self, Read = None):
        """ Loading values from configure file """
        
        buddycast = self.utility.session.get_buddycast()
        coopdl = self.utility.session.get_download_help()
        torrcoll = self.utility.session.get_torrent_collecting()
        maxcolltorrents = self.utility.session.get_torrent_collecting_max_torrents()
        maxbcpeers = self.utility.session.get_buddycast_max_peers()
        stopcollthres = self.utility.session.get_stop_collecting_threshold()
        collrate = self.utility.session.get_torrent_collecting_rate()
        
        self.rec_enable.SetValue(buddycast)
        self.dlhelp_enable.SetValue(coopdl)
        self.collect_enable.SetValue(torrcoll)
        self.ntorrents.SetValue(maxcolltorrents)
        self.npeers.SetValue(maxbcpeers)
        self.tc_threshold.SetValue(stopcollthres)
        self.tc_rate.SetValue(collrate)

        # For subscriptions
        self.timectrl.SetValue(self.utility.config.Read('torrentcollectsleep', 'int'))
        


    def apply(self):       
        """ do sth. when user click apply of OK button """
        
        buddycast = self.rec_enable.GetValue()
        coopdl = self.dlhelp_enable.GetValue()
        torrcoll = self.collect_enable.GetValue()
        maxcolltorrents = int(self.ntorrents.GetValue())
        maxbcpeers = int(self.npeers.GetValue())
        stopcollthres = int(self.tc_threshold.GetValue())
        collrate = int(self.tc_rate.GetValue())


        # Save SessConfig
        state_dir = self.utility.session.get_state_dir()
        cfgfilename = Session.get_default_config_filename(state_dir)
        scfg = SessionStartupConfig.load(cfgfilename)
        
        for target in [scfg,self.utility.session]:
            try:
                target.set_buddycast(buddycast)
            except:
                print_exc()
            try:
                target.set_download_help(coopdl)
            except:
                print_exc()
            try:
                target.set_torrent_collecting(torrcoll)
            except:
                print_exc()
            try:
                target.set_torrent_collecting_max_torrents(maxcolltorrents)
            except:
                print_exc()
            try:
                target.set_buddycast_max_peers(maxbcpeers)
            except:
                print_exc()
            try:
                target.set_stop_collecting_threshold(stopcollthres)
            except:
                print_exc()
            try:
                target.set_torrent_collecting_rate(collrate)
            except:
                print_exc()

        scfg.save(cfgfilename)

        # For subscriptions
        t = int(self.timectrl.GetValue())
        self.utility.config.Write('torrentcollectsleep', t)


    def OnMyInfoWizard(self, event = None):
        wizard = MyInfoWizard(self)
        wizard.RunWizard(wizard.getFirstPage())

    def WizardFinished(self,wizard):
        wizard.Destroy()

    def OnDebug(self,event):
        self.utility.frame.oldframe.Show()

# HERE

################################################################
#
# Class: VideoPanel
#
# Contains settings for video features
#
################################################################
class VideoPanel(ABCOptionPanel):
    def __init__(self, parent, dialog):
        ABCOptionPanel.__init__(self, parent, dialog)
        sizer = self.sizer

        playbacksection_title = wx.StaticBox(self, -1, self.utility.lang.get('playback_section'))
        playbacksection = wx.StaticBoxSizer(playbacksection_title, wx.VERTICAL)

        playbackbox = wx.BoxSizer(wx.HORIZONTAL)
        feasible = return_feasible_playback_modes(self.utility.getPath())
        playback_choices = []
        self.playback_indices = []
        if PLAYBACKMODE_INTERNAL in feasible:
            playback_choices.append(self.utility.lang.get('playback_internal'))
            self.playback_indices.append(PLAYBACKMODE_INTERNAL)
        if PLAYBACKMODE_EXTERNAL_DEFAULT in feasible:
            playback_choices.append(self.utility.lang.get('playback_external_default'))
            self.playback_indices.append(PLAYBACKMODE_EXTERNAL_DEFAULT)
        if PLAYBACKMODE_EXTERNAL_MIME in feasible:
            playback_choices.append(self.utility.lang.get('playback_external_mime'))
            self.playback_indices.append(PLAYBACKMODE_EXTERNAL_MIME)
        self.playback_chooser=wx.Choice(self, -1, wx.Point(-1, -1), wx.Size(-1, -1), playback_choices)

        playbackbox.Add(wx.StaticText(self, -1, self.utility.lang.get('playback_mode')), 1, wx.ALIGN_CENTER_VERTICAL)
        playbackbox.Add(self.playback_chooser)
        playbacksection.Add(playbackbox, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        
        player_box = wx.BoxSizer(wx.HORIZONTAL)
        self.player = wx.TextCtrl(self, -1, "")
        player_box.Add(wx.StaticText(self, -1, self.utility.lang.get('videoplayer_default_path')), 0, wx.ALIGN_CENTER_VERTICAL)
        player_box.Add(self.player, 1, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        #browsebtn = wx.Button(self, -1, "...", style = wx.BU_EXACTFIT)
        browsebtn = wx.Button(self, -1, "...")
        self.Bind(wx.EVT_BUTTON, self.onBrowsePlayer, browsebtn)
        player_box.Add(browsebtn, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        playbacksection.Add(player_box, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT|wx.EXPAND, 5)

        sizer.Add(playbacksection, 0, wx.EXPAND|wx.ALL, 5)

        analysissection_title = wx.StaticBox(self, -1, self.utility.lang.get('analysis_section'))
        analysissection = wx.StaticBoxSizer(analysissection_title, wx.VERTICAL)

        analyser_box = wx.BoxSizer(wx.HORIZONTAL)
        self.analyser = wx.TextCtrl(self, -1, "")
        analyser_box.Add(wx.StaticText(self, -1, self.utility.lang.get('videoanalyserpath')), 0, wx.ALIGN_CENTER_VERTICAL)
        analyser_box.Add(self.analyser, 1, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        #browsebtn = wx.Button(self, -1, "...", style = wx.BU_EXACTFIT)
        browsebtn = wx.Button(self, -1, "...")
        self.Bind(wx.EVT_BUTTON, self.onBrowseAnalyser, browsebtn)
        analyser_box.Add(browsebtn, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        analysissection.Add(analyser_box, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT|wx.EXPAND, 5)

        sizer.Add(analysissection, 0, wx.EXPAND|wx.ALL, 5)
        
        if sys.platform == 'win32':
            self.quote = '"'
        else:
            self.quote = "'"
        
        self.initTasks()
        
    def loadValues(self, Read = None):
        if Read is None:
            Read = self.utility.config.Read

        mode = Read('videoplaybackmode', "int")
        for index in self.playback_indices:
            if index == mode:
                self.playback_chooser.SetSelection(index)
        
        value = Read('videoplayerpath')
        qvalue = self.quote_path(value)
        self.player.SetValue(qvalue)

        value = Read('videoanalyserpath')
        qvalue = self.quote_path(value)
        self.analyser.SetValue(qvalue)

              
    def apply(self):       
        
        value = self.playback_chooser.GetSelection()
        mode = self.playback_indices[value]
        self.utility.config.Write('videoplaybackmode',mode)

        for key,widget,mainmsg in [('videoplayerpath',self.player,self.utility.lang.get('videoplayernotfound')),('videoanalyserpath',self.analyser,self.utility.lang.get('videoanalysernotfound'))]:
            qvalue = widget.GetValue()
            value = self.unquote_path(qvalue)
            if not os.access(value,os.F_OK):
                self.onError(mainmsg,value)
                return
            if DEBUG:
                print >>sys.stderr,"abcoptions: VideoPanel: Writing",key,value
            self.utility.config.Write(key,value)


    def unquote_path(self,value):
        value.strip()
        if value[0] == self.quote:
            idx = value.find(self.quote,1)
            return value[1:idx]
        else:
            return value

    def quote_path(self,value):
        value.strip()
        if value.find(' ') != -1:
            return self.quote+value+self.quote
        else:
            return value
        
        
    def onError(self,mainmsg,path):
        msg = mainmsg
        msg += '\n'
        msg += path
        msg += '\n'
        dlg = wx.MessageDialog(None, msg, self.utility.lang.get('videoplayererrortitle'), wx.OK|wx.ICON_ERROR)
        result = dlg.ShowModal()
        dlg.Destroy()

    def onBrowsePlayer(self, event = None):
        self.onBrowse(self.player,self.utility.lang.get('choosevideoplayer'))
        
    def onBrowseAnalyser(self, event = None):
        self.onBrowse(self.analyser,self.utility.lang.get('choosevideoanalyser'))
        
    def onBrowse(self,widget,title):
        dlg = wx.FileDialog(self.utility.frame, 
                           title, 
                           style = wx.OPEN | wx.FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            value = dlg.GetPath()
            qvalue = self.quote_path(value)
            widget.SetValue(qvalue)
        dlg.Destroy()

        
################################################################
#
# Class: ABCTree
#
# A collapsable listing of all the options panels
#
################################################################
class ABCTree(wx.TreeCtrl):
    def __init__(self, parent, dialog):
        style = wx.TR_DEFAULT_STYLE | wx.TR_HIDE_ROOT
        wx.TreeCtrl.__init__(self, parent, -1, style = style)

        self.dialog = dialog
        self.utility = dialog.utility
       
        self.root = self.AddRoot("Preferences")

	self.tribler = self.AppendItem(self.root, self.utility.lang.get('triblersetting'))
	self.video = self.AppendItem(self.root, self.utility.lang.get('videosetting'))
        self.ratelimits = self.AppendItem(self.root, self.utility.lang.get('ratelimits'))
        self.seedingoptions = self.AppendItem(self.root, self.utility.lang.get('seedoptions'))
        #self.queuesetting = self.AppendItem(self.root, self.utility.lang.get('queuesetting'))
        #self.timeout = self.AppendItem(self.root, self.utility.lang.get('timeout'))
        self.disk = self.AppendItem(self.root, self.utility.lang.get('disksettings'))
        self.advanceddisk = self.AppendItem(self.disk, self.utility.lang.get('advanced'))
        self.network = self.AppendItem(self.root, self.utility.lang.get('networksetting'))
        self.advancednetwork = self.AppendItem(self.network, self.utility.lang.get('advanced'))

        #self.display = self.AppendItem(self.root, self.utility.lang.get('displaysetting'))

        #self.colors = self.AppendItem(self.display, self.utility.lang.get('torrentcolors'))
                
        self.misc = self.AppendItem(self.root, self.utility.lang.get('miscsetting'))

        self.treeMap = {self.ratelimits : self.dialog.rateLimitPanel, 
                        self.seedingoptions : self.dialog.seedingOptionsPanel, 
                        #self.queuesetting : self.dialog.queuePanel, 
                        #self.timeout : self.dialog.schedulerRulePanel, 
                        self.network : self.dialog.networkPanel, 
                        self.misc : self.dialog.miscPanel,
                        self.tribler : self.dialog.triblerPanel,
                        self.video : self.dialog.videoPanel,
                        #self.display : self.dialog.displayPanel, 
                        #self.colors : self.dialog.colorPanel, 
                        self.disk : self.dialog.diskPanel }

        self.treeMap[self.advancednetwork] = self.dialog.advancedNetworkPanel
        self.treeMap[self.advanceddisk] = self.dialog.advancedDiskPanel
        
        self.Bind(wx.EVT_TREE_SEL_CHANGED, self.onSwitchPage)

        self.SetAutoLayout(True)
        self.Fit()

    def onSwitchPage(self, event = None):       
        if self.dialog.closing or event is None:
            return

        if DEBUG:
            print >>sys.stderr,"abcoption: <mluc> event type:", event.GetEventType()
        newitem = event.GetItem()
        newpanel = None
        foundnew = False
        for key in self.treeMap:
            if key == newitem:
                newpanel = self.treeMap[key]
                foundnew = True
            if foundnew:
                break

        if newpanel is not None:
            # Trying to switch to the current window
            try:
                oldpanel = self.dialog.splitter.GetWindow2()
                if oldpanel != newpanel:
                    oldpanel.Show(False)
                    self.dialog.splitter.ReplaceWindow(oldpanel, newpanel)
                    newpanel.Show(True)
                    newpanel.changed = True
            except:
                pass
                # TODO: for some reason this is sometimes failing
                # (splitter.GetWindow2() sometimes appears to
                #  return an Object rather than wx.Window)

    def open(self,name):
        rootid = self.GetRootItem()
        if rootid.IsOk():
            #print "root is",self.GetItemText(rootid)
            [firstid,cookie] = self.GetFirstChild(rootid)
            if firstid.IsOk():
                print "first is",self.GetItemText(firstid)
                if not self.doopen(name,firstid):
                    while True:
                        [childid,cookie] = self.GetNextChild(firstid,cookie)
                        if childid.IsOk():
                            if self.doopen(name,childid):
                                break
                        else:
                            break

    def doopen(self,wantname,childid):
        gotname = self.GetItemText(childid)
        print "gotname is",gotname
        if gotname == wantname:
            self.SelectItem(childid)
            return True
        else:
            return False


################################################################
#
# Class: ABCOptionDialog
#
# Creates a dialog that allows users to set various preferences
#
################################################################        
class ABCOptionDialog(wx.Dialog):
    def __init__(self, parent,openname=None):
        self.utility = parent.utility

        style = wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
#        size = wx.Size(530, 420)
        
        size, split = self.getWindowSettings()
        
        wx.Dialog.__init__(self, parent, -1, self.utility.lang.get('abcpreference'), size = size, style = style)
                     
        self.splitter = wx.SplitterWindow(self, -1, style = wx.SP_NOBORDER | wx.SP_LIVE_UPDATE)

        self.rateLimitPanel = RateLimitPanel(self.splitter, self)
        self.seedingOptionsPanel = SeedingOptionsPanel(self.splitter, self)
        #self.queuePanel = QueuePanel(self.splitter, self)

        #self.schedulerRulePanel = SchedulerRulePanel(self.splitter, self)
        self.networkPanel = NetworkPanel(self.splitter, self)
        self.miscPanel = MiscPanel(self.splitter, self)
        self.triblerPanel = TriblerPanel(self.splitter, self)
        self.videoPanel = VideoPanel(self.splitter, self)
        self.diskPanel = DiskPanel(self.splitter, self)
        
        self.advancedNetworkPanel = AdvancedNetworkPanel(self.splitter, self)
        self.advancedDiskPanel = AdvancedDiskPanel(self.splitter, self)
        
        self.tree = ABCTree(self.splitter, self)

        # TODO: Try wx.Listbook instead of splitterwindow

        self.splitter.SetAutoLayout(True)
        self.splitter.Fit()
      
        applybtn       = wx.Button(self, -1, " "+self.utility.lang.get('apply')+" ", size = (60, -1))
        okbtn          = wx.Button(self, -1, " "+self.utility.lang.get('ok')+" ", size = (60, -1))
        cancelbtn      = wx.Button(self, -1, " "+self.utility.lang.get('cancel')+" ", size = (60, -1))
        
        buttonbox = wx.BoxSizer(wx.HORIZONTAL)
        buttonbox.Add(applybtn, 0, wx.ALL, 5)
        buttonbox.Add(okbtn, 0, wx.ALL, 5)
        buttonbox.Add(cancelbtn, 0, wx.ALL, 5)
       
        outerbox = wx.BoxSizer(wx.VERTICAL)
        outerbox.Add(self.splitter , 1, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, 5)
        
        outerbox.Add(wx.StaticLine(self, -1), 0, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.BOTTOM, 5)
        
        outerbox.Add(buttonbox, 0, wx.ALIGN_RIGHT)

        # Add events
        ###########################
        self.Bind(wx.EVT_BUTTON, self.onOK, okbtn)
        self.Bind(wx.EVT_BUTTON, self.onApply, applybtn)
        self.Bind(wx.EVT_BUTTON, self.onCloseGlobalPref, cancelbtn)
        self.Bind(wx.EVT_CLOSE, self.onCloseGlobalPref)

        defaultPanel = self.triblerPanel

        self.splitter.SplitVertically(self.tree, defaultPanel, split)
        defaultPanel.changed = True
        self.splitter.SetMinimumPaneSize(50)

        for key in self.tree.treeMap:
            panel = self.tree.treeMap[key]
            panel.Show(False)
        
        defaultPanel.Show(True)
        defaultPanel.Fit()
        
        self.SetSizer(outerbox)
#        self.Fit()
        
        self.closing = False
        if openname is not None:
            self.tree.open(openname)

        treeitem = [k for (k,v) in self.tree.treeMap.iteritems() if v == defaultPanel][0]
        self.tree.SelectItem( treeitem, True )
        
    def getWindowSettings(self):
        width = self.utility.config.Read("prefwindow_width", "int")
        height = self.utility.config.Read("prefwindow_height", "int")
        split = self.utility.config.Read("prefwindow_split", "int")
                  
        return wx.Size(width, height), split
        
    def saveWindowSettings(self):       
        width, height = self.GetSizeTuple()
        self.utility.config.Write("prefwindow_width", width)
        self.utility.config.Write("prefwindow_height", height)
        self.utility.config.Write("prefwindow_split", self.splitter.GetSashPosition())
        self.utility.config.Flush()
              
    def onCloseGlobalPref(self, event = None):
        self.closing = True
        
        self.saveWindowSettings()
        
        self.EndModal(wx.ID_CANCEL)
        
    def onApply(self, event = None):        
        # Set new value to parameters
        ##############################          

        # Only apply changes for panels that the user has viewed
        for key in self.tree.treeMap:
            panel = self.tree.treeMap[key]
            if panel.changed:
                panel.apply()
            
        # write current changes to disk
        self.utility.config.Flush()
                
        return True

    def onOK(self, event = None):
        if self.onApply():
            self.closing = True
            self.saveWindowSettings()
            
            self.EndModal(wx.ID_OK)

