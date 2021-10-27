import logging
import logging.config
import os
import sys
from pathlib import Path

import yaml


# note: this class is used by src/tribler-common/tribler_common/logger/config.yaml
class InfoFilter(logging.Filter):
    def filter(self, rec):
        return rec.levelno == logging.INFO


# note: this class is used by src/tribler-common/tribler_common/logger/config.yaml
class ErrorFilter(logging.Filter):
    def filter(self, rec):
        return rec.levelno == logging.ERROR


def setup_logging(config_path='config.yaml', module='core', log_dir='LOG_DIR'):
    """
    Setup logging configuration with the given YAML file.
    """
    if os.path.exists(config_path):
        with open(config_path) as f:
            try:
                # Update the log file paths in the config
                config_text = f.read()
                module_info_log_file = Path(log_dir).joinpath(f"{module}-info.log")
                module_error_log_file = Path(log_dir).joinpath(f"{module}-error.log")
                config_text = config_text.replace('TRIBLER_INFO_LOG_FILE', str(module_info_log_file))
                config_text = config_text.replace('TRIBLER_ERROR_LOG_FILE', str(module_error_log_file))

                # Create log directory if it does not exist
                if not Path(log_dir).exists():
                    Path(log_dir).mkdir(parents=True)

                config = yaml.safe_load(config_text)
                logging.config.dictConfig(config)
            except Exception as e:
                print('Error in loading logger config. Using default configs. Error:', e)
                logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    else:
        print(f'Logger config not found in {config_path}. Using default configs.')
        logging.basicConfig(level=logging.INFO, stream=sys.stdout)
