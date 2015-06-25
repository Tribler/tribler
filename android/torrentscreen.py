from kivy.uix.boxlayout import BoxLayout
from kivy.logger import Logger
from kivy.uix.screenmanager import Screen
from videoplayer import open_player
from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.TorrentDef import TorrentDefNoMetainfo
import os


from math import ceil
import globalvars

"""
A widget for torrents that takes users to the torrent info screen when pressed.
"""
class TorrentWidget(BoxLayout):
    torrent = None
    name = "Unknown"

    def set_torrent(self, torrent):
        self.torrent = torrent
        self.name = self.torrent.name
        #seeders_text = 'Seeders: ' + (str(torrent.num_seeders) if torrent.num_seeders and torrent.num_seeders != -1 else "Unknown")
        #file_size_text = 'File size: ' + (file_size_to_string(torrent.length) if torrent.length else "Unknown") #TODO
        self.ids.filebutton.text = self.torrent.name #+ '\n' + seeders_text + '\n' + file_size_text

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
    download_started = False

    def open_screen(self, torrent):
        """
        To be called when this screen is opened for a torrent.
        :param torrent: The torrent this screen is opened for.
        :return: Nothing.
        """
        self._reset()
        self.torrent = torrent
        self.ids.name_label.text = self.torrent.name
        self.ids.type_label.text = 'Type: ' + str(torrent.category)
        self.ids.file_size_label.text = 'File size: ' + (file_size_to_string(torrent.length) if torrent.length else "Unknown") #TODO
        self.ids.seeders_label.text = 'Seeders: ' + (str(torrent.num_seeders) if torrent.num_seeders and torrent.num_seeders != -1 else "Unknown")
        self.ids.leechers_label.text = 'Leechers: ' + (str(torrent.num_leechers) if torrent.num_leechers and torrent.num_leechers != -1 else "Unknown")

    def start_download(self, navigate_to_home=True):
        """
        Starts a download from a torrent file.
        :return: Nothing.
        """
        Logger.info('Start download in TorrentInfoScreen.')

        if self.download_started:
            return
        self.download_started = True

        # Old code in case we did not want to use DownloadManager (as below):
        #session = globalvars.skelly.tw.get_session_mgr().get_session()
        #dscfg = DownloadStartupConfig()
        #dscfg.set_dest_dir(globalvars.videoFolder.getAbsolutePath())
        #tdef = TorrentDefNoMetainfo(self.torrent.infohash, self.torrent.name)
        #session.start_download(tdef, dscfg)

        download_mgr = globalvars.skelly.tw.get_download_mgr()
        download_destination_dir = globalvars.videoFolder.getAbsolutePath()
        download_mgr.add_torrent(self.torrent.infohash, self.torrent.name, download_destination_dir)

        if navigate_to_home:
            self.navigate_to_home()

    def navigate_to_home(self):
        # TODO: navigate user to (home?) screen with previously downloaded torrents and show this torrent with a progress bar
        pass

    def start_stream(self):
        """
        Starts downloading from a torrent file and starts a video player
        when enough of the video has been downloaded.
        :return: Nothing.
        """
        Logger.info('Starting download for stream in TorrentInfoScreen.')

        download_mgr = globalvars.skelly.tw.get_download_mgr()
        download_mgr.subscribe_for_changed_progress_info(self._check_streamable_callback)

        self.start_download(False)

        # Old code in case we did not want to use DownloadManager (as above):
        #session = globalvars.skelly.tw.get_session_mgr().get_session()
        #download = session.get_download(self.torrent.infohash)
        #download.set_state_callback(self._check_streamable_callback, delay=1)

        self.navigate_to_home()

    def _check_streamable_callback(self, info_hash, *largs):
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
        if progress_dict['vod_playable'] and self.download_in_vod_mode: # TODO: self.download_in_vod_mode might not be needed but for now it sets the vod_uri
            Logger.info('Starting video player.')
            self.started_player = True
            open_player(self.vod_uri)
        else:

            self.send_vod_message(progress_dict)

            # When metadata etc. has been downloaded then start downloading the actual video content in vod mode:
            status_code = progress_dict['status']
            if 3 <= status_code <= 5 and not self.download_in_vod_mode:
                Logger.info('Starting VOD mode.')
                self.vod_uri = download_mgr.start_vod(self.torrent.infohash)
                self.download_in_vod_mode = True

    def send_vod_message(self, progress_dict):
        vod_eta = progress_dict['vod_eta']
        progress = progress_dict['progress']
        download_speed = progress_dict['speed_down']
        message = 'Video starts playing in ' + seconds_to_string(vod_eta) + ' (' + bytes_per_sec_to_string(download_speed) + ').'
        progress = str(ceil(progress * 100))
        # TODO: show message and progress to user properly
        play = self.ids.play_button
        play.text = 'Progress: ' + progress + '.\n' + message
        play.on_release = self.do_nothing_on_button_release
        play.background_color = [0.5, 0.5, 0.5, 0.5]
        Logger.info('Video preparing for streaming info: ' + message + ' Progress: ' + progress)

    def _reset(self):
        """
        Resets the screen. To be used when a new torrent info screen is opened.
        :return: Nothing.
        """
        self.torrent = None
        self.download_in_vod_mode = False
        self.started_player = False
        self.download_started = False
        self.vod_uri = None

    def do_nothing_on_button_release(self):
        pass


def file_size_to_string(bytes, suffix='B'):
    for unit in ['', 'k', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(bytes) < 1024.0:
            return "%3.1f %s%s" % (bytes, unit, suffix)
        bytes /= 1024.0
    return "%.1f %s%s" % (bytes, 'Y', suffix)

def seconds_to_string(seconds):
    if seconds < 10:
        return "a few seconds"
    elif seconds < 60:
        return "about " + str((round(seconds / 10) * 10)) + " seconds"
    elif seconds < 3600:
        value = str(round(seconds / 10))
        return "about " + value + " minute" + ("s" if value > 1 else "")
    elif seconds < 24 * 3600:
        value = str(round(seconds / 3600))
        return "about " + value + " hour" + ("s" if value > 1 else "")
    else:
        return "more than a day"

def bytes_per_sec_to_string(speed_in_bytes):
    return file_size_to_string(speed_in_bytes) + '/s'
