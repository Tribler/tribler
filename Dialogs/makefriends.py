# Written by Jie Yang
# see LICENSE.txt for license information

import os
import sys
import base64
from traceback import print_exc
from shutil import copy2
import wx
import wx.lib.imagebrowser as ib
from Tribler.CacheDB.CacheDBHandler import FriendDBHandler
from Tribler.Overlay.permid import permid_for_user
import managefriends

DEBUG = False

class MakeFriendsDialog(wx.Dialog):
    def __init__(self, parent, editfriend = None):
        provider = wx.SimpleHelpProvider()
        wx.HelpProvider_Set(provider)
        
        self.utility = parent.utility
        self.editfriend = editfriend

        style = wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        pos = wx.DefaultPosition
        size = wx.Size(530, 420)
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

        label = wx.StaticText(self, -1, "Name:")
        #label.SetHelpText("")
        box.Add(label, 0, wx.ALIGN_CENTRE|wx.ALL, 5)

        if editfriend is not None:
            name = editfriend['name']
        else:   
            name = ''
        self.name_text = wx.TextCtrl(self, -1, name, size=(80,-1))
        self.name_text.SetHelpText("Input the friend's nickname or whatever you'd like to identify him/her")
        box.Add(self.name_text, 1, wx.ALIGN_CENTRE|wx.ALL, 5)

        sizer.Add(box, 0, wx.GROW|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        # ip
        box = wx.BoxSizer(wx.HORIZONTAL)

        label = wx.StaticText(self, -1, "IP:")
        #label.SetHelpText("")
        box.Add(label, 0, wx.ALIGN_CENTRE|wx.ALL, 5)

        if editfriend is not None:
            ip = editfriend['ip']
        else:   
            ip = ''
        self.ip_text = wx.TextCtrl(self, -1, ip, size=(80,-1))
        self.ip_text.SetHelpText("Input the friend's IP address, e.g. 202.115.39.65")
        box.Add(self.ip_text, 1, wx.ALIGN_CENTRE|wx.ALL, 5)

        sizer.Add(box, 0, wx.GROW|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        # port
        box = wx.BoxSizer(wx.HORIZONTAL)

        label = wx.StaticText(self, -1, "Port:")
        #label.SetHelpText("")
        box.Add(label, 0, wx.ALIGN_CENTRE|wx.ALL, 5)

        if editfriend is not None:
            port_str = str(editfriend['port'])
        else:   
            port_str = ''
        self.port_text = wx.TextCtrl(self, -1, port_str, size=(80,-1))
        self.port_text.SetHelpText("Input the friend's listening port number")
        box.Add(self.port_text, 1, wx.ALIGN_CENTRE|wx.ALL, 5)

        sizer.Add(box, 0, wx.GROW|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        # permid
        box = wx.BoxSizer(wx.HORIZONTAL)

        label = wx.StaticText(self, -1, "PermID:")
        #label.SetHelpText("")
        box.Add(label, 0, wx.ALIGN_CENTRE|wx.ALL, 5)

        if editfriend is not None:
            permid = permid_for_user(editfriend['permid'])
        else:   
            permid = ''
        self.permid_text = wx.TextCtrl(self, -1, permid, size=(80,-1))
        self.permid_text.SetHelpText("Input the friend's PermID.")
        box.Add(self.permid_text, 1, wx.ALIGN_CENTRE|wx.ALL, 5)

        sizer.Add(box, 0, wx.GROW|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        # picture
        box = wx.BoxSizer(wx.HORIZONTAL)

        label = wx.StaticText(self, -1, "Icon (BMP format):")
        #label.SetHelpText("")
        box.Add(label, 0, wx.ALIGN_CENTRE|wx.ALL, 5)

        self.icon_path = wx.TextCtrl(self, -1, "", size=(80,-1))
        self.icon_path.SetHelpText("Input full path of the friend's icon")
        box.Add(self.icon_path, 3, wx.ALIGN_CENTRE|wx.ALL, 5)
        
        iconbtn = wx.Button(self, -1, label="Browse")
        iconbtn.SetHelpText("Select an icon")
        box.Add(iconbtn, 1, wx.ALIGN_CENTRE|wx.ALL, 5)
        self.Bind(wx.EVT_BUTTON, self.OnIconButton, iconbtn)

        sizer.Add(box, 0, wx.GROW|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
        
        box = wx.BoxSizer(wx.HORIZONTAL)
        line = wx.StaticLine(self, -1, size=(20,-1), style=wx.LI_HORIZONTAL)
        sizer.Add(line, 0, wx.GROW|wx.ALIGN_CENTER_VERTICAL|wx.RIGHT|wx.TOP, 5)
        btnsizer = wx.StdDialogButtonSizer()
        
        if (sys.platform != 'win32'):
            btn = wx.ContextHelpButton(self)
            btnsizer.AddButton(btn)
        
        if editfriend is None:
            lbl = self.utility.lang.get('buttons_add')
        else:
            lbl = self.utility.lang.get('buttons_update')
        btn = wx.Button(self, wx.ID_OK, label=lbl)
        btn.SetHelpText("The OK button completes the dialog")
        btn.SetDefault()
        btnsizer.AddButton(btn)
        self.Bind(wx.EVT_BUTTON, self.OnAddFriend, btn)

        btn = wx.Button(self, wx.ID_CANCEL)
        btn.SetHelpText("The Cancel button cancels the dialog. (Cool, huh?)")
        btnsizer.AddButton(btn)
        btnsizer.Realize()

        sizer.Add(btnsizer, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        self.SetSizer(sizer)
        sizer.Fit(self)
        
    def OnAddFriend(self, evn):
        name = self.name_text.GetValue()
        ip = str(self.ip_text.GetValue())
        b64permid = str(self.permid_text.GetValue())
        try:
            permid = base64.decodestring( b64permid+'\n' )
        except:
            print_exc()
            permid = ''
        icon = self.icon_path.GetValue()
        try:
            port = int(self.port_text.GetValue())
        except:
            port = 0
            
        if len(name) == 0:
            self.show_inputerror( 'Invalid input. Name is empty' )
        elif len(permid) == 0:
            self.show_inputerror( 'Invalid input. PermID must be given (in BASE64, single line)' )
        elif port == 0:
            self.show_inputerror( 'Invalid input. Port is not a number' )
        elif icon != '' and not os.path.exists(icon):
            self.show_inputerror( 'Invalid input. Icon file does not exist' )
        else:
            if icon != '':
                try:
                    copy2(os.path.normpath(icon), managefriends.nickname2iconfilename(self.utility,name))
                except:
                    print_exc()
                icon = ''

            fdb = FriendDBHandler()
            friend = {'permid':permid, 'ip':ip, 'port':port, 'name':name, 'icon':icon}
            if DEBUG:
                print "add friend", friend

            if self.editfriend is not None:
                if self.editfriend['permid'] != permid:
                    fdb.deleteFriend(self.editfriend['permid'])
                elif self.editfriend['name'] != name:
                    # Renamed the dude, rename icon as well, if present
                    oldfilename = managefriends.nickname2iconfilename(self.utility,self.editfriend['name'])
                    newfilename = managefriends.nickname2iconfilename(self.utility,name)
                    try:
                        if os.path.exists(oldfilename):
                            os.rename(oldfilename,newfilename)
                    except:
                        print_exc()
                        pass

            fdb.addExternalFriend(friend)
            self.EndModal(wx.ID_OK)
        
    def OnIconButton(self, evt):
        # get current working directory
        try:
            path = os.getcwd()
        except:
            path = ''

        # open the image browser dialog
        dlg = ib.ImageDialog(self, path)

        dlg.Centre()

        if dlg.ShowModal() == wx.ID_OK:
            if DEBUG:
                print "You Selected File: ", dlg.GetFile()
            self.icon_path.SetValue(dlg.GetFile())
        else:
            if DEBUG:
                print "You pressed Cancel"
            pass

        dlg.Destroy()        

    def show_inputerror(self,txt):
        dlg = wx.MessageDialog(self, txt, 'Invalid Input', wx.OK | wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()


        
class FriendList(wx.ListCtrl):
    def __init__(self, parent):
        self.parent = parent
        self.utility = parent.utility
        style = wx.LC_REPORT|wx.LC_VRULES|wx.CLIP_CHILDREN
        wx.ListCtrl.__init__(self, parent, -1, size=wx.Size(300, 200), style=style)
       
       
if __name__ == "__main__":
    class Utility:
        lang = {'makefriend':" Make Friend"}

    class TestFrame(wx.Frame):
        def __init__(self):
            self.utility = Utility()
            size = wx.Size(800, 500)
            wx.Frame.__init__(self, None, -1, "Test Frame", wx.DefaultPosition, size)
           
            self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)
            dialog = MakeFriendsDialog(self)
            dialog.ShowModal()
            self.Destroy()

        def OnCloseWindow(self, event = None):
            self.EndModal(wx.ID_OK)     

if __name__ == '__main__':
    app = wx.PySimpleApp()
    frame = TestFrame()
#    frame = wx.Frame(None, -1).Show()
    app.MainLoop()
        
