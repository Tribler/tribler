#written by John Hoffman

import sys
from wxPython.wx import *

from ConnChoice import connChoices
from download_bt1 import defaults
from ConfigDir import ConfigDir
import socket
from parseargs import defaultargs

try:
    True
except:
    True = 1
    False = 0
    
try:
    wxFULL_REPAINT_ON_RESIZE
except:
    wxFULL_REPAINT_ON_RESIZE = 0        # fix for wx pre-2.5

if (sys.platform == 'win32'):
    _FONT = 9
else:
    _FONT = 10

def HexToColor(s):
    r, g, b = s.split(' ')
    return wxColour(red = int(r, 16), green = int(g, 16), blue = int(b, 16))
    
def hex2(c):
    h = hex(c)[2:]
    if len(h) == 1:
        h = '0'+h
    return h
def ColorToHex(c):
    return hex2(c.Red()) + ' ' + hex2(c.Green()) + ' ' + hex2(c.Blue())

ratesettingslist = []
for x in connChoices:
    if not x.has_key('super-seed'):
        ratesettingslist.append(x['name'])


configFileDefaults = [
    #args only available for the gui client
    ('win32_taskbar_icon', 1, 
         "whether to iconize do system try or not on win32"), 
    ('gui_stretchwindow', 0, 
         "whether to stretch the download status window to fit the torrent name"), 
    ('gui_displaystats', 1, 
         "whether to display statistics on peers and seeds"), 
    ('gui_displaymiscstats', 1, 
         "whether to display miscellaneous other statistics"), 
    ('gui_ratesettingsdefault', ratesettingslist[0], 
         "the default setting for maximum upload rate and users"), 
    ('gui_ratesettingsmode', 'full', 
         "what rate setting controls to display; options are 'none', 'basic', and 'full'"), 
    ('gui_forcegreenonfirewall', 0, 
         "forces the status icon to be green even if the client seems to be firewalled"), 
    ('gui_default_savedir', '', 
         "default save directory"), 
    ('last_saved', '', # hidden; not set in config
         "where the last torrent was saved"), 
    ('gui_font', _FONT, 
         "the font size to use"), 
    ('gui_saveas_ask', -1, 
         "whether to ask where to download to (0 = never, 1 = always, -1 = automatic resume"), 
]

def setwxconfigfiledefaults():
    CHECKINGCOLOR = ColorToHex(wxSystemSettings_GetColour(wxSYS_COLOUR_3DSHADOW))  
    DOWNLOADCOLOR = ColorToHex(wxSystemSettings_GetColour(wxSYS_COLOUR_ACTIVECAPTION))
    
    configFileDefaults.extend([
        ('gui_checkingcolor', CHECKINGCOLOR, 
            "progress bar checking color"), 
        ('gui_downloadcolor', DOWNLOADCOLOR, 
            "progress bar downloading color"), 
        ('gui_seedingcolor', '00 FF 00', 
            "progress bar seeding color"), 
    ])

defaultsToIgnore = ['responsefile', 'url', 'priority']


class configReader:

    def __init__(self):
        self.configfile = wxConfig("BitTorrent", style=wxCONFIG_USE_LOCAL_FILE)
        self.configMenuBox = None
        self.advancedMenuBox = None
        self._configReset = True         # run reset for the first time

        setwxconfigfiledefaults()

        defaults.extend(configFileDefaults)
        self.defaults = defaultargs(defaults)

        self.configDir = ConfigDir('gui')
        self.configDir.setDefaults(defaults, defaultsToIgnore)
        if self.configDir.checkConfig():
            self.config = self.configDir.loadConfig()
        else:
            self.config = self.configDir.getConfig()
            self.importOldGUIConfig()
            self.configDir.saveConfig()

        updated = False     # make all config default changes here

        if self.config['gui_ratesettingsdefault'] not in ratesettingslist:
            self.config['gui_ratesettingsdefault'] = (
                                self.defaults['gui_ratesettingsdefault'])
            updated = True
        if self.config['ipv6_enabled'] and (
                        sys.version_info < (2, 3) or not socket.has_ipv6):
            self.config['ipv6_enabled'] = 0
            updated = True
        for c in ['gui_checkingcolor', 'gui_downloadcolor', 'gui_seedingcolor']:
            try:
                HexToColor(self.config[c])
            except:
                self.config[c] = self.defaults[c]
                updated = True

        if updated:
            self.configDir.saveConfig()

        self.configDir.deleteOldCacheData(self.config['expire_cache_data'])


    def importOldGUIConfig(self):
        oldconfig = wxConfig("BitTorrent", style=wxCONFIG_USE_LOCAL_FILE)
        cont, s, i = oldconfig.GetFirstEntry()
        if not cont:
            oldconfig.DeleteAll()
            return False
        while cont:     # import old config data
            if self.config.has_key(s):
                t = oldconfig.GetEntryType(s)
                try:
                    if t == 1:
                        assert type(self.config[s]) == type('')
                        self.config[s] = oldconfig.Read(s)
                    elif t == 2 or t == 3:
                        assert type(self.config[s]) == type(1)
                        self.config[s] = int(oldconfig.ReadInt(s))
                    elif t == 4:
                        assert type(self.config[s]) == type(1.0)
                        self.config[s] = oldconfig.ReadFloat(s)
                except:
                    pass
            cont, s, i = oldconfig.GetNextEntry(i)

