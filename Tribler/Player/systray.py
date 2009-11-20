# Written by Arno Bakker
# see LICENSE.txt for license information

import sys
import os
import textwrap
import time
from sets import Set # M23TRIAL
import struct # M23TRIAL
from traceback import print_exc
import wx

from Tribler.Core.API import *
from Tribler.Core.Statistics.StatusReporter import get_reporter_instance

from Tribler.Core.Utilities.utilities import show_permid # M23TRIAL

class PlayerTaskBarIcon(wx.TaskBarIcon):
    
    def __init__(self,wxapp,iconfilename):
        wx.TaskBarIcon.__init__(self)
        self.wxapp = wxapp
        
        self.icons = wx.IconBundle()
        self.icons.AddIconFromFile(iconfilename,wx.BITMAP_TYPE_ICO)
        self.icon = self.icons.GetIcon(wx.Size(-1,-1))

        if sys.platform != "darwin":
            # Mac already has the right icon set at startup
            self.SetIcon(self.icon,self.wxapp.appname)
        
    def CreatePopupMenu(self):        
        menu = wx.Menu()
        
        mi = menu.Append(-1,"Options...")
        self.Bind(wx.EVT_MENU, self.OnOptions, id=mi.GetId())
        menu.AppendSeparator()
        mi = menu.Append(-1,"Exit")
        self.Bind(wx.EVT_MENU, self.OnExitClient, id=mi.GetId())
        return menu
        
    def OnOptions(self,event=None):
        #print >>sys.stderr,"PlayerTaskBarIcon: OnOptions"
        dlg = PlayerOptionsDialog(self.wxapp,self.icons)
        ret = dlg.ShowModal()
        #print >>sys.stderr,"PlayerTaskBarIcon: Dialog returned",ret
        dlg.Destroy()

    def OnExitClient(self,event=None):
        #print >>sys.stderr,"PlayerTaskBarIcon: OnExitClient"
        self.wxapp.ExitMainLoop()
    
    
    def set_icon_tooltip(self,txt):
        if sys.platform == "darwin":
            # no taskbar tooltip on OS/X
            return

        self.SetIcon(self.icon,txt)
    

