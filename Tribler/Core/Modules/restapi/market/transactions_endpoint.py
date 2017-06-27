import json

from twisted.web import http

from Tribler.Core.Modules.restapi.market import BaseMarketEndpoint
from Tribler.community.market.core.message import TraderId
from Tribler.community.market.core.transaction import TransactionId, TransactionNumber


class TransactionsEndpoint(BaseMarketEndpoint):
    """
    This class handles requests regarding (past) transactions in the market community.
    """

    def getChild(self, path, request):
        return TransactionSpecificTraderEndpoint(self.session, path)

    def render_GET(self, request):
        """
        .. http:get:: /market/transactions

        A GET request to this endpoint will return all performed transactions in the market community.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/market/transactions

            **Example response**:

            .. sourcecode:: javascript

                {
                    "transactions": [{
                        "trader_id": "12c406358ba05e5883a75da3f009477e4ca699a9",
                        "order_number": 4,
                        "partner_trader_id": "34c406358ba05e5883a75da3f009477e4ca699a9",
                        "partner_order_number": 1,
                        "transaction_number": 3,
                        "price": 10,
                        "price_type": "MC",
                        "transferred_price": 5,
                        "quantity": 10,
                        "quantity_type": "BTC",
                        "transferred_quantity": 4,
                        "timestamp": 1493906434.627721,
                        "payment_complete": False
                    ]
                }
        """
        transactions = self.get_market_community().transaction_manager.find_all()
        return json.dumps({"transactions": [transaction.to_dictionary() for transaction in transactions]})


class TransactionSpecificTraderEndpoint(BaseMarketEndpoint):
    """
    This class handles requests for a specific transaction.
    """

    def __init__(self, session, path):
        BaseMarketEndpoint.__init__(self, session)
        self.transaction_trader_id = path

    def getChild(self, path, request):
        return TransactionSpecificNumberEndpoint(self.session, self.transaction_trader_id, path)


class TransactionSpecificNumberEndpoint(BaseMarketEndpoint):
    """
    This class handles requests for a transaction with a specific number.
    """

    def __init__(self, session, transaction_trader_id, path):
        BaseMarketEndpoint.__init__(self, session)
        self.transaction_trader_id = transaction_trader_id
        self.transaction_number = path

        child_handler_dict = {"payments": TransactionPaymentsEndpoint}
        for path, child_cls in child_handler_dict.iteritems():
            self.putChild(path, child_cls(self.session, self.transaction_trader_id, self.transaction_number))


class TransactionPaymentsEndpoint(BaseMarketEndpoint):
    """
    This class handles requests for the payments of a specific transaction.
    """

    def __init__(self, session, transaction_trader_id, transaction_number):
        BaseMarketEndpoint.__init__(self, session)
        self.transaction_trader_id = transaction_trader_id
        self.transaction_number = transaction_number

    def render_GET(self, request):
        """
        .. http:get:: /market/transactions/(string:trader_id)/(string:transaction_number)/payments

        A GET request to this endpoint will return all payments tied to a specific transaction.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/market/transactions/
                12c406358ba05e5883a75da3f009477e4ca699a9/3/payments

            **Example response**:

            .. sourcecode:: javascript

                {
                    "payments": [{
                        "trader_id": "12c406358ba05e5883a75da3f009477e4ca699a9",
                        "transaction_number": 3,
                        "price": 10,
                        "price_type": "MC",
                        "quantity": 10,
                        "quantity_type": "BTC",
                        "transferred_quantity": 4,
                        "payment_id": "abcd",
                        "address_from": "my_mc_address",
                        "address_to": "my_btc_address",
                        "timestamp": 1493906434.627721,
                    ]
                }
        """
        transaction_id = TransactionId(TraderId(self.transaction_trader_id),
                                       TransactionNumber(int(self.transaction_number)))
        transaction = self.get_market_community().transaction_manager.find_by_id(transaction_id)

        if not transaction:
            request.setResponseCode(http.NOT_FOUND)
            return json.dumps({"error": "transaction not found"})

        return json.dumps({"payments": [payment.to_dictionary() for payment in transaction.payments]})
