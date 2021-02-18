import logging
import struct
from binascii import unhexlify

from ipv8.community import Community
from ipv8.lazy_community import lazy_wrapper
from ipv8.test.REST.test_overlays_endpoint import hexlify
from ipv8.types import Peer

from tribler_core.modules.metadata_store.community.tcp_over_ipv8 import TCPConnection, TCPServer, TcpPayload

BINARY_FIELDS = ("infohash", "channel_pk")

CHANNELS_SERVER_PORT = 99


class MessageFactory:
    header_size = 12  # Bytes
    magic = unhexlify("fefcccbeabf9fcb3")
    format = ">8s I"

    @classmethod
    def pack_message(cls, message_data: bytes) -> bytes:
        header = struct.pack(cls.format, cls.magic, len(message_data))
        return header + message_data

    @classmethod
    def get_frame_size(cls, raw_data: bytes) -> int:
        # Extracts message frame size and checks the message magic
        header = raw_data[: cls.header_size]
        magic, message_size = struct.unpack(cls.format, header)
        if magic != cls.magic:
            raise Exception("Wrong magic bytes in message %s", hexlify(magic))
        frame_size = cls.header_size + message_size

        return frame_size


class Tcp8MessageServer(TCPServer):
    def __init__(self, my_peer, on_packet, ez_send, overlay, **kwargs):
        super().__init__(**kwargs, has_data_to_send_callback=self.send_segments_for_connection)
        self.my_peer = my_peer
        self.on_packet = on_packet
        self.ez_send = ez_send
        self.overlay = overlay

    def on_tcp8_packet(self, src_peer, tcp8_payload):
        # Data contains a segment
        conn = self.handle_tcp(tcp8_payload, src_peer)
        self.send_segments_for_connection(conn)

        if not conn.has_ready_data():
            return

        # Segment contains a message
        message = self.check_message_ready(conn)
        if message is None:
            return

        # Message contains a request/response
        packet = (src_peer.address, message)
        self.on_packet(packet)

    def send_segments_for_connection(self, connection: TCPConnection):
        for segment_payload in connection.get_packets_to_send():
            self.overlay.ez_send(connection.other_ip, segment_payload)

    def send_message(self, peer: Peer, message_data: bytes):
        raw_data = MessageFactory.pack_message(message_data)
        ip_dst = peer

        conn = self.connections.get(ip_dst)
        if not conn:

            def connection_over_callback(s: TCPConnection):
                print("OVER")

            syn_seq = -1
            logging.debug("Creating a TCP8 connection: %s" % str(ip_dst))
            conn = TCPConnection(
                syn_seq,
                ip_dst,
                connection_over_callback,
                self.send_segments_for_connection,
            )
            self.connections[ip_dst] = conn
        conn.add_data_to_send(raw_data)

    @staticmethod
    def check_message_ready(conn: TCPConnection) -> bytes or None:
        # Parse the message header
        segment_data = conn.get_data()

        # TODO: stop unpacking every time?
        frame_size = MessageFactory.get_frame_size(segment_data)
        if len(segment_data) < frame_size:
            # Not enough bytes in the segment to decode the whole message - skipping
            return None
        frame = conn.release_segment_memory(frame_size)
        message = frame[MessageFactory.header_size :]
        return message

    async def shutdown(self):
        for conn in self.connections.values():
            await conn.shutdown_task_manager()


class Tcp8MessageCommunity(Community):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.tcp8_server = Tcp8MessageServer(self.my_peer, self.on_packet, self.ez_send, self)
        self.add_message_handler(TcpPayload, self.on_tcp8_packet)

    @lazy_wrapper(TcpPayload)
    async def on_tcp8_packet(self, src_peer, tcp8_payload):
        return self.tcp8_server.on_tcp8_packet(src_peer, tcp8_payload)

    def fat_send(self, peer, payload):
        serialized_payload = self.ezr_pack(payload.msg_id, payload)
        self.tcp8_server.send_message(peer, serialized_payload)

    async def unload(self):
        await self.tcp8_server.shutdown()
        await super().unload()
