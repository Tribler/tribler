from Tribler.Core.APIImplementation.IPv8EndpointAdapter import IPv8EndpointAdapter
from Tribler.pyipv8.ipv8_service import IPv8
from Tribler.pyipv8.ipv8.configuration import get_default_configuration


class IPv8Module(IPv8):

    def __init__(self, mimendpoint):
        config = get_default_configuration()
        config['overlays'] = []
        super(IPv8Module, self).__init__(config, IPv8EndpointAdapter(mimendpoint))
