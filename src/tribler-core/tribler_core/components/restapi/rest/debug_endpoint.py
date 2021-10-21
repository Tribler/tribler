import datetime
import logging
import os
import sys
from io import StringIO

from aiohttp import web

from aiohttp_apispec import docs

from ipv8.REST.schema import schema

from marshmallow.fields import Boolean, Float, Integer, String

import psutil

from tribler_common.osutils import get_root_state_directory

from tribler_core.components.restapi.rest.rest_endpoint import RESTEndpoint, RESTResponse
from tribler_core.utilities.instrumentation import WatchDog

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

    def __init__(self, *args, **kwargs):
        RESTEndpoint.__init__(self, *args, **kwargs)
        self.state_dir = None
        self.log_dir = None
        self.tunnel_community = None
        self.resource_monitor = None

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
            self.app.add_routes([web.get('/memory/dump', self.get_memory_dump)])

    @docs(
        tags=['Debug'],
        summary="Return information about the slots in the tunnel overlay.",
        responses={
            200: {
                'schema': schema(CircuitSlotsResponse={'slots': [
                    schema(CircuitSlot={
                        'random': Integer,
                        'competing': Integer
                    })
                ]})
            }
        }
    )
    async def get_circuit_slots(self, request):
        return RESTResponse({
            "slots": {
                "random": self.tunnel_community.random_slots,
                "competing": self.tunnel_community.competing_slots
            }
        })

    @docs(
        tags=['Debug'],
        summary="Return information about files opened by Tribler.",
        responses={
            200: {
                'schema': schema(OpenFilesResponse={'open_files': [
                    schema(OpenFile={
                        'path': String,
                        'fd': Integer
                    })
                ]})
            }
        }
    )
    async def get_open_files(self, request):
        my_process = psutil.Process()
        return RESTResponse({
            "open_files": [{"path": open_file.path, "fd": open_file.fd} for open_file in my_process.open_files()]})

    @docs(
        tags=['Debug'],
        summary="Return information about open sockets.",
        responses={
            200: {
                'schema': schema(OpenSocketsResponse={'open_sockets': [
                    schema(OpenSocket={
                        'family': Integer,
                        'status': String,
                        'laddr': String,
                        'raddr': String,
                        'type': Integer
                    })
                ]})
            }
        }
    )
    async def get_open_sockets(self, request):
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

    @docs(
        tags=['Debug'],
        summary="Return information about running threads.",
        responses={
            200: {
                'schema': schema(ThreadsResponse={'threads': [
                    schema(Thread={
                        'thread_id': Integer,
                        'thread_name': String,
                        'frames': [String]
                    })
                ]})
            }
        }
    )
    async def get_threads(self, request):
        watchdog = WatchDog()
        return RESTResponse({"threads": watchdog.get_threads_info()})

    @docs(
        tags=['Debug'],
        summary="Return information about CPU usage history.",
        responses={
            200: {
                'schema': schema(CPUHistoryResponse={'cpu_history': [
                    schema(CPUHistory={
                        'time': Integer,
                        'cpu': Float
                    })
                ]})
            }
        }
    )
    async def get_cpu_history(self, request):
        history = self.resource_monitor.get_cpu_history_dict() if self.resource_monitor else {}
        return RESTResponse({"cpu_history": history})

    @docs(
        tags=['Debug'],
        summary="Return information about memory usage history.",
        responses={
            200: {
                'schema': schema(MemoryHistoryResponse={'memory_history': [
                    schema(MemoryHistory={
                        'time': Integer,
                        'mem': Integer
                    })
                ]})
            }
        }
    )
    async def get_memory_history(self, request):
        history = self.resource_monitor.get_memory_history_dict() if self.resource_monitor else {}
        return RESTResponse({"memory_history": history})

    @docs(
        tags=['Debug'],
        summary="Return a Meliae-compatible dump of the memory contents.",
        responses={
            200: {
                'description': 'The content of the memory dump file'
            }
        }
    )
    async def get_memory_dump(self, request):
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
            dump_file_path = self.state_dir / 'memory_dump.json'
            scanner.dump_all_objects(dump_file_path)
            with open(dump_file_path) as dump_file:
                content = dump_file.read()
        date_str = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        return RESTResponse(content,
                            headers={'Content-Type', 'application/json',
                                     'Content-Disposition', 'attachment; filename=tribler_memory_dump_%s.json'
                                     % date_str})

    @docs(
        tags=['Debug'],
        summary="Return content of core or gui log file & max_lines requested.",
        parameters=[{
            'in': 'query',
            'name': 'process',
            'description': 'Specifies which log to return',
            'enum': ['core', 'gui'],
            'type': 'string',
            'required': False
        },
            {
            'in': 'query',
            'name': 'max_lines',
            'description': 'Maximum number of lines to return from the log file',
            'type': 'integer',
            'required': False
        }],
        responses={
            200: {
                'schema': schema(LogFileResponse={
                    'max_lines': Integer,
                    'content': String
                })
            }
        }
    )
    async def get_log(self, request):
        # First, flush all the logs to make sure it is written to file
        for handler in logging.getLogger().handlers:
            handler.flush()

        # Default response
        response = {'content': '', 'max_lines': 0}

        # Get the location of log file
        param_process = request.query.get('process', 'core')
        log_name = f'tribler-{param_process}-info.log'
        log_file_name = self.log_dir / log_name

        # If the log file is not present in the versioned state directory, try root state directory location
        if not log_file_name.exists():
            log_file_name = get_root_state_directory() / log_name

        # If the log file is still not found, maybe it is not created yet, then return the default response
        if not log_file_name.exists():
            return RESTResponse(response)

        # If the log file exists and return last requested 'max_lines' of log
        try:
            max_lines = int(request.query['max_lines'])
            with log_file_name.open(mode='r') as log_file:
                response['content'] = self.tail(log_file, max_lines)
            response['max_lines'] = max_lines
        except ValueError:
            with log_file_name.open(mode='r') as log_file:
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
            except OSError:  # either file is too small, or too many lines requested
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

    @docs(
        tags=['Debug'],
        summary="Return information about the state of the profiler.",
        responses={
            200: {
                'schema': schema(ProfilerStateResponse={
                    'state': (String, 'State of the profiler (STARTED or STOPPED)')
                })
            }
        }
    )
    async def get_profiler_state(self, _):
        if self.resource_monitor is None:
            return RESTResponse(status=404)
        state = "STARTED" if self.resource_monitor.profiler.is_running() else "STOPPED"
        return RESTResponse({"state": state})

    @docs(
        tags=['Debug'],
        summary="Start the profiler.",
        responses={
            200: {
                'schema': schema(StartProfilerResponse={
                    'success': Boolean
                })
            }
        }
    )
    async def start_profiler(self, _):
        self.resource_monitor.profiler.start()
        return RESTResponse({"success": True})

    @docs(
        tags=['Debug'],
        summary="Stop the profiler.",
        responses={
            200: {
                'schema': schema(StopProfilerResponse={
                    'success': Boolean
                })
            }
        }
    )
    async def stop_profiler(self, _):
        file_path = self.resource_monitor.profiler.stop()
        return RESTResponse({"success": True, "profiler_file": str(file_path)})
