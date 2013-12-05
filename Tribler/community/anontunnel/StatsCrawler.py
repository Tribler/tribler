import os
import logging.config
import uuid
import signal
from Tribler.community.anontunnel import ProxyMessage
from Tribler.community.anontunnel.HackyEndpoint import HackyEndpoint

logging.config.fileConfig(os.path.dirname(os.path.realpath(__file__)) + "/logger.conf")
logger = logging.getLogger(__name__)

import json
from threading import Thread, Event
from Tribler.Core.RawServer.RawServer import RawServer
from Tribler.community.anontunnel.ProxyCommunity import ProxyCommunity
from Tribler.dispersy.callback import Callback
from Tribler.dispersy.dispersy import Dispersy
import sqlite3

sqlite3.register_converter('GUID', lambda b: uuid.UUID(bytes_le=b))
sqlite3.register_adapter(uuid.UUID, lambda u: buffer(u.bytes_le))

class StatsCrawler(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.community = None

        self.server_done_flag = Event()
        self.raw_server = RawServer(self.server_done_flag,
                                    10.0 / 5.0,
                                    10.0,
                                    ipv6_enable=False)

        self.callback = Callback()

        self.endpoint = HackyEndpoint(self.raw_server, port=10000)
        self.prefix = 'f'*22 + 'e'
        self.endpoint.bypass_community = self
        self.endpoint.bypass_prefix = self.prefix
        
        self.dispersy = Dispersy(self.callback, self.endpoint, u".", u":memory:")

        self.first = True
        self.community = None

        self.conn = None

        def close_sql(*args, **kwargs):
            self.raw_server.add_task(self.stop)

        def init_sql():
            self.conn = sqlite3.connect("results.db")

            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS result(
                    result_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id GUID UNIQUE,
                    host,
                    port,
                    swift_size,
                    swift_time,
                    bytes_enter,
                    bytes_exit,
                    bytes_returned
                )
             ''')

            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS result_circuit (
                    result_circuit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    result_id,
                    hops,
                    bytes_up,
                    bytes_down,
                    time
                )
            ''')

            self.conn.execute('''
            CREATE TABLE IF NOT EXISTS result_relay(
                result_relay_id INTEGER PRIMARY KEY AUTOINCREMENT,
                result_id,
                bytes,
                time
            )
            ''')

        self.raw_server.add_task(init_sql)
        signal.signal(signal.SIGINT, close_sql)


    def on_bypass_message(self, sock_addr, packet):
        buffer = packet[len(self.prefix):]

        circuit_id, data = ProxyMessage.get_circuit_and_data(buffer)
        if circuit_id != 0:
            return

        type, payload = ProxyMessage.parse_payload(data)

        if type == ProxyMessage.MESSAGE_STATS:
            self.on_stats(sock_addr, payload)


    def run(self):
        def on_ready(community):
            logger.error("Community has been loaded")
            self.community = community

        def join_overlay(dispersy):
            dispersy.define_auto_load(ProxyCommunity,
                                      (self.dispersy.get_new_member(), on_ready),
                                      load=True)

        self.dispersy.start()
        self.dispersy.callback.call(join_overlay, (self.dispersy,))
        self.raw_server.listen_forever(None)

    @staticmethod
    def stats_to_txt(stats):
        return json.dumps(stats)

    def on_stats(self, sock_addr, stats):
        cursor = self.conn.cursor()

        try:

            cursor.execute('''INSERT OR FAIL INTO result
                                (session_id, host, port, swift_size, swift_time, bytes_enter, bytes_exit, bytes_returned)
                                VALUES (?,?,?,?,?,?,?,?)''',
                              [uuid.UUID(stats['uuid']),
                               sock_addr[0], sock_addr[1],
                              stats['swift']['size'],
                              stats['swift']['download_time'],
                              stats['bytes_enter'],
                              stats['bytes_exit'],
                              stats['bytes_return']]
                )

            result_id = cursor.lastrowid

            for c in stats['circuits']:
                cursor.execute('''
                    INSERT INTO result_circuit (result_id, hops, bytes_up, bytes_down, time)
                        VALUES (?, ?, ?, ?, ?)
                ''', [result_id, c['hops'], c['bytes_up'], c['bytes_down'], c['time']])

            for c in stats['relays']:
                cursor.execute('''
                    INSERT INTO result_relay (result_id, bytes, time)
                        VALUES (?, ?, ?)
                ''', [result_id, c['bytes'], c['time']])

            self.conn.commit()
        except sqlite3.IntegrityError:
            logger.info("Already stored this stat")
        except BaseException as e:
            logger.exception(e)

        cursor.close()

    def stop(self):
        logger.error("Stopping crawler")
        self.conn.close()
        self.dispersy.stop()
        self.server_done_flag.set()
        self.raw_server.shutdown()


def main():
    stats_crawler = StatsCrawler()
    stats_crawler.run()

if __name__ == "__main__":
    main()
