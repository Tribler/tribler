"""
The AnonTunnel community package

Defines a ProxyCommunity which discovers other proxies and offers an API to
create and reserve circuits. A basic SOCKS5 server is included which reserves
circuits for its client connections and tunnels UDP packets over them back and
forth
"""