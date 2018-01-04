import logging
import os

import datetime
import psutil
from meliae import scanner
from twisted.web import http, resource

from Tribler.community.tunnel.tunnel_community import TunnelCommunity
from Tribler.Core.Utilities.instrumentation import WatchDog
import Tribler.Core.Utilities.json_util as json


class DebugEndpoint(resource.Resource):
    """
    This endpoint is responsible for handing requests regarding debug information in Tribler.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)

        child_handler_dict = {"circuits": DebugCircuitsEndpoint, "open_files": DebugOpenFilesEndpoint,
                              "open_sockets": DebugOpenSocketsEndpoint, "threads": DebugThreadsEndpoint,
                              "cpu": DebugCPUEndpoint, "memory": DebugMemoryEndpoint,
                              "log": DebugLogEndpoint}

        for path, child_cls in child_handler_dict.iteritems():
            self.putChild(path, child_cls(session))


class DebugCircuitsEndpoint(resource.Resource):
    """
    This class handles requests regarding the tunnel community debug information.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

    def get_tunnel_community(self):
        """
        Search for the tunnel community in the dispersy communities.
        """
        for community in self.session.get_dispersy_instance().get_communities():
            if isinstance(community, TunnelCommunity):
                return community
        return None

    def render_GET(self, request):
        """
        .. http:get:: /debug/circuits

        A GET request to this endpoint returns information about the built circuits in the tunnel community.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/debug/circuits

            **Example response**:

            .. sourcecode:: javascript

                {
                    "circuits": [{
                        "id": 1234,
                        "state": "EXTENDING",
                        "goal_hops": 4,
                        "bytes_up": 45,
                        "bytes_down": 49,
                        "created": 1468176257,
                        "hops": [{
                            "host": "unknown"
                        }, {
                            "host": "39.95.147.20:8965"
                        }],
                        ...
                    }, ...]
                }
        """
        tunnel_community = self.get_tunnel_community()
        if not tunnel_community:
            request.setResponseCode(http.NOT_FOUND)
            return json.dumps({"error": "tunnel community not found"})

        circuits_json = []
        for circuit_id, circuit in tunnel_community.circuits.iteritems():
            item = {'id': circuit_id, 'state': str(circuit.state), 'goal_hops': circuit.goal_hops,
                    'bytes_up': circuit.bytes_up, 'bytes_down': circuit.bytes_down, 'created': circuit.creation_time}
            hops_array = []
            for hop in circuit.hops:
                hops_array.append({'host': 'unknown' if 'UNKNOWN HOST' in hop.host else '%s:%s' % (hop.host, hop.port)})

            item['hops'] = hops_array
            circuits_json.append(item)

        return json.dumps({'circuits': circuits_json})


class DebugOpenFilesEndpoint(resource.Resource):
    """
    This class handles request for information about open files.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

    def render_GET(self, request):
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

        return json.dumps({
            "open_files": [{"path": open_file.path, "fd": open_file.fd} for open_file in my_process.open_files()]})


class DebugOpenSocketsEndpoint(resource.Resource):
    """
    This class handles request for information about open sockets.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

    def render_GET(self, request):
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

        return json.dumps({"open_sockets": sockets})


class DebugThreadsEndpoint(resource.Resource):
    """
    This class handles request for information about threads.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

    def render_GET(self, request):
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
        return json.dumps({"threads": watchdog.get_threads_info()})


class DebugCPUEndpoint(resource.Resource):
    """
    This class handles request for information about CPU.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.putChild("history", DebugCPUHistoryEndpoint(session))


class DebugCPUHistoryEndpoint(resource.Resource):
    """
    This class handles request for information about CPU usage history.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

    def render_GET(self, request):
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
        return json.dumps({"cpu_history": self.session.lm.resource_monitor.get_cpu_history_dict()})


class DebugMemoryEndpoint(resource.Resource):
    """
    This class handles request for information about memory.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.putChild("history", DebugMemoryHistoryEndpoint(session))
        self.putChild("dump", DebugMemoryDumpEndpoint(session))


class DebugMemoryHistoryEndpoint(resource.Resource):
    """
    This class handles request for information about memory usage history.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

    def render_GET(self, request):
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
        return json.dumps({"memory_history": self.session.lm.resource_monitor.get_memory_history_dict()})


class DebugMemoryDumpEndpoint(resource.Resource):
    """
    This class handles request for dumping memory contents.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

    def render_GET(self, request):
        """
        .. http:get:: /debug/memory/dump

        A GET request to this endpoint returns a Meliae-compatible dump of the memory contents.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/debug/memory/dump

            **Example response**:

            The content of the memory dump file.
        """
        dump_file_path = os.path.join(self.session.config.get_state_dir(), 'memory_dump.json')
        scanner.dump_all_objects(dump_file_path)
        date_str = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        request.setHeader(b'content-type', 'application/json')
        request.setHeader(b'Content-Disposition', 'attachment; filename=tribler_memory_dump_%s.json' % date_str)
        content = ""
        with open(dump_file_path, 'r') as dump_file:
            content = dump_file.read()
        return content


class DebugLogEndpoint(resource.Resource):
    """
    This class handles the request for displaying the logs.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

    def render_GET(self, request):
        """
        .. http:get:: /debug/log?process=<core|gui>&max_lines=<max_lines>

        A GET request to this endpoint returns a json with content of core or gui log file & max_lines requested

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/debug/log?process=core&max_lines=5

            **Example response**:

            A JSON with content of the log file & max_lines requested, for eg.
            {
                "max_lines" : 5,
                "content" :"INFO    1506675301.76   sqlitecachedb:181   Reading database version...
                            INFO    1506675301.76   sqlitecachedb:185   Current database version is 29
                            INFO    1506675301.76   sqlitecachedb:203   Beginning the first transaction...
                            INFO    1506675301.76         upgrade:93    tribler is in the latest version,...
                            INFO    1506675302.08  LaunchManyCore:254   lmc: Starting Dispersy..."
            }

        """

        # First, flush all the logs to make sure it is written to file
        for handler in logging.getLogger().handlers:
            handler.flush()

        # Get the location of log file
        param_process = request.args['process'][0] if request.args['process'] else 'core'
        log_file_name = os.path.join(self.session.config.get_log_dir(), 'tribler-%s-info.log' % param_process)

        # Default response
        response = {'content': '', 'max_lines': 0}

        # Check if log file exists and return last requested 'max_lines' of log
        if os.path.exists(log_file_name):
            try:
                max_lines = int(request.args['max_lines'][0])
                with open(log_file_name, 'r') as log_file:
                    response['content'] = self.tail(log_file, max_lines)
                response['max_lines'] = max_lines
            except ValueError:
                with open(log_file_name, 'r') as log_file:
                    response['content'] = self.tail(log_file, 100)  # default 100 lines
                response['max_lines'] = 0

        return json.dumps(response)

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