class M23TrialPlayerTaskBarIcon(PlayerTaskBarIcon):
    
    def __init__(self,wxapp,iconfilename):
        PlayerTaskBarIcon.__init__(self,wxapp,iconfilename)
        self.helpedpeerids = Set()
        self.reporting_interval = 6
        self.counter_for_reporting = 0
        self.average_helpedpeers = 5 # for use in the compaverage treatment
        self.total_peers = 0 # for use in the efficacy treatment
    
    def gui_states_callback(self,dslist,haspeerlist):
        """ Called every second with Download engine statistics, peerlist is there 
        every 10 secs, see BaseApp.gui_states_callback """
        if haspeerlist:
            # this is over all content in the BackgroundProcess
            for ds in dslist:
                peers= ds.get_peerlist()
                for peer in peers:
                    #print >>sys.stderr,"M23SeedTreat: Got peer",`peer['ip']`
                    if peer['utotal'] > 0.0:
                        self.helpedpeerids.add(peer['ip']) # Could use 'id' but that is not unique for HTTP seeders
            
            # LOG HELPED PEER IDS TO SERVER
            # We don't need to log every 10s.          
            if self.counter_for_reporting % self.reporting_interval == 0:
                permid = show_permid(self.wxapp.s.get_permid())
                _event_reporter = get_reporter_instance()
                # Report (number of peers helped). 
                # temporary hack: instead of making a complicate xpath query later, we put everything 
                # we need in the text of this element
                _event_reporter.add_event("m23trial", "helped-peers:%d:" % len(self.helpedpeerids) + permid + ":" + str(self.counter_for_reporting))
                
                
        if self.counter_for_reporting == 0 or self.counter_for_reporting % self.reporting_interval == 0:
            if self.get_treatment() == "compaverage":
                try:
                    self.average_helpedpeers = self.get_avg_helped()
                except:
                    print_exc()
                
            if self.get_treatment() == "efficacy":
                try:
                    self.total_peers = self.get_total_peers()
                except:
                    print_exc()
                     
            
        self.counter_for_reporting += 1
                

    def get_avg_helped(self):
        url = 'http://trial.p2p-next.org/avghelped.txt'
        return self.get_num(url)

    def get_total_peers(self):
        url = 'http://trial.p2p-next.org/totalpeers.txt'
        return self.get_num(url)
        
    def get_num(self,url):
        f = urlOpenTimeout(url,timeout=2)
        data = f.read()
        f.close()
        clean = data.strip()
        try:
            return int(float(clean))
        except:
            print_exc()
            return 10
        
        

    def get_treatment(self):
        if self.wxapp.s is not None:
            permid = self.wxapp.s.get_permid()
            
            # TODO: check this is valid random number
            # Convert last 4 bytes to int32
            # Note this means a user gets the same treatment on each run.
            bits32 = permid[-4:]
            values = struct.unpack("L",bits32)
            bin = values[0] % 6
            
            #print >>sys.stderr,"m23seed: bin is",bin,values[0]
            
            if bin == 0:
                return "controlgroup"
            elif bin == 1:
                return "appealforhelp"
            elif bin == 2:
                return "quantitative"
            elif bin == 3:
                return "compaverage"
            elif bin == 4:
                return "efficacy"
            elif bin == 5:
                return "awareness"
        else:
            return "controlgroup"
    
    def OnExitClient(self,event=None):
        t = self.get_treatment()
        
        print >>sys.stderr,"m23seed: OnExitClient",t
        
        ask = True
        if t == "controlgroup":
            msg = "Do you really want to quit?"
        
        elif t == "appealforhelp" :
            msg = "By running SwarmPlugin you are helping other people see the video you watched.\n\nDo you really want to quit?"

        elif t == "quantitative":
            # X is calculated on the client side. It is the number of peers to whom this
            # user has uploaded data. This treatment needs X and the user answer for
            # the quit dialog every time the dialog is shown to him.
            X = len(self.helpedpeerids)
            # Dave: no minimum
            if X == 1:
                people = "person"
            else:
                people = "people"
            msg = "While running SwarmPlugin you have already helped %d other %s to see the video you watched. If you keep it running you can help more. \n\nDo you really want to quit?" % (X, people)
             
        elif t == "compaverage": 
            # X is calculated locally similarly to the quantitative treatment. Y needs to be
            # obtained from a server which calculates it periodically. This treatment
            # needs X, Y and the user answer for the quit dialog every time the dialog
            # is shown to him.
            
            X = len(self.helpedpeerids) 
            
            if X == 1:
                people = "person"
            else:
                people = "people"
            
            # Each client reports periodically the number of peers helped to the server. 
            # TODO: A script must calculate Y from this and puts it on a website.
            Y = self.average_helpedpeers

            msg = "While running SwarmPlugin you have helped %d other %s to see the video. The average number of people other SwarmPlugin users have helped is %d. \n\nDo you really want to quit?" % (X,people,Y)
             
        elif t == "efficacy":
            # P is the total number of users who participated in the experiment so far. 
            # TODO: calculate in the server and updated periodically.
            
            P = self.total_peers
            #msg = "Together with a total of %d other peers you have helped at least %d people see the video. By keeping this program running you are contributing to the development of a new, open video platform for the internet." % (P,P)
            msg = "Together with a total of %d other peers you have helped %d people see the video. \n\nBy keeping SwarmPlugin running you are contributing to the development of a new, open video platform for the internet.\n\nDo you really want to quit?" % (P,P) 
        else: #  "awareness":
            #  no dialog. But the user sees a message in the video window at the end.
            # TODO Msg in the video window
            ask = False 
            msg = ""

        content = ""
        lines = textwrap.wrap(msg,50)
        for line in lines:
            content += line + " "
        
        title = "Quit SwarmPlugin?"

        quit = 0
        if ask:
            print >>sys.stderr,"m23seed: OnExitClient ASKING"
            #dlg = wx.MessageDialog(None, content, title, wx.YES|wx.NO|wx.ICON_QUESTION)
            # TODO word wrap msg
            dlg = QuitDialog(msg)
            dlg.ShowModal()
            result = dlg.getAnswer()
            dlg.Destroy()
            if result == QUIT:
                #print >>sys.stderr,"PlayerTaskBarIcon: OnExitClient"
                quit = 1
        else:
            quit = 1
            
        # LOG TO SERVER
        _event_reporter = get_reporter_instance()
        # Report (treatment,choice and exact message). TODO: make more compact by storing just X,Y,P?
        _event_reporter.add_event("m23trial", "seed-treat:%s,q:%d,msg:%s" % (t,quit,msg))
        _event_reporter.flush()
        
        # Delay quit to allow log to succeed and exit
        if quit:
            time.sleep(1)
            self.wxapp.ExitMainLoop()
    
