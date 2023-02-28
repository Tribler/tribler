from __future__ import annotations

from asyncio import Future
from typing import TYPE_CHECKING

from ipv8.requestcache import RandomNumberCache

from tribler.core.components.bandwidth_accounting.db.transaction import BandwidthTransactionData

if TYPE_CHECKING:
    from tribler.core.components.bandwidth_accounting.community.bandwidth_accounting_community import \
        BandwidthAccountingCommunity


class BandwidthTransactionSignCache(RandomNumberCache):
    """
    This cache keeps track of pending bandwidth transaction signature requests.
    """

    def __init__(self, community: BandwidthAccountingCommunity, transaction: BandwidthTransactionData) -> None:
        """
        Initialize the cache.
        :param community: The bandwidth community associated with this cache.
        :param transaction: The transaction that will be signed by the counterparty.
        """
        super().__init__(community.request_cache, "bandwidth-tx-sign")
        self.transaction = transaction
        self.future = Future()
        self.register_future(self.future)

    @property
    def timeout_delay(self) -> float:
        """
        :return The timeout of this sign cache, defaults to one hour.
        """
        return 3600.0

    def on_timeout(self) -> None:
        """
        Invoked when the cache times out.
        """
        self._logger.info("Sign request for transaction %s timed out!", self.transaction)
