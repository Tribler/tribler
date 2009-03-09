import wx, math, time, os, sys, threading
import wx, os
from font import *

# font sizes
if sys.platform == 'darwin':
    FS_LEFTH1 = 12
    FS_HEADER = 11
    FS_FILETITLE = 10
    FS_SIMILARITY = 10
    FS_HEARTRANK = 8
elif sys.platform == 'linux2':
    FS_LEFTH1 = 11
    FS_HEADER = 10
    FS_FILETITLE = 8
    FS_SIMILARITY = 7
    FS_HEARTRANK = 7
else:
    FS_LEFTH1 = 11
    FS_HEADER = 10
    FS_FILETITLE = 8
    FS_SIMILARITY = 10
    FS_HEARTRANK = 7

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
    
    def colours(self, cNumber):
        if cNumber == 1:
            return wx.Colour(102,102,102)
        if cNumber == 2:
            return wx.Colour(77,163,184)
        
    
    
    def textButtonLeftH1(self, style=''):
#        item.SetForegroundColour(wx.Colour(50,50,50))
##        item.SetForegroundColour(wx.Colour(255,255,255))
#        item.SetBackgroundColour(wx.Colour(102,102,102))
##        wxFont(int pointSize, wxFontFamily family, int style, wxFontWeight weight, const bool underline = false, const wxString& faceName = "", wxFontEncoding encoding = wxFONTENCODING_DEFAULT)
#        item.SetFont(wx.Font(FS_LEFTH1,FONTFAMILY,wx.NORMAL,wx.BOLD,False,FONTFACE))
#        
#        if text != '':
#            item.SetLabel(text)
            
        if style == 'bgColour':
            return wx.Colour(102,102,102)
        elif style == 'textColour':
            return wx.Colour(166,166,166)
        elif style == 'textColour2':
            return wx.Colour(145,145,145)
        elif style == 'font':
            return wx.Font(FS_LEFTH1,FONTFAMILY,wx.NORMAL,wx.BOLD,False,FONTFACE)
        
        return None
            
    def textButtonLeft(self, style=''):
#        item = wx.BufferedPaintDC(self)
        if style == 'bgColour':
            return wx.Colour(102,102,102)
        elif style == 'bgColour2':
            return wx.Colour(0,0,0)
        elif style == 'textColour':
            return wx.Colour(220,220,220)
        elif style == 'textColourAdd':
            return wx.Colour(160,160,160)
        elif style == 'font':
            return wx.Font(FS_FILETITLE,FONTFAMILY,wx.NORMAL, wx.NORMAL,False,FONTFACE)
        elif style == 'fontAdd':
            return wx.Font(FS_FILETITLE,FONTFAMILY,wx.FONTSTYLE_ITALIC, wx.NORMAL,False,FONTFACE)
        
        return None
#        item.SetFont(
#        item.Clear()
#        item.DrawText(text, 2, 2)
#        
###        item.SetForegroundColour(wx.Colour(255,255,255))
####        item.SetForegroundColour(wx.Colour(255,255,255))
###        item.SetBackgroundColour(wx.Colour(102,102,102))
##        wxFont(int pointSize, wxFontFamily family, int style, wxFontWeight weight, const bool underline = false, const wxString& faceName = "", wxFontEncoding encoding = wxFONTENCODING_DEFAULT)
#        
#        
#        if text != '':
#            item.SetLabel(text)
    
    
    def titleBar(self, item, text=''):
        item.SetForegroundColour(wx.Colour(180,180,180))
        item.SetBackgroundColour(wx.Colour(71,71,71))
        item.SetFont(wx.Font(FS_FILETITLE,FONTFAMILY,wx.NORMAL,FONTWEIGHT,False,FONTFACE))

        
        if text != '':
            item.SetLabel(text)
    
    def setHeaderText(self, item, text=''):
        item.SetForegroundColour(wx.Colour(180,180,180))
        item.SetBackgroundColour(wx.Colour(102,102,102))
        item.SetFont(wx.Font(FS_HEADER,FONTFAMILY,wx.NORMAL,wx.BOLD,False,FONTFACE))
        
        if text != '':
            item.SetLabel(text)
    
    
    def setDarkText(self, item, text=''):
        item.SetForegroundColour(wx.BLACK) ## color of 'name' 'creation date' etc 51,51,51
        item.SetBackgroundColour(wx.Colour(216,233,240)) ## 102,102,102
        item.SetFont(wx.Font(FS_FILETITLE,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
        
        if text != '':
            item.SetLabel(text)
                
    def setLightText(self, item, text=''):
        # - normal text &
        # - left menu items

        item.SetFont(wx.Font(FS_FILETITLE,FONTFAMILY,FONTWEIGHT,wx.NORMAL,False,FONTFACE))
        item.SetForegroundColour(wx.Colour(100,100,100))
        item.SetBackgroundColour(wx.Colour(216,233,240)) ## 102,102,102
        
        if text != '':
            item.SetLabel(text)
            
    def selected (self, state):
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
#             colour = wx.Colour(230,230,230)
         if state == 3:
             colour = wx.Colour(80,70,70) 
         if state == 4:
             colour = wx.Colour(255,255,255)
         if state == 5:
             colour = wx.Colour(170,80,70)
             
         return colour
     
    def sortingColumns (self, state):
         # 1. unselected 
         # 2: selected + BG colour Pictues in column
         
         if state == 1:
             colour = wx.Colour(230,230,230) 
         if state == 2:
             colour = wx.Colour(230,230,230) 
         
         return colour
             
             
