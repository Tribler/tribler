#!/usr/bin/env python

# Written by Bram Cohen
# modified for multitracker by John Hoffman
# see LICENSE.txt for license information

from BitTornado import PSYCO
if PSYCO.psyco:
    try:
        import psyco
        assert psyco.__version__ >= 0x010100f0
        psyco.full()
    except:
        pass

import sys
import wx

from os.path import join, isdir
from threading import Event, Thread

from btcompletedir import completedir
from btmakemetafile import make_meta_file
from traceback import print_exc

try:
    True
except:
    True = 1
    False = 0

wxEVT_INVOKE = wx.NewEventType()

def EVT_INVOKE(win, func):
    win.Connect(-1, -1, wxEVT_INVOKE, func)

class InvokeEvent(wx.PyEvent):
    def __init__(self, func, args, kwargs):
        wx.PyEvent.__init__(self)
        self.SetEventType(wxEVT_INVOKE)
        self.func = func
        self.args = args
        self.kwargs = kwargs

class AnnounceFile:
    def __init__(self, announceconf):
        self.announcelst = []
        self.piece_size = 0
        self.announcedefault = ""
        self.announceconf = announceconf

    def readConfig(self):        
        f = open(self.announceconf, 'rb')
        while True:
            configline = f.readline()        
            if configline == "" or configline == "\n":
                break
            else:
                configmap = configline.split("=")
                if configmap[0] == "piece_size":
                    self.piece_size = int(configmap[1][0:-1])
                elif configmap[0] == "announce":
                    self.announcelst.append(configmap[1][0:-1])
                elif configmap[0] == "announcedefault":
                    self.announcelst.append(configmap[1][0:-1])
                    self.announcedefault = configmap[1][0:-1]

        f.close()
        return self.announcedefault, self.announcelst, self.piece_size

    def saveDefault(self, piece, url):
        numslot = -1
        self.piece_size = piece
        for i in range(0, len(self.announcelst)):
           if self.announcelst[i] == url:
               numslot = i
               break
        if numslot == -1:   #current URL is bad
            if len(self.announcelst) != 0:
                self.announcedefault = self.announcelst[0]
                
        f = open(self.announceconf, 'wb')
        f.writelines("piece_size=" + str(piece) + "\n")        
        for i in range(0, len(self.announcelst)):
            if self.announcelst[i] == self.announcedefault:
                f.writelines("announcedefault="+self.announcedefault+"\n")
            else:
                f.writelines("announce="+self.announcelst[i]+"\n")
        f.close()      
        
    def addAnnounce(self, url):
        self.announcelst.append(url)
        self.announcedefault = url
        f = open(self.announceconf, 'wb')
        f.writelines("piece_size=" + str(self.piece_size) + "\n")        
        for i in range(0, len(self.announcelst)):
            if self.announcelst[i] == self.announcedefault:
                f.writelines("announcedefault="+self.announcedefault+"\n")
            else:
                f.writelines("announce="+self.announcelst[i]+"\n")
        f.close()

    def removeAnnounce(self, url):
        numslot = -1
        for i in range(0, len(self.announcelst)):
           if self.announcelst[i] == url:
               numslot = i
               break
        if numslot == -1:
            return
        else:
            del self.announcelst[i]
            if self.announcedefault == url:
                if len(self.announcelst) != 0:
                    self.announcedefault = self.announcelst[0]
                else:
                    self.announcedefault = ''
        
        f = open(self.announceconf, 'wb')
        f.writelines("piece_size=" + str(self.piece_size) + "\n")        
        for i in range(0, len(self.announcelst)):
            if self.announcelst[i] == self.announcedefault:
                f.writelines("announcedefault="+self.announcedefault+"\n")
            else:
                f.writelines("announce="+self.announcelst[i]+"\n")
        f.close()

