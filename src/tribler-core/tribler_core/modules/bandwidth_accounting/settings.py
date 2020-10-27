from dataclasses import dataclass


@dataclass
class BandwidthAccountingSettings:
    """
    This class contains several settings related to the bandwidth accounting mechanism.
    """
    outgoing_query_interval: int = 30   # The interval at which we send out queries to other peers, in seconds.
    max_tx_returned_in_query: int = 10  # The maximum number of bandwidth transactions to return in response to a query.
