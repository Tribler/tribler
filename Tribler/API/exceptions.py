# Written by Arno Bakker 
# see LICENSE.txt for license information

#
# Exceptions
#
class TriblerException(Exception):
    
    def __init__(self,msg=None):
        Exception.__init__(self,msg)

    def __str__(self):
        return str(self.__class__)+': '+Exception.__str__(self)
 

class OperationNotPossibleAtRuntimeException(TriblerException):
    
    def __init__(self,msg=None):
        TriblerException.__init__(self,msg)
    
class NotYetImplementedException(TriblerException):
    
    def __init__(self,msg=None):
        TriblerException.__init__(self,msg)


class DownloadIsStoppedException(TriblerException):
    
    def __init__(self,msg=None):
        TriblerException.__init__(self,msg)


class DuplicateDownloadException(TriblerException):
    
    def __init__(self,msg=None):
        TriblerException.__init__(self,msg)

class VODNoFileSelectedInMultifileTorrentException(TriblerException):
    
    def __init__(self,msg=None):
        TriblerException.__init__(self,msg)

class TriblerLegacyException(TriblerException):
    """ Wrapper around fatal errors that happen in the download engine,
    but which are not reported as Exception objects for legacy reasons,
    just as text (often containing a stringified Exception).
    Will be phased out.
    """
    
    def __init__(self,msg=None):
        TriblerException.__init__(self,msg)
    
