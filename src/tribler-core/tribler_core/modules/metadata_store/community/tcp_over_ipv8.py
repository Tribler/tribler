"""
TCP-like protocol on top or IPv8
Author: Vadim Bulavintsev
https://github.com/ichorid

Most of the code copy-pasted from the Stanford VNS project (2010) by David Underhill,
https://github.com/dound/vns/blob/master/TCPStack.py
"""
import logging
import random
import struct
import time

from ipv8.messaging.lazy_payload import VariablePayload, vp_compile
from ipv8.taskmanager import TaskManager

logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)

DEFAULT_MTU = 1300
DEFAULT_WINDOW_SIZE = 5000

HTTP_PORT = struct.pack("> H", 80)  # normally 80
HTTP_ALT_PORT = struct.pack("> H", 8080)  # normally 8080


def ceildiv(a, b):
    return -(-a // b)


def checksum(buf):
    """One's complement 16-bit checksum."""
    # ensure multiple of two length
    if len(buf) & 1:
        buf = buf + "\0"
    sz = len(buf)

    # add all 16 bit pairs into the total
    num_shorts = sz / 2
    tot = sum(struct.unpack("> %uH" % num_shorts, buf))

    # fold any carries back into the lower 16 bits
    tot = (tot >> 16) + (tot & 0xFFFF)  # add hi 16 to low 16
    tot += tot >> 16  # add carry
    return (~tot) & 0xFFFF  # truncate to 16 bits


def tcp_checksum(ip_hdr, tcp_hdr, tcp_data):
    """Computes the TCP checksum for the given TCP/IP data."""

    total_len = struct.pack("> H", len(tcp_hdr) + len(tcp_data))
    pseudo_hdr = ip_hdr[12:20] + "\x00" + ip_hdr[9] + total_len
    tcp_hdr_with_zero_csum = tcp_hdr[0:16] + "\x00\x00" + tcp_hdr[18:]
    pad = "\x00" if len(tcp_data) & 1 else ""
    combined = tcp_hdr_with_zero_csum + tcp_data + pad + pseudo_hdr
    return checksum(combined)


TCP_FIN_FLAG = 0x01
TCP_SYN_FLAG = 0x02
TCP_RST_FLAG = 0x04
TCP_ACK_FLAG = 0x10


@vp_compile
class TcpPayload(VariablePayload):
    msg_id = 22
    names = [
        "seq",
        "ack",
        "flags",
        "window",
        "tcp_data",
    ]
    format_list = ["I", "I", "B", "H", "raw"]

    @property
    def is_tcp_syn(self):
        return bool(self.flags & TCP_SYN_FLAG)

    @property
    def is_tcp_fin(self):
        return bool(self.flags & TCP_FIN_FLAG)

    @property
    def is_tcp_ack(self):
        return bool(self.flags & TCP_ACK_FLAG)


def cmp(a, b):
    return (a > b) - (a < b)


def make_tcp_packet(
    seq=0,
    ack=0,
    window=DEFAULT_WINDOW_SIZE,
    data=b"",
    is_fin=False,
    is_rst=False,
    is_syn=False,
    is_ack=False,
):
    """Creates a TCP header with no options and with the checksum zeroed."""
    flags = 0x00
    if is_fin:
        flags |= TCP_FIN_FLAG
    if is_syn:
        flags |= TCP_SYN_FLAG
    if is_rst:
        flags |= TCP_RST_FLAG
    if is_ack:
        flags |= TCP_ACK_FLAG
    return TcpPayload(seq, ack, flags, window, data)


def add_fin_to_tcp_packet(payload: TcpPayload):
    """Add the FIN flag to a TCP packet (as returned by make_tcp_packet)."""
    payload.flags |= TCP_FIN_FLAG
    return payload


class TCPSegment:
    """Describes a contiguous chunk of data in a TCP stream."""

    def __init__(self, seq, data):
        self.seq = seq  # sequence # of the first byte in this segment
        self.data = data  # data in this segment
        self.next = seq + len(data)  # first sequence # of the next data byte
        if not data:
            raise Exception("segments must contain at least 1B of data")

    def combine(self, s2):
        """Combine this segment with a s2 which comes no earlier than this
        segment starts.  If they do not overlap or meet, False is returned."""
        assert self.__cmp__(s2) <= 0, "segment 2 must not start earlier"

        if self.next < s2.seq:
            return False  # no overlap: s2 is later than us

        if self.next >= s2.next:
            return True  # self completely subsumes s2

        # combine the two segments
        offset = self.next - s2.seq
        new_data = self.data + s2.data[offset:]  # union of the two

        self.data = new_data
        self.next = s2.next
        return True

    def __cmp__(self, x):
        return cmp(self.seq, x.seq)

    def __len__(self):
        return len(self.data)


class TCPConnection(TaskManager):
    """Manages the state of one half of a TCP connection."""

    def __init__(
        self,
        syn_seq,
        other_ip,
        connection_over_callback,
        has_data_to_send_callback,
        assumed_rtt=0.5,
        mtu=DEFAULT_MTU,  # lowered to account for IPv8 headers, etc
        max_data=2048 * 1024 * 100,
        max_wait_time_sec=50,
    ):
        super().__init__()
        # socket pair
        self.other_ip = other_ip

        # TCP configuration
        self.rtt = assumed_rtt
        self.mtu = mtu
        self.max_data = max_data
        self.max_wait_time_sec = max_wait_time_sec
        self.last_activity = time.time()
        # self.register_anonymous_task("Check wait time", self.__check_wait_time, delay=self.max_wait_time_sec)
        # reactor.callLater(self.max_wait_time_sec, self.__check_wait_time)

        # callbacks
        self.connection_over_callback = lambda: connection_over_callback(self)
        self.has_data_to_send_callback = lambda: has_data_to_send_callback(self)

        # info about this side of the TCP connection
        self.segments = []
        self.next_seq_needed = syn_seq + 1
        self.need_to_send_ack = False
        self.need_to_send_data = True  # need to send a SYN
        self.received_fin = False
        self.closed = False
        self.dead = False

        # information about outgoing data and relevant ACKs
        self.window = 0
        self.data_to_send = b""
        self.num_data_bytes_acked = 0
        self.first_unacked_seq = random.randint(0, 0x8FFFFFFF)
        self.last_seq_sent = self.first_unacked_seq
        self.my_syn_acked = False
        self.all_data_sent = True
        self.my_fin_sent = False
        self.my_fin_acked = False
        self.next_resend = 0
        self.reset_resend_timer()

    def add_segment(self, segment):
        """Merges segment into the bytes already received.  Raises socket.error
        if this segment indicates that the data block will exceed the maximum
        allowed."""
        if len(self.segments) > 0 and segment.next - self.segments[0].seq > self.max_data:
            raise OSError("maximum data limit exceeded")

        self.__add_segment(segment)
        if len(self.segments) > 0 and self.segments[0].next > self.next_seq_needed:
            self.__note_activity()
            self.next_seq_needed = self.segments[0].next
            self.__need_to_send_now()  # ACK the new data

    def __add_segment(self, segment):
        combined_index = None
        for i in range(len(self.segments)):
            if self.segments[i].combine(segment):
                combined_index = i
                break

        if combined_index is None:
            self.segments.append(segment)
            logging.debug("appended the new segment to the end of our current segments list")
            return
        else:
            logging.debug("merging the new segment into segment %d" % i)

        i = combined_index
        new_segment = self.segments[i]
        while i < len(self.segments) - 1:
            if new_segment.combine(self.segments[i + 1]):
                self.segments.pop(i + 1)
            else:
                break

    def add_data_to_send(self, data):
        """Adds data to be sent to the other side of the connection.  Raises
        socket.error if the socket is closed."""
        if self.closed:
            raise OSError("cannot send data on a closed socket")

        logging.debug("Adding %dB to send (%dB already waiting)" % (len(data), len(self.data_to_send)))
        self.data_to_send += data
        self.all_data_sent = False
        self.__need_to_send_now(True)  # send the data

    def __check_wait_time(self):
        """Checks to see if this connection has been idle for longer than
        allowed.  If so, it is marked as dead and the connection_over_callback
        is called."""
        if time.time() - self.last_activity > self.max_wait_time_sec:
            self.connection_over_callback()
            self.dead = True
        else:
            self.register_anonymous_task(
                "Call __check_wait_time ",
                self.__check_wait_time,
                delay=self.max_wait_time_sec,
            )
            # reactor.callLater(self.max_wait_time_sec, self.__check_wait_time)

    def close(self):
        """Closes this end of the connection.  Will cause a FIN to be sent if
        the connection was not already closed.  The connection will be call
        its connection over callback TCPConnection.WAIT_TIME_SEC later."""
        if not self.closed:
            self.closed = True
            self.__need_to_send_now()  # send the FIN

    def fin_received(self, seq):
        """Indicates that a FIN has been received from the other side."""
        self.received_fin = True
        self.next_seq_needed = seq + 1
        self.__need_to_send_now()  # ACK the FIN
        # self.register_anonymous_task("Send FIN", self.__check_wait_time, delay=self.max_wait_time_sec)

    def __get_ack_num(self):
        """Returns the sequence number we should use for the ACK field on
        outgoing packets."""
        return self.next_seq_needed

    def get_data(self):
        """Returns the data received so far (up to the first gap, if any)."""
        if self.segments:
            return self.segments[0].data
        else:
            return ""

    def has_data_to_send(self):
        """Returns True if there is an unACK'ed data waiting to be sent."""
        return self.num_unacked_data_bytes() > 0

    def has_ready_data(self):
        """Returns True if data has been received and there are no gaps in it."""
        logging.debug("# segments = %d" % len(self.segments))
        return len(self.segments) == 1

    def __need_to_send_now(self, data_not_ack=False):
        """The next call to get_packets_to_send will ensure an ACK is sent as
        well as any unacknowledged data."""
        if data_not_ack:
            self.need_to_send_data = True
        else:
            self.need_to_send_ack = True
        if self.has_data_to_send_callback:
            self.has_data_to_send_callback()

    def __note_activity(self):
        """Marks the current time as the last active time."""
        self.last_activity = time.time()

    def num_unacked_data_bytes(self):
        """Returns the number of outgoing data bytes which have not been ACK'ed."""
        return len(self.data_to_send) - self.num_data_bytes_acked

    def reset_resend_timer(self):
        """Resets the retransmission timer."""
        delay = 2 * self.rtt
        self.next_resend = time.time() + delay
        # self.register_anonymous_task("Run has_data_to_send_callback ", self.has_data_to_send_callback, delay=delay,)
        # reactor.callLater(2 * self.rtt, self.has_data_to_send_callback)

    def set_ack(self, ack):
        """Handles receipt of an ACK."""
        if ack - 1 > self.last_seq_sent:
            logging.warning(
                "truncating an ACK for bytes we haven't sent: ack=%d last_seq_sent=%d" % (ack, self.last_seq_sent)
            )
            ack = self.last_seq_sent + 1  # assume they meant to ack all bytes we have sent

        diff = ack - self.first_unacked_seq
        if diff > 0:
            self.__note_activity()
            self.reset_resend_timer()
            if not self.my_syn_acked:
                diff = diff - 1
                self.my_syn_acked = True

            if diff > self.num_unacked_data_bytes():
                self.my_fin_acked = True
                diff = self.num_unacked_data_bytes()

            self.num_data_bytes_acked += diff

            # logging.debug('received ack %d (last unacked was %d) => %dB less to send (%dB left)' % \
            #              (ack, self.first_unacked_seq, diff, self.num_unacked_data_bytes()))
            self.first_unacked_seq = ack

            # if data has been ACK'ed, then send more if we have any
            if diff > 0 and not self.all_data_sent and self.has_data_to_send():
                self.__need_to_send_now(True)

    def get_packets_to_send(self):
        """Returns a list of packets which should be sent now."""
        ret = []
        if self.dead:
            return ret

        # is it time to send data?
        retransmit = False
        now = time.time()
        if now < self.next_resend:
            if not self.need_to_send_ack and not self.need_to_send_data:
                logging.debug("not time to send any packets yet (now=%d next=%d)" % (now, self.next_resend))
                return ret
        else:
            logging.debug(
                "retransmit timer has expired: will retransmit %dB outstanding bytes",
                self.last_seq_sent - self.first_unacked_seq + 1,
            )
            retransmit = True

        # do we have something to send?
        if not self.my_syn_acked:
            logging.debug("Adding my SYN packet to the outgoing queue")
            ret.append(
                make_tcp_packet(
                    seq=self.first_unacked_seq,
                    ack=self.__get_ack_num(),
                    data=b"",
                    is_syn=True,
                    is_ack=self.__get_ack_num() > 0,
                )
            )

        sz = self.num_unacked_data_bytes()
        base_offset = self.first_unacked_seq + (0 if self.my_syn_acked else 1)
        if sz > 0:
            # figure out how many chunks we can send now
            data_chunk_size = self.mtu - 40  # 20B IP and 20B TCP header: rest for data
            num_chunks_left = ceildiv(sz, data_chunk_size)
            outstanding_bytes = self.last_seq_sent - self.first_unacked_seq + 1
            max_outstanding_chunks = self.window // data_chunk_size
            num_chunks_to_send_now = min(num_chunks_left, max_outstanding_chunks)
            logging.debug(
                "Will make sure %d chunks are out now (%d chunks total remain): chunk size=%dB, window=%dB=>%d chunks may be out, outstanding=%dB"
                % (
                    num_chunks_to_send_now,
                    num_chunks_left,
                    data_chunk_size,
                    self.window,
                    max_outstanding_chunks,
                    outstanding_bytes,
                )
            )
            # create the individual TCP packets to send
            for i in range(max(1, num_chunks_to_send_now)):
                # determine what bytes and sequence numbers this chunk includes
                start_index = i * data_chunk_size
                end_index_plus1 = min(sz, start_index + data_chunk_size)  # exclusive
                if end_index_plus1 == sz:
                    self.all_data_sent = True
                start_seq = base_offset + start_index
                end_seq = start_seq + end_index_plus1 - start_index - 1  # inclusive

                # manage retransmissions ...
                if not retransmit:
                    if end_seq <= self.last_seq_sent:
                        continue  # we've sent this segment before; don't retransmit it yet
                    diff = self.last_seq_sent - start_seq + 1
                    if diff > 0:
                        # we've sent part of this segment before: only send the new stuff
                        start_seq += diff
                        start_index += 1

                # indices are relative to the first unsent byte: transform these
                # to the actual queue (i.e., skip the ACK'ed bytes)
                start_index += self.num_data_bytes_acked
                end_index_plus1 += self.num_data_bytes_acked

                # track the latest byte we've sent and formulate this chunk into a packet
                self.last_seq_sent = max(self.last_seq_sent, end_seq)
                logging.debug(
                    "Adding data bytes from %d to %d (inclusive) to the outgoing queue" % (start_seq, end_seq)
                )
                ret.append(
                    make_tcp_packet(
                        seq=start_seq,
                        ack=self.__get_ack_num(),
                        data=self.data_to_send[start_index:end_index_plus1],
                        is_ack=True,  # CHECK THIS!
                    )
                )

        # send a FIN if we're closed, our FIN hasn't been ACKed, and we've sent
        # all the data we were asked to already (or there isn't any)
        if self.closed and not self.my_fin_acked and (self.all_data_sent or sz <= 0):
            if not self.my_fin_sent or retransmit:
                if ret:
                    logging.debug("Making the last packet a FIN packet")
                    ret[-1] = add_fin_to_tcp_packet(ret[-1])
                else:
                    logging.debug("Adding my FIN packet to the outgoing queue")
                    ret.append(
                        make_tcp_packet(
                            seq=base_offset + sz,
                            ack=self.__get_ack_num(),
                            data=b"",
                            is_fin=True,
                            is_ack=True,  # CHECK THIS!
                        )
                    )
            if not self.my_fin_sent:
                self.my_fin_sent = True
                self.last_seq_sent += 1

        if not ret and self.need_to_send_ack:
            logging.debug("Adding a pure ACK to the outgoing queue (nothing to piggyback on)")
            ret.append(
                make_tcp_packet(
                    seq=self.first_unacked_seq,
                    ack=self.__get_ack_num(),
                    data=b"",
                    is_ack=True,  # CHECK THIS!
                )
            )

        if ret:
            self.reset_resend_timer()
            self.need_to_send_ack = False
        return ret

    def release_segment_memory(self, num_bytes: int) -> bytes:
        # Truncate the segment available for consumption to release memory
        ready_segment_size = len(self.segments[0])

        if ready_segment_size < num_bytes:
            # Not enough bytes in the segment to decode the whole message
            raise Exception("Can't release segment memory - segment too short! %i %i", num_bytes, ready_segment_size)

        # The segment coincides with the message - pop it
        if ready_segment_size == num_bytes:
            return self.segments.pop(0).data

        # The segment is longer than the message - cut the message body from the segment
        elif ready_segment_size > num_bytes:
            segment = self.segments[0]
            self.segments[0] = TCPSegment(segment.seq + num_bytes, segment.data[num_bytes:])
            return segment.data[:num_bytes]


class TCPServer:
    """Implements a basic TCP Server which handles raw TCP packets passed to it."""

    def __init__(self, max_active_conns=25, has_data_to_send_callback=None):
        self.connections = {}
        self.max_active_conns = max_active_conns

        if has_data_to_send_callback is not None:
            self.__connection_has_data_to_send = has_data_to_send_callback

    def __connection_over(self, conn):
        """Called when it is ready to be removed.  Removes the connection."""
        other_ip = conn.other_ip
        logging.debug("connection over callback from: %s" % str(other_ip))
        try:
            del self.connections[other_ip]
        except KeyError:
            logging.warning("Tried to remove connection which is not in our dictionary: %s" % str(other_ip))

    def __connection_has_data_to_send(self, conn):
        """Called when a connection has data to send."""
        print("HAS DATA TO SEND BACK dst:", conn.other_ip)

    def handle_tcp(self, pkt: TcpPayload, ip_src):
        """Processes pkt as if it was just received.  pkt should be a valid TCP
        packet.  Returns the TCPConnection pkt is associated with, if any."""
        # assert pkt.is_tcp() and pkt.is_valid_tcp(), "TCPServer.handle_tcp expects a valid TCP packet as input"

        # get the connection associated with the client's socket, if any
        conn = self.connections.get(ip_src)
        if not conn:
            logging.debug("received TCP packet from a new socket pair: %s" % str(ip_src))
            # there is no connection for this socket pair -- did we get a SYN?
            if pkt.is_tcp_syn:
                if len(self.connections) >= self.max_active_conns:
                    logging.info(
                        "Ignoring new connection request: already have %d active connections (the max)"
                        % self.max_active_conns
                    )
                    return None

                conn = TCPConnection(
                    pkt.seq,
                    ip_src,
                    self.__connection_over,
                    self.__connection_has_data_to_send,
                )
                self.connections[ip_src] = conn
                logging.debug("received TCP SYN packet -- new connection created: %s" % conn)
            else:
                logging.debug("ignoring TCP packet without SYN for socket pair with no existing connection")
                return None  # this tcp fragment is not part of an active session: ignore it

        # pull out the data
        if len(pkt.tcp_data):
            logging.debug("Adding segment for %d bytes received" % len(pkt.tcp_data))
            try:
                conn.add_segment(TCPSegment(pkt.seq, pkt.tcp_data))
            except OSError:
                logging.debug("Maximum data allowed for a connection exceeded: closing it")
                conn.close()
                return None

        if pkt.is_tcp_fin:
            conn.fin_received(pkt.seq)

        # remember window and latest ACK
        conn.window = max(DEFAULT_MTU, pkt.window)  # ignore requests to shrink the window below an MTU
        if pkt.is_tcp_ack:
            if pkt.is_tcp_syn and conn.next_seq_needed == 0:  # Hacky!
                conn.next_seq_needed = pkt.seq + 1
            conn.set_ack(pkt.ack)
        return conn
