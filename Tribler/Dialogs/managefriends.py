# Written by Arno Bakker, Jie Yang
# see LICENSE.txt for license information

import wx
import os
import sys
from traceback import print_exc
import urllib
import webbrowser

from Tribler.CacheDB.CacheDBHandler import FriendDBHandler,MyDBHandler
from Tribler.Overlay.permid import permid_for_user

from makefriends import MakeFriendsDialog

################################################################
#
# Class: ManageFriendsPanel
#
# Panel for managing friends
#
################################################################
class ManageFriendsPanel(wx.Panel):
    def __init__(self, parent, utility, frame):
        self.utility = utility
        self.frame = frame
        
        style = wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        pos = wx.DefaultPosition
        size = wx.Size(530, 420)
        #size, split = self.getWindowSettings()
        
        title = self.utility.lang.get('managefriends')
        wx.Panel.__init__(self, parent, -1)

        # 1. Read friends from DB, and figure out who's already helping 
        # for this torrent
        self.friendsdb = FriendDBHandler()

        # 2. Build GUI
        mainbox = wx.BoxSizer(wx.VERTICAL)
        
        # 3. Friends in top window
        #friendsbox_title = wx.StaticBox(self, -1, self.utility.lang.get('friends'))
        friendsbox = wx.BoxSizer(wx.VERTICAL)
        self.friendListCtrl = FriendList(self, self.friendsdb)
        friendsbox.Add(self.friendListCtrl, 1, wx.EXPAND|wx.TOP, 5)

        # 4. Buttons in lower window
        botbox = wx.BoxSizer(wx.HORIZONTAL)
        button = wx.Button(self, -1, self.utility.lang.get('buttons_add'), style = wx.BU_EXACTFIT)
        wx.EVT_BUTTON(self, button.GetId(), self.addFriend)
        botbox.Add(button, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 3)

        button = wx.Button(self, -1, self.utility.lang.get('buttons_edit'), style = wx.BU_EXACTFIT)
        wx.EVT_BUTTON(self, button.GetId(), self.editFriend)
        botbox.Add(button, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 3)

        button = wx.Button(self, -1, self.utility.lang.get('buttons_remove'), style = wx.BU_EXACTFIT)
        wx.EVT_BUTTON(self, button.GetId(), self.removeFriend)
        botbox.Add(button, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 3)

        # 5. Show GUI
        mainbox.Add(friendsbox, 1, wx.EXPAND|wx.ALIGN_CENTER_HORIZONTAL, 5)
        mainbox.Add(botbox, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.ALL, 5)
        self.SetSizerAndFit(mainbox)


    def addFriend(self, event = None):
        dialog = MakeFriendsDialog(self,self.utility)
        ret = dialog.ShowModal()
        if ret == wx.ID_OK:
            self.updateView()
            dialog.Destroy()
            
    def editFriend(self, event = None):
        selected = self.getSelectedFriends()
        if not selected:
            return
        dialog = MakeFriendsDialog(self, selected[0])
        ret = dialog.ShowModal()
        if ret == wx.ID_OK:
            self.updateView()
            dialog.Destroy()

    def removeFriend(self, event = None):
        selected = self.getSelectedFriends()
        if not selected:
            return
        to_remove = []
        for friend in selected:
            permid = friend['permid']
            to_remove.append(permid)
            self.friendsdb.deleteFriend(permid)
        if len(selected) > 0:
            self.updateView()

    def show_error(self, err_msg):
        dlg = wx.MessageDialog(self, err_msg,
                               'Warning!',
                               wx.OK | wx.ICON_INFORMATION
                               #wx.YES_NO | wx.NO_DEFAULT | wx.CANCEL | wx.ICON_INFORMATION
                               )
        dlg.ShowModal()
        dlg.Destroy()

    def getSelectedFriends(self):
        item = -1
        itemList = []
        while 1:
            item = self.friendListCtrl.GetNextItem(item,wx.LIST_NEXT_ALL,wx.LIST_STATE_SELECTED)
            if item == -1:
                break
            else:
                itemList.append(item)
        friends = self.friendListCtrl.getFriends()
        selected = []
        for item in itemList:
            selected.append(friends[item])
        return selected

    def updateView(self, updateBuddyFrame=True):
        """ Easiest way of keeping the info presented to the user up to date:
            build a new window
        """
        self.friendListCtrl.updateView()
        if updateBuddyFrame:
            self.frame.updateBuddyPanel(self.friendListCtrl.getFriends())

    def show_inputerror(self,txt):
        dlg = wx.MessageDialog(self, txt, 'Invalid Input', wx.OK | wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()


################################################################
#
# Class: FriendList
#
# ListCtrl for managing friends
#
################################################################
class FriendList(wx.ListCtrl):
    def __init__(self, parent, friendsdb):
        self.parent = parent
        self.utility = parent.utility
        self.friendsdb = friendsdb
        self.type = wx.LC_REPORT
        style = self.type|wx.VSCROLL|wx.SIMPLE_BORDER|wx.LC_VRULES|wx.CLIP_CHILDREN
        if (sys.platform == 'win32'):
            style |= wx.LC_ALIGN_TOP
        wx.ListCtrl.__init__(self, parent, -1, style=style)
        self.SetMinSize(wx.Size(200, 300))
        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnActivated)
        self.updateView()
    
    def updateView(self):
        self.friends = self.friendsdb.getFriends()
        for index in range(len(self.friends)):
            self.friends[index]['tempiconindex'] = index
            if not self.friends[index]['name']:
                self.friends[index]['name'] = self.friends[index]['ip']
        
        self.ClearAll()
        if self.type != wx.LC_REPORT:
            try:
                self.updateImageList()
            except:
                print_exc()
                # disable icons
                self.type = wx.LC_REPORT
                self.updateReportList()
        else:
            self.updateReportList()
        self.Refresh()

    def updateImageList(self):
        return
        
        self.SetWindowStyleFlag(self.type)
        
        self.imgList = createImageList(self.utility, self.friends)
        self.AssignImageList(self.imgList, wx.IMAGE_LIST_SMALL)
        self.loadList()
        
    def updateReportList(self):
        self.SetWindowStyleFlag(self.type)
        
        if not hasattr(self, 'fw'):
            try:    # get system font width
                self.fw = wx.SystemSettings_GetFont(wx.SYS_DEFAULT_GUI_FONT).GetPointSize()+1
            except:
                self.fw = wx.SystemSettings_GetFont(wx.SYS_SYSTEM_FONT).GetPointSize()+1
            
        self.InsertColumn(0, self.utility.lang.get('name'), format=wx.LIST_FORMAT_CENTER, width=self.fw*20)
        self.loadList()
        
    def loadList(self):
        i = 0;
        for friend in self.friends:
            if self.type != wx.LC_REPORT:
                self.InsertImageStringItem(i,friend['name'],friend['tempiconindex'])
            else:
                self.InsertStringItem(i, friend['name'])
            i += 1
        
    def OnActivated(self, event):
        self.parent.editFriend(event)

    def getFriends(self):
        return self.friends

