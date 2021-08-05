from tribler_core.components.base import Component


class ReporterComponent(Component):
    core = True

    @classmethod
    def should_be_enabled(cls, config):
        return True

    @classmethod
    def make_implementation(cls, config, enable):
        from tribler_core.components.implementation.reporter import ReporterComponentImp
        return ReporterComponentImp()
