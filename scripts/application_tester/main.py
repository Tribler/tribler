import argparse
import asyncio
import os
from asyncio import ensure_future, get_event_loop
from pathlib import Path

import sentry_sdk

from tribler.core.utilities.utilities import make_async_loop_fragile
from tribler_apptester.executor import Executor
from tribler_apptester.logger.logger import init_logger

sentry_sdk.init(
    os.environ.get('APPLICATION_TESTER_SENTRY_DSN'),
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
    parser.add_argument('--monitordownloads', default=None, type=int, help='monitor the downloads with a specified interval in seconds')
    parser.add_argument('--monitorresources', default=None, type=int, help='monitor the resources with a specified interval in seconds')
    parser.add_argument('--monitoripv8', default=None, type=int, help='monitor IPv8 overlays with a specified interval in seconds')
    parser.add_argument('--fragile', '-f', help='Fail at the first error', action='store_true')

    init_logger()

    args = parser.parse_args()

    loop = asyncio.get_event_loop()
    executor_kwargs = {}
    if args.fragile:
        make_async_loop_fragile(loop)

        # Modify the base logic of the Executor to quickly receive feedback from the Application Tester.
        # This feature is employed in PR tests when we aim to assess potential disruptions in script logic due
        # to changes within Tribler.
        executor_kwargs['read_config_delay'] = 0
        executor_kwargs['read_config_attempts'] = 1
        executor_kwargs['check_process_started_interval'] = 1

    executor = Executor(args, **executor_kwargs)

    loop = get_event_loop()
    coro = executor.start()
    ensure_future(coro)
    loop.run_forever()
