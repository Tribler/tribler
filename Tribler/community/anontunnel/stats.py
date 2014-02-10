from collections import defaultdict
import logging
import sqlite3
import uuid
import time

from Tribler.community.anontunnel.community import TunnelObserver

__author__ = 'chris'


logger = logging.getLogger()


class CircuitStats:
    def __init__(self):
        self.timestamp = None
        self.times = []
        self.bytes_up_list = []
        self.bytes_down_list = []

        self.bytes_down = [0, 0]
        self.bytes_up = [0, 0]

        self.speed_up = 0.0
        self.speed_down = 0.0

    @property
    def bytes_downloaded(self):
        return self.bytes_down[1]

    @property
    def bytes_uploaded(self):
        return self.bytes_up[1]


class RelayStats:
    def __init__(self):
        self.timestamp = None

        self.times = []
        self.bytes_list = []
        self.bytes = [0, 0]
        self.speed = 0


class StatsCollector(TunnelObserver):
    def __init__(self, proxy):
        """
        @type proxy: Tribler.community.anontunnel.community.ProxyCommunity
        """
        self.stats = {
            'bytes_returned': 0,
            'bytes_exit': 0,
            'bytes_enter': 0
        }
        self.download_stats = {}
        self.session_id = uuid.uuid4()
        self.proxy = proxy

        self.running = False

        self.circuit_stats = defaultdict(lambda: CircuitStats())
        self.relay_stats = defaultdict(lambda: RelayStats())

    def pause(self):
        self.running = False
        self.proxy.remove_observer(self)

    def clear(self):
        self.circuit_stats.clear()
        self.relay_stats.clear()

    def stop(self):
        self.pause()
        self.clear()

    def start(self):
        if self.running:
            raise ValueError("Cannot start an already running stats collector")

        logger.error("Resuming stats collecting!")
        self.running = True
        self.proxy.add_observer(self)
        self.proxy.dispersy.callback.register(self.__calc_speeds)

    def __calc_speeds(self):
        while self.running:
            t2 = time.time()
            for circuit_id in self.proxy.circuits.keys():
                c = self.circuit_stats[circuit_id]

                if c.timestamp is None:
                    c.timestamp = time.time()
                elif c.timestamp < t2:

                    if len(c.bytes_up_list) == 0 or c.bytes_up[-1] != c.bytes_up_list[-1] and c.bytes_down[-1] != c.bytes_down_list[-1]:
                        c.bytes_up_list.append(c.bytes_up[-1])
                        c.bytes_down_list.append(c.bytes_down[-1])
                        c.times.append(t2)

                    c.speed_up = 1.0 * (c.bytes_up[1] - c.bytes_up[0]) / (t2 - c.timestamp)
                    c.speed_down = 1.0 * (c.bytes_down[1] - c.bytes_down[0]) / (t2 - c.timestamp)

                    c.timestamp = t2
                    c.bytes_up = [c.bytes_up[1], c.bytes_up[1]]
                    c.bytes_down = [c.bytes_down[1], c.bytes_down[1]]

            for relay_key in self.proxy.relay_from_to.values():
                r = self.relay_stats[relay_key]

                if r.timestamp is None:
                    r.timestamp = time.time()
                elif r.timestamp < t2:
                    if len(r.bytes_list) == 0 or r.bytes[-1] != r.bytes_list[-1]:
                        r.bytes_list.append(r.bytes[-1])
                        r.times.append(t2)

                    r.speed = 1.0 * (r.bytes[1] - r.bytes[0]) / (t2 - r.timestamp)
                    r.timestamp = t2
                    r.bytes = [r.bytes[1], r.bytes[1]]

            yield 1.0

    def on_enter_tunnel(self, circuit_id, candidate, origin, payload):
        self.stats['bytes_enter'] += len(payload)

    def on_incoming_from_tunnel(self, community, circuit_id, origin, data):
        self.stats['bytes_returned'] += len(data)
        self.circuit_stats[circuit_id].bytes_down[1] += len(data)

    def on_exiting_from_tunnel(self, circuit_id, candidate, destination, data):
        self.stats['bytes_exit'] += len(data)

        if circuit_id == 0:
            self.circuit_stats[0].bytes_up[-1] += len(data)

    def on_send_data(self, circuit_id, candidate, ultimate_destination, payload):
        self.circuit_stats[circuit_id].bytes_up[-1] += len(payload)

    def on_relay(self, from_key, to_key, data):
        self.relay_stats[from_key].bytes[-1] += len(data)
        self.relay_stats[to_key].bytes[-1] += len(data)

    def _create_stats(self):
        stats = {
            'uuid': str(self.session_id),
            'swift': self.download_stats,
            'bytes_enter': self.stats['bytes_enter'],
            'bytes_exit': self.stats['bytes_exit'],
            'bytes_return': self.stats['bytes_returned'],
            'circuits': [
                {
                    'hops': len(self.proxy.circuits[id].hops),
                    'bytes_down': c.bytes_down_list[-1] - c.bytes_down_list[0],
                    'bytes_up': c.bytes_up_list[-1] - c.bytes_up_list[0],
                    'time': c.times[-1] - c.times[0]
                }
                for id, c in self.circuit_stats.items()
                if len(c.times) >= 2
            ],
            'relays': [
                {
                    'bytes': r.bytes_list[-1],
                    'time': r.times[-1] - r.times[0]
                }
                for r in self.relay_stats.values()
                if r.times and len(r.times) >= 2
            ]
        }

        return stats

    def on_unload(self):
        if self.download_stats:
            logger.error("Sharing statistics now!")
            self.share_stats()

    def share_stats(self):
        self.proxy.send_stats(self._create_stats())


class StatsCrawler(TunnelObserver):
    def __init__(self, raw_server):
        logger.warning("Running StatsCrawler")
        self.raw_server = raw_server
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

    def on_tunnel_stats(self,  community, candidate, stats):
        self.raw_server.add_task(lambda: self.on_stats(community, candidate, stats))

    def on_stats(self, community, candidate, stats):
        sock_address = candidate.sock_addr
        cursor = self.conn.cursor()

        try:
            cursor.execute('''INSERT OR FAIL INTO result
                                (encryption, session_id, time, host, port, swift_size, swift_time, bytes_enter, bytes_exit, bytes_returned)
                                VALUES (1, ?,DATETIME('now'),?,?,?,?,?,?,?)''',
                              [uuid.UUID(stats['uuid']),

                               sock_address[0], sock_address[1],
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

            logger.warning("Storing stats data of %s:%d" % sock_address)
        except sqlite3.IntegrityError as e:
            logger.error("Stat already exists of %s:%d"  % sock_address)
        except BaseException as e:
            logger.exception(e)

        cursor.close()

    def stop(self):
        logger.error("Stopping crawler")
        self.conn.close()