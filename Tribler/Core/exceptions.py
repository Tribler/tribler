# Written by Arno Bakker
# see LICENSE for license information
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


class HttpError(TriblerException):

    """ HTTP error code 400+ """

    def __init__(self, response=None, msg=None):
        TriblerException.__init__(self, msg)
        self.response = response


class DuplicateChannelNameError(TriblerException):

    """ The Channel name already exists in the ChannelManager channel list,
    i.e., one of your own Channels with the same name already exists. """

    pass


class DuplicateTorrentFileError(TriblerException):

    """ The Torrent already exists in the Channel you try to add it to. """

    pass


class SaveResumeDataError(TriblerException):

    """ This error is used when the resume data of a download fails to save. """

    pass


class DuplicateDownloadException(TriblerException):

    """ The Download already exists in the Session, i.e., a Download for
    a torrent with the same infohash already exists. """

    def __init__(self, msg=None):
        TriblerException.__init__(self, msg)


class TorrentDefNotFinalizedException(TriblerException):

    """ Attempt to start downloading a torrent from a torrent definition
    that was not finalized. """

    def __init__(self, msg=None):
        TriblerException.__init__(self, msg)


class TorrentFileException(TriblerException):

    """ The torrent file that is used is corrupt or cannot be read. """

    def __init__(self, msg=None):
        TriblerException.__init__(self, msg)
