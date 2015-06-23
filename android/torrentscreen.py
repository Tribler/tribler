from kivy.uix.boxlayout import BoxLayout
from kivy.logger import Logger
from kivy.uix.screenmanager import Screen
import globalvars

from kivyvideoplayer.videoplayer import VideoPlayer

from jnius import autoclass
Intent = autoclass('android.content.Intent')
Uri = autoclass('android.net.Uri')
PythonActivity = autoclass('org.renpy.android.PythonActivity')

"""
A widget for torrents that takes users to the torrent info screen when pressed.
"""
class TorrentWidget(BoxLayout):
    torrent = None
    name = "Unknown"

    def set_torrent(self, torrent):
        self.torrent = torrent
        self.ids.filebutton.text = self.name = self.torrent.name

    def on_press(self):
        main = globalvars.skelly
        main.TorrentInfoScr.torrent = self.torrent
        main.swap_to(main.TorrentInfoScr)

"""
The screen shown when a torrent is pressed. Here the user can select to download or stream a torrent.
"""
class TorrentInfoScreen(Screen):
    torrent = None
    download_in_vod_mode = False
    started_player = False

    def start_download(self):
        """
        Starts a download from a torrent file.
        :return: Nothing.
        """
        Logger.info('Start download in TorrentInfoScreen.')
        download_mgr = globalvars.skelly.tw.get_download_mgr()
        download_mgr.add_torrent(self.torrent.infohash, self.torrent.name)
        # TODO: navigate user to screen with previously downloaded torrents and show this torrent with a progress bar

    def start_stream(self):
        """
        Starts downloading from a torrent file and starts a video player
        when enough of the video has been downloaded.
        :return: Nothing.
        """
        Logger.info('Starting download for stream in TorrentInfoScreen.')
        download_mgr = globalvars.skelly.tw.get_download_mgr()
        download_mgr.subscribe_for_changed_progress_info(self._check_streamable_callback)
        self.start_download()
        # TODO: Show progress to user, which is available in progress_dict variable in _check_streamable_callback

    def _check_streamable_callback(self, info_hash):
        """
        Called when download progress changes. Will start VOD download mode when
        possible and after that start a video player when enough has been downloaded.
        :param info_hash: The info hash of the torrent with new download progress.
        :return: Nothing.
        """
        if self.started_player or info_hash != self.torrent.infohash:
            return
        download_mgr = globalvars.skelly.tw.get_download_mgr()
        progress_dict = download_mgr.get_progress(self.torrent.infohash)

        # Start video player:
        if progress_dict['vod_playable']:
            Logger.info('Starting video player.')
            self._start_internal_kivy_player() # self._start_external_android_player()
        else:

            # When metadata etc. has been downloaded then start downloading the actual video content in vod mode:
            status_code = progress_dict['status']
            if 3 <= status_code <= 5 and not self.download_in_vod_mode:
                Logger.info('Starting VOD mode.')
                self.vod_uri = download_mgr.start_vod(self.torrent.infohash)
                self.download_in_vod_mode = True

    def _start_internal_kivy_player(self):
        """
        Starts the internal Kivy video player with the VOD uri from Tribler's video server.
        :return: Nothing.
        """
        self.started_player = True
        session_mgr = globalvars.skelly.tw.get_session_mgr()
        video_player = VideoPlayer()
        video_player.download = session_mgr.get_session().get_download(self.torrent.infohash)
        video_player.source = self.vod_uri # TODO: test this
        video_player.state = 'play'

    def _start_external_android_player(self):
        """
        Start the action chooser intent for viewing a video using the VOD uri from Tribler's video server.
        :return: Nothing.
        """
        self.started_player = True
        intent = Intent(Intent.ACTION_VIEW)
        intent.setDataAndType(Uri.parse(self.vod_uri), "video/*")
        PythonActivity.mActivity.startActivity(Intent.createChooser(intent, "Complete action using"))

