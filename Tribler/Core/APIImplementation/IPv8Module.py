from os import path

from Tribler.Core.APIImplementation.IPv8EndpointAdapter import IPv8EndpointAdapter
from Tribler.pyipv8.ipv8_service import IPv8
from Tribler.pyipv8.ipv8.configuration import get_default_configuration


class IPv8Module(IPv8):

    def __init__(self, mimendpoint, working_dir="."):
        config = get_default_configuration()
        config['overlays'] = []
        for key in config['keys']:
            key['file'] = path.abspath(path.join(working_dir, key['file']))
        config['keys'] = [key for key in config['keys'] if path.isdir(path.dirname(key['file']))]
        super(IPv8Module, self).__init__(config, IPv8EndpointAdapter(mimendpoint))
