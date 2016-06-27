# Written by Egbert Bouman

import wx

from Tribler.Main.Utility.GuiDBHandler import startWorker, GUI_PRI_DISPERSY
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Policies.BoostingManager import BoostingManager


class AddBoostingSource(wx.Dialog):

    def __init__(self, parent):
        wx.Dialog.__init__(self, parent, -1, 'Add boosting source', size=(275, 275), name="AddBoostingSourceDialog")

        self.guiutility = GUIUtility.getInstance()
        self.channels = []
        self.source = ''

        text = wx.StaticText(self, -1, 'Please enter a RSS feed URL or directory to start boosting swarms:')
        # self.channel_radio = wx.RadioButton(self, -1, 'Subscribed Channel:', style=wx.RB_GROUP)
        # self.channel_choice = wx.Choice(self, -1)
        # self.channel_choice.Bind(wx.EVT_CHOICE, lambda evt: self.channel_radio.SetValue(True))

        self.rss_feed_radio = wx.RadioButton(self, -1, 'RSS feed:')
        self.rss_feed_edit = wx.TextCtrl(self, -1)
        self.rss_feed_edit.Bind(wx.EVT_TEXT, lambda evt: self.rss_feed_radio.SetValue(True))

        self.rss_dir_radio = wx.RadioButton(self, -1, 'RSS dir:')
        self.rss_dir_edit = wx.TextCtrl(self, -1)
        self.rss_dir_edit.Bind(wx.EVT_TEXT, lambda evt: self.rss_dir_radio.SetValue(True))

        self.archive_check = wx.CheckBox(self, -1, "Archive mode")
        ok_btn = wx.Button(self, -1, "OK")
        ok_btn.Bind(wx.EVT_BUTTON, self.OnOK)
        cancel_btn = wx.Button(self, -1, "Cancel")
        cancel_btn.Bind(wx.EVT_BUTTON, self.OnCancel)

        sourceGrid = wx.FlexGridSizer(2, 2, 0, 0)
        sourceGrid.AddGrowableCol(1)
        # sourceGrid.Add(self.channel_radio, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT | wx.TOP, 5)
        # sourceGrid.Add(self.channel_choice, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 5)
        sourceGrid.Add(self.rss_feed_radio, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT | wx.TOP, 5)
        sourceGrid.Add(self.rss_feed_edit, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 5)
        sourceGrid.Add(self.rss_dir_radio, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT | wx.TOP, 5)
        sourceGrid.Add(self.rss_dir_edit, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 5)
        btnSizer = wx.BoxSizer(wx.HORIZONTAL)
        btnSizer.Add(ok_btn, 0, wx.RIGHT | wx.TOP | wx.BOTTOM, 5)
        btnSizer.Add(cancel_btn, 0, wx.ALL, 5)
        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.Add(text, 0, wx.EXPAND | wx.ALL, 5)
        vSizer.Add(sourceGrid, 0, wx.EXPAND | wx.ALL, 5)
        vSizer.AddSpacer((-1, 5))
        vSizer.Add(self.archive_check, 0, wx.LEFT | wx.RIGHT, 10)
        vSizer.AddStretchSpacer()
        vSizer.Add(btnSizer, 0, wx.EXPAND | wx.ALL, 5)
        self.SetSizer(vSizer)

        # def do_db():
        #     return self.guiutility.channelsearch_manager.getAllChannels()
        #
        # def do_gui(delayedResult):
        #     _, channels = delayedResult.get()
        #     self.channels = sorted([(channel.name, channel.dispersy_cid) for channel in channels])
        #     self.channel_choice.SetItems([channel[0] for channel in self.channels])
        #
        # startWorker(do_gui, do_db, retryOnBusy=True, priority=GUI_PRI_DISPERSY)

    def OnOK(self, event):
        # if self.channel_radio.GetValue():
        #     selection = self.channel_choice.GetSelection()
        #     if selection < len(self.channels):
        #         self.source = self.channels[selection][1]
        # el

        if self.rss_feed_radio.GetValue():
            self.source = self.rss_feed_edit.GetValue()
        else:
            self.source = self.rss_dir_edit.GetValue()

        self.guiutility.Notify(
            "Successfully add source for credit mining %s" % self.source)

        self.EndModal(wx.ID_OK)

    def OnCancel(self, event):
        self.EndModal(wx.ID_CANCEL)

    def GetValue(self):
        return self.source, self.archive_check.GetValue()


class RemoveBoostingSource(wx.Dialog):

    def __init__(self, parent):
        wx.Dialog.__init__(self, parent, -1, 'Remove boosting source', size=(475, 135), name="RemoveBoostingSourceDialog")

        self.guiutility = GUIUtility.getInstance()
        self.boosting_manager = BoostingManager.get_instance()
        self.sources = []
        self.source = ''

        text = wx.StaticText(self, -1, 'Please select the boosting source you wish to remove:')
        self.source_label = wx.StaticText(self, -1, 'Source:', style=wx.RB_GROUP)
        self.source_choice = wx.Choice(self, -1)
        ok_btn = wx.Button(self, -1, "OK")
        ok_btn.Bind(wx.EVT_BUTTON, self.OnOK)
        cancel_btn = wx.Button(self, -1, "Cancel")
        cancel_btn.Bind(wx.EVT_BUTTON, self.OnCancel)

        sourceSizer = wx.BoxSizer(wx.HORIZONTAL)
        sourceSizer.Add(self.source_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT | wx.TOP, 5)
        sourceSizer.Add(self.source_choice, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 5)
        btnSizer = wx.BoxSizer(wx.HORIZONTAL)
        btnSizer.Add(ok_btn, 0, wx.RIGHT | wx.TOP | wx.BOTTOM, 5)
        btnSizer.Add(cancel_btn, 0, wx.ALL, 5)
        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.Add(text, 0, wx.EXPAND | wx.ALL, 5)
        vSizer.Add(sourceSizer, 0, wx.EXPAND | wx.ALL, 5)
        vSizer.AddStretchSpacer()
        vSizer.Add(btnSizer, 0, wx.EXPAND | wx.ALL, 5)
        self.SetSizer(vSizer)

        channels = []
        for source in self.boosting_manager.boosting_sources.keys():
            if source.startswith('http://'):
                self.sources.append(source)
            elif len(source) == 20:
                channels.append(source)

        def do_db():
            return self.guiutility.channelsearch_manager.getChannelsByCID(channels)

        def do_gui(delayedResult):
            _, channels = delayedResult.get()
            channels = sorted([(channel.name, channel.dispersy_cid) for channel in channels])
            self.sources = self.sources + [channel[1] for channel in channels]
            self.source_choice.AppendItems([channel[0] for channel in channels])

        startWorker(do_gui, do_db, retryOnBusy=True, priority=GUI_PRI_DISPERSY)

        self.source_choice.SetItems(self.sources)

    def OnOK(self, event):
        selection = self.source_choice.GetSelection()
        if selection < len(self.sources):
            self.source = self.sources[selection]
        self.EndModal(wx.ID_OK)

    def OnCancel(self, event):
        self.EndModal(wx.ID_CANCEL)

    def GetValue(self):
        return self.source
