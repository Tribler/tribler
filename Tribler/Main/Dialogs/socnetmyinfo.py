# Written by Arno Bakker, Jie Yang
# see LICENSE.txt for license information

import os
import sys
from traceback import print_exc
import tempfile
import cStringIO

import wx
import wx.lib.imagebrowser as ib
# Arno: I have problems importing the Wizard classes, i.e. if I do
#   import wx
#   x = wx.Wizard
# it don't work. This explicit import seems to:
from wx.wizard import Wizard,WizardPageSimple,EVT_WIZARD_PAGE_CHANGED,EVT_WIZARD_PAGE_CHANGING,EVT_WIZARD_CANCEL,EVT_WIZARD_FINISHED

from Tribler.Main.vwxGUI.IconsManager import IconsManager, data2wxImage, data2wxBitmap, ICON_MAX_DIM
#from common import CommonTriblerList
from Tribler.Main.Utility.constants import *
from Tribler.Core.SessionConfig import SessionStartupConfig

from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Core.osutils import get_home_dir, get_picture_dir

DEBUG = False

################################################################
#
# Class: MyInfoDialog
#
# Dialog with user's public info
#
################################################################

class MyInfoWizard(Wizard):
    
    def __init__(self,parent):

        self.parent = parent
        self.utility = parent.utility

        title = self.utility.lang.get('myinfo')
        # TODO: bitmap?
        Wizard.__init__(self,parent, -1, title, style = wx.DEFAULT_DIALOG_STYLE)

        self.page1 = NameIconWizardPage(self,type)
        #self.page2 = RWIDsWizardPage(self,type)
        #self.page1.Chain(self.page1,self.page2)
        self.GetPageAreaSizer().Add(self.page1)
        #self.GetPageAreaSizer().Add(self.page2)

        self.Bind(EVT_WIZARD_PAGE_CHANGED,self.OnPageChanged)
        self.Bind(EVT_WIZARD_PAGE_CHANGING,self.OnPageChanging)
        self.Bind(EVT_WIZARD_CANCEL,self.OnCancel)
        self.Bind(EVT_WIZARD_FINISHED,self.OnFinished)

        self.guiUtility = GUIUtility.getInstance()

    def OnPageChanged(self,event=None):
        pass

    def OnPageChanging(self,event=None):
        if event is not None:
            if event.GetDirection():
                if self.GetCurrentPage() == self.page1:
                    if not self.page1.IsFilledIn():
                        event.Veto()

    def OnCancel(self,event=None):
        pass

    def OnFinished(self,event=None):
        (name,icondata, iconmime) = self.page1.getNameIconData()

        # write changes to the pickled config file, because on shutdown, changes are not pickled!
        # this is done to spare the mypreferences-changes.

        state_dir = self.utility.session.get_state_dir()
        cfgfilename = self.utility.session.get_default_config_filename(state_dir)
        scfg = SessionStartupConfig.load(cfgfilename)
        
#        for target in [scfg,self.utility.session]:
#            try:
#                target.set_nickname(name)
#                target.set_mugshot(icondata, mime=iconmime)
#            except:
#                print_exc()

#        scfg.save(cfgfilename)

        self.parent.WizardFinished(self, name, icondata, iconmime, scfg, cfgfilename, callback=self.saveInfo)



    def saveInfo(self, name, icondata, iconmime, scfg, cfgfilename, session):
        for target in [scfg,session]:
            try:
                target.set_nickname(name)
                target.set_mugshot(icondata, mime=iconmime)
            except:
                print_exc()

        scfg.save(cfgfilename)
       



    def getFirstPage(self):
        return self.page1



