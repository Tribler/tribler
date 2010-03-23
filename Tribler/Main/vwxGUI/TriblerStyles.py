import wx, math, time, os, sys, threading
import wx, os
from font import *

# font sizes
if sys.platform == 'darwin':
    FS_FILETITLE = 12
elif sys.platform == 'linux2':
    FS_FILETITLE = 9
else:
    FS_FILETITLE = 10

class TriblerStyles:
    __single = None


    def __init__(self):
        if TriblerStyles.__single:
            raise RuntimeError, "TriblerStyles is singleton"
        TriblerStyles.__single = self 
        
    def getInstance(*args, **kw):
        if TriblerStyles.__single is None:
            TriblerStyles(*args, **kw)
        return TriblerStyles.__single
    getInstance = staticmethod(getInstance)
    
    
    def setDarkText(self, item, text=''):
        item.SetForegroundColour(wx.BLACK)
        item.SetBackgroundColour(wx.Colour(216,233,240))
        item.SetFont(wx.Font(FS_FILETITLE,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
        
        if text != '':
            item.SetLabel(text)
                
    def selected(self, state):
        #possible states:
            # 1. first row - not selected - not in Library
            # 2. second row - not selected - not in Library
            # 3. selected - not in Library
            # 4. not selected - in Library
            # 5. selected - in Library 
         if state == 1:
             colour = wx.Colour(102,102,102)
         if state == 2:
             colour = wx.Colour(102,102,102)
         if state == 3:
             colour = wx.Colour(80,70,70) 
         if state == 4:
             colour = wx.Colour(255,255,255)
         if state == 5:
             colour = wx.Colour(170,80,70)
             
         return colour
     
    def sortingColumns(self, state):
         # 1. unselected 
         # 2: selected + BG colour Pictues in column
        if state == 1:
            colour = wx.Colour(230,230,230) 
        if state == 2:
            colour = wx.Colour(230,230,230) 
        return colour
             
             
