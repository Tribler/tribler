
class GetPeersLookup(object):

    def __init__(self, info_hash):
        self._info_hash = info_hash

    @property
    def info_hash(self):
        return self._info_hash

    def get_status(self):
        #lock
        return self._status
    def set_status(self, query_status):
        #lock
        self._status = query_status
    status = property(get_status, set_status)


    
    def add_peers(self, peer_list):
        '''
        Library users should not use this method.
        '''
        #lock
        self._peers.append(peer_list)