class DownloadInfo:
    def __init__(self, parent):

        self.parent = parent
        self.utility = self.parent.utility
        
        frame = wx.Frame(self.parent, -1, self.utility.lang.get('btfilemakertitle'), size = wx.Size(550, 410))
        self.frame = frame

        try:
            self.frame.SetIcon(self.utility.icon)
        except:
            pass

        self.announceconf = AnnounceFile(join(self.utility.getPath(), "announce.lst"))        
        # Read config file
        #########################
        self.announcedefault, self.announcelst, self.piece_size = self.announceconf.readConfig()

        panel = wx.Panel(frame, -1)
        
        outerbox = wx.BoxSizer(wx.VERTICAL)

        # Make torrent of:
        maketorrent_box = wx.BoxSizer(wx.HORIZONTAL)
        maketorrent_box.Add(wx.StaticText(panel, -1, self.utility.lang.get('maketorrentof')))

        self.dirCtl = wx.TextCtrl(panel, -1, '')
        maketorrent_box.Add(self.dirCtl, 1, wx.EXPAND|wx.LEFT|wx.RIGHT, 10)

        button = wx.Button(panel, -1, self.utility.lang.get('dir'))
        wx.EVT_BUTTON(frame, button.GetId(), self.selectdir)
        maketorrent_box.Add(button, 0, wx.RIGHT, 5)

        button2 = wx.Button(panel, -1, self.utility.lang.get('file'))
        wx.EVT_BUTTON(frame, button2.GetId(), self.selectfile)
        maketorrent_box.Add(button2, 0)

        outerbox.Add(maketorrent_box, 0, wx.EXPAND|wx.ALL, 10)

        # Announce url:
        announceurl_box = wx.BoxSizer(wx.HORIZONTAL)
        announceurl_box.Add(wx.StaticText(panel, -1, self.utility.lang.get('announceurl')))
       
        self.annCtl = wx.ComboBox(panel, -1, self.announcedefault,choices=self.announcelst, style=wx.CB_DROPDOWN)
        announceurl_box.Add(self.annCtl, 1, wx.EXPAND|wx.LEFT|wx.RIGHT, 10)
        
        button = wx.Button(panel, -1,self.utility.lang.get('add'))
        wx.EVT_BUTTON(frame, button.GetId(), self.addAnnounce)
        announceurl_box.Add(button, 0, wx.RIGHT, 5)

        button2 = wx.Button(panel, -1, self.utility.lang.get('remove'))
        wx.EVT_BUTTON(frame, button2.GetId(), self.removeAnnounce)
        announceurl_box.Add(button2, 0)        

        outerbox.Add(announceurl_box, 0, wx.EXPAND|wx.ALL, 10)

        # Announce List:      
        announcelist_box = wx.BoxSizer(wx.HORIZONTAL)
        
        announcelist_box1 = wx.BoxSizer(wx.VERTICAL)
        
        announcelist_box1.Add(wx.StaticText(panel, -1, self.utility.lang.get('announcelist')), 0, wx.EXPAND)
        
        abutton = wx.Button(panel, -1, self.utility.lang.get('copyannouncefromtorrent'))
        wx.EVT_BUTTON(frame, abutton.GetId(), self.announcecopy)

        announcelist_box1.Add(abutton, -1, wx.EXPAND|wx.TOP|wx.BOTTOM|wx.RIGHT, 10)
        
        announcelist_box.Add(announcelist_box1, 0, wx.EXPAND)
       
        announcelist_box2 = wx.BoxSizer(wx.VERTICAL)

        self.annListCtl = wx.TextCtrl(panel, -1, '\n\n\n\n\n', wx.Point(-1,-1), (-1, -1),
                                            wx.TE_MULTILINE|wx.HSCROLL|wx.TE_DONTWRAP)
        announcelist_box2.Add(self.annListCtl, -1, wx.EXPAND)

        exptext = wx.StaticText(panel, -1, self.utility.lang.get('multiannouncehelp'))
        announcelist_box2.Add(exptext, 0, wx.EXPAND)
        
        announcelist_box.Add(announcelist_box2, -1, wx.EXPAND)

        outerbox.Add(announcelist_box, 0, wx.EXPAND|wx.ALL, 10)


        # Piece size:
        piecesize_box = wx.BoxSizer(wx.HORIZONTAL)
        
        piecesize_box.Add(wx.StaticText(panel, -1, self.utility.lang.get('piecesize')))
        
        abbrev_mb = " " + self.utility.lang.get('MB')
        abbrev_kb = " " + self.utility.lang.get('KB')
        
        self.piece_length = wx.Choice(panel,
                                      -1,
                                      choices = [self.utility.lang.get('automatic'),
                                                 '2' + abbrev_mb,
                                                 '1' + abbrev_mb,
                                                 '512' + abbrev_kb,
                                                 '256' + abbrev_kb,
                                                 '128' + abbrev_kb,
                                                 '64' + abbrev_kb,
                                                 '32' + abbrev_kb])
        self.piece_length_list = [0,       21,     20,      19,       18,       17,      16,      15]
        self.piece_length.SetSelection(self.piece_size)
        piecesize_box.Add(self.piece_length, 0, wx.LEFT|wx.RIGHT, 10)
        
        outerbox.Add(piecesize_box, 0, wx.EXPAND|wx.ALL, 10)

        # Comment:        

        comment_box = wx.BoxSizer(wx.HORIZONTAL)
        comment_box.Add(wx.StaticText(panel, -1, self.utility.lang.get('comment')))
        self.commentCtl = wx.TextCtrl(panel, -1, '')
        comment_box.Add(self.commentCtl, -1, wx.EXPAND|wx.LEFT|wx.RIGHT, 10)
        
        outerbox.Add(comment_box, 0, wx.EXPAND|wx.ALL, 10)

        btnbox = wx.BoxSizer(wx.HORIZONTAL)
        b3 = wx.Button(panel, -1, self.utility.lang.get('saveasdefaultconfig'))
        btnbox.Add(b3, 0, wx.EXPAND)

        b2 = wx.Button(panel, -1, self.utility.lang.get('maketorrent'))
        btnbox.Add(b2, 0, wx.EXPAND|wx.LEFT|wx.RIGHT, 10)

        b4 = wx.Button(panel, -1, self.utility.lang.get('close'))
        btnbox.Add(b4, 0, wx.EXPAND)
        
        outerbox.Add(btnbox, 0, wx.ALIGN_CENTER)

        wx.EVT_BUTTON(frame, b2.GetId(), self.complete)
        wx.EVT_BUTTON(frame, b3.GetId(), self.saveconfig)
        wx.EVT_BUTTON(frame, b4.GetId(), self.closewin)

        panel.SetSizer(outerbox)
        panel.SetAutoLayout(True)
        panel.Fit()
        
        self.frame.Fit()

