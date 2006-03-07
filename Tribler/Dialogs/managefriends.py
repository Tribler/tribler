# Written by Arno Bakker, Jie Yang
# see LICENSE.txt for license information

import wx
import os
import sys
from traceback import print_exc
import urllib
import webbrowser

from Tribler.CacheDB.CacheDBHandler import FriendDBHandler
from Tribler.__init__ import myinfo
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
    def __init__(self, parent, utility, action):
        self.utility = utility
        self.action = action

        style = wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        pos = wx.DefaultPosition
        size = wx.Size(530, 420)
        #size, split = self.getWindowSettings()
        
        title = self.utility.lang.get('managefriends')
        #wx.Dialog.__init__(self, parent, -1, title, size = size, style = style)
        wx.Panel.__init__(self, parent, -1)

        # 0. Read friends from DB, and figure out who's already helping 
        # for this torrent
        self.friendsdb= FriendDBHandler()
        friends = self.friendsdb.getFriends()

        # 1. Create list of images of all friends
        type = wx.LC_LIST
        # type = wx.LC_REPORT

        imgList = None
        if type != wx.LC_REPORT:
            try:
                imgList = createImageList(self.utility,friends)
            except:
                print_exc()
                # disable icons
                type = wx.LC_REPORT


        for index in range(len(friends)):
            friend = friends[index]
            friend['tempiconindex'] = index

        # 2. Build GUI
        mainbox = wx.BoxSizer(wx.VERTICAL)
        #topbox = wx.BoxSizer(wx.HORIZONTAL)
        botbox = wx.BoxSizer(wx.HORIZONTAL)

        # 3. Friends in top window
        #friendsbox_title = wx.StaticBox(self, -1, self.utility.lang.get('friends'))
        #friendsbox_title = wx.StaticBox(self, -1, '')
        #friendsbox = wx.StaticBoxSizer(friendsbox_title, wx.VERTICAL)
        friendsbox = wx.BoxSizer(wx.VERTICAL)

        self.leftListCtl = FriendList(self,friends,type,imgList)
        #self.leftListCtl.SetToolTipString(self.utility.lang.get('multiannouncehelp'))
        
        friendsbox.Add(self.leftListCtl, 1, wx.EXPAND|wx.TOP, 5)
        #topbox.Add(friendsbox, 0, wx.EXPAND, 5)

        # 4. Buttons in lower window
        button = wx.Button(self, -1, self.utility.lang.get('buttons_add'), style = wx.BU_EXACTFIT)
        #button.SetToolTipString(self.utility.lang.get('requestdlhelp_help'))
        wx.EVT_BUTTON(self, button.GetId(), self.addFriend)
        botbox.Add(button, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 3)

        button = wx.Button(self, -1, self.utility.lang.get('buttons_edit'), style = wx.BU_EXACTFIT)
        #button.SetToolTipString(self.utility.lang.get('stopdlhelp_help'))
        wx.EVT_BUTTON(self, button.GetId(), self.editFriend)
        botbox.Add(button, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 3)

        button = wx.Button(self, -1, self.utility.lang.get('buttons_remove'), style = wx.BU_EXACTFIT)
        #button.SetToolTipString(self.utility.lang.get('stopdlhelp_help'))
        wx.EVT_BUTTON(self, button.GetId(), self.removeFriend)
        botbox.Add(button, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 3)

        ## button = wx.Button(self, -1, self.utility.lang.get('close'), style = wx.BU_EXACTFIT)
        ## #button.SetToolTipString(self.utility.lang.get('stopdlhelp_help'))
        ## wx.EVT_BUTTON(self, button.GetId(), self.close)
        ## botbox.Add(button, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 3)

        # 5. Show GUI
        mainbox.Add(friendsbox, 0, wx.EXPAND|wx.ALIGN_CENTER_HORIZONTAL, 5)
        mainbox.Add(botbox, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.ALL, 5)
        self.SetSizerAndFit(mainbox)


    def addFriend(self, event = None):
        dialog = MakeFriendsDialog(self.utility.frame)
        ret = dialog.ShowModal()
        dialog.Destroy()

        if ret == wx.ID_OK:
            self.phoenix()

    def editFriend(self, event = None):
        selected = self.getSelectedFriends()
        if len(selected) > 1:
            self.show_error("Too many friends selected")
        elif len(selected) == 1:
            dialog = MakeFriendsDialog(self.utility.frame,selected[0])
            ret = dialog.ShowModal()
            dialog.Destroy()
            if ret == wx.ID_OK:
                self.phoenix()

    def show_error(self, err_msg):
        dlg = wx.MessageDialog(self, err_msg,
                               'Warning!',
                               wx.OK | wx.ICON_INFORMATION
                               #wx.YES_NO | wx.NO_DEFAULT | wx.CANCEL | wx.ICON_INFORMATION
                               )
        dlg.ShowModal()
        dlg.Destroy()

    def removeFriend(self, event = None):
        selected = self.getSelectedFriends()
        to_remove = []
        for friend in selected:
            permid = friend['permid']
            to_remove.append(permid)
            self.friendsdb.deleteFriend(permid)
        if len(selected) > 0:
            self.phoenix()

    def getSelectedFriends(self):
        item = -1
        itemList = []
        while 1:
            item = self.leftListCtl.GetNextItem(item,wx.LIST_NEXT_ALL,wx.LIST_STATE_SELECTED)
            if item == -1:
                break
            else:
                itemList.append(item)
        friends = self.leftListCtl.getFriends()
        selected = []
        for item in itemList:
            selected.append(friends[item])
        return selected

    def close(self, event = None):
        self.EndModal(wx.ID_OK)

    def phoenix(self):
        """ Easiest way of keeping the info presented to the user up to date:
            build a new window
        """
        ##self.EndModal(wx.ID_OK)
        self.action.reaction()

    def show_inputerror(self,txt):
        dlg = wx.MessageDialog(self, txt, 'Invalid Input', wx.OK | wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()


################################################################
#
#
################################################################

def createImageList(utility,friends):
    if len(friends) == 0:
        return None
    height = 0
    width = 0
    list = []
    for friend in friends:
        if friend['name'] is not None:
            filename = nickname2iconfilename(utility, friend['name'])
            if not os.access(filename, os.F_OK):
                # fallback name, don't use nickname2... here
                filename = os.path.join(utility.getPath(), 'icons', 'joe32.bmp')
            bm = wx.Bitmap(filename,wx.BITMAP_TYPE_BMP)
            if bm.GetWidth() > width:
                width = bm.GetWidth()
            if bm.GetHeight() > height:
                height = bm.GetHeight()
            list.append(bm)
    imgList = wx.ImageList(width,height)
    for bm in list:
        imgList.Add(bm)
    return imgList

def nickname2iconfilename(utility,name):
        return os.path.join(utility.getConfigPath(), 'icons', name+'.bmp')


################################################################
#
# Class: FriendList
#
# ListCtrl for managing friends
#
################################################################
class FriendList(wx.ListCtrl):
    def __init__(self, parent, friends, type, imgList):

        self.type = type
        self.imgList = imgList
        style = wx.VSCROLL|wx.SIMPLE_BORDER|self.type|wx.LC_VRULES|wx.CLIP_CHILDREN
        if (sys.platform == 'win32'):
            style |= wx.LC_ALIGN_TOP
        wx.ListCtrl.__init__(self, parent, -1, size=wx.Size(200, 300), style=style)

        self.parent = parent
        self.friends = friends
        self.utility = parent.utility

        self.SetImageList(imgList,wx.IMAGE_LIST_SMALL)
        self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnActivated)
        self.loadList()

    def loadList(self):
        if self.type == wx.LC_REPORT:
            try:    # get system font width
                fw = wx.SystemSettings_GetFont(wx.SYS_DEFAULT_GUI_FONT).GetPointSize()+1
            except:
                fw = wx.SystemSettings_GetFont(wx.SYS_SYSTEM_FONT).GetPointSize()+1
            
            self.InsertColumn(0, self.utility.lang.get('name'), format=wx.LIST_FORMAT_CENTER, width=fw*6)

        self.updateAll()
        self.Show(True)

    def updateAll(self):
        self.DeleteAllItems() 
        i = 0;
        for friend in self.friends:
            self.addItem(i,friend)
            i += 1

    def OnActivated(self, event):
        self.parent.editFriend(event)

    def addItem(self,i,friend):
        if self.type != wx.LC_REPORT:
            label = friend['name']
            if not label:
                label = friend['ip']
            self.InsertImageStringItem(i,label,friend['tempiconindex'])
        else:
            self.InsertStringItem(i, friend['name'])

    def removeFriends(self,itemList):
        # Assumption: friends in list are in insert-order, i.e., not sorted afterwards!
        friendList = []
        # Make sure item ids stay the same during delete
        itemList.sort()
        itemList.reverse()
        for item in itemList:
            friend = self.friends[item]
            friendList.append(friend)
            del self.friends[item]
            self.DeleteItem(item)
        return friendList

    def addFriends(self,friendList):
        flag = 0
        i = self.GetItemCount()
        for friend in friendList:
            for chum in self.friends:
                if friend['name'] == chum['name']:
                    flag = 1
                    break
            if flag:
                continue
            self.friends.append(friend)
            self.addItem(i,friend)
            i += 1

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

        ip = self.utility.config.Read('bind')
        if ip is None or ip == '':
            ip = myinfo['ip']
        self.permid_txt = self.utility.lang.get('permid')+": "+permid_for_user(myinfo['permid'])
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
        invitation_body += self.permid_txt + '\r\n'
        invitation_body += self.ip_txt + '\r\n'
        invitation_body += self.port_txt + '\r\n\r\n\r\n'
        
        body = urllib.quote(invitation_body)
        mailToURL = 'mailto:%s?subject=%s&body=%s'%('', subject, body)
        webbrowser.open(mailToURL)
        
        
        