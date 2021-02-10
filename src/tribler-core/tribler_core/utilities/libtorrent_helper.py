__all__ = ['libtorrent']


class LibtorrentFallback:
    def __getattr__(self, item):
        # Cannot use RuntimeError here, as libtorrent functions like bdecode
        # raise RuntimeError as well, and we need to distinct these exceptions.
        raise ImportError('libtorrent library is not installed')


try:
    import libtorrent
except ImportError:
    libtorrent = LibtorrentFallback()
