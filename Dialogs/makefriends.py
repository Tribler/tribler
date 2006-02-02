import wx
import wx.lib.imagebrowser as ib
from Tribler.CacheDB.CacheDBHandler import FriendDBHandler

class MakeFriendsDialog(wx.Dialog):
    def __init__(self, parent):
        provider = wx.SimpleHelpProvider()
        wx.HelpProvider_Set(provider)
        
        self.utility = parent.utility

        style = wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        pos = wx.DefaultPosition
        size = wx.Size(530, 420)
        #size, split = self.getWindowSettings()
        
        title = self.utility.lang.get('makefriends')
        wx.Dialog.__init__(self, parent, -1, title, size = size, style = style)
        pre = wx.PreDialog()
        pre.SetExtraStyle(wx.DIALOG_EX_CONTEXTHELP)
        pre.Create(parent, -1, title, pos, size, style)
        self.PostCreate(pre)

        sizer = wx.BoxSizer(wx.VERTICAL)

        label = wx.StaticText(self, -1, "Friends List Management")
        sizer.Add(label, 0, wx.ALIGN_CENTRE|wx.ALL, 5)

        # name
        box = wx.BoxSizer(wx.HORIZONTAL)

        label = wx.StaticText(self, -1, "Name:")
        #label.SetHelpText("")
        box.Add(label, 0, wx.ALIGN_CENTRE|wx.ALL, 5)

        self.name_text = wx.TextCtrl(self, -1, "", size=(80,-1))
        self.name_text.SetHelpText("Input the friend's nickname or whatever you'd like to identify him/her")
        box.Add(self.name_text, 1, wx.ALIGN_CENTRE|wx.ALL, 5)

        sizer.Add(box, 0, wx.GROW|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        # ip
        box = wx.BoxSizer(wx.HORIZONTAL)

        label = wx.StaticText(self, -1, "IP:")
        #label.SetHelpText("")
        box.Add(label, 0, wx.ALIGN_CENTRE|wx.ALL, 5)

        self.ip_text = wx.TextCtrl(self, -1, "", size=(80,-1))
        self.ip_text.SetHelpText("Input the friend's IP address, like 202.115.39.65")
        box.Add(self.ip_text, 1, wx.ALIGN_CENTRE|wx.ALL, 5)

        sizer.Add(box, 0, wx.GROW|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        # port
        box = wx.BoxSizer(wx.HORIZONTAL)

        label = wx.StaticText(self, -1, "Port:")
        #label.SetHelpText("")
        box.Add(label, 0, wx.ALIGN_CENTRE|wx.ALL, 5)

        self.port_text = wx.TextCtrl(self, -1, "", size=(80,-1))
        self.port_text.SetHelpText("Input the friend's listening port number")
        box.Add(self.port_text, 1, wx.ALIGN_CENTRE|wx.ALL, 5)

        sizer.Add(box, 0, wx.GROW|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        # permid
        box = wx.BoxSizer(wx.HORIZONTAL)

        label = wx.StaticText(self, -1, "PermID:")
        #label.SetHelpText("")
        box.Add(label, 0, wx.ALIGN_CENTRE|wx.ALL, 5)

        self.permid_text = wx.TextCtrl(self, -1, "", size=(80,-1))
        self.permid_text.SetHelpText("Input the friend's PermID.")
        box.Add(self.permid_text, 1, wx.ALIGN_CENTRE|wx.ALL, 5)

        sizer.Add(box, 0, wx.GROW|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        # picture
        box = wx.BoxSizer(wx.HORIZONTAL)

        label = wx.StaticText(self, -1, "icon:")
        #label.SetHelpText("")
        box.Add(label, 0, wx.ALIGN_CENTRE|wx.ALL, 5)

        self.icon_path = wx.TextCtrl(self, -1, "", size=(80,-1))
        self.icon_path.SetHelpText("Input full path of the friend's icon")
        box.Add(self.icon_path, 3, wx.ALIGN_CENTRE|wx.ALL, 5)
        
        iconbtn = wx.Button(self, -1, label="...")
        iconbtn.SetHelpText("Select an icon")
        box.Add(iconbtn, 1, wx.ALIGN_CENTRE|wx.ALL, 5)
        self.Bind(wx.EVT_BUTTON, self.OnIconButton, iconbtn)

        sizer.Add(box, 0, wx.GROW|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
        
        box = wx.BoxSizer(wx.HORIZONTAL)
        line = wx.StaticLine(self, -1, size=(20,-1), style=wx.LI_HORIZONTAL)
        sizer.Add(line, 0, wx.GROW|wx.ALIGN_CENTER_VERTICAL|wx.RIGHT|wx.TOP, 5)
        btnsizer = wx.StdDialogButtonSizer()
        
        if wx.Platform != "__WXMSW__":
            btn = wx.ContextHelpButton(self)
            btnsizer.AddButton(btn)
        
        btn = wx.Button(self, wx.ID_OK, label="Add a friend")
        btn.SetHelpText("The OK button completes the dialog")
        btn.SetDefault()
        btnsizer.AddButton(btn)
        self.Bind(wx.EVT_BUTTON, self.OnAddFriend, btn)

        btn = wx.Button(self, wx.ID_CANCEL)
        btn.SetHelpText("The Cancel button cnacels the dialog. (Cool, huh?)")
        btnsizer.AddButton(btn)
        btnsizer.Realize()

        sizer.Add(btnsizer, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        self.SetSizer(sizer)
        sizer.Fit(self)
        
    def OnAddFriend(self, evn):
        name = self.name_text.GetValue()
        ip = str(self.ip_text.GetValue())
        permid = str(self.permid_text.GetValue())
        icon = self.icon_path.GetValue()
        try:
            port = int(self.port_text.GetValue())
        except:
            port = 0
        if len(name) == 0 or len(permid) == 0:
            dlg = wx.MessageDialog(self, 'Invalid Input. Name and PermID must be given',
                               'Invalid Input',
                               wx.OK | wx.ICON_INFORMATION)
            dlg.ShowModal()
            dlg.Destroy()
        else:
            fdb = FriendDBHandler()
            friend = {'permid':permid, 'ip':ip, 'port':port, 'name':name, 'icon':icon}
            print "add friend", friend
            fdb.addExternalFriend(friend)
        self.Destroy()
        
    def OnIconButton(self, evt):
        # get current working directory
        path = "E:\\Develop\\workspace\\abc310-buddycast-dlhelp\\icons"

        # open the image browser dialog
        dlg = ib.ImageDialog(self, path)

        dlg.Centre()

        if dlg.ShowModal() == wx.ID_OK:
            print "You Selected File: ", dlg.GetFile()
            self.icon_path.SetValue(dlg.GetFile())
        else:
            print "You pressed Cancel"

        dlg.Destroy()        

        
class FriendList(wx.ListCtrl):
    def __init__(self, parent):
        self.parent = parent
        self.utility = parent.utility
        style = wx.LC_REPORT|wx.LC_VRULES|wx.CLIP_CHILDREN
        wx.ListCtrl.__init__(self, parent, -1, size=wx.Size(300, 200), style=style)
       
       
if __name__ == "__main__":
    class Utility:
        lang = {'makefriends':"Manage Friends List"}

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
            self.Destroy()        

if __name__ == '__main__':
    app = wx.PySimpleApp()
    frame = TestFrame()
#    frame = wx.Frame(None, -1).Show()
    app.MainLoop()
        
