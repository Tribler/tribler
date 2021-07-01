from ipv8.configuration import ConfigBuilder


class Ipv8Config:
    """Extracted from session.py"""

    def __init__(self, state_dir=None, config=None):
        self.value = (ConfigBuilder()
                      .set_port(config.port())
                      .set_address(config.address())
                      .clear_overlays()
                      .clear_keys()  # We load the keys ourselves
                      .set_working_directory(str(state_dir))
                      .set_walker_interval(config.walk_interval())
                      .finalize())
