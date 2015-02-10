# Modified by Niels Zeilemaker, removed timeout did a small cleanup
from Tribler.Main.vwxGUI import DEFAULT_BACKGROUND

#-----------------------------------------------------------------------------
# Name:        gaugesplash.py
# Purpose:     splash screen with gauge to show progress
#
# Author:      Rob McMullen
#
# Created:     2007
# RCS-ID:      $Id: $
# Copyright:   (c) 2007 Rob McMullen
# License:     wxWidgets
#-----------------------------------------------------------------------------

"""Splash screen with progress bar

A replacement for the standard wx.SplashScreen that adds a text label
and progress bar to update the user on the progress loading the
application.

I looked at both Andrea Gavana's AdvancedSplash, here:

http://xoomer.alice.it/infinity77/main/AdvancedSplash.html

and Ryaan Booysen's AboutBoxSplash

http://boa-constructor.cvs.sourceforge.net/boa-constructor/boa/About.py?revision=1.38&view=markup

for inspiration and code.
"""

import logging
import wx


class GaugeSplash(wx.Frame):

    """Placeholder for a gauge-bar splash screen."""

    def __init__(self, bmp, label):
        wx.Frame.__init__(self, None, style=wx.FRAME_NO_TASKBAR)

        self._logger = logging.getLogger(self.__class__.__name__)

        self.count = 0
        self.border = 2
        self.SetBackgroundColour(DEFAULT_BACKGROUND)

        sizer = wx.BoxSizer(wx.VERTICAL)
        self.bmp = wx.StaticBitmap(self, -1, bmp)
        sizer.Add(self.bmp, 0, wx.EXPAND)

        self.label = wx.StaticText(self, -1, label)
        self.label.SetBackgroundColour(DEFAULT_BACKGROUND)
        sizer.Add(self.label, 0, flag=wx.EXPAND | wx.ALL, border=self.border)

        self.progressHeight = 12
        self.gauge = wx.Gauge(self, -1,
                              range=100, size=(-1, self.progressHeight),
                              style=wx.GA_HORIZONTAL | wx.GA_SMOOTH)
        self.gauge.SetBackgroundColour(DEFAULT_BACKGROUND)
        sizer.Add(self.gauge, 0, flag=wx.EXPAND | wx.TOP, border=self.border)
        self.SetSizer(sizer)
        sizer.Fit(self)

        self.CenterOnScreen()
        self.Layout()
        self.Show(True)

        try:
            wx.Yield()
        except:
            pass

    def setTicks(self, count):
        """Set the total number of ticks that will be contained in the
        progress bar.
        """
        self.gauge.SetRange(count)

    def tick(self, text):
        """Advance the progress bar by one tick and update the label.
        """
        self.count += 1
        self.label.SetLabel(text)
        self.gauge.SetValue(self.count)
        self.gauge.Update()
        self.Refresh()
        wx.Yield()

    def __del__(self):
        self._logger.debug("MAX ticks == %s", self.count)

        self.gauge.SetValue(self.gauge.GetRange())
        wx.Yield()
