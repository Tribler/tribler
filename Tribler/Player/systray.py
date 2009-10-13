# Written by Arno Bakker
# see LICENSE.txt for license information

import sys
import os
import textwrap
import time
from sets import Set # M23TRIAL
from traceback import print_exc
import wx

from Tribler.Core.API import *

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
    
    def gui_states_callback(self,dslist,haspeerlist):
        """ Called every second with Download engine statistics, peerlist is there 
        every 10 secs, see BaseApp.gui_states_callback """
        if haspeerlist:
            # TODO: this is over all content in the BackgroundProcess
            for ds in dslist:
                peers= ds.get_peerlist()
                for peer in peers:
                    #print >>sys.stderr,"M23SeedTreat: Got peer",`peer['ip']`
                    if peer['utotal'] > 0.0:
                        self.helpedpeerids.add(peer['ip']) # Could use 'id' but that is not unique for HTTP seeders
                

    def get_treatment(self):
        
        # TODO: determine which treatment to give.
        if self.wxapp.s is not None:
            permid = self.wxapp.s.get_permid()
            digit = ord(pubbytes[-1]) % 10
            # TODO: verify digit is correctly distributed over 0..9
            
            if digit >= 0 and digit <= 1:
                return "controlgroup"
            elif digit >= 2 and digit <= 3:
                return "appealforhelp"
            elif digit >= 4 and digit <= 5:
                return "quantitative"
            elif digit >= 6 and digit <= 7:
                return "compaverage"
            elif digit >= 8 and digit <= 9:
                return "efficacy"
            elif digit >= 8 and digit <= 9:   # TODO: map 6 treatments to 10 values
                return "awareness"
        else:
            return "controlgroup"
    
    def OnExitClient(self,event=None):

        t = self.get_treatment()
        ask = True
        if t == "controlgroup":
            msg = "Do you really want to quit?"
        
        elif t == "appealforhelp" :
            msg = "By keeping this program running you are helping other people see the video." 

        elif t == "quantitative":
            # X is calculated on the client side. It is the number of peers to whom this
            # user has uploaded data. This treatment needs X and the user answer for
            # the quit dialog every time the dialog is shown to him.
            X = len(self.helpedpeerids)
            # TODO: set minimum?
            msg = "By keeping this program running you have already helped %d other people to see the video. By not quitting you can help more." % (X)
             
        elif t == "compaverage": 
            # X is calculated locally similarly to the efficacy treatment. Y needs to be
            # obtained from a server which calculates it periodically. This treatment
            # needs X, Y and the user answer for the quit dialog every time the dialog
            # is shown to him.
            
            # TODO: set minimum + check description which says "similar to efficacy
            # treat". This is similar to "quant" treat.
            X = len(self.helpedpeerids) 
            
            # TODO: Idea: let each client report its helpedpeerids count, by calling 
            # add_event on gui_states_callback every N secs. A script calculates Y from
            # this and puts it on a website, which is also read periodically by each client.
            Y = 10 
            
            msg = "By keeping this program running you have helped %d other people to see the video. The average number of people other participants in the trial have helped is %d." % (X,Y)
             
        elif t == "efficacy":
            # P is the total number of users who participated in the experiment so far. 
            # It is calculated by the server and updated periodically.
            
            # TODO
            P = 10
            msg = "Together with a total of %d other peers you have helped at least %d people see the video. By keeping this program running you are contributing to the development of a new, open video platform for the internet." % (P,P)
              
        else: #  "awareness":
            #  no dialog. But the user sees a message in the video window at the end.
            # TODO: message currently always shown at end
            ask = False 

        content = ""
        lines = textwrap.wrap(msg,50)
        for line in lines:
            content += line + " "
        
        title = "Quit SwarmPlugin?"

        quit = 0
        if ask:
            dlg = wx.MessageDialog(None, content, title, wx.YES|wx.NO|wx.ICON_QUESTION)
            result = dlg.ShowModal()
            dlg.Destroy()
            if result == wx.ID_YES:
                #print >>sys.stderr,"PlayerTaskBarIcon: OnExitClient"
                quit = 1
        else:
            quit = 1
            
        # LOG TO SERVER
        from Tribler.Core.Statistics.StatusReporter import get_reporter_instance
        _event_reporter = get_reporter_instance()
        # Report (treatment,choice and exact message). TODO: make more compact by storing just X,Y,P?
        _event_reporter.add_event("m23-seed-treat", "t:%s:q:%d:msg:%s" % (t,quit,msg))
        _event_reporter.flush()
        
        # Delay quit to allow log to succeed and exit
        if quit:
            time.sleep(1)
            self.wxapp.ExitMainLoop()
    
    
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
        wx.Dialog.__init__(self, None, -1, 'SwarmPlayer Advanced Options', size=(400,200), style=style)
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
        
        
