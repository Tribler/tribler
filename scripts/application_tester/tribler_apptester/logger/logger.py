import logging
import os

import colorlog


def init_logger():
    logging_level = os.environ.get('APPTESTER_LOGGING_LEVEL', 'INFO')

    handler = colorlog.StreamHandler()
    handler.setFormatter(colorlog.ColoredFormatter('%(log_color)s%(levelname)s - %(name)s(%(lineno)d): %(message)s'))
    logging.basicConfig(level=logging_level, handlers=[handler])
