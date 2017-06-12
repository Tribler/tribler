TrustChain
==========

TrustChain is a tamper-resistent data structure that is used in Tribler to record community contributions. This blockchain-based distributed ledger can then be used to build a reputation mechanism that is able to identify free-riders. A basic implementation of TrustChain is available in our code base and available for other developers.

TrustChain is specifically designed to be transaction-agnostic which means that any transaction can be stored in TrustChain. In Tribler, this consists of the amount of uploaded and downloaded data.

Using TrustChain
----------------

Using TrustChain to store transaction is straightforward. Creating a new block is done by invoking the ``sign_block`` method of the community. The required arguments are the destination candidate (the counterparty of the transaction), your public key and the transaction itself, in the Python dictionary format. Note that this dictionary can only contain Python primitive types and no custom objects due to the serialization of the transaction when sending it to the other party.

Assuming that the transaction counterparty is online and the block is valid, the counterparty signs the block and sends it back where the ``received_half_block`` method is invoked, processing the received block.

Using TrustChain in your project
--------------------------------

To use TrustChain in your own projects, one can create a subclass of ``TrustChainCommunity`` or use the ``TrustChainCommunity`` directly. This should be enough for basic usage. For more information about communities, we reference the reader to `a Dispersy tutorial <http://dispersy.readthedocs.io/en/devel/usage.html#community>`_.

In order to implement custom transaction validation rules, a subclass of ``TrustChainBlock`` should be made and the ``BLOCK_CLASS`` variable in the ``TrustChainCommunity`` should be updated accordingly. By overriding the ``validate_transaction`` method, you can add your own custom validation rules.
