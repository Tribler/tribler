import sys
import wx
import os

from random import shuffle
from traceback import print_exc
from cStringIO import StringIO

from wx.lib import masked, colourselect

from ABC.GUI.menu import MenuDialog
from ABC.GUI.toolbar import ToolBarDialog
from Utility.configreader import ConfigReader
from Utility.constants import * #IGNORE:W0611

from Tribler.Dialogs.socnetmyinfo import MyInfoWizard
from Tribler.CacheDB.CacheDBHandler import MyDBHandler
from Tribler.Video.VideoPlayer import *
from Tribler.Overlay.permid import permid_for_user

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

        self.minport = self.utility.makeNumCtrl(self, 1, min = 1, max = 65536)
        port_box = wx.BoxSizer(wx.HORIZONTAL)
        port_box.Add(wx.StaticText(self, -1, self.utility.lang.get('portnumber')), 0, wx.ALIGN_CENTER_VERTICAL)
        port_box.Add(self.minport, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        port_box.Add(wx.StaticText(self, -1, self.utility.lang.get('restartabc')), 0, wx.ALIGN_CENTER_VERTICAL)

        sizer.Add(port_box, 0, wx.EXPAND|wx.ALL, 5)

        self.kickban = wx.CheckBox(self, -1, self.utility.lang.get('kickban'))
        sizer.Add(self.kickban, 0, wx.ALIGN_LEFT|wx.ALL, 5)

        self.notsameip = wx.CheckBox(self, -1, self.utility.lang.get('security'))
        sizer.Add(self.notsameip, 0, wx.ALIGN_LEFT|wx.ALL, 5)
    
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

        self.initTasks()
        
    def loadValues(self, Read = None):
        if Read is None:
            Read = self.utility.config.Read
        
        self.minport.SetValue(Read('minport', 'int'))
        
        self.kickban.SetValue(Read('kickban', "boolean"))
        self.notsameip.SetValue(Read('notsameip', "boolean"))
        self.scrape.SetValue(Read('scrape', "boolean"))
        
    def apply(self):
        minport = int(self.minport.GetValue())
        if minport > 65535:
            minport = 65535

        minchanged = self.utility.config.Write('minport', minport)

        self.utility.config.Write('kickban', self.kickban.GetValue(), "boolean")
        self.utility.config.Write('notsameip', self.notsameip.GetValue(), "boolean")
        self.utility.config.Write('scrape', self.scrape.GetValue(), "boolean")       


################################################################
#
# Class: QueuePanel
#
# Contains settings that control how many torrents to start
# at once and when to start them
#
################################################################
class QueuePanel(ABCOptionPanel):
    def __init__(self, parent, dialog):
        ABCOptionPanel.__init__(self, parent, dialog)
        sizer = self.sizer

        #
        # Number of simultaneous active torrents
        #
        activesection_title = wx.StaticBox(self, -1, self.utility.lang.get('activetorrents'))
        activesection = wx.StaticBoxSizer(activesection_title, wx.VERTICAL)

        self.numsimtext = wx.SpinCtrl(self, size = wx.Size(60, -1))
        self.numsimtext.SetRange(0, 1000)

        numsim = wx.BoxSizer(wx.HORIZONTAL)
        numsim.Add(wx.StaticText(self, -1, self.utility.lang.get('maxnumsimul')), 0, wx.ALIGN_CENTER_VERTICAL)
        numsim.Add(self.numsimtext, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
        
        activesection.Add(numsim, 0, wx.ALL, 5)

        self.trig_finish_values = [ self.utility.lang.get('after_downloading') , self.utility.lang.get('after_seeding') ]
        self.trig_finish_seed  = wx.ComboBox(self, -1, "", wx.Point(-1, -1), wx.Size(-1, -1), self.trig_finish_values, wx.CB_DROPDOWN|wx.CB_READONLY)

        trigger_box = wx.BoxSizer(wx.HORIZONTAL)
        trigger_box.Add(wx.StaticText(self, -1, self.utility.lang.get('trignexttorrent')), 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)
        trigger_box.Add(self.trig_finish_seed, 0, wx.ALIGN_CENTER_VERTICAL)

        activesection.Add(trigger_box, 0, wx.ALL, 5)
        
        sizer.Add(activesection, 0, wx.EXPAND|wx.ALL, 5)

        #
        # Autostart torrents
        #
        autostartsection_title = wx.StaticBox(self, -1, self.utility.lang.get('autostart'))
        autostartsection = wx.StaticBoxSizer(autostartsection_title, wx.VERTICAL)

        self.autostart = wx.CheckBox(self, -1, self.utility.lang.get('autostart_threshold'))

        self.autostartthreshold = self.utility.makeNumCtrl(self, 0, integerWidth = 4)        
        autostart_line1box = wx.BoxSizer(wx.HORIZONTAL)
        autostart_line1box.Add(self.autostart, 0, wx.ALIGN_CENTER_VERTICAL)
        autostart_line1box.Add(self.autostartthreshold, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
        autostart_line1box.Add(wx.StaticText(self, -1, self.utility.lang.get('KB') + "/" + self.utility.lang.get('l_second')), 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 3)
        
        self.autostartdelay = self.utility.makeNumCtrl(self, 0, integerWidth = 4, min = 1)
        autostart_line2box = wx.BoxSizer(wx.HORIZONTAL)
        autostart_line2box.Add(wx.StaticText(self, -1, self.utility.lang.get('autostart_delay')), 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 20)
        autostart_line2box.Add(self.autostartdelay, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
        autostart_line2box.Add(wx.StaticText(self, -1, self.utility.lang.get('l_second')), 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 3)
        
        autostartsection.Add(autostart_line1box, 0, wx.ALL, 3)
        autostartsection.Add(autostart_line2box, 0, wx.ALL, 3)

        sizer.Add(autostartsection, 0, wx.EXPAND|wx.ALL, 5)

        #
        # Default priority for new torrents
        #
        self.priorities = [ self.utility.lang.get('highest'), 
                            self.utility.lang.get('high'), 
                            self.utility.lang.get('normal'), 
                            self.utility.lang.get('low'), 
                            self.utility.lang.get('lowest') ]
        
        self.defaultpriority = wx.ComboBox(self, -1, "", wx.Point(-1, -1), wx.Size(-1, -1), self.priorities, wx.CB_DROPDOWN|wx.CB_READONLY)

        prio_box = wx.BoxSizer(wx.HORIZONTAL)
        prio_box.Add(wx.StaticText(self, -1, self.utility.lang.get('defaultpriority')), 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)
        prio_box.Add(self.defaultpriority, 0, wx.ALIGN_CENTER_VERTICAL)       
        sizer.Add(prio_box, 0, wx.ALL, 5)

        self.failbehaviors = [ self.utility.lang.get('stop'), self.utility.lang.get('queue') ]
        self.failbehavior = wx.ComboBox(self, -1, "", wx.Point(-1, -1), wx.Size(-1, -1), self.failbehaviors, wx.CB_DROPDOWN|wx.CB_READONLY)

        fail_box = wx.BoxSizer(wx.HORIZONTAL)
        fail_box.Add(wx.StaticText(self, -1, self.utility.lang.get('failbehavior1')), 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)
        fail_box.Add(self.failbehavior, 0, wx.ALIGN_CENTER_VERTICAL)
        fail_box.Add(wx.StaticText(self, -1, self.utility.lang.get('failbehavior2')), 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
        sizer.Add(fail_box, 0, wx.ALL, 5)

        self.fastresume = wx.CheckBox(self, -1, self.utility.lang.get('fastresume'))
        self.fastresume.SetToolTipString(self.utility.lang.get('fastresume_hint'))
        sizer.Add(self.fastresume, 0, wx.ALL, 5)

#        self.skipcheck = wx.CheckBox(self, -1, self.utility.lang.get('skipcheck'))
#        self.skipcheck.SetToolTipString(self.utility.lang.get('skipcheck_hint'))
#        sizer.Add(self.skipcheck, 0, wx.ALL, 5)

        self.initTasks()
        
    def loadValues(self, Read = None):
        if Read is None:
            Read = self.utility.config.Read

        if Read('trigwhenfinishseed', "boolean"):
            trig_default_value = self.utility.lang.get('after_seeding')
        else:
            trig_default_value = self.utility.lang.get('after_downloading')
        self.trig_finish_seed.SetStringSelection(trig_default_value)

        currentprio = Read('defaultpriority', "int")
        if currentprio >= len(self.priorities):
            currentprio = len(self.priorities) - 1
        defaultprio = self.priorities[currentprio]
        self.defaultpriority.SetStringSelection(defaultprio)

        defaultfail = self.failbehaviors[Read('failbehavior', "int")]
        self.failbehavior.SetStringSelection(defaultfail)

        self.numsimtext.SetValue(Read('numsimdownload', "int"))
        
        self.fastresume.SetValue(Read('fastresume', "boolean"))
        
#        self.skipcheck.SetValue(Read('skipcheck', "boolean"))
        
        self.autostart.SetValue(Read('urm', "boolean"))
        self.autostartthreshold.SetValue(Read('urmupthreshold', "int"))
        self.autostartdelay.SetValue(Read('urmdelay', "int"))
        
    def apply(self):            
        self.utility.config.Write('fastresume', self.fastresume.GetValue(), "boolean")
#        self.utility.config.Write('skipcheck', self.skipcheck.GetValue(), "boolean")

        selected = self.priorities.index(self.defaultpriority.GetValue())
        self.utility.config.Write('defaultpriority', selected)

        self.utility.config.Write('failbehavior', self.failbehaviors.index(self.failbehavior.GetValue()))

        self.utility.config.Write('numsimdownload', self.numsimtext.GetValue())

        trigwhenfinished = (self.trig_finish_seed.GetValue() == self.utility.lang.get('after_seeding'))
        self.utility.config.Write('trigwhenfinishseed', trigwhenfinished, "boolean")
        
        self.utility.config.Write('urm', self.autostart.GetValue(), "boolean")
        self.utility.config.Write('urmupthreshold', self.autostartthreshold.GetValue())        
        self.utility.config.Write('urmdelay', self.autostartdelay.GetValue())

        self.utility.queue.UpdateRunningTorrentCounters()


################################################################
#
# Class: DisplayPanel
#
# Contains settings for how ABC looks
#
################################################################
class DisplayPanel(ABCOptionPanel):
    def __init__(self, parent, dialog):
        ABCOptionPanel.__init__(self, parent, dialog)
        sizer = self.sizer
        
        listfont_box = wx.BoxSizer(wx.HORIZONTAL)
               
        listfont_box.Add(wx.StaticText(self, -1, self.utility.lang.get('listfont')), 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)
        
        self.fontexample = wx.TextCtrl(self, -1, self.utility.lang.get('sampletext'))
        listfont_box.Add(self.fontexample, 1, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)
        
        fontbutton = browsebtn = wx.Button(self, -1, self.utility.lang.get('choosefont'), style = wx.BU_EXACTFIT)
        listfont_box.Add(fontbutton, 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)
        self.Bind(wx.EVT_BUTTON, self.onFontButton, fontbutton)
        
        sizer.Add(listfont_box, 0, wx.EXPAND|wx.ALIGN_LEFT|wx.ALL, 5)
        
        # Striped list options
        stripedlist_box = wx.BoxSizer(wx.HORIZONTAL)
        
        self.stripedlist = wx.CheckBox(self, -1, self.utility.lang.get('stripedlist'))
        stripedlist_box.Add(self.stripedlist, 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)
        
        self.stripedlist_button = colourselect.ColourSelect(self, -1, "", size = (60, 20))
        
        stripedlist_box.Add(self.stripedlist_button, 0, wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(stripedlist_box, 0, wx.ALIGN_LEFT|wx.ALL, 5)

        self.savecolumnwidth = wx.CheckBox(self, -1, self.utility.lang.get('savecolumnwidth'))        
        sizer.Add(self.savecolumnwidth, 0, wx.ALL, 5)
        
        self.showearthpanel = wx.CheckBox(self, -1, self.utility.lang.get('showearthpanel'))        
        sizer.Add(self.showearthpanel, 0, wx.ALL, 5)
        
        self.contextmenu = wx.Button(self, -1, self.utility.lang.get('customizecontextmenu') + "...")
        sizer.Add(self.contextmenu, 0, wx.ALL, 5)
        self.Bind(wx.EVT_BUTTON, self.onContextMenuDialog, self.contextmenu)

        self.toolbar = wx.Button(self, -1, self.utility.lang.get('customizetoolbar') + "...")
        sizer.Add(self.toolbar, 0, wx.ALL, 5)
        self.Bind(wx.EVT_BUTTON, self.onToolbarDialog, self.toolbar)
        
#        self.showmenuicons = wx.CheckBox(self, -1, self.utility.lang.get('showmenuicons'))
#        sizer.Add(self.showmenuicons, 0, wx.ALL, 5)
        
        self.initTasks()
        
    def onContextMenuDialog(self, event = None):
        dialog = MenuDialog(self, 'menu_listrightclick')
        dialog.ShowModal()
        dialog.Destroy()


    def onToolbarDialog(self, event = None):
        dialog = ToolBarDialog(self.utility.frame.GetToolBar())
        dialog.ShowModal()
        dialog.Destroy()

        
    def loadValues(self, Read = None):
        if Read is None:
            Read = self.utility.config.Read
        
        self.stripedlist.SetValue(Read('stripedlist', "boolean"))
        
        self.stripedlist_button.SetValue(Read('color_stripe', "color"))
        
        self.savecolumnwidth.SetValue(Read('savecolumnwidth', "boolean"))
        self.showearthpanel.SetValue(Read('showearthpanel', "boolean"))
#        self.showmenuicons.SetValue(Read('showmenuicons', "boolean"))
        
        # Get font information                          
        self.fontexample.SetFont(self.utility.getFontFromInfo(Read('listfont', "bencode-fontinfo")))

               
    def apply(self):
        self.utility.config.Write('savecolumnwidth', self.savecolumnwidth.GetValue(), "boolean")
        self.utility.config.Write('showearthpanel', self.showearthpanel.GetValue(), "boolean")
#        self.utility.config.Write('showmenuicons', self.showmenuicons.GetValue(), "boolean")
         
        overallchanged = False
        changed = self.utility.config.Write('stripedlist', self.stripedlist.GetValue(), "boolean")
        if changed:
            overallchanged = True
            
        # Set stripe color
        changed = self.utility.config.Write('color_stripe', self.stripedlist_button.GetColour(), "color")
        if changed:
            overallchanged = True
            
        if overallchanged:
            for ABCTorrentTemp in self.utility.torrents["all"]:
                ABCTorrentTemp.updateColor()
        
        # Set list font
        newfont = self.fontexample.GetFont()
        newfontinfo = self.utility.getInfoFromFont(newfont)

        fontchanged = self.utility.config.Write('listfont', newfontinfo, "bencode-fontinfo")

        if fontchanged:
            for managedlist in self.utility.lists:
                try:
                    if self.utility.lists[managedlist]:
                        managedlist.loadFont()
                except:
                    pass
                
    def onFontButton(self, event = None):
        fontdata = wx.FontData()
        fontdata.EnableEffects(False)
        fontdata.SetInitialFont(self.fontexample.GetFont())

        dlg = wx.FontDialog(self, fontdata)
        if dlg.ShowModal() == wx.ID_OK:
            data = dlg.GetFontData()
                        
            newfont = data.GetChosenFont()
            newfontinfo = self.utility.getInfoFromFont(newfont)
            
            oldfontinfo = self.utility.config.Read('listfont', "bencode-fontinfo")
                           
            changed = False
            for attr in oldfontinfo:
                if oldfontinfo[attr] != newfontinfo[attr]:
                    changed = True
                    break
            
            if changed:
                # (TODO: May need to adjust if a large font was used)
                self.fontexample.SetFont(newfont)
                self.Layout()
                self.Refresh()


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

        #rename torrent with dest
        self.rtwd = wx.CheckBox(self, -1, self.utility.lang.get('rtwd'))
        self.rtwd.SetValue(self.utility.config.Read('defrentorwithdest', "boolean"))
        sizer.Add(self.rtwd, 0, wx.ALIGN_LEFT|wx.ALL, 5)

        
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
        
        self.rtwd.SetValue(Read('defrentorwithdest', "boolean"))
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
        self.utility.frame.tbicon.updateIcon(False)
        
        # FIXME: quick hack to prevent Unicode problem, will still give problems
        # when French, i.e. "fran\,cais" is selected.
        #
        val = str(self.language_choice.GetValue())
        langname_index = self.language_names.index(val)
        self.utility.config.Write('language_file', self.language_filenames[langname_index])
        
        self.utility.config.Write('confirmonclose', self.confirmonclose.GetValue(), "boolean")
        
        self.utility.config.Write('defrentorwithdest', self.rtwd.GetValue(), "boolean")          
        
        if (sys.platform == 'win32'):
            self.utility.config.Write('associate', self.associate.GetValue(), "boolean")
            self.utility.regchecker.updateRegistry(self.associate.GetValue())         

    def getLanguages(self):
        langpath = os.path.join(self.utility.getPath(), "Lang")
        
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
           
        self.defaultdir = wx.CheckBox(self, -1, self.utility.lang.get('setdefaultfolder'))

        self.dir = wx.TextCtrl(self, -1, "")
        browsebtn = wx.Button(self, -1, "...", style = wx.BU_EXACTFIT)
        self.Bind(wx.EVT_BUTTON, self.onBrowseDir, browsebtn)

        dirbox = wx.BoxSizer(wx.HORIZONTAL)
        dirbox.Add(self.defaultdir, 0, wx.ALIGN_CENTER_VERTICAL)
        dirbox.Add(self.dir, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        dirbox.Add(browsebtn, 0, wx.ALIGN_CENTER_VERTICAL)

        sizer.Add(dirbox, 0, wx.ALIGN_LEFT|wx.ALL, 5)

        self.movecompleted = wx.CheckBox(self, -1, self.utility.lang.get('movecompleted'))

        self.movedir = wx.TextCtrl(self, -1, "")
        movebrowsebtn = wx.Button(self, -1, "...", style = wx.BU_EXACTFIT)
        self.Bind(wx.EVT_BUTTON, self.onBrowseMoveDir, movebrowsebtn)

        movedirbox = wx.BoxSizer(wx.HORIZONTAL)
        movedirbox.Add(self.movecompleted, 0, wx.ALIGN_CENTER_VERTICAL)
        movedirbox.Add(self.movedir, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        movedirbox.Add(movebrowsebtn, 0, wx.ALIGN_CENTER_VERTICAL)

        sizer.Add(movedirbox, 0, wx.ALIGN_LEFT|wx.ALL, 5)
       
#        self.forcenewdir = wx.CheckBox(self, -1, self.utility.lang.get('forcenewdir'))
#        self.forcenewdir.SetToolTipString(self.utility.lang.get('forcenewdir_hint'))
#        
#        sizer.Add(self.forcenewdir, 0, wx.ALIGN_LEFT|wx.ALL, 5)

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

        self.dir.SetValue(Read('defaultfolder'))
        self.torrentbackup.SetValue(Read('removetorrent', "boolean"))
        self.defaultdir.SetValue(Read('setdefaultfolder', "boolean"))
        self.movecompleted.SetValue(Read('movecompleted', "boolean"))
        self.movedir.SetValue(Read('defaultmovedir'))
        
        diskfullthreshold = Read('diskfullthreshold', "int")
        if diskfullthreshold > 0:
            self.diskfullcheckbox.SetValue(True)
            self.diskfullthreshold.SetValue(diskfullthreshold)
#        self.forcenewdir.SetValue(Read('forcenewdir', "boolean"))
        
    def apply(self):
        self.utility.config.Write('removetorrent', self.torrentbackup.GetValue(), "boolean")

        self.utility.config.Write('setdefaultfolder', self.defaultdir.GetValue(), "boolean")
        self.utility.config.Write('defaultfolder', self.dir.GetValue())

        self.utility.config.Write('movecompleted', self.movecompleted.GetValue(), "boolean")
        self.utility.config.Write('defaultmovedir', self.movedir.GetValue())
        
        if self.diskfullcheckbox.GetValue():
            diskfullthreshold = self.diskfullthreshold.GetValue()
        else:
            diskfullthreshold = 0
        self.utility.config.Write('diskfullthreshold', diskfullthreshold)
                
#        self.utility.config.Write('forcenewdir', self.forcenewdir.GetValue(), "boolean")

    def onBrowseMoveDir(self, event = None):
        dlg = wx.DirDialog(self.utility.frame, 
                           self.utility.lang.get('choosemovedir'), 
                           style = wx.DD_DEFAULT_STYLE | wx.DD_NEW_DIR_BUTTON)
        if dlg.ShowModal() == wx.ID_OK:
            self.movedir.SetValue(dlg.GetPath())
        dlg.Destroy()
        
    def onBrowseDir(self, event = None):
        dlg = wx.DirDialog(self.utility.frame, 
                           self.utility.lang.get('choosedefaultdownloadfolder'), 
                           style = wx.DD_DEFAULT_STYLE | wx.DD_NEW_DIR_BUTTON)
        if dlg.ShowModal() == wx.ID_OK:
            self.dir.SetValue(dlg.GetPath())
        dlg.Destroy()


################################################################
#
# Class: SchedulerRulePanel
#
# Contains settings related to timeouts
#
################################################################
class SchedulerRulePanel(ABCOptionPanel):
    def __init__(self, parent, dialog):
        ABCOptionPanel.__init__(self, parent, dialog)
        sizer = self.sizer
        
        # GUI dialog for Global upload setting
        ########################################
        sizer.Add(wx.StaticText(self, -1, self.utility.lang.get('setrule')), 0, wx.ALL, 5)
        
        # Timeout for contacting tracker
        tracker_val  = ['oo', '5', '10', '15', '30', '45', '60', '120', '180'] #minute
        self.cb_tracker  = wx.ComboBox(self, -1, "", wx.Point(-1, -1), 
                                       wx.Size(65, -1), tracker_val, wx.CB_DROPDOWN|wx.CB_READONLY)
        tracker_box = wx.BoxSizer(wx.HORIZONTAL)
        tracker_box.Add(wx.StaticText(self, -1, self.utility.lang.get('timeout_tracker')), 0, wx.ALIGN_CENTER_VERTICAL)
        tracker_box.Add(self.cb_tracker, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        tracker_box.Add(wx.StaticText(self, -1, self.utility.lang.get('minute_long')), 0, wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(tracker_box, 0, wx.ALL, 5)

        # Timeout for downloading
        download_val = ['oo', '10', '20', '30', '60', '90', '120', '150', '180', '210', '240'] #minute
        self.cb_download = wx.ComboBox(self, -1, "", wx.Point(-1, -1), 
                                       wx.Size(65, -1), download_val, wx.CB_DROPDOWN|wx.CB_READONLY)
        download_box = wx.BoxSizer(wx.HORIZONTAL)
        download_box.Add(wx.StaticText(self, -1, self.utility.lang.get('timeout_download')), 0, wx.ALIGN_CENTER_VERTICAL)
        download_box.Add(self.cb_download, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        download_box.Add(wx.StaticText(self, -1, self.utility.lang.get('minute_long')), 0, wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(download_box, 0, wx.ALL, 5)

        # Timeout for seeding
        upload_val   = ['oo', '0.5', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12'] #hour
        self.cb_upload   = wx.ComboBox(self, -1, "", wx.Point(-1, -1), 
                                       wx.Size(65, -1), upload_val, wx.CB_DROPDOWN|wx.CB_READONLY)
        upload_box = wx.BoxSizer(wx.HORIZONTAL)
        upload_box.Add(wx.StaticText(self, -1, self.utility.lang.get('timeout_upload')), 0, wx.ALIGN_CENTER_VERTICAL)
        upload_box.Add(self.cb_upload, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        upload_box.Add(wx.StaticText(self, -1, self.utility.lang.get('hour_long')), 0, wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(upload_box, 0, wx.ALL, 5)

        self.initTasks()
    
    def loadValues(self, Read = None):
        if Read is None:
            Read = self.utility.config.Read
            
        self.cb_tracker.SetStringSelection(Read('timeouttracker'))
        self.cb_download.SetStringSelection(Read('timeoutdownload'))
        self.cb_upload.SetStringSelection(Read('timeoutupload'))
        
    def apply(self):
        # Set values for timeouts
        self.utility.config.Write('timeouttracker', self.cb_tracker.GetValue())
        self.utility.config.Write('timeoutdownload', self.cb_download.GetValue())
        self.utility.config.Write('timeoutupload', self.cb_upload.GetValue())


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
        
        self.maxupload = wx.SpinCtrl(self, size = wx.Size(60, -1))
        self.maxupload.SetRange(2, 100)
        
        maxuploadsbox = wx.BoxSizer(wx.HORIZONTAL)
        maxuploadsbox.Add(wx.StaticText(self, -1, self.utility.lang.get('maxuploads')), 0, wx.ALIGN_CENTER_VERTICAL)
        maxuploadsbox.Add(self.maxupload, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
        
        uploadsection.Add(maxuploadsbox, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

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
        
        # Prioritize Local
        self.prioritizelocal = wx.CheckBox(self, -1, self.utility.lang.get('prioritizelocal'))
        sizer.Add(self.prioritizelocal, 0, wx.ALL, 5)
    
        self.initTasks()

    def loadValues(self, Read = None):
        if Read is None:
            Read = self.utility.config.Read
        
        self.maxupload.SetValue(Read('maxupload', "int"))
        self.uploadrate.SetValue(Read('maxuploadrate', "int"))
        self.downloadrate.SetValue(Read('maxdownloadrate', "int"))
        self.seeduploadrate.SetValue(Read('maxseeduploadrate', "int"))
        self.prioritizelocal.SetValue(Read('prioritizelocal', "boolean"))
        
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

        self.utility.config.Write('prioritizelocal', self.prioritizelocal.GetValue(), "boolean")

        # Set new value to parameters
        ##############################
        self.utility.config.Write('maxupload', self.maxupload.GetValue())
        self.utility.config.Write('maxuploadrate', upload_rate)
        self.utility.config.Write('maxseeduploadrate', seedupload_rate)
        
        self.utility.config.Write('maxdownloadrate', download_rate)


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
# Class: ColorPanel
#
# Contains settings for what the colors for different torrent
# statuses should be.
#
################################################################
class ColorPanel(ABCOptionPanel):
    def __init__(self, parent, dialog):
        ABCOptionPanel.__init__(self, parent, dialog)
        sizer = self.sizer
        
        self.colors = ['color_startup', 
                       'color_disconnected', 
                       'color_noconnections', 
                       'color_noincoming', 
                       'color_nocomplete', 
                       'color_good' ]
        color_boxes = {}
        color_text = {}
        self.color_buttons = {}
        
        # Striped list options
        for color in self.colors:
            color_boxes[color] = wx.BoxSizer(wx.HORIZONTAL)

            self.color_buttons[color] = colourselect.ColourSelect(self, -1, "", size = (60, 20))       
            color_boxes[color].Add(self.color_buttons[color], 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)
        
            color_text[color] = wx.StaticText(self, -1, self.utility.lang.get(color))
            color_boxes[color].Add(color_text[color], 0, wx.ALIGN_CENTER_VERTICAL)
               
            sizer.Add(color_boxes[color], 0, wx.ALIGN_LEFT|wx.ALL, 5)

        self.initTasks()

    def loadValues(self, Read = None):
        if Read is None:
            Read = self.utility.config.Read
        
        for color in self.colors:
            self.color_buttons[color].SetValue(Read(color, "color"))
        
    def apply(self):
        overallchange = False
        
        for color in self.colors:
            color_value = self.color_buttons[color].GetColour()
            changed = self.utility.config.Write(color, color_value, "color")
            if changed:
                overallchange = True

        if overallchange:
            for ABCTorrentTemp in self.utility.torrents["all"]:
                ABCTorrentTemp.updateColor()


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
        self.maxconnections_choices = [self.utility.lang.get('nolimit'), '20', '30', '40', '60', '100', '200']
        self.maxconnections_data=wx.Choice(self, -1, wx.Point(-1, -1), wx.Size(-1, -1), self.maxconnections_choices)
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

        sizer.Add(datasizer, 0, wx.ALL, 5)
        
        # Set tooltips
        self.ip_data.SetToolTipString(self.utility.lang.get('iphint'))
        self.bind_data.SetToolTipString(self.utility.lang.get('bindhint'))
        self.minpeers_data.SetToolTipString(self.utility.lang.get('minpeershint'))
        self.maxconnections_data.SetToolTipString(self.utility.lang.get('maxconnectionhint'))
               
        self.initTasks()

    def loadValues(self, Read = None):
        if Read is None:
            Read = self.utility.config.Read
        
        self.ip_data.SetValue(Read('ip'))
        self.bind_data.SetValue(Read('bind'))
        
        self.minpeers_data.SetValue(Read('min_peers', "int"))
        
        setval = Read('max_connections', "int")
        if setval == 0:
            setval = self.utility.lang.get('nolimit')
        else:
            setval = str(setval)
        if not setval in self.maxconnections_choices:
            setval = self.maxconnections_choices[0]
        self.maxconnections_data.SetStringSelection(setval)
        
        upnp_val = self.utility.config.Read('upnp_nat_access', "int")
        selected = self.upnp_val2selected(upnp_val)
        self.upnp_data.SetStringSelection(self.upnp_choices[selected])

#        #self.ipv6bindsv4_data.SetSelection()
        
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
                upnp_val = 3
            else:
                upnp_val = 0
        return upnp_val
        

    def apply(self):
        #if self.ipv6.GetValue():
        #    self.utility.config.Write('ipv6') = "1"
        #else:
        #    self.utility.config.Write('ipv6') = "0"
        self.utility.config.Write('ipv6', "0")
        
                # Advanced Options
        self.utility.config.Write('ip', self.ip_data.GetValue())
        self.utility.config.Write('bind', self.bind_data.GetValue())
        
        minpeers = self.minpeers_data.GetValue()
        self.utility.config.Write('min_peers', minpeers)

        try:
            maxconnections = int(self.maxconnections_data.GetStringSelection())
            maxinitiate = min(2 * minpeers, maxconnections)
        except:       # if it ain't a number, it must be "no limit"
            maxconnections = 0
            maxinitiate = 2 * minpeers

        self.utility.config.Write('max_initiate', maxinitiate)
        self.utility.config.Write('max_connections', maxconnections)

        selected = self.upnp_choices.index(self.upnp_data.GetValue())
        upnp_val = self.selected2upnp_val(selected)
        self.utility.config.Write('upnp_nat_access',upnp_val)

        self.utility.config.Write('ipv6_binds_v4', "1")


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
        self.alloc_strings = {"normal": 0, "background": 1, "pre-allocate": 2, "sparse": 3}
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
        self.maxfilesopen_choices = ['50', '100', '200', self.utility.lang.get('nolimit')]
        self.maxfilesopen_data=wx.Choice(self, -1, wx.Point(-1, -1), wx.Size(-1, -1), self.maxfilesopen_choices)

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
                   
        self.buffer_write = wx.SpinCtrl(self, size = wx.Size(60, -1))
        self.buffer_write.SetRange(0, 999)
        
        self.buffer_write_enable = wx.CheckBox(self, -1, self.utility.lang.get('buffer_write'))

        buffer_write_box = wx.BoxSizer(wx.HORIZONTAL)
        buffer_write_box.Add(self.buffer_write_enable, 0, wx.ALIGN_CENTER_VERTICAL)
        buffer_write_box.Add(self.buffer_write, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
        buffer_write_box.Add(wx.StaticText(self, -1, self.utility.lang.get('mb')), 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
       
        buffer.Add(self.buffer_read_enable, 0, wx.ALL, 5)
        buffer.Add(buffer_write_box, 0, wx.ALL, 5)

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
        
        try:
            alloc_selection = self.alloc_strings[Read('alloc_type')]
        except:
            alloc_selection = 0
        self.alloctype_data.SetSelection(alloc_selection)
        
        self.allocrate_data.SetValue(Read('alloc_rate', "int"))
        
        if Read('lock_files', "int"):
            if Read('lock_while_reading', "int"):
                self.locking_data.SetSelection(2)
            else:
                self.locking_data.SetSelection(1)
        else:
            self.locking_data.SetSelection(0)
        
        if Read('double_check', "int"):
            if Read('triple_check', "int"):
                self.doublecheck_data.SetSelection(2)
            else:
                self.doublecheck_data.SetSelection(1)
        else:
            self.doublecheck_data.SetSelection(0)
        
        setval = Read('max_files_open', "int")
        if setval == 0:
            setval = self.utility.lang.get('nolimit')
        else:
            setval = str(setval)
        if not setval in self.maxfilesopen_choices:
            setval = self.maxfilesopen_choices[0]
        self.maxfilesopen_data.SetStringSelection(setval)
        
        self.buffer_read_enable.SetValue(Read('buffer_read', "boolean"))
        
        try:
            flushval = Read('auto_flush', "int")
        except:
            flushval = 0
        self.flush_data.SetValue(flushval)
        self.flush_data_enable.SetValue(flushval > 0)
        
        try:
            writeval = Read('buffer_write', "int")
        except:
            writeval = 0
        self.buffer_write.SetValue(writeval)
        self.buffer_write_enable.SetValue(writeval > 0)
                            
    def apply(self):
        truth = { True: "1", False: "0" }
        
        alloc_strings = ["normal", "background", "pre-allocate", "sparse"]
        
        self.utility.config.Write('alloc_type', alloc_strings[self.alloctype_data.GetSelection()])
        self.utility.config.Write('alloc_rate', int(self.allocrate_data.GetValue()))

        try:
            maxopen = int(self.maxfilesopen_data.GetStringSelection())
        except:       # if it ain't a number, it must be "no limit"
            maxopen = 0
        self.utility.config.Write('max_files_open', maxopen)

        self.utility.config.Write('lock_files', self.locking_data.GetSelection() >= 1, "boolean")
        self.utility.config.Write('lock_while_reading', self.locking_data.GetSelection() > 1, "boolean")

        self.utility.config.Write('double_check', self.doublecheck_data.GetSelection() >= 1, "boolean")
        self.utility.config.Write('triple_check', self.doublecheck_data.GetSelection() > 1, "boolean")
        
        self.utility.config.Write('buffer_read', self.buffer_read_enable.GetValue(), "boolean")
        
        if not self.buffer_write_enable.GetValue():
            writeval = 0
        else:
            writeval = self.buffer_write.GetValue()
        self.utility.config.Write('buffer_write', writeval)
        
        if not self.flush_data_enable.GetValue():
            flushval = 0
        else:
            flushval = self.flush_data.GetValue()
        self.utility.config.Write('auto_flush', flushval)




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

        self.rec_enable = wx.CheckBox(self, -1, self.utility.lang.get('enablerecommender'))
        sizer.Add(self.rec_enable, 0, wx.ALIGN_LEFT|wx.ALL, 5)
        sizer.Add(wx.StaticText(self, -1, self.utility.lang.get('restartabc')), 0, wx.ALIGN_CENTER_VERTICAL)

        self.dlhelp_enable = wx.CheckBox(self, -1, self.utility.lang.get('enabledlhelp'))
        sizer.Add(self.dlhelp_enable, 0, wx.ALIGN_LEFT|wx.ALL, 5)
        sizer.Add(wx.StaticText(self, -1, self.utility.lang.get('restartabc')), 0, wx.ALIGN_CENTER_VERTICAL)

        self.collect_enable = wx.CheckBox(self, -1, self.utility.lang.get('enabledlcollecting'))
        sizer.Add(self.collect_enable, 0, wx.ALIGN_LEFT|wx.ALL, 5)
        sizer.Add(wx.StaticText(self, -1, self.utility.lang.get('restartabc')), 0, wx.ALIGN_CENTER_VERTICAL)

        """
        name_box = wx.BoxSizer(wx.HORIZONTAL)
        self.myname = wx.TextCtrl(self, -1, "")
        name_box.Add(wx.StaticText(self, -1, self.utility.lang.get('myname')), 0, wx.ALIGN_CENTER_VERTICAL)
        name_box.Add(self.myname, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        sizer.Add(name_box, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        """

        # Show PermID
        mypermid = MyDBHandler().getMyPermid()
        pb64 = permid_for_user(mypermid)
        if True:
            # Make it copy-and-paste able
            permid_box = wx.BoxSizer(wx.HORIZONTAL)
            self.permidctrl = wx.TextCtrl(self, -1, pb64, size = (400, 30), style = wx.TE_READONLY)
            permid_box.Add(wx.StaticText(self, -1, self.utility.lang.get('mypermid')), 0, wx.ALIGN_CENTER_VERTICAL)
            permid_box.Add(self.permidctrl, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
            sizer.Add(permid_box, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        else:
            permid_txt = self.utility.lang.get('mypermid')+": "+pb64
            label = wx.StaticText(self, -1, self.permid_txt )
            sizer.Add( label, 1, wx.EXPAND|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
        
        self.myinfo = wx.Button(self, -1, self.utility.lang.get('myinfo') + "...")
        sizer.Add(self.myinfo, 0, wx.ALL, 5)
        self.Bind(wx.EVT_BUTTON, self.OnMyInfoWizard, self.myinfo)
        
        self.initTasks()
        
    def loadValues(self, Read = None):
        if Read is None:
            Read = self.utility.config.Read
        
        self.rec_enable.SetValue(Read('enablerecommender', "boolean"))
        self.dlhelp_enable.SetValue(Read('enabledlhelp', "boolean"))
        self.collect_enable.SetValue(Read('enabledlcollecting', "boolean"))

    def apply(self):       
        self.utility.config.Write('enablerecommender', self.rec_enable.GetValue(), "boolean")
        self.utility.config.Write('enabledlhelp', self.dlhelp_enable.GetValue(), "boolean")          
        self.utility.config.Write('enabledlcollecting', self.collect_enable.GetValue(), "boolean")          

    def OnMyInfoWizard(self, event = None):
        wizard = MyInfoWizard(self)
        wizard.RunWizard(wizard.getFirstPage())

    def WizardFinished(self,wizard):
        wizard.Destroy()



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

        playbackbox = wx.BoxSizer(wx.HORIZONTAL)
        feasible = return_feasible_playback_modes()
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
        sizer.Add(playbackbox, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        
        player_box = wx.BoxSizer(wx.HORIZONTAL)
        self.player = wx.TextCtrl(self, -1, "")
        player_box.Add(wx.StaticText(self, -1, self.utility.lang.get('videoplayer_default_path')), 0, wx.ALIGN_CENTER_VERTICAL)
        player_box.Add(self.player, 1, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        #browsebtn = wx.Button(self, -1, "...", style = wx.BU_EXACTFIT)
        browsebtn = wx.Button(self, -1, "...")
        self.Bind(wx.EVT_BUTTON, self.onBrowsePlayer, browsebtn)
        player_box.Add(browsebtn, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        sizer.Add(player_box, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT|wx.EXPAND, 5)

        analyser_box = wx.BoxSizer(wx.HORIZONTAL)
        self.analyser = wx.TextCtrl(self, -1, "")
        analyser_box.Add(wx.StaticText(self, -1, self.utility.lang.get('videoanalyserpath')), 0, wx.ALIGN_CENTER_VERTICAL)
        analyser_box.Add(self.analyser, 1, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        #browsebtn = wx.Button(self, -1, "...", style = wx.BU_EXACTFIT)
        browsebtn = wx.Button(self, -1, "...")
        self.Bind(wx.EVT_BUTTON, self.onBrowseAnalyser, browsebtn)
        analyser_box.Add(browsebtn, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        sizer.Add(analyser_box, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT|wx.EXPAND, 5)

        
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
        mode = self.playback_indices(value)
        self.utility.config.Write('videoplaybackmode',mode)

        for widget,mainmsg in [(self.player,self.utility.lang.get('videoplayernotfound')),(self.analyser,self.utility.lang.get('videoanalysernotfound'))]:
            qvalue = widget.GetValue()
            value = self.unquote_path(qvalue)
            if not os.access(value,os.F_OK):
                self.onError(mainmsg,value)
                return

        if DEBUG:
            print "abcoptions: VideoPanel: Writing videoplayerpath",value
        self.utility.config.Write('videoplayerpath',value)
        self.utility.config.Write('videoanalyserpath',value)


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
        self.onBrowse(self.utility.lang.get('choosevideoplayer'),self.player)
        
    def onBrowseAnalyser(self, event = None):
        self.onBrowse(self.utility.lang.get('choosevideoanalyser'),self.analyser)
        
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
        
        self.ratelimits = self.AppendItem(self.root, self.utility.lang.get('ratelimits'))
        self.seedingoptions = self.AppendItem(self.root, self.utility.lang.get('seedoptions'))
        self.queuesetting = self.AppendItem(self.root, self.utility.lang.get('queuesetting'))
        self.timeout = self.AppendItem(self.root, self.utility.lang.get('timeout'))
        
        self.network = self.AppendItem(self.root, self.utility.lang.get('networksetting'))
        
        self.advancednetwork = self.AppendItem(self.network, self.utility.lang.get('advanced'))
        
        self.disk = self.AppendItem(self.root, self.utility.lang.get('disksettings'))
        self.advanceddisk = self.AppendItem(self.disk, self.utility.lang.get('advanced'))

        self.display = self.AppendItem(self.root, self.utility.lang.get('displaysetting'))

        self.colors = self.AppendItem(self.display, self.utility.lang.get('torrentcolors'))
                
        self.misc = self.AppendItem(self.root, self.utility.lang.get('miscsetting'))

        self.tribler = self.AppendItem(self.root, self.utility.lang.get('triblersetting'))

        self.video = self.AppendItem(self.root, self.utility.lang.get('videosetting'))


        self.treeMap = {self.ratelimits : self.dialog.rateLimitPanel, 
                        self.seedingoptions : self.dialog.seedingOptionsPanel, 
                        self.queuesetting : self.dialog.queuePanel, 
                        self.timeout : self.dialog.schedulerRulePanel, 
                        self.network : self.dialog.networkPanel, 
                        self.misc : self.dialog.miscPanel,
                        self.tribler : self.dialog.triblerPanel,
                        self.video : self.dialog.videoPanel,
                        self.display : self.dialog.displayPanel, 
                        self.colors : self.dialog.colorPanel, 
                        self.disk : self.dialog.diskPanel }

        self.treeMap[self.advancednetwork] = self.dialog.advancedNetworkPanel
        self.treeMap[self.advanceddisk] = self.dialog.advancedDiskPanel
        
        self.Bind(wx.EVT_TREE_SEL_CHANGED, self.onSwitchPage)

        self.SetAutoLayout(True)
        self.Fit()

    def onSwitchPage(self, event = None):       
        if self.dialog.closing or event is None:
            return

        print "<mluc> event type:", event.GetEventType()
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


################################################################
#
# Class: ABCOptionDialog
#
# Creates a dialog that allows users to set various preferences
#
################################################################        
class ABCOptionDialog(wx.Dialog):
    def __init__(self, parent):
        self.utility = parent.utility

        style = wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
#        size = wx.Size(530, 420)
        
        size, split = self.getWindowSettings()
        
        wx.Dialog.__init__(self, parent, -1, self.utility.lang.get('abcpreference'), size = size, style = style)
                     
        self.splitter = wx.SplitterWindow(self, -1, style = wx.SP_NOBORDER | wx.SP_LIVE_UPDATE)

        self.rateLimitPanel = RateLimitPanel(self.splitter, self)
        self.seedingOptionsPanel = SeedingOptionsPanel(self.splitter, self)
        self.queuePanel = QueuePanel(self.splitter, self)

        self.schedulerRulePanel = SchedulerRulePanel(self.splitter, self)
        self.networkPanel = NetworkPanel(self.splitter, self)
        self.miscPanel = MiscPanel(self.splitter, self)
        self.triblerPanel = TriblerPanel(self.splitter, self)
        self.videoPanel = VideoPanel(self.splitter, self)
        self.displayPanel = DisplayPanel(self.splitter, self)
        self.colorPanel = ColorPanel(self.splitter, self)
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

        self.splitter.SplitVertically(self.tree, self.rateLimitPanel, split)
        self.rateLimitPanel.changed = True
        self.splitter.SetMinimumPaneSize(50)

        for key in self.tree.treeMap:
            panel = self.tree.treeMap[key]
            panel.Show(False)
        
        self.rateLimitPanel.Show(True)
        self.rateLimitPanel.Fit()
        
        self.SetSizer(outerbox)
#        self.Fit()
        
        self.closing = False
        
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
        
        self.utility.queue.changeABCParams()    #overwrite flag
                
        return True

    def onOK(self, event = None):
        if self.onApply():
            self.closing = True
            self.saveWindowSettings()
            
            self.EndModal(wx.ID_OK)
