import logging
import random
import sys
from unittest.mock import Mock

import pytest

from tribler_core.modules.metadata_store.community.tcp_over_ipv8 import TCPConnection, TCPServer

random.seed(123)
root = logging.getLogger()
root.setLevel(logging.DEBUG)


class PrintHandler(logging.Handler):
    def emit(self, record):
        print(self.format(record))


handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
logging.getLogger('faker').setLevel(logging.ERROR)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
# root.addHandler(handler)
root.addHandler(PrintHandler())


class TestTcpConn:
    @pytest.mark.timeout(0)
    def test_tcp(self):
        print()

        syn_seq = -1
        srv0_ip = 0
        srv1_ip = 1
        connection_over_callback = Mock()
        has_data_to_send_callback = Mock()

        srv0 = TCPServer()

        # Init the connection
        srv0.connections[srv1_ip] = conn = TCPConnection(
            syn_seq,
            srv1_ip,
            connection_over_callback,
            has_data_to_send_callback,
        )

        # SYN: p0 -> p1
        data_to_send = conn.get_packets_to_send()
        raw_data = b"a" * 1000 * 2
        conn.add_data_to_send(raw_data)
        assert has_data_to_send_callback.assert_called_once
        assert data_to_send[0].is_tcp_syn

        srv1 = TCPServer()
        conn = srv1.handle_tcp(data_to_send[0], srv0_ip)

        # SYN+ACK: p1 -> p0
        data_to_send = conn.get_packets_to_send()
        assert data_to_send[0].is_tcp_syn
        assert data_to_send[0].is_tcp_ack

        conn = srv0.handle_tcp(data_to_send[0], srv1_ip)

        # DATA: p0 -> p1
        data_to_send = conn.get_packets_to_send()
        assert data_to_send[0].tcp_data
        assert data_to_send[1].tcp_data

        for p in data_to_send:
            conn = srv1.handle_tcp(p, srv0_ip)

        # ACK: p1 -> p0
        data_to_send = conn.get_packets_to_send()
        assert data_to_send[0].is_tcp_ack
        conn = srv0.handle_tcp(data_to_send[0], srv1_ip)

        # Close the connection and send FIN p0 -> p1
        conn.close()
        data_to_send = conn.get_packets_to_send()
        assert data_to_send[0].is_tcp_fin

        # final ACK: p1 -> p0
        conn = srv1.handle_tcp(data_to_send[0], srv0_ip)
        data_to_send = conn.get_packets_to_send()
        assert data_to_send[0].is_tcp_ack

        # Close the connection and send FIN p1 -> p0
        conn.close()
        data_to_send = conn.get_packets_to_send()
        conn = srv0.handle_tcp(data_to_send[0], srv1_ip)
        assert data_to_send[0].is_tcp_fin

        # final ACK: p0 -> p1
        data_to_send = conn.get_packets_to_send()
        assert data_to_send[0].is_tcp_ack
