#   Copyright (c) 2006-2008 Open Source Applications Foundation
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

# 10-10-2011 Niels Zeilemaker: modified version of
# http://svn.osafoundation.org/chandler/trunk/chandler/application/feedback.py

import sys
import os
import wx
import platform
import httplib
from urllib import urlencode

from Tribler.Core.version import version_id
from Tribler.Main.vwxGUI.widgets import AutoWidthListCtrl


class FeedbackWindow(wx.PyOnDemandOutputWindow):

    """
    An error dialog that would be shown in case there is an uncaught
    exception. The user can send the error report back to us as well.
    """

    def __call__(self, *args, **kw):
        # Make this a Singleton to avoid the problem of multiple feedback
        # windows popping up at the same time
        return self

    def _fillOptionalSection(self):
        try:
            # columns
            self.sysInfo.InsertColumn(0, 'key')
            self.sysInfo.InsertColumn(1, 'value')

            def add(col, val):
                pos = self.sysInfo.InsertStringItem(sys.maxint, col)
                self.sysInfo.SetStringItem(pos, 1, val)

            # data
            add('os.getcwd', '%s' % os.getcwd())
            add('sys.executable', '%s' % sys.executable)

            add('os', os.name)
            add('platform', sys.platform)
            add('platform.details', platform.platform())
            add('platform.machine', platform.machine())
            add('python.version', sys.version)
            add('indebug', str(__debug__))

            for argv in sys.argv:
                add('sys.argv', '%s' % argv)

            for path in sys.path:
                add('sys.path', '%s' % path)

            for key in os.environ.keys():
                add('os.environ', '%s: %s' % (key, os.environ[key]))

            # read tribler.log?
#            try:
#
#                f = codecs.open(os.path.join(Globals.options.profileDir,
#                                             'chandler.log'),
#                                encoding='utf-8', mode='r', errors='ignore')
#                for line in f.readlines()[-LOGLINES:]:
#                    self.frame.sysInfo.InsertStringItem(index, 'chandler.log')
#                    self.frame.sysInfo.SetStringItem(index, 1, '%s' % line.strip())
#                    index += 1
#            except:
#                pass

        except:
            pass

        self.sysInfo.SetColumnWidth(0, wx.LIST_AUTOSIZE)
        self.sysInfo.SetColumnWidth(1, wx.LIST_AUTOSIZE)

    def _fillRequiredSection(self, st):
        # Version and other miscellaneous information
        try:
            self.text.AppendText('%s version: %s\n' % ('Tribler', version_id))
        except:
            pass

        # Traceback (actually just the first line of it)
        self.text.AppendText(st)

    def CreateOutputWindow(self, st):
        self.frame = wx.Dialog(
            None, -1, self.title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER, name="FeedbackWindow")

        self.frame.CenterOnParent()
        sizer = wx.BoxSizer(wx.HORIZONTAL)

        icon = wx.StaticBitmap(self.frame, -1, wx.ArtProvider.GetBitmap(wx.ART_ERROR, wx.ART_MESSAGE_BOX))
        sizer.Add(icon)

        vSizer = wx.BoxSizer(wx.VERTICAL)
        vSizer.Add(
            wx.StaticText(self.frame, -1, 'Tribler encountered an error, to help us fix this please send an error-report.'))

        self.text = wx.TextCtrl(self.frame, -1, "", style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.text.SetMinSize((600, 150))
        vSizer.Add(self.text, 0, wx.EXPAND)

        self.sysInfo = AutoWidthListCtrl(self.frame, style=wx.LC_REPORT | wx.NO_BORDER)
        self.sysInfo.SetMinSize((-1, 200))
        vSizer.Add(self.sysInfo, 1, wx.EXPAND)

        self.comments = wx.TextCtrl(self.frame, -1, "", style=wx.TE_MULTILINE)
        self.comments.SetMinSize((-1, 100))
        vSizer.Add(wx.StaticText(self.frame, -1, 'Comments: (optional)'))
        vSizer.Add(self.comments, 0, wx.EXPAND)

        self.email = wx.TextCtrl(self.frame, -1, "")
        vSizer.Add(wx.StaticText(self.frame, -1, 'Email: (optional)'))
        vSizer.Add(self.email, 0, wx.EXPAND)

        buttonSizer = wx.BoxSizer(wx.HORIZONTAL)

        self.sendButton = wx.Button(self.frame, -1, 'Send Report')
        self.sendButton.Bind(wx.EVT_BUTTON, self.OnSend)
        buttonSizer.Add(self.sendButton, 0, wx.RIGHT, 3)

        if self.parent:
            self.restartButton = wx.Button(self.frame, -1, 'Restart')
            self.restartButton.Bind(wx.EVT_BUTTON, self.OnRestart)
            buttonSizer.Add(self.restartButton, 0, wx.RIGHT, 3)

        self.closeButton = wx.Button(self.frame, wx.ID_CANCEL)
        self.closeButton.Bind(wx.EVT_BUTTON, self.OnCloseWindow)
        buttonSizer.Add(self.closeButton)

        vSizer.Add(buttonSizer, 0, wx.ALIGN_RIGHT | wx.TOP, 10)
        sizer.Add(vSizer, 1, wx.EXPAND | wx.LEFT, 10)

        self._fillRequiredSection(st)
        self._fillOptionalSection()

        self.frame.Bind(wx.EVT_CHAR, self.OnChar)
        self.frame.Bind(wx.EVT_CLOSE, self.OnCloseWindow)

        border = wx.BoxSizer()
        border.Add(sizer, 1, wx.ALL | wx.EXPAND, 10)

        self.frame.SetSizerAndFit(border)

    def OnChar(self, event):
        # Close the window if an escape is typed
        keycode = event.GetKeyCode()
        if keycode == wx.WXK_ESCAPE:
            self.OnCloseWindow(event)
        else:
            event.Skip()

    def OnRestart(self, event):
        try:
            self.sendButton.Disable()
            self.restartButton.Disable()
            self.closeButton.Disable()
            self.restartButton.SetLabel('Restarting...')

            self.parent.Restart()

        finally:
            self.frame.Show(False)

    def OnSend(self, event):
        self.sendButton.Disable()

        # Disabling the focused button disables keyboard navigation
        # unless we set the focus to something else - let's put it
        # on close button
        self.closeButton.SetFocus()
        self.sendButton.SetLabel('Sending...')

        try:
            c = httplib.HTTPConnection('dispersyreporter.tribler.org')

            email = 'Not provided'
            if self.email.GetValue():
                email = self.email.GetValue()

            comments = 'Not provided'
            if self.comments.GetValue():
                comments = self.comments.GetValue()

            body_dict = {'email': email, 'comments': comments}
            body_dict['stack'] = self.text.GetValue()

            optional = ''
            for i in range(self.sysInfo.GetItemCount()):
                field = self.sysInfo.GetItem(i, 0).GetText()
                value = self.sysInfo.GetItem(i, 1).GetText()
                optional += field + '\t' + value + '\n'
            body_dict['sysinfo'] = optional

            body = urlencode(body_dict)

            c.request('POST', '/exception.py', body)
            response = c.getresponse()

            if response.status != 200:
                raise Exception('response.status=' + response.status)
            c.close()
        except:
            self.sendButton.SetLabel('Failed to send')
        else:
            self.sendButton.SetLabel('Sent')

    def Show(self, show=True):
        return self.frame.Show(show)

    def ShowModal(self):
        return self.frame.ShowModal()
