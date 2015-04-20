# TunnelOptin.py ---
#
# Filename: TunnelOptin.py
# Description:
# Author: Elric Milon
# Maintainer:
# Created: Mon Dec 22 18:10:38 2014 (+0100)

# Commentary:
#
#
#
#

# Change Log:
#
#
#
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at
# your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GNU Emacs.  If not, see <http://www.gnu.org/licenses/>.
#
#

# Code:
import logging

import wx.lib.newevent

from Tribler.Main.vwxGUI.widgets import _set_font


CollectedEvent, EVT_COLLECTED = wx.lib.newevent.NewEvent()


class TunnelOptin(wx.Dialog):

    def __init__(self, parent):
        self._logger = logging.getLogger(self.__class__.__name__)
        wx.Dialog.__init__(self, parent, -1, 'Do you want to use the experimental anonymity feature?', size=(-1, -1),
                           name="TunnelOptinDialog")

        vSizer = wx.BoxSizer(wx.VERTICAL)

        line = 'If you are not familiar with proxy technology, please opt-out.'

        firstLine = wx.StaticText(self, -1, line)
        firstLine.SetMinSize((-1, -1))
        _set_font(firstLine, fontweight=wx.FONTWEIGHT_BOLD)
        vSizer.Add(firstLine, 0, wx.EXPAND | wx.BOTTOM, 3)

        long_text = wx.StaticText(self, -1, u'This experimental anonymity feature using Tor-inspired onion routing '
                                  'and multi-layered encryption.'
                                  'You will become an exit node for other users downloads which could get you in '
                                  'trouble in various countries.\n'
                                  'This privacy enhancement will not protect you against spooks or '
                                  'government agencies.\n'
                                  'We are a torrent client and aim to protect you against lawyer-based '
                                  'attacks and censorship.\n'
                                  'With help from many volunteers we are continuously evolving and improving.')
        long_text.SetMinSize((-1, -1))
        vSizer.Add(long_text, 0, wx.EXPAND | wx.BOTTOM | wx.RIGHT, 3)

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(wx.StaticText(self, -1, '\nIf you aren\'t sure, press Cancel to disable the \n'
                                 'experimental anonymity feature'), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT | wx.BOTTOM,
                   3)

        vSizer.Add(hSizer, 0, wx.EXPAND | wx.BOTTOM, 3)

        vSizer.Add(wx.StaticLine(self, -1), 0, wx.EXPAND | wx.BOTTOM, 10)

        cancel = wx.Button(self, wx.ID_CANCEL)
        cancel.Bind(wx.EVT_BUTTON, self.OnCancel)

        ok = wx.Button(self, wx.ID_OK)
        ok.Bind(wx.EVT_BUTTON, self.OnOk)

        bSizer = wx.StdDialogButtonSizer()
        bSizer.AddButton(cancel)
        bSizer.AddButton(ok)
        bSizer.Realize()
        vSizer.Add(bSizer, 0, wx.EXPAND | wx.BOTTOM, 3)

        sizer = wx.BoxSizer()
        sizer.Add(vSizer, 1, wx.EXPAND | wx.ALL, 10)
        self.SetSizer(sizer)

        wx.CallAfter(wx.GetTopLevelParent(self).Fit)

    def OnCancel(self, event=None):
        self.EndModal(wx.ID_CANCEL)

    def OnOk(self, event=None):
        self.EndModal(wx.ID_OK)

#
# TunnelOptin.py ends here
