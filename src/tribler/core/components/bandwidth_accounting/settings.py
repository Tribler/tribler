from pydantic import Field

from tribler_core.config.tribler_config_section import TriblerConfigSection


class BandwidthAccountingSettings(TriblerConfigSection):
    testnet: bool = Field(default=False, env='BANDWIDTH_TESTNET')
    outgoing_query_interval: int = 30  # The interval at which we send out queries to other peers, in seconds.
    max_tx_returned_in_query: int = 10  # The maximum number of bandwidth transactions to return in response to a query.
