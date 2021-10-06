__all__ = ['libtorrent']


class LibtorrentFallback:
    """
    Used as a fallback replacement for libtorrent library if it was not possible to import it.

    Any attempt to access any member raises ImportError.
    """

    def __getattr__(self, item):
        """
        Raises ImportError on any attempt to access a member of the class that is not explicitly defined.
        """
        # Cannot use RuntimeError here, as libtorrent functions like bdecode raise RuntimeError as well,
        # and we need to distinguish these exceptions.
        raise ImportError('libtorrent library is not installed')


try:
    import libtorrent
except ImportError:
    libtorrent = LibtorrentFallback()
