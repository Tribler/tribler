from pydantic import validator

from tribler_core.config.tribler_config_section import TriblerConfigSection


# pylint: disable=no-self-argument
class ResourceMonitorSettings(TriblerConfigSection):
    enabled: bool = True
    cpu_priority: int = 1
    poll_interval: int = 5
    history_size: int = 20

    @validator('cpu_priority')
    def validate_cpu_priority(cls, v):
        assert 0 <= v <= 5, 'Cpu priority must be in range [0..5]'
        return v

    @validator('poll_interval', 'history_size')
    def validate_not_less_than_one(cls, v):
        assert v >= 1, 'Value must be not less than 1'
        return v
