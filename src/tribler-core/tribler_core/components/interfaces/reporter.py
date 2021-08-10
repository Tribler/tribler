from tribler_core.components.base import Component, testcomponent
from tribler_core.config.tribler_config import TriblerConfig

class ReporterComponent(Component):
    enable_in_gui_test_mode = True

    user_id_str: str

    @classmethod
    def should_be_enabled(cls, config: TriblerConfig):
        return True

    @classmethod
    def make_implementation(cls, config: TriblerConfig, enable: bool):
        if enable:
            from tribler_core.components.implementation.reporter import ReporterComponentImp
            return ReporterComponentImp(cls)
        return ReporterComponentMock(cls)


@testcomponent
class ReporterComponentMock(ReporterComponent):
    user_id_str = 'user_id'
