# Written by Boxun Zhang
# see LICENSE.txt for license information

import sys
import logging

from Tribler.Core.simpledefs import DLSTATUS_SEEDING, DLMODE_VOD
from Tribler.Main.vwxGUI.UserDownloadChoice import UserDownloadChoice


class GlobalSeedingManager:

    def __init__(self, Read):
        self._logger = logging.getLogger(self.__class__.__name__)

        # seeding managers containing infohash:seeding_manager pairs
        self.seeding_managers = {}

        # callback to read from abc configuration file
        self.Read = Read

    def apply_seeding_policy(self, dslist):
        # Remove stopped seeds
        for infohash, seeding_manager in self.seeding_managers.items():
            if not seeding_manager.download_state.get_download().get_status() == DLSTATUS_SEEDING:
                self._logger.debug("SeedingManager: removing seeding manager %s", infohash.encode("HEX"))
                del self.seeding_managers[infohash]

        for download_state in dslist:
            # Arno, 2012-05-07: ContentDef support
            cdef = download_state.get_download().get_def()
            hash = cdef.get_id()
            if download_state.get_status() == DLSTATUS_SEEDING:
                if hash not in self.seeding_managers:
                    # apply new seeding manager
                    self._logger.debug("SeedingManager: apply seeding manager %s", hash.encode("HEX"))
                    seeding_manager = SeedingManager(download_state)

                    policy = self.Read('t4t_option', "int") if cdef.get_def_type() == 'torrent' else self.Read('g2g_option', "int")
                    if policy == 0:
                        # No leeching, seeding until sharing ratio is met
                        self._logger.debug("GlobalSeedingManager: RatioBasedSeeding")
                        seeding_manager.set_policy(TitForTatRatioBasedSeeding(self.Read) if cdef.get_def_type() == 'torrent' else GiveToGetRatioBasedSeeding(self.Read))

                    elif policy == 1:
                        # Unlimited seeding
                        self._logger.debug("GlobalSeedingManager: UnlimitedSeeding")
                        seeding_manager.set_policy(UnlimitedSeeding())

                    elif policy == 2:
                        # Time based seeding
                        self._logger.debug("GlobalSeedingManager: TimeBasedSeeding")
                        seeding_manager.set_policy(TitForTatTimeBasedSeeding(self.Read) if cdef.get_def_type() == 'torrent' else GiveToGetTimeBasedSeeding(self.Read))

                    else:
                        # No seeding
                        self._logger.debug("GlobalSeedingManager: NoSeeding")
                        seeding_manager.set_policy(NoSeeding())

                    self.seeding_managers[hash] = seeding_manager

                self.seeding_managers[hash].update_download_state(download_state)


class SeedingManager:

    def __init__(self, download_state):
        self._logger = logging.getLogger(self.__class__.__name__)

        self.download_state = download_state
        self.policy = None
        self.udc = UserDownloadChoice.get_singleton()

    def update_download_state(self, download_state):
        self.download_state = download_state
        download = self.download_state.get_download()
        if download.get_def().get_def_type() == 'torrent':
            if self.udc.get_download_state(download.get_def().get_id()) != 'restartseed' and download.get_mode() != DLMODE_VOD:
                if not self.policy.apply(self.download_state, self.download_state.get_seeding_statistics()):
                    if DEBUG:
                        print("Stop seeding with libtorrent: ", self.download_state.get_download().get_dest_files(), file=sys.stderr)
                    self.udc.set_download_state(download.get_def().get_id(), 'stop')
                    self.download_state.get_download().stop()
        else:
            if self.udc.get_download_state(download.get_def().get_id()) != 'restartseed' and download.get_mode() != DLMODE_VOD:
                if not self.policy.apply(self.download_state, self.download_state.get_seeding_statistics()):
                    if DEBUG:
                        print("Stop seeding with libswift: ", self.download_state.get_download().get_dest_files(), file=sys.stderr)
                    self.download_state.get_download().stop()

    def set_policy(self, policy):
        self.policy = policy


class SeedingPolicy:

    def __init__(self):
        pass

    def apply(self, _, __):
        pass


class UnlimitedSeeding(SeedingPolicy):

    def __init__(self):
        SeedingPolicy.__init__(self)

    def apply(self, _, __):
        return True


class NoSeeding(SeedingPolicy):

    def __init__(self):
        SeedingPolicy.__init__(self)

    def apply(self, _, __):
        return False


class TitForTatTimeBasedSeeding(SeedingPolicy):

    def __init__(self, Read):
        self._logger = logging.getLogger(self.__class__.__name__)
        SeedingPolicy.__init__(self)
        self.Read = Read

    def apply(self, _, storage):
        current = storage["time_seeding"]
        limit = long(self.Read('t4t_hours', "int")) * 3600 + long(self.Read('t4t_mins', "int")) * 60
        self._logger.debug("TitForTatTimeBasedSeeding: apply: %s/ %s", current, limit)
        return current <= limit


class GiveToGetTimeBasedSeeding(SeedingPolicy):

    def __init__(self, Read):
        self._logger = logging.getLogger(self.__class__.__name__)
        SeedingPolicy.__init__(self)
        self.Read = Read

    def apply(self, _, storage):
        current = storage["time_seeding"]
        limit = long(self.Read('g2g_hours', "int")) * 3600 + long(self.Read('g2g_mins', "int")) * 60
        self._logger.debug("GiveToGetTimeBasedSeeding: apply: %s / %s", current, limit)
        return current <= limit


class TitForTatRatioBasedSeeding(SeedingPolicy):

    def __init__(self, Read):
        self._logger = logging.getLogger(self.__class__.__name__)
        SeedingPolicy.__init__(self)
        self.Read = Read

    def apply(self, download_state, storage):
        # No Bittorrent leeching (minimal ratio of 1.0)
        ul = storage["total_up"]
        dl = storage["total_down"]

        # set dl at min progress*length
        size_progress = download_state.get_length() * download_state.get_progress()
        dl = max(dl, size_progress)

        if dl == 0:
            # no download will result in no-upload to anyone
            ratio = 1.0
        else:
            ratio = 1.0 * ul / dl

        self._logger.debug("TitForTatRatioBasedSeeding: apply: %s %s %s", dl, ul, ratio)

        return ratio < self.Read('t4t_ratio', "int") / 100.0


class GiveToGetRatioBasedSeeding(SeedingPolicy):

    def __init__(self, Read):
        self._logger = logging.getLogger(self.__class__.__name__)
        SeedingPolicy.__init__(self)
        self.Read = Read

    def apply(self, download_state, storage):
        ul = storage["total_up"]
        dl = storage["total_down"]

        if dl == 0:
            # no download will result in no-upload to anyone
            ratio = 1.0
        else:
            ratio = 1.0 * ul / dl

        self._logger.debug("GiveToGetRatioBasedSeedingapply: %s %s %s %s", dl, ul, ratio, self.Read('g2g_ratio', "int") / 100.0)
        return ratio < self.Read('g2g_ratio', "int") / 100.0
