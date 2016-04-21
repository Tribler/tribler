import wx
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.widgets import _set_font


class NewVersionDialog(wx.Dialog):

    def __init__(self, version, parent, name, msg_bold='', msg='', title='', center_on_frame=True):
        wx.Dialog.__init__(self, parent=parent, size=(475, 210), name=name)

        self.version = version
        self.SetTitle(title)
        messageSizer = wx.BoxSizer(wx.VERTICAL)

        if msg_bold:
            messageText1 = wx.StaticText(self, label=msg_bold)
            _set_font(messageText1, fontweight=wx.FONTWEIGHT_BOLD)
            messageSizer.Add(messageText1, 1, wx.EXPAND)
        if msg:
            messageText2 = wx.StaticText(self, label=msg)
            messageSizer.Add(messageText2, 1, wx.EXPAND | wx.TOP, 10 if msg_bold else 0)

        bodySizer = wx.BoxSizer(wx.HORIZONTAL)
        bodySizer.Add(wx.StaticBitmap(self, -1, wx.ArtProvider.GetBitmap(
            wx.ART_INFORMATION, wx.ART_CMN_DIALOG)), 0, wx.ALIGN_TOP | wx.RIGHT, 25)
        bodySizer.Add(messageSizer, 1, wx.EXPAND)

        buttonSizer = wx.StdDialogButtonSizer()
        okButton = wx.Button(self, wx.ID_OK, label='Ok')
        okButton.Bind(wx.EVT_BUTTON, self.OnOk)
        laterButton = wx.Button(self, id=wx.ID_CANCEL, label='Later')
        laterButton.Bind(wx.EVT_BUTTON, self.OnLater)
        ignoreButton = wx.Button(self, id=wx.ID_IGNORE, label='Ignore')
        ignoreButton.Bind(wx.EVT_BUTTON, self.OnIgnore)
        buttonSizer.Add(ignoreButton)
        buttonSizer.Add(laterButton)
        buttonSizer.Add(okButton)
        buttonSizer.Realize()

        mainSizer = wx.BoxSizer(wx.VERTICAL)
        mainSizer.Add(bodySizer, 1, wx.EXPAND | wx.ALL, 10)
        mainSizer.Add(buttonSizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        self.SetSizerAndFit(mainSizer)
        if center_on_frame:
            x, y, w, h = GUIUtility.getInstance().frame.GetScreenRect()
            self.SetPosition((x + ((w - self.GetSize().x) / 2), y + ((h - self.GetSize().y) / 2)))

    def OnOk(self, event):
        import webbrowser
        webbrowser.open("https://tribler.org")
        self.EndModal(wx.ID_OK)

    def OnLater(self, event):
        self.EndModal(wx.ID_CANCEL)

    def OnIgnore(self, event):
        GUIUtility.getInstance().utility.write_config('last_reported_version', str(self.version))
        self.EndModal(wx.ID_IGNORE)
