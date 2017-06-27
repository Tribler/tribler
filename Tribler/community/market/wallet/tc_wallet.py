from base64 import b64encode

from twisted.internet.defer import succeed, fail

from Tribler.community.market.wallet.wallet import Wallet, InsufficientFunds
from Tribler.dispersy.message import DelayPacketByMissingMember


MEGA_DIV = 1024 * 1024


class TrustchainWallet(Wallet):
    """
    This class is responsible for handling your wallet of TrustChain credits.
    """

    def __init__(self, tc_community):
        super(TrustchainWallet, self).__init__()

        self.tc_community = tc_community
        self.created = True
        self.check_negative_balance = True
        self.transaction_history = []

    def get_name(self):
        return 'Reputation'

    def get_identifier(self):
        return 'MC'

    def create_wallet(self, *args, **kwargs):
        raise RuntimeError("You cannot create a TrustChain wallet")

    def get_balance(self):
        latest_block = self.tc_community.persistence.get_latest(self.tc_community.my_member.public_key)
        total_up = latest_block.transaction["total_up"] / MEGA_DIV if latest_block else 0
        total_down = latest_block.transaction["total_down"] / MEGA_DIV if latest_block else 0
        return succeed({'available': total_up - total_down, 'pending': 0, 'currency': self.get_identifier()})

    def transfer(self, quantity, candidate):
        def on_balance(balance):
            if self.check_negative_balance and balance['available'] < quantity:
                return fail(InsufficientFunds())

            # Send the block
            if not candidate.get_member():
                return self.wait_for_intro_of_candidate(candidate).addCallback(
                    lambda _: self.send_signature(candidate, quantity))
            else:
                try:
                    return self.send_signature(candidate, quantity)
                except DelayPacketByMissingMember:
                    return self.wait_for_intro_of_candidate(candidate).addCallback(
                        lambda _: self.send_signature(candidate, quantity))

        return self.get_balance().addCallback(on_balance)

    def send_signature(self, candidate, quantity):
        transaction = {"up": 0, "down": int(quantity * MEGA_DIV)}
        self.tc_community.sign_block(candidate, candidate.get_member().public_key, transaction)
        latest_block = self.tc_community.persistence.get_latest(self.tc_community.my_member.public_key)
        txid = "%s.%s.%d.%d" % (latest_block.public_key.encode('hex'),
                                latest_block.sequence_number, 0, int(quantity * MEGA_DIV))

        self.transaction_history.append({
            'id': txid,
            'outgoing': True,
            'from': self.get_address(),
            'to': b64encode(candidate.get_member().public_key),
            'amount': quantity,
            'fee_amount': 0.0,
            'currency': self.get_identifier(),
            'timestamp': '',
            'description': ''
        })

        return succeed(txid)

    def wait_for_intro_of_candidate(self, candidate):
        self._logger.info("Sending introduction request in TrustChain to candidate %s", candidate)
        self.tc_community.add_discovered_candidate(candidate)
        new_candidate = self.tc_community.get_candidate(candidate.sock_addr)
        self.tc_community.create_introduction_request(new_candidate, False)
        return self.tc_community.wait_for_intro_of_candidate(new_candidate)

    def monitor_transaction(self, payment_id):
        """
        Monitor an incoming transaction with a specific id.
        """
        self.tc_community.received_payment_message(payment_id)
        block_id = '.'.join(payment_id.split('.')[:2])
        return self.tc_community.wait_for_signature_request(str(block_id))

    def get_address(self):
        return b64encode(self.tc_community.my_member.public_key)

    def get_transactions(self):
        return succeed(self.transaction_history)

    def min_unit(self):
        return 1
