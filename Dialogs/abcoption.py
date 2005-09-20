import sys
import wx
import os

from random import shuffle
from traceback import print_exc
from cStringIO import StringIO

from wx.lib import masked

from Utility.configreader import ConfigReader

class NetworkPanel(wx.Panel):
    def __init__(self, parent, dialog):
        wx.Panel.__init__(self, parent, -1)
        
        self.dialog = dialog
        self.utility = dialog.utility
        
        self.changed = False
        
        sizer = wx.BoxSizer(wx.VERTICAL)
               
        portsetting_title = wx.StaticBox(self,  -1,  self.utility.lang.get('portsetting'))
        portsetting = wx.StaticBoxSizer(portsetting_title, wx.VERTICAL)
               
        self.minport = self.utility.makeNumCtrl(self, self.utility.config.Read('minport'), max = 65536)
        minport_box = wx.BoxSizer(wx.HORIZONTAL)
        minport_box.Add(wx.StaticText(self, -1, self.utility.lang.get('minportnumber')), 0, wx.ALIGN_CENTER_VERTICAL)
        minport_box.Add(self.minport, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)

        self.maxport = self.utility.makeNumCtrl(self, self.utility.config.Read('maxport'), max = 65536)
        maxport_box = wx.BoxSizer(wx.HORIZONTAL)
        maxport_box.Add(wx.StaticText(self, -1, self.utility.lang.get('maxportnumber')), 0, wx.ALIGN_CENTER_VERTICAL)
        maxport_box.Add(self.maxport, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
       
        portsetting.Add(minport_box, 0, wx.ALL, 5)
        portsetting.Add(maxport_box, 0, wx.ALL, 5)

        self.randomport = wx.CheckBox(self, -1, self.utility.lang.get('randomport'))
        self.randomport.SetValue(self.utility.config.Read('randomport', "boolean"))
        portsetting.Add(self.randomport, 0, wx.ALIGN_LEFT|wx.ALL, 5)

        sizer.Add(portsetting, 0, wx.EXPAND|wx.ALL, 5)

        self.kickban = wx.CheckBox(self, -1, self.utility.lang.get('kickban'))
        self.kickban.SetValue(self.utility.config.Read('kickban', "boolean"))
        sizer.Add(self.kickban, 0, wx.ALIGN_LEFT|wx.ALL, 5)

        self.notsameip = wx.CheckBox(self, -1, self.utility.lang.get('security'))
        self.notsameip.SetValue(self.utility.config.Read('notsameip', "boolean"))
        sizer.Add(self.notsameip, 0, wx.ALIGN_LEFT|wx.ALL, 5)
        
        # Do or don't get scrape data
        ###################################################################
        self.scrape = wx.CheckBox(self, -1, self.utility.lang.get('scrape'))
        self.scrape.SetValue(self.utility.config.Read('scrape', "boolean"))
        sizer.Add(self.scrape, 0, wx.ALIGN_LEFT|wx.ALL, 5)
        self.scrape.SetToolTipString(self.utility.lang.get('scrape_hint'))

        ###################################################################        
        #self.ipv6 = wx.CheckBox(self, -1, "Initiate and receive connections via IPv6")
        #if self.utility.config.Read('ipv6') == "1":
        #    self.ipv6.SetValue(True)
        #else:
        #    self.ipv6.SetValue(False)
        ####################################################################

        self.SetSizerAndFit(sizer)
        
    def apply(self):
        minport = int(self.minport.GetValue())
        maxport = int(self.maxport.GetValue())
        if minport > 65535:
            minport = 65535
        if maxport > 65535:
            minport = 65535
        if minport > maxport:
            dlg = wx.MessageDialog(self.dialog, self.utility.lang.get('portrangewarning')  , self.utility.lang.get('error'), wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            return False

        minchanged = self.utility.config.Write('minport', minport)
        maxchanged = self.utility.config.Write('maxport', maxport)

        # Only need to update the port settings if they haven't changed
        if (minchanged or maxchanged):
            ports = range(minport, maxport + 1)
            for ABCTorrentTemp in self.utility.queue.activetorrents:
                port = ABCTorrentTemp.listen_port
                if (port is not None
                    and (port >= minport and port <= maxport)):
                    try:
                        ports.remove(ABCTorrentTemp.listen_port)
                    except:
                        pass
            if self.randomport.GetValue():
                # Randomly shuffle the range of ports
                shuffle(ports)
    
            self.utility.queue.availableports = ports

        self.utility.config.Write('kickban', self.kickban.GetValue(), "boolean")
        self.utility.config.Write('randomport', self.randomport.GetValue(), "boolean")
        self.utility.config.Write('notsameip', self.notsameip.GetValue(), "boolean")
        self.utility.config.Write('scrape', self.scrape.GetValue(), "boolean")
        
class QueuePanel(wx.Panel):
    def __init__(self, parent, dialog):
        wx.Panel.__init__(self, parent, -1)
        
        self.dialog = dialog
        self.utility = dialog.utility
        
        self.changed = False
        
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.numsimtext = wx.SpinCtrl(self, size = wx.Size(60, -1))
        self.numsimtext.SetRange(0, 1000)
        self.numsimtext.SetValue(self.utility.config.Read('numsimdownload', "int"))

        numsim = wx.BoxSizer(wx.HORIZONTAL)
        numsim.Add(wx.StaticText(self, -1, self.utility.lang.get('maxnumsimul')), 0, wx.ALIGN_CENTER_VERTICAL)
        numsim.Add(self.numsimtext, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
        
        sizer.Add(numsim, 0, wx.ALL, 5)

        trig_finish_values = [ self.utility.lang.get('after_downloading') , self.utility.lang.get('after_seeding') ]
        if self.utility.config.Read('trigwhenfinishseed') == "1":
            trig_default_value = self.utility.lang.get('after_seeding')
        else:
            trig_default_value = self.utility.lang.get('after_downloading')
        self.trig_finish_seed  = wx.ComboBox(self, -1, trig_default_value, wx.Point(-1, -1), wx.Size(-1, -1), trig_finish_values, wx.CB_DROPDOWN|wx.CB_READONLY)

        trigger_box = wx.BoxSizer(wx.HORIZONTAL)
        trigger_box.Add(wx.StaticText(self, -1, self.utility.lang.get('trignexttorrent')), 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)
        trigger_box.Add(self.trig_finish_seed, 0, wx.ALIGN_CENTER_VERTICAL)

        sizer.Add(trigger_box, 0, wx.ALL, 5)

        priorities = [ self.utility.lang.get('highest'),
                       self.utility.lang.get('high'),
                       self.utility.lang.get('normal'),
                       self.utility.lang.get('low'),
                       self.utility.lang.get('lowest') ]
        
        currentprio = self.utility.config.Read('defaultpriority', "int")
        if currentprio >= len(priorities):
            currentprio = len(priorities) - 1
        defaultprio = priorities[currentprio]
        self.defaultpriority = wx.ComboBox(self, -1, defaultprio, wx.Point(-1,-1), wx.Size(-1,-1), priorities, wx.CB_DROPDOWN|wx.CB_READONLY)

        prio_box = wx.BoxSizer(wx.HORIZONTAL)
        prio_box.Add(wx.StaticText(self, -1, self.utility.lang.get('defaultpriority')), 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)
        prio_box.Add(self.defaultpriority, 0, wx.ALIGN_CENTER_VERTICAL)       
        sizer.Add(prio_box, 0, wx.ALL, 5)

        self.failbehaviors = [ self.utility.lang.get('stop'), self.utility.lang.get('queue') ]
        defaultfail  = self.failbehaviors[self.utility.config.Read('failbehavior', "int")]
        self.failbehavior = wx.ComboBox(self, -1, defaultfail, wx.Point(-1,-1), wx.Size(-1,-1), self.failbehaviors, wx.CB_DROPDOWN|wx.CB_READONLY)

        fail_box = wx.BoxSizer(wx.HORIZONTAL)
        fail_box.Add(wx.StaticText(self, -1, self.utility.lang.get('failbehavior1')), 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)
        fail_box.Add(self.failbehavior, 0, wx.ALIGN_CENTER_VERTICAL)
        fail_box.Add(wx.StaticText(self, -1, self.utility.lang.get('failbehavior2')), 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
        sizer.Add(fail_box, 0, wx.ALL, 5)
                
        self.fastresume = wx.CheckBox(self, -1, self.utility.lang.get('fastresume'))
        self.fastresume.SetValue(self.utility.config.Read('fastresume', "boolean"))
        self.fastresume.SetToolTipString(self.utility.lang.get('fastresume_hint'))
        sizer.Add(self.fastresume, 0, wx.ALL, 5)

        self.SetSizerAndFit(sizer)
        
    def apply(self):            
        self.utility.config.Write('fastresume', self.fastresume.GetValue(), "boolean")

        priorities = [ self.utility.lang.get('highest'),
                       self.utility.lang.get('high'),
                       self.utility.lang.get('normal'),
                       self.utility.lang.get('low'),
                       self.utility.lang.get('lowest') ]
        selected = priorities.index(self.defaultpriority.GetValue())
        self.utility.config.Write('defaultpriority', selected)

        self.utility.config.Write('failbehavior', self.failbehaviors.index(self.failbehavior.GetValue()))

        self.utility.config.Write('numsimdownload', self.numsimtext.GetValue())

        if self.trig_finish_seed.GetValue() == self.utility.lang.get('after_seeding'):
            self.utility.config.Write('trigwhenfinishseed', "1")
        else:
            self.utility.config.Write('trigwhenfinishseed', "0")
        self.utility.queue.UpdateRunningTorrentCounters()

class MiscPanel(wx.Panel):
    def __init__(self, parent, dialog):
        wx.Panel.__init__(self, parent, -1)
        
        self.dialog = dialog
        self.utility = dialog.utility
        
        self.changed = False

        sizer = wx.BoxSizer(wx.VERTICAL)
        
        trayoptions = [self.utility.lang.get('showtray_never'),
                            self.utility.lang.get('showtray_min'),
                            self.utility.lang.get('showtray_always')]
        self.mintray = wx.RadioBox(self,
                                    -1,
                                    self.utility.lang.get('showtray'),
                                    wx.DefaultPosition,
                                    wx.DefaultSize,
                                    trayoptions,
                                    3,
                                    wx.RA_SPECIFY_COLS)
        mintray = self.utility.config.Read('mintray', "int")
        if mintray >= len(trayoptions):
            mintray = len(trayoptions) - 1
        self.mintray.SetSelection(mintray)
        sizer.Add(self.mintray, 0, wx.ALIGN_LEFT|wx.ALL, 5)
        
        self.stripedlist = wx.CheckBox(self, -1, self.utility.lang.get('stripedlist'))
        self.stripedlist.SetValue(self.utility.config.Read('stripedlist', "boolean"))
        sizer.Add(self.stripedlist, 0, wx.ALIGN_LEFT|wx.ALL, 5)
        
        self.confirmonclose = wx.CheckBox(self, -1, self.utility.lang.get('confirmonexit'))
        self.confirmonclose.SetValue(self.utility.config.Read('confirmonclose', "boolean"))
        sizer.Add(self.confirmonclose, 0, wx.ALIGN_LEFT|wx.ALL, 5)

        # Registry association (only makes sense under windows)
        if (sys.platform == 'win32'):
            self.associate = wx.CheckBox(self, -1, self.utility.lang.get('associate'))
            self.associate.SetValue(self.utility.config.Read('associate', "boolean"))
            sizer.Add(self.associate, 0, wx.ALIGN_LEFT|wx.ALL, 5)
        
        # Languages option
        if self.utility.languages == {}:
            self.getLanguages()
        self.language_names = []
        self.language_filenames = []
        for item in self.utility.languages:
            self.language_names.append(item)
            self.language_filenames.append(self.utility.languages[item])

        index = self.language_filenames.index(self.utility.config.Read('language_file'))
        if (len(self.language_names) == 0):
            # Should never get here -- this means there are no valid language files found!
            sys.stderr.write("\nNO LANGUAGE FILES FOUND!  Please add a valid language file\n")
            defaultlang = ""
        elif (index > -1):
            defaultlang = self.language_names[index]
        
        self.language_choice = wx.ComboBox(self, -1, defaultlang, wx.Point(-1,-1), wx.Size(-1,-1), self.language_names, wx.CB_DROPDOWN|wx.CB_READONLY)
        
        lang_box = wx.BoxSizer(wx.HORIZONTAL)
        lang_box.Add(wx.StaticText(self, -1, self.utility.lang.get('choose_language')), 0, wx.ALIGN_CENTER_VERTICAL)
        lang_box.Add(self.language_choice, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        lang_box.Add(wx.StaticText(self, -1, self.utility.lang.get('restartabc')), 0, wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(lang_box, 0, wx.ALL, 5)

        self.SetSizerAndFit(sizer)
        
    def apply(self):       
        self.utility.config.Write('mintray', str(self.mintray.GetSelection()))
        self.utility.frame.tbicon.updateIcon()

        langname_index = self.language_names.index(self.language_choice.GetValue())
        self.utility.config.Write('language_file', self.language_filenames[langname_index])

        self.utility.config.Write('confirmonclose', self.confirmonclose.GetValue(), "boolean")
        
        self.utility.config.Write('associate', self.associate.GetValue(), "boolean")
        self.utility.regchecker.updateRegistry(self.associate.GetValue())
          
        changed = self.utility.config.Write('stripedlist', self.stripedlist.GetValue(), "boolean")
        if changed:
            for ABCTorrentTemp in self.utility.queue.proctab:
                ABCTorrentTemp.updateColor()

    def getLanguages(self):
        langpath = os.path.join(self.utility.getPath(), "lang")
        
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

            config = ConfigReader(filepath, "ABC/language")
            if config.Exists('languagename'):
                self.utility.languages[config.Read('languagename')] = filename

class DiskPanel(wx.Panel):
    def __init__(self, parent, dialog):
        wx.Panel.__init__(self, parent, -1)
        
        self.dialog = dialog
        self.utility = dialog.utility
        
        self.changed = False

        sizer = wx.BoxSizer(wx.VERTICAL)
                      
        self.torrentbackup = wx.CheckBox(self, -1, self.utility.lang.get('removebackuptorrent'))
        self.torrentbackup.SetValue(self.utility.config.Read('removetorrent') == "1")
        sizer.Add(self.torrentbackup, 0, wx.ALIGN_LEFT|wx.ALL, 5)
           
        self.defaultdir = wx.CheckBox(self, -1, self.utility.lang.get('setdefaultfolder'))
        self.defaultdir.SetValue(self.utility.config.Read('setdefaultfolder') == "1")

        self.dir = wx.TextCtrl(self, -1, self.utility.config.Read('defaultfolder'))
        browsebtn = wx.Button(self, -1, "...", wx.Point(-1,-1), wx.Size(20, -1))
        self.Bind(wx.EVT_BUTTON, self.onBrowseDir, browsebtn)

        dirbox = wx.BoxSizer(wx.HORIZONTAL)
        dirbox.Add(self.defaultdir, 0, wx.ALIGN_CENTER_VERTICAL)
        dirbox.Add(self.dir, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        dirbox.Add(browsebtn, 0, wx.ALIGN_CENTER_VERTICAL)

        sizer.Add(dirbox, 0, wx.ALIGN_LEFT|wx.ALL, 5)

        self.movecompleted = wx.CheckBox(self, -1, self.utility.lang.get('movecompleted'))
        self.movecompleted.SetValue(self.utility.config.Read('movecompleted', "boolean"))

        self.movedir = wx.TextCtrl(self, -1, self.utility.config.Read('defaultmovedir'))
        movebrowsebtn = wx.Button(self, -1, "...", wx.Point(-1,-1), wx.Size(20, -1))
        self.Bind(wx.EVT_BUTTON, self.onBrowseMoveDir, movebrowsebtn)

        movedirbox = wx.BoxSizer(wx.HORIZONTAL)
        movedirbox.Add(self.movecompleted, 0, wx.ALIGN_CENTER_VERTICAL)
        movedirbox.Add(self.movedir, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        movedirbox.Add(movebrowsebtn, 0, wx.ALIGN_CENTER_VERTICAL)

        sizer.Add(movedirbox, 0, wx.ALIGN_LEFT|wx.ALL, 5)
        
        self.forcenewdir = wx.CheckBox(self, -1, self.utility.lang.get('forcenewdir'))
        self.forcenewdir.SetValue(self.utility.config.Read('forcenewdir', "boolean"))
        self.forcenewdir.SetToolTipString(self.utility.lang.get('forcenewdir_hint'))
        
        sizer.Add(self.forcenewdir, 0, wx.ALIGN_LEFT|wx.ALL, 5)

        self.SetSizerAndFit(sizer)
        
    def apply(self):
        self.utility.config.Write('removetorrent', self.torrentbackup.GetValue(), "boolean")

        self.utility.config.Write('setdefaultfolder', self.defaultdir.GetValue(), "boolean")
        self.utility.config.Write('defaultfolder', self.dir.GetValue())

        self.utility.config.Write('movecompleted', self.movecompleted.GetValue(), "boolean")
        self.utility.config.Write('defaultmovedir', self.movedir.GetValue())
        
        self.utility.config.Write('forcenewdir', self.forcenewdir.GetValue(), "boolean")

    def onBrowseMoveDir(self, event):
        foldername = wx.DirDialog(self.utility.frame, self.utility.lang.get('choosemovedir'), 
                                 style = wx.DD_DEFAULT_STYLE | wx.DD_NEW_DIR_BUTTON)
        if foldername.ShowModal() == wx.ID_OK:
            self.movedir.SetValue(foldername.GetPath())
        foldername.Destroy()
        
    def onBrowseDir(self, event):
        foldername = wx.DirDialog(self.utility.frame, self.utility.lang.get('choosedefaultdownloadfolder'), 
                                 style = wx.DD_DEFAULT_STYLE | wx.DD_NEW_DIR_BUTTON)
        if foldername.ShowModal() == wx.ID_OK:
            self.dir.SetValue(foldername.GetPath())
        foldername.Destroy()

class SchedulerRulePanel(wx.Panel):
    def __init__(self, parent, dialog):
        wx.Panel.__init__(self, parent, -1)
        
        self.dialog = dialog
        self.utility = dialog.utility
        
        self.changed = False
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # GUI dialog for Global upload setting
        ########################################
        sizer.Add(wx.StaticText(self, -1, self.utility.lang.get('setrule')), 0, wx.ALL, 5)
        
        # Timeout for contacting tracker
        tracker_val  = ['oo', '5', '10', '15', '30', '45', '60', '120', '180'] #minute
        timeout_tracker  = self.utility.config.Read('timeouttracker')
        self.cb_tracker  = wx.ComboBox(self, -1, timeout_tracker, wx.Point(-1, -1),  
                                       wx.Size(48, -1), tracker_val, wx.CB_DROPDOWN|wx.CB_READONLY)
        tracker_box = wx.BoxSizer(wx.HORIZONTAL)
        tracker_box.Add(wx.StaticText(self, -1, self.utility.lang.get('timeout_tracker')), 0, wx.ALIGN_CENTER_VERTICAL)
        tracker_box.Add(self.cb_tracker, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        tracker_box.Add(wx.StaticText(self, -1, self.utility.lang.get('minute_long')), 0, wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(tracker_box, 0, wx.ALL, 5)

        # Timeout for downloading
        download_val = ['oo', '10', '20', '30', '60', '90', '120', '150', '180', '210', '240'] #minute
        timeout_download = self.utility.config.Read('timeoutdownload')
        self.cb_download = wx.ComboBox(self, -1, timeout_download, wx.Point(-1, -1),
                                       wx.Size(48, -1), download_val, wx.CB_DROPDOWN|wx.CB_READONLY)
        download_box = wx.BoxSizer(wx.HORIZONTAL)
        download_box.Add(wx.StaticText(self, -1, self.utility.lang.get('timeout_download')), 0, wx.ALIGN_CENTER_VERTICAL)
        download_box.Add(self.cb_download, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        download_box.Add(wx.StaticText(self, -1, self.utility.lang.get('minute_long')), 0, wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(download_box, 0, wx.ALL, 5)

        # Timeout for seeding
        timeout_upload   = self.utility.config.Read('timeoutupload')
        upload_val   = ['oo', '0.5', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12'] #hour
        self.cb_upload   = wx.ComboBox(self, -1, timeout_upload, wx.Point(-1, -1),
                                       wx.Size(48, -1), upload_val, wx.CB_DROPDOWN|wx.CB_READONLY)
        upload_box = wx.BoxSizer(wx.HORIZONTAL)
        upload_box.Add(wx.StaticText(self, -1, self.utility.lang.get('timeout_upload')), 0, wx.ALIGN_CENTER_VERTICAL)
        upload_box.Add(self.cb_upload, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        upload_box.Add(wx.StaticText(self, -1, self.utility.lang.get('hour_long')), 0, wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(upload_box, 0, wx.ALL, 5)
              
        self.SetSizerAndFit(sizer)
        
    def apply(self):
        # Set values for timeouts
        self.utility.config.Write('timeouttracker', self.cb_tracker.GetValue())
        self.utility.config.Write('timeoutdownload', self.cb_download.GetValue())
        self.utility.config.Write('timeoutupload', self.cb_upload.GetValue())

class URMPanel(wx.Panel):
    def __init__(self, parent, dialog):
        wx.Panel.__init__(self, parent, -1)
        
        self.dialog = dialog
        self.utility = dialog.utility

        self.changed = False
        
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.urm = wx.CheckBox(self, -1, self.utility.lang.get('urm'))
        if self.utility.config.Read('urm') == "1":
            self.urm.SetValue(True)
        else:
            self.urm.SetValue(False)
        sizer.Add(self.urm, 0, wx.ALL, 5)

        self.urmmaxtorrenttext = wx.SpinCtrl(self, size = wx.Size(60, -1))
        self.urmmaxtorrenttext.SetRange(0, 1000)
        self.urmmaxtorrenttext.SetValue(self.utility.config.Read('urmmaxtorrent', "int"))

        urmmaxtorrentbox = wx.BoxSizer(wx.HORIZONTAL)
        urmmaxtorrentbox.Add(wx.StaticText(self, -1, self.utility.lang.get('urmmaxtorrent')), 0, wx.ALIGN_CENTER_VERTICAL)
        urmmaxtorrentbox.Add(self.urmmaxtorrenttext, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        urmmaxtorrentbox.Add(wx.StaticText(self, -1, self.utility.lang.get('torrents')), 0, wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(urmmaxtorrentbox, 0, wx.ALL, 5)

        self.urmupthresholdtext = self.utility.makeNumCtrl(self, self.utility.config.Read('urmupthreshold'), integerWidth = 4)
        urmupthresholdbox = wx.BoxSizer(wx.HORIZONTAL)
        urmupthresholdbox.Add(wx.StaticText(self, -1, self.utility.lang.get('urmupthreshold')), 0, wx.ALIGN_CENTER_VERTICAL)
        urmupthresholdbox.Add(self.urmupthresholdtext, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        urmupthresholdbox.Add(wx.StaticText(self, -1, self.utility.lang.get('KB') + "/" + self.utility.lang.get('l_second')), 0, wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(urmupthresholdbox, 0, wx.ALL, 5)
        
        self.urmdelaytext = self.utility.makeNumCtrl(self, self.utility.config.Read('urmdelay'), integerWidth = 4, min = 1)
        urmdelaybox = wx.BoxSizer(wx.HORIZONTAL)
        urmdelaybox.Add(wx.StaticText(self, -1, self.utility.lang.get('urmdelaya')), 0, wx.ALIGN_CENTER_VERTICAL)
        urmdelaybox.Add(self.urmdelaytext, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        urmdelaybox.Add(wx.StaticText(self, -1, self.utility.lang.get('l_second')), 0, wx.ALIGN_CENTER_VERTICAL)
        urmdelaybox.Add(wx.StaticText(self, -1, self.utility.lang.get('urmdelayb')), 0, wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(urmdelaybox, 0, wx.ALL, 5)
        
        self.urmlowpriority = wx.CheckBox(self, -1, self.utility.lang.get('urmlowpriority'))
        self.urmlowpriority.SetValue(self.utility.config.Read('urmlowpriority', "boolean"))
        sizer.Add(self.urmlowpriority, 0, wx.ALL, 5)
        
#        self.dynmaxuprate = wx.CheckBox(self, -1, self.utility.lang.get('dynmaxuprate'))
#        self.dynmaxuprate.SetValue(self.utility.config.Read('dynmaxuprate') == "1")
#        sizer.Add(self.dynmaxuprate, 0, wx.ALL, 5)

#        self.upfromdownAtext = self.utility.makeNumCtrl(self, self.utility.config.Read('upfromdownA'), integerWidth = 3, fractionWidth = 1, size = (40, -1))
#        self.upfromdownBtext = self.utility.makeNumCtrl(self, self.utility.config.Read('upfromdownB'), integerWidth = 3, fractionWidth = 1, size = (40, -1))
#        self.upfromdownCtext = self.utility.makeNumCtrl(self, self.utility.config.Read('upfromdownC'), integerWidth = 3, fractionWidth = 1, size = (40, -1))
#        self.upfromdownDtext = self.utility.makeNumCtrl(self, self.utility.config.Read('upfromdownD'), integerWidth = 3, fractionWidth = 1, size = (40, -1))
#
#        sizer.Add(wx.StaticText(self, -1, self.utility.lang.get('dynrate')), 0, wx.ALL, 5)
#
#        abbox = wx.BoxSizer(wx.HORIZONTAL)
#        
#        abbox.Add(wx.StaticText(self, -1, self.utility.lang.get('downcalc_left')), 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
#               
#        blackpanel1 = wx.Panel(self, -1, size = (-1, 1))
#        blackpanel1.SetBackgroundColour(wx.Colour(0, 0, 0))
#       
#        abbox_bottom = wx.BoxSizer(wx.HORIZONTAL)
#        abbox_bottom.Add(self.upfromdownAtext, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
#        abbox_bottom.Add(wx.StaticText(self, -1, self.utility.lang.get('downcalc_bottom')), 0, wx.ALIGN_CENTER_VERTICAL)
#        abbox_bottom.Add(self.upfromdownBtext, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
#
#        abbox_right = wx.BoxSizer(wx.VERTICAL)                      
#        abbox_right.Add(wx.StaticText(self, -1, self.utility.lang.get('downcalc_top')), 0, wx.ALIGN_CENTER)
#        abbox_right.Add(blackpanel1, 0, wx.EXPAND|wx.ALIGN_CENTER|wx.TOP|wx.BOTTOM, 5)
#        abbox_right.Add(abbox_bottom)
#        
#        abbox.Add(abbox_right, 0, wx.ALL, 5)
#        
#        bcbox = wx.BoxSizer(wx.HORIZONTAL)
#
#        bcbox.Add(wx.StaticText(self, -1, self.utility.lang.get('connectcalc_left')), 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
#
#        blackpanel2 = wx.Panel(self, -1, size = (-1, 1))
#        blackpanel2.SetBackgroundColour(wx.Colour(0, 0, 0))
#               
#        bcbox_bottom = wx.BoxSizer(wx.HORIZONTAL)
#        bcbox_bottom.Add(self.upfromdownCtext, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
#        bcbox_bottom.Add(wx.StaticText(self, -1, self.utility.lang.get('connectcalc_bottom')), 0, wx.ALIGN_CENTER)
#        bcbox_bottom.Add(self.upfromdownDtext, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
#        
#        bcbox_right = wx.BoxSizer(wx.VERTICAL)
#        bcbox_right.Add(wx.StaticText(self, -1, self.utility.lang.get('connectcalc_top')), 0, wx.ALIGN_CENTER)
#        bcbox_right.Add(blackpanel2, 0, wx.EXPAND|wx.ALIGN_CENTER|wx.TOP|wx.BOTTOM, 5)
#        bcbox_right.Add(bcbox_bottom)
#        
#        bcbox.Add(bcbox_right, 0, wx.ALL, 5)
#
#        sizer.Add(abbox, 0, wx.ALL, 5)
#        sizer.Add(bcbox, 0, wx.ALL, 5)

        self.SetSizerAndFit(sizer)
        
    def apply(self):
        urmupth = int(self.urmupthresholdtext.GetValue())

        urmdel = int(self.urmdelaytext.GetValue())
        # Check if urmdelay >= 1 s
        if urmdel < 1:
            urmdel = 1

#        urmufdA = float(self.upfromdownAtext.GetValue())
#        urmufdB = float(self.upfromdownBtext.GetValue())
#        urmufdC = float(self.upfromdownCtext.GetValue())
#        urmufdD = float(self.upfromdownDtext.GetValue())

        self.utility.config.Write('urmlowpriority', self.urmlowpriority.GetValue(), "boolean")

#        if self.dynmaxuprate.GetValue():
#            if self.utility.config.Read('dynmaxuprate') == "0":
#                # Store the current static max up rate into the list that is used to calculate the mean dyn upload rate
#                # This will provide a smooth transition in time from the static value to the dynamic value
#                # That's better than leaving old erroneous values in the mean list, or to store null values into it.
#                if self.utility.queue.counters['downloading']:
#                    # Static overall maximum up rate when downloading
#                    staticuprate = self.utility.config.Read('maxuploadrate', "float")
#                else:
#                    # Static overall maximum up rate when seeding
#                    staticuprate = self.utility.config.Read('maxseeduploadrate', "float")
#                for i in range(5):
#                    self.utility.queue.pastdynmaxuprate[i] = staticuprate
#                self.utility.queue.dynmaxuprate = staticuprate            
#            self.utility.config.Write('dynmaxuprate', "1")
#        else:
#            self.utility.config.Write('dynmaxuprate', "0")

        self.utility.config.Write('urmupthreshold', str(urmupth))
        self.utility.config.Write('urmdelay', str(urmdel))
#        self.utility.config.Write('upfromdownA', str(urmufdA))
#        self.utility.config.Write('upfromdownB', str(urmufdB))
#        self.utility.config.Write('upfromdownC', str(urmufdC))
#        self.utility.config.Write('upfromdownD', str(urmufdD))
        
        self.utility.config.Write('urmmaxtorrent', str(self.urmmaxtorrenttext.GetValue()))
        
        self.utility.config.Write('urm', self.urm.GetValue(), "boolean")

class RateLimitPanel(wx.Panel):
    def __init__(self, parent, dialog):
        wx.Panel.__init__(self, parent, -1)

        self.dialog = dialog
        self.utility = dialog.utility

        self.changed = False
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # GUI dialog for Global upload setting
        ########################################
        loc_maxupload           = self.utility.config.Read('maxupload')

        # Upload settings
        ########################################
       
        uploadsection_title = wx.StaticBox(self,  -1,  self.utility.lang.get('uploadsetting'))
        uploadsection = wx.StaticBoxSizer(uploadsection_title, wx.VERTICAL)
        
        self.maxupload = wx.SpinCtrl(self, size = wx.Size(60, -1))
        self.maxupload.SetRange(2, 100)
        self.maxupload.SetValue(int(loc_maxupload))
        
        maxuploadsbox = wx.BoxSizer(wx.HORIZONTAL)
        maxuploadsbox.Add(wx.StaticText(self, -1,  self.utility.lang.get('maxuploads')), 0, wx.ALIGN_CENTER_VERTICAL)
        maxuploadsbox.Add(self.maxupload, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
        
        uploadsection.Add(maxuploadsbox, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        maxoverall_down_label = wx.BoxSizer(wx.VERTICAL)
        maxoverall_down_label.Add(wx.StaticText(self, -1, self.utility.lang.get('maxoveralluploadrate')), 0, wx.ALIGN_CENTER_VERTICAL)
        maxoverall_down_label.Add(wx.StaticText(self, -1, self.utility.lang.get('whendownload')), 0, wx.ALIGN_CENTER_VERTICAL)

        self.uploadrate = self.utility.makeNumCtrl(self, self.utility.config.Read('maxuploadrate'), integerWidth = 4)
        self.uploadrate.SetToolTipString(self.utility.lang.get('global_uprate_hint'))

        maxoverall_down = wx.BoxSizer(wx.HORIZONTAL)
        maxoverall_down.Add(maxoverall_down_label, 0, wx.ALIGN_CENTER_VERTICAL)
        maxoverall_down.Add(self.uploadrate, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
        maxoverall_down.Add(wx.StaticText(self, -1, self.utility.lang.get('KB') + "/" + self.utility.lang.get('l_second')), 0, wx.ALIGN_CENTER_VERTICAL)
        
        uploadsection.Add(maxoverall_down, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
        
        maxoverall_nodown_label = wx.BoxSizer(wx.VERTICAL)
        maxoverall_nodown_label.Add(wx.StaticText(self, -1, self.utility.lang.get('maxoveralluploadrate')), 0, wx.ALIGN_CENTER_VERTICAL)
        maxoverall_nodown_label.Add(wx.StaticText(self, -1, self.utility.lang.get('whennodownload')), 0, wx.ALIGN_CENTER_VERTICAL)

        self.seeduploadrate = self.utility.makeNumCtrl(self, self.utility.config.Read('maxseeduploadrate'), integerWidth = 4)
        self.seeduploadrate.SetToolTipString(self.utility.lang.get('global_uprate_hint'))

        maxoverall_nodown = wx.BoxSizer(wx.HORIZONTAL)
        maxoverall_nodown.Add(maxoverall_nodown_label, 0, wx.ALIGN_CENTER_VERTICAL)
        maxoverall_nodown.Add(self.seeduploadrate, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
        maxoverall_nodown.Add(wx.StaticText(self, -1, self.utility.lang.get('KB') + "/" + self.utility.lang.get('l_second')), 0, wx.ALIGN_CENTER_VERTICAL)

        uploadsection.Add(maxoverall_nodown, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)       

        uploadsection.Add(wx.StaticText(self, -1,  self.utility.lang.get('zeroisunlimited')), 0, wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_RIGHT|wx.ALL, 5)

        sizer.Add( uploadsection, 0, wx.EXPAND|wx.ALL, 5)

        # Download Section
        downloadsection_title = wx.StaticBox(self,  -1,  self.utility.lang.get('downloadsetting'))
        downloadsection = wx.StaticBoxSizer(downloadsection_title, wx.VERTICAL)

        self.downloadrate = self.utility.makeNumCtrl(self, self.utility.config.Read('maxdownloadrate'), integerWidth = 4)

        maxdownoverall_down = wx.BoxSizer(wx.HORIZONTAL)
        maxdownoverall_down.Add(wx.StaticText(self, -1, self.utility.lang.get('maxoveralldownloadrate')), 0, wx.ALIGN_CENTER_VERTICAL)
        maxdownoverall_down.Add(self.downloadrate, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
        maxdownoverall_down.Add(wx.StaticText(self, -1, self.utility.lang.get('KB') + "/" + self.utility.lang.get('l_second')), 0, wx.ALIGN_CENTER_VERTICAL)
        
        downloadsection.Add(maxdownoverall_down, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        downloadsection.Add(wx.StaticText(self, -1,  self.utility.lang.get('zeroisunlimited')), 0, wx.ALIGN_CENTER_VERTICAL|wx.ALIGN_RIGHT|wx.ALL, 5)        

        sizer.Add( downloadsection, 0, wx.EXPAND|wx.ALL, 5)
        
        # Prioritize Local
        self.prioritizelocal = wx.CheckBox(self, -1, self.utility.lang.get('prioritizelocal'))
        self.prioritizelocal.SetValue(self.utility.config.Read('prioritizelocal') == "1")
        sizer.Add(self.prioritizelocal, 0, wx.ALL, 5)
    
        self.SetSizerAndFit( sizer )
        
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
        self.utility.config.Write('maxupload', str(self.maxupload.GetValue()))
        self.utility.config.Write('maxuploadrate', str(upload_rate))
        self.utility.config.Write('maxseeduploadrate', str(seedupload_rate))
        
        self.utility.config.Write('maxdownloadrate', str(download_rate))

class SeedingOptionsPanel(wx.Panel):
    def __init__(self, parent, dialog):
        wx.Panel.__init__(self, parent, -1)

        self.dialog = dialog
        self.utility = dialog.utility

        self.changed = False
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # GUI dialog for Global upload setting
        ########################################
        loc_uploadopt           = self.utility.config.Read('uploadoption')
        loc_uploadtimeh         = self.utility.config.Read('uploadtimeh')
        loc_uploadtimem         = self.utility.config.Read('uploadtimem')
        loc_uploadratio         = self.utility.config.Read('uploadratio')

        # Upload setting for completed files
        ########################################

        continuesection_title = wx.StaticBox(self, -1,  self.utility.lang.get('uploadoptforcompletedfile'))
        continuesection = wx.StaticBoxSizer(continuesection_title, wx.VERTICAL)
        
        uploadlist = [self.utility.lang.get('unlimitedupload'), self.utility.lang.get('continueuploadfor'), self.utility.lang.get('untilratio')]
       
        rb1 = wx.RadioButton(self, -1, uploadlist[0], wx.Point(-1,-1), wx.Size(-1, -1), wx.RB_GROUP)
        rb2 = wx.RadioButton(self, -1, uploadlist[1], wx.Point(-1,-1), wx.Size(-1, -1))
        rb3 = wx.RadioButton(self, -1, uploadlist[2], wx.Point(-1,-1), wx.Size(-1, -1))
        self.rb = [rb1, rb2, rb3]
        self.rb[int(loc_uploadopt)].SetValue(True)
              
        mtimeval = ['30', '45', '60', '75']
        htimeval = []
        for i in range(0, 24):
            htimeval.append(str(i))
            
        self.cbhtime = wx.ComboBox(self, -1, loc_uploadtimeh, wx.Point(-1, -1),                                  
                                  wx.Size(37, -1), htimeval, wx.CB_DROPDOWN|wx.CB_READONLY)
        self.cbmtime = wx.ComboBox(self, -1, loc_uploadtimem, wx.Point(-1, -1),
                                  wx.Size(37, -1), mtimeval, wx.CB_DROPDOWN|wx.CB_READONLY)
        self.cbhtime.SetValue(loc_uploadtimeh)
        self.cbmtime.SetValue(loc_uploadtimem)

        continuesection.Add(rb1, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        time_sizer = wx.BoxSizer(wx.HORIZONTAL)
        time_sizer.Add(rb2, 0, wx.ALIGN_CENTER_VERTICAL)
        time_sizer.Add(self.cbhtime, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
        time_sizer.Add(wx.StaticText(self, -1, self.utility.lang.get('hour')), 0, wx.ALIGN_CENTER_VERTICAL)
        time_sizer.Add(self.cbmtime, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
        time_sizer.Add(wx.StaticText(self, -1, self.utility.lang.get('minute')), 0, wx.ALIGN_CENTER_VERTICAL)
        
        continuesection.Add(time_sizer, -1, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        ratioval = ['50', '75', '100', '125', '150','175','200', '300', '400', '500']
        self.cbratio = wx.ComboBox(self, -1, loc_uploadratio,
                                  wx.Point(-1, -1), wx.Size(45, -1), ratioval, wx.CB_DROPDOWN|wx.CB_READONLY)
        self.cbratio.SetValue(loc_uploadratio)
       
        percent_sizer = wx.BoxSizer(wx.HORIZONTAL)
        percent_sizer.Add(rb3, 0, wx.ALIGN_CENTER_VERTICAL)
        percent_sizer.Add(self.cbratio, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
        percent_sizer.Add(wx.StaticText(self, -1, "%"), 0, wx.ALIGN_CENTER_VERTICAL)
        
        continuesection.Add(percent_sizer, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        sizer.Add( continuesection, 0, wx.EXPAND|wx.ALL, 5)
     
        self.SetSizerAndFit( sizer )
        
    def apply(self):
        # Set new value to parameters
        ##############################
        for i in range (0, 3):
            if self.rb[i].GetValue():
                self.utility.config.Write('uploadoption', str(i))

        self.utility.config.Write('uploadtimeh', self.cbhtime.GetValue())
        self.utility.config.Write('uploadtimem', self.cbmtime.GetValue())
        self.utility.config.Write('uploadratio', self.cbratio.GetValue())

class ColumnsPanel(wx.Panel):
    def __init__(self, parent, dialog):
        wx.Panel.__init__(self, parent, -1)
        
        # Constants
        self.RANK = 0
        self.COLID = 1
        self.TEXT = 2
        self.WIDTH = 3

        self.dialog = dialog
        self.utility = dialog.utility
        
        self.changed = False
        
        self.changingvalue = False

        self.leftid = []
        self.rightid = []
        self.leftindex = -1
        self.rightindex = -1
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        listsizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # unselected list ctrl
       
        self.checklistbox = wx.CheckListBox(self, -1, size = wx.Size(150, 200), style = wx.LB_SINGLE)

        listsizer.Add(self.checklistbox, 0, wx.ALL, 5)

        # Up & Down button
        ###################        
        self.upbutton = self.makeBitmapButton('moveup.bmp', 'move_up', self.OnMove)
        self.downbutton = self.makeBitmapButton('movedown.bmp', 'move_down', self.OnMove)

        updownsizer = wx.BoxSizer(wx.VERTICAL)
        
        updownsizer.Add(self.upbutton, 0, wx.BOTTOM, 5)
        updownsizer.Add(self.downbutton, 0, wx.TOP, 5)
        
        listsizer.Add(updownsizer, 0, wx.ALL, 5)
        
        sizer.Add(listsizer, 0)
        
        labelbox = wx.BoxSizer(wx.HORIZONTAL)
        labelbox.Add(wx.StaticText(self, -1, self.utility.lang.get('displayname')), 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)
        columnlabel = ""
        self.labelsetting = wx.TextCtrl(self, -1, columnlabel)
        labelbox.Add(self.labelsetting, 0, wx.ALIGN_CENTER_VERTICAL)
        
        sizer.Add(labelbox, 0, wx.ALL, 5)
        
        widthbox = wx.BoxSizer(wx.HORIZONTAL)
        widthbox.Add(wx.StaticText(self, -1, self.utility.lang.get('columnwidth')), 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)
        initialvalue = 0
        self.widthsetting = self.utility.makeNumCtrl(self, initialvalue, integerWidth = 4, max = 2000)
        widthbox.Add(self.widthsetting, 0, wx.ALIGN_CENTER_VERTICAL)
        
        sizer.Add(widthbox, 0, wx.ALL, 5)
        
        self.savecolumnwidth = wx.CheckBox(self, -1, self.utility.lang.get('savecolumnwidth'))
        self.savecolumnwidth.SetValue(self.utility.config.Read('savecolumnwidth') == "1")
        
        sizer.Add(self.savecolumnwidth, 0, wx.ALL, 5)
        
        self.getDefaultValues()

        self.labelsetting.Enable(False)
        self.widthsetting.Enable(False)
        
        self.SetSizerAndFit( sizer )

        # Add Event
        #########################
#        self.Bind(wx.EVT_BUTTON, self.OnMove, self.upbutton)
#        self.Bind(wx.EVT_BUTTON, self.OnMove, self.downbutton)
        self.Bind(wx.EVT_LISTBOX, self.OnSelect, self.checklistbox)
        self.Bind(wx.EVT_TEXT, self.OnChangeLabel, self.labelsetting)
        self.Bind(masked.EVT_NUM, self.OnChangeWidth, self.widthsetting)

    def makeBitmapButton(self, bitmap, tooltip, event, trans_color = wx.Colour(200, 200, 200), toggle = False, bitmapselected = None):
        tooltiptext = self.utility.lang.get(tooltip)
        
        button_bmp = self.utility.makeBitmap(bitmap, trans_color)
        if bitmapselected:
            buttonselected_bmp = self.utility.makeBitmap(bitmapselected, trans_color)
        
        ID_BUTTON = wx.NewId()
        if (toggle):
            button_btn = wxGenBitmapToggleButton(self, ID_BUTTON, None, size=wx.Size(button_bmp.GetWidth() + 4, button_bmp.GetHeight() + 4), style = wx.NO_BORDER)
            button_btn.SetBitmapLabel(button_bmp)
            if bitmapselected:
                button_btn.SetBitmapSelected(buttonselected_bmp)
            else:
                button_btn.SetBitmapSelected(button_bmp)
        else:
            button_btn = wx.BitmapButton(self, ID_BUTTON, button_bmp, size=wx.Size(button_bmp.GetWidth()+18, button_bmp.GetHeight()+4))
        button_btn.SetToolTipString(tooltiptext)
        self.Bind(wx.EVT_BUTTON, event, button_btn)
        return button_btn

    def getDefaultValues(self):
        unselected = []
        
        selected = []

        for colid in range(4, self.utility.guiman.maxid):
            rank = self.utility.config.Read('column' + str(colid) + "_rank", "int")
            text = self.utility.lang.get('column' + str(colid) + "_text")
            width = self.utility.config.Read('column' + str(colid) + "_width", "int")
            if rank == -1:
                unselected.append([rank, colid, text, width])
            else:
                selected.append([rank, colid, text, width])
        
        unselected.sort()
        selected.sort()
        
        self.columnlist = selected + unselected
        
        self.checklistbox.Set([item[2] for item in self.columnlist])
        
        for i in range(0, len(self.columnlist)):
            if self.columnlist[i][0] != -1:
                self.checklistbox.Check(i)
    
    # Select one of the items in the list
    def OnSelect(self, event):
        # The index of the selection within the checklistbox
        index = self.checklistbox.GetSelection()
        if index == wx.NOT_FOUND:
            self.labelsetting.Enable(False)
            self.widthsetting.Enable(False)
            return
        self.labelsetting.Enable(True)
        self.widthsetting.Enable(True)
            
        textstring = self.checklistbox.GetString(index)

        self.changingvalue = True
        self.labelsetting.SetValue(textstring)
        self.widthsetting.SetValue(self.columnlist[index][self.WIDTH])
        self.changingvalue = False
        
    def OnChangeLabel(self, event):
        if self.changingvalue:
            return
        
        index = self.checklistbox.GetSelection()
        if index == wx.NOT_FOUND:
            return
        
        oldlabel = self.columnlist[index][self.TEXT]
        newlabel = self.labelsetting.GetValue()
        if oldlabel == newlabel:
            return
            
        self.columnlist[index][self.TEXT] = newlabel
        self.checklistbox.SetString(index, newlabel)
        
    def OnChangeWidth(self, event):
        if self.changingvalue:
            return
        
        index = self.checklistbox.GetSelection()
        if index == wx.NOT_FOUND:
            return
        
        oldwidth = self.columnlist[index][self.WIDTH]
        newwidth = str(self.widthsetting.GetValue())
        if oldwidth == newwidth:
            return
        
        self.columnlist[index][self.WIDTH] = newwidth
    
    # Move a list item up or down           
    def OnMove(self, event):
        # Move up
        if event.GetId() == self.upbutton.GetId():
            direction = -1
        # Move down
        else:
            direction = 1
        
        index = self.checklistbox.GetSelection()
        if index == wx.NOT_FOUND:
            # Nothing is selected:
            return

        if (direction == 1) and (index == self.checklistbox.GetCount() - 1):
            #Last Item can't move down anymore
            return
        elif (direction == -1) and (index == 0):
            # First Item can't move up anymore
            return
        else:
            self.columnlist[index], self.columnlist[index + direction] = self.columnlist[index + direction], self.columnlist[index]
           
            col1text = self.checklistbox.GetString(index)
            col2text = self.checklistbox.GetString(index + direction)

            col1checked = self.checklistbox.IsChecked(index)
            col2checked = self.checklistbox.IsChecked(index + direction)

            #Update display
            self.checklistbox.SetString(index + direction, col1text)
            self.checklistbox.SetString(index, col2text)
            
            self.checklistbox.Check(index + direction, col1checked)
            self.checklistbox.Check(index, col2checked)
            
            self.checklistbox.SetSelection(index + direction)
               
    def getrank(self, selected_list, id):
        for i in range(0, len(selected_list)):
            if selected_list[i] == id :
                return str(i)
        return str(-1)

    def apply(self):
        self.utility.config.Write('savecolumnwidth', self.savecolumnwidth.GetValue(), "boolean")

        selected = 0
        for i in range(0, self.checklistbox.GetCount()):
            colid = self.columnlist[i][1]
            if self.checklistbox.IsChecked(i):
                self.columnlist[i][self.RANK] = selected
                selected += 1
            else:
                self.columnlist[i][self.RANK] = -1

        # Check to see if anything has changed
        overallchange = False                
        for item in self.columnlist:
            colid = item[self.COLID]

            rank = item[self.RANK]
            changed = self.utility.config.Write("column" + str(colid) + "_rank", rank)
            if changed:
                overallchange = True
            
            changed = self.changeText(item)
            if changed:
                overallchange = True

            width = str(item[self.WIDTH])
            changed = self.utility.config.Write("column" + str(colid) + "_width", width)
            if changed:
                overallchange = True

        # APPLY on-the-fly
        if overallchange:
            self.utility.lang.flush()
            self.utility.frame.updateABCDisplay()
            
    def changeText(self, item):
        colid = item[self.COLID]
        
        param = "column" + str(colid) + "_text"
        text = item[self.TEXT]
        
        return self.utility.lang.writeUser(param, text)

class AdvancedNetworkPanel(wx.Panel):
    def __init__(self, parent, dialog):
        wx.Panel.__init__(self, parent, -1)
        
        self.dialog = dialog
        self.utility = dialog.utility
        
        self.changed = False

        colsizer = wx.FlexGridSizer(cols = 1, hgap = 13, vgap = 13)
        warningtext = wx.StaticText(self, -1, self.utility.lang.get('changeownrisk'))
        colsizer.Add(warningtext, 1, wx.ALIGN_CENTER)
       
        #self.ipv6bindsv4_data=wx.Choice(self, -1,
        #                 choices = ['separate sockets', 'single socket'])
        #self.ipv6bindsv4_data.SetSelection(int(self.advancedConfig['ipv6_binds_v4']))
        
        twocolsizer = wx.FlexGridSizer(cols = 2, hgap = 20)
        datasizer = wx.FlexGridSizer(cols = 2, vgap = 2)

        # Local IP
        self.ip_data = wx.TextCtrl(self, -1, self.utility.config.Read('ip'))
        datasizer.Add(wx.StaticText(self, -1, self.utility.lang.get('localip')), 1, wx.ALIGN_CENTER_VERTICAL)
        datasizer.Add(self.ip_data)

        # IP to Bind to
        self.bind_data = wx.TextCtrl(self, -1, self.utility.config.Read('bind'))
        datasizer.Add(wx.StaticText(self, -1, self.utility.lang.get('iptobindto')), 1, wx.ALIGN_CENTER_VERTICAL)
        datasizer.Add(self.bind_data)

        #datasizer.Add(wx.StaticText(self, -1, 'IPv6 socket handling: '), 1, wx.ALIGN_CENTER_VERTICAL)
        #datasizer.Add(ipv6bindsv4_data)

        # Minimum Peers
        self.minpeers_data = wx.SpinCtrl(self, size = wx.Size(60, -1))
        self.minpeers_data.SetRange(10,100)
        self.minpeers_data.SetValue(self.utility.config.Read('min_peers', "int"))
        datasizer.Add(wx.StaticText(self, -1, self.utility.lang.get('minnumberofpeer')), 1, wx.ALIGN_CENTER_VERTICAL)
        datasizer.Add(self.minpeers_data)

        # Maximum Connections
        maxconnections_choices = [self.utility.lang.get('nolimit'), '20', '30', '40', '60', '100', '200']
        self.maxconnections_data=wx.Choice(self, -1, wx.Point(-1, -1), wx.Size(-1, -1), maxconnections_choices)
        setval = self.utility.config.Read('max_connections', "int")
        if setval == 0:
            setval = self.utility.lang.get('nolimit')
        else:
            setval = str(setval)
        if not setval in maxconnections_choices:
            setval = maxconnections_choices[0]
        self.maxconnections_data.SetStringSelection(setval)
        datasizer.Add(wx.StaticText(self, -1, self.utility.lang.get('maxpeerconnection')), 1, wx.ALIGN_CENTER_VERTICAL)
        datasizer.Add(self.maxconnections_data)
        
        # UPnP Settings
        upnp_choices = [ self.utility.lang.get('upnp_0'),
                         self.utility.lang.get('upnp_1'),
                         self.utility.lang.get('upnp_2') ]
        upnp_val = self.utility.config.Read('upnp_nat_access', "int")
        if upnp_val >= len(upnp_choices):
            upnp_val = len(upnp_choices) - 1
        upnp_text = upnp_choices[upnp_val]
        self.upnp_data = wx.ComboBox(self, -1, upnp_text, wx.Point(-1,-1), wx.Size(-1,-1), upnp_choices, wx.CB_DROPDOWN|wx.CB_READONLY)
        datasizer.Add(wx.StaticText(self, -1, self.utility.lang.get('upnp')), 1, wx.ALIGN_CENTER_VERTICAL)
        datasizer.Add(self.upnp_data)
        
        twocolsizer.Add(datasizer)

        colsizer.Add(twocolsizer)

#        self.hinttext = wx.StaticText(self, -1, '\n\n\n')
#        colsizer.Add(self.hinttext)

        defaultsButton = wx.Button(self, -1, self.utility.lang.get('reverttodefault'))
        colsizer.Add(defaultsButton, 0, wx.ALIGN_CENTER)

        border = wx.BoxSizer(wx.HORIZONTAL)
        border.Add(colsizer, 1, wx.EXPAND | wx.ALL, 4)
        
        self.SetAutoLayout(True)
        
        self.SetSizerAndFit( border )
        
        wx.EVT_BUTTON(self, defaultsButton.GetId(), self.setDefaults)
        
        # Set tooltips
        self.ip_data.SetToolTipString(self.utility.lang.get('iphint'))
        self.bind_data.SetToolTipString(self.utility.lang.get('bindhint'))
        self.minpeers_data.SetToolTipString(self.utility.lang.get('minpeershint'))
        self.maxconnections_data.SetToolTipString(self.utility.lang.get('maxconnectionhint'))
        
#        wx.EVT_ENTER_WINDOW(self.ip_data, self.ip_hint)
#        wx.EVT_ENTER_WINDOW(self.bind_data, self.bind_hint)
#        #wx.EVT_ENTER_WINDOW(self.ipv6bindsv4_data, self.ipv6bindsv4_hint)
#        wx.EVT_ENTER_WINDOW(self.minpeers_data, self.minpeers_hint)
#        wx.EVT_ENTER_WINDOW(self.maxconnections_data, self.maxconnections_hint)
#        
#    def ip_hint(self, event = None):
#        self.hinttext.SetLabel( self.utility.lang.get('iphint') )
#
#    def bind_hint(self, event = None):
#        self.hinttext.SetLabel( self.utility.lang.get('bindhint') )
#
#    #def ipv6bindsv4_hint(self, event = None):
#    #    self.hinttext.SetLabel('\n\n\nCertain operating systems will\n' +
#    #                          'open IPv4 protocol connections on\n' +
#    #                          'an IPv6 socket; others require you\n' +
#    #                          "to open two sockets on the same\n" +
#    #                          "port, one IPv4 and one IPv6.")
#
#    def minpeers_hint(self, event = None):
#        self.hinttext.SetLabel( self.utility.lang.get('minpeershint') )
#
#    def maxconnections_hint(self, event = None):
#        self.hinttext.SetLabel( self.utility.lang.get('maxconnectionhint') )

    def setDefaults(self, event = None):
        self.ip_data.SetValue('')
        self.bind_data.SetValue('')
        #self.ipv6bindsv4_data.SetSelection(1)
        self.minpeers_data.SetValue(20)
        self.maxconnections_data.SetStringSelection(self.utility.lang.get('nolimit'))
        self.upnp_data.SetStringSelection(self.utility.lang.get('upnp_0'))
        
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
        
        upnp_choices = [ self.utility.lang.get('upnp_0'),
                         self.utility.lang.get('upnp_1'),
                         self.utility.lang.get('upnp_2') ]
        selected = upnp_choices.index(self.upnp_data.GetValue())
        self.utility.config.Write('upnp_nat_access', selected)

        self.utility.config.Write('ipv6_binds_v4', "1")

class AdvancedDiskPanel(wx.Panel):
    def __init__(self, parent, dialog):
        wx.Panel.__init__(self, parent, -1)
        
        self.dialog = dialog
        self.utility = dialog.utility
        
        self.changed = False

        colsizer = wx.FlexGridSizer(cols = 1, hgap = 13, vgap = 13)
        warningtext = wx.StaticText(self, -1, self.utility.lang.get('changeownrisk'))
        colsizer.Add(warningtext, 1, wx.ALIGN_CENTER)
       
        datasizer = wx.FlexGridSizer(cols = 2, vgap = 2, hgap = 20)

        # Allocation Type
        
        alloc_choices = [self.utility.lang.get('alloc_normal'),
                         self.utility.lang.get('alloc_background'), 
                         self.utility.lang.get('alloc_prealloc'), 
                         self.utility.lang.get('alloc_sparse')]
        alloc_strings = {"normal": 0, "background": 1, "pre-allocate": 2, "sparse": 3}
        self.alloctype_data=wx.Choice(self, -1, wx.Point(-1, -1), wx.Size(-1, -1), alloc_choices)
        try:
            alloc_selection = alloc_strings[self.utility.config.Read('alloc_type')]
        except:
            alloc_selection = 0
        self.alloctype_data.SetSelection(alloc_selection)
        datasizer.Add(wx.StaticText(self, -1, self.utility.lang.get('diskalloctype')), 1, wx.ALIGN_CENTER_VERTICAL)
        datasizer.Add(self.alloctype_data)

        # Allocation Rate
        self.allocrate_data = wx.SpinCtrl(self, size = wx.Size(60, -1))
        self.allocrate_data.SetRange(1,100)
        self.allocrate_data.SetValue(self.utility.config.Read('alloc_rate', "int"))
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
        if self.utility.config.Read('lock_files', "int"):
            if self.utility.config.Read('lock_while_reading', "int"):
                self.locking_data.SetSelection(2)
            else:
                self.locking_data.SetSelection(1)
        else:
            self.locking_data.SetSelection(0)
        datasizer.Add(wx.StaticText(self, -1, self.utility.lang.get('filelocking')), 1, wx.ALIGN_CENTER_VERTICAL)
        datasizer.Add(self.locking_data)

        # Doublecheck Method
        doublecheck_choices = [self.utility.lang.get('check_none'),
                               self.utility.lang.get('check_double'),
                               self.utility.lang.get('check_triple')]
        self.doublecheck_data=wx.Choice(self, -1, wx.Point(-1, -1), wx.Size(-1, -1), doublecheck_choices)
        if self.utility.config.Read('double_check', "int"):
            if self.utility.config.Read('triple_check', "int"):
                self.doublecheck_data.SetSelection(2)
            else:
                self.doublecheck_data.SetSelection(1)
        else:
            self.doublecheck_data.SetSelection(0)
        datasizer.Add(wx.StaticText(self, -1, self.utility.lang.get('extradatachecking')), 1, wx.ALIGN_CENTER_VERTICAL)
        datasizer.Add(self.doublecheck_data)

        # Maximum Files Open
        maxfilesopen_choices = ['50', '100', '200', self.utility.lang.get('nolimit')]
        self.maxfilesopen_data=wx.Choice(self, -1, wx.Point(-1, -1), wx.Size(-1, -1), maxfilesopen_choices)
        setval = self.utility.config.Read('max_files_open', "int")
        if setval == 0:
            setval = self.utility.lang.get('nolimit')
        else:
            setval = str(setval)
        if not setval in maxfilesopen_choices:
            setval = maxfilesopen_choices[0]
        self.maxfilesopen_data.SetStringSelection(setval)
        datasizer.Add(wx.StaticText(self, -1, self.utility.lang.get('maxfileopen')), 1, wx.ALIGN_CENTER_VERTICAL)
        datasizer.Add(self.maxfilesopen_data)        
      
        # Flush data        
        try:
            flushval = self.utility.config.Read('auto_flush', "int")
        except:
            flushval = 0

        self.flush_data_enable = wx.CheckBox(self, -1, self.utility.lang.get('flush_data'))
        self.flush_data_enable.SetValue(flushval > 0)

        self.flush_data = wx.SpinCtrl(self, size = wx.Size(60, -1))
        self.flush_data.SetRange(0,999)
        self.flush_data.SetValue(flushval)
        
        datasizer.Add(self.flush_data_enable, 0, wx.ALIGN_CENTER_VERTICAL)

        flush_box = wx.BoxSizer(wx.HORIZONTAL)
        flush_box.Add(self.flush_data, 0, wx.ALIGN_CENTER_VERTICAL)
        flush_box.Add(wx.StaticText(self, -1, self.utility.lang.get('minute_long')), 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)

        datasizer.Add(flush_box)

        colsizer.Add(datasizer)

        # Disk buffering
        buffer_title = wx.StaticBox(self,  -1,  self.utility.lang.get('bufferdisk'))
        buffer = wx.StaticBoxSizer(buffer_title, wx.VERTICAL)

        self.buffer_read_enable = wx.CheckBox(self, -1, self.utility.lang.get('buffer_read'))
        self.buffer_read_enable.SetValue(self.utility.config.Read('buffer_read', "boolean"))        
        
        try:
            writeval = self.utility.config.Read('buffer_write', "int")
        except:
            writeval = 0
            
        self.buffer_write = wx.SpinCtrl(self, size = wx.Size(60, -1))
        self.buffer_write.SetRange(0,999)
        self.buffer_write.SetValue(writeval)
        
        self.buffer_write_enable = wx.CheckBox(self, -1, self.utility.lang.get('buffer_write'))
        self.buffer_write_enable.SetValue(writeval > 0)

        buffer_write_box = wx.BoxSizer(wx.HORIZONTAL)
        buffer_write_box.Add(self.buffer_write_enable, 0, wx.ALIGN_CENTER_VERTICAL)
        buffer_write_box.Add(self.buffer_write, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
        buffer_write_box.Add(wx.StaticText(self, -1, "MB"), 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
       
        buffer.Add(self.buffer_read_enable, 0, wx.ALL, 5)
        buffer.Add(buffer_write_box, 0, wx.ALL, 5)

        colsizer.Add(buffer, 0, wx.EXPAND)

#        self.hinttext = wx.StaticText(self, -1, '\n\n\n')
#        colsizer.Add(self.hinttext)

        defaultsButton = wx.Button(self, -1, self.utility.lang.get('reverttodefault'))
        colsizer.Add(defaultsButton, 1, wx.ALIGN_CENTER)

        border = wx.BoxSizer(wx.HORIZONTAL)
        border.Add(colsizer, 1, wx.EXPAND | wx.ALL, 4)
        
        self.SetAutoLayout(True)
        
        self.SetSizerAndFit( border )
        
        wx.EVT_BUTTON(self, defaultsButton.GetId(), self.setDefaults)

        self.alloctype_data.SetToolTipString( self.utility.lang.get('alloctypehint'))
        self.allocrate_data.SetToolTipString(self.utility.lang.get('allocratehint') )
        self.locking_data.SetToolTipString( self.utility.lang.get('lockinghint'))
        self.doublecheck_data.SetToolTipString( self.utility.lang.get('doublecheckhint') )
        self.maxfilesopen_data.SetToolTipString( self.utility.lang.get('maxfileopenhint'))
        
#        wx.EVT_ENTER_WINDOW(self.alloctype_data, self.alloctype_hint)
#        wx.EVT_ENTER_WINDOW(self.allocrate_data, self.allocrate_hint)
#        wx.EVT_ENTER_WINDOW(self.locking_data, self.locking_hint)
#        wx.EVT_ENTER_WINDOW(self.doublecheck_data, self.doublecheck_hint)
#        wx.EVT_ENTER_WINDOW(self.maxfilesopen_data, self.maxfilesopen_hint)
#        
#    def alloctype_hint(self, event = None):
#        self.hinttext.SetLabel( self.utility.lang.get('alloctypehint') )
#
#    def allocrate_hint(self, event = None):
#        self.hinttext.SetLabel( self.utility.lang.get('allocratehint') )
#
#    def locking_hint(self, event = None):
#        self.hinttext.SetLabel( self.utility.lang.get('lockinghint') )
#
#    def doublecheck_hint(self, event = None):
#        self.hinttext.SetLabel( self.utility.lang.get('doublecheckhint') )
#
#    def maxfilesopen_hint(self, event = None):
#        self.hinttext.SetLabel( self.utility.lang.get('maxfileopenhint') )

    def setDefaults(self, event = None):
        self.alloctype_data.SetSelection(0)
        self.allocrate_data.SetValue(2)
        self.locking_data.SetSelection(1)
        self.doublecheck_data.SetSelection(1)
        self.maxfilesopen_data.SetStringSelection("50")
        self.buffer_read_enable.SetValue(True)
        self.buffer_write_enable.SetValue(True)
        self.buffer_write.SetValue(4)
        self.flush_data_enable.SetValue(False)
        self.flush_data.SetValue(0)
        
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

class ABCTree(wx.TreeCtrl):
    def __init__(self, parent, dialog):
        style = wx.TR_DEFAULT_STYLE | wx.TR_HIDE_ROOT
        wx.TreeCtrl.__init__(self, parent, -1, style = style)

        self.dialog = dialog
        self.utility = dialog.utility
       
        self.root = self.AddRoot("Preferences")
        
#        self.globalupload = self.AppendItem(self.root, self.utility.lang.get('globaluploadsetting'))
        self.ratelimits = self.AppendItem(self.root, self.utility.lang.get('ratelimits'))
        self.seedingoptions = self.AppendItem(self.root, self.utility.lang.get('seedoptions'))
        self.urmsetting = self.AppendItem(self.root, self.utility.lang.get('urmsetting'))
        self.queuesetting = self.AppendItem(self.root, self.utility.lang.get('queuesetting'))
        self.timeout = self.AppendItem(self.root, self.utility.lang.get('timeout'))
        
        self.network = self.AppendItem(self.root, self.utility.lang.get('networksetting'))
        self.advancednetwork = self.AppendItem(self.network, self.utility.lang.get('advanced'))
        
        self.disk = self.AppendItem(self.root, self.utility.lang.get('disksettings'))
        self.advanceddisk = self.AppendItem(self.disk, self.utility.lang.get('advanced'))
                
        self.misc = self.AppendItem(self.root, self.utility.lang.get('miscsetting'))
        self.columns = self.AppendItem(self.root, self.utility.lang.get('columns'))

        self.treeMap = {self.ratelimits : self.dialog.rateLimitPanel,
                        self.seedingoptions : self.dialog.seedingOptionsPanel,
                        self.urmsetting : self.dialog.urmPanel,
                        self.queuesetting : self.dialog.queuePanel,
                        self.timeout : self.dialog.schedulerRulePanel,
                        self.network : self.dialog.networkPanel,
                        self.advancednetwork : self.dialog.advancedNetworkPanel,
                        self.misc : self.dialog.miscPanel,
                        self.columns : self.dialog.columnsPanel,
                        self.disk : self.dialog.diskPanel,
                        self.advanceddisk : self.dialog.advancedDiskPanel
                        }
        
        self.Bind(wx.EVT_TREE_SEL_CHANGED, self.onSwitchPage)

        self.SetAutoLayout( True )
        self.Fit()

    def onSwitchPage(self, event = None):       
        if self.dialog.closing or event is None:
            return

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
#                data = StringIO()
#                print_exc(file = data)
#                sys.stderr.write(data.getvalue())
        
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
        self.urmPanel = URMPanel(self.splitter, self)
        self.schedulerRulePanel = SchedulerRulePanel(self.splitter, self)
        self.networkPanel = NetworkPanel(self.splitter, self)
        self.miscPanel = MiscPanel(self.splitter, self)
        self.columnsPanel = ColumnsPanel(self.splitter, self)
        self.diskPanel = DiskPanel(self.splitter, self)        
        self.advancedNetworkPanel = AdvancedNetworkPanel(self.splitter, self)
        self.advancedDiskPanel = AdvancedDiskPanel(self.splitter, self)
        
        self.tree = ABCTree(self.splitter, self)

        # TODO: Try wx.Listbook instead of splitterwindow

        self.splitter.SetAutoLayout( True )
        self.splitter.Fit()
      
        applybtn       = wx.Button(self, -1, " "+self.utility.lang.get('apply')+" ", size = (60, -1))
        okbtn          = wx.Button(self, -1, " "+self.utility.lang.get('ok')+" ", size = (60, -1))
        cancelbtn      = wx.Button(self, -1, " "+self.utility.lang.get('cancel')+" ", size = (60, -1))
        
        buttonbox = wx.BoxSizer( wx.HORIZONTAL )
        buttonbox.Add(applybtn, 0, wx.ALL, 5)
        buttonbox.Add(okbtn, 0, wx.ALL, 5)
        buttonbox.Add(cancelbtn, 0, wx.ALL, 5)
       
        outerbox = wx.BoxSizer( wx.VERTICAL )
        outerbox.Add( self.splitter , 1, wx.EXPAND|wx.LEFT|wx.RIGHT|wx.TOP, 5)
        outerbox.Add( buttonbox, 0, wx.ALIGN_RIGHT)

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
        
        self.SetSizer( outerbox )
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
        
    def onApply(self, event):        
        # Set new value to parameters
        ##############################          
        totalmaxdownload = int(self.queuePanel.numsimtext.GetValue())
        if self.urmPanel.urm.GetValue():
            totalmaxdownload += int(self.urmPanel.urmmaxtorrenttext.GetValue())
            
        minport = int(self.networkPanel.minport.GetValue())
        maxport = int(self.networkPanel.maxport.GetValue())
        numports = maxport - minport + 1

        if totalmaxdownload > numports:
            dlg = wx.MessageDialog(self, self.utility.lang.get('maxsimdownloadwarning')  , self.utility.lang.get('error'), wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            return False

        # Only apply changes for panels that the user has viewed
        for key in self.tree.treeMap:
            panel = self.tree.treeMap[key]
            if panel.changed:
                panel.apply()
            
        # write current changes to disk
        self.utility.config.Flush()
        
        self.utility.queue.changeABCParams()    #overwrite flag
                
        return True

    def onOK(self, event):
        if self.onApply(event):
            self.closing = True
            self.saveWindowSettings()
            
            self.EndModal(wx.ID_OK)
