# Written by Andrea Reale
# see LICENSE.txt for license information


class RichMetadataException(Exception):
    '''
    General exception of the RichMetadata subsystem
    '''


    def __init__(self, value):
        self.value = value
        
    def __str__(self):
        return repr(self.value)

class SerializationException(RichMetadataException):
    '''
    Thrown when some problem occurs when trying to transform a Metadata
    object into the external representation
    '''


    def __init__(self, value):
        self.value = value
        
    def __str__(self):
        return repr(self.value)

class SignatureException(RichMetadataException):
    '''
    Thrown when some problem occurs concerning metadata signature.
    '''
    def __init__(self, value):
        self.value = value
        
    def __str__(self):
        return repr(self.value)

class MetadataDBException(RichMetadataException):
    '''
    Thrown when something  violated Metadata and Subtitles DB constraints.
    '''
    def __init__(self, value):
        self.value = value
        
    def __str__(self):
        return repr(self.value)
    
class SubtitleMsgHandlerException(RichMetadataException):
    """
    Thrown when a problem is encountered in sending o receiving a subtitle
    message.
    """
    def __init__(self, value):
        self.value = value
        
    def __str__(self):
        return repr(self.value)
    
class DiskManagerException(RichMetadataException):
    '''
    Thrown by the Disk Manager when problems dealing with disk reading
    and writings occur
    '''
    def __init__(self, value):
        self.value = value
        
    def __str__(self):
        return repr(self.value)

    