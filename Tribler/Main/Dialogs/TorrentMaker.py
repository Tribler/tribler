# Written by Bram Cohen
# modified for multitracker by John Hoffman
# modified for Merkle hashes and digital signatures by Arno Bakker
# see LICENSE.txt for license information

import sys
import wx
import wx.lib.imagebrowser as ib
import os

from threading import Event, Thread, currentThread
from tempfile import mkstemp
from traceback import print_exc

from Tribler.Core.API import *
from Tribler.Main.globals import DefaultDownloadStartupConfig

FILESTOIGNORE = ['core', 'CVS']

DEBUG = False


################################################################
#
# Class: MiscInfoPanel
#
# Panel for defining miscellaneous settings for a torrent
#
################################################################
class MiscInfoPanel(wx.Panel):
    def __init__(self, parent, dialog):
        wx.Panel.__init__(self, parent, -1)
        
        self.dialog = dialog
        self.utility = dialog.utility

        outerbox = wx.BoxSizer(wx.VERTICAL)

        # Created by:
        outerbox.Add(wx.StaticText(self, -1, self.utility.lang.get('createdby')), 0, wx.EXPAND|wx.ALL, 5)
        self.createdBy = wx.TextCtrl(self, -1)
        outerbox.Add(self.createdBy, 0, wx.EXPAND|wx.ALL, 5)

        # Comment:        
        outerbox.Add(wx.StaticText(self, -1, self.utility.lang.get('comment')), 0, wx.EXPAND|wx.ALL, 5)
        self.commentCtl = wx.TextCtrl(self, -1, size = (-1, 75), style = wx.TE_MULTILINE|wx.HSCROLL|wx.TE_DONTWRAP)        
        outerbox.Add(self.commentCtl, 0, wx.EXPAND|wx.ALL, 5)

        # Playtime:        
        outerbox.Add(wx.StaticText(self, -1, self.utility.lang.get('playtime')), 0, wx.EXPAND|wx.ALL, 5)
        self.playtCtl = wx.TextCtrl(self, -1)
        outerbox.Add(self.playtCtl, 0, wx.EXPAND|wx.ALL, 5)

        # Thumbnail:
        ybox = wx.BoxSizer(wx.VERTICAL)
        ybox.Add(wx.StaticText(self, -1, self.utility.lang.get('addthumbnail')), 0, wx.EXPAND|wx.ALL, 5)
        xbox = wx.BoxSizer(wx.HORIZONTAL)
        self.thumbCtl = wx.TextCtrl(self, -1)
        xbox.Add(self.thumbCtl, 1, wx.EXPAND|wx.ALL, 5)
        browsebtn = wx.Button(self, -1, "...")
        self.Bind(wx.EVT_BUTTON, self.onBrowseThumb, browsebtn)
        xbox.Add(browsebtn, 0, wx.ALL, 5)
        ybox.Add(xbox, 0, wx.EXPAND|wx.ALL, 5)
        outerbox.Add(ybox, 0, wx.ALL|wx.EXPAND, 5)
      
        self.SetSizerAndFit(outerbox)
        
        self.loadValues()

    def loadValues(self, Read = None):
        if Read is None:
            Read = self.utility.makerconfig.Read
        
        self.createdBy.SetValue(Read('created_by'))
        self.commentCtl.SetValue(Read('comment'))

    def saveConfig(self, event = None):
        self.utility.makerconfig.Write('created_by', self.createdBy.GetValue())
        self.utility.makerconfig.Write('comment', self.commentCtl.GetValue())
        
    def getParams(self):
        params = {}

        thumbfn = self.thumbCtl.GetValue()
        if len(thumbfn) > 0:
            try:
                im = wx.Image(thumbfn)
                ims = im.Scale(171,96)
    
                [thumbhandle,thumbfilename] = mkstemp("torrent-thumb")
                os.close(thumbhandle)
                ims.SaveFile(thumbfilename,wx.BITMAP_TYPE_JPEG)
                params['thumb'] = thumbfilename 
            except:
                print_exc()

        playt = self.playtCtl.GetValue()
        if playt != '':
            params['playtime'] = playt
        
        comment = self.commentCtl.GetValue()
        if comment != '':
            params['comment'] = comment

        createdby = self.createdBy.GetValue()
        if comment != '':
            params['created by'] = createdby
            
        return params


    def onBrowseThumb(self, evt):
        path = ''
            
        # open the image browser dialog
        dlg = ib.ImageDialog(self, path)
        dlg.Centre()
        if dlg.ShowModal() == wx.ID_OK:
            iconpath = dlg.GetFile()

            try:
                im = wx.Image(iconpath)
                if im is None:
                    self.show_inputerror(self.utility.lang.get('cantopenfile'))
                else:
                    self.thumbCtl.SetValue(iconpath)
            except:
                self.show_inputerror(self.utility.lang.get('iconbadformat'))
        else:
            pass

        dlg.Destroy()        

    def show_inputerror(self,txt):
        dlg = wx.MessageDialog(self, txt, self.utility.lang.get('invalidinput'), wx.OK | wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()


################################################################
#
# Class: TrackerInfoPanel
#
# Panel for defining tracker settings for a torrent
#
################################################################
class TrackerInfoPanel(wx.Panel):
    def __init__(self, parent, dialog):
        wx.Panel.__init__(self, parent, -1)
        
        self.dialog = dialog
        self.utility = dialog.utility

        outerbox = wx.BoxSizer(wx.VERTICAL)

        announcesection_title = wx.StaticBox(self, -1, self.utility.lang.get('announce'))
        announcesection = wx.StaticBoxSizer(announcesection_title, wx.VERTICAL)

        self.announcehistory = []

        # Use internal tracker?
        itracker_box = wx.BoxSizer(wx.HORIZONTAL)
        prompt = self.utility.lang.get('useinternaltracker')+' ('+self.utility.session.get_internal_tracker_url()+')'
        self.itracker = wx.CheckBox(self, -1, prompt)
        wx.EVT_CHECKBOX(self, self.itracker.GetId(), self.OnInternalTracker)
        itracker_box.Add(self.itracker, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
        announcesection.Add(itracker_box, 0, wx.EXPAND|wx.ALL, 3)

        # Manual override of tracker definition
        manualover_box = wx.BoxSizer(wx.HORIZONTAL)
        self.manualover = wx.CheckBox(self, -1, self.utility.lang.get('manualtrackerconfig'))
        wx.EVT_CHECKBOX(self, self.manualover.GetId(), self.OnInternalTracker) # yes, OnInternalTracker
        manualover_box.Add(self.manualover, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
        announcesection.Add(manualover_box, 0, wx.EXPAND|wx.ALL, 3)

        # Copy announce from torrent
        self.copybutton = wx.Button(self, -1, self.utility.lang.get('copyannouncefromtorrent'))
        wx.EVT_BUTTON(self, self.copybutton.GetId(), self.announceCopy)
        announcesection.Add(self.copybutton, 0, wx.ALL, 5)

        # Announce url:
        self.annText = wx.StaticText(self, -1, self.utility.lang.get('announceurl'))
        announcesection.Add(self.annText, 0, wx.ALL, 5)

        announceurl_box = wx.BoxSizer(wx.HORIZONTAL)
       
        self.annCtl = wx.ComboBox(self, -1, "", choices = self.announcehistory, style=wx.CB_DROPDOWN)
        announceurl_box.Add(self.annCtl, 1, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)
        
        self.addbutton = wx.Button(self, -1, "+", size = (30, -1))
        self.addbutton.SetToolTipString(self.utility.lang.get('add'))
        wx.EVT_BUTTON(self, self.addbutton.GetId(), self.addAnnounce)
        announceurl_box.Add(self.addbutton, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 3)

        self.delbutton = wx.Button(self, -1, "-", size = (30, -1))
        self.delbutton.SetToolTipString(self.utility.lang.get('remove'))
        wx.EVT_BUTTON(self, self.delbutton.GetId(), self.removeAnnounce)
        announceurl_box.Add(self.delbutton, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 3)

        announcesection.Add(announceurl_box, 0, wx.EXPAND)

        # Announce List:        
        self.annListText = wx.StaticText(self, -1, self.utility.lang.get('announcelist'))
        announcesection.Add(self.annListText, 0, wx.EXPAND|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
       
        self.annListCtl = wx.TextCtrl(self, -1, size = (-1, 75), style = wx.TE_MULTILINE|wx.HSCROLL|wx.TE_DONTWRAP)
        self.annListCtl.SetToolTipString(self.utility.lang.get('multiannouncehelp'))
        
        announcesection.Add(self.annListCtl, 1, wx.EXPAND|wx.TOP, 5)
        
        outerbox.Add(announcesection, 0, wx.EXPAND|wx.ALL, 3)
      
        # HTTP Seeds:
        outerbox.Add(wx.StaticText(self, -1, self.utility.lang.get('httpseeds')), 0, wx.EXPAND|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
       
        self.httpSeeds = wx.TextCtrl(self, -1, size = (-1, 75), style = wx.TE_MULTILINE|wx.HSCROLL|wx.TE_DONTWRAP)
        self.httpSeeds.SetToolTipString(self.utility.lang.get('httpseedshelp'))
        outerbox.Add(self.httpSeeds, 1, wx.EXPAND|wx.ALL, 5)
      
        self.SetSizerAndFit(outerbox)
        
        self.loadValues()

    def loadValues(self, Read = None):
        if Read is None:
            Read = self.utility.makerconfig.Read

        useitracker = Read('useitracker','boolean')
        self.itracker.SetValue(useitracker)
        manualtrackerconfig = Read('manualtrackerconfig','boolean')
        self.manualover.SetValue(manualtrackerconfig)

        self.annCtl.Clear()
        self.announcehistory = Read('announcehistory', "bencode-list")
        for announceurl in self.announcehistory:
            self.annCtl.Append(announceurl)
        self.annCtl.SetValue(Read('announcedefault'))

        self.annListCtl.SetValue(Read('announce-list'))
        
        self.toggle_itracker(useitracker,manualtrackerconfig)
        
        self.httpSeeds.SetValue(Read('httpseeds'))


    def toggle_itracker(self,useitracker,manualtrackerconfig):
        if useitracker:
            self.manualover.Enable()
            if manualtrackerconfig:
                self.copybutton.Enable()
                self.annText.Enable()
                self.annCtl.Enable()
                self.annListText.Enable()
                self.annListCtl.Enable()
                self.addbutton.Enable()
                self.delbutton.Enable()
            else:
                self.copybutton.Disable()
                self.annText.Disable()
                self.annCtl.Disable()
                self.annListText.Disable()
                self.annListCtl.Disable()
                self.addbutton.Disable()
                self.delbutton.Disable()
                
            self.dialog.fileInfoPanel.startnow.SetValue(True)
            self.dialog.fileInfoPanel.startnow.Disable()
        else:
            self.manualover.Disable()
            self.copybutton.Enable()
            self.annText.Enable()
            self.annCtl.Enable()
            self.annListText.Enable()
            self.annListCtl.Enable()
            self.addbutton.Enable()
            self.delbutton.Enable()
            self.dialog.fileInfoPanel.startnow.Enable()

    def saveConfig(self, event = None):
        index = self.annCtl.GetSelection()
        if index != -1:
            self.utility.makerconfig.Write('announcedefault', self.annCtl.GetValue())
        self.utility.makerconfig.Write('announcehistory', self.announcehistory, "bencode-list")
        self.utility.makerconfig.Write('announce-list', self.annListCtl.GetValue())
        self.utility.makerconfig.Write('httpseeds', self.httpSeeds.GetValue())

    def addAnnounce(self, event = None):
        announceurl = self.annCtl.GetValue()

        # Don't add to the list if it's already present or the string is empty
        announceurl = announceurl.strip()
        if not announceurl or announceurl in self.announcehistory:
            return
        self.announcehistory.append(announceurl)
        self.annCtl.Append(announceurl)
        
    def removeAnnounce(self, event = None):
        index = self.annCtl.GetSelection()
        if index != -1:
            announceurl = self.annCtl.GetValue()
            self.annCtl.Delete(index)
            try:
                self.announcehistory.remove(announceurl)
            except:
                pass

    def announceCopy(self, event = None):
        dl = wx.FileDialog(self.dialog, 
                           self.utility.lang.get('choosedottorrentfiletouse'), 
                           '', 
                           '', 
                           self.utility.lang.get('torrentfileswildcard') + ' (*.torrent)|*.torrent', 
                           wx.OPEN)
        if dl.ShowModal() == wx.ID_OK:
            try:
                metainfo = self.utility.getMetainfo(dl.GetPath())
                if (metainfo is None):
                    return
                self.annCtl.SetValue(metainfo['announce'])
                if 'announce-list' in metainfo:
                    list = []
                    for tier in metainfo['announce-list']:
                        for tracker in tier:
                            list += [tracker, ', ']
                        del list[-1]
                        list += ['\n']
                    liststring = ''
                    for i in list:
                        liststring += i
                    self.annListCtl.SetValue(liststring+'\n\n')
                else:
                    self.annListCtl.SetValue('')
            except:
                return                

    def getAnnounceList(self):
        text = self.annListCtl.GetValue()
        list = []
        for tier in text.split('\n'):
            sublist = []
            tier.replace(',', ' ')
            for tracker in tier.split(' '):
                if tracker != '':
                    sublist += [tracker]
            if sublist:
                list.append(sublist)
        return list
        
    def getHTTPSeedList(self):
        text = self.httpSeeds.GetValue()
        list = []
        for tier in text.split('\n'):
            tier.replace(',', ' ')
            for tracker in tier.split(' '):
                if tracker != '':
                    list.append(tracker)
        return list

    def getParams(self):
        params = {}

        if self.itracker.GetValue():
            params['usinginternaltracker'] = True
        else:
             params['usinginternaltracker'] = False
            
        if self.manualover.GetValue(): # Use manual specification of trackers
            # Announce list
            annlist = self.getAnnounceList()
            if annlist:
                params['announce-list'] = annlist
            
            # Announce URL
            announceurl = None
            index = self.annCtl.GetSelection()
            if annlist and index == -1:
                # If we don't have an announce url specified,
                # try using the first value in announce-list
                tier1 = annlist[0]
                if tier1:
                    announceurl = tier1[0]
            else:
                announceurl = self.annCtl.GetValue()
                    
            if announceurl is None:
                # What should we do here?
                announceurl = ""
    
            params['announce'] = announceurl
        else:
            # Use just internal tracker
            params['announce'] = self.utility.session.get_internal_tracker_url()
                   
        # HTTP Seeds
        httpseedlist = self.getHTTPSeedList()
        if httpseedlist:
            params['httpseeds'] = httpseedlist

        return params
    
    def OnInternalTracker(self,event=None):
        self.toggle_itracker(self.itracker.GetValue(),self.manualover.GetValue())
    


################################################################
#
# Class: FileInfoPanel
#
# Class for choosing a file when creating a torrent
#
################################################################        
class FileInfoPanel(wx.Panel):
    def __init__(self, parent, dialog):
        wx.Panel.__init__(self, parent, -1)
        
        self.dialog = dialog
        self.utility = dialog.utility

        outerbox = wx.BoxSizer(wx.VERTICAL)

        # Make torrent of:
        maketorrent_box = wx.BoxSizer(wx.HORIZONTAL)
        maketorrent_box.Add(wx.StaticText(self, -1, self.utility.lang.get('maketorrentof')), 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        self.dirCtl = wx.TextCtrl(self, -1, '')
        maketorrent_box.Add(self.dirCtl, 1, wx.ALIGN_CENTER_VERTICAL|wx.EXPAND|wx.ALL, 5)

        button = wx.Button(self, -1, self.utility.lang.get('dir'), style = wx.BU_EXACTFIT)
        wx.EVT_BUTTON(self, button.GetId(), self.selectDir)
        maketorrent_box.Add(button, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        button2 = wx.Button(self, -1, self.utility.lang.get('file'), style = wx.BU_EXACTFIT)
        wx.EVT_BUTTON(self, button2.GetId(), self.selectFile)
        maketorrent_box.Add(button2, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        outerbox.Add(maketorrent_box, 0, wx.EXPAND)        

        # Merkle:
        merkletorrent_box = wx.BoxSizer(wx.HORIZONTAL)
        self.createmerkletorrent = wx.CheckBox(self, -1, self.utility.lang.get('createmerkletorrent'))
        merkletorrent_box.Add(self.createmerkletorrent, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
        outerbox.Add(merkletorrent_box, 0, wx.EXPAND)

        # Piece size:
        piecesize_box = wx.BoxSizer(wx.HORIZONTAL)
        
        piecesize_box.Add(wx.StaticText(self, -1, self.utility.lang.get('piecesize')), 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
        
        abbrev_mb = " " + self.utility.lang.get('MB')
        abbrev_kb = " " + self.utility.lang.get('KB')
        
        piece_choices = [self.utility.lang.get('automatic'), 
                         '2' + abbrev_mb, 
                         '1' + abbrev_mb, 
                         '512' + abbrev_kb, 
                         '256' + abbrev_kb, 
                         '128' + abbrev_kb, 
                         '64' + abbrev_kb, 
                         '32' + abbrev_kb]
        self.piece_length = wx.Choice(self, -1, choices = piece_choices)
        self.piece_length_list = [0, 2**21, 2**20, 2**19, 2**18, 2**17, 2**16, 2**15]
        piecesize_box.Add(self.piece_length, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
        
        outerbox.Add(piecesize_box, 0, wx.EXPAND)
        

#        panel.DragAcceptFiles(True)
#        wx.EVT_DROP_FILES(panel, self.selectdrop)

        # Save torrent :
        savetorrentbox = wx.StaticBoxSizer(wx.StaticBox(self, -1, self.utility.lang.get('savetor')), wx.VERTICAL)

        self.savetorrb1 = wx.RadioButton(self, -1, self.utility.lang.get('savetordefault'), (-1, -1), (-1, -1), wx.RB_GROUP)
        savetorrb2 = wx.RadioButton(self, -1, self.utility.lang.get('savetorsource'), (-1, -1), (-1, -1))
        savetorrb3 = wx.RadioButton(self, -1, self.utility.lang.get('savetorask'), (-1, -1), (-1, -1))
        self.savetor = [self.savetorrb1, savetorrb2, savetorrb3]

        savetordefbox = wx.BoxSizer(wx.HORIZONTAL)
        savetordefbox.Add(self.savetorrb1, 0, wx.ALIGN_CENTER_VERTICAL)
        self.savetordeftext = wx.TextCtrl(self, -1, "")
        browsebtn = wx.Button(self, -1, "...", style = wx.BU_EXACTFIT)
        browsebtn.Bind(wx.EVT_BUTTON, self.onBrowseDir)
        savetordefbox.Add(self.savetordeftext, 1, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
        savetordefbox.Add(browsebtn, 0, wx.ALIGN_CENTER_VERTICAL|wx.LEFT|wx.RIGHT, 3)
        savetorrentbox.Add(savetordefbox, 0, wx.EXPAND)
        
        savetorrentbox.Add(savetorrb2, 0)

        savetorrentbox.Add(savetorrb3, 0, wx.TOP, 4)

        outerbox.Add(savetorrentbox, 0, wx.EXPAND|wx.TOP|wx.BOTTOM, 5)

        optionalhash_title = wx.StaticBox(self, -1, self.utility.lang.get('makehash_optional'))
        optionalhash = wx.StaticBoxSizer(optionalhash_title, wx.VERTICAL)

        self.makehash_md5 = wx.CheckBox(self, -1, self.utility.lang.get('makehash_md5'))
        optionalhash.Add(self.makehash_md5, 0)

        self.makehash_crc32 = wx.CheckBox(self, -1, self.utility.lang.get('makehash_crc32'))
        optionalhash.Add(self.makehash_crc32, 0, wx.TOP, 4)

        self.makehash_sha1 = wx.CheckBox(self, -1, self.utility.lang.get('makehash_sha1'))
        optionalhash.Add(self.makehash_sha1, 0, wx.TOP, 4)
        
        self.createtorrentsig = wx.CheckBox(self, -1, self.utility.lang.get('createtorrentsig'))
        optionalhash.Add(self.createtorrentsig, 0, wx.TOP, 4)

        outerbox.Add(optionalhash, 0, wx.EXPAND|wx.TOP|wx.BOTTOM, 5)

        self.startnow = wx.CheckBox(self, -1, self.utility.lang.get('startnow'))
        outerbox.Add(self.startnow, 0, wx.ALIGN_LEFT|wx.ALL, 5)

        self.SetSizerAndFit(outerbox)
        
        self.loadValues()

#        panel.DragAcceptFiles(True)
#        wx.EVT_DROP_FILES(panel, self.selectdrop)

    def loadValues(self, Read = None):
        if Read is None:
            Read = self.utility.makerconfig.Read
        self.startnow.SetValue(Read('startnow', "boolean"))
        self.makehash_md5.SetValue(Read('makehash_md5', "boolean"))
        self.makehash_crc32.SetValue(Read('makehash_crc32', "boolean"))
        self.makehash_sha1.SetValue(Read('makehash_sha1', "boolean"))
        self.createmerkletorrent.SetValue(Read('createmerkletorrent', "boolean"))
        self.createtorrentsig.SetValue(Read('createtorrentsig', "boolean"))
        
        self.savetor[Read('savetorrent', "int")].SetValue(True)        
        self.piece_length.SetSelection(Read('piece_size', "int"))
        self.savetordeftext.SetValue(Read('savetordeffolder'))
        
    def saveConfig(self, event = None):        
        self.utility.makerconfig.Write('startnow', self.startnow.GetValue(), "boolean")
        
        self.utility.makerconfig.Write('makehash_md5', self.makehash_md5.GetValue(), "boolean")
        self.utility.makerconfig.Write('makehash_crc32', self.makehash_crc32.GetValue(), "boolean")
        self.utility.makerconfig.Write('makehash_sha1', self.makehash_sha1.GetValue(), "boolean")
        self.utility.makerconfig.Write('createmerkletorrent', self.createmerkletorrent.GetValue(), "boolean")
        self.utility.makerconfig.Write('createtorrentsig', self.createtorrentsig.GetValue(), "boolean")
            
        self.utility.makerconfig.Write('savetordeffolder', self.savetordeftext.GetValue())

        for i in range(3):
            if self.savetor[i].GetValue():
                self.utility.makerconfig.Write('savetorrent', i)
                break
        self.utility.makerconfig.Write('piece_size', self.piece_length.GetSelection())

    def selectDir(self, event = None):
        dlg = wx.DirDialog(self.dialog, 
                           self.utility.lang.get('selectdir'), 
                           style = wx.DD_DEFAULT_STYLE | wx.DD_NEW_DIR_BUTTON)
        if dlg.ShowModal() == wx.ID_OK:
            self.dirCtl.SetValue(dlg.GetPath())
        dlg.Destroy()

    def onBrowseDir(self, event = None):
        dlg = wx.DirDialog(self.dialog, 
                           self.utility.lang.get('choosetordeffolder'), 
                           style = wx.DD_DEFAULT_STYLE | wx.DD_NEW_DIR_BUTTON)
        if dlg.ShowModal() == wx.ID_OK:
            self.savetordeftext.SetValue(dlg.GetPath())
        dlg.Destroy()

    def selectFile(self, event = None):
        dlg = wx.FileDialog(self.dialog, 
                            self.utility.lang.get('choosefiletouse'), 
                            '', 
                            '', 
                            self.utility.lang.get('allfileswildcard') + ' (*.*)|*.*', 
                            wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            self.dirCtl.SetValue(dlg.GetPath())
        dlg.Destroy()

    def selectdrop(self, x):
        list = x.m_files
        self.dirCtl.SetValue(x[0])
    
    def getParams(self):
        params = {}
        self.targeted = []
        
        params['piece length'] = self.piece_length_list[self.piece_length.GetSelection()]
        
        if self.makehash_md5.GetValue():
            params['makehash_md5'] = True
        if self.makehash_crc32.GetValue():
            params['makehash_crc32'] = True
        if self.makehash_sha1.GetValue():
            params['makehash_sha1'] = True   
        if self.createmerkletorrent.GetValue():
            params['createmerkletorrent'] = 1
        if self.createtorrentsig.GetValue():
            params['torrentsigkeypairfilename'] = self.utility.session.get_permid_keypair_filename()
##
        for i in range(3):
            if self.savetor[i].GetValue():
                break
        
        if i == 0:
            defdestfolder = self.savetordeftext.GetValue()                    
#

            # Check if default download folder is not a file and create it if necessary
            if os.path.exists(defdestfolder):
                if not os.path.isdir(defdestfolder):
                    dlg = wx.MessageDialog(self, 
                                           message = self.utility.lang.get('notadir') + '\n' + \
                                                     self.utility.lang.get('savedtofolderwithsource'), 
                                           caption = self.utility.lang.get('error'), 
                                           style = wx.OK | wx.ICON_ERROR)
                    dlg.ShowModal()
                    dlg.Destroy()
                    defdestfolder = ""
            else:
                try:
                    os.makedirs(defdestfolder)
                except:
                    dlg = wx.MessageDialog(self, 
                                           message = self.utility.lang.get('invalidwinname') + '\n'+ \
                                                     self.utility.lang.get('savedtofolderwithsource'), 
                                           caption = self.utility.lang.get('error'), 
                                           style = wx.OK | wx.ICON_ERROR)
                    dlg.ShowModal()
                    dlg.Destroy()
                    defdestfolder = ""
                     

#                
            params['target'] = defdestfolder
                
            self.targeted = defdestfolder                 

        elif i == 2:
            dl = wx.DirDialog(self, style = wx.DD_DEFAULT_STYLE | wx.DD_NEW_DIR_BUTTON)
            result = dl.ShowModal()
            dl.Destroy()
            if result != wx.ID_OK:
                return
            params['target'] = dl.GetPath()
            self.targeted = dl.GetPath()
        else:
            self.targeted = ""

        return params
    
    def getTargeted(self):
        targeted = self.targeted
        return targeted


################################################################
#
# Class: TorrentMaker
#
# Creates the dialog for making a torrent
#
################################################################
class TorrentMaker(wx.Frame):
    def __init__(self, parent):
        self.parent = parent
        self.utility = self.parent.utility

        title = self.utility.lang.get('btfilemakertitle')
        wx.Frame.__init__(self, None, -1, title)

        if sys.platform == 'win32':
            self.SetIcon(self.utility.icon)

        panel = wx.Panel(self, -1)
        
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.notebook = wx.Notebook(panel, -1)
                
        self.fileInfoPanel = FileInfoPanel(self.notebook, self)
        self.notebook.AddPage(self.fileInfoPanel, self.utility.lang.get('fileinfo'))
        
        self.trackerInfoPanel = TrackerInfoPanel(self.notebook, self)
        self.notebook.AddPage(self.trackerInfoPanel, self.utility.lang.get('trackerinfo'))

        self.miscInfoPanel = MiscInfoPanel(self.notebook, self)
        self.notebook.AddPage(self.miscInfoPanel, self.utility.lang.get('miscinfo'))
        
        sizer.Add(self.notebook, 1, wx.EXPAND|wx.ALL, 5)        
        
        btnbox = wx.BoxSizer(wx.HORIZONTAL)
        b3 = wx.Button(panel, -1, self.utility.lang.get('saveasdefaultconfig'))
        btnbox.Add(b3, 0, wx.EXPAND)

        b2 = wx.Button(panel, -1, self.utility.lang.get('maketorrent'))
        btnbox.Add(b2, 0, wx.EXPAND|wx.LEFT|wx.RIGHT, 10)

        b4 = wx.Button(panel, -1, self.utility.lang.get('close'))
        btnbox.Add(b4, 0, wx.EXPAND)
        
        sizer.Add(btnbox, 0, wx.ALIGN_CENTER|wx.ALL, 10)

        wx.EVT_BUTTON(panel, b2.GetId(), self.complete)
        wx.EVT_BUTTON(panel, b3.GetId(), self.saveConfig)
        wx.EVT_BUTTON(panel, b4.GetId(), self.closeWin)

        panel.SetSizerAndFit(sizer)
        
        self.Fit()
        
        self.Show()

    def closeWin(self, event = None):
        savetordeffolder = self.fileInfoPanel.savetordeftext.GetValue()
        self.utility.makerconfig.Write('savetordeffolder', savetordeffolder)
        self.utility.makerconfig.Write('announcehistory', self.trackerInfoPanel.announcehistory, "bencode-list")

        self.Destroy()
        
    def saveConfig(self, event = None):
        self.fileInfoPanel.saveConfig()
        self.trackerInfoPanel.saveConfig()
        self.miscInfoPanel.saveConfig()
        
        self.utility.makerconfig.Flush()
    
    def complete(self, event = None):
        if DEBUG:
            print "complete thread",currentThread()

        filename = self.fileInfoPanel.dirCtl.GetValue()
        if filename == '':
            dlg = wx.MessageDialog(self, message = self.utility.lang.get('youmustselectfileordir'), 
                caption = self.utility.lang.get('error'), style = wx.OK | wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            return
        
        params = {}
        params.update(tdefdefaults)
        params.update(self.fileInfoPanel.getParams())
        params.update(self.trackerInfoPanel.getParams())
        params.update(self.miscInfoPanel.getParams())

        try:
            CompleteDir(self, filename, params)
        except:
            oldstdout = sys.stdout
            sys.stdout = sys.stderr
            print_exc()
            sys.stdout = oldstdout


################################################################
#
# Class: CompleteDir
#
# Creating torrents for one or more files
#
################################################################
class CompleteDir:
    def __init__(self, parent, srcpath, params):
        self.srcpath = srcpath
        self.params = params
        self.startnow = parent.fileInfoPanel.startnow.GetValue() 
        
        self.usinginternaltracker = False
        if 'usinginternaltracker' in params:
            self.usinginternaltracker = params['usinginternaltracker']
            del params['usinginternaltracker']
            self.startnow = True # Always start seeding immediately
            
        self.params = params
        self.parent = parent
        self.utility = self.parent.utility
        self.flag = Event()
        self.separatetorrents = False
        self.files = []
        
        if os.path.isdir(srcpath):
            self.choicemade = Event()
            frame = wx.Frame(None, -1, self.utility.lang.get('btmaketorrenttitle'), size = (1, 1))
            self.frame = frame
            panel = wx.Panel(frame, -1)
            gridSizer = wx.FlexGridSizer(cols = 1, vgap = 8, hgap = 8)
            gridSizer.AddGrowableRow(1)
            gridSizer.Add(wx.StaticText(panel, -1, 
                    self.utility.lang.get('dirnotice')), 0, wx.ALIGN_CENTER)
            gridSizer.Add(wx.StaticText(panel, -1, ''))

            b = wx.FlexGridSizer(cols = 3, hgap = 10)
            yesbut = wx.Button(panel, -1, self.utility.lang.get('yes'))
            def saidyes(e, self = self):
                self.frame.Destroy()
                self.separatetorrents = True
                self.begin()
            wx.EVT_BUTTON(frame, yesbut.GetId(), saidyes)
            b.Add(yesbut, 0)

            nobut = wx.Button(panel, -1, self.utility.lang.get('no'))
            def saidno(e, self = self):
                self.frame.Destroy()
                self.begin()
            wx.EVT_BUTTON(frame, nobut.GetId(), saidno)
            b.Add(nobut, 0)

            cancelbut = wx.Button(panel, -1, self.utility.lang.get('cancel'))
            def canceled(e, self = self):
                self.frame.Destroy()                
            wx.EVT_BUTTON(frame, cancelbut.GetId(), canceled)
            b.Add(cancelbut, 0)
            gridSizer.Add(b, 0, wx.ALIGN_CENTER)
            border = wx.BoxSizer(wx.HORIZONTAL)
            border.Add(gridSizer, 1, wx.EXPAND | wx.ALL, 4)
            
            panel.SetSizer(border)
            panel.SetAutoLayout(True)
            frame.Show()
            border.Fit(panel)
            frame.Fit()
        else:
            self.begin()

    def begin(self):
        if self.separatetorrents:
            frame = wx.Frame(None, -1, self.utility.lang.get('btmakedirtitle'), size = wx.Size(550, 250))
        else:
            frame = wx.Frame(None, -1, self.utility.lang.get('btmaketorrenttitle'), size = wx.Size(550, 250))
        self.frame = frame

        panel = wx.Panel(frame, -1)
        gridSizer = wx.FlexGridSizer(cols = 1, vgap = 15, hgap = 8)

        if self.separatetorrents:
            self.currentLabel = wx.StaticText(panel, -1, self.utility.lang.get('checkfilesize'))
        else:
            self.currentLabel = wx.StaticText(panel, -1, self.utility.lang.get('building'))
        gridSizer.Add(self.currentLabel, 0, wx.EXPAND)
        self.gauge = wx.Gauge(panel, -1, range = 1000, style = wx.GA_SMOOTH)
        gridSizer.Add(self.gauge, 0, wx.EXPAND)
        gridSizer.Add((10, 10), 1, wx.EXPAND)
        self.button = wx.Button(panel, -1, self.utility.lang.get('cancel'))
        gridSizer.Add(self.button, 0, wx.ALIGN_CENTER)
        gridSizer.AddGrowableRow(2)
        gridSizer.AddGrowableCol(0)

        g2 = wx.FlexGridSizer(cols = 1, vgap = 15, hgap = 8)
        g2.Add(gridSizer, 1, wx.EXPAND | wx.ALL, 25)
        g2.AddGrowableRow(0)
        g2.AddGrowableCol(0)
        panel.SetSizer(g2)
        panel.SetAutoLayout(True)
        wx.EVT_BUTTON(frame, self.button.GetId(), self.onDone)
        wx.EVT_CLOSE(frame, self.onDone)
        frame.Show(True)
        Thread(target = self.complete).start()

    def complete(self):        
        try:
            if self.separatetorrents:
                completedir(self.srcpath, self.params, self.flag, self.progressCallback, self.fileCallback)
            else:
                make_meta_file(self.srcpath, self.params, self.flag, self.progressCallback, self.fileCallback)
            if not self.flag.isSet():
                self.completeCallback()
        except (OSError, IOError), e:
            self.errorCallback(e)

    def errorCallback(self,e):
        wx.CallAfter(self.onError,e)
    
    def onError(self,e):
        self.currentLabel.SetLabel(self.utility.lang.get('error'))
        self.button.SetLabel(self.utility.lang.get('close'))
        dlg = wx.MessageDialog(None, 
                               message = self.utility.lang.get('error') + ' - ' + str(e), 
                               caption = self.utility.lang.get('error'), 
                               style = wx.OK | wx.ICON_ERROR)
        dlg.ShowModal()
        dlg.Destroy()

    def completeCallback(self):
        wx.CallAfter(self.onComplete)
    
    def onComplete(self):
        self.currentLabel.SetLabel(self.utility.lang.get('Done'))
        self.gauge.SetValue(1000)
        self.button.SetLabel(self.utility.lang.get('close'))

    def progressCallback(self, amount):
        wx.CallAfter(self.OnProgressUpdate,amount)

    def OnProgressUpdate(self, amount):
        target = int(amount * 1000)
        old = self.gauge.GetValue()
        perc10 = self.gauge.GetRange()/10
        if target > old+perc10: # 10% increments
            self.gauge.SetValue(target)

    def fileCallback(self, orig, torrent):
        self.files.append([orig,torrent])
        wx.CallAfter(self.onFile,torrent)

    def onFile(self, torrent):
        if DEBUG:
            print "onFile thread",currentThread()
        self.currentLabel.SetLabel(self.utility.lang.get('building') + torrent)

    def onDone(self, event):
        self.flag.set()
        self.frame.Destroy()
        if self.startnow:
            # When seeding immediately, add torrents to queue
            for orig,torrentfilename in self.files:
                try:
                    absorig = os.path.abspath(orig)
                    if os.path.isfile(absorig):
                        # To seed a file, destdir must be one up.
                        destdir = os.path.dirname(absorig) 
                    else:
                        destdir = absorig
                        
                    tdef = TorrentDef.load(torrentfilename)
                    defaultDLConfig = DefaultDownloadStartupConfig.getInstance()
                    dscfg = defaultDLConfig.copy()
                    dscfg.set_dest_dir(destdir)
                    self.utility.session.start_download(tdef,dscfg)
                    
                except Exception,e:
                    print_exc()
                    self.onError(e)


def make_meta_file(srcpath,params,userabortflag,progressCallback,torrentfilenameCallback):
    
    tdef = TorrentDef()
    
    if not os.path.isdir(srcpath):
        if 'playtime' in params:
            tdef.add_content(srcpath,playtime=params['playtime'])
        else:
            tdef.add_content(srcpath)
    else:
        srcbasename = os.path.basename(os.path.normpath(srcpath))
        for filename in os.listdir(srcpath):
            inpath = os.path.join(srcpath,filename)
            outpath = os.path.join(srcbasename,filename)
            # h4x0r playtime
            if 'playtime' in params:
                tdef.add_content(inpath,outpath,playtime=params['playtime'])
            else:
                tdef.add_content(inpath,outpath)
            
    if params['comment']:
        tdef.set_comment(params['comment'])
    if params['created by']:
        tdef.set_created_by(params['created by'])
    if params['announce']:
        tdef.set_tracker(params['announce'])
    if params['announce-list']:
        tdef.set_tracker_hierarchy(params['announce-list'])
    if params['nodes']: # mainline DHT
        tdef.set_dht_nodes(params['nodes'])
    if params['httpseeds']:
        tdef.set_httpseeds(params['httpseeds'])
    if params['encoding']:
        tdef.set_encoding(params['encoding'])
    if params['piece length']:
        tdef.set_piece_length(params['piece length'])
    if params['makehash_md5']:
        print >>sys.stderr,"TorrentMaker: make MD5"
        tdef.set_add_md5hash(params['makehash_md5'])
    if params['makehash_crc32']:
        print >>sys.stderr,"TorrentMaker: make CRC32"
        tdef.set_add_crc32(params['makehash_crc32'])
    if params['makehash_sha1']:
        print >>sys.stderr,"TorrentMaker: make SHA1"
        tdef.set_add_sha1hash(params['makehash_sha1'])
    if params['createmerkletorrent']:
        tdef.set_create_merkle_torrent(params['createmerkletorrent'])
    if params['torrentsigkeypairfilename']:
        tdef.set_signature_keypair_filename(params['torrentsigkeypairfilename'])
    if params['thumb']:
        tdef.set_thumbnail(params['thumb'])
        
    tdef.finalize(userabortflag=userabortflag,userprogresscallback=progressCallback)
    
    if params['createmerkletorrent']:
        postfix = TRIBLER_TORRENT_EXT
    else:
        postfix = '.torrent'
    
    if 'target' in params and params['target']:
        torrentfilename = os.path.join(params['target'], os.path.split(os.path.normpath(srcpath))[1] + postfix)
    else:
        a, b = os.path.split(srcpath)
        if b == '':
            torrentfilename = a + postfix
        else:
            torrentfilename = os.path.join(a, b + postfix)
            
    tdef.save(torrentfilename)
    
    # Inform higher layer we created torrent
    torrentfilenameCallback(srcpath,torrentfilename)
    
def completedir(srcpath, params, userabortflag, progressCallback, torrentfilenameCallback):
    merkle_torrent = params['createmerkletorrent'] == 1
    if merkle_torrent:
        ext = TRIBLER_TORRENT_EXT
    else:
        ext = '.torrent'
    srcfiles = os.listdir(srcpath)
    srcfiles.sort()

    # Filter out any .torrent files
    goodfiles = []
    for srcfile in srcfiles:
        if srcfile[-len(ext):] != ext and (srcfile + ext) not in srcfiles:
            goodfile = os.path.join(srcpath, srcfile)
            goodfiles.append(goodfile)
        
    for goodfile in goodfiles:
        basename = os.path.split(goodfile)[-1]
        # Ignore cores, CVS and dotfiles
        if basename not in FILESTOIGNORE and basename[0] != '.':
            make_meta_file(goodfile, params,userabortflag,progressCallback,torrentfilenameCallback)
    
