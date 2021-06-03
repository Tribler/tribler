import logging
import random
import socket


class FreePortNotFoundError(Exception):
    pass


class NetworkUtils:
    MAX_PORT = 65535
    FIRST_PORT_IN_DYNAMIC_RANGE = 49152

    def __init__(self, socket_class_set=None):
        if socket_class_set is None:
            socket_class_set = {
                lambda: socket.socket(socket.AF_INET, socket.SOCK_STREAM),  # tcp
                lambda: socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # udp
            }

        self.socket_class_set = socket_class_set
        self.logger = logging.getLogger(self.__class__.__name__)

    def get_first_free_port(self, start=FIRST_PORT_IN_DYNAMIC_RANGE, stop=MAX_PORT):
        self.logger.info(f'Looking for first free port in range [{start}..{stop}]')

        for port in range(start, stop):
            if self.is_port_free(port):
                self.logger.info(f'{port} is free')
                return port

            self.logger.info(f'{port} in use')

        raise FreePortNotFoundError(f'Free port not found in range [{start}..{stop}]')

    def get_random_free_port(self, start=FIRST_PORT_IN_DYNAMIC_RANGE, stop=MAX_PORT, attempts=100):
        start = max(0, start)
        stop = min(NetworkUtils.MAX_PORT, stop)

        self.logger.info(f'Looking for random free port in range [{start}..{stop}]')

        for _ in range(attempts):
            port = random.randint(start, stop)
            if self.is_port_free(port):
                self.logger.info(f'{port} is free')
                return port

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
