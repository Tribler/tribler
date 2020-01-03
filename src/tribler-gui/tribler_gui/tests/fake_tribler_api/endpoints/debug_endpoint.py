import time

from aiohttp import web

from tribler_core.restapi.rest_endpoint import RESTEndpoint, RESTResponse


class DebugEndpoint(RESTEndpoint):
    def setup_routes(self):
        self.app.add_routes(
            [
                web.get('/open_files', self.get_open_files),
                web.get('/open_sockets', self.get_open_sockets),
                web.get('/threads', self.get_threads),
                web.get('/cpu/history', self.get_cpu_history),
                web.get('/memory/history', self.get_memory_history),
                web.get('/log', self.get_log),
            ]
        )

    async def get_open_files(self, _):
        return RESTResponse({"open_files": [{"path": "a/b/c.log", "fd": 3}, {"path": "d/e/f.txt", "fd": 4}]})

    async def get_open_sockets(self, _):
        return RESTResponse(
            {
                "open_sockets": [
                    {"family": 2, "status": "ESTABLISHED", "laddr": "0.0.0.0:0", "raddr": "0.0.0.0:0", "type": 30},
                    {
                        "family": 2,
                        "status": "OPEN",
                        "laddr": "127.0.0.1:1234",
                        "raddr": "134.233.89.7:3849",
                        "type": 30,
                    },
                ]
            }
        )

    async def get_threads(self, _):
        return RESTResponse(
            {
                "threads": [
                    {"thread_id": 12345, "thread_name": "fancy_thread", "frames": ['line 1', 'line 2']},
                    {"thread_id": 5653, "thread_name": "another_thread", "frames": ['line 1']},
                ]
            }
        )

    async def get_cpu_history(self, _request):
        now = time.time()
        return RESTResponse(
            {
                "cpu_history": [
                    {"time": now, "cpu": 5.3},
                    {"time": now + 5, "cpu": 10.5},
                    {"time": now + 10, "cpu": 50},
                    {"time": now + 15, "cpu": 57},
                    {"time": now + 20, "cpu": 40},
                    {"time": now + 25, "cpu": 30},
                    {"time": now + 30, "cpu": 34},
                ]
            }
        )

    async def get_memory_history(self, _):
        now = time.time()
        return RESTResponse(
            {
                "memory_history": [
                    {"time": now, "mem": 5000},
                    {"time": now + 5, "mem": 5100},
                    {"time": now + 10, "mem": 5150},
                    {"time": now + 15, "mem": 5125},
                    {"time": now + 20, "mem": 5175},
                    {"time": now + 25, "mem": 5100},
                    {"time": now + 30, "mem": 5150},
                ]
            }
        )

    async def get_log(self, _request):
        sample_logs = ''.join(["Sample log [%d]\n" % i for i in range(10)])
        return RESTResponse({"content": sample_logs, "max_lines": 10})
