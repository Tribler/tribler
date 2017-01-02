"""
This module contains wx dialog gui for adding/removing boosting source

Written by Egbert Bouman and Ardhi Putra Pratama H
"""

import wx

from Tribler.Core.CreditMining.BoostingSource import ChannelSource
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility


class AddBoostingSource(wx.Dialog):
    """
    Class for adding the source for credit mining
    """

    def __init__(self, parent):
        wx.Dialog.__init__(self, parent, -1, 'Add boosting source', size=(475, 275), name="AddBoostingSourceDialog")

        self.channels = []
        self.source = ''

        text = wx.StaticText(self, -1, 'Please enter a RSS feed URL or directory to start boosting swarms:')

        self.rss_feed_radio = wx.RadioButton(self, -1, 'RSS feed:')
        self.rss_feed_edit = wx.TextCtrl(self, -1)
        self.rss_feed_edit.Bind(wx.EVT_TEXT, lambda evt: self.rss_feed_radio.SetValue(True))

        self.rss_dir_radio = wx.RadioButton(self, -1, 'Torrents local directory:')
        self.rss_dir_edit = wx.TextCtrl(self, -1)
        self.rss_dir_edit.Bind(wx.EVT_TEXT, lambda evt: self.rss_dir_radio.SetValue(True))
        self.rss_dir_edit.Bind(wx.EVT_LEFT_DOWN, self.on_open_dir)

        self.archive_check = wx.CheckBox(self, -1, "Archive mode")
        ok_btn = wx.Button(self, -1, "OK")
        ok_btn.Bind(wx.EVT_BUTTON, self.on_added_source)
        cancel_btn = wx.Button(self, -1, "Cancel")
        cancel_btn.Bind(wx.EVT_BUTTON, self.on_cancel)

        source_grid = wx.FlexGridSizer(2, 2, 0, 0)
        source_grid.AddGrowableCol(1)
        source_grid.Add(self.rss_feed_radio, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT | wx.TOP, 5)
        source_grid.Add(self.rss_feed_edit, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 5)
        source_grid.Add(self.rss_dir_radio, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT | wx.TOP, 5)
        source_grid.Add(self.rss_dir_edit, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 5)
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.Add(ok_btn, 0, wx.RIGHT | wx.TOP | wx.BOTTOM, 5)
        btn_sizer.Add(cancel_btn, 0, wx.ALL, 5)
        v_sizer = wx.BoxSizer(wx.VERTICAL)
        v_sizer.Add(text, 0, wx.EXPAND | wx.ALL, 5)
        v_sizer.Add(source_grid, 0, wx.EXPAND | wx.ALL, 5)
        v_sizer.AddSpacer((-1, 5))
        v_sizer.Add(self.archive_check, 0, wx.LEFT | wx.RIGHT, 10)
        v_sizer.AddStretchSpacer()
        v_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 5)
        self.SetSizer(v_sizer)

    def on_added_source(self, _):
        """
        this function called when user clicked 'OK' button for adding source
        """
        if self.rss_feed_radio.GetValue():
            self.source = self.rss_feed_edit.GetValue()
        else:
            self.source = self.rss_dir_edit.GetValue()

        GUIUtility.getInstance().Notify(
            "Successfully add source for credit mining %s" % self.source)

        self.EndModal(wx.ID_OK)

    def on_cancel(self, _):
        """
        this function called when user clicked 'Cancel' button when adding source
        thus, cancelled
        """
        self.EndModal(wx.ID_CANCEL)

    def get_value(self):
        """
        get the value of new source
        """
        return self.source, self.archive_check.GetValue()

    def on_open_dir(self, event):
        """
        opening local directory for choosing directory source
        """
        rss_dir_dialog = wx.DirDialog(self, "Choose a directory:",
                                      style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST)

        if rss_dir_dialog.ShowModal() == wx.ID_OK:
            self.rss_dir_edit.SetValue(rss_dir_dialog.GetPath())


class RemoveBoostingSource(wx.Dialog):
    """
    Class for adding the source for credit mining
    """
    def __init__(self, parent):
        wx.Dialog.__init__(self, parent, -1, 'Remove boosting source', size=(475, 135),
                           name="RemoveBoostingSourceDialog")

        self.guiutility = GUIUtility.getInstance()
        self.boosting_manager = self.guiutility.utility.session.lm.boosting_manager
        self.sources = []
        self.source = ''

        text = wx.StaticText(self, -1, 'Please select the boosting source you wish to remove:')
        self.source_label = wx.StaticText(self, -1, 'Source:')
        self.source_choice = wx.Choice(self, -1)
        ok_btn = wx.Button(self, -1, "OK")
        ok_btn.Bind(wx.EVT_BUTTON, self.on_remove_source)
        cancel_btn = wx.Button(self, -1, "Cancel")
        cancel_btn.Bind(wx.EVT_BUTTON, self.on_cancel)

        sourcesizer = wx.BoxSizer(wx.HORIZONTAL)
        sourcesizer.Add(self.source_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT | wx.TOP, 5)
        sourcesizer.Add(self.source_choice, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 5)
        btnsizer = wx.BoxSizer(wx.HORIZONTAL)
        btnsizer.Add(ok_btn, 0, wx.RIGHT | wx.TOP | wx.BOTTOM, 5)
        btnsizer.Add(cancel_btn, 0, wx.ALL, 5)
        vsizer = wx.BoxSizer(wx.VERTICAL)
        vsizer.Add(text, 0, wx.EXPAND | wx.ALL, 5)
        vsizer.Add(sourcesizer, 0, wx.EXPAND | wx.ALL, 5)
        vsizer.AddStretchSpacer()
        vsizer.Add(btnsizer, 0, wx.EXPAND | wx.ALL, 5)
        self.SetSizer(vsizer)

        # retrieve all source except channel source
        self.sources = [s.get_source_text() for s in self.boosting_manager.boosting_sources.values()
                        if not isinstance(s, ChannelSource)]

        self.source_choice.SetItems(self.sources)

    def on_remove_source(self, _):
        """
        this function called when user clicked 'OK' button for removing source
        """
        selection = self.source_choice.GetSelection()
        if selection < len(self.sources):
            self.source = self.sources[selection]
        self.EndModal(wx.ID_OK)

    def on_cancel(self, _):
        """
        this function called when user clicked 'Cancel' button when adding source
        thus, cancelled
        """
        self.EndModal(wx.ID_CANCEL)

    def get_value(self):
        """
        get value when removing source
        """
        return self.source
