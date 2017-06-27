from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import LoopingCall

from Tribler.Core.simpledefs import NTFY_TUNNEL, NTFY_REMOVE
from Tribler.community.triblerchain.block import TriblerChainBlock
from Tribler.community.triblerchain.database import TriblerChainDB
from Tribler.community.trustchain.community import TrustChainCommunity
from Tribler.dispersy.util import blocking_call_on_reactor_thread

MIN_TRANSACTION_SIZE = 1024*1024


class PendingBytes(object):
    def __init__(self, up, down, clean=None):
        super(PendingBytes, self).__init__()
        self.up = up
        self.down = down
        self.clean = clean

    def add(self, up, down):
        if self.up + up >= 0 and self.down + down >= 0:
            self.up = max(0, self.up + up)
            self.down = max(0, self.down + down)
            if self.clean is not None:
                self.clean.reset(2 * 60)
            return True
        else:
            return False


class TriblerChainCommunity(TrustChainCommunity):
    """
    Community for reputation based on TrustChain tamper proof interaction history.
    """
    BLOCK_CLASS = TriblerChainBlock
    DB_CLASS = TriblerChainDB
    SIGN_DELAY = 5

    def __init__(self, *args, **kwargs):
        super(TriblerChainCommunity, self).__init__(*args, **kwargs)
        self.notifier = None

        # We store the bytes send and received in the tunnel community in a dictionary.
        # The key is the public key of the peer being interacted with, the value a tuple of the up and down bytes
        # This data is not used to create outgoing requests, but _only_ to verify incoming requests
        self.pending_bytes = dict()

        # Store invalid messages since one of these might contain a block that is bought on the market
        self.pending_sign_messages = {}

    @classmethod
    def get_master_members(cls, dispersy):
        # generated: Mon Jun 19 09:25:14 2017
        # curve: None
        # len: 571 bits ~ 144 bytes signature
        # pub: 170 3081a7301006072a8648ce3d020106052b81040027038192000403a4cf6036eb2a9daa0ae4bd23c1be5343c0b2d30fa85
        # da2554532e3e73ba1fde4db0c8864c7f472ce688afef5a9f7ccfe1396bb5ef09be80e00e0a5ab4814f43166d086720af10807dbb1f
        # a71c06040bb4aadc85fdffe69cdc6125f5b5f81c785f6b3fece98c5ecfa6de61432822e52a049850d11802dc1050a60f6983ac3eed
        # b8172ebc47e3cd50f1d97bfffe187b5
        # pub-sha1 1742feacab3bcc3ee8c4d7ee16d9c0b57e0bb266
        # prv-sha1 2d4025490ef949ea7347d020f09403c46222483a
        # -----BEGIN PUBLIC KEY-----
        # MIGnMBAGByqGSM49AgEGBSuBBAAnA4GSAAQDpM9gNusqnaoK5L0jwb5TQ8Cy0w+o
        # XaJVRTLj5zuh/eTbDIhkx/RyzmiK/vWp98z+E5a7XvCb6A4A4KWrSBT0MWbQhnIK
        # 8QgH27H6ccBgQLtKrchf3/5pzcYSX1tfgceF9rP+zpjF7Ppt5hQygi5SoEmFDRGA
        # LcEFCmD2mDrD7tuBcuvEfjzVDx2Xv//hh7U=
        # -----END PUBLIC KEY-----
        master_key = "3081a7301006072a8648ce3d020106052b81040027038192000403a4cf6036eb2a9daa0ae4bd23c1be5343c0b2d30f" \
                     "a85da2554532e3e73ba1fde4db0c8864c7f472ce688afef5a9f7ccfe1396bb5ef09be80e00e0a5ab4814f43166d086" \
                     "720af10807dbb1fa71c06040bb4aadc85fdffe69cdc6125f5b5f81c785f6b3fece98c5ecfa6de61432822e52a04985" \
                     "0d11802dc1050a60f6983ac3eedb8172ebc47e3cd50f1d97bfffe187b5"
        return [dispersy.get_member(public_key=master_key.decode("HEX"))]

    def initialize(self, tribler_session=None):
        super(TriblerChainCommunity, self).initialize(tribler_session)
        if tribler_session:
            self.notifier = tribler_session.notifier
            self.notifier.add_observer(self.on_tunnel_remove, NTFY_TUNNEL, [NTFY_REMOVE])

    def received_payment_message(self, payment_id):
        """
        We received a payment message originating from the market community. We set pending bytes so the validator
        passes when we receive the half block from the counterparty.

        Note that it might also be possible that the half block has been received already. That's why we revalidate
        the invalid messages again.
        """
        pub_key, seq_num, bytes_up, bytes_down = payment_id.split('.')
        pub_key = pub_key.decode('hex')
        pend = self.pending_bytes.get(pub_key)
        if not pend:
            self.pending_bytes[pub_key] = PendingBytes(int(bytes_up),
                                                       int(bytes_down),
                                                       None)
        else:
            pend.add(int(bytes_up), int(bytes_down))

        block_id = "%s.%s" % (pub_key.encode('hex'), seq_num)
        if block_id in self.pending_sign_messages:
            self._logger.debug("Signing pending half block")
            message = self.pending_sign_messages[block_id]
            self.sign_block(message.candidate, linked=message.payload.block)
            del self.pending_sign_messages[block_id]

    def should_sign(self, message):
        """
        Return whether we should sign the block in the passed message.
        @param message: the message containing a block we want to sign or not.
        """
        block = message.payload.block
        pend = self.pending_bytes.get(block.public_key)
        if not pend or not (pend.up - block.transaction['down'] >= 0 and pend.down - block.transaction['up'] >= 0):
            self.logger.info("Request block counter party does not have enough bytes pending.")

            # These bytes might have been bought on the market so we store this message and process it when we
            # receive a payment message that confirms we have bought these bytes.
            block_id = "%s.%s" % (block.public_key.encode('hex'), block.sequence_number)
            self.pending_sign_messages[block_id] = message

            return False
        return True

    @blocking_call_on_reactor_thread
    def get_statistics(self, public_key=None):
        """
        Returns a dictionary with some statistics regarding the local trustchain database
        :returns a dictionary with statistics
        """
        if public_key is None:
            public_key = self.my_member.public_key
        latest_block = self.persistence.get_latest(public_key)
        statistics = dict()
        statistics["id"] = public_key.encode("hex")
        interacts = self.persistence.get_num_unique_interactors(public_key)
        statistics["peers_that_pk_helped"] = interacts[0] if interacts[0] is not None else 0
        statistics["peers_that_helped_pk"] = interacts[1] if interacts[1] is not None else 0
        if latest_block:
            statistics["total_blocks"] = latest_block.sequence_number
            statistics["total_up"] = latest_block.transaction["total_up"]
            statistics["total_down"] = latest_block.transaction["total_down"]
            statistics["latest_block"] = dict(latest_block)

            # Set up/down
            statistics["latest_block"]["up"] = latest_block.transaction["up"]
            statistics["latest_block"]["down"] = latest_block.transaction["down"]
        else:
            statistics["total_blocks"] = 0
            statistics["total_up"] = 0
            statistics["total_down"] = 0
        return statistics

    @blocking_call_on_reactor_thread
    def on_tunnel_remove(self, subject, change_type, tunnel, candidate):
        """
        Handler for the remove event of a tunnel. This function will attempt to create a block for the amounts that
        were transferred using the tunnel.
        :param subject: Category of the notifier event
        :param change_type: Type of the notifier event
        :param tunnel: The tunnel that was removed (closed)
        :param candidate: The dispersy candidate with whom this node has interacted in the tunnel
        """
        from Tribler.community.tunnel.tunnel_community import Circuit, RelayRoute, TunnelExitSocket
        assert isinstance(tunnel, Circuit) or isinstance(tunnel, RelayRoute) or isinstance(tunnel, TunnelExitSocket), \
            "on_tunnel_remove() was called with an object that is not a Circuit, RelayRoute or TunnelExitSocket"
        assert isinstance(tunnel.bytes_up, int) and isinstance(tunnel.bytes_down, int),\
            "tunnel instance must provide byte counts in int"

        up = tunnel.bytes_up
        down = tunnel.bytes_down
        pk = candidate.get_member().public_key

        # If the transaction is not big enough we discard the bytes up and down.
        if up + down >= MIN_TRANSACTION_SIZE:
            # Tie breaker to prevent both parties from requesting
            if up > down or (up == down and self.my_member.public_key > pk):
                self.register_task("sign_%s" % tunnel.circuit_id,
                                   reactor.callLater(self.SIGN_DELAY, self.sign_block, candidate, pk,
                                                     {'up': tunnel.bytes_up, 'down': tunnel.bytes_down}))
            else:
                pend = self.pending_bytes.get(pk)
                if not pend:
                    task = self.register_task("cleanup_pending_%s" % tunnel.circuit_id,
                                              reactor.callLater(2 * 60, self.cleanup_pending, pk))
                    self.pending_bytes[pk] = PendingBytes(up, down, task)
                else:
                    pend.add(up, down)

    def cleanup_pending(self, public_key):
        self.pending_bytes.pop(public_key, None)

    @inlineCallbacks
    def unload_community(self):
        if self.notifier:
            self.notifier.remove_observer(self.on_tunnel_remove)
        for pk in self.pending_bytes:
            if self.pending_bytes[pk].clean is not None:
                self.pending_bytes[pk].clean.reset(0)
        yield super(TriblerChainCommunity, self).unload_community()

    def get_trust(self, member):
        """
        Get the trust for another member.
        Currently this is just the amount of MBs exchanged with them.

        :param member: the member we interacted with
        :type member: dispersy.member.Member
        :return: the trust value for this member
        :rtype: int
        """
        block = self.persistence.get_latest(member.public_key)
        if block:
            return block.transaction['total_up'] + block.transaction['total_down']
        else:
            # We need a minimum of 1 trust to have a chance to be selected in the categorical distribution.
            return 1


class TriblerChainCommunityCrawler(TriblerChainCommunity):
    """
    Extended TriblerChainCommunity that also crawls other TriblerChainCommunities.
    It requests the chains of other TrustChains.
    """

    # Time the crawler waits between crawling a new candidate.
    CrawlerDelay = 5.0

    def on_introduction_response(self, messages):
        super(TriblerChainCommunityCrawler, self).on_introduction_response(messages)
        for message in messages:
            self.send_crawl_request(message.candidate, message.candidate.get_member().public_key)

    def start_walking(self):
        self.register_task("take step", LoopingCall(self.take_step)).start(self.CrawlerDelay, now=False)
