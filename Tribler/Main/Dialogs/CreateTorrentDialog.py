# Written by Niels Zeilemaker
# see LICENSE.txt for license information

import os
from threading import Event
from traceback import print_exc

import wx

from Tribler.Core.Utilities.torrent_utils import create_torrent_file
from Tribler.Core.version import version_id
from Tribler.Main.vwxGUI import forceWxThread
from Tribler.Main.vwxGUI.GuiUtility import GUIUtility
from Tribler.Main.vwxGUI.widgets import BetterText as StaticText, _set_font


class CreateTorrentDialog(wx.Dialog):

    def __init__(self, parent, recent_creation_config_file, recent_trackers_config_file,
                 suggested_trackers, to_channel=False):
        wx.Dialog.__init__(self, parent, -1, 'Create a .torrent', size=(600, 200), name="CreateTorrentDialog")

        self.to_channel = to_channel

        # setup layout
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
        self.config = wx.FileConfig(appName="Tribler", localFilename=recent_creation_config_file)
        self.trackerHistory.Load(self.config)

        if self.trackerHistory.GetCount() > 0:
            trackers = [self.trackerHistory.GetHistoryFile(i) for i in range(self.trackerHistory.GetCount())]
            if len(trackers) < len(suggested_trackers):
                trackers.extend(suggested_trackers[:len(suggested_trackers) - len(trackers)])
        else:
            trackers = suggested_trackers

        for tracker in trackers:
            self.trackerList.AppendText(tracker + os.linesep)

        vSizer.Add(self.trackerList, 0, wx.EXPAND | wx.BOTTOM, 3)

        vSizer.Add(StaticText(self, -1, 'Comment'))
        self.commentList = wx.TextCtrl(self, -1, '', style=wx.TE_MULTILINE)
        vSizer.Add(self.commentList, 0, wx.EXPAND, 3)

        vSizer.Add(wx.StaticLine(self, -1), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        header = wx.StaticText(self, -1, 'Advanced options')
        _set_font(header, fontweight=wx.FONTWEIGHT_BOLD)
        vSizer.Add(header, 0, wx.EXPAND | wx.BOTTOM | wx.TOP, 3)

        abbrev_mb = " MB"
        abbrev_kb = " KB"
        piece_choices = ['Automatic',
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
        self.fileconfig = wx.FileConfig(appName="Tribler", localFilename=recent_trackers_config_file)
        self.filehistory.Load(self.fileconfig)

        if self.filehistory.GetCount() > 0:
            self.latestFile = self.filehistory.GetHistoryFile(0)
        else:
            self.latestFile = ''
        self.paths = None

    def OnBrowse(self, event):
        dlg = wx.FileDialog(None, "Please select the file(s).",
                            style=wx.FD_OPEN | wx.FD_MULTIPLE, defaultDir=self.latestFile)
        if dlg.ShowModal() == wx.ID_OK:
            filenames = dlg.GetPaths()
            dlg.Destroy()

            self._browsePaths(filenames)
        else:
            dlg.Destroy()

    def OnBrowseDir(self, event):
        dlg = wx.DirDialog(None, "Please a directory.", style=wx.DD_DIR_MUST_EXIST, defaultPath=self.latestFile)
        if dlg.ShowModal() == wx.ID_OK:
            filenames = [dlg.GetPath()]
            dlg.Destroy()

            self._browsePaths(filenames)
        else:
            dlg.Destroy()

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
        max = 1 if self.combineRadio.GetValue() else len(self.selectedPaths)
        if self.to_channel:
            dlg = wx.MessageDialog(self, "This will add %d new .torrents to this Channel.\nDo you want to continue?" %
                                   max, "Are you sure?", style=wx.YES_NO | wx.ICON_QUESTION)
        else:
            dlg = wx.MessageDialog(self, "This will create %d new .torrents.\nDo you want to continue?" %
                                   max, "Are you sure?", style=wx.YES_NO | wx.ICON_QUESTION)

        if dlg.ShowModal() == wx.ID_YES:
            dlg.Destroy()

            params = {}
            params['comment'] = self.commentList.GetValue()
            params['created by'] = '%s version: %s' % ('Tribler', version_id)

            trackers = self.trackerList.GetValue()
            trackers = [tracker for tracker in trackers.split(os.linesep) if tracker]

            for tracker in trackers:
                self.trackerHistory.AddFileToHistory(tracker)
            self.trackerHistory.Save(self.config)
            self.config.Flush()

            self.filehistory.Save(self.fileconfig)
            self.fileconfig.Flush()

            if trackers:
                params['announce'] = trackers[0]
                params['announce-list'] = trackers

            if self.webSeed.GetValue():
                params['urllist'] = [self.webSeed.GetValue()]

            params['nodes'] = False
            params['httpseeds'] = False
            params['encoding'] = False

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
                        create_torrent_file(self.selectedPaths, params, self._torrentCreated)
                    else:
                        for path in self.selectedPaths:
                            if os.path.isfile(path):
                                create_torrent_file([path], params, self._torrentCreated)
                except:
                    print_exc()

                wx.CallAfter(do_gui)

            def start():
                if self.combineRadio.GetValue():
                    self.progressDlg = wx.ProgressDialog(
                        "Creating new .torrents", "Please wait while Tribler is creating your .torrents.\n"
                        "This could take a while due to creating the required hashes.",
                        maximum=max, parent=self,
                        style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE)
                else:
                    self.progressDlg = wx.ProgressDialog(
                        "Creating new .torrents", "Please wait while Tribler is creating your .torrents.\n"
                        "This could take a while due to creating the required hashes.",
                        maximum=max, parent=self,
                        style=wx.PD_CAN_ABORT | wx.PD_APP_MODAL | wx.PD_ELAPSED_TIME | wx.PD_AUTO_HIDE)
                self.progressDlg.Pulse()
                self.progressDlg.cur = 0

                GUIUtility.getInstance().utility.session.lm.rawserver.call_in_thread(0, create_torrents)

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
                    dlg2 = wx.MessageDialog(self, "The selected piecesize will cause a torrent to have %d pieces.\n"
                                            "This is more than the recommended max 2500 pieces.\nDo you want to continue?" %
                                            nrPieces, "Are you sure?", style=wx.YES_NO | wx.ICON_QUESTION)
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
    def _torrentCreated(self, result):
        if not result['success']:
            self.cancelEvent.set()

        path = result['base_path']
        correctedfilename = result['base_dir']
        torrentfilename = result['torrent_file_path']

        self.progressDlg.cur += 1
        keepGoing, _ = self.progressDlg.Update(self.progressDlg.cur)
        if not keepGoing:
            self.cancelEvent.set()

        self.createdTorrents.append((path, correctedfilename, torrentfilename))
