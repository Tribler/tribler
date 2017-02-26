"""
Definitions for RPC calls (see rpcprocess.py)

Response codes:
* RPC_RESPONSE_OK: Report error-free execution
* RPC_RESPONSE_ERR: Report that an error occurred

RPC calls:
* RPC_CREATE: Create/set-up the TunnelCommunity
* RPC_NOTIFY: Forward a notification
* RPC_SYNC: Synchronize a SyncDict
* RPC_MONITOR: Call for a monitor_downloads
* RPC_CIRCUIT: Try creating a circuit with create_circuit
* RPC_CIRDEAD: Forward that a circuit has died
"""

RPC_RESPONSE_OK = chr(0)
RPC_RESPONSE_ERR = chr(1)

RPC_CREATE = "CREATE"
RPC_NOTIFY = "NOTIFY"
RPC_SYNC = "SYNC"
RPC_MONITOR = "MONITOR"
RPC_CIRCUIT = "CIRCUIT"
RPC_CIRDEAD = "CIRDEAD"