class NameIconWizardPage(WizardPageSimple):
    """ Ask user for public name and icon """
    
    def __init__(self,parent,type):
        WizardPageSimple.__init__(self,parent)
        self.utility = parent.utility

        # 0. mainbox
        mainbox = wx.BoxSizer(wx.VERTICAL)

        # 1. topbox
        topbox = wx.BoxSizer(wx.VERTICAL)

        # Ask public name
        name = self.utility.session.get_nickname()

        name_box = wx.BoxSizer(wx.HORIZONTAL)
        self.myname = wx.TextCtrl(self, -1, name)
        name_box.Add(wx.StaticText(self, -1, self.utility.lang.get('myname')), 0, wx.ALIGN_CENTER_VERTICAL)
        name_box.Add(self.myname, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        topbox.Add(name_box, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)

        # Ask public user icon / avatar
        icon_box = wx.BoxSizer(wx.HORIZONTAL)
        icon_box.Add(wx.StaticText(self, -1, self.utility.lang.get('myicon')), 0, wx.ALIGN_CENTER_VERTICAL)

        ## TODO: integrate this code with makefriends.py, especially checking code
        self.iconbtn = None
        self.iconmime, self.icondata = self.utility.session.get_mugshot()
        if self.icondata:
            bm = data2wxBitmap(self.iconmime, self.icondata)
        else:
            im = IconsManager.getInstance()
            bm = im.get_default('personsMode','DEFAULT_THUMB')

        if sys.platform == 'darwin':
            path = get_home_dir()
            self.iconbtn = wx.FilePickerCtrl(self, -1, path)
            self.Bind(wx.EVT_FILEPICKER_CHANGED,self.OnIconSelected,id=self.iconbtn.GetId())
            icon_box.Add(self.iconbtn, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        else:
            self.iconbtn = wx.BitmapButton(self, -1, bm)
            icon_box.Add(self.iconbtn, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
            #label = wx.StaticText(self, -1, self.utility.lang.get('obligiconformat'))
            #icon_box.Add(label, 0, wx.ALIGN_CENTRE|wx.ALL, 5)
            self.Bind(wx.EVT_BUTTON, self.OnIconButton, self.iconbtn)
        
        topbox.Add(icon_box, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)


        mainbox.Add(topbox, 0, wx.EXPAND)
        self.SetSizerAndFit(mainbox)

    def OnIconButton(self, evt):
        # open the image browser dialog
        dlg = ib.ImageDialog(self, get_picture_dir())
        dlg.Centre()
        if dlg.ShowModal() == wx.ID_OK:
            self.iconpath = dlg.GetFile()
            self.process_input()
        else:
            pass
        dlg.Destroy()
                    

    def OnIconSelected(self,event=None):
        self.iconpath = self.iconbtn.GetPath()
        self.process_input()

    def process_input(self):
        try:
            im = wx.Image(self.iconpath)
            if im is None:
                self.show_inputerror(self.utility.lang.get('cantopenfile'))
            else:
                if sys.platform != 'darwin':
                    bm = wx.BitmapFromImage(im.Scale(64,64),-1)
                    self.iconbtn.SetBitmapLabel(bm)
                
                # Arno, 2008-10-21: scale image!
                sim = im.Scale(ICON_MAX_DIM,ICON_MAX_DIM)
                [thumbhandle,thumbfilename] = tempfile.mkstemp("user-thumb")
                os.close(thumbhandle)
                sim.SaveFile(thumbfilename,wx.BITMAP_TYPE_JPEG)
                
                self.iconmime = 'image/jpeg'
                f = open(thumbfilename,"rb")
                self.icondata = f.read()
                f.close()
                os.remove(thumbfilename)
        except:
            print_exc()
            self.show_inputerror(self.utility.lang.get('iconbadformat'))
        


    def show_inputerror(self,txt):
        dlg = wx.MessageDialog(self, txt, self.utility.lang.get('invalidinput'), wx.OK | wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()

    def IsFilledIn(self):
        (name,_,_) = self.getNameIconData()
        #print "ICONPATH IS",iconpath
        return len(name) != 0 #and icondata is not None

    def getNameIconData(self):
        name = self.myname.GetValue()
        return (name,self.icondata, self.iconmime)


class RWIDsWizardPage(WizardPageSimple):
    """ Ask user for his real-world identifiers """

    def __init__(self,parent,type):
        WizardPageSimple.__init__(self,parent)
        self.parent = parent
        self.utility = parent.utility
        
        mainbox = wx.BoxSizer(wx.VERTICAL)
        text = wx.StaticText(self, -1, self.utility.lang.get('rwid_explanation'))
        text.Wrap(400)
        mainbox.Add(text, 0, wx.ALIGN_CENTER_HORIZONTAL|wx.ALL, 5)

        # Real-World Identifiers
        rwidbox = wx.BoxSizer(wx.VERTICAL)
        self.rwidlist = RWIDList(self)
        rwidbox.Add(self.rwidlist, 1, wx.EXPAND|wx.ALL, 5)
        
        rwidbtnbox = wx.BoxSizer(wx.HORIZONTAL)
        
        button = wx.Button(self, -1, self.utility.lang.get('addrwid'), style = wx.BU_EXACTFIT)
        self.Bind(wx.EVT_BUTTON, self.OnAddRWID, button)
        rwidbtnbox.Add(button, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 3)

        button = wx.Button(self, -1, self.utility.lang.get('remrwid'), style = wx.BU_EXACTFIT)
        self.Bind(wx.EVT_BUTTON, self.OnRemoveRWID, button)
        rwidbtnbox.Add(button, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 3)
        rwidbox.Add(rwidbtnbox, 0, wx.EXPAND)
        mainbox.Add(rwidbox, 0, wx.EXPAND)

        self.SetSizerAndFit(mainbox)

        self.rwidlist.loadList()


    def OnAddRWID(self,event=None):
        dlg = RWIDDialog(self)
        dlg.ShowModal()
        dlg.Destroy()

    def OnRemoveRWID(self,event=None):
        self.rwidlist.remove()

    def add(self,service,id):
        self.rwidlist.add(service,id)


