import logging
import os
import sqlite3
import time
import uuid
from collections import defaultdict

from twisted.internet.base import DelayedCall
from twisted.internet.defer import Deferred
from twisted.internet.task import LoopingCall

from Tribler.community.anontunnel.crypto import NoCrypto
from Tribler.community.anontunnel.events import TunnelObserver
from Tribler.dispersy.database import Database


__author__ = 'chris'

sqlite3.register_converter('GUID', lambda b: uuid.UUID(bytes_le=b))
sqlite3.register_adapter(uuid.UUID, lambda u: buffer(u.bytes_le))

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
    def __init__(self, proxy, name):
        """
        @type proxy: Tribler.community.anontunnel.community.ProxyCommunity
        """

        TunnelObserver.__init__(self)

        self._logger = logging.getLogger(__name__)
        self.name = name

        self._pending_tasks = {}

        self.stats = {
            'bytes_returned': 0,
            'bytes_exit': 0,
            'bytes_enter': 0,
            'broken_circuits': 0
        }
        self.download_stats = {}
        self.session_id = uuid.uuid4()
        self.proxy = proxy
        self.running = False
        self.circuit_stats = defaultdict(lambda: CircuitStats())
        ''':type : dict[int, CircuitStats] '''
        self.relay_stats = defaultdict(lambda: RelayStats())
        ''':type : dict[((str,int),int), RelayStats] '''
        self._circuit_cache = {}
        ''':type : dict[int, Circuit] '''

    def cancel_pending_task(self, key):
        task = self._pending_tasks.pop(key)
        if isinstance(task, Deferred) and not task.called:
            # Have in mind that any deferred in the pending tasks list should have been constructed with a
            # canceller function.
            task.cancel()
        elif isinstance(task, DelayedCall) and task.active():
            task.cancel()
        elif isinstance(task, LoopingCall) and task.running:
            task.stop()

    def pause(self):
        """
        Pause stats collecting
        """
        self._logger.info("Removed StatsCollector %s as observer", self.name)
        self.running = False
        self.proxy.observers.remove(self)

        # cancel all pending tasks
        for key in self._pending_tasks.keys():
            self.cancel_pending_task(key)

    def clear(self):
        """
        Clear collected stats
        """

        self.circuit_stats.clear()
        self.relay_stats.clear()

    def stop(self):
        self.pause()
        self.clear()

    def start(self):
        if self.running:
            raise ValueError("Cannot start collector {0} since it is already running".format(self.name))

        self._logger.info("Resuming stats collector {0}!".format(self.name))
        self.running = True
        self.proxy.observers.append(self)
        self._pending_tasks["calc speeds"] = lc = LoopingCall(self.__calc_speeds)
        lc.start(1, now=True)

    def on_break_circuit(self, circuit):
        if len(circuit.hops) == circuit.goal_hops:
            self.stats['broken_circuits'] += 1

    def __calc_speeds(self):
        if self.running:
            t2 = time.time()
            self._circuit_cache.update(self.proxy.circuits)

            for circuit_id in self.proxy.circuits.keys():
                c = self.circuit_stats[circuit_id]

                if c.timestamp is None:
                    c.timestamp = time.time()
                elif c.timestamp < t2:

                    if len(c.bytes_up_list) == 0 or c.bytes_up[-1] != \
                            c.bytes_up_list[-1] and c.bytes_down[-1] != \
                            c.bytes_down_list[-1]:
                        c.bytes_up_list.append(c.bytes_up[-1])
                        c.bytes_down_list.append(c.bytes_down[-1])
                        c.times.append(t2)

                    c.speed_up = 1.0 * (c.bytes_up[1] - c.bytes_up[0]) / (
                        t2 - c.timestamp)
                    c.speed_down = 1.0 * (
                        c.bytes_down[1] - c.bytes_down[0]) / (t2 - c.timestamp)

                    c.timestamp = t2
                    c.bytes_up = [c.bytes_up[1], c.bytes_up[1]]
                    c.bytes_down = [c.bytes_down[1], c.bytes_down[1]]

            for relay_key in self.proxy.relay_from_to.keys():
                r = self.relay_stats[relay_key]

                if r.timestamp is None:
                    r.timestamp = time.time()
                elif r.timestamp < t2:
                    changed = len(r.bytes_list) == 0 \
                        or r.bytes[-1] != r.bytes_list[-1]

                    if changed:
                        r.bytes_list.append(r.bytes[-1])
                        r.times.append(t2)

                    r.speed = 1.0 * (r.bytes[1] - r.bytes[0]) / (
                        t2 - r.timestamp)
                    r.timestamp = t2
                    r.bytes = [r.bytes[1], r.bytes[1]]

    def on_enter_tunnel(self, circuit_id, candidate, origin, payload):
        self.stats['bytes_enter'] += len(payload)

    def on_incoming_from_tunnel(self, community, circuit, origin, data):
        self.stats['bytes_returned'] += len(data)
        self.circuit_stats[circuit.circuit_id].bytes_down[1] += len(data)

    def on_exiting_from_tunnel(self, circuit_id, candidate, destination, data):
        self.stats['bytes_exit'] += len(data)

        valid = False if circuit_id not in self.proxy.circuits \
            else self.proxy.circuits[circuit_id].goal_hops == 0

        if valid:
            self.circuit_stats[circuit_id].bytes_up[-1] += len(data)

    def on_send_data(self, circuit_id, candidate, destination,
                     payload):
        self.circuit_stats[circuit_id].bytes_up[-1] += len(payload)

    def on_relay(self, from_key, to_key, direction, data):
        self.relay_stats[from_key].bytes[-1] += len(data)
        self.relay_stats[to_key].bytes[-1] += len(data)

    def _create_stats(self):
        stats = {
            'uuid': self.session_id.get_bytes_le(),
            'encryption': 0 if isinstance(self.proxy.settings.crypto, NoCrypto) else 1,
            'swift': self.download_stats,
            'bytes_enter': self.stats['bytes_enter'],
            'bytes_exit': self.stats['bytes_exit'],
            'bytes_return': self.stats['bytes_returned'],
            'broken_circuits': self.stats['broken_circuits'],
            'circuits': [
                {
                    'hops': self._circuit_cache[circuit_id].goal_hops,
                    'bytes_down': c.bytes_down_list[-1] - c.bytes_down_list[0],
                    'bytes_up': c.bytes_up_list[-1] - c.bytes_up_list[0],
                    'time': c.times[-1] - c.times[0]
                }
                for circuit_id, c in self.circuit_stats.items()
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
            self._logger.error("Sharing statistics now!")
            self.share_stats()

    def share_stats(self):
        self.proxy.send_stats(self._create_stats())


class StatsDatabase(Database):
    LATEST_VERSION = 1
    schema = u"""
        CREATE TABLE result (
            "result_id" INTEGER PRIMARY KEY AUTOINCREMENT,
            "mid" BLOB,
            "session_id" GUID,
            "time" DATETIME,
            "host" NULL,
            "port" NULL,
            "swift_size" NULL,
            "swift_time" NULL,
            "bytes_enter" NULL,
            "bytes_exit" NULL,
            "bytes_returned" NULL,
            "encryption" INTEGER NOT NULL DEFAULT ('0')
        , "broken_circuits" INTEGER);

        CREATE TABLE IF NOT EXISTS result_circuit (
            result_circuit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            result_id,
            hops,
            bytes_up,
            bytes_down,
            time
        );

        CREATE TABLE IF NOT EXISTS result_relay(
            result_relay_id INTEGER PRIMARY KEY AUTOINCREMENT,
            result_id,
            bytes,
            time
        );

        CREATE TABLE option(key TEXT PRIMARY KEY, value BLOB);
        INSERT INTO option(key, value) VALUES('database_version', '""" + str(LATEST_VERSION) + """');
    """

    if __debug__:
        __doc__ = schema

    def __init__(self, dispersy):
        self._dispersy = dispersy

        super(StatsDatabase, self).__init__(os.path.join(dispersy.working_directory, u"anontunnel.db"))

    def open(self, initial_statements=True, prepare_visioning=True):
        self._dispersy.database.attach_commit_callback(self.commit)
        return super(StatsDatabase, self).open(initial_statements, prepare_visioning)

    def close(self, commit=True):
        self._dispersy.database.detach_commit_callback(self.commit)
        return super(StatsDatabase, self).close(commit)

    def check_database(self, database_version):
        assert isinstance(database_version, unicode)
        assert database_version.isdigit()
        assert int(database_version) >= 0
        database_version = int(database_version)

        # setup new database with current database_version
        if database_version < 1:
            self.executescript(self.schema)
            self.commit()

        else:
            # upgrade to version 2
            if database_version < 2:
                # there is no version 2 yet...
                # if __debug__: dprint("upgrade database ", database_version, " -> ", 2)
                # self.executescript(u"""UPDATE option SET value = '2' WHERE key = 'database_version';""")
                # self.commit()
                # if __debug__: dprint("upgrade database ", database_version, " -> ", 2, " (done)")
                pass

        return self.LATEST_VERSION

    def add_stat(self, member, candidate, stats):
        """
        @param Member member:
        @param Candidate candidate:
        @param stats:
        """

        sock_addr = candidate.sock_addr

        self.execute(
            u'''INSERT OR FAIL INTO result
                (
                    mid, encryption, session_id, time,
                    host, port, swift_size, swift_time,
                    bytes_enter, bytes_exit, bytes_returned, broken_circuits
                )
                VALUES (?, ?, ?,DATETIME('now'),?,?,?,?,?,?,?,?)''',
            (
                buffer(member.mid),
                stats['encryption'] or 0,
                uuid.UUID(bytes_le=stats['uuid']),
                unicode(sock_addr[0]), sock_addr[1],
                stats['swift']['size'], stats['swift']['download_time'],
                stats['bytes_enter'], stats['bytes_exit'],
                (stats['bytes_return'] or 0),
                (stats['broken_circuits'] or 0)
            )
        )

        result_id = self.last_insert_rowid

        for circuit in stats['circuits']:
            self.execute(u'''
                INSERT INTO result_circuit (
                    result_id, hops, bytes_up, bytes_down, time
                ) VALUES (?, ?, ?, ?, ?)''',
                (
                   result_id, circuit['hops'],
                   circuit['bytes_up'],
                   circuit['bytes_down'],
                   circuit['time']
                ))

        for relay in stats['relays']:
            self.execute(u'''
                INSERT INTO result_relay (result_id, bytes, time)
                    VALUES (?, ?, ?)
            ''', (result_id, relay['bytes'], relay['time']))

        self.commit()

    def get_num_stats(self):
        '''
        @rtype: int
        @return: number of stats
        '''

        return self.execute(u'''
            SELECT COUNT(*)
            FROM result
        ''').fetchone()[0]


class StatsCrawler(TunnelObserver):
    """
    Stores incoming stats in a SQLite database
    @param RawServer raw_server: the RawServer instance to queue database tasks
    on
    """

    def __init__(self, dispersy, raw_server):
        TunnelObserver.__init__(self)
        self._logger = logging.getLogger(__name__)
        self._logger.warning("Running StatsCrawler")
        self.raw_server = raw_server
        self.database = StatsDatabase(dispersy)
        self.raw_server.add_task(lambda: self.database.open())

    def on_tunnel_stats(self, community, member, candidate, stats):
        self.raw_server.add_task(lambda: self.database.add_stat(member, candidate, stats))

    def get_num_stats(self):
        return self.database.get_num_stats()

    def stop(self):
        self._logger.error("Stopping crawler")
        self.raw_server.add_task(lambda: self.database.close())
