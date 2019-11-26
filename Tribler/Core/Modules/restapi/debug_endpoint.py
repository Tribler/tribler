import datetime
import logging
import os
import sys
from io import StringIO

from aiohttp import web

import psutil

from Tribler.Core.Utilities.instrumentation import WatchDog
from Tribler.Core.Modules.restapi.rest_endpoint import RESTEndpoint, RESTResponse

HAS_MELIAE = True
try:
    from meliae import scanner
except ImportError:
    HAS_MELIAE = False


class MemoryDumpBuffer(StringIO):
    """
    Meliae expects its file handle to support write(), flush() and __call__().
    The StringIO class does not support __call__(), therefore we provide this subclass.
    """

    def __call__(self, s):
        StringIO.write(self, s)


class DebugEndpoint(RESTEndpoint):
    """
    This endpoint is responsible for handing requests regarding debug information in Tribler.
    """

    def setup_routes(self):
        self.app.add_routes([web.get('/circuits/slots', self.get_circuit_slots),
                             web.get('/open_files', self.get_open_files),
                             web.get('/open_sockets', self.get_open_sockets),
                             web.get('/threads', self.get_threads),
                             web.get('/cpu/history', self.get_cpu_history),
                             web.get('/memory/history', self.get_memory_history),
                             web.get('/log', self.get_log),
                             web.get('/profiler', self.get_profiler_state),
                             web.put('/profiler', self.start_profiler),
                             web.delete('/profiler', self.stop_profiler)])
        if HAS_MELIAE:
            self.app.add_routes(web.get('/memory/dump', self.get_memory_dump))

    async def get_circuit_slots(self, request):
        """
        .. http:get:: /debug/circuits/slots

        A GET request to this endpoint returns information about the slots in the tunnel overlay.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/debug/circuits/slots

            **Example response**:

            .. sourcecode:: javascript

                {
                    "open_files": [{
                        "path": "path/to/open/file.txt",
                        "fd": 33,
                    }, ...]
                }
        """
        return RESTResponse({
            "slots": {
                "random": self.session.lm.tunnel_community.random_slots,
                "competing": self.session.lm.tunnel_community.competing_slots
            }
        })

    async def get_open_files(self, request):
        """
        .. http:get:: /debug/open_files

        A GET request to this endpoint returns information about files opened by Tribler.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/debug/open_files

            **Example response**:

            .. sourcecode:: javascript

                {
                    "open_files": [{
                        "path": "path/to/open/file.txt",
                        "fd": 33,
                    }, ...]
                }
        """
        my_process = psutil.Process()
        return RESTResponse({
            "open_files": [{"path": open_file.path, "fd": open_file.fd} for open_file in my_process.open_files()]})

    async def get_open_sockets(self, request):
        """
        .. http:get:: /debug/open_sockets

        A GET request to this endpoint returns information about open sockets.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/debug/openfiles

            **Example response**:

            .. sourcecode:: javascript

                {
                    "open_sockets": [{
                        "family": 2,
                        "status": "ESTABLISHED",
                        "laddr": "0.0.0.0:0",
                        "raddr": "0.0.0.0:0",
                        "type": 30
                    }, ...]
                }
        """
        my_process = psutil.Process()
        sockets = []
        for open_socket in my_process.connections():
            sockets.append({
                "family": open_socket.family,
                "status": open_socket.status,
                "laddr": ("%s:%d" % open_socket.laddr) if open_socket.laddr else "-",
                "raddr": ("%s:%d" % open_socket.raddr) if open_socket.raddr else "-",
                "type": open_socket.type
            })
        return RESTResponse({"open_sockets": sockets})

    async def get_threads(self, request):
        """
        .. http:get:: /debug/threads

        A GET request to this endpoint returns information about running threads.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/debug/threads

            **Example response**:

            .. sourcecode:: javascript

                {
                    "threads": [{
                        "thread_id": 123456,
                        "thread_name": "my_thread",
                        "frames": ["my_frame", ...]
                    }, ...]
                }
        """
        watchdog = WatchDog()
        return RESTResponse({"threads": watchdog.get_threads_info()})

    async def get_cpu_history(self, request):
        """
        .. http:get:: /debug/cpu/history

        A GET request to this endpoint returns information about CPU usage history in the form of a list.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/debug/cpu/history

            **Example response**:

            .. sourcecode:: javascript

                {
                    "cpu_history": [{
                        "time": 1504015291214,
                        "cpu": 3.4,
                    }, ...]
                }
        """
        history = self.session.lm.resource_monitor.get_cpu_history_dict() if self.session.lm.resource_monitor else {}
        return RESTResponse({"cpu_history": history})

    async def get_memory_history(self, request):
        """
        .. http:get:: /debug/memory/history

        A GET request to this endpoint returns information about memory usage history in the form of a list.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/debug/memory/history

            **Example response**:

            .. sourcecode:: javascript

                {
                    "memory_history": [{
                        "time": 1504015291214,
                        "mem": 324324,
                    }, ...]
                }
        """
        history = self.session.lm.resource_monitor.get_memory_history_dict() if self.session.lm.resource_monitor else {}
        return RESTResponse({"memory_history": history})

    async def get_memory_dump(self, request):
        """
        .. http:get:: /debug/memory/dump

        A GET request to this endpoint returns a Meliae-compatible dump of the memory contents.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/debug/memory/dump

            **Example response**:

            The content of the memory dump file.
        """
        content = ""
        if sys.platform == "win32":
            # On Windows meliae (especially older versions) segfault on writing to file
            dump_buffer = MemoryDumpBuffer()
            try:
                scanner.dump_all_objects(dump_buffer)
            except OverflowError as e:
                # https://bugs.launchpad.net/meliae/+bug/569947
                logging.error("meliae dump failed (your version may be too old): %s", str(e))
            content = dump_buffer.getvalue()
            dump_buffer.close()
        else:
            # On other platforms, simply writing to file is much faster
            dump_file_path = os.path.join(self.session.config.get_state_dir(), 'memory_dump.json')
            scanner.dump_all_objects(dump_file_path)
            with open(dump_file_path, 'r') as dump_file:
                content = dump_file.read()
        date_str = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        return RESTResponse(content,
                            headers={'Content-Type', 'application/json',
                                     'Content-Disposition', 'attachment; filename=tribler_memory_dump_%s.json'
                                     % date_str})

    async def get_log(self, request):
        """
        .. http:get:: /debug/log?process=<core|gui>&max_lines=<max_lines>

        A GET request to this endpoint returns a json with content of core or gui log file & max_lines requested

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/debug/log?process=core&max_lines=5

            **Example response**:

            A JSON with content of the log file & max_lines requested, for eg.

            .. sourcecode:: javascript

                {
                    "max_lines" : 5,
                    "content" :"INFO    1506675301.76   sqlitecachedb:181   Reading database version...
                                INFO    1506675301.76   sqlitecachedb:185   Current database version is 29
                                INFO    1506675301.76   sqlitecachedb:203   Beginning the first transaction...
                                INFO    1506675301.76         upgrade:93    tribler is in the latest version,...
                                INFO    1506675302.08  LaunchManyCore:254   lmc: Starting IPv8..."
                }
        """

        # First, flush all the logs to make sure it is written to file
        for handler in logging.getLogger().handlers:
            handler.flush()

        # Get the location of log file
        param_process = request.query.get('process', 'core')
        log_file_name = os.path.join(self.session.config.get_log_dir(), 'tribler-%s-info.log' % param_process)

        # Default response
        response = {'content': '', 'max_lines': 0}

        # Check if log file exists and return last requested 'max_lines' of log
        if os.path.exists(log_file_name):
            try:
                max_lines = int(request.query['max_lines'])
                with open(log_file_name, 'r') as log_file:
                    response['content'] = self.tail(log_file, max_lines)
                response['max_lines'] = max_lines
            except ValueError:
                with open(log_file_name, 'r') as log_file:
                    response['content'] = self.tail(log_file, 100)  # default 100 lines
                response['max_lines'] = 0

        return RESTResponse(response)

    def tail(self, file_handler, lines=1):
        """Tail a file and get X lines from the end"""
        # place holder for the lines found
        lines_found = []
        byte_buffer = 1024

        # block counter will be multiplied by buffer
        # to get the block size from the end
        block_counter = -1

        # loop until we find X lines
        while len(lines_found) < lines:
            try:
                file_handler.seek(block_counter * byte_buffer, os.SEEK_END)
            except IOError:  # either file is too small, or too many lines requested
                file_handler.seek(0)
                lines_found = file_handler.readlines()
                break

            lines_found = file_handler.readlines()

            # we found enough lines, get out
            if len(lines_found) > lines:
                break

            # decrement the block counter to get the
            # next X bytes
            block_counter -= 1

        return ''.join(lines_found[-lines:])

    async def get_profiler_state(self, request):
        """
        .. http:get:: /debug/profiler

        A GET request to this endpoint returns information about the state of the profiler.
        This state is either STARTED or STOPPED.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/debug/profiler

            **Example response**:

            .. sourcecode:: javascript

                {
                    "state": "STARTED"
                }
        """
        monitor_enabled = self.session.config.get_resource_monitor_enabled()
        state = "STARTED" if (monitor_enabled and self.session.lm.resource_monitor.profiler_running) else "STOPPED"
        return RESTResponse({"state": state})

    async def start_profiler(self, request):
        """
        .. http:put:: /debug/profiler

        A PUT request to this endpoint starts the profiler.

            **Example request**:

            .. sourcecode:: none

                curl -X PUT http://localhost:8085/debug/profiler

            **Example response**:

            .. sourcecode:: javascript

                {
                    "success": "true"
                }
        """
        self.session.lm.resource_monitor.start_profiler()
        return RESTResponse({"success": True})

    async def stop_profiler(self, request):
        """
        .. http:delete:: /debug/profiler

        A PUT request to this endpoint stops the profiler.

            **Example request**:

            .. sourcecode:: none

                curl -X DELETE http://localhost:8085/debug/profiler

            **Example response**:

            .. sourcecode:: javascript

                {
                    "success": "true"
                }
        """
        file_path = self.session.lm.resource_monitor.stop_profiler()
        return RESTResponse({"success": True, "profiler_file": file_path})
