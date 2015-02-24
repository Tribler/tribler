# Written by Arno Bakker
# see LICENSE.txt for license information
""" The Tribler-specifc Exceptions the Core may throw. """

#
# Exceptions
#


class TriblerException(Exception):

    """ Super class for all Tribler-specific Exceptions the Tribler Core
    throws.
    """

    def __init__(self, msg=None):
        Exception.__init__(self, msg)

    def __str__(self):
        return str(self.__class__) + ': ' + Exception.__str__(self)


class OperationNotPossibleAtRuntimeException(TriblerException):

    """ The requested operation is not possible after the Session or Download
    has been started.
    """

    def __init__(self, msg=None):
        TriblerException.__init__(self, msg)


class OperationNotPossibleWhenStoppedException(TriblerException):

    """ The requested operation is not possible when the Download
    has been stopped.
    """

    def __init__(self, msg=None):
        TriblerException.__init__(self, msg)


class OperationNotEnabledByConfigurationException(TriblerException):

    """ The requested operation is not possible with the current
    Session/Download configuration.
    """

    def __init__(self, msg=None):
        TriblerException.__init__(self, msg)


class NotYetImplementedException(TriblerException):

    """ The requested operation is not yet fully implemented. """

    def __init__(self, msg=None):
        TriblerException.__init__(self, msg)


class DuplicateDownloadException(TriblerException):

    """ The Download already exists in the Session, i.e., a Download for
    a torrent with the same infohash already exists. """

    def __init__(self, msg=None):
        TriblerException.__init__(self, msg)


class VODNoFileSelectedInMultifileTorrentException(TriblerException):

    """ Attempt to download a torrent in Video-On-Demand mode that contains
    multiple video files, but without specifying which one to play. """

    def __init__(self, msg=None):
        TriblerException.__init__(self, msg)


class LiveTorrentRequiresUsercallbackException(TriblerException):

    """ Attempt to download a live-stream torrent without specifying a
    callback function to call when the stream is ready to play.
    Use set_video_event_callback(usercallback) to correct this problem. """

    def __init__(self, msg=None):
        TriblerException.__init__(self, msg)


class TorrentDefNotFinalizedException(TriblerException):

    """ Attempt to start downloading a torrent from a torrent definition
    that was not finalized. """

    def __init__(self, msg=None):
        TriblerException.__init__(self, msg)


class TriblerLegacyException(TriblerException):

    """ Wrapper around fatal errors that happen in the download engine,
    but which are not reported as Exception objects for legacy reasons,
    just as text (often containing a stringified Exception).
    Will be phased out.
    """

    def __init__(self, msg=None):
        TriblerException.__init__(self, msg)
