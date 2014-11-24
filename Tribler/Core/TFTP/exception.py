class InvalidPacketException(Exception):
    """ Indicates an invalid packet.
    """
    pass


class InvalidStringException(Exception):
    """ Indicates an invalid zero-terminated string.
    """
    pass


class InvalidOptionException(Exception):
    """ Indicates an invalid option.
    """
    pass