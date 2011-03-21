from Tribler.Core.dispersy.message import Packet
from Tribler.Core.dispersy.payload import Payload

class ChannelPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, name, description):
            assert isinstance(name, unicode)
            assert len(name) < 256
            assert isinstance(description, unicode)
            assert len(description) < 1024
            super(ChannelPayload.Implementation, self).__init__(meta)
            self._name = name
            self._description = description

        @property
        def name(self):
            return self._name

        @property
        def description(self):
            return self._description

class TorrentPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, infohash, timestamp):
            assert isinstance(infohash, str), 'infohash is a %s'%type(infohash)
            assert len(infohash) == 20, 'infohash has length %d'%len(infohash)
            assert isinstance(timestamp, (int, long))
            super(TorrentPayload.Implementation, self).__init__(meta)
            self._infohash = infohash
            self._timestamp = timestamp

        @property
        def infohash(self):
            return self._infohash

        @property
        def timestamp(self):
            return self._timestamp

class PlaylistPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, name, description):
            assert isinstance(name, unicode)
            assert len(name) < 255
            assert isinstance(description, unicode)
            assert len(description) < 1024
            super(PlaylistPayload.Implementation, self).__init__(meta)
            self._name = name
            self._description = description

        @property
        def name(self):
            return self._name

        @property
        def description(self):
            return self._description

class CommentPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, text, timestamp, reply_to_packet, reply_to_mid, reply_to_global_time, reply_after_packet, reply_after_mid, reply_after_global_time, playlist_packet, infohash):
            assert isinstance(text, unicode)
            assert len(text) < 2^16
            assert isinstance(timestamp, (int, long)) 
            
            assert not reply_to_packet or isinstance(reply_to_packet, Packet)
            assert not reply_to_mid or isinstance(reply_to_mid, str), 'reply_to_mid is a %s'%type(reply_to_mid)
            assert not reply_to_mid or len(reply_to_mid) == 20, 'reply_to_mid has length %d'%len(reply_to_mid)
            assert not reply_to_global_time or isinstance(reply_to_global_time, (int, long)), 'reply_to_global_time is a %s'%type(reply_to_global_time)
            
            assert not reply_after_packet or isinstance(reply_after_packet, Packet)
            assert not reply_after_mid or isinstance(reply_after_mid, str), 'reply_after_mid is a %s'%type(reply_after_mid)
            assert not reply_after_mid or len(reply_after_mid) == 20, 'reply_after_mid has length %d'%len(reply_after_global_time)
            assert not reply_after_global_time or isinstance(reply_after_global_time, (int, long)), 'reply_after_global_time is a %s'%type(reply_to_global_time)
            
            assert not playlist_packet or isinstance(playlist_packet, Packet)
            
            assert not infohash or isinstance(infohash, str), 'infohash is a %s'%type(infohash)
            assert not infohash or len(infohash) == 20, 'infohash has length %d'%len(infohash)
            
            super(CommentPayload.Implementation, self).__init__(meta)
            self._text = text
            self._timestamp = timestamp
            self._reply_to_packet = reply_to_packet
            self._reply_to_mid = reply_to_mid
            self._reply_to_global_time = reply_to_global_time
            
            self._reply_after_packet = reply_after_packet
            self._reply_after_mid = reply_after_mid
            self._reply_after_global_time = reply_after_global_time
            
            self._playlist_packet = playlist_packet
            self._infohash = infohash

        @property
        def text(self):
            return self._text
        
        @property
        def timestamp(self):
            return self._timestamp

        @property
        def reply_to_packet(self):
            return self._reply_to_packet
        
        @property
        def reply_to_mid(self):
            return self._reply_to_mid
        
        @property
        def reply_to_global_time(self):
            return self._reply_to_global_time
        
        @property
        def reply_to_id(self):
            if self._reply_to_mid and self._reply_to_global_time:
                return "%s@%d"%(self._reply_to_mid, self._reply_to_global_time)

        @property
        def reply_after_packet(self):
            return self._reply_after_packet
        
        @property
        def reply_after_mid(self):
            return self._reply_after_mid
        
        @property
        def reply_after_global_time(self):
            return self._reply_after_global_time
        
        @property
        def reply_after_id(self):
            if self._reply_after_mid and self._reply_after_global_time:
                return "%s@%d"%(self._reply_after_mid, self._reply_after_global_time)
        
        @property
        def playlist_packet(self):
            return self._playlist_packet
        
        @property
        def infohash(self):
            return self._infohash
        

class ModificationPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, modification, modification_on, latest_modification):
            assert isinstance(modification, dict)
            assert isinstance(modification_on, Packet)
            assert not latest_modification or isinstance(latest_modification, Packet)
            super(ModificationPayload.Implementation, self).__init__(meta)
            self._modification = modification
            self._modification_on = modification_on
            self._latest_modification = latest_modification

        @property
        def modification(self):
            return self._modification

        @property
        def modification_on(self):
            return self._modification_on
        
        @property
        def latest_modification(self):
            return self._latest_modification

class PlaylistTorrentPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, infohash, playlist):
            assert isinstance(infohash, str), 'infohash is a %s'%type(infohash)
            assert len(infohash) == 20, 'infohash has length %d'%len(infohash)
            assert isinstance(playlist, Packet)
            super(PlaylistTorrentPayload.Implementation, self).__init__(meta)
            self._infohash = infohash
            self._playlist = playlist

        @property
        def infohash(self):
            return self._infohash

        @property
        def playlist(self):
            return self._playlist

class MissingChannelPayload(Payload):
    pass