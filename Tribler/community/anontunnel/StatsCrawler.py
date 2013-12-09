import os
import logging.config
import uuid
from Tribler.community.anontunnel import ProxyMessage

logging.config.fileConfig(os.path.dirname(os.path.realpath(__file__)) + "/logger.conf")
logger = logging.getLogger(__name__)

import sqlite3

sqlite3.register_converter('GUID', lambda b: uuid.UUID(bytes_le=b))
sqlite3.register_adapter(uuid.UUID, lambda u: buffer(u.bytes_le))

class StatsCrawler(object):
    def __init__(self, proxy, raw_server):
        logger.warning("Running StatsCrawler")
        self.proxy = proxy
        self.raw_server = raw_server
        self.proxy.message_observer.subscribe(ProxyMessage.MESSAGE_STATS, self.on_stats)
        self.conn = None

        def close_sql(*args, **kwargs):
            self.raw_server.add_task(self.stop)

        def init_sql():
            self.conn = sqlite3.connect("results.db")

            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS result(
                    result_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id GUID UNIQUE,
                    time DATETIME,
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

    def on_stats(self, circuit_id, candidate, message):
        stats = message
        sock_addr = candidate.sock_addr
        cursor = self.conn.cursor()

        try:

            cursor.execute('''INSERT OR FAIL INTO result
                                (session_id, time, host, port, swift_size, swift_time, bytes_enter, bytes_exit, bytes_returned)
                                VALUES (?,DATETIME('now'),?,?,?,?,?,?,?)''',
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

            logger.warning("Storing stats data off %s:%d" % sock_addr)
        except sqlite3.IntegrityError:
            logger.info("Already stored this stat")
        except BaseException as e:
            logger.exception(e)

        cursor.close()

    def stop(self):
        logger.error("Stopping crawler")
        self.conn.close()


def main():
    stats_crawler = StatsCrawler()
    stats_crawler.run()

if __name__ == "__main__":
    main()
