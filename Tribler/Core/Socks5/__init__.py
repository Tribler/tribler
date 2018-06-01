"""
CODE REVIEW:
Twisted-Protocol based UDP SOCKS5 server partial implementation used by TunnelCommunity.
Written very cleanly. Nothing to add.

OBJECTION: should be moved to IPv8 TunnelCommunity, where it belongs.
"""


"""
The Socks5 package contains a basic SOCKS5 server is included which reserves
circuits for its client connections and tunnels UDP packets over them back and forth.
"""
