from tribler_core.config.tribler_config_section import TriblerConfigSection


class GeneralSettings(TriblerConfigSection):
    version: str = ""
    log_dir: str = "log"
    version_checker_enabled: bool = True


class ErrorHandlingSettings(TriblerConfigSection):
    core_error_reporting_requires_user_consent: bool = True
