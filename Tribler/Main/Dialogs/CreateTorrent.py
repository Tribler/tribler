# Written by Niels Zeilemaker
# see LICENSE.txt for license information

import wx
import os
import sys

from Tribler.Main.vwxGUI.widgets import _set_font, BetterText as StaticText
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.simpledefs import TRIBLER_TORRENT_EXT
from threading import Event
from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue
from Tribler.Main.vwxGUI import forceWxThread
from traceback import print_exc


class CreateTorrent(wx.Dialog):

    def __init__(self, parent, configfile, fileconfigfile, suggestedTrackers, toChannel=False):
        wx.Dialog.__init__(self, parent, -1, 'Create a .torrent', size=(600, 200), name="CreateTorrentDialog")
        self.guiutility = GUIUtility.getInstance()
        self.toChannel = toChannel

        vSizer = wx.BoxSizer(wx.VERTICAL)

        header = wx.StaticText(self, -1, 'Browse for a file or files')
        _set_font(header, fontweight=wx.FONTWEIGHT_BOLD)
        vSizer.Add(header, 0, wx.EXPAND | wx.BOTTOM, 3)

        self.locationText = StaticText(self, -1, '')
        vSizer.Add(self.locationText, 0, wx.EXPAND | wx.BOTTOM, 3)

        browseButton = wx.Button(self, -1, 'Browse')
        browseButton.Bind(wx.EVT_BUTTON, self.OnBrowse)

        browseDirButton = wx.Button(self, -1, 'Browse for a Directory')
        browseDirButton.Bind(wx.EVT_BUTTON, self.OnBrowseDir)

        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(browseButton)
        hSizer.Add(browseDirButton)
        vSizer.Add(hSizer, 0, wx.ALIGN_RIGHT | wx.BOTTOM, 3)

        # self.recursive = wx.CheckBox(self, -1, 'Include all subdirectories')
        # self.recursive.Bind(wx.EVT_CHECKBOX, self.OnRecursive)
        # vSizer.Add(self.recursive, 0, wx.ALIGN_RIGHT|wx.BOTTOM, 3)

        vSizer.Add(wx.StaticLine(self, -1), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        header = wx.StaticText(self, -1, '.Torrent details')
        _set_font(header, fontweight=wx.FONTWEIGHT_BOLD)
        vSizer.Add(header, 0, wx.EXPAND | wx.BOTTOM, 3)

        self.foundFilesText = StaticText(self, -1, 'Please select a file or files first')
        vSizer.Add(self.foundFilesText, 0, wx.EXPAND | wx.BOTTOM, 3)

        self.combineRadio = wx.RadioButton(self, -1, 'Combine files into a single .torrent', style=wx.RB_GROUP)
        self.combineRadio.Bind(wx.EVT_RADIOBUTTON, self.OnCombine)
        self.combineRadio.Enable(False)

        self.sepRadio = wx.RadioButton(self, -1, 'Create separate .torrent for every file')
        self.sepRadio.Bind(wx.EVT_RADIOBUTTON, self.OnCombine)
        self.sepRadio.Enable(False)

        vSizer.Add(self.combineRadio, 0, wx.EXPAND | wx.BOTTOM, 3)
        vSizer.Add(self.sepRadio, 0, wx.EXPAND | wx.BOTTOM, 3)

        self.specifiedName = wx.TextCtrl(self, -1, '')
        self.specifiedName.Enable(False)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(wx.StaticText(self, -1, 'Specify a name'), 0, wx.ALIGN_CENTER_VERTICAL)
        hSizer.Add(self.specifiedName, 1, wx.EXPAND)
        vSizer.Add(hSizer, 0, wx.EXPAND | wx.BOTTOM, 3)

        vSizer.Add(StaticText(self, -1, 'Trackers'))
        self.trackerList = wx.TextCtrl(self, -1, '', style=wx.TE_MULTILINE)
        self.trackerList.SetMinSize((500, -1))

        self.trackerHistory = wx.FileHistory(10)
        self.config = wx.FileConfig(appName="Tribler", localFilename=configfile)
        self.trackerHistory.Load(self.config)

        if self.trackerHistory.GetCount() > 0:
            trackers = [self.trackerHistory.GetHistoryFile(i) for i in range(self.trackerHistory.GetCount())]
            if len(trackers) < len(suggestedTrackers):
                trackers.extend(suggestedTrackers[:len(suggestedTrackers) - len(trackers)])
        else:
            trackers = suggestedTrackers

        for tracker in trackers:
            self.trackerList.AppendText(tracker + "\n")

        vSizer.Add(self.trackerList, 0, wx.EXPAND | wx.BOTTOM, 3)

        vSizer.Add(StaticText(self, -1, 'Comment'))
        self.commentList = wx.TextCtrl(self, -1, '', style=wx.TE_MULTILINE)
        vSizer.Add(self.commentList, 0, wx.EXPAND, 3)

        vSizer.Add(wx.StaticLine(self, -1), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        header = wx.StaticText(self, -1, 'Advanced options')
        _set_font(header, fontweight=wx.FONTWEIGHT_BOLD)
        vSizer.Add(header, 0, wx.EXPAND | wx.BOTTOM | wx.TOP, 3)

        abbrev_mb = " " + self.guiutility.utility.lang.get('MB')
        abbrev_kb = " " + self.guiutility.utility.lang.get('KB')
        piece_choices = [self.guiutility.utility.lang.get('automatic'),
                         '4' + abbrev_mb,
                         '2' + abbrev_mb,
                         '1' + abbrev_mb,
                         '512' + abbrev_kb,
                         '256' + abbrev_kb,
                         '128' + abbrev_kb,
                         '64' + abbrev_kb,
                         '32' + abbrev_kb]
        self.pieceChoice = wx.Choice(self, -1, choices=piece_choices)
        self.pieceChoice.SetSelection(0)
        hSizer = wx.BoxSizer(wx.HORIZONTAL)
        hSizer.Add(StaticText(self, -1, 'Piecesize'), 1)
        hSizer.Add(self.pieceChoice)
        vSizer.Add(hSizer, 0, wx.EXPAND | wx.BOTTOM, 3)

        vSizer.Add(StaticText(self, -1, 'Webseed'))
        self.webSeed = wx.TextCtrl(self, -1, 'Please select a file or files first')
        self.webSeed.Enable(False)
        vSizer.Add(self.webSeed, 0, wx.EXPAND | wx.BOTTOM, 3)

        cancel = wx.Button(self, wx.ID_CANCEL)
        cancel.Bind(wx.EVT_BUTTON, self.OnCancel)

        create = wx.Button(self, wx.ID_OK, 'Create .torrent(s)')
        create.Bind(wx.EVT_BUTTON, self.OnOk)

        bSizer = wx.StdDialogButtonSizer()
        bSizer.AddButton(cancel)
        bSizer.AddButton(create)
        bSizer.Realize()
        vSizer.Add(bSizer, 0, wx.EXPAND)

        sizer = wx.BoxSizer()
        sizer.Add(vSizer, 1, wx.EXPAND | wx.ALL, 10)
        self.SetSizerAndFit(sizer)

        self.selectedPaths = []
        self.createdTorrents = []
        self.cancelEvent = Event()

        self.filehistory = wx.FileHistory(1)
        self.fileconfig = wx.FileConfig(appName="Tribler", localFilename=fileconfigfile)
        self.filehistory.Load(self.fileconfig)

        if self.filehistory.GetCount() > 0:
            self.latestFile = self.filehistory.GetHistoryFile(0)
        else:
            self.latestFile = ''
        self.paths = None

    def OnBrowse(self, event):
        dlg = wx.FileDialog(self, "Please select the file(s).", style=wx.FD_OPEN | wx.FD_MULTIPLE, defaultDir=self.latestFile)
        if dlg.ShowModal() == wx.ID_OK:
            filenames = dlg.GetPaths()
            dlg.Destroy()

            self._browsePaths(filenames)
        else:
            dlg.Destroy()

    def OnBrowseDir(self, event):
        dlg = wx.DirDialog(self, "Please a directory.", style=wx.DD_DIR_MUST_EXIST, defaultPath=self.latestFile)
        if dlg.ShowModal() == wx.ID_OK:
            filenames = [dlg.GetPath()]
            dlg.Destroy()

            self._browsePaths(filenames)
        else:
            dlg.Destroy()

    def OnRecursive(self, event):
        self._browsePaths()

    def OnCombine(self, event=None):
        combine = self.combineRadio.GetValue()
        self.specifiedName.Enable(False)
        if combine:
            path = ''

            nrFiles = len([file for file in self.selectedPaths if os.path.isfile(file)])
            if nrFiles > 1:
                self.specifiedName.Enable(True)
                path = os.path.abspath(os.path.commonprefix(self.selectedPaths))

            elif nrFiles > 0:
                path = self.selectedPaths[0]

            _, name = os.path.split(path)
            self.specifiedName.SetValue(name)

    def OnOk(self, event):
#            if self.specifyNames.GetValue():
#                dlg = wx.Dialog(self, -1, 'Please correct the names for the torrents.', size=(750,450))
#                sizer = wx.BoxSizer(wx.VERTICAL)
#                header = wx.StaticText(dlg, -1, 'Please modify the names for the .torrents.')
#
#                _set_font(header, fontweight=wx.FONTWEIGHT_BOLD)
#                sizer.Add(header, 0, wx.EXPAND|wx.BOTTOM, 3)
#
#                flexSizer =  wx.FlexGridSizer(2,2,3,3)
#                controls = []
#                for name in names:
#                    flexSizer.Add(wx.StaticText(dlg, -1, name), 0, wx.ALIGN_CENTER_VERTICAL)
#                    control = wx.TextCtrl(dlg,-1, name)
#                    control.SetMinSize((300,-1))
#                    flexSizer.Add(control, 1, wx.EXPAND)
#                    controls.append(control)
#
#                sizer.Add(flexSizer, 1, wx.EXPAND|wx.BOTTOM, 3)
#
#                cancel = wx.Button(dlg, wx.ID_CANCEL)
#                ok = wx.Button(dlg, wx.ID_OK)
#
#                bSizer = wx.StdDialogButtonSizer()
#                bSizer.AddButton(cancel)
#                bSizer.AddButton(ok)
#                bSizer.Realize()
#                sizer.Add(bSizer, 0, wx.EXPAND|wx.BOTTOM, 3)
#
#                bsizer = wx.BoxSizer()
#                bsizer.Add(sizer, 1, wx.EXPAND|wx.ALL, 10)
#                dlg.SetSizerAndFit(bsizer)
#
#                if dlg.ShowModal() == wx.ID_OK:
#                    for i, control in enumerate(controls):
#                        names[i] = control.GetValue()
#                    dlg.Destroy()
#                else:
#                    dlg.Destroy()
#                    return

        max = 1 if self.combineRadio.GetValue() else len(self.selectedPaths)
        if self.toChannel:
            dlg = wx.MessageDialog(self, "This will add %d new .torrents to this Channel.\nDo you want to continue?" % max, "Are you sure?", style=wx.YES_NO | wx.ICON_QUESTION)
        else:
            dlg = wx.MessageDialog(self, "This will create %d new .torrents.\nDo you want to continue?" % max, "Are you sure?", style=wx.YES_NO | wx.ICON_QUESTION)

        if dlg.ShowModal() == wx.ID_YES:
            dlg.Destroy()

            params = {}
            params['comment'] = self.commentList.GetValue()
            params['created by'] = '%s version: %s' % (self.guiutility.utility.lang.get('title'), self.guiutility.utility.lang.get('version'))

            trackers = self.trackerList.GetValue()
            trackers = [tracker for tracker in trackers.split('\n') if tracker]

            for tracker in trackers:
                self.trackerHistory.AddFileToHistory(tracker)
            self.trackerHistory.Save(self.config)
            self.config.Flush()

            if len(self.selectedPaths) > 1:
                basedir = os.path.commonprefix(self.selectedPaths)
            else:
                basedir = os.path.dirname(self.selectedPaths[0])
            self.filehistory.Save(self.fileconfig)
            self.fileconfig.Flush()

            params['announce'] = trackers[0]
            params['announce-list'] = [trackers]

            if self.webSeed.GetValue():
                params['urllist'] = [self.webSeed.GetValue()]

            params['nodes'] = False
            params['httpseeds'] = False
            params['encoding'] = False
            params['makehash_md5'] = False
            params['makehash_crc32'] = False
            params['makehash_sha1'] = True
            params['createmerkletorrent'] = False
            params['torrentsigkeypairfilename'] = False
            params['thumb'] = False

            piece_length_list = [0, 2 ** 22, 2 ** 21, 2 ** 20, 2 ** 19, 2 ** 18, 2 ** 17, 2 ** 16, 2 ** 15]
            if self.pieceChoice.GetSelection() != wx.NOT_FOUND:
                params['piece length'] = piece_length_list[self.pieceChoice.GetSelection()]
            else:
                params['piece length'] = 0

            def do_gui():
                if self.cancelEvent.isSet():
                    self.OnCancel(event)
                else:
                    self.EndModal(wx.ID_OK)

            def create_torrents():
                try:
                    if self.combineRadio.GetValue():
                        params['name'] = self.specifiedName.GetValue()
                        make_meta_file(self.selectedPaths, params, self.cancelEvent, None, self._torrentCreated)
                    else:
                        for path in self.selectedPaths:
                            if os.path.isfile(path):
                                make_meta_file([path], params, self.cancelEvent, None, self._torrentCreated)
                except:
                    print_exc()

                wx.CallAfter(do_gui)

            def start():
                if self.combineRadio.GetValue():
                    self.progressDlg = wx.ProgressDialog("Creating new .torrents", "Please wait while Tribler is creating your .torrents.\nThis could take a while due to creating the required hashes.", maximum=max, parent=self, style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE)
                else:
                    self.progressDlg = wx.ProgressDialog("Creating new .torrents", "Please wait while Tribler is creating your .torrents.\nThis could take a while due to creating the required hashes.", maximum=max, parent=self, style=wx.PD_CAN_ABORT | wx.PD_APP_MODAL | wx.PD_ELAPSED_TIME | wx.PD_AUTO_HIDE)
                self.progressDlg.Pulse()
                self.progressDlg.cur = 0

                self.guiserver = GUITaskQueue.getInstance()
                self.guiserver.add_task(create_torrents)

            if params['piece length']:
                total_size = 0
                if self.combineRadio.GetValue():
                    for path in self.selectedPaths:
                        total_size += os.path.getsize(path)
                else:
                    for path in self.selectedPaths:
                        total_size = max(total_size, os.path.getsize(path))

                nrPieces = total_size / params['piece length']
                if nrPieces > 2500:
                    dlg2 = wx.MessageDialog(self, "The selected piecesize will cause a torrent to have %d pieces.\nThis is more than the recommended max 2500 pieces.\nDo you want to continue?" % nrPieces, "Are you sure?", style=wx.YES_NO | wx.ICON_QUESTION)
                    if dlg2.ShowModal() == wx.ID_YES:
                        start()
                    dlg2.Destroy()

                else:
                    start()
            else:
                start()
        else:
            dlg.Destroy()

    def OnCancel(self, event):
        self.EndModal(wx.ID_CANCEL)

    def _browsePaths(self, paths=None):
        if paths:
            self.paths = paths
        else:
            paths = self.paths

        if paths:
            label = ";".join(paths)
            self.locationText.SetLabel(label)

            if os.path.isdir(paths[0]):
                def addDir(path, recursive=False):
                    paths = [path]

                    for file in os.listdir(path):
                        absfile = os.path.join(path, file)

                        if os.path.isfile(absfile):
                            if file.lower().endswith('.torrent') or file.lower().endswith('thumbs.db'):
                                continue
                            paths.append(absfile)

                        elif os.path.isdir(absfile) and recursive:
                            paths.extend(addDir(absfile, recursive))

                    return paths
                paths = addDir(paths[0], False)  # self.recursive.GetValue())

            self.selectedPaths = paths
            nrFiles = len([file for file in paths if os.path.isfile(file)])
            self.foundFilesText.SetLabel('Selected %d files' % nrFiles)

            if nrFiles == 1:
                self.webSeed.Enable(True)
                self.webSeed.SetValue('')
            else:
                self.webSeed.SetValue('Webseed will only work for a single file.')
                self.webSeed.Enable(False)

            self.combineRadio.Enable(nrFiles > 0)
            self.sepRadio.Enable(nrFiles > 1)

            self.combineRadio.SetValue(nrFiles == 1)
            self.sepRadio.SetValue(nrFiles > 1)

            self.OnCombine()

            self.Layout()

    @forceWxThread
    def _torrentCreated(self, path, correctedfilename, torrentfilename):
        self.progressDlg.cur += 1
        keepGoing, _ = self.progressDlg.Update(self.progressDlg.cur)
        if not keepGoing:
            self.cancelEvent.Set()

        self.createdTorrents.append((path, correctedfilename, torrentfilename))


def make_meta_file(srcpaths, params, userabortflag, progressCallback, torrentfilenameCallback):
    tdef = TorrentDef()

    basedir = None

    nrFiles = len([file for file in srcpaths if os.path.isfile(file)])
    if nrFiles > 1:
        # outpaths should start with a common prefix, this prefix is the swarmname of the torrent
        # if srcpaths contain c:\a\1, c:\a\2 -> basepath should be c:\ and basedir a and outpaths should be a\1 and a\2
        # if srcpaths contain c:\a\1, c:\a\2, c:\a\b\1, c:\a\b\2 -> basepath should be c:\ and outpaths should be a\1, a\2, a\b\1 and a\b\2
        basepath = os.path.abspath(os.path.commonprefix(srcpaths))
        basepath, basedir = os.path.split(basepath)
        for srcpath in srcpaths:
            if os.path.isfile(srcpath):
                outpath = os.path.relpath(srcpath, basepath)

                # h4x0r playtime
                if 'playtime' in params:
                    tdef.add_content(srcpath, outpath, playtime=params['playtime'])
                else:
                    tdef.add_content(srcpath, outpath)
    else:
        srcpaths = [file for file in srcpaths if os.path.isfile(file)]

        srcpath = srcpaths[0]
        basepath, _ = os.path.split(srcpath)
        if 'playtime' in params:
            tdef.add_content(srcpath, playtime=params['playtime'])
        else:
            tdef.add_content(srcpath)

        if params.get('urllist', False):
            tdef.set_urllist(params['urllist'])

    if params['name']:
        tdef.set_name(params['name'])
    if params['comment']:
        tdef.set_comment(params['comment'])
    if params['created by']:
        tdef.set_created_by(params['created by'])
    if params['announce']:
        tdef.set_tracker(params['announce'])
    if params['announce-list']:
        tdef.set_tracker_hierarchy(params['announce-list'])
    if params['nodes']:  # mainline DHT
        tdef.set_dht_nodesmax(params['nodes'])
    if params['httpseeds']:
        tdef.set_httpseeds(params['httpseeds'])
    if params['encoding']:
        tdef.set_encoding(params['encoding'])
    if params['piece length']:
        tdef.set_piece_length(params['piece length'])
    if params['makehash_md5']:
        print >> sys.stderr, "TorrentMaker: make MD5"
        tdef.set_add_md5hash(params['makehash_md5'])
    if params['makehash_crc32']:
        print >> sys.stderr, "TorrentMaker: make CRC32"
        tdef.set_add_crc32(params['makehash_crc32'])
    if params['makehash_sha1']:
        print >> sys.stderr, "TorrentMaker: make SHA1"
        tdef.set_add_sha1hash(params['makehash_sha1'])
    if params['createmerkletorrent']:
        tdef.set_create_merkle_torrent(params['createmerkletorrent'])
    if params['torrentsigkeypairfilename']:
        tdef.set_signature_keypair_filename(params['torrentsigkeypairfilename'])
    if params['thumb']:
        tdef.set_thumbnail(params['thumb'])

    tdef.finalize(userabortflag=userabortflag, userprogresscallback=progressCallback)

    if params['createmerkletorrent']:
        postfix = TRIBLER_TORRENT_EXT
    else:
        postfix = '.torrent'

    if params.get('target', False):
        torrentfilename = os.path.join(params['target'], os.path.split(os.path.normpath(srcpath))[1] + postfix)
    else:
        torrentfilename = os.path.join(basepath, tdef.get_name() + postfix)
    tdef.save(torrentfilename)

    # Inform higher layer we created torrent
    torrentfilenameCallback(basepath, basedir, torrentfilename)
