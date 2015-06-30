"""
The Tunnel community package

Defines a ProxyCommunity which discovers other proxies and offers an API to
create and reserve circuits. A basic SOCKS5 server is included which reserves
circuits for its client connections and tunnels UDP packets over them back and
forth
"""

ORIGINATOR = 0
EXIT_NODE = 1
ORIGINATOR_SALT = 2
EXIT_NODE_SALT = 3
ORIGINATOR_SALT_EXPLICIT = 4
EXIT_NODE_SALT_EXPLICIT = 5

# Data circuits are supposed to end in an exit peer that allows exiting data to the outside world
CIRCUIT_TYPE_DATA = 'DATA'

# The other circuits are supposed to end in a connectable node, not allowed to exit
# anything else than dispersy messages, used for setting up end-to-end circuits
CIRCUIT_TYPE_IP = 'IP'
CIRCUIT_TYPE_RP = 'RP'
CIRCUIT_TYPE_RENDEZVOUS = 'RENDEZVOUS'

CIRCUIT_STATE_READY = 'READY'
CIRCUIT_STATE_EXTENDING = 'EXTENDING'
CIRCUIT_STATE_TO_BE_EXTENDED = 'TO_BE_EXTENDED'
CIRCUIT_STATE_BROKEN = 'BROKEN'

CIRCUIT_ID_PORT = 1024
PING_INTERVAL = 15.0
