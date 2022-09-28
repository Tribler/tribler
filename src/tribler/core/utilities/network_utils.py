import logging
import random
import socket


class FreePortNotFoundError(Exception):
    pass


class NetworkUtils:
    MAX_PORT = 65535
    MAX_EPHEMERAL_PORT = MAX_PORT
    MIN_EPHEMERAL_PORT = 49152

    MAX_PORT_FOR_TRIBLER = 32768
    MIN_PORT_FOR_TRIBLER = 1024

    def __init__(self, socket_class_set=None, remember_checked_ports_enabled=False):
        """

        Args:
            socket_class_set: a set of sockets that will be used for checkings
                port availability. A port is considered free only in case that
                it is free in all sockets from `socket_class_set`
            remember_checked_ports_enabled: a flag that enables or disables
                remembering returned ports. If it is set to true, then
                a particular port will be returned only once.
        """
        if socket_class_set is None:
            socket_class_set = {
                lambda: socket.socket(socket.AF_INET, socket.SOCK_STREAM),  # tcp
                lambda: socket.socket(socket.AF_INET, socket.SOCK_DGRAM),  # udp
            }

        self.socket_class_set = socket_class_set
        self.remember_checked_ports_enabled = remember_checked_ports_enabled

        self.logger = logging.getLogger(self.__class__.__name__)
        self.random_instance = random.Random()
        self.ports_in_use = set()

    def not_in_use(self, port):
        return port not in self.ports_in_use

    def get_first_free_port(self, start=MIN_EPHEMERAL_PORT, stop=MAX_PORT):
        self.logger.info(f'Looking for first free port in range [{start}..{stop}]')

        for port in range(start, stop):
            if self.not_in_use(port) and self.is_port_free(port):
                self.logger.info(f'{port} is free')
                return self.remember(port)

            self.logger.info(f'{port} in use')

        raise FreePortNotFoundError(f'Free port not found in range [{start}..{stop}]')

    def get_random_free_port(self, start=MIN_EPHEMERAL_PORT, stop=MAX_EPHEMERAL_PORT, attempts=100):
        start = max(0, start)
        stop = min(NetworkUtils.MAX_PORT, stop)

        self.logger.info(f'Looking for random free port in range [{start}..{stop}]')

        for _ in range(attempts):
            port = self.random_instance.randint(start, stop)
            if self.not_in_use(port) and self.is_port_free(port):
                self.logger.info(f'{port} is free')
                return self.remember(port)

            self.logger.info(f'{port} in use')

        raise FreePortNotFoundError(f'Free port not found in range [{start}..{stop}]')

    def is_port_free(self, port):
        try:
            for socket_class in self.socket_class_set:
                with socket_class() as s:
                    s.bind(('', port))
            return True
        except OSError:
            return False

    def remember(self, port):
        if self.remember_checked_ports_enabled:
            self.ports_in_use.add(port)

        return port


default_network_utils = NetworkUtils(remember_checked_ports_enabled=True)
