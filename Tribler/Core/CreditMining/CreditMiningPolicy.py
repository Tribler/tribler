"""
Supported credit mining policy.
Author(s): Egbert Bouman, Mihai Capota, Elric Milon, Ardhi Putra
"""
import random

class BasePolicy(object):
    """
    Base class for determining what swarm selection policy will be applied
    """

    def sort(self, torrents):
        raise NotImplementedError()


class RandomPolicy(BasePolicy):
    """
    A credit mining policy that chooses a swarm randomly
    """

    def sort(self, torrents):
        result = torrents[:]
        random.shuffle(result)
        return result


class SeederRatioPolicy(BasePolicy):
    """
    Find the most underseeded swarm to boost.
    """

    def sort(self, torrents):
        def sort_key(torrent):
            ds = torrent.state
            seeds, peers = ds.get_num_seeds_peers() if ds else (0, 1)
            return seeds / float(seeds + peers)

        return sorted(torrents, key=sort_key, reverse=True)


class UploadPolicy(BasePolicy):
    """
    Choose swarm such that we maximize the total upload.
    """

    def sort(self, torrents):
        def sort_key(torrent):
            if torrent.download and torrent.download.handle:
                status = torrent.download.handle.status()
                return status.total_upload / float(status.active_time) if status.active_time else 0.0
            return 0.0

        return sorted(torrents, key=sort_key, reverse=True)