################################################################
#
# Class: MyInfoDialog
#
# Panel with user's info, to give to others to become friends
#
################################################################
class MyInfoDialog(wx.Dialog):
    def __init__(self, parent, utility):
        self.utility = utility

        style = wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        pos = wx.DefaultPosition
        size = wx.Size(530, 420)
        
        title = self.utility.lang.get('myinfo')
        wx.Dialog.__init__(self, parent, -1, title, size = size, style = style)

        # 1. Build My Info
        mainbox = wx.BoxSizer(wx.VERTICAL)

        # my info
        myinfobox_title = wx.StaticBox(self, -1, self.utility.lang.get('myinfo'))
        myinfobox = wx.StaticBoxSizer(myinfobox_title, wx.VERTICAL)

        self.my_db = MyDBHandler()
        ip = self.utility.config.Read('bind')
        if ip is None or ip == '':
            ip = self.my_db.getMyIP()
        permid = self.my_db.getMyPermid()
        self.permid_txt = self.utility.lang.get('permid')+": "+permid_for_user(permid)
        self.ip_txt = self.utility.lang.get('ipaddress')+": "+ip

        # port = self.utility.controller.listen_port
        port = self.utility.config.Read('minport', 'int')
        self.port_txt = self.utility.lang.get('portnumber')+" "+str(port)

        if True:
            # Make it copy-and-paste able
            self.textctrl = wx.TextCtrl(self, -1, size = (640, 100), style = wx.TE_MULTILINE|wx.TE_DONTWRAP|wx.TE_READONLY)
            self.textctrl.AppendText( self.permid_txt + '\n' );
            self.textctrl.AppendText( self.ip_txt + '\n' );
            self.textctrl.AppendText( self.port_txt + '\n' );
            myinfobox.Add( self.textctrl, 0, wx.EXPAND|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
        else:
            label = wx.StaticText(self, -1, self.permid_txt )
            myinfobox.Add( label, 0, wx.EXPAND|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

            label = wx.StaticText(self, -1, self.ip_txt )
            myinfobox.Add( label, 0, wx.EXPAND|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

            label = wx.StaticText(self, -1, self.port_txt )
            myinfobox.Add( label, 0, wx.EXPAND|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)


       # 1.5 Explanatory text
        botbox = wx.BoxSizer(wx.VERTICAL)

        msg = self.utility.lang.get('myinfo_explanation')
        botbox.Add(wx.StaticText(self, -1, msg), 0, wx.EXPAND|wx.ALIGN_LEFT|wx.ALL, 5)

        # 2. Invitation and Close buttons
        btnbox = wx.BoxSizer(wx.HORIZONTAL)
        invitation_btn = wx.Button(self, -1, self.utility.lang.get('invitationbtn'), style = wx.BU_EXACTFIT)
        #button.SetToolTipString(self.utility.lang.get('stopdlhelp_help'))
        wx.EVT_BUTTON(self, invitation_btn.GetId(), self.emailFriend)
        btnbox.Add(invitation_btn, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.ALL, 3)
        
        button = wx.Button(self, -1, self.utility.lang.get('close'), style = wx.BU_EXACTFIT)
        #button.SetToolTipString(self.utility.lang.get('stopdlhelp_help'))
        wx.EVT_BUTTON(self, button.GetId(), self.close)
        btnbox.Add(button, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.ALL, 3)

        # 3. Show GUI
        mainbox.Add(myinfobox, 0, wx.EXPAND)
        mainbox.Add(botbox, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.ALL, 5)
        mainbox.Add(btnbox, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.ALL, 5)
        self.SetSizerAndFit(mainbox)

    def close(self, event = None):
        self.EndModal(wx.ID_OK)

    def emailFriend(self, event):
        subject = self.utility.lang.get('invitation_subject')
        invitation_body = self.utility.lang.get('invitation_body')
        invitation_body = invitation_body.replace('\\n', '\n')
        invitation_body += self.permid_txt + '\n'
        invitation_body += self.ip_txt + '\n'
        invitation_body += self.port_txt + '\n\n\n'
       
        if sys.platform == "darwin":
            body = invitation_body.replace('\\r','\r')
            body = invitation_body.replace('\\n','\n')
        else:
            body = urllib.quote(invitation_body)
        mailToURL = 'mailto:%s?subject=%s&body=%s'%('', subject, body)
        webbrowser.open(mailToURL)
        
        