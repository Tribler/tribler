import logging

from ipv8.taskmanager import TaskManager, task

from tribler_core.utilities.unicode import hexlify


class PayoutManager(TaskManager):
    """
    This manager is responsible for keeping track of known Tribler peers and doing (zero-hop) payouts.
    """

    def __init__(self, bandwidth_community, dht):
        super(PayoutManager, self).__init__()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.bandwidth_community = bandwidth_community
        self.dht = dht
        self.tribler_peers = {}

    @task
    async def do_payout(self, mid):
        """
        Perform a payout to a given mid. First, determine the outstanding balance. Then resolve the node in the DHT.
        """
        if mid not in self.tribler_peers:
            return None

        total_bytes = sum(self.tribler_peers[mid].values())

        self.logger.info("Doing direct payout to %s (%d bytes)", hexlify(mid), total_bytes)
        try:
            nodes = await self.dht.connect_peer(mid)
        except Exception as e:
            self.logger.warning("Error while doing DHT lookup for payouts, error %s", e)
            return None

        self.logger.debug("Received %d nodes for DHT lookup", len(nodes))
        if nodes:
            try:
                await self.bandwidth_community.do_payout(nodes[0], total_bytes)
            except Exception as e:
                self.logger.error("Error while doing bandwidth payout, error %s", e)
                return None

        # Remove the outstanding bytes; otherwise we will payout again
        self.tribler_peers.pop(mid, None)
        return nodes[0]

    def update_peer(self, mid, infohash, balance):
        """
        Update a peer with a specific mid for a specific infohash.
        """
        self.logger.debug("Updating peer with mid %s and ih %s (balance: %d)", hexlify(mid),
                          hexlify(infohash), balance)

        if mid not in self.tribler_peers:
            self.tribler_peers[mid] = {}

        self.tribler_peers[mid][infohash] = balance

    async def shutdown(self):
        await self.shutdown_task_manager()
