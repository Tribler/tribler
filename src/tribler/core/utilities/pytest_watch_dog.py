import logging
import threading
import time
from datetime import datetime, timedelta

import human_readable

from tribler.core.components.restapi.rest.utils import print_threads_info

TEST_TIMEOUT_SECONDS = 15

event_new_test = threading.Event()

_logger = logging.Logger('PytestWatchDog')


def watch_dog_thread():
    last_time = datetime.now()
    enable_print = False

    while True:
        time.sleep(1)
        if event_new_test.is_set():
            event_new_test.clear()
            last_time = datetime.now()
            enable_print = True

        duration = datetime.now() - last_time
        if enable_print and duration > timedelta(seconds=TEST_TIMEOUT_SECONDS):
            _logger.warning(f'Watch Dog: Long duration detected: {human_readable.time_delta(duration)}')
            print_threads_info()
            enable_print = False


def start_watch_dog():
    _logger.info('Enable watch dog')
    thread = threading.Thread(target=watch_dog_thread, daemon=True)
    thread.start()
