"""
Contains a snapshot of the state of the Download at a specific point in time.

Author(s): Arno Bakker
"""
from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    import libtorrent

    from tribler.core.libtorrent.download_manager.download import Download, PeerDict, PeerDictHave


class DownloadStatus(Enum):
    """
    The libtorrent status for a download.
    """

    ALLOCATING_DISKSPACE = 0
    WAITING_FOR_HASHCHECK = 1
    HASHCHECKING = 2
    DOWNLOADING = 3
    SEEDING = 4
    STOPPED = 5
    STOPPED_ON_ERROR = 6
    METADATA = 7
    CIRCUITS = 8
    EXIT_NODES = 9


# Map used to convert libtorrent -> Tribler download status
DOWNLOAD_STATUS_MAP = [
    DownloadStatus.WAITING_FOR_HASHCHECK,
    DownloadStatus.HASHCHECKING,
    DownloadStatus.METADATA,
    DownloadStatus.DOWNLOADING,
    DownloadStatus.SEEDING,
    DownloadStatus.SEEDING,
    DownloadStatus.ALLOCATING_DISKSPACE,
    DownloadStatus.HASHCHECKING,
]

UPLOAD = 'up'
DOWNLOAD = 'down'


class DownloadState:
    """
    Contains a snapshot of the state of the Download at a specific
    point in time. Using a snapshot instead of providing live data and
    protecting access via locking should be faster.

    cf. libtorrent torrent_status
    """

    def __init__(self, download: Download, lt_status: libtorrent.torrent_status, error: str | None) -> None:
        """
        Internal constructor.

        :param download: The download this state belongs too.
        :param lt_status: The libtorrent status object.
        """
        self._logger = logging.getLogger(self.__class__.__name__)

        self.download = download
        self.lt_status = lt_status
        self.error = error

    def __str__(self) -> str:
        """
        Create a pretty printed string.
        """
        return f"DownloadState(infohash={self.download.tdef.infohash}, lt_status={self.lt_status}, error={self.error})"

    def get_download(self) -> Download:
        """
        Returns the Download object of which this is the state.
        """
        return self.download

    def get_progress(self) -> float:
        """
        The general progress of the Download as a percentage. When status is
         * HASHCHECKING it is the percentage of already downloaded
           content checked for integrity.
         * DOWNLOADING/SEEDING it is the percentage downloaded.

        :return: Progress as a float (0..1).
        """
        return self.lt_status.progress if self.lt_status else 0

    def get_status(self) -> DownloadStatus:
        """
        Returns the status of the torrent.
        """
        if self.lt_status:
            if self.lt_status.paused:
                return DownloadStatus.STOPPED
            return DOWNLOAD_STATUS_MAP[self.lt_status.state]
        if self.get_error():
            return DownloadStatus.STOPPED_ON_ERROR
        return DownloadStatus.STOPPED

    def get_error(self) -> str | None:
        """
        Returns the Exception that caused the download to be moved to STOPPED_ON_ERROR status.

        :return: An error message
        """
        return self.error or (self.lt_status.error if self.lt_status and self.lt_status.error else None)

    def get_current_speed(self, direct: str) -> int:
        """
        Returns the current up or download speed.

        :return: The speed in bytes/s.
        """
        if not self.lt_status or self.get_status() not in [DownloadStatus.DOWNLOADING, DownloadStatus.SEEDING]:
            return 0
        if direct == UPLOAD:
            return self.lt_status.upload_rate
        return self.lt_status.download_rate

    def get_current_payload_speed(self, direct: str) -> int:
        """
        Returns the current up or download payload speed.

        :return: The speed in bytes/s.
        """
        if not self.lt_status or self.get_status() not in [DownloadStatus.DOWNLOADING, DownloadStatus.SEEDING]:
            return 0
        if direct == UPLOAD:
            return self.lt_status.upload_payload_rate
        return self.lt_status.download_payload_rate

    @property
    def all_time_upload(self) -> int:
        """
        Returns accumulated upload byte counter. It is persisted in the resume data to keep totals across sessions.

        :return: The amount in bytes.
        """
        if not self.lt_status:
            return 0
        return self.lt_status.all_time_upload

    @property
    def all_time_download(self) -> int:
        """
        Returns accumulated download byte counter. It is persisted in the resume data to keep totals across sessions.

        :return: The amount in bytes.
        """
        if not self.lt_status:
            return 0
        return self.lt_status.all_time_download

    @property
    def total_upload(self) -> int:
        """
        Returns the number of bytes uploaded to all peers, accumulated, this session only.

        :return: The amount in bytes.
        """
        if not self.lt_status:
            return 0
        return self.lt_status.total_upload

    @property
    def total_download(self) -> int:
        """
        Returns the number of bytes downloaded from all peers, accumulated, this session only.

        :return: The amount in bytes.
        """
        if not self.lt_status:
            return 0
        return self.lt_status.total_download

    @property
    def total_payload_upload(self) -> int:
        """
        Returns the amount of bytes sent this session, but only the actual payload data.

        :return: The amount in bytes.
        """
        if not self.lt_status:
            return 0
        return self.lt_status.total_payload_upload

    @property
    def total_payload_download(self) -> int:
        """
        Returns the amount of bytes received this session, but only the actual payload data.

        :return: The amount in bytes.
        """
        if not self.lt_status:
            return 0
        return self.lt_status.total_payload_download

    def get_all_time_ratio(self) -> float:
        """
        Returns the accumulated seeding ratio of the download across multiple sessions.
        """
        if not self.lt_status:
            return 0

        bytes_completed = self.get_progress() * self.download.tdef.get_length()
        if not bytes_completed:
            # We're returning -1 instead of infinity, as it avoids issues when JSON encoding.
            return 0 if not self.all_time_upload else -1

        return self.all_time_upload / bytes_completed

    def get_seeding_time(self) -> int:
        """
        The active time (not paused), while finished and while being a seed, in seconds.
        """
        return self.lt_status.finished_time if self.lt_status else 0

    def get_eta(self) -> float:
        """
        Returns the estimated time to finish of download.

        :return: The time in ?, as ?.
        """
        return (1.0 - self.get_progress()) * (float(self.download.get_def().get_length()) /
                                              max(0.000001, self.lt_status.download_rate)) \
            if self.lt_status else 0.0

    def get_num_seeds_peers(self) -> tuple[int, int]:
        """
        Returns the sum of the number of seeds and peers.

        :return: A tuple (num seeds, num peers)
        """
        if not self.lt_status or self.get_status() not in [DownloadStatus.DOWNLOADING, DownloadStatus.SEEDING]:
            return 0, 0

        total = self.lt_status.list_peers
        seeds = self.lt_status.list_seeds
        return seeds, total - seeds

    def get_pieces_complete(self) -> list[bool]:
        """
        Returns a list of booleans indicating whether we have completely
        received that piece of the content. The list of pieces for which
        we provide this info depends on which files were selected for download
        using DownloadConfig.set_selected_files().

        :return: A list of booleans.
        """
        return self.lt_status.pieces if self.lt_status else []

    def get_pieces_total_complete(self) -> tuple[int, int]:
        """
        Returns the number of total and completed pieces.

        :return: A tuple containing two integers, total and completed nr of pieces
        """
        return (len(self.lt_status.pieces), sum(self.lt_status.pieces)) if self.lt_status else (0, 0)

    def get_files_completion(self) -> list[tuple[Path, float]]:
        """
        Returns a list of filename, progress tuples indicating the progress
        for every file selected using set_selected_files. Progress is a float
        between 0 and 1.
        """
        completion = []

        if self.lt_status and self.download.handle and self.download.handle.is_valid():
            files = self.download.get_def().get_files_with_length()
            try:
                progress = self.download.handle.file_progress(flags=1)
            except RuntimeError:
                # For large torrents, the handle can be invalid at this point.
                # See https://github.com/Tribler/tribler/issues/6454
                progress = None
            if progress and len(progress) == len(files):
                for index, (path, size) in enumerate(files):
                    completion_frac = (float(progress[index]) / size) if size > 0 else 1
                    completion.append((path, completion_frac))

        return completion

    def get_selected_files(self) -> list[int] | None:
        """
        Get the selection status of the download's files, or None if it is not available.
        """
        selected_files = self.download.config.get_selected_files()
        return selected_files if len(selected_files) > 0 else None

    def get_availability(self) -> float:
        """
        Return the overall availability of all pieces, using connected peers.

        Availability is defined as the number of complete copies of a piece, thus seeders
        increment the availability by 1. Leechers provide a subset of piece thus we count the
        overall availability of all pieces provided by the connected peers and use the minimum
        of this + the average of all additional pieces.
        """
        if not self.lt_status:
            return 0  # We do not have any info for this download so we cannot accurately get its availability

        nr_seeders_complete = 0
        merged_bitfields = [0] * len(self.lt_status.pieces)

        peers = self.get_peer_list()
        for peer in peers:
            completed = peer.get('completed', 0)
            have = peer.get('have', [])

            if completed == 1 or (have and all(have)):
                nr_seeders_complete += 1
            elif have and len(have) == len(merged_bitfields):
                for i in range(len(have)):
                    if have[i]:
                        merged_bitfields[i] += 1

        if merged_bitfields:
            # count the number of complete copies due to overlapping leecher bitfields
            nr_leechers_complete = min(merged_bitfields)

            # detect remainder of bitfields which are > 0
            nr_more_than_min = len([x for x in merged_bitfields if x > nr_leechers_complete])
            fraction_additonal = float(nr_more_than_min) / len(merged_bitfields)

            return nr_seeders_complete + nr_leechers_complete + fraction_additonal
        return nr_seeders_complete

    def get_peer_list(self, include_have: bool = True) -> list[PeerDict | PeerDictHave]:
        """
        Returns a list of dictionaries, one for each connected peer, containing the statistics for that peer.
        """
        return self.download.get_peer_list(include_have)