KEEP_RUNNING = 0
QUIT = 1

class QuitDialog(wx.Dialog):
    def __init__(self, msg):
        wx.Dialog.__init__(self, None, wx.ID_ANY, 'SwarmPlugin', style = wx.CAPTION)
        self.answerToDialog = KEEP_RUNNING
        
        main_sizer    = wx.BoxSizer(wx.HORIZONTAL)
        inside_sizer1 = wx.BoxSizer(wx.VERTICAL)
        inside_sizer2 = wx.BoxSizer(wx.HORIZONTAL)

        # TODO: add better icon. The same as the systray, perhaps?
        bmp = wx.ArtProvider.GetBitmap(wx.ART_QUESTION, wx.ART_CMN_DIALOG, (-1, -1))
        icon = wx.StaticBitmap(self, wx.ID_ANY, bmp)
        
        main_sizer.Add(icon, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 20)

        text1 =  wx.StaticText(self, wx.ID_ANY, msg)
        #text1.SetFont(wx.Font(12, wx.SWISS, wx.NORMAL, wx.NORMAL))
        text1.Wrap(400)
        
        keepRunningBtn = wx.Button(self, wx.ID_ANY, 'Keep running')
        quitBtn = wx.Button(self, wx.ID_ANY, 'Quit')
        
        self.Bind(wx.EVT_BUTTON, self.onQuit, quitBtn)
        self.Bind(wx.EVT_BUTTON, self.onKeepRunning, keepRunningBtn)
        
        inside_sizer2.Add(keepRunningBtn, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        inside_sizer2.Add(quitBtn, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        inside_sizer1.Add(text1, 0, wx.ALIGN_TOP | wx.ALIGN_LEFT | wx.ALL, 10)
        inside_sizer1.Add(inside_sizer2, 0, wx.ALIGN_RIGHT | wx.ALL, 0)

        main_sizer.Add(inside_sizer1, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        
        self.CenterOnScreen()
        self.SetSizer(main_sizer)
        main_sizer.Fit(self)
        
        
    def onKeepRunning(self, event):
        self.answerToDialog = KEEP_RUNNING
        self.Close()
 
    def onQuit(self, event):
        self.answerToDialog = QUIT
        self.Close()
        
    def getAnswer(self):
        return self.answerToDialog
        
        #TODO: do the message to be shown in the video window: NOTE THAT IN A MAC THE BG PROCESS IS IN THE DOCK, NOT IN THE SYSTRAY!
        #TODO How to display the dialog upon shutdown signal?
        #TODO If we can differentiate between shutdown and clicking on quit, we should adapt wording for context
        #TODO: what if we still have an appeal in the video window to control for 'controlling appeals'?


    
class PlayerOptionsDialog(wx.Dialog):
    
    def __init__(self,wxapp,icons):
        self.wxapp = wxapp
        self.icons = icons
        self.port = None
        
        style = wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        wx.Dialog.__init__(self, None, -1, self.wxapp.appname+' Options', size=(400,200), style=style)
        self.SetIcons(self.icons)

        mainbox = wx.BoxSizer(wx.VERTICAL)
        
        aboutbox = wx.BoxSizer(wx.VERTICAL)
        aboutlabel1 = wx.StaticText(self, -1, self.wxapp.appname+' is a product of the Tribler team.')
        aboutlabel2 = wx.StaticText(self, -1, 'Visit us at www.p2p-next.org!')
        aboutbox.Add(aboutlabel1, 1, wx.EXPAND|wx.LEFT|wx.RIGHT, 5)
        aboutbox.Add(aboutlabel2, 1, wx.EXPAND|wx.LEFT|wx.RIGHT, 5)
        
        uploadrate = self.wxapp.get_playerconfig('total_max_upload_rate')
        
        uploadratebox = wx.BoxSizer(wx.HORIZONTAL)
        label = wx.StaticText(self, -1, 'Max upload to others (KB/s)')
        self.uploadratectrl = wx.TextCtrl(self, -1, str(uploadrate))
        uploadratebox.Add(label, 1, wx.ALIGN_CENTER_VERTICAL)
        uploadratebox.Add(self.uploadratectrl)


        buttonbox2 = wx.BoxSizer(wx.HORIZONTAL)
        advbtn = wx.Button(self, -1, 'Advanced...')
        buttonbox2.Add(advbtn, 0, wx.ALL, 5)

        
        buttonbox = wx.BoxSizer(wx.HORIZONTAL)
        okbtn = wx.Button(self, wx.ID_OK, 'OK')
        buttonbox.Add(okbtn, 0, wx.ALL, 5)
        cancelbtn = wx.Button(self, wx.ID_CANCEL, 'Cancel')
        buttonbox.Add(cancelbtn, 0, wx.ALL, 5)
        applybtn = wx.Button(self, -1, 'Apply')
        buttonbox.Add(applybtn, 0, wx.ALL, 5)

        mainbox.Add(aboutbox, 1, wx.ALL, 5)
        mainbox.Add(uploadratebox, 1, wx.EXPAND|wx.ALL, 5)
        mainbox.Add(buttonbox2, 1, wx.EXPAND, 1)
        mainbox.Add(buttonbox, 1, wx.EXPAND, 1)
        self.SetSizerAndFit(mainbox)

        self.Bind(wx.EVT_BUTTON, self.OnAdvanced, advbtn)
        self.Bind(wx.EVT_BUTTON, self.OnOK, okbtn)
        #self.Bind(wx.EVT_BUTTON, self.OnCancel, cancelbtn)
        self.Bind(wx.EVT_BUTTON, self.OnApply, applybtn)
        #self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)

    def OnOK(self,event = None):
        self.OnApply(event)
        self.EndModal(wx.ID_OK)
        
    #def OnCancel(self,event = None):
    #    self.EndModal(wx.ID_CANCEL)
        
    def OnApply(self,event = None):
        print >>sys.stderr,"PlayerOptionsDialog: OnApply",self.port
        
        if self.port is not None:
            session = self.wxapp.s
            state_dir = session.get_state_dir()
            cfgfilename = Session.get_default_config_filename(state_dir)
            scfg = SessionStartupConfig.load(cfgfilename)
            
            scfg.set_listen_port(self.port)
            print >>sys.stderr,"PlayerOptionsDialog: OnApply: Saving SessionStartupConfig to",cfgfilename
            scfg.save(cfgfilename)
        
        uploadrate = int(self.uploadratectrl.GetValue())
        self.wxapp.set_playerconfig('total_max_upload_rate',uploadrate)
        self.wxapp.save_playerconfig()
         
        # TODO: For max upload, etc. we also have to modify the runtime Session.

    def OnAdvanced(self,event = None):

        if self.port is None:
            self.port = self.wxapp.s.get_listen_port()
        #destdir = self.wxapp.s.get_dest_dir()

        dlg = PlayerAdvancedOptionsDialog(self.icons,self.port,self.wxapp)
        ret = dlg.ShowModal()
        if ret == wx.ID_OK:
            self.port = dlg.get_port()
        dlg.Destroy()


class PlayerAdvancedOptionsDialog(wx.Dialog):
    
    def __init__(self,icons,port,wxapp):
        style = wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER  # TODO: Add OK+Cancel
        wx.Dialog.__init__(self, None, -1, 'SwarmPlugin Advanced Options', size=(400,200), style=style)
        self.wxapp = wxapp

        self.SetIcons(icons)

        mainbox = wx.BoxSizer(wx.VERTICAL)
        
        portbox = wx.BoxSizer(wx.HORIZONTAL)
        label = wx.StaticText(self, -1, 'Port')
        self.portctrl = wx.TextCtrl(self, -1, str(port))
        portbox.Add(label, 1, wx.ALIGN_CENTER_VERTICAL)
        portbox.Add(self.portctrl)

        button2box = wx.BoxSizer(wx.HORIZONTAL)
        clearbtn = wx.Button(self, -1, 'Clear disk cache and exit')
        button2box.Add(clearbtn, 0, wx.ALL, 5)
        self.Bind(wx.EVT_BUTTON, self.OnClear, clearbtn)
        
        buttonbox = wx.BoxSizer(wx.HORIZONTAL)
        okbtn = wx.Button(self, wx.ID_OK, 'OK')
        buttonbox.Add(okbtn, 0, wx.ALL, 5)
        cancelbtn = wx.Button(self, wx.ID_CANCEL, 'Cancel')
        buttonbox.Add(cancelbtn, 0, wx.ALL, 5)

        mainbox.Add(portbox, 1, wx.EXPAND|wx.ALL, 5)
        mainbox.Add(button2box, 1, wx.EXPAND, 1)
        mainbox.Add(buttonbox, 1, wx.EXPAND, 1)
        self.SetSizerAndFit(mainbox)

    def get_port(self):
        return int(self.portctrl.GetValue())
        
    def OnClear(self,event=None):
        self.wxapp.clear_session_state()
        
        
