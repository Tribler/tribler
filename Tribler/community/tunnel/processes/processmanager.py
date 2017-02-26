import logging
import os
import shutil
from multiprocessing import cpu_count
from random import sample

from twisted.internet.defer import DeferredList, inlineCallbacks, returnValue

from Tribler.community.tunnel.processes.tunnel_childprocess import TunnelProcess


class ProcessManager(object):

    """
    The ProcessManager creates and manages ChildProcesses
    """

    def __init__(self, session, community=None):
        """
        Create a new ProcessManager

        :param session: the session to extract info from
        :type session: Tribler.Core.Session.Session
        :param community: (non-Session) community to report to
        :type community: Tribler.dispersy.community.Community
        :returns: None
        """
        super(ProcessManager, self).__init__()

        self.pool = {}          # Map of pid -> Process
        self.circuit_map = {}   # Map of circuit -> pid
        self.session = session
        self.community = community

        self._clean_working_dir()

    def _clean_working_dir(self):
        """
        Clean leftover directories from crashed/terminated processes

        :returns: None
        """
        for directory in [x[0] for x in os.walk(self.session.get_state_dir())]:
            if os.path.split(directory)[1].startswith("tunnel_subprocess"):
                logging.error("Cleaning up leftover subprocess artifacts in " + directory)
                try:
                    shutil.rmtree(directory)
                except OSError:
                    logging.error("Failed to clean leftover subprocess directory " + directory)

    def get_suggested_workers(self):
        """
        Have the process manager suggest a number of workers to use

        :return: the suggested amount of workers
        :rtype: int
        """
        return cpu_count()

    def set_worker_count(self, value):
        """
        Set the amount of workers to use

        :param value: the new amount of workers
        :returns: None
        """
        count = self.get_worker_count()
        if count < value:
            # We have too little workers, create more
            return [self._create_worker() for _ in xrange(value - count)]
        elif count > value:
            # We have too many workers, remove some
            return self._remove_workers(max(count - value, count))

    def get_worker_count(self):
        """
        Return the active amount of workers

        :return: the current worker count
        :rtype: int
        """
        return len(self.pool.keys())

    def _create_worker(self):
        """
        Create a single worker and add it to the pool

        :return: the deferred for when the process has started
        :rtype: twisted.internet.defer.Deferred
        """
        key_pair = self.session.get_multichain_permid_keypair_filename()
        is_exit_node = self.session.get_tunnel_community_exitnode_enabled()

        process = TunnelProcess(self.community if self.community
                                else self.session.lm.tunnel_community)

        def on_created(proc):
            self.pool[proc.pid] = proc
            proc.create(key_pair, is_exit_node)
        process.started.addCallback(on_created)

        return process.started

    def _remove_workers(self, amount):
        """
        Remove some amount of workers

        :param amount: the amount of workers to remove
        :type amount: int
        :returns: None
        """
        to_remove = sample(self.pool.keys(), amount)
        waiters = []
        for worker in to_remove:
            waiters.append(self.pool[worker].end())
            self.pool.pop(worker)
        self.circuit_map = {
            k:v for k, v in self.circuit_map.iteritems()
            if v in to_remove}
        return DeferredList(waiters)

    def monitor_infohashes(self, infohashes):
        """
        Call monitor_infohashes on all workers in the pool

        :param infohashes: the infohashes the workers need to monitor
        :type infohashes: [(str, int, int)]
        :returns: None
        """
        for worker in self.pool.values():
            worker.monitor_infohashes(infohashes)

    def send_data(self, candidates, circuit_id, dest_address,
                  source_address, data):
        """
        Call send_data() on the worker assigned to circuit_id

        :param candidates: the candidates to use
        :type candidates: Tribler.dispersy.candidate.Candidate
        :param circuit_id: the circuit id to send over
        :type circuit_id: long
        :param dest_address: the destination address to send to
        :type dest_address: (str, int)
        :param source_address: the source address to send from
        :type source_address: (str, int)
        :param data: the data to send
        :type data: str
        :returns: None
        """
        if circuit_id in self.circuit_map:
            worker_id = self.circuit_map[circuit_id]
            if worker_id not in self.pool:
                logging.warning("Could not find worker with pid " + str(worker_id)
                                + " (probably shutting down)")
                return
            worker = self.pool[worker_id]
            worker.send_data([cd.sock_addr for cd in candidates],
                             circuit_id,
                             dest_address,
                             source_address,
                             data)
        else:
            logging.warning("Could not find worker registered for " +
                            str(circuit_id) + ", trying anyway")
            for worker in self.pool.values():
                worker.send_data([cd.sock_addr for cd in candidates],
                                 circuit_id,
                                 dest_address,
                                 source_address,
                                 data)

    @inlineCallbacks
    def create_circuit(self, goal_hops, ctype, required_endpoint,
                       info_hash):
        """
        Try to create a circuit on any worker which will accept it

        :param goal_hops: the hop count in the circuit
        :type goal_hops: int
        :param ctype: type of circuit to create
        :type ctype: str
        :param required_endpoint: the endpoint to use
        :type required_endpoint: (str, int ,str)
        :param info_hash: the infohash to assign to this circuit
        :type info_hash: str
        :return: the newly created circuit id or False
        :rtype: long or False
        """
        circuit_id = False
        for worker in sorted(self.pool,
                             key=lambda x: (
                                 self.circuit_map.values().count(x))):
            if worker not in self.pool:
                logging.warning("Could not find worker with pid " + str(worker)
                                + " (probably shutting down)")
                continue
            circuit_id = yield self.pool[worker].create_circuit(goal_hops,
                                                                ctype,
                                                                required_endpoint,
                                                                info_hash)

            if circuit_id:
                self.circuit_map[circuit_id] = worker
                break
        returnValue(circuit_id)
