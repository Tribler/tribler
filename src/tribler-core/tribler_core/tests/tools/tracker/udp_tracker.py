import random
import struct
from asyncio import DatagramProtocol, get_event_loop

from tribler_core.components.torrent_checker.torrent_checker.torrentchecker_session import MAX_INT32
from tribler_core.tests.tools.tracker.tracker_info import TrackerInfo

UDP_TRACKER_INIT_CONNECTION_ID = 0x41727101980
LENGTH_INFOHASH = 20

TRACKER_ACTION_CONNECT = 0
TRACKER_ACTION_ANNOUNCE = 1
TRACKER_ACTION_SCRAPE = 2
TRACKER_ACTION_ERROR = 3


class UDPTrackerProtocol(DatagramProtocol):

    def __init__(self, tracker_session):
        self.transaction_id = -1
        self.connection_id = -1
        self.tracker_session = tracker_session
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, response, host_and_port):
        """
        Parse an incoming datagram. Check the action and based on that, send a response.
        """
        (host, port) = host_and_port
        connection_id, action, transaction_id = struct.unpack_from('!qii', response, 0)
        if action == 0 and connection_id != UDP_TRACKER_INIT_CONNECTION_ID:
            self.send_error(host, port, "invalid protocol")
        self.transaction_id = transaction_id

        if action == TRACKER_ACTION_CONNECT:
            self.send_connection_reply(host, port)
        elif action == TRACKER_ACTION_SCRAPE:
            if len(response) - 16 < LENGTH_INFOHASH:
                self.send_error(host, port, "no infohash")
                return

            num_infohashes = (len(response) - 16) // LENGTH_INFOHASH
            infohashes = []
            for ind in range(num_infohashes):
                tup = struct.unpack_from('!' + str(LENGTH_INFOHASH) + 'c', response, 16 + ind * LENGTH_INFOHASH)
                infohash = b''.join(tup)
                if not self.tracker_session.tracker_info.has_info_about_infohash(infohash):
                    self.send_error(host, port, f"no info about hash {infohash}")
                    return
                infohashes.append(infohash)

            self.send_scrape_reply(host, port, infohashes)

    def send_connection_reply(self, host, port):
        """
        Send a connection reply.
        """
        self.connection_id = random.randint(0, MAX_INT32)
        response_msg = struct.pack('!iiq', TRACKER_ACTION_CONNECT, self.transaction_id, self.connection_id)
        self.transport.sendto(response_msg, (host, port))

    def send_scrape_reply(self, host, port, infohashes):
        """
        Send a scrape reply.
        """
        response_msg = struct.pack('!ii', TRACKER_ACTION_SCRAPE, self.transaction_id)
        for infohash in infohashes:
            ih_info = self.tracker_session.tracker_info.get_info_about_infohash(infohash)
            response_msg += struct.pack('!iii', ih_info['seeders'], ih_info['downloaded'], ih_info['leechers'])
        self.transport.sendto(response_msg, (host, port))

    def send_error(self, host, port, error_msg):
        """
        Send an error message if the client does not follow the protocol.
        """
        response_msg = struct.pack('!ii' + str(len(error_msg)) + 's', TRACKER_ACTION_ERROR,
                                   self.transaction_id, error_msg)
        self.transport.sendto(response_msg, (host, port))


class UDPTracker:

    def __init__(self, port):
        super().__init__()
        self.port = port
        self.transport = None
        self.tracker_info = TrackerInfo()

    async def start(self):
        """
        Start the UDP Tracker
        """
        self.transport, _ = await get_event_loop().create_datagram_endpoint(lambda: UDPTrackerProtocol(self),
                                                                            local_addr=('127.0.0.1', self.port))

    async def stop(self):
        """
        Stop the UDP Tracker, returns a deferred that fires when the server is closed.
        """
        if self.transport:
            self.transport.close()
