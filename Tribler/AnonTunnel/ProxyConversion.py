import struct

from Tribler.dispersy.conversion import BinaryConversion
from Tribler.dispersy.message import DropPacket
from Tribler.dispersy.payload import Payload

class PingPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta):
            pass

class CreatePayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, circuit_id):
            super(CreatePayload.Implementation, self).__init__(meta)
            
            self.circuit_id = circuit_id


class BreakPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, circuit_id):
            super(BreakPayload.Implementation, self).__init__(meta)

            self.circuit_id = circuit_id


class ExtendPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, circuit_id, extend_with):
            super(ExtendPayload.Implementation, self).__init__(meta)
             
            self.circuit_id = circuit_id
            self.extend_with = extend_with


class ExtendedPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, circuit_id, extended_with):
            super(ExtendedPayload.Implementation, self).__init__(meta)
             
            self.circuit_id = circuit_id
            self.extended_with = extended_with


class DataPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, circuit_id, destination, data, origin = None):
            super(DataPayload.Implementation, self).__init__(meta)
             
            self.circuit_id = circuit_id
            self.destination = destination
            self.data = data
            self.origin = origin


class ProxyConversion(BinaryConversion):
    def __init__(self, community):
        super(ProxyConversion, self).__init__(community, "\x01")
        
        self.define_meta_message(
             chr(1)
             , community.get_meta_message(u"create")
             , self._encode_createOrCreated
             , self._decode_createOrCreated)
        
        self.define_meta_message(
             chr(2)
             , community.get_meta_message(u"created")
             , self._encode_createOrCreated
             , self._decode_createOrCreated)
        
        self.define_meta_message(
             chr(3)
             , community.get_meta_message(u"extend")
             , self._encode_extend
             , self._decode_extend)
        

        self.define_meta_message(
             chr(4)
             , community.get_meta_message(u"extended")
             , self._encode_extended
             , self._decode_extended)
        
        self.define_meta_message(
             chr(5)
             , community.get_meta_message(u"data")
             , self._encode_data
             , self._decode_data)

        self.define_meta_message(
            chr(6),
            community.get_meta_message(u"break")
            , self._encode_break
            , self._decode_break
        )

        self.define_meta_message(
            chr(7),
            community.get_meta_message(u"ping")
            , self._encode_ping
            , self._decode_ping
        )

    @staticmethod
    def _encode_ping(message):
        return ''

    @staticmethod
    def _decode_ping(placeholder, offset, data):
        return offset, placeholder.meta.payload.implement()

    @staticmethod
    def _encode_break(message):
        return struct.pack("!L", message.payload.circuit_id)

    @staticmethod
    def _decode_break(placeholder, offset, data):
        if len(data) < offset + 4:
            raise DropPacket("Cannot unpack circuit_id, insufficient packet size")

        circuit_id ,= struct.unpack_from("!L", data, offset)
        offset += 4

        return offset, placeholder.meta.payload.implement(circuit_id)

    @staticmethod
    def _encode_createOrCreated(message):
        return struct.pack("!L", message.payload.circuit_id),

    @staticmethod
    def _decode_createOrCreated(placeholder, offset, data):
        if len(data) < offset + 4:
            raise DropPacket("Cannot unpack circuit_id, insufficient packet size")
        
        circuit_id ,= struct.unpack_from("!L", data, offset)
        offset += 4
    
        return offset, placeholder.meta.payload.implement(circuit_id)
    
    @staticmethod
    def _encode_extended(message):
        (host, port) = message.payload.extended_with
        return (
                struct.pack("!LL", message.payload.circuit_id, len(host))
                , host
                , struct.pack("!L", port)
                )
        
    @staticmethod
    def _encode_extend(message):
        (host, port) = message.payload.extend_with
        return (
                struct.pack("!LL", message.payload.circuit_id, len(host))
                , host
                , struct.pack("!L", port)
                )
        
    @staticmethod
    def _encode_data(message):

        if message.payload.destination is None:
            (host, port) = ("0.0.0.0", 0)
        else:
            (host, port) = message.payload.destination


        if message.payload.origin is None:
            origin = ("0.0.0.0", 0)
        else: origin = message.payload.origin

        return (
                struct.pack("!LL", message.payload.circuit_id, len(host))
                , host
                , struct.pack("!LL", port, len(origin[0]))
                , origin[0]
                , struct.pack("!L", origin[1])
                , struct.pack("!L",len(message.payload.data))
                , message.payload.data
                )
    
    @staticmethod
    def _decode_extend(placeholder, offset, data):
        if len(data) < offset + 8:
            raise DropPacket("Cannot unpack circuit_id/HostLength, insufficient packet size")
        circuit_id , host_length = struct.unpack_from("!LL", data, offset)
        offset += 8
        
        if len(data) < offset + host_length:
            raise DropPacket("Cannot unpack Host, insufficient packet size")
        host = data[offset:offset + host_length]
        offset += host_length

        if len(data) < offset + 4:
            raise DropPacket("Cannot unpack Port, insufficient packet size")
        port ,= struct.unpack_from("!L", data, offset)
        offset += 4
        
        ExtendWith = (host, port)
        
        return offset, placeholder.meta.payload.implement(circuit_id, ExtendWith)
    
    @staticmethod
    def _decode_extended(placeholder, offset, data):
        if len(data) < offset + 8:
            raise DropPacket("Cannot unpack circuit_id/HostLength, insufficient packet size")
        circuit_id , host_length = struct.unpack_from("!LL", data, offset)
        offset += 8
        
        if len(data) < offset + host_length:
            raise DropPacket("Cannot unpack Host, insufficient packet size")
        host = data[offset:offset + host_length]
        offset += host_length

        if len(data) < offset + 4:
            raise DropPacket("Cannot unpack Port, insufficient packet size")
        port ,= struct.unpack_from("!L", data, offset)
        offset += 4
        
        ExtendedWith = (host, port)
        
        return offset, placeholder.meta.payload.implement(circuit_id, ExtendedWith)
    
    @staticmethod
    def _decode_data(placeholder, offset, data):
        if len(data) < offset + 8:
            raise DropPacket("Cannot unpack circuit_id/HostLength, insufficient packet size")
        circuit_id , host_length = struct.unpack_from("!LL", data, offset)
        offset += 8
        
        if len(data) < offset + host_length:
            raise DropPacket("Cannot unpack Host, insufficient packet size")
        host = data[offset:offset + host_length]
        offset += host_length

        if len(data) < offset + 4:
            raise DropPacket("Cannot unpack Port, insufficient packet size")
        port, origin_host_length= struct.unpack_from("!LL", data, offset)
        offset += 8
        
        destination = (host, port)

        if len(data) < offset + origin_host_length:
            raise DropPacket("Cannot unpack Origin Host Length, insufficient packet size")
        origin_host = data[offset:offset + origin_host_length]
        offset += origin_host_length

        if len(data) < offset + 4:
            raise DropPacket("Cannot unpack Origin Port, insufficient packet size")
        origin_port ,= struct.unpack_from("!L", data, offset)
        offset += 4

        origin = (origin_host, origin_port)

        if origin == ("0.0.0.0",0):
            origin = None

        if len(data) < offset + 4:
            raise DropPacket("Cannot unpack Data Length, insufficient packet size")
        payload_length ,= struct.unpack_from("!L", data, offset)
        offset += 4
        
        if payload_length == 0:
            payload = None
        else:
            if len(data) < offset + payload_length:
                raise DropPacket("Cannot unpack Data, insufficient packet size")
            payload = data[offset:offset + payload_length]
            offset += payload_length
        
        return offset, placeholder.meta.payload.implement(circuit_id, destination, payload, origin)