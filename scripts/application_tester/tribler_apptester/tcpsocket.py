import logging
from asyncio import open_connection, ensure_future
from base64 import b64decode


class TriblerCodeClient(object):

    def __init__(self, host, port, executor):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.host = host
        self.port = port
        self.executor = executor
        self.buffer = b''
        self.reader = None
        self.writer = None
        self.connected = False

    async def connect(self):
        self.reader, self.writer = await open_connection(self.host, self.port)  # can rise ConnectionRefusedError
        self.connected = True
        self._logger.info("Code socket opened!")
        ensure_future(self.read_loop())

    async def read_loop(self):
        while True:
            try:
                data = await self.reader.readline()
            except ConnectionResetError:
                break

            if not data:
                break
            self.data_received(data)

    def data_received(self, data):
        """
        We received some data from Tribler. Parse it and handle it.
        """
        self.buffer = b''
        for line in data.split(b'\n'):
            if not line.startswith(b'result') and not line.startswith(b'crash'):
                self.buffer += line
            else:
                self.process_response(self.buffer)
                self.buffer = line

        self.process_response(self.buffer)

    def process_response(self, data):
        if data.startswith(b'result'):
            parts = data.split(b' ')
            if len(parts) != 3:
                return
            result_value = b64decode(parts[1])
            task_id = parts[2]
            self.executor.on_task_result(task_id, result_value)
        elif data.startswith(b'crash '):
            parts = data.split(b' ')
            if len(parts) != 2:
                self._logger.error("Icorrect crash data received: %r" % data)
                return
            traceback = b64decode(parts[1])
            self.executor.on_tribler_crash(traceback)

    def run_code(self, code, task_id):
        if self.writer is None:
            self._logger.error("Writer is not available")
            return

        self.writer.write(b"%s %s\n" % (code, task_id))
