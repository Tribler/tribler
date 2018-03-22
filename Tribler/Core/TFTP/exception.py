"""
All exceptions used in the TFTP package.
"""


class InvalidPacketException(Exception):
    """Indicates an invalid packet."""
    pass


class InvalidStringException(Exception):
    """Indicates an invalid zero-terminated string."""
    pass


class FileNotFound(OSError):
    """Indicates that a file is not found."""
    pass
