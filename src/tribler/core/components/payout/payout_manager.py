import logging

from ipv8.taskmanager import TaskManager, task

from tribler.core.utilities.unicode import hexlify


class PayoutManager(TaskManager):
    """
    This manager is responsible for keeping track of known Tribler peers and doing (zero-hop) payouts.
    """

    def __init__(self, bandwidth_community, dht):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.bandwidth_community = bandwidth_community
        self.dht = dht
        self.tribler_peers = {}

    def on_peer_disconnected(self, peer_id: bytes):
        # do_payout is not specified directly, as PyCharm does not understand its type correctly due to a task decorator
        self.do_payout(peer_id)

    @task
    async def do_payout(self, peer_id: bytes):
        """
        Perform a payout to a given mid. First, determine the outstanding balance. Then resolve the node in the DHT.
        """
        if peer_id not in self.tribler_peers:
            return None

        total_bytes = sum(self.tribler_peers[peer_id].values())

        self.logger.info("Doing direct payout to %s (%d bytes)", hexlify(peer_id), total_bytes)
        try:
            nodes = await self.dht.connect_peer(peer_id)
        except Exception as e:
            self.logger.warning("Error while doing DHT lookup for payouts, error %s", e)
            return None

        self.logger.debug("Received %d nodes for DHT lookup", len(nodes))
        if not nodes:
            return None

        try:
            await self.bandwidth_community.do_payout(nodes[0], total_bytes)
        except Exception as e:
            self.logger.error("Error while doing bandwidth payout, error %s", e)
            return None

        # Remove the outstanding bytes; otherwise we will payout again
        self.tribler_peers.pop(peer_id, None)
        return nodes[0]

    def update_peer(self, peer_id: bytes, infohash: bytes, balance: int):
        """
        Update a peer with a specific mid for a specific infohash.
        """
        self.logger.debug("Updating peer with mid %s and ih %s (balance: %d)", hexlify(peer_id),
                          hexlify(infohash), balance)

        if peer_id not in self.tribler_peers:
            self.tribler_peers[peer_id] = {}

        self.tribler_peers[peer_id][infohash] = balance

    async def shutdown(self):
        await self.shutdown_task_manager()
