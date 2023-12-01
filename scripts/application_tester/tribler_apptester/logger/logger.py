import logging
import os

import colorlog

log_colors = {
    'DEBUG': 'white',
    'INFO': 'white',
}


def init_logger():
    logging_level = os.environ.get('APPTESTER_LOGGING_LEVEL', 'INFO')

    handler = colorlog.StreamHandler()
    handler.setFormatter(colorlog.ColoredFormatter('%(log_color)s%(levelname)s - %(name)s(%(lineno)d): %(message)s',
                                                   log_colors=log_colors))
    logging.basicConfig(level=logging_level, handlers=[handler])
