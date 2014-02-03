import wx
from Tribler.Main.vwxGUI.widgets import _set_font
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility


class ConfirmationDialog(wx.Dialog):

    def __init__(self, parent, name, msg_bold='', msg=''):
        wx.Dialog.__init__(self, parent=parent, size=(475, 210), name = name)

        self.checkbox = wx.CheckBox(self, label='Don\'t show this dialog again')
        self.checkbox.SetValue(False)
        messageText1 = wx.StaticText(self, label=msg_bold)
        _set_font(messageText1, fontweight=wx.FONTWEIGHT_BOLD)
        messageText2 = wx.StaticText(self, label=msg)
        messageSizer = wx.BoxSizer(wx.VERTICAL)
        messageSizer.Add(messageText1, 1, wx.EXPAND)
        messageSizer.Add(messageText2, 1, wx.EXPAND)
        messageSizer.Add(self.checkbox, 0, wx.EXPAND | wx.TOP, 15)
        bodySizer = wx.BoxSizer(wx.HORIZONTAL)
        bodySizer.Add(wx.StaticBitmap(self, -1, wx.ArtProvider.GetBitmap(wx.ART_QUESTION, wx.ART_CMN_DIALOG)), 0, wx.ALIGN_TOP | wx.RIGHT, 15)
        bodySizer.Add(messageSizer, 1, wx.EXPAND)
        buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
        confirmButton = wx.Button(self, label='Confirm')
        confirmButton.Bind(wx.EVT_BUTTON, self.OnConfirm)
        cancelButton = wx.Button(self, label='Cancel')
        cancelButton.Bind(wx.EVT_BUTTON, self.OnCancel)
        buttonSizer.AddStretchSpacer()
        buttonSizer.Add(confirmButton)
        buttonSizer.Add(cancelButton, 0, wx.LEFT, 5)
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        mainSizer.Add(bodySizer, 1, wx.EXPAND | wx.ALL, 15)
        mainSizer.Add(buttonSizer, 0, wx.EXPAND | wx.ALL, 15)
        self.SetSizer(mainSizer)

        self.Bind(wx.EVT_CLOSE, self.OnCancel)

    def OnConfirm(self, event):
        if self.checkbox.GetValue():
            GUIUtility.getInstance().WriteGuiSetting('show_%s' % self.GetName(), False)
        self.EndModal(wx.ID_OK)

    def OnCancel(self, event):
        self.EndModal(wx.ID_CANCEL)
