import logging
import logging.config
import sys
from pathlib import Path

import yaml

LOG_CONFIG_FILENAME = 'logger.yaml'


logger = logging.getLogger(__name__)


# note: this class is used by src/tribler-common/tribler_common/logger/config.yaml
class StdoutFilter(logging.Filter):
    def filter(self, record):
        return record.levelno < logging.ERROR


def load_logger_config(app_mode, log_dir):
    """
    Loads tribler-gui module logger configuration. Note that this function should be called explicitly to
    enable GUI logs dump to a file in the log directory (default: inside state directory).
    """
    logger_config_path = get_logger_config_path()
    setup_logging(app_mode, Path(log_dir), logger_config_path)


def get_logger_config_path():
    if not hasattr(sys, '_MEIPASS'):
        dirname = Path(__file__).absolute().parent
    else:
        dirname = Path(getattr(sys, '_MEIPASS'), "tribler_source", "tribler_common")
    return dirname / LOG_CONFIG_FILENAME


def setup_logging(app_mode, log_dir: Path, config_path: Path):
    """
    Setup logging configuration with the given YAML file.
    """
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
        logging.info(f'Config loaded for app_mode={app_mode}')
    except Exception as e:  # pylint: disable=broad-except
        print('Error in loading logger config. Using default configs. Error:', e, file=sys.stderr)
        logging.basicConfig(level=logging.INFO, stream=sys.stdout)
