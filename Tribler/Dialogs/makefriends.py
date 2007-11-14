# Written by Jie Yang, Arno Bakker
# see LICENSE.txt for license information

import os
import sys
import base64
from sha import sha
from traceback import print_exc
from shutil import copy2
import wx
import wx.lib.imagebrowser as ib
from Tribler.CacheDB.CacheDBHandler import FriendDBHandler
from Tribler.CacheDB.SynDBHandler import SynPeerDBHandler
from Tribler.Overlay.permid import permid_for_user
#from Tribler.vwxGUI.peermanager import PeerDataManager

DEBUG = False


class MakeFriendsDialog(wx.Dialog):
    def __init__(self, parent, utility, editfriend = None):
        #provider = wx.SimpleHelpProvider()
        #wx.HelpProvider_Set(provider)
        
        self.utility = utility
        self.editfriend = editfriend

        style = wx.DEFAULT_DIALOG_STYLE 
        #| wx.RESIZE_BORDER
        pos = wx.DefaultPosition
        size = wx.Size(600, 200)
        #size, split = self.getWindowSettings()

        if editfriend is None:
            title = self.utility.lang.get('addfriend')
        else:
            title = self.utility.lang.get('editfriend')
        wx.Dialog.__init__(self, parent, -1, title, size = size, style = style)
        pre = wx.PreDialog()
        pre.SetExtraStyle(wx.DIALOG_EX_CONTEXTHELP)
        pre.Create(parent, -1, title, pos, size, style)
        self.PostCreate(pre)

        sizer = wx.BoxSizer(wx.VERTICAL)

        label = wx.StaticText(self, -1, title)
        sizer.Add(label, 0, wx.ALIGN_CENTRE|wx.ALL, 5)

        # name
        box = wx.BoxSizer(wx.HORIZONTAL)

        label = wx.StaticText(self, -1, self.utility.lang.get('name')+':',wx.DefaultPosition,wx.Size(40,18))
        #label.SetHelpText("")
        box.Add(label, 0, wx.ALIGN_CENTRE|wx.ALL, 5)

        if editfriend is not None:
            name = editfriend['name']
        else:   
            name = ''
        self.name_text = wx.TextCtrl(self, -1, name, size=(140,-1))
        ##self.name_text.SetHelpText(self.utility.lang.get('nickname_help'))
        box.Add(self.name_text, 0, wx.ALIGN_CENTRE|wx.ALL, 5)

        sizer.Add(box, 0, wx.GROW|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        # text about e-mail invitation
        label = wx.StaticText(self, -1, self.utility.lang.get('pasteinvitationemail'),wx.DefaultPosition)
        label.Wrap( 500 )
        sizer.Add(label, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        # ip
        box = wx.BoxSizer(wx.HORIZONTAL)

        label = wx.StaticText(self, -1, self.utility.lang.get('ipaddress')+':',wx.DefaultPosition,wx.Size(40,18))
        #label.SetHelpText("")
        box.Add(label, 0, wx.ALIGN_CENTRE|wx.ALL, 5)

        if editfriend is not None:
            ip = editfriend['ip']
        else:   
            ip = ''
        self.ip_text = wx.TextCtrl(self, -1, ip, size=(140,-1))
        ##self.ip_text.SetHelpText(self.utility.lang.get('friendsipaddr_help'))
        box.Add(self.ip_text, 0, wx.ALIGN_CENTRE|wx.ALL, 5)

        sizer.Add(box, 0, wx.GROW|wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT|wx.BOTTOM, 5)

        # port
        box = wx.BoxSizer(wx.HORIZONTAL)

        label = wx.StaticText(self, -1, self.utility.lang.get('portnumber'),wx.DefaultPosition,wx.Size(40,18))
        #label.SetHelpText("")
        box.Add(label, 0, wx.ALIGN_CENTRE|wx.ALL, 5)

        if editfriend is not None:
            port_str = str(editfriend['port'])
        else:   
            port_str = ''
        self.port_text = wx.TextCtrl(self, -1, port_str, size=(140,-1))
        ##self.port_text.SetHelpText(self.utility.lang.get('friendsport_help'))
        box.Add(self.port_text, 0, wx.ALIGN_CENTRE|wx.ALL, 5)

        sizer.Add(box, 0, wx.GROW|wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT|wx.BOTTOM, 5)

        # permid
        box = wx.BoxSizer(wx.HORIZONTAL)

        label = wx.StaticText(self, -1, self.utility.lang.get('permid')+':',wx.DefaultPosition,wx.Size(40,18))
        #label.SetHelpText("")
        box.Add(label, 0, wx.ALIGN_CENTRE|wx.ALL, 5)

        if editfriend is not None:
            permid = permid_for_user(editfriend['permid'])
        else:   
            permid = ''
        self.permid_text = wx.TextCtrl(self, -1, permid, size=(300,-1))
        ## self.permid_text.SetHelpText(self.utility.lang.get('friendspermid_help'))
        box.Add(self.permid_text, 0, wx.ALIGN_CENTRE|wx.ALL, 5)

        sizer.Add(box, 0, wx.GROW|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        """
        # picture
        box = wx.BoxSizer(wx.HORIZONTAL)

        label = wx.StaticText(self, -1, self.utility.lang.get('icon'))
        #label.SetHelpText("")
        box.Add(label, 0, wx.ALIGN_CENTRE|wx.ALL, 5)

        if editfriend is not None and editfriend.has_key('icon'):
            icon = str(editfriend['icon'])
        else:   
            icon = ''
        self.icon_path = wx.TextCtrl(self, -1, icon, size=(80,-1))
        ## self.icon_path.SetHelpText(self.utility.lang.get('friendsicon_help'))
        box.Add(self.icon_path, 3, wx.ALIGN_CENTRE|wx.ALL, 5)
        
        iconbtn = wx.Button(self, -1, label=self.utility.lang.get('browsebtn'))
        box.Add(iconbtn, 1, wx.ALIGN_CENTRE|wx.ALL, 5)
        self.Bind(wx.EVT_BUTTON, self.OnIconButton, iconbtn)

        sizer.Add(box, 0, wx.GROW|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
        """  
        
        box = wx.BoxSizer(wx.HORIZONTAL)
        line = wx.StaticLine(self, -1, size=(20,-1), style=wx.LI_HORIZONTAL)
        sizer.Add(line, 0, wx.GROW|wx.ALIGN_CENTER_VERTICAL|wx.RIGHT|wx.TOP, 5)
        btnsizer = wx.StdDialogButtonSizer()
        
        ##if (sys.platform != 'win32'):
        ##    btn = wx.ContextHelpButton(self)
        ##    btnsizer.AddButton(btn)
        
        if editfriend is None:
            lbl = self.utility.lang.get('buttons_add')
        else:
            lbl = self.utility.lang.get('buttons_update')
        btn = wx.Button(self, wx.ID_OK, label=lbl)
        btn.SetDefault()
        btnsizer.AddButton(btn)
        self.Bind(wx.EVT_BUTTON, self.OnAddEditFriend, btn)

        btn = wx.Button(self, wx.ID_CANCEL)
        btnsizer.AddButton(btn)
        btnsizer.Realize()

        #sizer.Add(btnsizer, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
        sizer.Add(btnsizer, 0, wx.ALIGN_CENTER|wx.ALL, 5)


        

        self.SetSizer(sizer)
        sizer.Fit(self)
        
    def OnAddEditFriend(self, event):
        name = self.name_text.GetValue()
        ip = str(self.ip_text.GetValue())
        b64permid = str(self.permid_text.GetValue())
        try:
            permid = base64.decodestring( b64permid+'\n' )
        except:
            print_exc()
            permid = ''
        #icon = self.icon_path.GetValue()
        try:
            port = int(self.port_text.GetValue())
        except:
            port = 0
            
        if len(name) == 0:
            self.show_inputerror(self.utility.lang.get('nicknameempty_error'))
        elif len(permid) == 0:
            self.show_inputerror(self.utility.lang.get('friendspermid_error'))
        elif port == 0:
            self.show_inputerror(self.utility.lang.get('friendsport_error'))
        else:
            fdb = FriendDBHandler.getInstance()
            pdb = SynPeerDBHandler.getInstance()
            
            #friend = {'permid':permid, 'ip':ip, 'port':port, 'name':name, 'icon':newiconfilename}
            #friend = {'permid':permid, 'ip':ip, 'port':port, 'name':name}
            friend = {'ip':ip, 'port':port, 'name':name}
            if self.editfriend is not None:
                if self.editfriend['permid'] != permid:
                    fdb.deleteFriend(self.editfriend['permid'])
                    pdb.deletePeer(self.editfriend['permid'])
                    
            #fdb.addExternalFriend(friend)
            fdb.addFriend(permid)
            pdb.addPeer(permid,friend)
            
            event.Skip()    # must be done, otherwise ShowModal() returns wrong error 
            self.Destroy()

        """            
        elif icon != '' and not os.path.exists(icon):
            self.show_inputerror(self.utility.lang.get('fiendsiconnotfound_error'))
        else:
            newiconfilename = ''
            if icon != '':
                ret = self.mm.create_from_file(permid,icon)
                if not ret:
                    self.show_inputerror(self.utility.lang.get('friendsiconnotbmp_error'))
                    return
        """

        
    def OnIconButton(self, evt):
        # get current working directory
        # TODO: record the last opened path in config file
        try:
            path = os.path.join(os.getcwd(), 'icons')
            path = os.path.join(path, 'mugshots')
        except Exception, msg:
            path = ''
            
        # open the image browser dialog
        dlg = ib.ImageDialog(self, path)

        dlg.Centre()

        if dlg.ShowModal() == wx.ID_OK:
            self.icon_path.SetValue(dlg.GetFile())
        else:
            pass

        dlg.Destroy()        

    def show_inputerror(self,txt):
        dlg = wx.MessageDialog(self, txt, 'Invalid Input', wx.OK | wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()

