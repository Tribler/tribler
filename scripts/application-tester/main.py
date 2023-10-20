import argparse
import logging
import os
from asyncio import ensure_future, get_event_loop
from pathlib import Path

import sentry_sdk

from tribler_apptester.executor import Executor

sentry_sdk.init(
    os.environ.get('SENTRY_URL', 'https://e489691c2e214c03961e18069a71d76c@sentry.tribler.org/6'),
    traces_sample_rate=1.0,
    ignore_errors=[KeyboardInterrupt],
)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run a Tribler application test.')
    parser.add_argument('tribler_executable', metavar='path', type=str, help='the full path to the Tribler executable')
    parser.add_argument('-p', '--plain', action='store_true', help='allow plain downloads')
    parser.add_argument('-d', '--duration', default=None, type=int, help='run the Tribler application tester for a specific period of time')
    parser.add_argument('-s', '--silent', action='store_true', help='do not execute random actions')
    parser.add_argument('--codeport', default=5500, type=int, help='the port used to execute code')
    parser.add_argument('--apiport', default=52194, type=int, help='the port used by Tribler REST API')
    parser.add_argument('--monitordownloads', default=None, type=int, help='monitor the downloads with a specified interval in seconds')
    parser.add_argument('--monitorresources', default=None, type=int, help='monitor the resources with a specified interval in seconds')
    parser.add_argument('--monitoripv8', default=None, type=int, help='monitor IPv8 overlays with a specified interval in seconds')
    parser.add_argument('--magnetsfile', default=Path("tribler_apptester") / "data" / "torrent_links.txt", type=str, help='specify the location of the file with magnet links')

    # Setup logging
    logging_level = os.environ.get('APPTESTER_LOGGING_LEVEL', 'INFO')
    logging.basicConfig(level=logging_level)

    args = parser.parse_args()
    executor = Executor(args)

    loop = get_event_loop()
    coro = executor.start()
    ensure_future(coro)
    loop.run_forever()
