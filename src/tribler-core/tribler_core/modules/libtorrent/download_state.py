"""
Contains a snapshot of the state of the Download at a specific point in time.

Author(s): Arno Bakker
"""
import logging

from ipv8.messaging.anonymization.tunnel import PEER_FLAG_EXIT_BT

from tribler_common.simpledefs import (
    DLSTATUS_ALLOCATING_DISKSPACE,
    DLSTATUS_CIRCUITS,
    DLSTATUS_DOWNLOADING,
    DLSTATUS_EXIT_NODES,
    DLSTATUS_HASHCHECKING,
    DLSTATUS_METADATA,
    DLSTATUS_SEEDING,
    DLSTATUS_STOPPED,
    DLSTATUS_STOPPED_ON_ERROR,
    DLSTATUS_WAITING4HASHCHECK,
    UPLOAD,
)

# Map used to convert libtorrent -> Tribler download status
DLSTATUS_MAP = [DLSTATUS_WAITING4HASHCHECK,
                DLSTATUS_HASHCHECKING,
                DLSTATUS_METADATA,
                DLSTATUS_DOWNLOADING,
                DLSTATUS_SEEDING,
                DLSTATUS_SEEDING,
                DLSTATUS_ALLOCATING_DISKSPACE,
                DLSTATUS_HASHCHECKING]


class DownloadState:
    """
    Contains a snapshot of the state of the Download at a specific
    point in time. Using a snapshot instead of providing live data and
    protecting access via locking should be faster.

    cf. libtorrent torrent_status
    """

    def __init__(self, download, lt_status, error):
        """
        Internal constructor.
        @param download The download this state belongs too.
        @param lt_status The libtorrent status object
        @param tr_status Any Tribler specific information regarding the download
        """
        self._logger = logging.getLogger(self.__class__.__name__)

        self.download = download
        self.lt_status = lt_status
        self.error = error

    def get_download(self):
        """ Returns the Download object of which this is the state """
        return self.download

    def get_progress(self):
        """ The general progress of the Download as a percentage. When status is
         * DLSTATUS_HASHCHECKING it is the percentage of already downloaded
           content checked for integrity.
         * DLSTATUS_DOWNLOADING/SEEDING it is the percentage downloaded.
        @return Progress as a float (0..1).
        """
        return self.lt_status.progress if self.lt_status else 0

    def get_status(self):
        """ Returns the status of the torrent.
        @return DLSTATUS_* """
        if not self.lt_status:
            return (DLSTATUS_CIRCUITS if not self.download.session.tunnel_community
                    or self.download.session.tunnel_community.get_candidates(PEER_FLAG_EXIT_BT)
                    else DLSTATUS_EXIT_NODES) if self.download.config.get_hops() > 0 else DLSTATUS_WAITING4HASHCHECK
        elif self.get_error():
            return DLSTATUS_STOPPED_ON_ERROR
        return DLSTATUS_MAP[self.lt_status.state] if not self.lt_status.paused else DLSTATUS_STOPPED

    def get_error(self):
        """ Returns the Exception that caused the download to be moved to DLSTATUS_STOPPED_ON_ERROR status.
        @return An error message
        """
        return self.error or (self.lt_status.error if self.lt_status and self.lt_status.error else None)

    def get_current_speed(self, direct):
        """
        Returns the current up or download speed.
        @return The speed in bytes/s.
        """
        if not self.lt_status or self.get_status() not in [DLSTATUS_DOWNLOADING, DLSTATUS_SEEDING]:
            return 0
        elif direct == UPLOAD:
            return self.lt_status.upload_rate
        return self.lt_status.download_rate

    def get_current_payload_speed(self, direct):
        """
        Returns the current up or download payload speed.
        @return The speed in bytes/s.
        """
        if not self.lt_status or self.get_status() not in [DLSTATUS_DOWNLOADING, DLSTATUS_SEEDING]:
            return 0
        elif direct == UPLOAD:
            return self.lt_status.upload_payload_rate
        return self.lt_status.download_payload_rate

    def get_total_transferred(self, direct):
        """
        Returns the total amount of up or downloaded bytes.
        @return The amount in bytes.
        """
        if not self.lt_status:
            return 0
        elif direct == UPLOAD:
            return self.lt_status.total_upload
        return self.lt_status.total_download

    def get_seeding_ratio(self):
        if self.lt_status and self.lt_status.all_time_download > 0:
            return self.lt_status.all_time_upload / float(self.lt_status.all_time_download)
        return 0

    def get_seeding_time(self):
        return self.lt_status.finished_time if self.lt_status else 0

    def get_eta(self):
        """
        Returns the estimated time to finish of download.
        @return The time in ?, as ?.
        """
        return (1.0 - self.get_progress()) * (float(self.download.get_def().get_length()) /
                                              max(0.000001, self.lt_status.download_rate)) \
               if self.lt_status else 0.0

    def get_num_seeds_peers(self):
        """
        Returns the sum of the number of seeds and peers.
        @return A tuple (num seeds, num peers)
        """
        if not self.lt_status or self.get_status() not in [DLSTATUS_DOWNLOADING, DLSTATUS_SEEDING]:
            return 0, 0

        total = self.lt_status.list_peers
        seeds = self.lt_status.list_seeds
        return seeds, total - seeds

    def get_pieces_complete(self):
        """ Returns a list of booleans indicating whether we have completely
        received that piece of the content. The list of pieces for which
        we provide this info depends on which files were selected for download
        using DownloadConfig.set_selected_files().
        @return A list of booleans
        """
        return self.lt_status.pieces if self.lt_status else []

    def get_pieces_total_complete(self):
        """ Returns the number of total and completed pieces
        @return A tuple containing two integers, total and completed nr of pieces
        """
        return (len(self.lt_status.pieces), sum(self.lt_status.pieces)) if self.lt_status else (0, 0)

    def get_files_completion(self):
        """ Returns a list of filename, progress tuples indicating the progress
        for every file selected using set_selected_files. Progress is a float
        between 0 and 1
        """
        completion = []

        if self.lt_status and self.download.handle and self.download.handle.is_valid():
            files = self.download.get_def().get_files_with_length()
            progress = self.download.handle.file_progress(flags=1)
            for index, (path, size) in enumerate(files):
                completion_frac = (float(progress[index]) / size) if size > 0 else 1
                completion.append((path, completion_frac))

        return completion

    def get_selected_files(self):
        selected_files = self.download.config.get_selected_files()
        if len(selected_files) > 0:
            return selected_files

    def get_availability(self):
        """ Return overall the availability of all pieces, using connected peers
        Availability is defined as the number of complete copies of a piece, thus seeders
        increment the availability by 1. Leechers provide a subset of piece thus we count the
        overall availability of all pieces provided by the connected peers and use the minimum
        of this + the average of all additional pieces.
        """
        if not self.lt_status:
            return 0  # We do not have any info for this download so we cannot accurately get its availability

        nr_seeders_complete = 0
        merged_bitfields = [0] * len(self.lt_status.pieces)

        peers = self.get_peerlist()
        for peer in peers:
            completed = peer.get('completed', 0)
            have = peer.get('have', [])

            if completed == 1 or have and all(have):
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

    def get_peerlist(self):
        """ Returns a list of dictionaries, one for each connected peer
        containing the statistics for that peer.
        """
        return self.download.get_peerlist()
