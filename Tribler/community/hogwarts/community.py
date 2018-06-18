from twisted.internet import reactor
from twisted.internet.task import LoopingCall

from Tribler.pyipv8.ipv8.deprecated.community import Community
from Tribler.pyipv8.ipv8.deprecated.payload import Payload
from Tribler.pyipv8.ipv8.deprecated.payload_headers import BinMemberAuthenticationPayload, GlobalTimeDistributionPayload
from Tribler.pyipv8.ipv8_service import _COMMUNITIES, IPv8
from Tribler.pyipv8.ipv8.configuration import get_default_configuration
from Tribler.pyipv8.ipv8.keyvault.crypto import ECCrypto
from Tribler.pyipv8.ipv8.peer import Peer
from twisted.python import log
observer = log.PythonLoggingObserver()
observer.start()

import Tribler.pyipv8.ipv8.deprecated.community as community_file
community_file._DEFAULT_ADDRESSES = [("127.0.0.1",10001)]


class TorrentMetadata(object):
    def __init__(self, ver, infohash, date, title):
        self.ver = ver
        self.infohash = infohash
        self.date = int(date)
        self.title = title 

test_md = TorrentMetadata(1, "12312312asddfasxf", 1528383245.0, "TEST torrent LA-la-la")

class MetadataRequestMessage(Payload):
    """
    //Request format:
    char request_format_version;
    char* keyword;
    """
    format_list = ['c','20s']

    def __init__(self, ver, keyword):
        self.ver = ver
        self.keyword = keyword 

    def to_pack_list(self):
        return [('c',   self.ver),
                ('20s',   self.keyword)]

    @classmethod
    def from_unpack_list(cls, ver, keyword):
        return           cls (ver, keyword)

class MetadataPushMessage(Payload):
    """
    //Metadata format is:
    char metadata_format_version;
    char[20] torrent_infohash;
    int torrent_creation_date; // Unix date
    char* torrent_title;
    """
    #format_list = ['c','20s','I','p']
    format_list = ['raw']

    def __init__(self, ver, infohash, date, title):
        self.ver = ver
        self.infohash = infohash
        self.date = date
        self.title = title

    def to_pack_list(self):
        return [('raw', self.title)]

        """
        return [('c',   self.ver),
                ('20s', self.infohash),
                ('I',   self.date),
                ('p',   self.title)]
        """

    @classmethod
    #def from_unpack_list(cls, ver, infohash, date, title):
        #return           cls (ver, infohash, date, title)
    def from_unpack_list(cls, title):
        return           cls (1, "aaa", 123, title)

class MyMessage(Payload):
    # When reading data, we unpack an unsigned integer from it.
    format_list = ['I']

    def __init__(self, clock):
        self.clock = clock

    def to_pack_list(self):
        # We convert this object by writing 'self.clock' as
        # an unsigned int. This conforms to the 'format_list'.
        return [('I', self.clock)]

    @classmethod
    def from_unpack_list(cls, clock):
        # We received arguments in the format of 'format_list'.
        # We instantiate our class using the unsigned int we
        # read from the raw input.
        return cls(clock)


class MyCommunity(Community):
    master_peer = Peer(ECCrypto().generate_key(u"medium"))

    def __init__(self, my_peer, endpoint, network):
        super(MyCommunity, self).__init__(my_peer, endpoint, network)

        self.message_id = {
        MetadataPushMessage:    1,
        MetadataRequestMessage: 2}

        self.decode_map[chr(1)]    = self.on_metadata_push
        self.decode_map[chr(2)] = self.on_metadata_request

        self.metadata_store = []
    def started(self):
        def start_communication():
            if not self.metadata_store:
                for p in self.get_peers():
                    self.request_metadata(p.address, "test")
                    #packet = self.create_message()
                    #self.endpoint.send(p.address, packet)
            else:
                self.cancel_pending_task("start_communication")
        self.register_task("start_communication", LoopingCall(start_communication)).start(5.0, True)

    def create_message(self, message_class, *args):
        auth = BinMemberAuthenticationPayload (self.my_peer.public_key.key_to_bin()).to_pack_list()
        dist = GlobalTimeDistributionPayload (self.claim_global_time()).to_pack_list()
        payload = message_class(*args).to_pack_list()
        return self._ez_pack(self._prefix, self.message_id[message_class], [auth, dist, payload])

    def request_metadata(self, dst, keyword):
        REQ_VER = chr(1) # request format version
        packet = self.create_message (MetadataRequestMessage, REQ_VER, keyword)
        self.endpoint.send(dst, packet)

    def push_metadata(self, dst, md):
        MD_VER = chr(1) # metadata format version
        packet = self.create_message (MetadataPushMessage, MD_VER, md.infohash, md.date, md.title)
        self.endpoint.send(dst, packet)

    def on_metadata_request(self, source_address, data):
        auth, dist, payload = self._ez_unpack_auth(MetadataRequestMessage, data)
        print (": " + str(payload))
        print ("received metadata request:" + str(source_address) + " : " + payload.keyword)
        dst = source_address
        self.push_metadata(dst, test_md)

    def on_metadata_push(self, source_address, data):
        auth, dist, payload = self._ez_unpack_auth(MetadataPushMessage, data)
        print ("received metadata push:" + str(source_address) + " : " + str(payload))
        md = TorrentMetadata(payload.ver, payload.infohash, payload.date, payload.title)
        self.metadata_store.append(md)

_COMMUNITIES['MyCommunity'] = MyCommunity


for i in [1, 2]:
    configuration = get_default_configuration()
    configuration['port'] = 10000+i
    configuration['address'] = "127.0.0.1"
    configuration['keys'] = [{
                'alias': "my peer",
                'generation': u"medium",
                'file': u"ec%d.pem" % i
            }]
    configuration['overlays'] = [{
        'class': 'MyCommunity',
        'key': "my peer",
        'walkers': [{
                        'strategy': "RandomWalk",
                        'peers': 10,
                        'init': {
                            'timeout': 3.0
                        }
                    }],
        'initialize': {},
        'on_start': [('started', )]
    }]
    IPv8(configuration)

reactor.run()
