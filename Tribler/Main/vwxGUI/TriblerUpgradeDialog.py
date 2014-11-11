import wx


class TriblerUpgradeDialog(wx.Dialog):

    UI_UPDATE_INTERVAL = 1000  # in milliseconds

    def __init__(self, upgrader, ui_update_interval=UI_UPDATE_INTERVAL, *args, **kwargs):
        super(TriblerUpgradeDialog, self).__init__(*args, **kwargs)

        self._upgrader = upgrader
        self._ui_update_interval = ui_update_interval

        # create layout
        self._text = wx.StaticText(self, label=u"Starting to upgrade...")

        self.Bind(wx.EVT_CLOSE, self.on_close)

        # start a timer to regularly update the UI
        self._timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_timer, self._timer)
        self._timer.Start(self._ui_update_interval)

    def on_close(self, event):
        # stop and remove the timer
        self._timer.Stop()

    def on_timer(self, event):
        # updates the UI
        self._text.SetLabel(self._upgrader)

