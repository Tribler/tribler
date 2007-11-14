# Written by Arno Bakker, Jie Yang
# see LICENSE.txt for license information

import os
import sys
import base64
from traceback import print_exc

import wx
import wx.lib.imagebrowser as ib
# Arno: I have problems importing the Wizard classes, i.e. if I do
#   import wx
#   x = wx.Wizard
# it don't work. This explicit import seems to:
from wx.wizard import Wizard,WizardPageSimple,EVT_WIZARD_PAGE_CHANGED,EVT_WIZARD_PAGE_CHANGING,EVT_WIZARD_CANCEL,EVT_WIZARD_FINISHED

from Tribler.Dialogs.MugshotManager import MugshotManager
from Tribler.Overlay.permid import permid_for_user
from Tribler.unicode import str2unicode
from common import CommonTriblerList
from Utility.constants import *

SERVICETYPES = []

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
        (name,iconpath) = self.page1.getNameIconPath()
        self.utility.session.set_nickname(name)
        mm = MugshotManager.getInstance()
        if iconpath:
            mypermid = my_db.getMyPermid()
            oldiconpath = mm.find_filename(mypermid,name)
            if oldiconpath != iconpath:
                mm.create_from_file(mypermid,iconpath)

        self.parent.WizardFinished(self)

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
        self.my_db = MyDBHandler.getInstance()
        name = self.my_db.get('name', '')

        name_box = wx.BoxSizer(wx.HORIZONTAL)
        self.myname = wx.TextCtrl(self, -1, name)
        name_box.Add(wx.StaticText(self, -1, self.utility.lang.get('myname')), 0, wx.ALIGN_CENTER_VERTICAL)
        name_box.Add(self.myname, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        topbox.Add(name_box, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)

        # Ask public user icon / avatar
        mypermid = self.my_db.getMyPermid()
        mm = MugshotManager.getInstance()
        self.iconpath = mm.find_filename(mypermid,name)

        icon_box = wx.BoxSizer(wx.HORIZONTAL)
        icon_box.Add(wx.StaticText(self, -1, self.utility.lang.get('myicon')), 0, wx.ALIGN_CENTER_VERTICAL)

        ## TODO: integrate this code with makefriends.py, especially checking code
        self.iconbtn = None
        my_db = MyDBHandler.getInstance()
        self.mypermid = my_db.getMyPermid()
        self.mm = MugshotManager.getInstance()
        bm = self.mm.load_wxBitmap(self.mypermid)
        if bm is None:
            bm = mm.get_default('personsMode','DEFAULT_THUMB')
        self.iconbtn = wx.BitmapButton(self, -1, bm)
        icon_box.Add(self.iconbtn, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)
        #label = wx.StaticText(self, -1, self.utility.lang.get('obligiconformat'))
        #icon_box.Add(label, 0, wx.ALIGN_CENTRE|wx.ALL, 5)
        self.Bind(wx.EVT_BUTTON, self.OnIconButton, self.iconbtn)
        topbox.Add(icon_box, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 5)

        mainbox.Add(topbox, 0, wx.EXPAND)
        self.SetSizerAndFit(mainbox)

    def OnIconButton(self, evt):
        try:
            if sys.platform == 'win32':
                # Arno goes win32, find location of "My Pictures"
                # see http://www.mvps.org/access/api/api0054.htm
                from win32com.shell import shell
                pidl = shell.SHGetSpecialFolderLocation(0,0x27)
                path = shell.SHGetPathFromIDList(pidl)
            else:
                path = os.path.expandvars('$HOME')
        except Exception, msg:
            path = ''
            print_exc()
            
        # open the image browser dialog
        dlg = ib.ImageDialog(self, path)
        dlg.Centre()
        if dlg.ShowModal() == wx.ID_OK:
            self.iconpath = dlg.GetFile()

            try:
                im = wx.Image(self.iconpath)
                if im is None:
                    self.show_inputerror(self.utility.lang.get('cantopenfile'))
                else:
                    bm = wx.BitmapFromImage(im.Scale(64,64),-1)
                    self.iconbtn.SetBitmapLabel(bm)
            except:
                self.show_inputerror(self.utility.lang.get('iconbadformat'))
        else:
            pass

        dlg.Destroy()        

    def show_inputerror(self,txt):
        dlg = wx.MessageDialog(self, txt, self.utility.lang.get('invalidinput'), wx.OK | wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()

    def IsFilledIn(self):
        (name,iconpath) = self.getNameIconPath()
        #print "ICONPATH IS",iconpath
        return len(name) != 0 ## and len(iconpath) != 0

    def getNameIconPath(self):
        name = self.myname.GetValue()
        iconpath = self.iconpath
        return (name,iconpath)


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


class RWIDList(CommonTriblerList):
    def __init__(self, parent):
        self.parent = parent
        self.utility = parent.utility

        self.my_db = MyDBHandler.getInstance()

        self.min_rank = -1
        self.max_rank = 5
        self.reversesort = 0
        self.lastcolumnsorted = -1
        
        style = wx.LC_REPORT|wx.LC_HRULES|wx.LC_VRULES
        
        prefix = 'myrwid'
        minid = 0
        maxid = 2
        rightalign = []
        centeralign = [
            IMPORT_SERVICE,
            IMPORT_ID
        ]
        
        exclude = []
        self.data = []

        self.keys = ['service', 'id']

        CommonTriblerList.__init__(self, parent, style, prefix, minid, maxid, 
                                     exclude, rightalign, centeralign)

    def getText(self, data, row, col):
        key = self.keys[col]
        if row < len(data):
            return str2unicode(data[row][key])
        else:
            return u''
                
    def reloadData(self):
        self.data = []
        rwids = self.my_db.getRWIDs()
        i = 0
        for rwid in rwids:
            self.data.append({})
            self.data[i]['service'] = rwid[0]
            self.data[i]['id'] = rwid[1]
            i += 1

    def remove(self):
        selected = self.getSelectedItems()
        for i in selected:
            self.my_db.deleteRWID(self.data[i]['service'],self.data[i]['id'])
        self.loadList()

    def add(self,service,id):
        self.my_db.addRWID(service,id)
        self.loadList()


class RWIDDialog(wx.Dialog):
    def __init__(self, parent):
        self.utility = parent.utility
        self.parent = parent

        style = wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        pos = wx.DefaultPosition
        size = wx.Size(530, 420)
        #size, split = self.getWindowSettings()

        title = self.utility.lang.get('addrwid')
        wx.Dialog.__init__(self, parent, -1, title, size = size, style = style)

        mainbox = wx.BoxSizer(wx.VERTICAL)
        topbox = wx.BoxSizer(wx.VERTICAL)

        servicebox = wx.BoxSizer(wx.HORIZONTAL)
        servicebox.Add(wx.StaticText(self, -1, self.utility.lang.get('service')+':'), 0, wx.ALIGN_CENTRE|wx.ALL, 5)
        self.servicetypes = SERVICETYPES
        self.servicechoice= wx.Choice(self, -1, wx.Point(-1, -1), wx.Size(-1, -1), self.servicetypes)
        servicebox.Add(self.servicechoice, 1, wx.ALIGN_CENTRE|wx.ALL, 5)        
        topbox.Add(servicebox, 0, wx.ALIGN_CENTRE|wx.ALL, 5)

        # name
        namebox = wx.BoxSizer(wx.HORIZONTAL)
        namebox.Add(wx.StaticText(self, -1, self.utility.lang.get('identifier')+':'), 0, wx.ALIGN_CENTRE|wx.ALL, 5)
        self.name_text = wx.TextCtrl(self, -1, '', size=(80,-1))
        namebox.Add(self.name_text, 1, wx.ALIGN_CENTRE|wx.ALL, 5)
        topbox.Add(namebox, 0, wx.GROW|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        btnsizer = wx.StdDialogButtonSizer()
        lbl = self.utility.lang.get('buttons_add')
        btn = wx.Button(self, wx.ID_OK, label=lbl)
        btn.SetDefault()
        btnsizer.AddButton(btn)
        self.Bind(wx.EVT_BUTTON, self.OnAddRWID, btn)

        btn = wx.Button(self, wx.ID_CANCEL)
        btnsizer.AddButton(btn)
        btnsizer.Realize()

        mainbox.Add(topbox, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
        mainbox.Add(btnsizer, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        self.SetSizer(mainbox)
        mainbox.Fit(self)
        
    def OnAddRWID(self, event=None):
        idx = self.servicechoice.GetCurrentSelection()
        print "SERVICE CHOICE",idx
        if idx == -1:
            idx = 0
        servicetype = self.servicetypes[idx]
        id = self.name_text.GetValue()

        # Add to DB
        if DEBUG:
            print "rwid: adding rwid",id,"for service",servicetype
        self.parent.add(servicetype,id)

        event.Skip()    # must be done, otherwise ShowModal() returns wrong error 
        self.Destroy()

