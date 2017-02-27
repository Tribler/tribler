# Written by Arno Bakker
# see LICENSE.txt for license information
""" Contains a snapshot of the state of the Download at a specific point in time. """
import logging
import sys

from Tribler.Core.simpledefs import (DLSTATUS_DOWNLOADING, DLSTATUS_SEEDING, DLSTATUS_STOPPED,
                                     DLSTATUS_STOPPED_ON_ERROR, DLSTATUS_WAITING4HASHCHECK, UPLOAD)


class DownloadState(object):

    """
    Contains a snapshot of the state of the Download at a specific
    point in time. Using a snapshot instead of providing live data and
    protecting access via locking should be faster.

    cf. libtorrent torrent_status
    """

    def __init__(self, download, status, error, progress, stats=None, seeding_stats=None, filepieceranges=None, logmsgs=None, peerid=None, videoinfo=None):
        """ Internal constructor.
        @param download The Download this state belongs too.
        @param status The status of the Download (DLSTATUS_*)
        @param progress The general progress of the Download.
        @param stats The BT engine statistics for the Download.
        @param filepieceranges The range of pieces that we are interested in.
        The get_pieces_complete() returns only completeness information about
        this range. This is used for playing a video in a multi-torrent file.
        @param logmsgs A list of messages from the BT engine which may be of
        """
        self._logger = logging.getLogger(self.__class__.__name__)

        self.download = download
        self.filepieceranges = filepieceranges  # NEED CONC CONTROL IF selected_files RUNTIME SETABLE
        self.logmsgs = logmsgs
        self.vod_status_msg = None
        self.seeding_stats = seeding_stats

        self.haveslice = None
        self.stats = None
        self.length = None

        name = self.download.get_def().get_name()

        if stats is None:
            # No info available yet from download engine
            self._logger.debug("stats is None '%s'", name)
            self.error = error  # readonly access
            self.progress = progress
            if self.error is not None:
                self.status = DLSTATUS_STOPPED_ON_ERROR
            else:
                self.status = status

        elif error is not None:
            self._logger.debug("error is not None '%s'", name)
            self.error = error  # readonly access
            self.progress = 0.0  # really want old progress
            self.status = DLSTATUS_STOPPED_ON_ERROR

        elif status is not None and not status in [DLSTATUS_DOWNLOADING, DLSTATUS_SEEDING]:
            # For HASHCHECKING and WAITING4HASHCHECK
            self._logger.debug("we have status and it is not downloading or seeding '%s'", name)
            self.error = error
            self.status = status
            if self.status == DLSTATUS_WAITING4HASHCHECK:
                self.progress = 0.0
            else:
                self.progress = stats['frac']
                if 'wanted' in stats:
                    self.length = stats['wanted']

        else:
            # Copy info from stats
            self._logger.debug("copy from stats '%s'", name)
            self.error = None
            self.progress = stats['frac']
            if stats['frac'] == 1.0:
                self.status = DLSTATUS_SEEDING
            else:
                self.status = DLSTATUS_DOWNLOADING

            # Safe to store the stats dict. The stats dict is created per
            # invocation of the BT1Download returned statsfunc and contains no
            # pointers.
            #
            self.stats = stats

        if stats and stats.get('stats', None):
            # for pieces complete
            if not self.filepieceranges:
                self.haveslice = stats['stats'].have  # is copy of network engine list
            else:
                # For get_files_completion()
                self.haveslice_total = stats['stats'].have

                selected_files = self.download.get_selected_files()
                # Show only pieces complete for the selected ranges of files
                totalpieces = 0
                for t, tl, o, f in self.filepieceranges:
                    if f in selected_files or not selected_files:
                        diff = tl - t
                        totalpieces += diff

                haveslice = [False] * totalpieces
                have = 0
                index = 0
                for t, tl, o, f in self.filepieceranges:
                    if f in selected_files or not selected_files:
                        for piece in range(t, tl):
                            haveslice[index] = stats['stats'].have[piece]
                            if haveslice[index]:
                                have += 1

                            index += 1
                self.haveslice = haveslice
                if have == len(haveslice) and self.status == DLSTATUS_DOWNLOADING:
                    # we have all pieces of the selected files
                    self.status = DLSTATUS_SEEDING
                    self.progress = 1.0

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
        return self.progress

    def get_status(self):
        """ Returns the status of the torrent.
        @return DLSTATUS_* """
        return self.status

    def get_error(self):
        """ Returns the Exception that caused the download to be moved to
        DLSTATUS_STOPPED_ON_ERROR status.
        @return Exception
        """
        return self.error

    #
    # Details
    #
    def get_current_speed(self, direct):
        """
        Returns the current up or download speed.
        @return The speed in bytes/s.
        """
        if self.stats is None:
            return 0
        if direct == UPLOAD:
            return self.stats['up']
        else:
            return self.stats['down']

    def get_total_transferred(self, direct):
        """
        Returns the total amount of up or downloaded bytes.
        @return The amount in bytes.
        """
        if self.stats is None:
            return 0
        if direct == UPLOAD:
            return self.stats['stats'].upTotal
        else:
            return self.stats['stats'].downTotal

    def set_seeding_statistics(self, seeding_stats):
        self.seeding_stats = seeding_stats

    def get_seeding_statistics(self):
        """
        Returns the seedings stats for this download. Will only be availible after
        SeedingManager update_download_state is called.
        Contains if not null, version, total_up, total_down, time_seeding
        All values are stored by the seedingmanager, thus will not only contain current download session values
        """
        return self.seeding_stats

    @property
    def seeding_downloaded(self):
        return self.seeding_stats['total_down'] if self.seeding_stats else 0

    @property
    def seeding_uploaded(self):
        return self.seeding_stats['total_up'] if self.seeding_stats else 0

    @property
    def seeding_ratio(self):
        return self.seeding_stats['ratio'] if self.seeding_stats else 0.0

    def get_eta(self):
        """
        Returns the estimated time to finish of download.
        @return The time in ?, as ?.
        """
        return self.stats['time'] if self.stats else 0.0

    def get_num_con_initiated(self):
        """
        Returns the download's number of initiated connections. This is used
        to see if there is any progress when non-fatal errors have occured
        (e.g. tracker timeout).
        @return An integer.
        """
        return self.stats['stats'].numConInitiated if self.stats else 0

    def get_num_peers(self):
        """
        Returns the download's number of active connections. This is used
        to see if there is any progress when non-fatal errors have occured
        (e.g. tracker timeout).
        @return An integer.
        """
        if self.stats is None:
            return 0

        # Determine if we need statsobj to be requested, same as for spew
        statsobj = self.stats['stats']
        return statsobj.numSeeds + statsobj.numPeers

    def get_num_nonseeds(self):
        """
        Returns the download's number of non-seeders.
        @return An integer.
        """
        if self.stats is None:
            return 0

        # Determine if we need statsobj to be requested, same as for spew
        statsobj = self.stats['stats']
        return statsobj.numPeers

    def get_num_seeds_peers(self):
        """
        Returns the sum of the number of seeds and peers. This function
        works only if the Download.set_state_callback() /
        Session.set_download_states_callback() was called with the getpeerlist
        parameter set to True, otherwise returns (None,None)
        @return A tuple (num seeds, num peers)
        """
        if self.stats is None or self.stats.get('spew', None) is None:
            total = self.get_num_peers()
            non_seeds = self.get_num_nonseeds()
            return (total - non_seeds, non_seeds)

        total = len(self.stats['spew'])
        seeds = len([i for i in self.stats['spew'] if i.get('completed', 0) == 1.0])
        return seeds, total - seeds

    def get_pieces_complete(self):
        """ Returns a list of booleans indicating whether we have completely
        received that piece of the content. The list of pieces for which
        we provide this info depends on which files were selected for download
        using DownloadStartupConfig.set_selected_files().
        @return A list of booleans
        """
        if self.haveslice is None:
            return []
        else:
            return self.haveslice

    def get_pieces_total_complete(self):
        """ Returns the number of total and completed pieces
        @return A tuple containing two integers, total and completed nr of pieces
        """
        if self.haveslice is None:
            return (0, 0)
        else:
            return (len(self.haveslice), sum(self.haveslice))

    def get_files_completion(self):
        """ Returns a list of filename, progress tuples indicating the progress
        for every file selected using set_selected_files. Progress is a float
        between 0 and 1
        """
        if len(self.download.get_selected_files()) > 0:
            files = self.download.get_selected_files()
        else:
            files = self.download.get_def().get_files()

        completion = []
        if self.filepieceranges:
            for t, tl, o, f in self.filepieceranges:
                if f in files and self.progress == 1.0:
                    completion.append((f, 1.0))
                else:
                    # niels: ranges are from-to (inclusive ie if a file consists one piece t and tl will be the same)
                    total_pieces = tl - t
                    if total_pieces and getattr(self, 'haveslice_total', False):
                        completed = 0
                        for index in range(t, tl):
                            if self.haveslice_total[index]:
                                completed += 1

                        completion.append((f, completed / (total_pieces * 1.0)))
                    elif f in files:
                        completion.append((f, 0.0))
        elif files:
            # Single file
            completion.append((files[0], self.get_progress()))
        return completion

    def get_selected_files(self):
        selected_files = self.download.get_selected_files()
        if len(selected_files) > 0:
            return selected_files

    def get_length(self):
        # Niels: 28/08/2012 for larger .torrent this methods gets quite expensive,
        # cache the result to prevent us calculating this unnecessarily.
        if not self.length:
            files = self.get_selected_files()

            tdef = self.download.get_def()
            self.length = tdef.get_length(files)
        return self.length

    def get_availability(self):
        """ Return overall the availability of all pieces, using connected peers
        Availability is defined as the number of complete copies of a piece, thus seeders
        increment the availability by 1. Leechers provide a subset of piece thus we count the
        overall availability of all pieces provided by the connected peers and use the minimum
        of this + the average of all additional pieces.
        """
        nr_seeders_complete = 0
        merged_bitfields = None

        peers = self.get_peerlist()
        for peer in peers:
            completed = peer.get('completed', 0)
            have = peer.get('have', [])

            if completed == 1 or have and all(have):
                nr_seeders_complete += 1
            else:
                if merged_bitfields is None:
                    merged_bitfields = [0] * len(have)

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

    def get_vod_prebuffering_progress(self):
        """ Returns the percentage of prebuffering for Video-On-Demand already
        completed.
        @return A float (0..1) """
        if self.stats is None:
            if self.status == DLSTATUS_STOPPED and self.progress == 1.0:
                return 1.0
            else:
                return 0.0
        else:
            return self.stats['vod_prebuf_frac']

    def get_vod_prebuffering_progress_consec(self):
        """ Returns the percentage of consecutive prebuffering for Video-On-Demand already
        completed.
        @return A float (0..1) """
        if self.stats is None:
            if self.status == DLSTATUS_STOPPED and self.progress == 1.0:
                return 1.0
            else:
                return 0.0
        else:
            return self.stats.get('vod_prebuf_frac_consec', -1)

    def is_vod(self):
        """ Returns if this download is currently in vod mode

        @return A Boolean"""
        if self.stats is None:
            return False
        else:
            return self.stats['vod']

    def get_peerlist(self):
        """ Returns a list of dictionaries, one for each connected peer
        containing the statistics for that peer. In particular, the
        dictionary contains the keys:
        <pre>
        'id' = PeerID or 'http seed'
        'extended_version' = Peer client version, as received during the extend handshake message
        'ip' = IP address as string or URL of httpseed
        'port' = Port
        'pex_received' = True/False
        'optimistic' = True/False
        'direction' = 'L'/'R' (outgoing/incoming)
        'uprate' = Upload rate in KB/s
        'uinterested' = Upload Interested: True/False
        'uchoked' = Upload Choked: True/False
        'uhasqueries' = Upload has requests in buffer and not choked
        'uflushed' = Upload is not flushed
        'downrate' = Download rate in KB/s
        'dinterested' = Download interested: True/Flase
        'dchoked' = Download choked: True/False
        'snubbed' = Download snubbed: True/False
        'utotal' = Total uploaded from peer in KB
        'dtotal' = Total downloaded from peer in KB
        'completed' = Fraction of download completed by peer (0-1.0)
        -- QUESTION(lipu): swift and Bitfield are gone. Does this 'have' thing has anything to do with swift?
        'have' = Bitfield object for this peer if not complete
        'speed' = The peer's current total download speed (estimated)
        </pre>
        """
        if self.stats is None or 'spew' not in self.stats or self.stats['spew'] is None:
            return []
        else:
            return self.stats['spew']

    def get_tracker_status(self):
        if self.stats is None or 'tracker_status' not in self.stats or self.stats['tracker_status'] is None:
            return {}
        else:
            return self.stats['tracker_status']
