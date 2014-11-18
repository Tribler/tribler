import wx


class TriblerUpgradeDialog(wx.Dialog):

    UI_UPDATE_INTERVAL = 50  # in milliseconds

    def __init__(self, upgrader, ui_update_interval=UI_UPDATE_INTERVAL):
        super(TriblerUpgradeDialog, self).__init__(parent=None, size=(400, 100))

        self._upgrader = upgrader
        self._ui_update_interval = ui_update_interval

        # create layout
        self._text = wx.StaticText(self, label=u"Upgrading Tribler data...")

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        vbox = wx.BoxSizer(wx.VERTICAL)
        hsizer.Add(self._text, 0, wx.ALL | wx.ALIGN_CENTER)
        vbox.Add(hsizer, 1, wx.ALL | wx.ALIGN_CENTER, 5)

        self.SetSizer(vbox)

        self.Bind(wx.EVT_CLOSE, self.on_close)

        # start a timer to regularly update the UI
        self._timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_timer, self._timer)
        self._timer.Start(self._ui_update_interval)

    def on_close(self, event):
        # stop and remove the timer
        self._timer.Stop()
        self.EndModal(int(self._upgrader.has_error))

    def on_timer(self, event):
        # updates the UI
        self._text.SetLabel(self._upgrader.current_status)
        if self._upgrader.is_done:
            self.Close()
