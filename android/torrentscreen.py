from kivy.uix.boxlayout import BoxLayout
from kivy.logger import Logger
from kivy.uix.screenmanager import Screen
from videoplayer import start_internal_kivy_player
import globalvars

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
        """
        Called when this torrent widget is pressed. Opens the torrent info screen.
        """
        main = globalvars.skelly
        main.TorrentInfoScr.open_screen(self.torrent)
        main.swap_to(main.TorrentInfoScr)

"""
The screen shown when a torrent is pressed. Here the user can select to download or stream a torrent.
"""
class TorrentInfoScreen(Screen):
    torrent = None
    download_in_vod_mode = False
    started_player = False
    vod_uri = None

    type_label_text = 'Type'
    filesize_label_text = 'Filesize'
    seeders_label_text = 'Seeders'
    leechers_label_text = 'Leechers'

    def open_screen(self, torrent):
        """
        To be called when this screen is opened for a torrent.
        :param torrent: The torrent this screen is opened for.
        :return: Nothing.
        """
        self._reset()
        self.torrent = torrent
        self.type_label_text = 'Type: ' + str(torrent.category)
        self.filesize_label_text = 'Filesize: ' + str(torrent.length) if torrent.length else "Unknown" #TODO
        self.seeders_label_text = 'Seeders: ' + str(torrent.num_seeders) if torrent.num_seeders and torrent.num_seeders != -1 else "Unknown"
        self.leechers_label_text = 'Leechers: ' + str(torrent.num_leechers) if torrent.num_leechers and torrent.num_leechers != -1 else "Unknown"

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
            self.started_player = True
            session_mgr = globalvars.skelly.tw.get_session_mgr()
            start_internal_kivy_player(session_mgr.get_session().get_download(self.torrent.infohash), self.vod_uri) # start_external_android_player(self.vod_uri)
        else:

            # When metadata etc. has been downloaded then start downloading the actual video content in vod mode:
            status_code = progress_dict['status']
            if 3 <= status_code <= 5 and not self.download_in_vod_mode:
                Logger.info('Starting VOD mode.')
                self.vod_uri = download_mgr.start_vod(self.torrent.infohash)
                self.download_in_vod_mode = True

    def _reset(self):
        """
        Resets the screen. To be used when a new torrent info screen is opened.
        :return: Nothing.
        """
        self.torrent = None
        self.download_in_vod_mode = False
        self.started_player = False
        self.vod_uri = None

