import logging
import logging.config
import sys
from pathlib import Path

import yaml

LOG_CONFIG_FILENAME = 'logger.yaml'
GREEN = "\033[32m"
CYAN = "\033[36m"
logger = logging.getLogger(__name__)


# note: this class is used by logger.yaml
class StdoutFilter(logging.Filter):
    def filter(self, record):
        return record.levelno < logging.ERROR


log_factory = logging.getLogRecordFactory()


def load_logger_config(app_mode, log_dir, current_process_is_primary=True):
    """
    Loads tribler-gui module logger configuration. Note that this function should be called explicitly to
    enable GUI logs dump to a file in the log directory (default: inside state directory).
    """
    if current_process_is_primary:
        # Set up logging to files for primary process only, as logging module does not support
        # writing to the same log file from multiple Python processes
        logger_config_path = get_logger_config_path()
        setup_logging(app_mode, Path(log_dir), logger_config_path)
    else:
        logger.info('Skip the initialization of a normal file-based logging as the current process is non-primary.\n'
                    'Continue using the basic logging config from the boot logger initialization.\n'
                    'Only primary Tribler process can write to Tribler log files, as logging module does not support\n'
                    'writing to files from multiple Python processes.')


def get_logger_config_path():
    if not hasattr(sys, '_MEIPASS'):
        dirname = Path(__file__).absolute().parent
    else:
        dirname = Path(getattr(sys, '_MEIPASS')) / "tribler_source/tribler/core/logger"
    return dirname / LOG_CONFIG_FILENAME


def setup_logging(app_mode, log_dir: Path, config_path: Path):
    """
    Setup logging configuration with the given YAML file.
    """

    def record_factory(*args, **kwargs):
        record = log_factory(*args, **kwargs)
        record.app_mode = app_mode
        record.app_mode_color = GREEN if app_mode == 'tribler-gui' else CYAN
        return record

    logger.info(f'Load logger config: app_mode={app_mode}, config_path={config_path}, dir={log_dir}')
    if not config_path.exists():
        print(f'Logger config not found in {config_path}. Using default configs.', file=sys.stderr)
        logging.basicConfig(level=logging.INFO, stream=sys.stdout)
        return

    try:
        # Update the log file paths in the config
        module_info_log_file = log_dir.joinpath(f"{app_mode}-info.log")
        module_error_log_file = log_dir.joinpath(f"{app_mode}-error.log")

        with config_path.open() as f:
            config_text = f.read()

        config_text = config_text.replace('TRIBLER_INFO_LOG_FILE', str(module_info_log_file))
        config_text = config_text.replace('TRIBLER_ERROR_LOG_FILE', str(module_error_log_file))

        # Create log directory if it does not exist
        if not log_dir.exists():
            log_dir.mkdir(parents=True)
        config = yaml.safe_load(config_text)
        logging.config.dictConfig(config)
        logging.setLogRecordFactory(record_factory)
        logger.info(f'Config loaded for app_mode={app_mode}')
    except Exception as e:  # pylint: disable=broad-except
        error_description = format_error_description(e)
        print('Error in loading logger config. Using default configs. ', error_description, file=sys.stderr)
        logging.basicConfig(level=logging.INFO, stream=sys.stdout)


def format_error_description(e: Exception):
    result = f'{e.__class__.__name__}: {e}'
    cause = e.__cause__
    if cause:
        result += f'. Cause: {cause.__class__.__name__}: {cause}'
    return result