#        panel.DragAcceptFiles(True)
#        wx.EVT_DROP_FILES(panel, self.selectdrop)

    def closewin(self, x):
        self.frame.Destroy()
        
    def saveconfig(self, x):
        self.piece_length.GetSelection()
        self.announceconf.saveDefault(self.piece_length.GetSelection(), self.annCtl.GetValue())
        
    def addAnnounce(self, x):
        announceurl = self.annCtl.GetValue()
        if announceurl == "":
            return
        self.annCtl.Append(announceurl)
        self.announceconf.addAnnounce(announceurl)
        
    def removeAnnounce(self, x):
        if self.annCtl.GetSelection() == -1:
            dlg = wx.MessageDialog(self.frame, self.utility.lang.get('errorremoveannounceurl'), self.utility.lang.get('error'), wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
        else:
            announceurl = self.annCtl.GetValue()
            i = self.annCtl.GetSelection()
            self.announceconf.removeAnnounce(announceurl)
            self.annCtl.Delete(i)
        
    def selectdir(self, x):
        dl = wx.DirDialog(self.frame, style = wx.DD_DEFAULT_STYLE | wx.DD_NEW_DIR_BUTTON)
        if dl.ShowModal() == wx.ID_OK:
            self.dirCtl.SetValue(dl.GetPath())

    def selectfile(self, x):
        dl = wx.FileDialog (self.frame, self.utility.lang.get('choosefiletouse'), '', '', '', wx.OPEN)
        if dl.ShowModal() == wx.ID_OK:
            self.dirCtl.SetValue(dl.GetPath())

    def selectdrop(self, x):
        list = x.m_files
        self.dirCtl.SetValue(x[0])

    def announcecopy(self, x):
        dl = wx.FileDialog (self.frame, self.utility.lang.get('choosedottorrentfiletouse'), '', '', '*.torrent', wx.OPEN)
        if dl.ShowModal() == wx.ID_OK:
            try:
                metainfo = self.utility.getMetainfo(dl.GetPath())
                if (metainfo is None):
                    return
                self.annCtl.SetValue(metainfo['announce'])
                if metainfo.has_key('announce-list'):
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

    def getannouncelist(self):
        list = []
        for t in self.annListCtl.GetValue().split('\n'):
            tier = []
            t = t.replace(',',' ')
            for tr in t.split(' '):
                if tr != '':
                    tier += [tr]
            if len(tier)>0:
                list.append(tier)
        return list
    
    def complete(self, x):
        if self.dirCtl.GetValue() == '':
            dlg = wx.MessageDialog(self.frame, message = self.utility.lang.get('youmustselectfileordir'), 
                caption = self.utility.lang.get('error'), style = wx.OK | wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            return
        params = {'piece_size_pow2': self.piece_length_list[self.piece_length.GetSelection()]}
        annlist = self.getannouncelist()
        if len(annlist)>0:
            params['real_announce_list'] = annlist
        comment = self.commentCtl.GetValue()
        if comment != '':
            params['comment'] = comment
        try:
            CompleteDir(self, self.dirCtl.GetValue(), self.annCtl.GetValue(), params)
        except:
            oldstdout = sys.stdout
            sys.stdout = sys.stderr
            print_exc()
            sys.stdout = oldstdout

from traceback import print_exc

class CompleteDir:
    def __init__(self, parent, d, a, params):
        self.d = d
        self.a = a
        self.params = params
        self.parent = parent
        self.utility = self.parent.utility
        self.flag = Event()
        self.separatetorrents = False

        if isdir(d):
            self.choicemade = Event()
            frame = wx.Frame(None, -1, self.utility.lang.get('btmaketorrenttitle'), size = (1,1))
            self.frame = frame
            panel = wx.Panel(frame, -1)
            gridSizer = wx.FlexGridSizer(cols = 1, vgap = 8, hgap = 8)
            gridSizer.AddGrowableRow(1)
            gridSizer.Add(wx.StaticText(panel, -1,
                    self.utility.lang.get('dirnotice')),0,wx.ALIGN_CENTER)
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
            self.currentLabel = wx.StaticText(panel, -1, self.utility.lang.get('building') + self.d + '.torrent')
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
        wx.EVT_BUTTON(frame, self.button.GetId(), self.done)
        wx.EVT_CLOSE(frame, self.done)
        EVT_INVOKE(frame, self.onInvoke)
        frame.Show(True)
        Thread(target = self.complete).start()

    def complete(self):
        try:
            if self.separatetorrents:
                completedir(self.d, self.a, self.params, self.flag,
                            self.valcallback, self.filecallback)
            else:
                make_meta_file(self.d, self.a, self.params, self.flag,
                            self.valcallback, progress_percent = 1)
            if not self.flag.isSet():
                self.currentLabel.SetLabel(self.utility.lang.get('Done'))
                self.gauge.SetValue(1000)
                self.button.SetLabel(self.utility.lang.get('close'))
                self.frame.Refresh()
        except (OSError, IOError), e:
            self.currentLabel.SetLabel(self.utility.lang.get('error'))
            self.button.SetLabel(self.utility.lang.get('close'))
            dlg = wx.MessageDialog(self.frame, message = self.utility.lang.get('error') + ' - ' + str(e), 
                caption = self.utility.lang.get('error'), style = wx.OK | wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()

    def valcallback(self, amount):
        self.invokeLater(self.onval, [amount])

    def onval(self, amount):
        self.gauge.SetValue(int(amount * 1000))

    def filecallback(self, f):
        self.invokeLater(self.onfile, [f])

    def onfile(self, f):
        self.currentLabel.SetLabel(self.utility.lang.get('building') + join(self.d, f) + '.torrent')

    def onInvoke(self, event):
        if not self.flag.isSet():
            apply(event.func, event.args, event.kwargs)

    def invokeLater(self, func, args = [], kwargs = {}):
        if not self.flag.isSet():
            wx.PostEvent(self.frame, InvokeEvent(func, args, kwargs))

    def done(self, event):
        self.flag.set()
        self.frame.Destroy()

class btWxApp(wx.App):
    def OnInit(self):
        d = DownloadInfo()
        d.frame.Show(True)
        self.SetTopWindow(d.frame)
        return True

if __name__ == '__main__':
    btWxApp().MainLoop()
