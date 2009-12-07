# Written by Arno Bakker
# see LICENSE.txt for license information

import wx

DEBUG = False

# Default font properties
FONTFAMILY = wx.SWISS
FONTWEIGHT = wx.NORMAL
FONTFACE_CANDIDATES = ["Verdana","Arial",""] # "" means default font
FONTFACE = ""

def init():
    """ Initialise the font subsystem. Has to be called after wx.App(). """

    # FONTFACE := first existing font in FONTFACE_CANDIDATES array
    global FONTFACE
    fontnames = wx.FontEnumerator.GetFacenames()
    for f in FONTFACE_CANDIDATES:
        if f in fontnames:
            FONTFACE = f
            if DEBUG:
                print "Found font %s" % f
            break