#        oldconfig.DeleteAll()
        return True


    def resetConfigDefaults(self):
        for p, v in self.defaults.items():
            if not p in defaultsToIgnore:
                self.config[p] = v
        self.configDir.saveConfig()

    def writeConfigFile(self):
        self.configDir.saveConfig()

    def WriteLastSaved(self, l):
        self.config['last_saved'] = l
        self.configDir.saveConfig()


    def getcheckingcolor(self):
        return HexToColor(self.config['gui_checkingcolor'])
    def getdownloadcolor(self):
        return HexToColor(self.config['gui_downloadcolor'])
    def getseedingcolor(self):
        return HexToColor(self.config['gui_seedingcolor'])

    def configReset(self):
        r = self._configReset
        self._configReset = False
        return r

    def getConfigDir(self):
        return self.configDir

    def getIconDir(self):
        return self.configDir.getIconDir()

    def getTorrentData(self, t):
        return self.configDir.getTorrentData(t)

    def setColorIcon(self, xxicon, xxiconptr, xxcolor):
        idata = wxMemoryDC()
        idata.SelectObject(xxicon)
        idata.SetBrush(wxBrush(xxcolor, wxSOLID))
        idata.DrawRectangle(0, 0, 16, 16)
        idata.SelectObject(wxNullBitmap)
        xxiconptr.Refresh()


    def getColorFromUser(self, parent, colInit):
        data = wxColourData()
        if colInit.Ok():
            data.SetColour(colInit)
        data.SetCustomColour(0, self.checkingcolor)
        data.SetCustomColour(1, self.downloadcolor)
        data.SetCustomColour(2, self.seedingcolor)
        dlg = wxColourDialog(parent, data)
        if not dlg.ShowModal():
            return colInit
        return dlg.GetColourData().GetColour()


    def configMenu(self, parent):
        self.parent = parent
        try:
            self.FONT = self.config['gui_font']
            self.default_font = wxFont(self.FONT, wxDEFAULT, wxNORMAL, wxNORMAL, False)
            self.checkingcolor = HexToColor(self.config['gui_checkingcolor'])
            self.downloadcolor = HexToColor(self.config['gui_downloadcolor'])
            self.seedingcolor = HexToColor(self.config['gui_seedingcolor'])
            
            if (self.configMenuBox is not None):
                try:
                    self.configMenuBox.Close()
                except wxPyDeadObjectError, e:
                    self.configMenuBox = None
    
            self.configMenuBox = wxFrame(None, -1, 'BitTorrent Preferences', size = (1, 1), 
                                style = wxDEFAULT_FRAME_STYLE|wxFULL_REPAINT_ON_RESIZE)
            if (sys.platform == 'win32'):
                self.icon = self.parent.icon
                self.configMenuBox.SetIcon(self.icon)
    
            panel = wxPanel(self.configMenuBox, -1)
            self.panel = panel
    
            def StaticText(text, font = self.FONT, underline = False, color = None, panel = panel):
                x = wxStaticText(panel, -1, text, style = wxALIGN_LEFT)
                x.SetFont(wxFont(font, wxDEFAULT, wxNORMAL, wxNORMAL, underline))
                if color is not None:
                    x.SetForegroundColour(color)
                return x
    
            colsizer = wxFlexGridSizer(cols = 1, vgap = 8)
    
            self.gui_stretchwindow_checkbox = wxCheckBox(panel, -1, "Stretch window to fit torrent name *")
            self.gui_stretchwindow_checkbox.SetFont(self.default_font)
            self.gui_stretchwindow_checkbox.SetValue(self.config['gui_stretchwindow'])
    
            self.gui_displaystats_checkbox = wxCheckBox(panel, -1, "Display peer and seed statistics")
            self.gui_displaystats_checkbox.SetFont(self.default_font)
            self.gui_displaystats_checkbox.SetValue(self.config['gui_displaystats'])
    
            self.gui_displaymiscstats_checkbox = wxCheckBox(panel, -1, "Display miscellaneous other statistics")
            self.gui_displaymiscstats_checkbox.SetFont(self.default_font)
            self.gui_displaymiscstats_checkbox.SetValue(self.config['gui_displaymiscstats'])
    
            self.security_checkbox = wxCheckBox(panel, -1, "Don't allow multiple connections from the same IP")
            self.security_checkbox.SetFont(self.default_font)
            self.security_checkbox.SetValue(self.config['security'])
    
            self.autokick_checkbox = wxCheckBox(panel, -1, "Kick/ban clients that send you bad data *")
            self.autokick_checkbox.SetFont(self.default_font)
            self.autokick_checkbox.SetValue(self.config['auto_kick'])
    
            self.buffering_checkbox = wxCheckBox(panel, -1, "Enable read/write buffering *")
            self.buffering_checkbox.SetFont(self.default_font)
            self.buffering_checkbox.SetValue(self.config['buffer_reads'])
    
            self.breakup_checkbox = wxCheckBox(panel, -1, "Break-up seed bitfield to foil ISP manipulation")
            self.breakup_checkbox.SetFont(self.default_font)
            self.breakup_checkbox.SetValue(self.config['breakup_seed_bitfield'])

            self.autoflush_checkbox = wxCheckBox(panel, -1, "Flush data to disk every 5 minutes")
            self.autoflush_checkbox.SetFont(self.default_font)
            self.autoflush_checkbox.SetValue(self.config['auto_flush'])
    
            if sys.version_info >= (2, 3) and socket.has_ipv6:
                self.ipv6enabled_checkbox = wxCheckBox(panel, -1, "Initiate and receive connections via IPv6 *")
                self.ipv6enabled_checkbox.SetFont(self.default_font)
                self.ipv6enabled_checkbox.SetValue(self.config['ipv6_enabled'])
    
            self.gui_forcegreenonfirewall_checkbox = wxCheckBox(panel, -1, 
                                "Force icon to display green when firewalled")
            self.gui_forcegreenonfirewall_checkbox.SetFont(self.default_font)
            self.gui_forcegreenonfirewall_checkbox.SetValue(self.config['gui_forcegreenonfirewall'])
    
    
            self.minport_data = wxSpinCtrl(panel, -1, '', (-1, -1), (self.FONT*8, -1))
            self.minport_data.SetFont(self.default_font)
            self.minport_data.SetRange(1, 65535)
            self.minport_data.SetValue(self.config['minport'])
    
            self.maxport_data = wxSpinCtrl(panel, -1, '', (-1, -1), (self.FONT*8, -1))
            self.maxport_data.SetFont(self.default_font)
            self.maxport_data.SetRange(1, 65535)
            self.maxport_data.SetValue(self.config['maxport'])
            
            self.randomport_checkbox = wxCheckBox(panel, -1, "randomize")
            self.randomport_checkbox.SetFont(self.default_font)
            self.randomport_checkbox.SetValue(self.config['random_port'])
            
            self.gui_font_data = wxSpinCtrl(panel, -1, '', (-1, -1), (self.FONT*5, -1))
            self.gui_font_data.SetFont(self.default_font)
            self.gui_font_data.SetRange(8, 16)
            self.gui_font_data.SetValue(self.config['gui_font'])
    
            self.gui_ratesettingsdefault_data=wxChoice(panel, -1, choices = ratesettingslist)
            self.gui_ratesettingsdefault_data.SetFont(self.default_font)
            self.gui_ratesettingsdefault_data.SetStringSelection(self.config['gui_ratesettingsdefault'])
    
            self.maxdownload_data = wxSpinCtrl(panel, -1, '', (-1, -1), (self.FONT*7, -1))
            self.maxdownload_data.SetFont(self.default_font)
            self.maxdownload_data.SetRange(0, 5000)
            self.maxdownload_data.SetValue(self.config['max_download_rate'])
    
            self.gui_ratesettingsmode_data=wxRadioBox(panel, -1, 'Rate Settings Mode', 
                     choices = [ 'none', 'basic', 'full' ])
            self.gui_ratesettingsmode_data.SetFont(self.default_font)
            self.gui_ratesettingsmode_data.SetStringSelection(self.config['gui_ratesettingsmode'])
    
            if (sys.platform == 'win32'):
                self.win32_taskbar_icon_checkbox = wxCheckBox(panel, -1, "Minimize to system tray")
                self.win32_taskbar_icon_checkbox.SetFont(self.default_font)
                self.win32_taskbar_icon_checkbox.SetValue(self.config['win32_taskbar_icon'])
                
    #            self.upnp_checkbox = wxCheckBox(panel, -1, "Enable automatic UPnP port forwarding")
    #            self.upnp_checkbox.SetFont(self.default_font)
    #            self.upnp_checkbox.SetValue(self.config['upnp_nat_access'])
                self.upnp_data=wxChoice(panel, -1, 
                            choices = ['disabled', 'type 1 (fast)', 'type 2 (slow)'])
                self.upnp_data.SetFont(self.default_font)
                self.upnp_data.SetSelection(self.config['upnp_nat_access'])
    
            self.gui_default_savedir_ctrl = wxTextCtrl(parent = panel, id = -1, 
                                value = self.config['gui_default_savedir'], 
                                size = (26*self.FONT, -1), style = wxTE_PROCESS_TAB)
            self.gui_default_savedir_ctrl.SetFont(self.default_font)
    
            self.gui_savemode_data=wxRadioBox(panel, -1, 'Ask where to save: *', 
                     choices = [ 'always', 'never', 'auto-resume' ])
            self.gui_savemode_data.SetFont(self.default_font)
            self.gui_savemode_data.SetSelection(1-self.config['gui_saveas_ask'])
    
            self.checkingcolor_icon = wxEmptyBitmap(16, 16)
            self.checkingcolor_iconptr = wxStaticBitmap(panel, -1, self.checkingcolor_icon)
            self.setColorIcon(self.checkingcolor_icon, self.checkingcolor_iconptr, self.checkingcolor)
    
            self.downloadcolor_icon = wxEmptyBitmap(16, 16)
            self.downloadcolor_iconptr = wxStaticBitmap(panel, -1, self.downloadcolor_icon)
            self.setColorIcon(self.downloadcolor_icon, self.downloadcolor_iconptr, self.downloadcolor)
    
            self.seedingcolor_icon = wxEmptyBitmap(16, 16)
            self.seedingcolor_iconptr = wxStaticBitmap(panel, -1, self.seedingcolor_icon)
            self.setColorIcon(self.seedingcolor_icon, self.downloadcolor_iconptr, self.seedingcolor)
            
            rowsizer = wxFlexGridSizer(cols = 2, hgap = 20)
    
            block12sizer = wxFlexGridSizer(cols = 1, vgap = 7)
    
            block1sizer = wxFlexGridSizer(cols = 1, vgap = 2)
            if (sys.platform == 'win32'):
                block1sizer.Add(self.win32_taskbar_icon_checkbox)
    #            block1sizer.Add(self.upnp_checkbox)
            block1sizer.Add(self.gui_stretchwindow_checkbox)
            block1sizer.Add(self.gui_displaystats_checkbox)
            block1sizer.Add(self.gui_displaymiscstats_checkbox)
            block1sizer.Add(self.security_checkbox)
            block1sizer.Add(self.autokick_checkbox)
            block1sizer.Add(self.buffering_checkbox)
            block1sizer.Add(self.breakup_checkbox)
            block1sizer.Add(self.autoflush_checkbox)
            if sys.version_info >= (2, 3) and socket.has_ipv6:
                block1sizer.Add(self.ipv6enabled_checkbox)
            block1sizer.Add(self.gui_forcegreenonfirewall_checkbox)
    
            block12sizer.Add(block1sizer)
    
            colorsizer = wxStaticBoxSizer(wxStaticBox(panel, -1, "Gauge Colors:"), wxVERTICAL)
            colorsizer1 = wxFlexGridSizer(cols = 7)
            colorsizer1.Add(StaticText('           Checking: '), 1, wxALIGN_BOTTOM)
            colorsizer1.Add(self.checkingcolor_iconptr, 1, wxALIGN_BOTTOM)
            colorsizer1.Add(StaticText('   Downloading: '), 1, wxALIGN_BOTTOM)
            colorsizer1.Add(self.downloadcolor_iconptr, 1, wxALIGN_BOTTOM)
            colorsizer1.Add(StaticText('   Seeding: '), 1, wxALIGN_BOTTOM)
            colorsizer1.Add(self.seedingcolor_iconptr, 1, wxALIGN_BOTTOM)
            colorsizer1.Add(StaticText('  '))
            minsize = self.checkingcolor_iconptr.GetBestSize()
            minsize.SetHeight(minsize.GetHeight()+5)
            colorsizer1.SetMinSize(minsize)
            colorsizer.Add(colorsizer1)
           
            block12sizer.Add(colorsizer, 1, wxALIGN_LEFT)
    
            rowsizer.Add(block12sizer)
    
            block3sizer = wxFlexGridSizer(cols = 1)
    
            portsettingsSizer = wxStaticBoxSizer(wxStaticBox(panel, -1, "Port Range:*"), wxVERTICAL)
            portsettingsSizer1 = wxGridSizer(cols = 2, vgap = 1)
            portsettingsSizer1.Add(StaticText('From: '), 1, wxALIGN_CENTER_VERTICAL|wxALIGN_RIGHT)
            portsettingsSizer1.Add(self.minport_data, 1, wxALIGN_BOTTOM)
            portsettingsSizer1.Add(StaticText('To: '), 1, wxALIGN_CENTER_VERTICAL|wxALIGN_RIGHT)
            portsettingsSizer1.Add(self.maxport_data, 1, wxALIGN_BOTTOM)
            portsettingsSizer.Add(portsettingsSizer1)
            portsettingsSizer.Add(self.randomport_checkbox, 1, wxALIGN_CENTER)
            block3sizer.Add(portsettingsSizer, 1, wxALIGN_CENTER)
            block3sizer.Add(StaticText(' '))
            block3sizer.Add(self.gui_ratesettingsmode_data, 1, wxALIGN_CENTER)
            block3sizer.Add(StaticText(' '))
            ratesettingsSizer = wxFlexGridSizer(cols = 1, vgap = 2)
            ratesettingsSizer.Add(StaticText('Default Rate Setting: *'), 1, wxALIGN_CENTER)
            ratesettingsSizer.Add(self.gui_ratesettingsdefault_data, 1, wxALIGN_CENTER)
            block3sizer.Add(ratesettingsSizer, 1, wxALIGN_CENTER)
            if (sys.platform == 'win32'):
                block3sizer.Add(StaticText(' '))
                upnpSizer = wxFlexGridSizer(cols = 1, vgap = 2)
                upnpSizer.Add(StaticText('UPnP Port Forwarding: *'), 1, wxALIGN_CENTER)
                upnpSizer.Add(self.upnp_data, 1, wxALIGN_CENTER)
                block3sizer.Add(upnpSizer, 1, wxALIGN_CENTER)
            
            rowsizer.Add(block3sizer)
            colsizer.Add(rowsizer)
    
            block4sizer = wxFlexGridSizer(cols = 3, hgap = 15)        
            savepathsizer = wxFlexGridSizer(cols = 2, vgap = 1)
            savepathsizer.Add(StaticText('Default Save Path: *'))
            savepathsizer.Add(StaticText(' '))
            savepathsizer.Add(self.gui_default_savedir_ctrl, 1, wxEXPAND)
            savepathButton = wxButton(panel, -1, '...', size = (18, 18))
    #        savepathButton.SetFont(self.default_font)
            savepathsizer.Add(savepathButton, 0, wxALIGN_CENTER)
            savepathsizer.Add(self.gui_savemode_data, 0, wxALIGN_CENTER)
            block4sizer.Add(savepathsizer, -1, wxALIGN_BOTTOM)
    
            fontsizer = wxFlexGridSizer(cols = 1, vgap = 2)
            fontsizer.Add(StaticText(''))
            fontsizer.Add(StaticText('Font: *'), 1, wxALIGN_CENTER)
            fontsizer.Add(self.gui_font_data, 1, wxALIGN_CENTER)
            block4sizer.Add(fontsizer, 1, wxALIGN_CENTER_VERTICAL)
    
            dratesettingsSizer = wxFlexGridSizer(cols = 1, vgap = 2)
            dratesettingsSizer.Add(StaticText('Default Max'), 1, wxALIGN_CENTER)
            dratesettingsSizer.Add(StaticText('Download Rate'), 1, wxALIGN_CENTER)
            dratesettingsSizer.Add(StaticText('(kB/s): *'), 1, wxALIGN_CENTER)
            dratesettingsSizer.Add(self.maxdownload_data, 1, wxALIGN_CENTER)
            dratesettingsSizer.Add(StaticText('(0 = disabled)'), 1, wxALIGN_CENTER)
            
            block4sizer.Add(dratesettingsSizer, 1, wxALIGN_CENTER_VERTICAL)
    
            colsizer.Add(block4sizer, 0, wxALIGN_CENTER)
    #        colsizer.Add(StaticText(' '))
    
            savesizer = wxGridSizer(cols = 4, hgap = 10)
            saveButton = wxButton(panel, -1, 'Save')
    #        saveButton.SetFont(self.default_font)
            savesizer.Add(saveButton, 0, wxALIGN_CENTER)
    
            cancelButton = wxButton(panel, -1, 'Cancel')
    #        cancelButton.SetFont(self.default_font)
            savesizer.Add(cancelButton, 0, wxALIGN_CENTER)
    
            defaultsButton = wxButton(panel, -1, 'Revert to Defaults')
    #        defaultsButton.SetFont(self.default_font)
            savesizer.Add(defaultsButton, 0, wxALIGN_CENTER)
    
            advancedButton = wxButton(panel, -1, 'Advanced...')
    #        advancedButton.SetFont(self.default_font)
            savesizer.Add(advancedButton, 0, wxALIGN_CENTER)
            colsizer.Add(savesizer, 1, wxALIGN_CENTER)
    
            resizewarningtext=StaticText('* These settings will not take effect until the next time you start BitTorrent', self.FONT-2)
            colsizer.Add(resizewarningtext, 1, wxALIGN_CENTER)
    
            border = wxBoxSizer(wxHORIZONTAL)
            border.Add(colsizer, 1, wxEXPAND | wxALL, 4)
            
            panel.SetSizer(border)
            panel.SetAutoLayout(True)
    
            self.advancedConfig = {}
    
            def setDefaults(evt, self = self):
                try:
                    self.minport_data.SetValue(self.defaults['minport'])
                    self.maxport_data.SetValue(self.defaults['maxport'])
                    self.randomport_checkbox.SetValue(self.defaults['random_port'])
                    self.gui_stretchwindow_checkbox.SetValue(self.defaults['gui_stretchwindow'])
                    self.gui_displaystats_checkbox.SetValue(self.defaults['gui_displaystats'])
                    self.gui_displaymiscstats_checkbox.SetValue(self.defaults['gui_displaymiscstats'])
                    self.security_checkbox.SetValue(self.defaults['security'])
                    self.autokick_checkbox.SetValue(self.defaults['auto_kick'])
                    self.buffering_checkbox.SetValue(self.defaults['buffer_reads'])
                    self.breakup_checkbox.SetValue(self.defaults['breakup_seed_bitfield'])
                    self.autoflush_checkbox.SetValue(self.defaults['auto_flush'])
                    if sys.version_info >= (2, 3) and socket.has_ipv6:
                        self.ipv6enabled_checkbox.SetValue(self.defaults['ipv6_enabled'])
                    self.gui_forcegreenonfirewall_checkbox.SetValue(self.defaults['gui_forcegreenonfirewall'])
                    self.gui_font_data.SetValue(self.defaults['gui_font'])
                    self.gui_ratesettingsdefault_data.SetStringSelection(self.defaults['gui_ratesettingsdefault'])
                    self.maxdownload_data.SetValue(self.defaults['max_download_rate'])
                    self.gui_ratesettingsmode_data.SetStringSelection(self.defaults['gui_ratesettingsmode'])
                    self.gui_default_savedir_ctrl.SetValue(self.defaults['gui_default_savedir'])
                    self.gui_savemode_data.SetSelection(1-self.defaults['gui_saveas_ask'])
        
                    self.checkingcolor = HexToColor(self.defaults['gui_checkingcolor'])
                    self.setColorIcon(self.checkingcolor_icon, self.checkingcolor_iconptr, self.checkingcolor)
                    self.downloadcolor = HexToColor(self.defaults['gui_downloadcolor'])
                    self.setColorIcon(self.downloadcolor_icon, self.downloadcolor_iconptr, self.downloadcolor)
                    self.seedingcolor = HexToColor(self.defaults['gui_seedingcolor'])
                    self.setColorIcon(self.seedingcolor_icon, self.seedingcolor_iconptr, self.seedingcolor)
        
                    if (sys.platform == 'win32'):
                        self.win32_taskbar_icon_checkbox.SetValue(self.defaults['win32_taskbar_icon'])
        #                self.upnp_checkbox.SetValue(self.defaults['upnp_nat_access'])
                        self.upnp_data.SetSelection(self.defaults['upnp_nat_access'])
        
                    # reset advanced too
                    self.advancedConfig = {}
                    for key in ['ip', 'bind', 'min_peers', 'max_initiate', 'display_interval', 
                'alloc_type', 'alloc_rate', 'max_files_open', 'max_connections', 'super_seeder', 
                'ipv6_binds_v4', 'double_check', 'triple_check', 'lock_files', 'lock_while_reading', 
                'expire_cache_data']:
                        self.advancedConfig[key] = self.defaults[key]
                    self.CloseAdvanced()
                except:
                    self.parent.exception()
    
    
            def saveConfigs(evt, self = self):
                try:
                    self.config['gui_stretchwindow']=int(self.gui_stretchwindow_checkbox.GetValue())
                    self.config['gui_displaystats']=int(self.gui_displaystats_checkbox.GetValue())
                    self.config['gui_displaymiscstats']=int(self.gui_displaymiscstats_checkbox.GetValue())
                    self.config['security']=int(self.security_checkbox.GetValue())
                    self.config['auto_kick']=int(self.autokick_checkbox.GetValue())
                    buffering=int(self.buffering_checkbox.GetValue())
                    self.config['buffer_reads']=buffering
                    if buffering:
                        self.config['write_buffer_size']=self.defaults['write_buffer_size']
                    else:
                        self.config['write_buffer_size']=0
                    self.config['breakup_seed_bitfield']=int(self.breakup_checkbox.GetValue())
                    if self.autoflush_checkbox.GetValue():
                        self.config['auto_flush']=5
                    else:
                        self.config['auto_flush']=0
                    if sys.version_info >= (2, 3) and socket.has_ipv6:
                        self.config['ipv6_enabled']=int(self.ipv6enabled_checkbox.GetValue())
                    self.config['gui_forcegreenonfirewall']=int(self.gui_forcegreenonfirewall_checkbox.GetValue())
                    self.config['minport']=self.minport_data.GetValue()
                    self.config['maxport']=self.maxport_data.GetValue()
                    self.config['random_port']=int(self.randomport_checkbox.GetValue())
                    self.config['gui_font']=self.gui_font_data.GetValue()
                    self.config['gui_ratesettingsdefault']=self.gui_ratesettingsdefault_data.GetStringSelection()
                    self.config['max_download_rate']=self.maxdownload_data.GetValue()
                    self.config['gui_ratesettingsmode']=self.gui_ratesettingsmode_data.GetStringSelection()
                    self.config['gui_default_savedir']=self.gui_default_savedir_ctrl.GetValue()
                    self.config['gui_saveas_ask']=1-self.gui_savemode_data.GetSelection()
                    self.config['gui_checkingcolor']=ColorToHex(self.checkingcolor)
                    self.config['gui_downloadcolor']=ColorToHex(self.downloadcolor)
                    self.config['gui_seedingcolor']=ColorToHex(self.seedingcolor)
                    
                    if (sys.platform == 'win32'):
                        self.config['win32_taskbar_icon']=int(self.win32_taskbar_icon_checkbox.GetValue())
        #                self.config['upnp_nat_access']=int(self.upnp_checkbox.GetValue())
                        self.config['upnp_nat_access']=self.upnp_data.GetSelection()
        
                    if self.advancedConfig:
                        for key, val in self.advancedConfig.items():
                            self.config[key] = val
        
                    self.writeConfigFile()
                    self._configReset = True
                    self.Close()
                except:
                    self.parent.exception()
    
            def cancelConfigs(evt, self = self):
                self.Close()
    
            def savepath_set(evt, self = self):
                try:
                    d = self.gui_default_savedir_ctrl.GetValue()
                    if d == '':
                        d = self.config['last_saved']
                    dl = wxDirDialog(self.panel, 'Choose a default directory to save to', 
                        d, style = wxDD_DEFAULT_STYLE | wxDD_NEW_DIR_BUTTON)
                    if dl.ShowModal() == wxID_OK:
                        self.gui_default_savedir_ctrl.SetValue(dl.GetPath())
                except:
                    self.parent.exception()
    
            def checkingcoloricon_set(evt, self = self):
                try:
                    newcolor = self.getColorFromUser(self.panel, self.checkingcolor)
                    self.setColorIcon(self.checkingcolor_icon, self.checkingcolor_iconptr, newcolor)
                    self.checkingcolor = newcolor
                except:
                    self.parent.exception()
    
            def downloadcoloricon_set(evt, self = self):
                try:
                    newcolor = self.getColorFromUser(self.panel, self.downloadcolor)
                    self.setColorIcon(self.downloadcolor_icon, self.downloadcolor_iconptr, newcolor)
                    self.downloadcolor = newcolor
                except:
                    self.parent.exception()
    
            def seedingcoloricon_set(evt, self = self):
                try:
                    newcolor = self.getColorFromUser(self.panel, self.seedingcolor)
                    self.setColorIcon(self.seedingcolor_icon, self.seedingcolor_iconptr, newcolor)
                    self.seedingcolor = newcolor
                except:
                    self.parent.exception()

            EVT_BUTTON(self.configMenuBox, saveButton.GetId(), saveConfigs)
            EVT_BUTTON(self.configMenuBox, cancelButton.GetId(), cancelConfigs)
            EVT_BUTTON(self.configMenuBox, defaultsButton.GetId(), setDefaults)
            EVT_BUTTON(self.configMenuBox, advancedButton.GetId(), self.advancedMenu)
            EVT_BUTTON(self.configMenuBox, savepathButton.GetId(), savepath_set)
            EVT_LEFT_DOWN(self.checkingcolor_iconptr, checkingcoloricon_set)
            EVT_LEFT_DOWN(self.downloadcolor_iconptr, downloadcoloricon_set)
            EVT_LEFT_DOWN(self.seedingcolor_iconptr, seedingcoloricon_set)
    
            self.configMenuBox.Show()
            border.Fit(panel)
            self.configMenuBox.Fit()
        except:
            self.parent.exception()


    def Close(self):
        self.CloseAdvanced()
        if self.configMenuBox is not None:
            try:
                self.configMenuBox.Close()
            except wxPyDeadObjectError, e:
                pass
            self.configMenuBox = None

    def advancedMenu(self, event = None):
        try:
            if not self.advancedConfig:
                for key in ['ip', 'bind', 'min_peers', 'max_initiate', 'display_interval', 
            'alloc_type', 'alloc_rate', 'max_files_open', 'max_connections', 'super_seeder', 
            'ipv6_binds_v4', 'double_check', 'triple_check', 'lock_files', 'lock_while_reading', 
            'expire_cache_data']:
                    self.advancedConfig[key] = self.config[key]
    
            if (self.advancedMenuBox is not None):
                try:
                    self.advancedMenuBox.Close()
                except wxPyDeadObjectError, e:
                    self.advancedMenuBox = None
    
            self.advancedMenuBox = wxFrame(None, -1, 'BitTorrent Advanced Preferences', size = (1, 1), 
                                style = wxDEFAULT_FRAME_STYLE|wxFULL_REPAINT_ON_RESIZE)
            if (sys.platform == 'win32'):
                self.advancedMenuBox.SetIcon(self.icon)
    
            panel = wxPanel(self.advancedMenuBox, -1)
    #        self.panel = panel
    
            def StaticText(text, font = self.FONT, underline = False, color = None, panel = panel):
                x = wxStaticText(panel, -1, text, style = wxALIGN_LEFT)
                x.SetFont(wxFont(font, wxDEFAULT, wxNORMAL, wxNORMAL, underline))
                if color is not None:
                    x.SetForegroundColour(color)
                return x
    
            colsizer = wxFlexGridSizer(cols = 1, hgap = 13, vgap = 13)
            warningtext = StaticText('CHANGE THESE SETTINGS AT YOUR OWN RISK', self.FONT+4, True, 'Red')
            colsizer.Add(warningtext, 1, wxALIGN_CENTER)
    
            self.ip_data = wxTextCtrl(parent = panel, id = -1, 
                        value = self.advancedConfig['ip'], 
                        size = (self.FONT*13, int(self.FONT*2.2)), style = wxTE_PROCESS_TAB)
            self.ip_data.SetFont(self.default_font)
            
            self.bind_data = wxTextCtrl(parent = panel, id = -1, 
                        value = self.advancedConfig['bind'], 
                        size = (self.FONT*13, int(self.FONT*2.2)), style = wxTE_PROCESS_TAB)
            self.bind_data.SetFont(self.default_font)
            
            if sys.version_info >= (2, 3) and socket.has_ipv6:
                self.ipv6bindsv4_data=wxChoice(panel, -1, 
                                 choices = ['separate sockets', 'single socket'])
                self.ipv6bindsv4_data.SetFont(self.default_font)
                self.ipv6bindsv4_data.SetSelection(self.advancedConfig['ipv6_binds_v4'])
    
            self.minpeers_data = wxSpinCtrl(panel, -1, '', (-1, -1), (self.FONT*7, -1))
            self.minpeers_data.SetFont(self.default_font)
            self.minpeers_data.SetRange(10, 100)
            self.minpeers_data.SetValue(self.advancedConfig['min_peers'])
            # max_initiate = 2*minpeers
    
            self.displayinterval_data = wxSpinCtrl(panel, -1, '', (-1, -1), (self.FONT*7, -1))
            self.displayinterval_data.SetFont(self.default_font)
            self.displayinterval_data.SetRange(100, 2000)
            self.displayinterval_data.SetValue(int(self.advancedConfig['display_interval']*1000))
    
            self.alloctype_data = wxChoice(panel, -1, 
                             choices = ['normal', 'background', 'pre-allocate', 'sparse'])
            self.alloctype_data.SetFont(self.default_font)
            self.alloctype_data.SetStringSelection(self.advancedConfig['alloc_type'])
    
            self.allocrate_data = wxSpinCtrl(panel, -1, '', (-1, -1), (self.FONT*7, -1))
            self.allocrate_data.SetFont(self.default_font)
            self.allocrate_data.SetRange(1, 100)
            self.allocrate_data.SetValue(int(self.advancedConfig['alloc_rate']))
    
            self.locking_data = wxChoice(panel, -1, 
                               choices = ['no locking', 'lock while writing', 'lock always'])
            self.locking_data.SetFont(self.default_font)
            if self.advancedConfig['lock_files']:
                if self.advancedConfig['lock_while_reading']:
                    self.locking_data.SetSelection(2)
                else:
                    self.locking_data.SetSelection(1)
            else:
                self.locking_data.SetSelection(0)
    
            self.doublecheck_data = wxChoice(panel, -1, 
                               choices = ['no extra checking', 'double-check', 'triple-check'])
            self.doublecheck_data.SetFont(self.default_font)
            if self.advancedConfig['double_check']:
                if self.advancedConfig['triple_check']:
                    self.doublecheck_data.SetSelection(2)
                else:
                    self.doublecheck_data.SetSelection(1)
            else:
                self.doublecheck_data.SetSelection(0)
    
            self.maxfilesopen_choices = ['50', '100', '200', 'no limit ']
            self.maxfilesopen_data = wxChoice(panel, -1, choices = self.maxfilesopen_choices)
            self.maxfilesopen_data.SetFont(self.default_font)
            setval = self.advancedConfig['max_files_open']
            if setval == 0:
                setval = 'no limit '
            else:
                setval = str(setval)
            if not setval in self.maxfilesopen_choices:
                setval = self.maxfilesopen_choices[0]
            self.maxfilesopen_data.SetStringSelection(setval)
    
            self.maxconnections_choices = ['no limit ', '20', '30', '40', '50', '60', '100', '200']
            self.maxconnections_data = wxChoice(panel, -1, choices = self.maxconnections_choices)
            self.maxconnections_data.SetFont(self.default_font)
            setval = self.advancedConfig['max_connections']
            if setval == 0:
                setval = 'no limit '
            else:
                setval = str(setval)
            if not setval in self.maxconnections_choices:
                setval = self.maxconnections_choices[0]
            self.maxconnections_data.SetStringSelection(setval)
    
            self.superseeder_data = wxChoice(panel, -1, 
                             choices = ['normal', 'super-seed'])
            self.superseeder_data.SetFont(self.default_font)
            self.superseeder_data.SetSelection(self.advancedConfig['super_seeder'])
    
            self.expirecache_choices = ['never ', '3', '5', '7', '10', '15', '30', '60', '90']
            self.expirecache_data = wxChoice(panel, -1, choices = self.expirecache_choices)
            setval = self.advancedConfig['expire_cache_data']
            if setval == 0:
                setval = 'never '
            else:
                setval = str(setval)
            if not setval in self.expirecache_choices:
                setval = self.expirecache_choices[0]
            self.expirecache_data.SetFont(self.default_font)
            self.expirecache_data.SetStringSelection(setval)
           
    
            twocolsizer = wxFlexGridSizer(cols = 2, hgap = 20)
            datasizer = wxFlexGridSizer(cols = 2, vgap = 2)
            datasizer.Add(StaticText('Local IP: '), 1, wxALIGN_CENTER_VERTICAL)
            datasizer.Add(self.ip_data)
            datasizer.Add(StaticText('IP to bind to: '), 1, wxALIGN_CENTER_VERTICAL)
            datasizer.Add(self.bind_data)
            if sys.version_info >= (2, 3) and socket.has_ipv6:
                datasizer.Add(StaticText('IPv6 socket handling: '), 1, wxALIGN_CENTER_VERTICAL)
                datasizer.Add(self.ipv6bindsv4_data)
            datasizer.Add(StaticText('Minimum number of peers: '), 1, wxALIGN_CENTER_VERTICAL)
            datasizer.Add(self.minpeers_data)
            datasizer.Add(StaticText('Display interval (ms): '), 1, wxALIGN_CENTER_VERTICAL)
            datasizer.Add(self.displayinterval_data)
            datasizer.Add(StaticText('Disk allocation type:'), 1, wxALIGN_CENTER_VERTICAL)
            datasizer.Add(self.alloctype_data)
            datasizer.Add(StaticText('Allocation rate (MiB/s):'), 1, wxALIGN_CENTER_VERTICAL)
            datasizer.Add(self.allocrate_data)
            datasizer.Add(StaticText('File locking:'), 1, wxALIGN_CENTER_VERTICAL)
            datasizer.Add(self.locking_data)
            datasizer.Add(StaticText('Extra data checking:'), 1, wxALIGN_CENTER_VERTICAL)
            datasizer.Add(self.doublecheck_data)
            datasizer.Add(StaticText('Max files open:'), 1, wxALIGN_CENTER_VERTICAL)
            datasizer.Add(self.maxfilesopen_data)
            datasizer.Add(StaticText('Max peer connections:'), 1, wxALIGN_CENTER_VERTICAL)
            datasizer.Add(self.maxconnections_data)
            datasizer.Add(StaticText('Default seeding mode:'), 1, wxALIGN_CENTER_VERTICAL)
            datasizer.Add(self.superseeder_data)
            datasizer.Add(StaticText('Expire resume data(days):'), 1, wxALIGN_CENTER_VERTICAL)
            datasizer.Add(self.expirecache_data)
            
            twocolsizer.Add(datasizer)
    
            infosizer = wxFlexGridSizer(cols = 1)
            self.hinttext = StaticText('', self.FONT, False, 'Blue')
            infosizer.Add(self.hinttext, 1, wxALIGN_LEFT|wxALIGN_CENTER_VERTICAL)
            infosizer.SetMinSize((180, 100))
            twocolsizer.Add(infosizer, 1, wxEXPAND)
    
            colsizer.Add(twocolsizer)
    
            savesizer = wxGridSizer(cols = 3, hgap = 20)
            okButton = wxButton(panel, -1, 'OK')
    #        okButton.SetFont(self.default_font)
            savesizer.Add(okButton, 0, wxALIGN_CENTER)
    
            cancelButton = wxButton(panel, -1, 'Cancel')
    #        cancelButton.SetFont(self.default_font)
            savesizer.Add(cancelButton, 0, wxALIGN_CENTER)
    
            defaultsButton = wxButton(panel, -1, 'Revert to Defaults')
    #        defaultsButton.SetFont(self.default_font)
            savesizer.Add(defaultsButton, 0, wxALIGN_CENTER)
            colsizer.Add(savesizer, 1, wxALIGN_CENTER)
    
            resizewarningtext=StaticText('None of these settings will take effect until the next time you start BitTorrent', self.FONT-2)
            colsizer.Add(resizewarningtext, 1, wxALIGN_CENTER)
    
            border = wxBoxSizer(wxHORIZONTAL)
            border.Add(colsizer, 1, wxEXPAND | wxALL, 4)
            
            panel.SetSizer(border)
            panel.SetAutoLayout(True)
    
            def setDefaults(evt, self = self):
                try:
                    self.ip_data.SetValue(self.defaults['ip'])
                    self.bind_data.SetValue(self.defaults['bind'])
                    if sys.version_info >= (2, 3) and socket.has_ipv6:
                        self.ipv6bindsv4_data.SetSelection(self.defaults['ipv6_binds_v4'])
                    self.minpeers_data.SetValue(self.defaults['min_peers'])
                    self.displayinterval_data.SetValue(int(self.defaults['display_interval']*1000))
                    self.alloctype_data.SetStringSelection(self.defaults['alloc_type'])
                    self.allocrate_data.SetValue(int(self.defaults['alloc_rate']))
                    if self.defaults['lock_files']:
                        if self.defaults['lock_while_reading']:
                            self.locking_data.SetSelection(2)
                        else:
                            self.locking_data.SetSelection(1)
                    else:
                        self.locking_data.SetSelection(0)
                    if self.defaults['double_check']:
                        if self.defaults['triple_check']:
                            self.doublecheck_data.SetSelection(2)
                        else:
                            self.doublecheck_data.SetSelection(1)
                    else:
                        self.doublecheck_data.SetSelection(0)
                    setval = self.defaults['max_files_open']
                    if setval == 0:
                        setval = 'no limit '
                    else:
                        setval = str(setval)
                    if not setval in self.maxfilesopen_choices:
                        setval = self.maxfilesopen_choices[0]
                    self.maxfilesopen_data.SetStringSelection(setval)
                    setval = self.defaults['max_connections']
                    if setval == 0:
                        setval = 'no limit '
                    else:
                        setval = str(setval)
                    if not setval in self.maxconnections_choices:
                        setval = self.maxconnections_choices[0]
                    self.maxconnections_data.SetStringSelection(setval)
                    self.superseeder_data.SetSelection(int(self.defaults['super_seeder']))
                    setval = self.defaults['expire_cache_data']
                    if setval == 0:
                        setval = 'never '
                    else:
                        setval = str(setval)
                    if not setval in self.expirecache_choices:
                        setval = self.expirecache_choices[0]
                    self.expirecache_data.SetStringSelection(setval)
                except:
                    self.parent.exception()
    
            def saveConfigs(evt, self = self):
                try:
                    self.advancedConfig['ip'] = self.ip_data.GetValue()
                    self.advancedConfig['bind'] = self.bind_data.GetValue()
                    if sys.version_info >= (2, 3) and socket.has_ipv6:
                        self.advancedConfig['ipv6_binds_v4'] = self.ipv6bindsv4_data.GetSelection()
                    self.advancedConfig['min_peers'] = self.minpeers_data.GetValue()
                    self.advancedConfig['display_interval'] = float(self.displayinterval_data.GetValue())/1000
                    self.advancedConfig['alloc_type'] = self.alloctype_data.GetStringSelection()
                    self.advancedConfig['alloc_rate'] = float(self.allocrate_data.GetValue())
                    self.advancedConfig['lock_files'] = int(self.locking_data.GetSelection() >= 1)
                    self.advancedConfig['lock_while_reading'] = int(self.locking_data.GetSelection() > 1)
                    self.advancedConfig['double_check'] = int(self.doublecheck_data.GetSelection() >= 1)
                    self.advancedConfig['triple_check'] = int(self.doublecheck_data.GetSelection() > 1)
                    try:
                        self.advancedConfig['max_files_open'] = int(self.maxfilesopen_data.GetStringSelection())
                    except:       # if it ain't a number, it must be "no limit"
                        self.advancedConfig['max_files_open'] = 0
                    try:
                        self.advancedConfig['max_connections'] = int(self.maxconnections_data.GetStringSelection())
                        self.advancedConfig['max_initiate'] = min(
                            2*self.advancedConfig['min_peers'], self.advancedConfig['max_connections'])
                    except:       # if it ain't a number, it must be "no limit"
                        self.advancedConfig['max_connections'] = 0
                        self.advancedConfig['max_initiate'] = 2*self.advancedConfig['min_peers']
                    self.advancedConfig['super_seeder']=int(self.superseeder_data.GetSelection())
                    try:
                        self.advancedConfig['expire_cache_data'] = int(self.expirecache_data.GetStringSelection())
                    except:
                        self.advancedConfig['expire_cache_data'] = 0
                    self.advancedMenuBox.Close()
                except:
                    self.parent.exception()
    
            def cancelConfigs(evt, self = self):            
                self.advancedMenuBox.Close()
    
            def ip_hint(evt, self = self):
                self.hinttext.SetLabel('\n\n\nThe IP reported to the tracker.\n' +
                                      'unless the tracker is on the\n' +
                                      'same intranet as this client,\n' +
                                      'the tracker will autodetect the\n' +
                                      "client's IP and ignore this\n" +
                                      "value.")
    
            def bind_hint(evt, self = self):
                self.hinttext.SetLabel('\n\n\nThe IP the client will bind to.\n' +
                                      'Only useful if your machine is\n' +
                                      'directly handling multiple IPs.\n' +
                                      "If you don't know what this is,\n" +
                                      "leave it blank.")
    
            def ipv6bindsv4_hint(evt, self = self):
                self.hinttext.SetLabel('\n\n\nCertain operating systems will\n' +
                                      'open IPv4 protocol connections on\n' +
                                      'an IPv6 socket; others require you\n' +
                                      "to open two sockets on the same\n" +
                                      "port, one IPv4 and one IPv6.")
    
            def minpeers_hint(evt, self = self):
                self.hinttext.SetLabel('\n\n\nThe minimum number of peers the\n' +
                                      'client tries to stay connected\n' +
                                      'with.  Do not set this higher\n' +
                                      'unless you have a very fast\n' +
                                      "connection and a lot of system\n" +
                                      "resources.")
    
            def displayinterval_hint(evt, self = self):
                self.hinttext.SetLabel('\n\n\nHow often to update the\n' +
                                      'graphical display, in 1/1000s\n' +
                                      'of a second. Setting this too low\n' +
                                      "will strain your computer's\n" +
                                      "processor and video access.")
    
            def alloctype_hint(evt, self = self):
                self.hinttext.SetLabel('\n\nHow to allocate disk space.\n' +
                                      'normal allocates space as data is\n' +
                                      'received, background also adds\n' +
                                      "space in the background, pre-\n" +
                                      "allocate reserves up front, and\n" +
                                      'sparse is only for filesystems\n' +
                                      'that support it by default.')
    
            def allocrate_hint(evt, self = self):
                self.hinttext.SetLabel('\n\n\nAt what rate to allocate disk\n' +
                                      'space when allocating in the\n' +
                                      'background.  Set this too high on a\n' +
                                      "slow filesystem and your download\n" +
                                      "will slow to a crawl.")
    
            def locking_hint(evt, self = self):
                self.hinttext.SetLabel('\n\n\n\nFile locking prevents other\n' +
                                      'programs (including other instances\n' +
                                      'of BitTorrent) from accessing files\n' +
                                      "you are downloading.")
    
            def doublecheck_hint(evt, self = self):
                self.hinttext.SetLabel('\n\n\nHow much extra checking to do\n' +
                                      'making sure no data is corrupted.\n' +
                                      'Double-check mode uses more CPU,\n' +
                                      "while triple-check mode increases\n" +
                                      "disk accesses.")
    
            def maxfilesopen_hint(evt, self = self):
                self.hinttext.SetLabel('\n\n\nThe maximum number of files to\n' +
                                      'keep open at the same time.  Zero\n' +
                                      'means no limit.  Please note that\n' +
                                      "if this option is in effect,\n" +
                                      "files are not guaranteed to be\n" +
                                      "locked.")
    
            def maxconnections_hint(evt, self = self):
                self.hinttext.SetLabel('\n\nSome operating systems, most\n' +
                                      'notably Windows 9x/ME combined\n' +
                                      'with certain network drivers,\n' +
                                      "cannot handle more than a certain\n" +
                                      "number of open ports.  If the\n" +
                                      "client freezes, try setting this\n" +
                                      "to 60 or below.")
    
            def superseeder_hint(evt, self = self):
                self.hinttext.SetLabel('\n\nThe "super-seed" method allows\n' +
                                      'a single source to more efficiently\n' +
                                      'seed a large torrent, but is not\n' +
                                      "necessary in a well-seeded torrent,\n" +
                                      "and causes problems with statistics.\n" +
                                      "Unless you routinely seed torrents\n" +
                                      "you can enable this by selecting\n" +
                                      '"SUPER-SEED" for connection type.\n' +
                                      '(once enabled it does not turn off.)')
    
            def expirecache_hint(evt, self = self):
                self.hinttext.SetLabel('\n\nThe client stores temporary data\n' +
                                      'in order to handle downloading only\n' +
                                      'specific files from the torrent and\n' +
                                      "so it can resume downloads more\n" +
                                      "quickly.  This sets how long the\n" +
                                      "client will keep this data before\n" +
                                      "deleting it to free disk space.")
    
            EVT_BUTTON(self.advancedMenuBox, okButton.GetId(), saveConfigs)
            EVT_BUTTON(self.advancedMenuBox, cancelButton.GetId(), cancelConfigs)
            EVT_BUTTON(self.advancedMenuBox, defaultsButton.GetId(), setDefaults)
            EVT_ENTER_WINDOW(self.ip_data, ip_hint)
            EVT_ENTER_WINDOW(self.bind_data, bind_hint)
            if sys.version_info >= (2, 3) and socket.has_ipv6:
                EVT_ENTER_WINDOW(self.ipv6bindsv4_data, ipv6bindsv4_hint)
            EVT_ENTER_WINDOW(self.minpeers_data, minpeers_hint)
            EVT_ENTER_WINDOW(self.displayinterval_data, displayinterval_hint)
            EVT_ENTER_WINDOW(self.alloctype_data, alloctype_hint)
            EVT_ENTER_WINDOW(self.allocrate_data, allocrate_hint)
            EVT_ENTER_WINDOW(self.locking_data, locking_hint)
            EVT_ENTER_WINDOW(self.doublecheck_data, doublecheck_hint)
            EVT_ENTER_WINDOW(self.maxfilesopen_data, maxfilesopen_hint)
            EVT_ENTER_WINDOW(self.maxconnections_data, maxconnections_hint)
            EVT_ENTER_WINDOW(self.superseeder_data, superseeder_hint)
            EVT_ENTER_WINDOW(self.expirecache_data, expirecache_hint)
    
            self.advancedMenuBox.Show()
            border.Fit(panel)
            self.advancedMenuBox.Fit()
        except:
            self.parent.exception()


    def CloseAdvanced(self):
        if self.advancedMenuBox is not None:
            try:
                self.advancedMenuBox.Close()
            except wxPyDeadObjectError, e:
                self.advancedMenuBox = None

