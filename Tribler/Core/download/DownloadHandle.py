import ctypes
import logging
import os

import sys

import libtorrent

from Tribler.Core.download.definitions import DownloadStatus

logger = logging.getLogger(__name__)


class DownloadHandle:
    """
    Holds a libtorrent download handle and interacts with it.
    """
    def __init__(self, handle):
        if isinstance(handle, DownloadHandle):
            raise Exception("x")

        self.libtorrent_handle = handle

    def add_trackers(self, trackers):
        for tracker in trackers:
            self.libtorrent_handle.add_tracker({'url': tracker, 'verified': False})

    def force_recheck(self):
        self.libtorrent_handle.resume()
        self.libtorrent_handle.force_recheck()

    def get_current_download_speed_bytes(self):
        status = self.libtorrent_handle.status()
        return status.status.download_payload_rate

    def get_magnet_link(self):
        return libtorrent.make_magnet_uri(self.libtorrent_handle)

    def is_valid(self):
        return self.libtorrent_handle.is_valid()

    def get_download_state(self):
        status = self.libtorrent_handle.status()

        download_state = DownloadStatus(status.state) if not status.paused else DownloadStatus.STOPPED
        if status.error and download_state is DownloadStatus.STOPPED:
            download_state = DownloadStatus.STOPPED_ON_ERROR

        return download_state

    def get_file_priority(self, index):
        return self.libtorrent_handle.file_priority(index)

    def get_info(self):
        # In libtorrent 0.16.18, the torrent_handle.torrent_file method is not available.
        # this method checks whether the torrent_file method is available on a given handle.
        # If not, fall back on the deprecated get_torrent_info
        try:
            if hasattr(self.libtorrent_handle, 'torrent_file'):
                return self.libtorrent_handle.torrent_file()
            return self.libtorrent_handle.get_torrent_info()
        except RuntimeError as e:  # This can happen when the torrent handle is invalid.
            logger.warning("Got exception when fetching info from handle: %s", str(e))
            return None

    def get_network_statistics(self):
        status = self.libtorrent_handle.status()
        return {
            'total_seeds': status.num_complete if status.num_complete >= 0 else status.list_seeds,
            'total_peers': status.num_incomplete if status.num_incomplete >= 0 else status.list_peers,
            # when anon downloading, this might become negative
            'leechers': max(status.num_peers - status.num_seeds, 0),
            'seeders': status.num_seeds,
            'pieces': status.pieces,
            'total_up': status.all_time_upload,
            'total_down': status.all_time_download,
        }

    def get_peer_info(self):
        return self.libtorrent_handle.get_peer_info()

    def get_statistics(self, get_peer_list):
        download_state = self.get_download_state()
        status = self.libtorrent_handle.status()
        return {
            'down': float(status.download_payload_rate) if download_state not in [DownloadStatus.STOPPED,
                                                                                  DownloadStatus.STOPPED_ON_ERROR] else 0.0,
            'up': float(status.upload_payload_rate) if download_state not in [DownloadStatus.STOPPED,
                                                                               DownloadStatus.STOPPED_ON_ERROR] else 0.0,
            'wanted': float(status.total_wanted),
            'stats': self.get_network_statistics(),
            'spew': self.create_peer_list() if get_peer_list else None,
        }

    def create_peer_list(self):
        peers = list()
        for peer_info in self.get_peer_info():
            # Only consider fully connected peers.
            # Disabling for now, to avoid presenting the user with conflicting information
            # (partially connected peers are included in seeder/leecher stats).
            # if peer_info.flags & peer_info.connecting or peer_info.flags & peer_info.handshake:
            #     continue
            peer_dict = DownloadHandle.create_peer_list_data(peer_info)
            peers.append(peer_dict)

        return peers

    @staticmethod
    def create_peer_list_data(peer_info):
        """
        A function to convert peer_info libtorrent object into dictionary
        This data is used to identify peers with combination of several flags
        """
        return {'id': peer_info.pid.to_bytes().encode('hex'),
                'extended_version': peer_info.client,
                'ip': peer_info.ip[0],
                'port': peer_info.ip[1],
                # optimistic_unchoke = 0x800 seems unavailable in python bindings
                'optimistic': bool(peer_info.flags & 0x800),
                'direction': 'L' if bool(peer_info.flags & peer_info.local_connection) else 'R',
                'uprate': peer_info.payload_up_speed,
                'uinterested': bool(peer_info.flags & peer_info.remote_interested),
                'uchoked': bool(peer_info.flags & peer_info.remote_choked),
                'uhasqueries': peer_info.upload_queue_length > 0,
                'uflushed': peer_info.used_send_buffer > 0,
                'downrate': peer_info.payload_down_speed,
                'dinterested': bool(peer_info.flags & peer_info.interesting),
                'dchoked': bool(peer_info.flags & peer_info.choked),
                'snubbed': bool(peer_info.flags & 0x1000),
                'utotal': peer_info.total_upload,
                'dtotal': peer_info.total_download,
                'completed': peer_info.progress,
                'have': peer_info.pieces, 'speed': peer_info.remote_dl_rate,
                'country': peer_info.country,
                'connection_type': peer_info.connection_type,
                # add upload_only and/or seed
                'seed': bool(peer_info.flags & peer_info.seed),
                'upload_only': bool(peer_info.flags & peer_info.upload_only),
                # add read and write state (check unchoke/choke peers)
                # read and write state is char with value 0, 1, 2, 4. May be empty
                'rstate': peer_info.read_state,
                'wstate': peer_info.write_state}

    def get_seeding_statistics(self):
        status = self.libtorrent_handle.status()
        return {
            'total_up': status.all_time_upload,
            'total_down': status.all_time_download,
            'ratio': status.all_time_upload / float(status.all_time_download),
            'time_seeding': status.finished_time,
        }

    def get_trackers(self):
        self.libtorrent_handle.trackers()

    def info_hash(self):
        """
        Info hash of the torrent pointed to by this handle.
        :return: hash in bytes
        """
        self.libtorrent_handle.info_hash()

    def move_storage(self, new_directory):
        self.libtorrent_handle.move_storage(new_directory)
        return True

    def pause(self):
        self.libtorrent_handle.pause()

    def prioritize_files(self, priorities):
        self.libtorrent_handle.prioritize_files(priorities)

    def get_length(self):
        return float(self.libtorrent_handle.status().total_wanted)

    def get_byte_progress(self, byte_ranges, consecutive=False):
        pieces = []
        for file_index, bytes_begin, bytes_end in byte_ranges:
            if file_index >= 0:
                # Ensure the we remain within the file's boundaries
                file_entry = self.get_info().file_at(file_index)
                bytes_begin = min(
                    file_entry.size, bytes_begin) if bytes_begin >= 0 else file_entry.size + (bytes_begin + 1)
                bytes_end = min(file_entry.size, bytes_end) if bytes_end >= 0 else file_entry.size + (bytes_end + 1)

                start_piece = self.get_info().map_file(file_index, bytes_begin, 0).piece
                end_piece = self.get_info().map_file(file_index, bytes_end, 0).piece + 1
                start_piece = max(start_piece, 0)
                end_piece = min(end_piece, self.get_info().num_pieces())

                pieces += range(start_piece, end_piece)
            else:
                logger.info("DownloadHandle: could not get progress for incorrect file index")

        pieces = list(set(pieces))
        return self.get_piece_progress(pieces, consecutive)

    def get_piece_progress(self, pieces, consecutive=False):
        if not pieces:
            return 1.0
        elif consecutive:
            pieces.sort()

        pieces_have = 0
        pieces_all = len(pieces)
        bitfield = self.libtorrent_handle.status().pieces
        for pieceindex in pieces:
            if pieceindex < len(bitfield) and bitfield[pieceindex]:
                pieces_have += 1
            elif consecutive:
                break
        return float(pieces_have) / pieces_all

    def get_save_path(self):
        # torrent_handle.save_path() is deprecated in newer versions of Libtorrent. We should use
        # self.handle.status().save_path to query the save path of a torrent. However, this attribute
        # is only included in libtorrent 1.0.9+
        status = self.libtorrent_handle.get_status()
        if hasattr(status, 'save_path'):
            return status.save_path
        return self.libtorrent_handle.save_path()

    def get_status(self):
        return self.libtorrent_handle.status()

    def resolve_countries(self, resolve):
        self.libtorrent_handle.resolve_countries(resolve)

    def set_max_connections(self, connections):
        self.libtorrent_handle.set_max_connections(connections)

    def set_priority(self, priority):
        self.libtorrent_handle.set_priority(priority)

    def set_sequential_download(self, sequential_download):
        self.libtorrent_handle.set_sequential_download(sequential_download)

    def set_share_mode(self, mode):
        self.libtorrent_handle.set_share_mode(mode)

    def update_path(self, index, save_path, unwanted_directory, new_path):
        absolute_unwanted_directory = os.path.join(save_path.decode('utf-8'), unwanted_directory)
        if not os.path.exists(absolute_unwanted_directory) and unwanted_directory in new_path:
            os.makedirs(absolute_unwanted_directory)
            if sys.platform == "win32":
                ctypes.windll.kernel32.SetFileAttributesW(
                    absolute_unwanted_directory, 2)  # 2 = FILE_ATTRIBUTE_HIDDEN

        # Path should be unicode if Libtorrent is using std::wstring (on Windows),
        # else we use str (on Linux).
        try:
            self.libtorrent_handle.rename_file(index, new_path)
        except TypeError:
            self.libtorrent_handle.rename_file(index, new_path.encode("utf-8"))
