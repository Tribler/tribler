import wx
import textwrap


class TriblerUpgradeDialog(wx.Dialog):

    UI_UPDATE_INTERVAL = 50  # in milliseconds

    def __init__(self, gui_image_manager, upgrader, ui_update_interval=UI_UPDATE_INTERVAL):
        super(TriblerUpgradeDialog, self).__init__(parent=None, title=u"Tribler Upgrade",
                                                   size=(400, 100), style=wx.CAPTION)

        self._upgrader = upgrader
        self._ui_update_interval = ui_update_interval

        # create layout
        self._bitmap = gui_image_manager.getImage(u'upgrade.png')
        self._static_bitmap = wx.StaticBitmap(self, bitmap=self._bitmap)

        self._text = wx.StaticText(self, label=u"Upgrading Tribler data...")

        hsizer = wx.BoxSizer(wx.HORIZONTAL)
        vbox = wx.BoxSizer(wx.VERTICAL)

        hsizer.Add(self._static_bitmap, 0, wx.ALL | wx.ALIGN_CENTER, 10)
        hsizer.Add(self._text, 0, wx.ALL | wx.ALIGN_CENTER)
        vbox.Add(hsizer, 1, wx.ALL | wx.ALIGN_CENTER, 2)

        self.SetSizer(vbox)

        self.Bind(wx.EVT_CLOSE, self.on_close)

        # start a timer to regularly update the UI
        self._timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_timer, self._timer)
        self._timer.Start(self._ui_update_interval)

    def on_close(self, event):
        # stop and remove the timer
        self._timer.Stop()
        self.EndModal(int(self._upgrader.failed))

    def on_timer(self, event):
        # updates the UI
        self._text.SetLabel(u"\n".join(textwrap.wrap(self._upgrader.current_status, 40)))
        if self._upgrader.is_done:
            self.Close()
