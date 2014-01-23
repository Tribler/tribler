import logging

from AES import AESencode, AESdecode
from Tribler.community.anontunnel.globals import MESSAGE_CREATED, ORIGINATOR, ENDPOINT, MESSAGE_CREATE


logger = logging.getLogger(__name__)


class NoCrypto(object):
    def enable(self, proxy):
        pass


class DefaultCrypto(object):
    def __init__(self):
        self.proxy = None
        self.session_keys = {}

    def enable(self, proxy):

        """
        :type proxy: Tribler.community.anontunnel.community.ProxyCommunity
        :param proxy:
        """
        self.proxy = proxy

        proxy.add_relay_transformer(self._crypto_relay)
        proxy.add_receive_transformer(self._crypto_incoming)
        proxy.add_send_transformer(self._crypto_outgoing)
        proxy.add_message_filter(MESSAGE_CREATE, self._on_create)

    def _on_create(self, candidate, circuit_id, payload):
        return payload

    def _crypto_outgoing(self, circuit_id, message_type, content):
        if circuit_id in self.proxy.circuits:
            # I am the originator so I have to create the full onion
            circuit = self.proxy.circuits[circuit_id]
            hops = circuit.hops

            for hop in reversed(hops):
                logger.debug("Adding AES layer for hop %s:%s with key %s" % (hop.host, hop.port, hop.session_key))
                content = AESencode(hop.session_key, content)
        elif circuit_id in self.proxy.session_keys:
            if message_type == MESSAGE_CREATED:
                logger.debug("Adding public key encryption for circuit %s" % (circuit_id))
                logger.error("Still have to implement public key encryption for CREATED message")
            else:
                content = AESencode(self.proxy.session_keys[circuit_id], content)
                logger.debug(
                    "Adding AES layer for circuit %s with key %s" % (circuit_id, self.session_keys[circuit_id]))

        return content

    def _crypto_relay(self, direction, candidate, circuit_id, data):
        relay_key = (candidate, circuit_id)
        next_relay = self.proxy.relay_from_to[relay_key]

        if direction == ORIGINATOR:
            # Message is going downstream so I have to add my onion layer
            # logger.debug("Adding AES layer with key %s to circuit %d" % (self.session_keys[next_relay.circuit_id], next_relay.circuit_id))
            data = AESencode(self.proxy.session_keys[next_relay.circuit_id], data)

        elif direction == ENDPOINT:
            # Message is going upstream so I have to remove my onion layer
            # logger.debug("Removing AES layer with key %s" % self.session_keys[circuit_id])
            data = AESdecode(self.proxy.session_keys[circuit_id], data)

        return data

    def _crypto_incoming(self, candidate, circuit_id, data):
        if circuit_id in self.proxy.circuits:
            # I am the originator so I'll peel the onion skins
            for hop in self.proxy.circuits[circuit_id].hops:
                logger.debug("Removing AES layer for %s:%s with key %s" % (hop.host, hop.port, hop.session_key))
                data = AESdecode(hop.session_key, data)

        elif circuit_id in self.proxy.session_keys:
            # last node in circuit, circuit already exists
            logger.debug("Removing AES layer with key %s" % (self.proxy.session_keys[circuit_id]))
            data = AESdecode(self.proxy.session_keys[circuit_id], data)
        else:
            # last node in circuit, circuit does not exist yet
            data = data

        return data

